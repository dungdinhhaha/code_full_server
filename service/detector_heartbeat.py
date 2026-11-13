"""Independent liveness and input/evaluation-age metrics for the advisory detector.

The periodic publisher is separate from the MQTT callback and the detector
evaluation path. This lets monitoring distinguish an absent input stream from
a healthy input stream whose advisory evaluation has stopped advancing.
"""

from __future__ import annotations

import logging
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from service.datadog_metrics import emit_detector_gauge
from service.farm_registry import FARM_KEYS

LOGGER = logging.getLogger("smiot.detector_heartbeat")
_lock = threading.Lock()
_thread_lock = threading.Lock()
_last_input_at: dict[str, datetime] = {}
_last_evaluation_at: dict[str, float] = {}
_input_probe_ok: dict[str, int] = {}
_demo_evaluation_fault_farms: set[str] = set()
_thread: threading.Thread | None = None


def _farm_key(value: object) -> str | None:
    key = str(value or "")
    return key if key in FARM_KEYS else None


def mark_detector_input(farm_key: object) -> None:
    """Record a sample only after MongoDB persistence has succeeded."""
    key = _farm_key(farm_key)
    if key is None:
        return
    with _lock:
        _last_input_at[key] = datetime.now(timezone.utc)


def mark_detector_evaluation(farm_key: object) -> None:
    """Record completion only after advisory evaluation/persistence succeeds."""
    key = _farm_key(farm_key)
    if key is None:
        return
    with _lock:
        _last_evaluation_at[key] = time.monotonic()
    # A W6 recovery is only complete after the detector has actually produced
    # a fresh evaluation.  The normal-control ACK merely means the fault flag
    # was cleared; this closes the incident only on the first real evaluation.
    try:
        from service.special_incident_correlation import active_special_incident, recover_special_incident
        incident = active_special_incident("detector_heartbeat_missing", key)
        if incident:
            recover_special_incident(
                str(incident.get("_id") or incident.get("incident_id")),
                farm_key=key,
                verification={"fresh_evaluation": True, "farm_key": key,
                              "verified_at": datetime.now(timezone.utc).isoformat(),
                              "source": "detector_evaluation"},
                event="recovered_detector_evaluation",
            )
    except Exception as exc:
        LOGGER.debug("Could not close correlated W6 incident (%s)", type(exc).__name__)


def set_demo_evaluation_fault(farm_key: object, active: bool) -> bool:
    """Toggle a synthetic, farm-scoped W6 evaluation-heartbeat fault."""
    key = _farm_key(farm_key)
    if key is None:
        return False
    with _lock:
        if active:
            _demo_evaluation_fault_farms.add(key)
        else:
            _demo_evaluation_fault_farms.discard(key)
    return True


def has_advisory_input(readings: object) -> bool:
    """True only if this node sample contains an evaluatable advisory reading."""
    if not isinstance(readings, dict):
        return False
    # MQTT node payloads use compact device keys (at/ah); normalized payloads
    # may use the long names. Accept both forms so a persisted node sample can
    # advance the evaluation heartbeat without inventing a separate signal.
    for field in ("air_temp", "air_hum", "at", "ah"):
        value = readings.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            return True
    return False


def _interval_seconds() -> int:
    try:
        return min(300, max(5, int(os.getenv("SMIOT_DETECTOR_HEARTBEAT_INTERVAL_SECONDS", "30"))))
    except (TypeError, ValueError):
        return 30


def _evaluation_stale_after_seconds() -> int:
    """Maximum age of a successful per-farm detector evaluation for W6."""
    try:
        return min(3600, max(30, int(os.getenv("SMIOT_DETECTOR_EVALUATION_STALE_AFTER_SECONDS", "180"))))
    except (TypeError, ValueError):
        return 180


