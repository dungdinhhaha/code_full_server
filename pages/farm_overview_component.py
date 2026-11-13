"""Home page data layer and views, all read from MongoDB.

Every query runs in a worker thread through ``run.io_bound`` (see ``pages/home.py``),
is cached for a few seconds and keeps the last good result when a new read fails, so
the page can say "dữ liệu cũ" instead of going blank. Nothing here invents a value:
a channel with no sample stays empty and says so.
"""

from __future__ import annotations

import math
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from nicegui import app, ui

from components.theme import CHART
from components.ui_kit import (
    as_utc, command_chain, echart_base, fmt_age, fmt_num, fmt_time, panel, range_pills,
    source_note, state_panel, stat, stats, status_chip, VN_TZ,
)
from service import auth
from service.agronomic_thresholds import THRESHOLDS, classify_advisory, soil_moisture_calibration_note
from service.farm_registry import FARM_KEYS, FARM_LABELS
from service.incident_blackbox import ACTIVE_STATUSES
from service.mongodb_store import database
from service.telemetry_health import _setting, compute_node_status

LEVEL_TEXT = {"ok": "Bình thường", "watch": "Cần theo dõi", "act": "Cần xử lý", "none": "Chưa đủ dữ liệu"}
LEVEL_MARK = {"ok": "●", "watch": "▲", "act": "■", "none": "○"}
LEVEL_RANK = {"act": 0, "watch": 1, "none": 2, "ok": 3}
CHANNEL_NAME = {"water": "Kênh pH và EC nước", "flow": "Kênh lưu lượng",
                "drain_sensor": "Kênh thoát nước", "ventilation_feedback": "Kênh quạt"}
_DEMO_SEEDS = ["smiot-demo-history-v1", "smiot-demo-history-v2"]


# ── access ────────────────────────────────────────────────────────────

def _allowed_farms() -> list[str]:
    role = app.storage.user.get("role", "viewer")
    user_id = app.storage.user.get("user_id")
    if role == "admin":
        return list(FARM_KEYS)
    if user_id is None:
        return []
    try:
        permitted = set(auth.get_user_farms(int(user_id)))
    except Exception:
        return []
    return [farm for farm in FARM_KEYS if farm in permitted]


def can_open_incident() -> bool:
    """Same rule as pages/incident.py: admin or the manage_users permission."""
    permissions = app.storage.user.get("permissions", []) or []
    return app.storage.user.get("role") == "admin" or "manage_users" in permissions


# ── cache that survives a failed read ────────────────────────────────

_CACHE: dict[Any, dict] = {}
_KEY_LOCKS: dict[Any, threading.Lock] = {}
_GUARD = threading.Lock()


def _cached(key: Any, ttl: float, fn: Callable, *args: Any) -> dict:
    """Run ``fn(*args)`` at most once per ``ttl`` seconds.

    Returns {"value", "read_at", "stale", "error"}. When a read fails the last good
    value is kept and marked stale (``read_at`` stays the time it was really read).
    """
    with _GUARD:
        entry = _CACHE.get(key)
        lock = _KEY_LOCKS.setdefault(key, threading.Lock())
    if entry and time.monotonic() - entry["mono"] < ttl:
        return entry["out"]
    with lock:
        entry = _CACHE.get(key)
        if entry and time.monotonic() - entry["mono"] < ttl:
            return entry["out"]
        try:
            out = {"value": fn(*args), "read_at": datetime.now(timezone.utc), "stale": False, "error": None}
            mono = time.monotonic()
        except Exception as exc:
            message = f"Không đọc được dữ liệu ({type(exc).__name__})"
            prior = (entry or {}).get("out")
            if prior and prior.get("value") is not None:
                out = {**prior, "stale": True, "error": message}
            else:
                out = {"value": None, "read_at": None, "stale": False, "error": message}
            # Retry soon, but not on every 2 s tick.
            mono = time.monotonic() - ttl + min(ttl, 5.0)
        _CACHE[key] = {"mono": mono, "out": out}
        return out


# ── latest samples, incidents, notices (per farm) ─────────────────────

def _real_samples(extra: dict) -> dict:
    return {**extra, "source.demo_seed_key": {"$exists": False},
            "source.demo_seed_version": {"$nin": _DEMO_SEEDS}}


def _aggregate_farms(farm_keys: list[str]) -> list[dict]:
    """Fetch latest real Mongo sample per farm/signal/device plus related events."""
    db = database()
    by_farm = {farm: {"farm_key": farm, "samples": [], "incidents": [], "notices": []}
               for farm in farm_keys}
    # One farm/measurement pair per query so the compound index on
    # (meta.farm_key, meta.measurement_type, timestamp) serves each latest-sample scan.
    measurements = ("node", "flow", "water", "drain_sensor", "ventilation_feedback", "plc", "inverter")
    for farm in farm_keys:
        latest_by_source: dict[tuple[str, str, str], dict] = {}
        for measurement in measurements:
            cursor = db.telemetry.find(
                _real_samples({"meta.farm_key": farm, "meta.measurement_type": measurement}),
                {"timestamp": 1, "meta": 1, "readings": 1, "source": 1, "_id": 0},
            ).sort("timestamp", -1).limit(80).max_time_ms(4000)
            for sample in cursor:
                meta, source = sample.get("meta") or {}, sample.get("source") or {}
                node = meta.get("node_id", source.get("node_id"))
                device = source.get("device_id", meta.get("source_table", ""))
                key = (measurement, str(node or ""), str(device or ""))
                latest_by_source.setdefault(key, sample)  # newest first
        by_farm[farm]["samples"].extend(latest_by_source.values())

    incidents = db.operational_incidents.find(
        {"farm_key": {"$in": farm_keys}, "status": {"$in": ACTIVE_STATUSES}},
        {"_id": 1, "farm_key": 1, "incident_id": 1, "kind": 1, "status": 1, "opened_at": 1,
         "lot_id": 1, "node_id": 1},
    ).sort("opened_at", -1).limit(len(farm_keys) * 8).max_time_ms(4000)
    for incident in incidents:
        farm = incident.get("farm_key")
        if farm in by_farm and len(by_farm[farm]["incidents"]) < 8:
            incident["incident_id"] = incident.get("incident_id") or incident.get("_id")
            by_farm[farm]["incidents"].append(incident)

    notices = db.notifications.find(
        {"farm_key": {"$in": farm_keys}, "source": {"$ne": "demo_seed"}},
        {"_id": 0, "farm_key": 1, "message": 1, "category": 1, "severity": 1, "created_at": 1,
         "node_id": 1, "advisory_id": 1},
    ).sort("created_at", -1).limit(len(farm_keys) * 30).max_time_ms(4000)
    per_farm_notices = {farm: 0 for farm in farm_keys}
    for notice in notices:
        farm = notice.get("farm_key")
        if farm in by_farm and per_farm_notices[farm] < 30:
            by_farm[farm]["notices"].append(notice)
            per_farm_notices[farm] += 1
    return list(by_farm.values())


def _aggregate_unscoped_notices() -> list[dict]:
    """Fetch system-level notices without associating them with a farm."""
    db = database()
    notices = db.notifications.find(
        {"farm_key": {"$in": [None, ""]}, "source": {"$ne": "demo_seed"}},
        {"_id": 0, "farm_key": 1, "message": 1, "category": 1, "severity": 1, "created_at": 1,
         "node_id": 1, "advisory_id": 1},
    ).sort("created_at", -1).limit(30)
    result = []
    for notice in notices:
        # Missing and empty farm keys remain explicitly unscoped in the view.
        notice["farm_key"] = None
        result.append(notice)
    return result


def _ts(sample: dict | None) -> datetime | None:
    return as_utc((sample or {}).get("timestamp"))


def _sample_index(row: dict) -> dict[tuple[str, int | None], list[dict]]:
    out: dict[tuple[str, int | None], list[dict]] = {}
    for sample in row.get("samples", []):
        meta, source = sample.get("meta") or {}, sample.get("source") or {}
        kind = str(meta.get("measurement_type") or "")
        node = meta.get("node_id", source.get("node_id"))
        try:
            node = int(node) if node is not None else None
        except (TypeError, ValueError):
            node = None
        out.setdefault((kind, node), []).append(sample)
    return out


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _latest(samples: list[dict]) -> dict | None:
    return max(samples, key=lambda s: _ts(s) or datetime.min.replace(tzinfo=timezone.utc), default=None)


def _latest_with(index: dict, kind: str, field: str, node: int | None = None) -> dict | None:
    return _latest([s for s in index.get((kind, node), [])
                    if _num((s.get("readings") or {}).get(field)) is not None])


def _value(sample: dict | None, field: str) -> float | None:
    return _num(((sample or {}).get("readings") or {}).get(field))


def _node_state(index: dict, node_id: int, now: datetime) -> dict:
    sample = _latest(index.get(("node", node_id), []))
    provenance = (sample or {}).get("source") or {}
    status = (compute_node_status(_ts(sample), now, last_sequence=provenance.get("sequence"),
                                  boot_id=provenance.get("boot_id"))
              if sample else {"status": "UNKNOWN", "age_s": None})
    return {"sample": sample, "status": status}


def _channel_freshness(sample: dict | None, expected_interval_s: float, now: datetime) -> dict:
    stamp = _ts(sample)
    if stamp is None:
        return {"status": "UNKNOWN", "age_s": None}
    age_s = max(0.0, (now - stamp).total_seconds())
    fresh_s = max(45.0, expected_interval_s * 1.5)
    stale_s = max(fresh_s, expected_interval_s * 3.0)
    state = "ONLINE" if age_s <= fresh_s else "STALE" if age_s <= stale_s else "OFFLINE"
    return {"status": state, "age_s": round(age_s, 1)}


