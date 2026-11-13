#!/usr/bin/env python3
"""External SMIOT probe, run OUTSIDE the app process (systemd timer, one-shot).

Why: telemetry_health.py lives inside main.py, so when smiot.service dies its metrics
stop (no-data). This probe keeps reporting from a separate process:

  smiot.external.app_up{farm,...}                1 if the app HTTP endpoint answers, else 0
  smiot.external.sample_age_seconds{farm,...}    age of the newest MongoDB telemetry sample
  smiot.external.mongo_up{...}                   1 if MongoDB answered the probe query (extra, optional)

Tags: service:smiot-smart-farm, env:demo (override with SMIOT_PROBE_ENV), farm:<key>.
Never put incident_id / message_id in tags.

Self-contained: stdlib + pymongo (already in requirements.txt). It does not import any app module.
Config comes from environment variables (systemd EnvironmentFile); it prints no secret.

Environment:
  SMIOT_PROBE_URL        default http://127.0.0.1:8080/healthz  (falls back to /login on 404/405)
  SMIOT_PROBE_FALLBACK_URL default http://127.0.0.1:8080/login
  SMIOT_PROBE_TIMEOUT    HTTP timeout seconds, default 4
  MONGODB_URI            required for sample age (use a read-only user); MONGODB_DATABASE default smiot
  MONGODB_TELEMETRY_COLLECTION default telemetry
  SMIOT_PROBE_FARMS      comma list, default greenhouse_a
  SMIOT_PROBE_ENV        default demo
  DD_DOGSTATSD_HOST/PORT default 127.0.0.1 / 8125
  SMIOT_PROBE_DRY_RUN    1 = print metrics, do not send UDP, do not write incidents

Optional incident recording (off by default; unchanged behaviour when unset):
  SMIOT_PROBE_RECORD_INCIDENT=1          open/close a service_down incident in operational_incidents
  SMIOT_PROBE_MONGODB_URI_WRITE          write-capable URI (user may only write operational_incidents)
  SMIOT_PROBE_STATE_FILE                 default /var/lib/smiot-probe/state.json (fail streak, open id)
  SMIOT_PROBE_DRILL=1                    mark the incident synthetic
  SMIOT_PROBE_MONITOR_ID                 current-org Datadog monitor ID (optional; omit link if unset)
  SMIOT_PROBE_WORKFLOW_ID                current-org Datadog workflow ID (optional; skip lookup/link if unset)
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

SERVICE_TAG = "service:smiot-smart-farm"
SEED_V1 = "smiot-demo-history-v1"  # old demo seed, excluded by the app as well
DEFAULT_STATE_FILE = "/var/lib/smiot-probe/state.json"
INCIDENT_ACTIVE = ["open", "holding", "recovering"]  # same statuses as service/incident_lifecycle.py
SERVICE_DOWN_FAILS = 2  # consecutive app_up==0 runs before opening
RECOVER_MAX_AGE_S = 180.0  # newest sample must be younger than this to close
DETECTOR_INPUT_FRESH_MAX_AGE_S = 180.0
MONITOR_ID_ENV = "SMIOT_PROBE_MONITOR_ID"
WORKFLOW_ID_ENV = "SMIOT_PROBE_WORKFLOW_ID"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def probe_http(url: str, fallback: str, timeout: float) -> tuple[int, int, str]:
    """Return (app_up, status_code, url_used). app_up=1 for status < 400."""
    tried = []
    for candidate in (url, fallback):
        if not candidate or candidate in tried:
            continue
        tried.append(candidate)
        req = urllib.request.Request(candidate, headers={"User-Agent": "smiot-external-probe/1"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed local URL)
                code = resp.status
        except urllib.error.HTTPError as exc:
            code = exc.code
            if code in (404, 405) and candidate == url and fallback:
                continue  # /healthz not available yet: use /login
        except (urllib.error.URLError, OSError, TimeoutError):
            code = 0
        return (1 if 200 <= code < 400 else 0), code, candidate
    return 0, 0, url


def newest_sample_age_seconds(farms: list[str]) -> tuple[dict[str, float | None], bool, str]:
    """Query MongoDB independently of the app. Returns ({farm: age|None}, mongo_up, error_kind)."""
    uri = _env("MONGODB_URI")
    if not uri:
        return {f: None for f in farms}, False, "no_mongodb_uri"
    try:
        from pymongo import MongoClient
    except ImportError:
        return {f: None for f in farms}, False, "pymongo_missing"
    client = MongoClient(uri, appname="smiot-external-probe", serverSelectionTimeoutMS=4000,
                         connectTimeoutMS=4000, socketTimeoutMS=6000)
    ages: dict[str, float | None] = {}
    try:
        client.admin.command("ping")
        coll = client[_env("MONGODB_DATABASE", "smiot")][_env("MONGODB_TELEMETRY_COLLECTION", "telemetry")]
        now = datetime.now(timezone.utc)
        for farm in farms:
            row = coll.find_one(
                {"meta.farm_key": farm, "source.demo_seed_version": {"$ne": SEED_V1}},
                {"timestamp": 1},
                sort=[("timestamp", -1)],
            )
            ts = row.get("timestamp") if row else None
            if ts is None:
                ages[farm] = None
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ages[farm] = max(0.0, (now - ts).total_seconds())
        return ages, True, ""
    except Exception as exc:  # report kind only, never the message (may contain URI)
        return {f: None for f in farms}, False, type(exc).__name__
    finally:
        client.close()


def send_dogstatsd(lines: list[str], host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto("\n".join(lines).encode("utf-8"), (host, port))
        return True
    except OSError:
        return False


def _load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(path: str, state: dict) -> bool:
    try:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _parse_ts(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def latest_workflow_execution_id(opened_at: datetime) -> tuple[str | None, str]:
    """Return (newest execution id started in [opened_at, now], reason). Never raises.

    Uses the same endpoint and headers as scripts/wokwi_datadog_bridge.py (DD_API_KEY, DD_APP_KEY, DD_SITE),
    via stdlib urllib so the probe stays self-contained. Reason is a short code, never the key or URL.
    """
    api_key = _env("DD_API_KEY")
    app_key = _env("DD_APP_KEY")
    if not api_key or not app_key:
        return None, "no_api_key"
    workflow_id = _env(WORKFLOW_ID_ENV)
    if not workflow_id:
        return None, "no_workflow_id"
    site = _env("DD_SITE", "datadoghq.com").removeprefix("https://").removesuffix("/")
    req = urllib.request.Request(
        f"https://api.{site}/api/v2/workflows/{workflow_id}/instances",
        headers={"DD-API-KEY": api_key, "DD-APPLICATION-KEY": app_key,
                 "Accept": "application/json", "User-Agent": "smiot-external-probe/1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 (fixed Datadog API host)
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        return None, f"http_{exc.code}"
    except Exception as exc:  # network, timeout, bad JSON: kind only
        return None, type(exc).__name__
    try:
        window_start = _as_utc(opened_at)
        window_end = datetime.now(timezone.utc)
        best_id, best_ts = None, None
        for item in (payload.get("data") or []):
            ts = _parse_ts((item.get("attributes") or {}).get("startTime"))
            if ts is None or ts < window_start or ts > window_end:
                continue
            if best_ts is None or ts > best_ts:
                best_id, best_ts = item.get("id"), ts
        return (str(best_id), "found") if best_id else (None, "none_in_window")
    except Exception as exc:
        return None, type(exc).__name__


def update_service_down_incident(app_up: int, http_status: int, url_path: str,
                                 newest_age: float | None, farm_key: str) -> dict:
    """Open service_down after N failed runs (app dead, Mongo alive); close when app and fresh sample are back.

    Writes only to operational_incidents with the write URI. Returns keys to merge into the JSON record.
    Never prints the URI; errors are reported by exception type name only.
    """
    if _env("SMIOT_PROBE_RECORD_INCIDENT") != "1":
        return {}
    uri = _env("SMIOT_PROBE_MONGODB_URI_WRITE")
    if not uri:
        return {"incident_action": "skipped", "incident_error": "no_write_uri"}
    state_path = _env("SMIOT_PROBE_STATE_FILE", DEFAULT_STATE_FILE)
    state = _load_state(state_path)
    try:
        fails = int(state.get("app_fail_streak", 0) or 0)
    except (TypeError, ValueError):
        fails = 0
    fails = fails + 1 if app_up == 0 else 0
    open_id = state.get("service_down_incident_id") or None
    action = "none"
    error = ""
    client = None
    try:
        from pymongo import MongoClient
        client = MongoClient(uri, appname="smiot-external-probe-write", serverSelectionTimeoutMS=4000,
                             connectTimeoutMS=4000, socketTimeoutMS=6000)
        incidents = client[_env("MONGODB_DATABASE", "smiot")]["operational_incidents"]
        now = datetime.now(timezone.utc)
        if app_up == 0 and fails >= SERVICE_DOWN_FAILS and not open_id:
            existing = incidents.find_one(
                {"kind": "service_down", "farm_key": "_system", "node_id": None, "status": {"$in": INCIDENT_ACTIVE}},
                {"_id": 1}, sort=[("opened_at", -1)])
            if existing:
                open_id = str(existing["_id"])
                action = "already_open"
            else:
                new_id = f"INC-SMIOT-{now:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8].upper()}"
                incident_doc = {
                    "_id": new_id, "incident_id": new_id, "kind": "service_down", "status": "open",
                    "farm_key": "_system", "node_id": None,
                    "synthetic": _env("SMIOT_PROBE_DRILL") == "1",
                    "opened_by": "external_probe", "opened_at": now, "detected_at": now,
                    "details": {"http_status": http_status, "url_path": url_path},
                    "timeline": [{"at": now, "event": "opened", "by": "external_probe"}],
                }
                # IDs are organization-specific. Omit links unless provisioned for
                # this Datadog org; never stamp incidents with a stale org's IDs.
                monitor_id = _env(MONITOR_ID_ENV)
                workflow_id = _env(WORKFLOW_ID_ENV)
                if monitor_id:
                    incident_doc["monitor_id"] = monitor_id
                if workflow_id:
                    incident_doc["workflow_id"] = workflow_id
                incidents.insert_one(incident_doc)
                open_id = new_id
                action = "opened"
        elif app_up == 1 and open_id:
            if newest_age is not None and newest_age < RECOVER_MAX_AGE_S:
                set_fields: dict = {"status": "recovered", "recovered_at": now, "updated_at": now,
                                    "recovery_verification": {"http_status": http_status,
                                                              "newest_sample_age_s": round(newest_age, 1)}}
                # Optional link to the investigation workflow; a failure here never blocks the close.
                try:
                    doc = incidents.find_one({"_id": open_id}, {"opened_at": 1})
                    opened_at = (doc or {}).get("opened_at")
                    if isinstance(opened_at, datetime):
                        exec_id, lookup = latest_workflow_execution_id(opened_at)
                        if exec_id:
                            set_fields["last_workflow_execution_id"] = exec_id
                    else:
                        lookup = "no_opened_at"
                except Exception as exc:
                    lookup = type(exc).__name__
                if lookup != "found":
                    print(json.dumps({"event": "smiot.external_probe.workflow_lookup", "result": lookup}),
                          file=sys.stderr)
                res = incidents.update_one(
                    {"_id": open_id, "status": {"$in": INCIDENT_ACTIVE}},
                    {"$set": set_fields,
                     "$push": {"timeline": {"at": now, "event": "recovered", "by": "external_probe"}}})
                action = "recovered" if res.modified_count == 1 else "already_closed"
                open_id = None
            else:
                action = "waiting_fresh_sample"
    except Exception as exc:  # type name only; message may contain the URI
        error = type(exc).__name__
    finally:
        if client is not None:
            client.close()
    state["app_fail_streak"] = fails
    if open_id:
        state["service_down_incident_id"] = open_id
    else:
        state.pop("service_down_incident_id", None)
    state_ok = _save_state(state_path, state)
    out: dict = {"incident_action": action, "app_fail_streak": fails}
    if error:
        out["incident_error"] = error
    if not state_ok:
        out["state_error"] = "write_failed"
    return out


def main() -> int:
    url = _env("SMIOT_PROBE_URL", "http://127.0.0.1:8080/healthz")
    fallback = _env("SMIOT_PROBE_FALLBACK_URL", "http://127.0.0.1:8080/login")
    try:
        timeout = float(_env("SMIOT_PROBE_TIMEOUT", "4"))
    except ValueError:
        print(json.dumps({"event": "smiot.external_probe", "error": "invalid_timeout"}))
        return 2
    farms = [f.strip() for f in _env("SMIOT_PROBE_FARMS", "greenhouse_a").split(",") if f.strip()]
    env_tag = f"env:{_env('SMIOT_PROBE_ENV', 'demo')}"
    if not farms:
        print(json.dumps({"event": "smiot.external_probe", "error": "no_farms"}))
        return 2

    started = time.monotonic()
    app_up, status, used_url = probe_http(url, fallback, timeout)
    ages, mongo_up, mongo_err = newest_sample_age_seconds(farms)

    lines = []
    for farm in farms:
        tags = f"#{SERVICE_TAG},{env_tag},farm:{farm}"
        lines.append(f"smiot.external.app_up:{app_up}|g|{tags}")
        if ages.get(farm) is not None:  # no sample_age when Mongo/sample unavailable -> monitor sees no-data
            lines.append(f"smiot.external.sample_age_seconds:{ages[farm]:.1f}|g|{tags}")
            # Independent watchdog context: this process reads Mongo directly,
            # so it can still report input freshness when smiot.service is down.
            fresh = int(ages[farm] <= DETECTOR_INPUT_FRESH_MAX_AGE_S)
            lines.append(f"smiot.external.detector_input_fresh:{fresh}|g|{tags},detector:agronomic_advisory")
        else:
            # Keep this metric absent when Mongo has no usable sample; no-data
            # semantics are safer than emitting a fabricated zero.
            pass
    lines.append(f"smiot.external.mongo_up:{1 if mongo_up else 0}|g|#{SERVICE_TAG},{env_tag}")

    dry = _env("SMIOT_PROBE_DRY_RUN") == "1"
    sent = False if dry else send_dogstatsd(lines, _env("DD_DOGSTATSD_HOST", "127.0.0.1"),
                                            int(_env("DD_DOGSTATSD_PORT", "8125") or "8125"))
    record = {
        "event": "smiot.external_probe",
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "app_up": app_up,
        "http_status": status,
        "url_path": urllib.parse.urlparse(used_url).path,
        "mongo_up": mongo_up,
        "mongo_error_kind": mongo_err,
        "sample_age_seconds": {k: (round(v, 1) if v is not None else None) for k, v in ages.items()},
        "dogstatsd_sent": sent,
        "dry_run": dry,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }
    if dry:
        if _env("SMIOT_PROBE_RECORD_INCIDENT") == "1":
            record["incident_action"] = "dry_run_skipped"
    else:
        record.update(update_service_down_incident(app_up, status, urllib.parse.urlparse(used_url).path,
                                                   ages.get(farms[0]), farms[0]))
    print(json.dumps(record, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