def _refresh_persisted_input_times() -> None:
    """Refresh each farm's last input from Mongo so process restarts retain context."""
    try:
        from service.mongodb_store import collection

        telemetry = collection("telemetry")
    except Exception as exc:
        LOGGER.debug("Could not open telemetry collection for detector heartbeat (%s)", type(exc).__name__)
        return

    def _latest_for_farm(farm_key: str):
        query = {
            "meta.farm_key": farm_key,
            "meta.source_table": {"$in": ["telemetry_node", "telemetry_node_live"]},
            "meta.measurement_type": "node",
            "source.demo_seed_version": {"$ne": "smiot-demo-history-v1"},
        }
        row = telemetry.find_one(
            query, {"timestamp": 1, "_id": 0},
            sort=[("timestamp", -1)], max_time_ms=2500,
        )
        return farm_key, row.get("timestamp") if row else None

    try:
        # Reuse the established farm+measurement+timestamp index, but issue
        # the small bounded lookups concurrently to avoid 10x serial latency.
        with ThreadPoolExecutor(max_workers=min(10, len(FARM_KEYS))) as pool:
            futures = [pool.submit(_latest_for_farm, farm_key) for farm_key in FARM_KEYS]
            latest_by_farm = dict(future.result() for future in as_completed(futures))
        with _lock:
            for farm_key in FARM_KEYS:
                stamp = latest_by_farm.get(farm_key)
                if isinstance(stamp, datetime):
                    if stamp.tzinfo is None:
                        stamp = stamp.replace(tzinfo=timezone.utc)
                    _last_input_at[farm_key] = stamp.astimezone(timezone.utc)
                else:
                    _last_input_at.pop(farm_key, None)
                _input_probe_ok[farm_key] = 1
    except Exception as exc:
        # Keep the last known values on transient query errors; never turn
        # database unavailability into a fabricated "no input" result.
        with _lock:
            for farm_key in FARM_KEYS:
                _input_probe_ok[farm_key] = 0
        LOGGER.debug("Could not refresh detector input times (%s)", type(exc).__name__)


def _emit_once(now: float | None = None) -> None:
    """Emit independent liveness plus bounded per-farm input/evaluation ages."""
    current = time.monotonic() if now is None else now
    _refresh_persisted_input_times()
    wall_now = datetime.now(timezone.utc)
    with _lock:
        input_times = dict(_last_input_at)
        evaluation_times = dict(_last_evaluation_at)
        probe_status = dict(_input_probe_ok)
        demo_fault_farms = set(_demo_evaluation_fault_farms)

    for farm_key in FARM_KEYS:
        tags = ["detector:agronomic_advisory", f"farm:{farm_key}"]
        emit_detector_gauge("smiot.detector.watchdog_heartbeat", 1, tags)
        input_at = input_times.get(farm_key)
        evaluation_at = evaluation_times.get(farm_key)
        emit_detector_gauge("smiot.detector.input_seen", int(input_at is not None), tags)
        emit_detector_gauge("smiot.detector.input_probe_ok", probe_status.get(farm_key, 0), tags)
        emit_detector_gauge("smiot.detector.evaluation_seen", int(evaluation_at is not None), tags)
        evaluation_age = max(0, current - evaluation_at) if evaluation_at is not None else None
        # watchdog_heartbeat proves this publisher/app process is alive. This
        # separate signal proves the advisory evaluation path is still making
        # progress; keeping them distinct lets W6 identify a stalled detector.
        evaluation_fresh = (
            evaluation_age is not None
            and evaluation_age <= _evaluation_stale_after_seconds()
            and farm_key not in demo_fault_farms
        )
        emit_detector_gauge("smiot.detector.evaluation_heartbeat", int(evaluation_fresh), tags)
        if input_at is not None:
            emit_detector_gauge("smiot.detector.input_age_seconds", max(0, (wall_now - input_at).total_seconds()), tags)
        if evaluation_age is not None:
            emit_detector_gauge("smiot.detector.evaluation_age_seconds", evaluation_age, tags)


def _run() -> None:
    interval = _interval_seconds()
    while True:
        try:
            _emit_once()
        except Exception as exc:
            # The heartbeat publisher must never interfere with telemetry.
            LOGGER.warning("Detector heartbeat emission failed (%s)", type(exc).__name__)
        time.sleep(interval)


def start_detector_heartbeat() -> None:
    """Start one daemon publisher; safe to call repeatedly during app startup."""
    global _thread
    with _thread_lock:
        if _thread and _thread.is_alive():
            return
        _thread = threading.Thread(target=_run, name="smiot-detector-heartbeat", daemon=True)
        _thread.start()