def stale_limits() -> tuple[int, int]:
    """Node ONLINE/STALE/OFFLINE limits in seconds, the same ones compute_node_status uses."""
    stale = _setting("SMIOT_TELEMETRY_STALE_SECONDS", 90)
    return stale, max(stale, _setting("SMIOT_NODE_OFFLINE_SECONDS", 300))


def _dur(seconds: float | None) -> str:
    if seconds is None:
        return "chưa rõ"
    s = int(seconds)
    if s < 60:
        return f"{s} giây"
    if s < 3600:
        return f"{s // 60} phút"
    if s < 86400:
        return f"{s // 3600} giờ {(s % 3600) // 60} phút"
    return f"{s // 86400} ngày"


_INCIDENT_LABEL = {
    "soil_humidity_flatline": "Cảm biến đất đứng số", "false_offline": "Báo offline sai",
    "service_down": "Ứng dụng ngừng hoạt động", "water_overrun": "Lưu lượng vượt giới hạn",
    "pipe_leak": "Nghi rò đường ống", "ventilation_stuck": "Quạt không phản hồi",
    "soil_humidity_spike": "Độ ẩm đất tăng bất thường",
    "soil_humidity_out_of_range": "Số đo đất ngoài khoảng", "scenario_event": "Sự kiện kịch bản",
}


def _incident_label(kind: str | None) -> str:
    return _INCIDENT_LABEL.get(str(kind), "Sự cố")


def _assess(nodes: list[dict], channels: dict, incidents: list[dict]) -> tuple[str, list[str]]:
    """Level and the real reasons behind it.

    act   : an incident is open, or a node has been silent past the offline limit.
    watch : a node or channel is late, or a reading is outside the advisory band.
    none  : no act/watch reason and a node has never sent a sample.
    ok    : both nodes are fresh and nothing above applies.
    """
    stale_s, offline_s = stale_limits()
    causes: list[tuple[int, str]] = []
    for incident in incidents:
        causes.append((0, f"Sự cố đang mở: {_incident_label(incident.get('kind'))}, "
                          f"từ {fmt_time(incident.get('opened_at'))}"))
    for number, node in enumerate(nodes, 1):
        status, age = node["status"].get("status"), node["status"].get("age_s")
        if status == "OFFLINE":
            causes.append((0, f"Node {number} mất tín hiệu {_dur(age)} (ngưỡng {offline_s} giây)"))
        elif status == "STALE":
            causes.append((1, f"Node {number} chậm {_dur(age)} (ngưỡng {stale_s} giây)"))
        elif status == "UNKNOWN":
            causes.append((2, f"Node {number} chưa có mẫu nào"))
        if node["sample"] is not None and status in ("ONLINE", "STALE"):
            readings = node["sample"].get("readings") or {}
            for metric, field, label, unit in (("air_temp_c", "air_temp", "nhiệt độ", "°C"),
                                               ("air_humidity_pct", "air_hum", "ẩm không khí", "%")):
                value = _num(readings.get(field))
                advice = classify_advisory(metric, value)
                if value is not None and advice["state"] == "advisory":
                    causes.append((1, f"Node {number}: {label} {fmt_num(value)} {unit}, "
                                      f"ngoài ngưỡng {fmt_num(advice['threshold'], 0)} {unit}"))
    for kind, channel in channels.items():
        if channel["status"].get("status") in ("STALE", "OFFLINE"):
            causes.append((1, f"{CHANNEL_NAME.get(kind, kind)} chậm {_dur(channel['status'].get('age_s'))}"))
    causes.sort(key=lambda item: item[0])
    ranks = {rank for rank, _ in causes}
    level = "act" if 0 in ranks else "watch" if 1 in ranks else "none" if 2 in ranks else "ok"
    return level, [text for _, text in causes]


