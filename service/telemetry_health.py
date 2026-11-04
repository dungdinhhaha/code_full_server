"""Independent MongoDB-backed telemetry freshness watchdog for Datadog."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from service.datadog_metrics import emit_health_gauge, metric_tags
from service.mongodb_store import collection, database

LOGGER = logging.getLogger("smiot.telemetry_health")
FARMS = ("greenhouse_a", "greenhouse_b", "greenhouse_c", "greenhouse_d")
_thread: threading.Thread | None = None
_lock = threading.Lock()
_last_state: dict[tuple[str, int], str] = {}
_last_flatline_state: dict[tuple[str, int, str], bool] = {}
_FLATLINE_SAMPLE_COUNT = 10
_FLATLINE_EPSILON = 0.01
_FLATLINE_LOOKBACK_SECONDS = 600


def _setting(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def inspect_once() -> list[dict[str, Any]]:
    """Inspect newest sample per farm/node and emit low-cardinality health signals."""
    now = datetime.now(timezone.utc)
    stale_after = _setting("SMIOT_TELEMETRY_STALE_SECONDS", 90)
    base_tags = ["service:smiot-smart-farm", "env:demo"]
    outcomes: list[dict[str, Any]] = []
    try:
        database().command("ping")
        emit_health_gauge("smiot.dependency.mongo.up", 1, base_tags)
    except Exception as exc:
        emit_health_gauge("smiot.dependency.mongo.up", 0, base_tags)
        LOGGER.error(json.dumps({"event": "smiot_dependency_check", "dependency": "mongodb",
                                 "healthy": False, "error_type": type(exc).__name__}, separators=(",", ":")))
    try:
        from service import mqtt
        connected = bool(mqtt.mqtt_client and mqtt.mqtt_client.is_connected())
        emit_health_gauge("smiot.dependency.mqtt.up", int(connected), base_tags)
    except Exception:
        connected = False
        emit_health_gauge("smiot.dependency.mqtt.up", 0, base_tags)

    telemetry = collection("telemetry")
    for farm in FARMS:
        for node_id in (1, 2):
            row = telemetry.find_one(
                {"meta.farm_key": farm, "meta.measurement_type": "node", "meta.node_id": node_id},
                {"timestamp": 1, "source.source": 1, "source.simulator": 1, "source.synthetic": 1}, sort=[("timestamp", -1)],
            )
            if not row or not isinstance(row.get("timestamp"), datetime):
                age, source, current = float(stale_after * 10), "unknown", "missing"
            else:
                stamp = row["timestamp"]
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                age = max(0.0, (now - stamp.astimezone(timezone.utc)).total_seconds())
                source_meta = row.get("source") or {}
                source = str(source_meta.get("source") or source_meta.get("simulator") or (
                    "synthetic_unlabelled" if source_meta.get("synthetic") is True else "device_unclassified"
                ))
                if source not in {"device", "wokwi_synthetic", "smiot_demo_stream", "synthetic_unlabelled", "device_unclassified"}:
                    source = "other"
                current = "stale" if age > stale_after else "fresh"
            tags = metric_tags(farm, node_id, source)
            emit_health_gauge("smiot.telemetry.sample_age_seconds", age, tags)
            emit_health_gauge("smiot.telemetry.fresh", int(current == "fresh"), tags)
            # Detect a stuck reading from the values actually persisted in Mongo,
            # rather than trusting the simulator's requested mode or a derived
            # Datadog diff() expression. Require ten fresh, consecutive samples
            # so ordinary short-lived stability does not page the operator.
            # The lookback must cover the cadence of all required samples;
            # freshness is independently gated by the newest sample above.
            cutoff = now - timedelta(seconds=max(
                _FLATLINE_LOOKBACK_SECONDS,
                _FLATLINE_SAMPLE_COUNT * _setting("SMIOT_DEMO_INTERVAL_SECONDS", 30) * 2,
            ))
            recent = list(telemetry.find(
                {"meta.farm_key": farm, "meta.measurement_type": "node",
                 "meta.node_id": node_id, "timestamp": {"$gte": cutoff},
                 "readings.soil_hum": {"$type": "number"}},
                {"timestamp": 1, "readings.soil_hum": 1, "source.source": 1,
                 "source.simulator": 1, "source.synthetic": 1},
            ).sort("timestamp", -1).limit(_FLATLINE_SAMPLE_COUNT))
            values = [float((sample.get("readings") or {}).get("soil_hum")) for sample in recent]
            newest_source = (recent[0].get("source") or {}) if recent else {}
            flatline_source = str(newest_source.get("source") or newest_source.get("simulator") or source)
            fresh_sample_count = len(values)
            flatline = (
                current == "fresh"
                and fresh_sample_count == _FLATLINE_SAMPLE_COUNT
                and max(values) - min(values) <= _FLATLINE_EPSILON
            )
            flatline_tags = metric_tags(farm, node_id, flatline_source)
            emit_health_gauge("smiot.telemetry.sensor_flatline", int(flatline), flatline_tags)
            flatline_key = (farm, node_id, flatline_source)
            if flatline != _last_flatline_state.get(flatline_key):
                LOGGER.info(json.dumps({
                    "event": "smiot_sensor_flatline_transition",
                    "farm": farm,
                    "node": node_id,
                    "source": flatline_source,
                    "flatline": flatline,
                    "sample_count": fresh_sample_count,
                    "required_sample_count": _FLATLINE_SAMPLE_COUNT,
                    "soil_humidity_range_pct": (
                        [round(min(values), 3), round(max(values), 3)] if values else None
                    ),
                }, separators=(",", ":")))
                _last_flatline_state[flatline_key] = flatline
            outcome = {"farm": farm, "node": node_id, "source": source, "age_seconds": round(age, 1),
                       "state": current, "mqtt_connected": connected,
                       "soil_humidity_flatline": flatline,
                       "flatline_sample_count": fresh_sample_count}
            outcomes.append(outcome)
            key = (farm, node_id)
            if current != _last_state.get(key):
                LOGGER.info(json.dumps({"event": "smiot_telemetry_freshness_transition", **outcome,
                                        "stale_after_seconds": stale_after}, separators=(",", ":")))
                _last_state[key] = current
    return outcomes


def _run() -> None:
    interval = _setting("SMIOT_TELEMETRY_HEALTH_INTERVAL_SECONDS", 30)
    while True:
        try:
            inspect_once()
        except Exception as exc:
            LOGGER.exception("Telemetry freshness inspection failed: %s", type(exc).__name__)
        time.sleep(interval)


def start_telemetry_health_watchdog() -> None:
    global _thread
    with _lock:
        if _thread and _thread.is_alive():
            return
        _thread = threading.Thread(target=_run, name="smiot-telemetry-health", daemon=True)
        _thread.start()
