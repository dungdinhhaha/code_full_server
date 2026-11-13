"""Apply a Datadog US API key to the SMIOT app without exposing it in SSM output."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import boto3


PARAMETER_NAME = "/smiot/datadog/api-key"
APP_PARAMETER_NAME = "/smiot/datadog/app-key"
REGION = "ap-southeast-2"
SITE = "datadoghq.com"
MONITOR_ID = os.getenv("SMIOT_DD_MONITOR_ID", "").strip()
WORKFLOW_ID = os.getenv("SMIOT_DD_WORKFLOW_ID", "").strip()
APP_ENV = Path("/etc/smiot/app.env")
AGENT_CONFIG = Path("/etc/datadog-agent/datadog.yaml")
RECOVERY_LOG = Path("/opt/smiot/logs/recovery/guarded_recovery.jsonl")
HEALTH_URL = "http://127.0.0.1:8080/healthz"


def get_parameter(name: str) -> str:
    response = boto3.client("ssm", region_name=REGION).get_parameter(Name=name, WithDecryption=True)
    key = response["Parameter"]["Value"].strip()
    if not key:
        raise RuntimeError("A Datadog credential parameter is empty")
    return key


def validate_key(key: str) -> None:
    request = urllib.request.Request(
        f"https://api.{SITE}/api/v1/validate",
        headers={"DD-API-KEY": key},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            valid = json.loads(response.read()).get("valid") is True
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Datadog key validation returned HTTP {exc.code}") from None
    except Exception as exc:
        raise RuntimeError(f"Datadog key validation failed ({type(exc).__name__})") from None
    if not valid:
        raise RuntimeError("Datadog rejected the configured API key")


def validate_app_key(api_key: str, app_key: str) -> None:
    request = urllib.request.Request(
        f"https://api.datadoghq.com/api/v2/workflows/{WORKFLOW_ID}/instances",
        headers={"DD-API-KEY": api_key, "DD-APPLICATION-KEY": app_key},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Datadog workflow read validation returned HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Datadog application key validation returned HTTP {exc.code}") from None
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Datadog application key validation failed ({type(exc).__name__})") from None


def validate_monitor(api_key: str, app_key: str) -> None:
    request = urllib.request.Request(
        f"https://api.datadoghq.com/api/v1/monitor/{MONITOR_ID}",
        headers={"DD-API-KEY": api_key, "DD-APPLICATION-KEY": app_key},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Datadog monitor validation returned HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Datadog monitor validation returned HTTP {exc.code}") from None
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Datadog monitor validation failed ({type(exc).__name__})") from None


def atomic_write(path: Path, content: str) -> None:
    old = path.stat()
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(temporary, old.st_uid, old.st_gid)
        os.chmod(temporary, stat.S_IMODE(old.st_mode))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def set_env_value(text: str, name: str, value: str) -> str:
    lines = text.splitlines()
    replacement = f"{name}={value}"
    found = False
    for index, line in enumerate(lines):
        if line.startswith(f"{name}="):
            lines[index] = replacement
            found = True
    if not found:
        lines.append(replacement)
    return "\n".join(lines) + "\n"


def env_value(text: str, name: str) -> str | None:
    for line in text.splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def set_agent_value(text: str, name: str, value: str) -> str:
    lines = text.splitlines()
    replacement = f'{name}: "{value}"'
    found = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith(f"{name}:"):
            lines[index] = replacement
            found = True
    if not found:
        lines.insert(0, replacement)
    return "\n".join(lines) + "\n"


def agent_value(text: str, name: str) -> str | None:
    for line in text.splitlines():
        if line.lstrip().startswith(f"{name}:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return None


def backup(path: Path) -> Path:
    folder = Path("/var/backups/smiot/datadog-telemetry")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(folder, 0o700)
    target = folder / f"{path.name}.{int(time.time())}.bak"
    shutil.copy2(path, target)
    os.chmod(target, 0o600)
    return target


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=True)


def wait_for_health(timeout: int = 60) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(HEALTH_URL, method="GET")
            with urllib.request.urlopen(request, timeout=3) as response:
                if 200 <= response.status < 300:
                    return True
        except Exception:
            time.sleep(2)
    return False


def wait_for_unit(unit: str, timeout: int = 30) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if run("systemctl", "is-active", unit, check=False).returncode == 0:
            return True
        time.sleep(1)
    return False


def main() -> None:
    if not MONITOR_ID or not WORKFLOW_ID:
        raise RuntimeError("Terraform must provide the current Datadog monitor and workflow IDs")
    key = get_parameter(PARAMETER_NAME)
    app_key = get_parameter(APP_PARAMETER_NAME)
    validate_key(key)
    validate_app_key(key, app_key)
    validate_monitor(key, app_key)

    if not APP_ENV.is_file() or not AGENT_CONFIG.is_file():
        raise RuntimeError("Required SMIOT or Datadog Agent configuration file is missing")

    app_before = APP_ENV.read_text(encoding="utf-8")
    agent_before = AGENT_CONFIG.read_text(encoding="utf-8")
    app_changed = (
        env_value(app_before, "DD_API_KEY") != key
        or env_value(app_before, "DD_APP_KEY") != app_key
        or env_value(app_before, "DD_SITE") != SITE
        or env_value(app_before, "DD_MONITOR_ID") != MONITOR_ID
        or env_value(app_before, "DD_WORKFLOW_ID") != WORKFLOW_ID
    )
    agent_changed = agent_value(agent_before, "api_key") != key or agent_value(agent_before, "site") != SITE
    app_backup = backup(APP_ENV) if app_changed else None
    agent_backup = backup(AGENT_CONFIG) if agent_changed else None
    bridge_state = run("systemctl", "is-active", "wokwi-bridge.service", check=False).stdout.strip()
    bridge_should_run = bridge_state in {"active", "activating"}
    bridge_active = bridge_state == "active"

    try:
        if app_changed:
            app_after = set_env_value(app_before, "DD_API_KEY", key)
            app_after = set_env_value(app_after, "DD_APP_KEY", app_key)
            app_after = set_env_value(app_after, "DD_SITE", SITE)
            app_after = set_env_value(app_after, "DD_MONITOR_ID", MONITOR_ID)
            app_after = set_env_value(app_after, "DD_WORKFLOW_ID", WORKFLOW_ID)
            atomic_write(APP_ENV, app_after)
        if agent_changed:
            agent_after = set_agent_value(agent_before, "api_key", key)
            agent_after = set_agent_value(agent_after, "site", SITE)
            atomic_write(AGENT_CONFIG, agent_after)

        if RECOVERY_LOG.exists():
            os.chmod(RECOVERY_LOG, 0o640)

        if agent_changed:
            run("datadog-agent", "configcheck")
            run("systemctl", "restart", "datadog-agent.service")
        if app_changed:
            run("systemctl", "restart", "smiot.service")
            if bridge_should_run:
                run("systemctl", "restart", "wokwi-bridge.service", check=False)
                bridge_active = wait_for_unit("wokwi-bridge.service")

        if not wait_for_health():
            raise RuntimeError("SMIOT health endpoint did not return success after the update")
        if run("systemctl", "is-active", "smiot.service", check=False).returncode != 0:
            raise RuntimeError("SMIOT service is not active after the update")
        if agent_changed and run("systemctl", "is-active", "datadog-agent.service", check=False).returncode != 0:
            raise RuntimeError("Datadog Agent is not active after the update")
    except Exception:
        if app_backup:
            shutil.copy2(app_backup, APP_ENV)
            os.chmod(APP_ENV, 0o600)
        if agent_backup:
            shutil.copy2(agent_backup, AGENT_CONFIG)
            os.chmod(AGENT_CONFIG, 0o640)
        if app_backup:
            run("systemctl", "restart", "smiot.service", check=False)
            if bridge_should_run:
                run("systemctl", "restart", "wokwi-bridge.service", check=False)
        if agent_backup:
            run("systemctl", "restart", "datadog-agent.service", check=False)
        raise

    print(
        "SMIOT_DATADOG_TELEMETRY_APPLIED "
        f"app_key_updated={str(app_changed).lower()} "
        f"agent_key_updated={str(agent_changed).lower()} "
        f"bridge_active={str(bridge_active).lower()} "
        "api_key_validated=true app_key_validated=true monitor_validated=true "
        "bridge_workflow_ids_aligned=true healthz=2xx"
    )


if __name__ == "__main__":
    main()
