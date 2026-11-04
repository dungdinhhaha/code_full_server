"""Normalize telemetry origin and transport timestamps without inventing sensor time."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


SYNTHETIC_SOURCES = {
    "smiot_demo_stream", "wokwi_synthetic", "local_traceability_demo",
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


def metadata_for_payload(payload: dict[str, Any], received_at: datetime | None = None) -> dict[str, Any]:
    """Return bounded provenance fields; message IDs stay in Mongo/logs, never metric tags."""
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
    }
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
    bridge_received_at = parse_datetime(payload.get("bridge_received_at"))
    if bridge_received_at:
        result["bridge_received_at"] = bridge_received_at
        bridge_lag_ms = (received_at - bridge_received_at).total_seconds() * 1000
        if 0 <= bridge_lag_ms <= 24 * 60 * 60 * 1000:
            result["bridge_to_app_lag_ms"] = round(bridge_lag_ms, 1)
    measured_at = parse_datetime(payload.get("measured_at"))
    if measured_at:
        result["device_measured_at"] = measured_at
        lag_ms = (received_at - measured_at).total_seconds() * 1000
        if 0 <= lag_ms <= 7 * 24 * 60 * 60 * 1000:
            result["device_to_app_lag_ms"] = round(lag_ms, 1)
    if device_id is not None and boot_id is not None and sequence is not None:
        result["message_id"] = f"{device_id}:{boot_id}:{sequence}"[:200]
    return result
