"""Read-only Datadog snapshot for the incident black box UI.

Only HTTP GET is used. The app remains usable when Datadog is unavailable: every
part (monitor, metric, soil metric, monitor events, logs) is read in its own
``try`` and reports its own ``*_error`` reason, so one missing permission never
hides the other parts. Secrets are read only from the process environment and
are never returned to the caller or logged.

Reason codes (mapped to Vietnamese messages by ``components.ui_kit.dd_state``):
``keys_missing``, ``monitor_not_found``, ``http_<code>``, ``timeout``, ``network``,
``monitor_id_missing``.
"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_OVERVIEW_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
PAD_SECONDS = 900          # 15 minutes either side of the incident window
MAX_SERIES_POINTS = 120
SNAPSHOT_TTL = 15
OVERVIEW_TTL = 30
REQUEST_TIMEOUT = 4        # seconds, one request
SNAPSHOT_BUDGET = 12       # seconds, whole snapshot: the page must not hang when Datadog is slow
MAX_EVENTS = 10
MAX_LOGS = 5


class KeysMissing(Exception):
    """DD_API_KEY / DD_APP_KEY are not set in this process."""


def _keys() -> tuple[str, str]:
    return ((os.getenv("DD_API_KEY") or os.getenv("DATADOG_API_KEY") or "").strip(),
            (os.getenv("DD_APP_KEY") or os.getenv("DATADOG_APP_KEY") or "").strip())


def keys_configured() -> bool:
    api, app = _keys()
    return bool(api and app)


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    """GET only. Raises KeysMissing when the keys are not configured."""
    api, app = _keys()
    if not api or not app:
        raise KeysMissing()
    url = "https://api.datadoghq.com" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET", headers={
        "DD-API-KEY": api, "DD-APPLICATION-KEY": app, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as res:
        return json.loads(res.read().decode("utf-8"))


def reason_of(exc: BaseException, *, not_found: str | None = None) -> str:
    """Exception -> short reason code. Never includes keys or URLs."""
    if isinstance(exc, KeysMissing):
        return "keys_missing"
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 404 and not_found:
            return not_found
        return f"http_{exc.code}"
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(exc, urllib.error.URLError) and isinstance(getattr(exc, "reason", None), (socket.timeout, TimeoutError)):
        return "timeout"
    return "network"


def _metric_query(kind: str) -> str | None:
    return {
        "false_offline": "max:smiot.telemetry.status_mismatch{*}",
        "soil_humidity_flatline": "max:smiot.telemetry.sensor_flatline{*}",
        "service_down": "min:systemd.unit.active{unit:smiot.service}",
    }.get(kind)


def _epoch(value: Any) -> float | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def incident_window(incident: dict[str, Any], now: float) -> tuple[int, int]:
    """Metric window of the incident itself: opened minus pad, to recovery or now plus pad."""
    opened = _epoch(incident.get("opened_at") or incident.get("detected_at")) or now
    closed = _epoch(incident.get("recovered_at"))
    end_anchor = min(now, closed) if closed else now
    start = int(opened - PAD_SECONDS)
    end = int(min(now, end_anchor + PAD_SECONDS))
    if end <= start:
        end = start + PAD_SECONDS
    return start, end


def _iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _points(payload: Any) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for row in (payload or {}).get("series") or []:
        for point in row.get("pointlist") or []:
            if len(point) == 2 and point[1] is not None:
                pts.append((float(point[0]), float(point[1])))
    pts.sort()
    return pts


# ---------------------------------------------------------------------------
# Monitor overview (one call for the whole /incident page)
# ---------------------------------------------------------------------------
STATE_ORDER = ("Alert", "Warn", "No Data", "OK")


def summarize_monitors(rows: Any, ids: list[str]) -> dict[str, Any]:
    """Pure: list of monitor JSON -> {monitors: {id: {...}}, counts, missing_ids}.

    Counted monitors are the case monitors (by id) plus any monitor whose name contains SMIOT.
    """
    wanted = {str(i) for i in ids if i}
    monitors: dict[str, dict[str, Any]] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        mid = str(row.get("id") or "")
        name = str(row.get("name") or "")
        if mid in wanted or "smiot" in name.lower():
            thresholds = ((row.get("options") or {}).get("thresholds") or {})
            monitors[mid] = {
                "id": mid, "name": name or None,
                "overall_state": str(row.get("overall_state") or "Unknown"),
                "overall_state_modified": row.get("overall_state_modified"),
                "query": row.get("query"),
                "thresholds": thresholds if isinstance(thresholds, dict) else {},
            }
    counts: dict[str, int] = {state: 0 for state in STATE_ORDER}
    for info in monitors.values():
        counts[info["overall_state"]] = counts.get(info["overall_state"], 0) + 1
    return {"monitors": monitors, "counts": counts, "total": len(monitors),
            "missing_ids": sorted(wanted - set(monitors))}


def read_monitor_overview(ids: list[str] | tuple[str, ...] = ()) -> dict[str, Any]:
    """One GET /api/v1/monitor for the case monitors. Cached 30 s. Never raises."""
    id_list = [str(i) for i in ids if i]
    cache_key = ",".join(sorted(id_list))
    now = time.time()
    cached = _OVERVIEW_CACHE.get(cache_key)
    if cached and now - cached[0] < OVERVIEW_TTL:
        return cached[1]
    result: dict[str, Any] = {"available": False, "fetched_at": now, "monitors": {}, "counts": {}, "total": 0,
                              "missing_ids": id_list}
    try:
        rows = _get("/api/v1/monitor", {"page": 0, "page_size": 100})
        result.update(summarize_monitors(rows, id_list))
        result["available"] = True
    except Exception as exc:  # noqa: BLE001 - reported as a reason code
        result["reason"] = reason_of(exc)
    _OVERVIEW_CACHE[cache_key] = (now, result)
    return result


# ---------------------------------------------------------------------------
# Incident snapshot
# ---------------------------------------------------------------------------
def parse_events(payload: Any) -> list[dict[str, Any]]:
    """Pure: /api/v2/events response -> [{ts (epoch s), title, status}] oldest first."""
    out: list[dict[str, Any]] = []
    for item in (payload or {}).get("data") or []:
        attrs = (item or {}).get("attributes") or {}
        inner = attrs.get("attributes") or {}
        stamp = attrs.get("timestamp")
        ts = None
        if isinstance(stamp, str):
            try:
                ts = datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
            except ValueError:
                ts = None
        title = inner.get("title") or attrs.get("message") or (inner.get("evt") or {}).get("name")
        if ts is None or not title:
            continue
        out.append({"ts": ts, "title": str(title)[:200], "status": str(inner.get("status") or "")})
    out.sort(key=lambda e: e["ts"])
    return out[:MAX_EVENTS]


def parse_logs(payload: Any) -> dict[str, Any]:
    """Pure: /api/v2/logs/events response -> {rows: [{ts, service, message}], more}."""
    rows: list[dict[str, Any]] = []
    for item in (payload or {}).get("data") or []:
        attrs = (item or {}).get("attributes") or {}
        stamp = attrs.get("timestamp")
        ts = None
        if isinstance(stamp, str):
            try:
                ts = datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
            except ValueError:
                ts = None
        message = attrs.get("message")
        if message is None:
            continue
        rows.append({"ts": ts, "service": str(attrs.get("service") or ""), "message": str(message)[:140]})
    more = bool((((payload or {}).get("meta") or {}).get("page") or {}).get("after"))
    return {"rows": rows[:MAX_LOGS], "more": more}


def read_incident_snapshot(incident: dict[str, Any]) -> dict[str, Any]:
    """Current monitor state, plus metric points, monitor events and matching logs in this incident's own window."""
    monitor_id = str(incident.get("monitor_id") or "").strip()
    kind = str(incident.get("kind") or "")
    incident_id = str(incident.get("incident_id") or incident.get("_id") or "")
    cache_key = f"{incident_id}:{monitor_id}:{kind}"
    now = time.time()
    cached = _CACHE.get(cache_key)
    if cached and now - cached[0] < SNAPSHOT_TTL:
        return cached[1]
    deadline = now + SNAPSHOT_BUDGET
    result: dict[str, Any] = {"available": False, "monitor_id": monitor_id or None, "fetched_at": now,
                              "keys_configured": keys_configured()}
    if not monitor_id:
        result["reason"] = "monitor_id_missing"  # metric and logs below are still read

    def over_budget() -> bool:
        return time.time() >= deadline

    start, end = incident_window(incident, now)
    result.update({"window_start": start, "window_end": end})

    # 1. Monitor.
    if monitor_id:
        try:
            monitor = _get(f"/api/v1/monitor/{urllib.parse.quote(monitor_id)}") or {}
            thresholds = ((monitor.get("options") or {}).get("thresholds") or {})
            result.update({
                "available": True,
                "monitor_state": monitor.get("overall_state") or monitor.get("state") or "UNKNOWN",
                "monitor_name": monitor.get("name"), "monitor_query": monitor.get("query"),
                "thresholds": thresholds if isinstance(thresholds, dict) else {},
                "overall_state_modified": monitor.get("overall_state_modified"),
            })
        except Exception as exc:  # noqa: BLE001
            result["reason"] = reason_of(exc, not_found="monitor_not_found")

    # 2. Detection metric (independent: a vanished monitor can still have points).
    try:
        query = _metric_query(kind)
        if query and not over_budget():
            points = _points(_get("/api/v1/query", {"from": start, "to": end, "query": query}))
            result["metric"] = query
            if points:
                ts, value = points[-1]
                step = max(1, len(points) // MAX_SERIES_POINTS)
                result.update({"latest_value": value, "latest_at": ts / 1000,
                               "series": [[p[0] / 1000, p[1]] for p in points[::step]]})
    except Exception as exc:  # noqa: BLE001
        result["metric_error"] = reason_of(exc)

    # 3. Soil humidity as Datadog sees it.
    try:
        farm = str(incident.get("farm_key") or "").strip()
        node = incident.get("node_id")
        if kind.startswith("soil_humidity") and farm and farm != "_system" and not over_budget():
            tags = f"farm:{farm}" + (f",node:{node}" if node is not None else "")
            soil_query = f"avg:smiot.telemetry.soil_humidity{{{tags}}}"
            soil_points = _points(_get("/api/v1/query", {"from": start, "to": end, "query": soil_query}))
            s_step = max(1, len(soil_points) // MAX_SERIES_POINTS)
            result.update({"soil_query": soil_query,
                           "soil_series": [[p[0] / 1000, p[1]] for p in soil_points[::s_step]]})
    except Exception as exc:  # noqa: BLE001
        result["soil_error"] = reason_of(exc)

    # 4. Monitor transitions (Events API v2, GET).
    if monitor_id:
        try:
            if over_budget():
                raise TimeoutError()
            payload = _get("/api/v2/events", {"filter[query]": f"monitor_id:{monitor_id}",
                                              "filter[from]": _iso(start), "filter[to]": _iso(end),
                                              "sort": "timestamp", "page[limit]": MAX_EVENTS})
            result["events"] = parse_events(payload)
        except Exception as exc:  # noqa: BLE001
            result["events_error"] = reason_of(exc)

    # 5. Logs that contain the incident id (Logs list API v2, GET).
    if incident_id:
        try:
            if over_budget():
                raise TimeoutError()
            payload = _get("/api/v2/logs/events", {"filter[query]": f'"{incident_id}"',
                                                   "filter[from]": _iso(start), "filter[to]": _iso(end),
                                                   "sort": "-timestamp", "page[limit]": MAX_LOGS})
            parsed = parse_logs(payload)
            result["logs"], result["logs_more"] = parsed["rows"], parsed["more"]
        except Exception as exc:  # noqa: BLE001
            result["logs_error"] = reason_of(exc)

    _CACHE[cache_key] = (now, result)
    return result