def _prepared(rows: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    prepared = []
    for row in rows:
        index = _sample_index(row)
        nodes = [_node_state(index, n, now) for n in (1, 2)]
        channels = {}
        for kind, field, interval in (("water", "ph_val", 300), ("flow", "flow_f1", 60),
                                      ("drain_sensor", "drain_l", 300),
                                      ("ventilation_feedback", "state", 15)):
            sample = _latest_with(index, kind, field)
            channels[kind] = {"sample": sample, "status": _channel_freshness(sample, interval, now)}
        incidents = row.get("incidents") or []
        level, causes = _assess(nodes, channels, incidents)
        stamps = [_ts(node["sample"]) for node in nodes if node["sample"] is not None]
        newest = max((s for s in stamps if s), default=None)
        prepared.append({
            "farm_key": row["farm_key"], "label": FARM_LABELS.get(row["farm_key"], row["farm_key"]),
            "index": index, "nodes": nodes, "channels": channels, "incidents": incidents,
            "notices": row.get("notices", []), "level": level, "causes": causes,
            "newest": newest, "age_s": None if newest is None else max(0.0, (now - newest).total_seconds()),
        })
    return prepared


def _fleet_build(farm_keys: tuple[str, ...]) -> dict:
    rows = _aggregate_farms(list(farm_keys))
    try:
        unscoped = _aggregate_unscoped_notices()
    except Exception:
        unscoped = []
    return {"cards": _prepared(rows), "unscoped": unscoped}


def get_fleet(farm_keys: tuple[str, ...]) -> dict:
    if not farm_keys:
        return {"value": {"cards": [], "unscoped": []}, "read_at": datetime.now(timezone.utc),
                "stale": False, "error": None}
    return _cached(("fleet", farm_keys), 10.0, _fleet_build, farm_keys)


# ── time series (aggregation pipelines on the telemetry time-series collection) ──

_BIN_MINUTES = {1: 1, 6: 5, 24: 15}


def _ms(value: Any) -> int | None:
    stamp = as_utc(value)
    return None if stamp is None else int(stamp.timestamp() * 1000)


def _bucket(hours: int) -> dict:
    return {"$dateTrunc": {"date": "$timestamp", "unit": "minute", "binSize": _BIN_MINUTES.get(hours, 5)}}


def _fleet_series_query(farm_keys: tuple[str, ...], hours: int) -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    pipeline = [
        {"$match": _real_samples({"meta.farm_key": {"$in": list(farm_keys)}, "meta.measurement_type": "node",
                                  "timestamp": {"$gte": since}})},
        {"$group": {"_id": {"farm": "$meta.farm_key", "t": _bucket(hours)},
                    "air_temp": {"$avg": "$readings.air_temp"},
                    "soil_hum": {"$avg": "$readings.soil_hum"}, "n": {"$sum": 1}}},
        {"$sort": {"_id.t": 1}},
    ]
    out: dict[str, dict[str, list]] = {"temp": {}, "soil": {}}
    count = 0
    for row in database().telemetry.aggregate(pipeline, maxTimeMS=8000):
        farm, stamp = row["_id"]["farm"], _ms(row["_id"]["t"])
        if stamp is None:
            continue
        count += int(row.get("n") or 0)
        for target, field in (("temp", "air_temp"), ("soil", "soil_hum")):
            value = _num(row.get(field))
            if value is not None:
                out[target].setdefault(farm, []).append([stamp, round(value, 2)])
    return {**out, "hours": hours, "bin": _BIN_MINUTES.get(hours, 5), "samples": count}


def get_fleet_series(farm_keys: tuple[str, ...], hours: int) -> dict:
    return _cached(("fleet-series", farm_keys, hours), 25.0, _fleet_series_query, farm_keys, hours)


_SERIES_FIELDS = ("air_temp", "air_hum", "soil_hum", "soil_temp", "ec", "ph_val", "ec_val", "flow_f1", "flow_f2")


def _farm_series_query(farm_key: str, hours: int) -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    group: dict[str, Any] = {"_id": {"m": "$meta.measurement_type", "node": "$meta.node_id", "t": _bucket(hours)},
                             "n": {"$sum": 1}}
    for field in _SERIES_FIELDS:
        group[field] = {"$avg": f"$readings.{field}"}
    pipeline = [
        {"$match": _real_samples({"meta.farm_key": farm_key, "meta.measurement_type": {"$in": ["node", "water", "flow"]},
                                  "timestamp": {"$gte": since}})},
        {"$group": group},
        {"$sort": {"_id.t": 1}},
    ]
    series: dict[str, list] = {}
    count = 0
    for row in database().telemetry.aggregate(pipeline, maxTimeMS=8000):
        ident, stamp = row["_id"], _ms(row["_id"]["t"])
        if stamp is None:
            continue
        count += int(row.get("n") or 0)
        measurement, node = ident.get("m"), ident.get("node")
        for field in _SERIES_FIELDS:
            value = _num(row.get(field))
            if value is None:
                continue
            if measurement == "node" and field in ("air_temp", "air_hum", "soil_hum", "soil_temp", "ec"):
                name = f"{field}:{int(node) if node is not None else 0}"
            elif measurement == "water" and field in ("ph_val", "ec_val"):
                name = field
            elif measurement == "flow" and field in ("flow_f1", "flow_f2"):
                name = field
            else:
                continue
            series.setdefault(name, []).append([stamp, round(value, 3)])
    return {"series": series, "hours": hours, "bin": _BIN_MINUTES.get(hours, 5), "samples": count}


def get_farm_series(farm_key: str, hours: int) -> dict:
    return _cached(("farm-series", farm_key, hours), 25.0, _farm_series_query, farm_key, hours)


# ── incidents (24 h), pending review, per-farm commands, weather ──────

def _events_query(farm_keys: tuple[str, ...]) -> dict:
    db = database()
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    incidents = []
    cursor = db.operational_incidents.find(
        {"farm_key": {"$in": list(farm_keys)},
         "$or": [{"opened_at": {"$gte": since}}, {"status": {"$in": ACTIVE_STATUSES}}]},
        {"_id": 1, "incident_id": 1, "farm_key": 1, "kind": 1, "status": 1, "opened_at": 1,
         "recovered_at": 1, "node_id": 1},
    ).sort("opened_at", -1).limit(200).max_time_ms(5000)
    for incident in cursor:
        incident["incident_id"] = str(incident.get("incident_id") or incident.get("_id"))
        incidents.append(incident)
    status_by_id = {item["incident_id"]: item.get("status") for item in incidents}

    # Review queue: Datadog workflow notices that say a human still has to look
    # (escalated, waiting for verification) or whose verification is pending.
    # The app stores no separate approval record, so nothing here is approvable.
    pending = []
    cursor = db.notifications.find(
        {"source": "datadog_workflow", "created_at": {"$gte": since},
         "farm_key": {"$in": list(farm_keys) + [None, ""]},
         "$or": [{"workflow_status": {"$in": ["escalated", "pending_verification"]}},
                 {"verification_status": "pending"}]},
        {"_id": 0, "message": 1, "farm_key": 1, "incident_id": 1, "severity": 1, "created_at": 1,
         "workflow_status": 1, "verification_status": 1, "workflow_name": 1, "workflow_run_id": 1},
    ).sort("created_at", -1).limit(30).max_time_ms(5000)
    for notice in cursor:
        linked = notice.get("incident_id")
        if linked and linked in status_by_id and status_by_id[linked] not in ACTIVE_STATUSES:
            continue  # the incident has since recovered
        pending.append(notice)
    # Commands still waiting for the device ACK (requested or published, not yet acknowledged).
    # None when this read fails, so the tile shows a dash instead of an invented 0.
    try:
        ack_waiting = db.action_ledger.count_documents(
            {"farm_key": {"$in": list(farm_keys)}, "state": {"$in": ["requested", "published"]},
             "requested_at": {"$gte": since}}, maxTimeMS=4000)
    except Exception:
        ack_waiting = None
    return {"incidents": incidents, "pending": pending, "since": since, "ack_waiting": ack_waiting}


def get_events(farm_keys: tuple[str, ...]) -> dict:
    return _cached(("events", farm_keys), 20.0, _events_query, farm_keys)


def _farm_extra_query(farm_key: str) -> dict:
    db = database()
    ledger = list(db.action_ledger.find(
        {"farm_key": farm_key},
        {"_id": 0, "command_id": 1, "action": 1, "state": 1, "reason": 1, "error": 1, "requested_at": 1,
         "published_at": 1, "acknowledged_at": 1, "verified_at": 1, "failed_at": 1, "updated_at": 1,
         "target": 1, "node_id": 1},
    ).sort("updated_at", -1).limit(5).max_time_ms(4000))
    try:
        water_today = float(auth.get_total_actual_water(farm_key, datetime.now().strftime("%Y-%m-%d")))
    except Exception:
        water_today = None
    try:
        ai = auth.get_latest_ai_water_suggest(farm_key)
    except Exception:
        ai = None
    return {"ledger": ledger, "water_today": water_today, "ai": ai}


def get_farm_extra(farm_key: str) -> dict:
    return _cached(("farm-extra", farm_key), 10.0, _farm_extra_query, farm_key)


def _weather_fetch() -> dict:
    from service.weather_api import WeatherAPIClient
    result = WeatherAPIClient().get_weather_data()
    if result.get("status") != "success":
        raise RuntimeError(str(result.get("message") or "open-meteo"))
    return result["data"]


def get_weather() -> dict:
    return _cached(("weather",), 1800.0, _weather_fetch)


# ── shared view helpers ───────────────────────────────────────────────

def _loading(what: str) -> None:
    state_panel("loading", f"Đang đọc {what} từ MongoDB", "Lần đọc đầu tiên có thể mất vài giây.")


def _failed(loaded: dict | None, what: str, on_retry: Callable[[], Any] | None) -> bool:
    """Render an error panel when nothing could be read. True if it did."""
    if loaded is not None and loaded.get("value") is None and loaded.get("error"):
        state_panel("error", f"Không đọc được {what}", f"{loaded['error']}. Kiểm tra kết nối MongoDB rồi thử lại.",
                    action_label="Thử lại" if on_retry else None, on_action=on_retry)
        return True
    return False


def _stale_banner(loaded: dict | None) -> None:
    if loaded and loaded.get("stale"):
        state_panel("stale", "Đang hiển thị dữ liệu cũ",
                    f"Lần đọc mới nhất lỗi. Dữ liệu dưới đây được đọc lúc {fmt_time(loaded.get('read_at'))}.")


stale_banner = _stale_banner


def invalidate() -> None:
    """Forget cached reads so a retry button really reads again."""
    with _GUARD:
        _CACHE.clear()


def fleet_headline(cards: list[dict]) -> str:
    counts = {level: sum(1 for c in cards if c["level"] == level) for level in LEVEL_TEXT}
    if not cards:
        return "Chưa có nhà màng nào được cấp quyền"
    parts = []
    if counts["act"]:
        parts.append(f"{counts['act']} nhà màng cần xử lý")
    if counts["watch"]:
        parts.append(f"{counts['watch']} nhà màng cần theo dõi" if not parts else f"{counts['watch']} cần theo dõi")
    if parts:
        return ", ".join(parts)
    if counts["ok"] == len(cards):
        return f"Cả {len(cards)} nhà màng bình thường"
    return f"{counts['ok']} nhà màng bình thường, {counts['none']} chưa đủ dữ liệu"


def tab_levels(cards: list[dict]) -> list[tuple[str, str, str]]:
    return [(c["farm_key"], c["label"], c["level"]) for c in cards]


def _chart(options: dict, height: int, on_point_click: Callable | None = None) -> ui.element:
    chart = ui.echart(options, on_point_click=on_point_click) if on_point_click else ui.echart(options)
    return chart.classes("sm-chart").style(f"height:{height}px")


# ── fleet: signal heatmap ─────────────────────────────────────────────

_CELL_TINT = {"missing": "none", "observed": "info", "normal": "ok", "advisory": "watch", "problem": "act"}
_CELL_RANK = {"missing": 0, "observed": 1, "normal": 2, "advisory": 3, "problem": 4}
_FRESH_STATE = {"ONLINE": "observed", "STALE": "advisory", "OFFLINE": "problem"}
_NODE_WORD = {"ONLINE": "Mới", "STALE": "Cũ", "OFFLINE": "Mất", "UNKNOWN": "—"}
_LEVEL_SHORT = {"ok": "Bình thường", "watch": "Theo dõi", "act": "Xử lý", "none": "Chưa đủ"}
CHART_H = 300  # cùng một chiều cao cho mọi biểu đồ ở hàng dưới để lưới đều

# Tooltip ECharts: tên điểm dùng "\n" làm dấu xuống dòng; hàm này thoát HTML rồi mới đổi sang <br/>,
# nên không bao giờ hiện nguyên chữ thẻ.
_TIP_FN = (
    "function (p) {"
    " var s = String((p.data && p.data.name) || p.name || '');"
    " s = s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');"
    " return s.split('\\n').join('<br/>');"
    "}"
)


def _age_tip(sample: dict | None) -> str:
    return f" · mẫu {fmt_age(_ts(sample))}" if sample else ""


def _fresh_state(channel: dict, value_present: bool) -> str:
    if not value_present:
        return "missing"
    return _FRESH_STATE.get(channel["status"].get("status"), "missing")


def _matrix_rows(card: dict) -> list[tuple[str, str, str]]:
    level = card["level"]
    entries = [(f"{LEVEL_MARK[level]} {_LEVEL_SHORT[level]}",
                {"ok": "normal", "watch": "advisory", "act": "problem", "none": "missing"}[level],
                f"{LEVEL_TEXT[level]}. " + ("; ".join(card["causes"][:3]) or "Hai node có mẫu mới, không có sự cố đang mở"))]
    states = [node["status"].get("status", "UNKNOWN") for node in card["nodes"]]
    fresh = sum(1 for s in states if s == "ONLINE")
    entries.append((f"{fresh}/{len(states)} mới" if any(s != "UNKNOWN" for s in states) else "—",
                    "problem" if "OFFLINE" in states else "advisory" if "STALE" in states
                    else "normal" if all(s == "ONLINE" for s in states) else "missing",
                    f"N1 {_NODE_WORD.get(states[0], '—')} · N2 {_NODE_WORD.get(states[1], '—')}. "
                    "Theo tuổi mẫu mới nhất trong MongoDB, cùng ngưỡng với trạng thái node của ứng dụng"))
    temps, rhs, soil, ecs = [], [], [], []
    for node in card["nodes"]:
        if node["status"].get("status") != "ONLINE":
            continue
        readings = (node["sample"] or {}).get("readings") or {}
        for key, target in (("air_temp", temps), ("air_hum", rhs), ("soil_hum", soil), ("ec", ecs)):
            value = _num(readings.get(key))
            if value is not None:
                target.append(value)

    def mean(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    temp, rh, soil_mean, ec = mean(temps), mean(rhs), mean(soil), mean(ecs)
    temp_advice, rh_advice = classify_advisory("air_temp_c", temp), classify_advisory("air_humidity_pct", rh)
    entries.extend([
        (fmt_num(temp) and f"{fmt_num(temp)} °C" or "—",
         "advisory" if temp_advice["state"] == "advisory" else "normal" if temp is not None else "missing",
         temp_advice.get("message") or "Trung bình các node có mẫu mới"),
        (fmt_num(rh) and f"{fmt_num(rh)} %" or "—",
         "advisory" if rh_advice["state"] == "advisory" else "normal" if rh is not None else "missing",
         rh_advice.get("message") or "Trung bình các node có mẫu mới"),
        (fmt_num(soil_mean) and f"{fmt_num(soil_mean)} %" or "—", "observed" if soil_mean is not None else "missing",
         soil_moisture_calibration_note()),
        (fmt_num(ec, 2) or "—", "observed" if ec is not None else "missing",
         "EC đất trung bình các node có mẫu mới (mS/cm)"),
    ])
    water, flow, drain, vent = (card["channels"][k] for k in ("water", "flow", "drain_sensor", "ventilation_feedback"))
    ph = _value(water["sample"], "ph_val")
    f1, f2 = _value(flow["sample"], "flow_f1"), _value(flow["sample"], "flow_f2")
    flow_sum = None if f1 is None and f2 is None else (f1 or 0.0) + (f2 or 0.0)
    drain_l = _value(drain["sample"], "drain_l")
    vent_state, rpm = _value(vent["sample"], "state"), _value(vent["sample"], "fan_rpm")
    entries.extend([
        (fmt_num(ph, 2) or "—", _fresh_state(water, ph is not None), "pH từ mẫu nước mới nhất" + _age_tip(water["sample"])),
        (f"{fmt_num(flow_sum)} L/ph" if flow_sum is not None else "—", _fresh_state(flow, flow_sum is not None),
         "Tổng hai đường; 0 là số đo hợp lệ khi bơm dừng" + _age_tip(flow["sample"])),
        (f"{fmt_num(drain_l, 2)} L" if drain_l is not None else "—", _fresh_state(drain, drain_l is not None),
         "Lượng nước thoát ghi nhận" + _age_tip(drain["sample"])),
        ("Chạy" if vent_state else "Dừng" if vent_state is not None else "—",
         _fresh_state(vent, vent_state is not None),
         "Phản hồi quạt" + (f", {int(rpm)} vòng/phút" if vent_state and rpm else "") + _age_tip(vent["sample"])),
    ])
    return entries


MATRIX_COLUMNS = ["Tình trạng", "Kết nối", "Nhiệt độ", "Ẩm không khí", "Ẩm đất", "EC đất", "pH nước",
                  "Lưu lượng", "Thoát nước", "Quạt"]


def render_signal_matrix(cards: list[dict], read_at: Any, on_open: Callable[[str], Any]) -> None:
    rows = [card["label"] for card in cards]
    keys = [card["farm_key"] for card in cards]
    cells = []
    for y, card in enumerate(cards):
        for x, (text, state, tip) in enumerate(_matrix_rows(card)):
            tint = _CELL_TINT[state]
            abnormal = state in ("advisory", "problem")
            cells.append({
                "name": f"{card['label']} · {MATRIX_COLUMNS[x]}\n{text}\n{tip}",
                "value": [x, y, _CELL_RANK[state]],
                "itemStyle": {"color": CHART["tint"][tint], "borderColor": CHART["surface"], "borderWidth": 3},
                "label": {"show": True, "formatter": text, "fontSize": 10.5,
                          "fontWeight": "bold" if abnormal else "normal",
                          "color": CHART["level"][tint] if abnormal else (CHART["muted"] if state == "missing" else CHART["ink"])},
            })
    option = echart_base(
        grid={"left": 92, "right": 6, "top": 40, "bottom": 6},
        tooltip={"confine": True, ":formatter": _TIP_FN, "backgroundColor": CHART["surface"],
                 "borderColor": CHART["grid"], "textStyle": {"color": CHART["ink"], "fontSize": 12},
                 "extraCssText": "max-width:300px;white-space:normal;"},
        legend={"show": False},
        visualMap={"show": False, "min": 0, "max": 4, "inRange": {"color": [CHART["tint"][k] for k in
                                                                            ("none", "info", "ok", "watch", "act")]}},
    )
    axis_label = {"fontSize": 10.5, "color": CHART["muted"], "interval": 0, "width": 68, "overflow": "break"}
    option["xAxis"] = {"type": "category", "data": MATRIX_COLUMNS, "position": "top", "splitLine": {"show": False},
                       "axisLabel": axis_label, "axisTick": {"show": False}, "axisLine": {"show": False}}
    option["yAxis"] = {"type": "category", "data": rows, "inverse": True, "splitLine": {"show": False},
                       "axisLabel": {**axis_label, "color": CHART["ink"], "width": 84}, "axisTick": {"show": False},
                       "axisLine": {"show": False}}
    option["series"] = [{"type": "heatmap", "data": cells, "label": {"show": True}}]

    def click(event) -> None:
        try:
            on_open(keys[int(event.value[1])])
        except (TypeError, ValueError, IndexError, KeyError):
            return

    with panel(f"Tín hiệu {len(cards)} nhà màng", "Bấm một hàng để mở nhà màng"):
        # Desktop: vừa khít khối. Màn hẹp (CSS .sm-matrix): giữ bề rộng tối thiểu và cuộn trong khung.
        with ui.element("div").classes("sm-scroll-x"):
            _chart(option, 46 + 36 * max(1, len(cards)), click).classes("sm-matrix")
        source_note(f"Nguồn: MongoDB telemetry (mẫu mới nhất mỗi kênh) và operational_incidents. Đọc lúc {fmt_time(read_at)}. "
                    "Ngưỡng nhiệt độ và ẩm không khí là tham khảo; độ ẩm đất chưa hiệu chuẩn nên không tô ngưỡng.")


# ── fleet: attention list and sample age ──────────────────────────────

def render_fleet_kpis(cards: list[dict], events: dict | None) -> None:
    """Five fleet numbers, each from a real MongoDB read; a number that is not read yet shows a dash."""
    stale_s, offline_s = stale_limits()
    acting = [c for c in cards if c["level"] == "act"]
    watching = [c for c in cards if c["level"] == "watch"]
    flagged = len(acting) + len(watching)
    open_incidents = sum(len(c.get("incidents") or []) for c in cards)
    aged = [c for c in cards if c.get("age_s") is not None]
    oldest = max(aged, key=lambda c: c["age_s"], default=None)
    no_sample = len(cards) - len(aged)
    value = (events or {}).get("value")
    pending = None if value is None else len(value.get("pending") or [])
    ack_waiting = None if value is None else value.get("ack_waiting")
    loading = "Đang đọc" if events is None else "Chưa đọc được"
    with stats():
        stat("Nhà màng cần chú ý", str(flagged), f"/ {len(cards)}",
             f"{len(acting)} cần xử lý, {len(watching)} cần theo dõi" if flagged else "Tất cả bình thường",
             "act" if acting else "watch" if watching else None)
        stat("Sự cố đang mở", str(open_incidents), None,
             "Theo operational_incidents" if open_incidents else "Không có sự cố đang mở",
             "act" if open_incidents else None)
        stat("Mẫu node cũ nhất", _dur(oldest["age_s"]) if oldest else None, None,
             (f"{oldest['label']}" + (f"; {no_sample} nhà màng chưa có mẫu" if no_sample else "")) if oldest else None,
             "act" if oldest and oldest["age_s"] > offline_s else "watch" if oldest and oldest["age_s"] > stale_s else None)
        stat("Chờ người xem", None if pending is None else str(pending), None,
             "Thông báo workflow 24 giờ qua" if pending is not None else loading,
             "watch" if pending else None)
        stat("Lệnh chờ ACK", None if ack_waiting is None else str(ack_waiting), None,
             "action_ledger 24 giờ qua, thiết bị ảo" if ack_waiting is not None else loading,
             "watch" if ack_waiting else None)


def _clip(text: Any, limit: int = 110) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _clipped_label(full: str) -> None:
    """One text row cut to two lines; the whole sentence shows as a tooltip when it was shortened."""
    flat = " ".join(str(full).split())
    label = ui.label(_clip(flat)).classes("sm-clamp").style("font-size:13px")
    if len(flat) > 110:
        label.tooltip(flat)


def _hhmm(value: Any) -> str:
    stamp = as_utc(value)
    return "chưa có" if stamp is None else stamp.astimezone(VN_TZ).strftime("%H:%M")


def _group_key(*parts: Any) -> tuple:
    return tuple(" ".join(str(p or "").split()).casefold() for p in parts)


def _group_rows(rows: list[tuple[tuple, dict]]) -> list[dict]:
    """Merge rows whose key is equal: {"count", "latest" (newest row), "first_at", "last_at"}, newest group first.

    Display only: nothing is changed or removed in MongoDB.
    """
    floor = datetime.min.replace(tzinfo=timezone.utc)
    groups: dict[tuple, dict] = {}
    for key, row in rows:
        stamp = as_utc(row.get("created_at")) or floor
        group = groups.get(key)
        if group is None:
            groups[key] = {"count": 1, "latest": row, "last_at": stamp, "first_at": stamp}
            continue
        group["count"] += 1
        if stamp >= group["last_at"]:
            group["latest"], group["last_at"] = row, stamp
        group["first_at"] = min(group["first_at"], stamp)
    return sorted(groups.values(), key=lambda g: g["last_at"], reverse=True)


def group_notices(entries: list[tuple[str, dict | None, dict]]) -> list[dict]:
    """Collapse repeated notices (same scope and text). Each group also carries ``scope``."""
    keyed = [(_group_key(scope, notice.get("message")), (scope, notice)) for scope, _card, notice in entries]
    grouped = _group_rows([(key, {**notice, "created_at": notice.get("created_at"), "_scope": scope})
                           for key, (scope, notice) in keyed])
    for group in grouped:
        group["scope"] = group["latest"]["_scope"]
    return grouped


def group_pending(pending: list[dict]) -> list[dict]:
    """Collapse repeated review-queue notices (same scope, text and status)."""
    return _group_rows([
        (_group_key(n.get("farm_key"), n.get("message") or n.get("workflow_name"),
                    n.get("workflow_status"), n.get("verification_status")), n)
        for n in pending])


def _repeat_line(group: dict) -> str:
    """'x 12 lần, gần nhất 14:05' for repeated rows; the plain time for a single row."""
    if group["count"] > 1:
        return f"x {group['count']} lần, gần nhất {_hhmm(group['last_at'])}"
    return fmt_time(group["last_at"])


def _visible(items: list, key: str, expanded: set | None, default: int = 5, cap: int = 30) -> list:
    return items[:cap] if expanded is not None and key in expanded else items[:default]


def _more_button(key: str, total: int, expanded: set | None, on_expand: Callable[[str], Any] | None,
                 default: int = 5) -> None:
    if on_expand is None or total <= default:
        return
    open_now = expanded is not None and key in expanded
    ui.button("Thu gọn" if open_now else f"Xem thêm {min(total, 30) - default} mục",
              on_click=lambda _e=None: on_expand(key)).props("flat dense no-caps").classes("sm-btn-quiet")


def render_attention(cards: list[dict], read_at: Any, on_open: Callable[[str], Any],
                     expanded: set | None = None, on_expand: Callable[[str], Any] | None = None) -> None:
    flagged = sorted((c for c in cards if c["level"] != "ok"), key=lambda c: (LEVEL_RANK[c["level"]], c["label"]))
    with panel("Cần chú ý", f"{len(flagged)} trên {len(cards)} nhà màng"):
        if not flagged:
            state_panel("empty", "Không có nhà màng nào cần chú ý",
                        "Mọi nhà màng có mẫu mới và không có sự cố đang mở.")
        for card in _visible(flagged, "attention", expanded):
            with ui.element("div").classes("sm-row").style("align-items:flex-start"):
                with ui.element("div").style("min-width:0;flex:1"):
                    with ui.element("div").classes("sm-inline"):
                        ui.label(card["label"]).style("font-weight:600;font-size:13px")
                        status_chip(card["level"], LEVEL_TEXT[card["level"]])
                    for cause in card["causes"][:2]:
                        ui.label(_clip(cause, 90)).classes("sm-note")
                    if len(card["causes"]) > 2:
                        ui.label(f"và {len(card['causes']) - 2} lý do khác").classes("sm-note")
                ui.button("Mở farm", on_click=lambda _e=None, k=card["farm_key"]: on_open(k)).props(
                    "flat dense no-caps").classes("sm-btn-quiet")
        _more_button("attention", len(flagged), expanded, on_expand)
        source_note(f"Nguồn: MongoDB. Đọc lúc {fmt_time(read_at)}.")


def render_age_chart(cards: list[dict], read_at: Any) -> None:
    stale_s, offline_s = stale_limits()
    labels = [c["label"] for c in cards]
    data = []
    for card in cards:
        age = card["age_s"]
        if age is None:
            data.append(None)
            continue
        tint = "ok" if age <= stale_s else "watch" if age <= offline_s else "act"
        data.append({"value": max(1, round(age)),
                     "itemStyle": {"color": CHART["level"]["none"] if tint == "ok" else CHART["level"][tint]}})
    option = echart_base(grid={"left": 92, "right": 40, "top": 18, "bottom": 22}, legend={"show": False},
                         tooltip={"trigger": "axis", "axisPointer": {"type": "shadow"}, "confine": True,
                                  "backgroundColor": CHART["surface"], "borderColor": CHART["grid"],
                                  "textStyle": {"color": CHART["ink"], "fontSize": 12}})
    option["xAxis"] = {**option["xAxis"], "type": "log", "min": 1, "axisLabel": {"color": CHART["muted"], "fontSize": 11}}
    option["yAxis"] = {**option["yAxis"], "type": "category", "data": labels, "inverse": True,
                       "splitLine": {"show": False}}
    option["series"] = [{
        "type": "bar", "data": data, "barWidth": 10, "name": "Tuổi mẫu (giây)",
        "label": {"show": True, "position": "right", "fontSize": 10, "color": CHART["muted"]},
        "markLine": {"symbol": "none", "silent": True, "data": [
            {"xAxis": stale_s, "lineStyle": {"color": CHART["level"]["watch"], "type": "dashed"},
             "label": {"formatter": f"Cũ {stale_s} giây", "fontSize": 10, "position": "insideEndTop"}},
            {"xAxis": offline_s, "lineStyle": {"color": CHART["level"]["act"], "type": "dashed"},
             "label": {"formatter": f"Mất {offline_s} giây", "fontSize": 10, "position": "insideEndTop"}},
        ]},
    }]
    with panel("Tuổi mẫu mới nhất", "Giây, thang log"):
        if all(item is None for item in data):
            state_panel("empty", "Chưa có mẫu node nào", "Chưa nhà màng nào có mẫu trong MongoDB.")
        else:
            _chart(option, CHART_H)
        source_note(f"Nguồn: MongoDB telemetry, mẫu node mới nhất mỗi nhà màng. Vạch cam và đỏ là ngưỡng Cũ và Mất "
                    f"của ứng dụng. Đọc lúc {fmt_time(read_at)}.")


# ── fleet: overlaid lines ─────────────────────────────────────────────

def _axis_time(base: dict, hours: int) -> dict:
    now = datetime.now(timezone.utc)
    return {**base["xAxis"], "type": "time", "min": int((now - timedelta(hours=hours)).timestamp() * 1000),
            "max": int(now.timestamp() * 1000), "splitLine": {"show": False}}


def _temp_band(low: float, high: float, values: list[float]) -> dict | None:
    """Shade only what lies outside the advisory band, so orange keeps meaning 'attention'.

    An area is drawn only when the data comes within 3 units of that limit.
    """
    if not values:
        return None
    vmin, vmax = min(values), max(values)
    areas = []
    if vmax > high - 3:
        areas.append([{"yAxis": high}, {"yAxis": max(vmax, high) + 2}])
    if vmin < low + 3:
        areas.append([{"yAxis": min(vmin, low) - 2}, {"yAxis": low}])
    if not areas:
        return None
    return {"type": "line", "data": [], "silent": True, "tooltip": {"show": False},
            "markArea": {"silent": True, "itemStyle": {"color": CHART["band"]}, "data": areas}}


def _fleet_line_chart(title: str, unit: str, by_farm: dict[str, list], cards: list[dict], hours: int,
                      band: tuple[float, float] | None, note: str) -> None:
    level_of = {c["farm_key"]: c["level"] for c in cards}
    series = []
    for card in cards:
        points = by_farm.get(card["farm_key"])
        if not points:
            continue
        level = level_of[card["farm_key"]]
        flagged = level in ("watch", "act")
        color = CHART["level"][level] if flagged else CHART["level"]["none"]
        item = {"name": card["label"], "type": "line", "data": points, "showSymbol": False, "z": 3 if flagged else 1,
                "lineStyle": {"color": color, "width": 2.2 if flagged else 1, "opacity": 1 if flagged else 0.55},
                "itemStyle": {"color": color}, "emphasis": {"focus": "series"}}
        if flagged:
            item["endLabel"] = {"show": True, "formatter": "{a}", "color": color, "fontSize": 11, "fontWeight": "bold"}
        series.append(item)
    with panel(title, unit):
        if not series:
            state_panel("empty", f"Chưa có mẫu trong {hours} giờ qua",
                        "MongoDB không có mẫu node nào của các nhà màng này trong khoảng đã chọn.")
        else:
            option = echart_base(legend={"show": False}, grid={"left": 44, "right": 104, "top": 14, "bottom": 28},
                                 tooltip={"trigger": "axis", "confine": True, "order": "valueDesc",
                                          "backgroundColor": CHART["surface"], "borderColor": CHART["grid"],
                                          "textStyle": {"color": CHART["ink"], "fontSize": 12}})
            option["xAxis"] = _axis_time(option, hours)
            option["yAxis"] = {**option["yAxis"], "scale": True}
            if band:
                area = _temp_band(band[0], band[1], [p[1] for pts in by_farm.values() for p in pts])
                if area:
                    series.append(area)
            option["series"] = series
            _chart(option, CHART_H)
        source_note(note)


def render_fleet_lines(loaded: dict, hours: int, cards: list[dict], on_range: Callable[[int], Any],
                       on_retry: Callable[[], Any]) -> None:
    with ui.element("div").classes("sm-inline").style("justify-content:space-between"):
        ui.label("Diễn biến theo thời gian").classes("sm-h2")
        range_pills([("1 giờ", 1), ("6 giờ", 6), ("24 giờ", 24)], hours, on_range)
    if loaded is None:
        _loading("chuỗi thời gian")
        return
    if _failed(loaded, "chuỗi thời gian", on_retry):
        return
    _stale_banner(loaded)
    value = loaded["value"]
    read_text = f"Đọc lúc {fmt_time(loaded.get('read_at'))}"
    base = (f"Nguồn: MongoDB telemetry, trung bình hai node mỗi {value['bin']} phút, {value['samples']} mẫu. "
            f"{read_text}.")
    temp_cfg = THRESHOLDS["air_temp_c"]
    band = (temp_cfg["below"], temp_cfg["above"])
    with ui.element("div").classes("sm-cols-2"):
        _fleet_line_chart("Nhiệt độ không khí", "°C", value["temp"], cards, hours, band,
                          f"{base} Vùng cam: ngoài {band[0]:g} đến {band[1]:g} °C, ngưỡng tham khảo từ service.agronomic_thresholds.")
        _fleet_line_chart("Độ ẩm đất", "%", value["soil"], cards, hours, None,
                          f"{base} {soil_moisture_calibration_note()}")


# ── fleet: incident timeline, review queue, notices ──────────────────

_RENDER_BAR = (
    "function (params, api) {"
    " var idx = api.value(0);"
    " var s = api.coord([api.value(1), idx]);"
    " var e = api.coord([api.value(2), idx]);"
    " var h = Math.min(api.size([0, 1])[1] * 0.5, 16);"
    " var cs = params.coordSys;"
    " var x0 = Math.max(s[0], cs.x);"
    " var x1 = Math.min(Math.max(e[0], s[0] + 5), cs.x + cs.width);"
    " if (x1 <= x0) { return null; }"
    " return {type: 'rect', shape: {x: x0, y: s[1] - h / 2, width: x1 - x0, height: h}, style: api.style()};"
    "}"
)


def render_incident_timeline(loaded: dict, cards: list[dict], can_open: bool, on_open_incident: Callable[[str], Any],
                             on_retry: Callable[[], Any]) -> None:
    with panel("Sự cố 24 giờ qua", "Bấm một thanh để mở hồ sơ" if can_open else "Hồ sơ sự cố chỉ mở cho quản trị"):
        if loaded is None:
            _loading("sự cố")
            return
        if _failed(loaded, "sự cố", on_retry):
            return
        _stale_banner(loaded)
        value = loaded["value"]
        now = datetime.now(timezone.utc)
        start, end = now - timedelta(hours=24), now
        row_of = {c["farm_key"]: i for i, c in enumerate(cards)}
        data = []
        for incident in value["incidents"]:
            idx = row_of.get(incident.get("farm_key"))
            opened = as_utc(incident.get("opened_at"))
            if idx is None or opened is None:
                continue
            active = incident.get("status") in ACTIVE_STATUSES
            closed_at = as_utc(incident.get("recovered_at")) or (now if active else opened)
            label = _incident_label(incident.get("kind"))
            tint = "act" if active else "ok"
            data.append({
                "value": [idx, int(max(opened, start).timestamp() * 1000), int(min(closed_at, end).timestamp() * 1000)],
                "name": (f"{cards[idx]['label']} · {label}\n{'Đang mở' if active else 'Đã đóng'} ({incident.get('status')})"
                         f"\nMở {fmt_time(opened)}" + ("" if active else f"\nĐóng {fmt_time(closed_at)}")),
                "itemStyle": {"color": CHART["level"][tint]}, "incident_id": incident["incident_id"],
            })
        if not data:
            state_panel("empty", "Không có sự cố trong 24 giờ qua",
                        "operational_incidents không có bản ghi mở trong khoảng này của các nhà màng đang xem.")
        else:
            option = echart_base(legend={"show": False}, grid={"left": 98, "right": 12, "top": 10, "bottom": 28},
                                 tooltip={"trigger": "item", "confine": True, ":formatter": _TIP_FN,
                                          "backgroundColor": CHART["surface"], "borderColor": CHART["grid"],
                                          "textStyle": {"color": CHART["ink"], "fontSize": 12}})
            option["xAxis"] = {**option["xAxis"], "type": "time", "min": int(start.timestamp() * 1000),
                               "max": int(end.timestamp() * 1000), "splitLine": {"show": True, "lineStyle": {"color": CHART["grid"]}}}
            option["yAxis"] = {**option["yAxis"], "type": "category", "data": [c["label"] for c in cards],
                               "inverse": True, "splitLine": {"show": True, "lineStyle": {"color": CHART["grid"]}},
                               "axisLabel": {"color": CHART["ink"], "fontSize": 11, "interval": 0}}
            option["series"] = [{"type": "custom", "data": data, ":renderItem": _RENDER_BAR,
                                 "encode": {"x": [1, 2], "y": 0}}]

            def click(event) -> None:
                incident_id = (event.data or {}).get("incident_id") if isinstance(event.data, dict) else None
                if incident_id and can_open:
                    on_open_incident(str(incident_id))

            _chart(option, CHART_H, click)
        source_note(f"Nguồn: MongoDB operational_incidents, từ opened_at tới recovered_at hoặc hiện tại; đỏ là đang mở "
                    f"({', '.join(ACTIVE_STATUSES)}), xanh trầm là đã đóng. Đọc lúc {fmt_time(loaded.get('read_at'))}.")


def render_review_queue(loaded: dict | None, labels: dict[str, str], can_open: bool,
                        on_open_incident: Callable[[str], Any],
                        expanded: set | None = None, on_expand: Callable[[str], Any] | None = None) -> None:
    groups = group_pending(loaded["value"]["pending"]) if loaded and loaded.get("value") else []
    with panel("Cần người duyệt", f"{len(groups)} nhóm" if groups else None):
        if loaded is None:
            _loading("hàng chờ duyệt")
            return
        if loaded.get("value") is None:
            state_panel("error", "Không đọc được hàng chờ duyệt", str(loaded.get("error") or ""))
            return
        pending = loaded["value"]["pending"]
        if not pending:
            state_panel("empty", "Không có mục nào chờ người xem",
                        "Không có thông báo Datadog nào ở trạng thái escalated, pending_verification hoặc "
                        "verification pending trong 24 giờ qua. Ứng dụng chưa lưu trạng thái chờ duyệt riêng "
                        "cho operational_decisions nên không có nút duyệt.")
        for group in _visible(groups, "review", expanded):
            notice = group["latest"]
            with ui.element("div").classes("sm-row").style("align-items:flex-start"):
                with ui.element("div").style("min-width:0;flex:1"):
                    scope = labels.get(notice.get("farm_key") or "", "Toàn hệ thống")
                    full = f"{scope} · {notice.get('message') or notice.get('workflow_name') or 'Thông báo workflow'}"
                    _clipped_label(full)
                    ui.label(f"{_repeat_line(group)} · workflow {notice.get('workflow_status') or '—'}, "
                             f"xác minh {notice.get('verification_status') or '—'}").classes("sm-note")
                if can_open and notice.get("incident_id"):
                    ui.button("Mở hồ sơ", on_click=lambda _e=None, i=notice["incident_id"]: on_open_incident(str(i))).props(
                        "flat dense no-caps").classes("sm-btn-quiet")
        with ui.element("div").classes("sm-inline"):
            _more_button("review", len(groups), expanded, on_expand)
            if can_open:
                ui.link("Mở trang Sự cố", "/incident").classes("sm-link").style("font-size:12px")
        source_note("Nguồn: MongoDB notifications (workflow Datadog), đã loại mục có sự cố liên kết đã đóng; "
                    f"các dòng giống nhau được gộp khi hiển thị. Đọc lúc {fmt_time(loaded.get('read_at'))}.")


_SEVERITY_LEVEL = {"error": "act", "warning": "watch", "info": "info"}


def _notice_feed_entries(cards: list[dict], labels: dict[str, str], unscoped_notices: list[dict]) -> list[tuple[str, dict | None, dict]]:
    """Combine farm-scoped and system-level notices without cross-linking them."""
    notices_by_id = {}
    for card in cards:
        for notice in card.get("notices", []):
            identity = (card["farm_key"], notice.get("advisory_id"), notice.get("message"), notice.get("created_at"))
            if not notice.get("message", "").startswith("SMIOT demo:"):
                notices_by_id[identity] = (labels.get(card["farm_key"], card["farm_key"]), card, notice)
    for notice in unscoped_notices:
        identity = (None, notice.get("advisory_id"), notice.get("message"), notice.get("created_at"))
        if not notice.get("message", "").startswith("SMIOT demo:"):
            notices_by_id[identity] = ("Toàn hệ thống", None, notice)
    return list(notices_by_id.values())


def render_notices(fleet: dict, farm_key: str | None = None,
                   expanded: set | None = None, on_expand: Callable[[str], Any] | None = None) -> None:
    cards, unscoped = fleet["cards"], fleet["unscoped"]
    labels = {c["farm_key"]: c["label"] for c in cards}
    entries = _notice_feed_entries(cards, labels, [] if farm_key else unscoped)
    if farm_key:
        entries = [e for e in entries if e[1] is not None and e[1]["farm_key"] == farm_key]
    entries.sort(key=lambda e: as_utc(e[2].get("created_at")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    groups = group_notices(entries)
    key = f"notices:{farm_key or ''}"
    with panel("Thông báo", f"{len(groups)} nhóm, {len(entries)} bản ghi" if groups else None):
        if not groups:
            state_panel("empty", "Chưa có thông báo", "notifications không có bản ghi nào cho phạm vi này.")
        for group in _visible(groups, key, expanded):
            notice = group["latest"]
            with ui.element("div").classes("sm-row").style("align-items:flex-start"):
                with ui.element("div").style("min-width:0;flex:1"):
                    full = f"{group['scope']} · {notice.get('message', '')}"
                    _clipped_label(full)
                    ui.label(_repeat_line(group)).classes("sm-note")
                severity = _SEVERITY_LEVEL.get(str(notice.get("severity")), "none")
                if severity != "info":
                    status_chip(severity, {"act": "Lỗi", "watch": "Cảnh báo"}.get(severity, "Thông báo"))
        _more_button(key, len(groups), expanded, on_expand)
        source_note("Nguồn: MongoDB notifications, giờ Việt Nam. Dòng giống nhau được gộp khi hiển thị "
                    "(dữ liệu gốc không đổi); số lần tính trên các bản ghi đã đọc.")


# ── farm: strip, numbers ─────────────────────────────────────────────

def render_farm_strip(card: dict, shortcuts: list[tuple[str, str]], navigate: Callable[[str], Any]) -> None:
    level = card["level"]
    with panel(card["label"]):
        with ui.element("div").classes("sm-inline"):
            status_chip(level, LEVEL_TEXT[level])
            ui.label(f"Mẫu node mới nhất {fmt_age(card['newest'])}").classes("sm-note")
        if card["causes"]:
            for cause in card["causes"][:3]:
                ui.label(cause).classes("sm-note").style("margin-top:4px")
        else:
            ui.label("Hai node có mẫu mới và không có sự cố đang mở.").classes("sm-note").style("margin-top:4px")
        with ui.element("div").classes("sm-inline").style("margin-top:10px"):
            for text, url in shortcuts:
                ui.button(text, on_click=lambda _e=None, u=url: navigate(u)).props("flat dense no-caps").classes("sm-btn-quiet")


def render_farm_stats(card: dict, extra: dict | None) -> None:
    index = card["index"]

    def tile(label: str, sample: dict | None, field: str, unit: str, digits: int = 1, metric: str | None = None,
             where: str = "") -> None:
        value = _value(sample, field)
        level = None
        if value is not None and metric:
            level = "watch" if classify_advisory(metric, value)["state"] == "advisory" else None
        meta = f"{fmt_age(_ts(sample))}{where}, thiết bị ảo" if sample and value is not None else None
        stat(label, fmt_num(value, digits), unit, meta, level)

    with stats():
        for n, node in enumerate(card["nodes"], 1):
            tile(f"Nhiệt độ không khí, node {n}", node["sample"], "air_temp", "°C", 1, "air_temp_c", f", node {n}")
        for n, node in enumerate(card["nodes"], 1):
            tile(f"Độ ẩm không khí, node {n}", node["sample"], "air_hum", "%", 1, "air_humidity_pct", f", node {n}")
        for n, node in enumerate(card["nodes"], 1):
            tile(f"Độ ẩm đất, node {n}", node["sample"], "soil_hum", "%", 1, None, f", node {n}")
        for n, node in enumerate(card["nodes"], 1):
            tile(f"EC đất, node {n}", node["sample"], "ec", "mS/cm", 2, None, f", node {n}")
        water_ph = _latest_with(index, "water", "ph_val")
        water_ec = _latest_with(index, "water", "ec_val")
        tile("pH nước", water_ph, "ph_val", "", 2)
        tile("EC nước", water_ec, "ec_val", "mS/cm", 2)
        flow = card["channels"]["flow"]["sample"]
        f1, f2 = _value(flow, "flow_f1"), _value(flow, "flow_f2")
        total = None if f1 is None and f2 is None else (f1 or 0.0) + (f2 or 0.0)
        stat("Lưu lượng", fmt_num(total, 2), "L/phút",
             f"{fmt_age(_ts(flow))}, hai đường, thiết bị ảo" if flow and total is not None else None)
        water_today = ((extra or {}).get("value") or {}).get("water_today")
        stat("Nước hôm nay", fmt_num(water_today, 0), "L",
             "Tổng schedule_logs hôm nay, MongoDB" if water_today is not None else None)
    source_note("Nguồn: MongoDB telemetry, mẫu mới nhất của nhà màng này; node 1 và node 2 từ thiết bị ảo. "
                "Độ ẩm đất chưa hiệu chuẩn nên không tô ngưỡng.")


# ── farm: charts ──────────────────────────────────────────────────────

def _multi_line(defs: list[dict], hours: int, units: tuple[str, str | None], band: tuple[float, float] | None = None) -> dict:
    option = echart_base(grid={"left": 44, "right": 44 if units[1] else 14, "top": 30, "bottom": 26},
                         tooltip={"trigger": "axis", "confine": True, "backgroundColor": CHART["surface"],
                                  "borderColor": CHART["grid"], "textStyle": {"color": CHART["ink"], "fontSize": 12}})
    option["xAxis"] = _axis_time(option, hours)
    axes = [{**option["yAxis"], "scale": True, "name": units[0], "nameTextStyle": {"color": CHART["muted"], "fontSize": 11}}]
    if units[1]:
        axes.append({**option["yAxis"], "scale": True, "name": units[1], "position": "right",
                     "splitLine": {"show": False}, "nameTextStyle": {"color": CHART["muted"], "fontSize": 11}})
    option["yAxis"] = axes if units[1] else axes[0]
    series = []
    for item in defs:
        color = CHART["series"][item["color"] % len(CHART["series"])]
        entry = {"name": item["name"], "type": "line", "data": item["data"], "showSymbol": False,
                 "yAxisIndex": item.get("axis", 0), "lineStyle": {"color": color, "width": 1.6,
                                                                   "type": "dashed" if item.get("axis", 0) else "solid"},
                 "itemStyle": {"color": color}}
        series.append(entry)
    if band:
        area = _temp_band(band[0], band[1], [p[1] for item in defs if item.get("axis", 0) == 0 for p in item["data"]])
        if area:
            series.append(area)
    option["series"] = series
    return option


def render_farm_charts(loaded: dict | None, hours: int, on_range: Callable[[int], Any], on_retry: Callable[[], Any]) -> None:
    with ui.element("div").classes("sm-inline").style("justify-content:space-between"):
        ui.label("Diễn biến theo thời gian").classes("sm-h2")
        range_pills([("1 giờ", 1), ("6 giờ", 6), ("24 giờ", 24)], hours, on_range)
    if loaded is None:
        _loading("chuỗi thời gian của nhà màng")
        return
    if _failed(loaded, "chuỗi thời gian của nhà màng", on_retry):
        return
    _stale_banner(loaded)
    value = loaded["value"]
    series = value["series"]
    note = (f"Nguồn: MongoDB telemetry, trung bình mỗi {value['bin']} phút, thiết bị ảo. "
            f"Đọc lúc {fmt_time(loaded.get('read_at'))}.")
    temp_cfg = THRESHOLDS["air_temp_c"]
    node_defs = lambda field, label, axis, offset: [  # noqa: E731
        {"name": f"{label} node {n}", "data": series[f"{field}:{n}"], "axis": axis, "color": n - 1 + offset}
        for n in (1, 2) if f"{field}:{n}" in series]
    specs = [
        ("Nhiệt độ và ẩm không khí", ("°C", "%"),
         node_defs("air_temp", "Nhiệt độ", 0, 0) + node_defs("air_hum", "Ẩm KK", 1, 2),
         (temp_cfg["below"], temp_cfg["above"]), "Vùng cam: ngoài ngưỡng nhiệt độ tham khảo. "),
        ("Độ ẩm đất và EC đất", ("%", "mS/cm"),
         node_defs("soil_hum", "Ẩm đất", 0, 0) + node_defs("ec", "EC đất", 1, 2), None,
         soil_moisture_calibration_note() + " "),
        ("pH và EC nước", ("pH", "mS/cm"),
         ([{"name": "pH", "data": series["ph_val"], "axis": 0, "color": 0}] if "ph_val" in series else [])
         + ([{"name": "EC nước", "data": series["ec_val"], "axis": 1, "color": 2}] if "ec_val" in series else []),
         None, ""),
        ("Lưu lượng", ("L/phút", None),
         ([{"name": "Đường 1", "data": series["flow_f1"], "color": 0}] if "flow_f1" in series else [])
         + ([{"name": "Đường 2", "data": series["flow_f2"], "color": 1}] if "flow_f2" in series else []),
         None, "Giá trị 0 là hợp lệ khi bơm dừng. "),
    ]
    with ui.element("div").classes("sm-charts"):
        for title, units, defs, band, extra_note in specs:
            with panel(title, units[0] if not units[1] else f"{units[0]} và {units[1]}"):
                if not defs:
                    state_panel("empty", f"Chưa có mẫu {title.lower()} trong {hours} giờ qua",
                                "MongoDB không có mẫu của kênh này trong khoảng đã chọn.")
                else:
                    _chart(_multi_line(defs, hours, units, band), 220)
                source_note(extra_note + note)


# ── farm: devices and commands ───────────────────────────────────────

_NODE_CHIP = {"ONLINE": ("ok", "Trực tuyến"), "STALE": ("watch", "Chậm"), "OFFLINE": ("act", "Mất tín hiệu"),
              "UNKNOWN": ("none", "Chưa có mẫu")}
_ACTION_NAME = {"SET_OUTPUTS": "Đặt đầu ra bơm", "SET_VALVE": "Điều khiển van", "SET_VENT": "Điều khiển quạt",
                "SET_INVERTER": "Điều khiển biến tần", "HOLD": "Giữ an toàn (HOLD)",
                "CLEAR": "Xóa chế độ an toàn", "SAFE_STOP": "Dừng an toàn"}
_ACTUATOR_NAME = {"plc_pump": "Bơm", "inverter": "Biến tần"}


def _device_row(name: str, chip: tuple[str, str], detail: str) -> None:
    with ui.element("div").classes("sm-row").style("align-items:flex-start"):
        with ui.element("div").style("min-width:0;flex:1"):
            ui.label(name).style("font-weight:600;font-size:13px")
            ui.label(detail).classes("sm-note")
        status_chip(*chip)


def _recent_commands(farm_key: str, ledger: list[dict], pending: dict) -> list[dict]:
    items = []
    seen = set()
    for row in ledger:
        seen.add(row.get("command_id"))
        sent = row.get("published_at") or row.get("requested_at")
        items.append({"label": _ACTION_NAME.get(row.get("action"), str(row.get("action") or "Lệnh")),
                      "detail": row.get("reason") or "", "status": row.get("state"), "sent_at": sent,
                      "acked_at": row.get("acknowledged_at"), "verified_at": row.get("verified_at"),
                      "reason": row.get("error") or None, "at": as_utc(row.get("updated_at") or sent)})
    for record in list(pending.values()):
        if record.get("farm_key") != farm_key or record.get("command_id") in seen:
            continue
        items.append({"label": f"{_ACTUATOR_NAME.get(record.get('actuator'), record.get('actuator') or 'Thiết bị')} "
                               f"{record.get('channel') or ''}: {'bật' if record.get('target') else 'tắt'}",
                      "detail": "Lệnh trong bộ nhớ ứng dụng, chưa có bản ghi sổ lệnh",
                      "status": record.get("status"), "sent_at": record.get("published_at") or record.get("requested_at"),
                      "acked_at": record.get("acknowledged_at"), "verified_at": None, "reason": None,
                      "at": as_utc(record.get("requested_at"))})
    items.sort(key=lambda i: i["at"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items[:5]


def render_farm_devices(card: dict, extra: dict | None, home_state: dict, on_retry: Callable[[], Any]) -> None:
    farm_key = card["farm_key"]
    with ui.element("div").classes("sm-cols-2"):
        with panel("Thiết bị ảo"):
            for n, node in enumerate(card["nodes"], 1):
                status = node["status"].get("status", "UNKNOWN")
                _device_row(f"Node {n}", _NODE_CHIP.get(status, _NODE_CHIP["UNKNOWN"]),
                            f"Mẫu cuối {fmt_age(_ts(node['sample']))}" if node["sample"] else "Chưa có mẫu trong MongoDB")
            feedback = home_state.get("virtual_plc_feedback") or {}
            if feedback.get("farm_key") == farm_key:
                outputs = feedback.get("virtual_output") or {}
                on = [k.replace("bit", "q") for k, v in outputs.items() if v in (1, True, "1")]
                safe = feedback.get("safe_mode_active")
                _device_row("PLC ảo", ("act", "Chế độ an toàn") if safe else ("ok", "Có phản hồi"),
                            f"Đầu ra bật: {', '.join(on) if on else 'không'}; van {'mở' if feedback.get('valve_state') else 'đóng'}; "
                            f"cập nhật {fmt_time(feedback.get('updated_at'))}")
            else:
                _device_row("PLC ảo", ("none", "Chưa có phản hồi"), "Chưa nhận phản hồi PLC ảo của nhà màng này")
            if home_state.get("inv_updated"):
                online = home_state.get("inv_online") == 1
                running = home_state.get("inv_status") == 1
                chip = ("ok", "Đang chạy") if online and running else ("none", "Đang dừng") if online else ("act", "Ngoại tuyến")
                _device_row("Biến tần ảo", chip, f"Số đọc chung của hệ thống, chưa tách theo nhà màng; cập nhật {home_state['inv_updated']}")
            else:
                _device_row("Biến tần ảo", ("none", "Chưa có phản hồi"), "Chưa nhận số đọc biến tần")
            source_note("Nguồn: MongoDB telemetry (node) và bộ nhớ ứng dụng (PLC, biến tần). Tất cả là thiết bị ảo.")
        with panel("Lệnh gần đây", "5 lệnh mới nhất"):
            if extra is None:
                _loading("sổ lệnh")
            elif extra.get("value") is None:
                state_panel("error", "Không đọc được sổ lệnh", str(extra.get("error") or ""),
                            action_label="Thử lại", on_action=on_retry)
            else:
                commands = _recent_commands(farm_key, extra["value"]["ledger"], home_state.get("actuator_pending_by_command") or {})
                if not commands:
                    state_panel("empty", "Chưa có lệnh nào cho nhà màng này",
                                "action_ledger và bộ nhớ ứng dụng không có lệnh của nhà màng này.")
                for item in commands:
                    with ui.element("div").style("padding:8px 0;border-top:1px solid var(--sm-net-soft);width:100%"):
                        with ui.element("div").classes("sm-inline"):
                            ui.label(item["label"]).style("font-weight:600;font-size:13px")
                            ui.label(fmt_time(item["at"])).classes("sm-note")
                        if item["detail"]:
                            ui.label(item["detail"]).classes("sm-note")
                        command_chain(item["status"], sent_at=item["sent_at"], acked_at=item["acked_at"],
                                      verified_at=item["verified_at"], reason=item["reason"])
                source_note("Nguồn: MongoDB action_ledger và lệnh đang chờ trong bộ nhớ ứng dụng. ACK từ bộ mô phỏng, "
                            f"chưa phải xác minh vật lý. Đọc lúc {fmt_time(extra.get('read_at'))}.")


# ── farm: open incidents, weather, AI ────────────────────────────────

def render_farm_incidents(card: dict, can_open: bool, on_open_incident: Callable[[str], Any]) -> None:
    with panel("Sự cố đang mở", f"{len(card['incidents'])}"):
        if not card["incidents"]:
            state_panel("empty", "Không có sự cố đang mở", "operational_incidents không có bản ghi mở của nhà màng này.")
        for incident in card["incidents"]:
            with ui.element("div").classes("sm-row"):
                with ui.element("div").style("min-width:0;flex:1"):
                    ui.label(_incident_label(incident.get("kind"))).style("font-weight:600;font-size:13px")
                    ui.label(f"{incident.get('incident_id')} · mở lúc {fmt_time(incident.get('opened_at'))}").classes("sm-note")
                status_chip("act", str(incident.get("status") or "mở"))
                if can_open:
                    ui.button("Mở hồ sơ", on_click=lambda _e=None, i=str(incident.get("incident_id")): on_open_incident(i)).props(
                        "flat dense no-caps").classes("sm-btn-quiet")
        source_note("Nguồn: MongoDB operational_incidents, trạng thái " + ", ".join(ACTIVE_STATUSES) + ".")


def render_weather(loaded: dict | None, on_retry: Callable[[], Any]) -> None:
    with panel("Dự báo thời tiết", "Open-Meteo"):
        if loaded is None:
            _loading("dự báo")
            return
        if loaded.get("value") is None:
            state_panel("error", "Không lấy được dự báo", "Open-Meteo không trả dữ liệu; không hiển thị số mặc định.",
                        action_label="Thử lại", on_action=on_retry)
            return
        _stale_banner(loaded)
        data = loaded["value"]
        now = datetime.now()
        with ui.element("div").classes("sm-facts"):
            for hours, t_key, h_key in ((1, "t1h", "h1h"), (2, "t2h", "h2h"), (3, "t3h", "h3h")):
                with ui.element("div"):
                    ui.label((now + timedelta(hours=hours)).strftime("%H:00")).classes("sm-fact-k")
                    ui.label(f"{fmt_num(_num(data.get(t_key)))} °C, ẩm {fmt_num(_num(data.get(h_key)), 0)} %").classes("sm-fact-v")
            with ui.element("div"):
                ui.label("Bức xạ cả ngày").classes("sm-fact-k")
                ui.label(f"{fmt_num(_num(data.get('total_radiation_day')), 0)} Wh/m²").classes("sm-fact-v")
            with ui.element("div"):
                ui.label("Bốc thoát hơi nước ET0 cả ngày").classes("sm-fact-k")
                ui.label(f"{fmt_num(_num(data.get('total_et0_day')))} mm").classes("sm-fact-v")
        source_note(f"Nguồn: Open-Meteo, tọa độ cấu hình chung của hệ thống ({data.get('lat')}, {data.get('lon')}), "
                    f"không riêng từng nhà màng. Đọc lúc {fmt_time(loaded.get('read_at'))}.")


def render_ai_suggestion(extra: dict | None) -> None:
    with panel("Dự đoán tưới của AI"):
        ai = ((extra or {}).get("value") or {}).get("ai") if extra else None
        amount = (ai or {}).get("ai_water_suggest")
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            state_panel("empty", "Chưa có dự đoán tưới",
                        "MongoDB chưa lưu dự đoán nào của AI cho nhà màng này. Hệ thống giữ nguyên, không tưới theo mặc định.")
            return
        stamp = None
        try:
            stamp = datetime.strptime(str(ai.get("timestamp")), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
        with ui.element("div").classes("sm-inline"):
            ui.label(f"{amount:g} ml").classes("sm-big")
            ui.label("Đề xuất, không tự điều khiển bơm").classes("sm-note")
        source_note(f"Nguồn: MongoDB telemetry_sensor, dự đoán lưu lúc {fmt_time(stamp)} ({fmt_age(stamp)}).")
