"""Read-only W9 Datadog verification; never prints Datadog credentials."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

KEY_FILE = Path(r"D:\attt\APP_KEY.txt")
MONITOR_ID = "342734743"
WORKFLOW_ID = "47e95b24-db40-4cd5-b667-5b90e170b667"
BASE = "https://api.datadoghq.com"


def headers() -> dict[str, str]:
    values = {}
    for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip().upper()] = value.strip()
    api_key = values.get("API_KEY") or values.get("API_KEYS")
    app_key = values.get("APP_KEY")
    if not api_key or not app_key:
        raise RuntimeError("Datadog key labels are incomplete")
    return {"DD-API-KEY": api_key, "DD-APPLICATION-KEY": app_key, "Accept": "application/json"}


def get_json(url: str) -> dict:
    with urlopen(Request(url, headers=headers()), timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def read_metric(metric: str, now: int) -> dict:
    query = f"sum:{metric}{{farm:greenhouse_j,actuator:plc_pump}} by {{farm,actuator}}"
    url = BASE + "/api/v1/query?" + urlencode({"from": now - 900, "to": now, "query": query})
    data = get_json(url)
    series_rows = []
    for series in data.get("series", []):
        points = [[int(point[0]), float(point[1])] for point in series.get("pointlist", [])]
        series_rows.append({
            "scope": series.get("scope"),
            "peak_value": max((point[1] for point in points), default=None),
            "nonzero_points": [point for point in points if point[1] != 0],
            "latest_points": points[-5:],
        })
    return {
        "metric": metric,
        "series": series_rows,
    }


def main() -> dict:
    now = int(time.time())
    monitor = get_json(f"{BASE}/api/v1/monitor/{MONITOR_ID}?group_states=all")
    workflows = get_json(f"{BASE}/api/v2/workflows/{WORKFLOW_ID}/instances?page[size]=20")
    runs = []
    for row in workflows.get("data", []):
        attrs = row.get("attributes", {})
        source = attrs.get("source") or {}
        handle = source.get("handle") or {}
        source_payload = {}
        try:
            source_payload = json.loads(handle.get("payload") or "{}")
        except (TypeError, json.JSONDecodeError):
            pass
        runs.append({
            "id": row.get("id"),
            "status": (attrs.get("instanceStatus") or {}).get("displayName") or attrs.get("status"),
            "source_monitor_id": str(handle.get("id") or ""),
            "source_event_id": source_payload.get("id"),
            "source_event_time_utc": source_payload.get("date_happened"),
            "created_at": attrs.get("createdAt") or attrs.get("created_at"),
        })
    result = {
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "monitor": {
            "id": MONITOR_ID,
            "name": monitor.get("name"),
            "state": monitor.get("overall_state"),
            "state_modified_utc": monitor.get("overall_state_modified"),
            "groups": {
                str(key): (value.get("state") if isinstance(value, dict) else value)
                for key, value in (monitor.get("groups") or {}).items()
            },
        },
        "metrics": [
            read_metric("smiot.actuator.command_unacknowledged", now),
            read_metric("smiot.actuator.command_late_acknowledged", now),
        ],
        "workflow_id": WORKFLOW_ID,
        "workflow_runs": runs,
    }
    evidence = Path("outputs/evidence/w9_late_ack_20261112.json")
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    try:
        print(json.dumps(main(), indent=2, ensure_ascii=False))
    except (OSError, RuntimeError, HTTPError, URLError, TimeoutError) as exc:
        # Keep diagnostics sanitized: do not print request headers or key values.
        print(json.dumps({"status": "readback_failed", "error_type": type(exc).__name__}))
