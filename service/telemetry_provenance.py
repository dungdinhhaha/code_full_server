"""Normalize telemetry origin and transport timestamps without inventing sensor time."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

SYNTHETIC_SOURCES = {
    "smiot_demo_stream", "wokwi_synthetic", "velxio_synthetic", "local_traceability_demo",
    "synthetic_auto_trigger_test", "synthetic_safe_mode_recovery",
}


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class SequenceTracker:
    """In-memory last (boot_id, sequence) per key, so the write path stays O(1).

    Detects reboot (boot_id changed), sequence gap, duplicate and regression.
    Rows without boot_id are never judged: reboot_state stays "unknown".
    State is lost on app restart (first sample after restart is just "first_seen").
    """

    def __init__(self) -> None:
        self._last: dict[Any, tuple[str, int | None]] = {}
        self._lock = threading.Lock()

    def observe(self, key: Any, boot_id: Any, sequence: Any) -> dict[str, Any]:
        flags: dict[str, Any] = {}
        if boot_id is None:
            return flags
        boot = str(boot_id)[:100]
        try:
            seq = int(sequence) if sequence is not None else None
        except (TypeError, ValueError):
            seq = None
        with self._lock:
            prev = self._last.get(key)
            self._last[key] = (boot, seq if seq is not None else (prev[1] if prev and prev[0] == boot else None))
        if prev is None:
            return flags
        prev_boot, prev_seq = prev
        if prev_boot != boot:
            flags["reboot_detected"] = True
            flags["previous_boot_id"] = prev_boot
            return flags
        if seq is None or prev_seq is None:
            return flags
        if seq == prev_seq:
            flags["sequence_duplicate"] = True
        elif seq < prev_seq:
            flags["sequence_regression"] = True
        elif seq > prev_seq + 1:
            flags["sequence_gap"] = seq - prev_seq - 1
        return flags


_TRACKER = SequenceTracker()


def metadata_for_payload(payload: dict[str, Any], received_at: datetime | None = None,
                         track_key: Any = None) -> dict[str, Any]:
    """Return bounded provenance fields; message IDs stay in Mongo/logs, never metric tags.

    With track_key (e.g. (farm, node)) also flags reboot/sequence anomalies into the result.
    """
    received_at = received_at or datetime.now(timezone.utc)
    source_name = str(payload.get("source") or "device_unclassified")[:64]
    synthetic = bool(payload.get("synthetic")) or source_name in SYNTHETIC_SOURCES
    device_id = payload.get("device_id")
    boot_id = payload.get("boot_id")
    sequence = payload.get("sample_sequence", payload.get("sequence"))
    incident_id = payload.get("incident_id")
    result: dict[str, Any] = {
        "source": source_name,
        "synthetic": synthetic,
        "provenance": "declared" if payload.get("source") else "unclassified",
        "app_received_at": received_at,
        # Old rows without boot metadata must remain explicitly unknown; never infer
        # a reboot from a missing field or from sequence values alone.
        "reboot_state": "known" if boot_id is not None else "unknown",
    }
    for field in ("device_profile", "dataset_id", "scenario_code", "scenario_run_id"):
        value = payload.get(field)
        if value is not None and str(value).strip():
            result[field] = str(value)[:128]
    if synthetic:
        result["simulator"] = source_name
    if device_id is not None:
        result["device_id"] = str(device_id)[:100]
    if incident_id is not None:
        # Keep incident identity in Mongo/logs/traces, never as a metric tag.
        result["incident_id"] = str(incident_id)[:100]
    if boot_id is not None:
        result["boot_id"] = str(boot_id)[:100]
    if sequence is not None:
        try:
            result["sequence"] = int(sequence)
        except (TypeError, ValueError):
            result["sequence_invalid"] = True
    uptime = payload.get("uptime_seconds")
    if uptime is not None:
        try:
            result["uptime_seconds"] = max(0, int(uptime))
        except (TypeError, ValueError):
            result["uptime_invalid"] = True
    bridge_received_at = parse_datetime(payload.get("bridge_received_at"))
    if bridge_received_at:
        result["bridge_received_at"] = bridge_received_at
        bridge_lag_ms = (received_at - bridge_received_at).total_seconds() * 1000
        if 0 <= bridge_lag_ms <= 24 * 60 * 60 * 1000:
            result["bridge_to_app_lag_ms"] = round(bridge_lag_ms, 1)
    measured_at = parse_datetime(payload.get("measured_at") or payload.get("timestamp"))
    if measured_at:
        result["device_measured_at"] = measured_at
        lag_ms = (received_at - measured_at).total_seconds() * 1000
        if 0 <= lag_ms <= 7 * 24 * 60 * 60 * 1000:
            result["device_to_app_lag_ms"] = round(lag_ms, 1)
    if device_id is not None and boot_id is not None and sequence is not None:
        result["message_id"] = f"{device_id}:{boot_id}:{sequence}"[:200]
    if track_key is not None:
        flags = _TRACKER.observe(track_key, boot_id, result.get("sequence"))
        if flags:
            result.update(flags)
    return result
