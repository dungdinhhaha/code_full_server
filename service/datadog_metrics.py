"""Optional DogStatsD metrics for SMIOT telemetry.

Metrics are disabled by default. Enable them with DATADOG_METRICS_ENABLED=true
after a Datadog Agent with DogStatsD enabled is running on the configured host.
"""

from __future__ import annotations

import math
import os
import re
import socket
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass


def _enabled() -> bool:
    return os.getenv("DATADOG_METRICS_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _tag_value(value: object) -> str:
    text = re.sub(r"[^a-zA-Z0-9_.-]", "_", str(value))
    return text[:100] or "unknown"


def _send_gauge(metric: str, value: object, tags: list[str]) -> None:
    try:
        number = float(value)
        if not math.isfinite(number):
            return
        host = os.getenv("DD_AGENT_HOST", "127.0.0.1")
        port = int(os.getenv("DD_DOGSTATSD_PORT", "8125"))
        message = f"{metric}:{number}|g|#{','.join(tags)}".encode("utf-8")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.sendto(message, (host, port))
    except (OSError, TypeError, ValueError):
        # Telemetry ingestion must continue even if Datadog is unavailable.
        return


def metric_tags(farm_key: str, node_id: int, source: str) -> list[str]:
    """Use bounded dimensions; incident and message IDs belong in logs and MongoDB."""
    allowed_sources = {"device", "wokwi_synthetic", "velxio_synthetic", "smiot_demo_stream", "synthetic_unlabelled", "device_unclassified", "unknown", "other"}
    source_value = source if source in allowed_sources else "other"
    return [f"farm:{_tag_value(farm_key)}", f"node:{_tag_value(node_id)}", f"source:{source_value}"]


def emit_health_gauge(metric: str, value: object, tags: list[str] | None = None) -> None:
    """Emit a bounded operational gauge through the existing optional DogStatsD path."""
    if not _enabled():
        return
    _send_gauge(metric, value, tags or [])


def emit_detector_gauge(metric: str, value: object, tags: list[str] | None = None) -> None:
    """Emit detector-only gauges without enabling every SMIOT metric family.

    The dedicated opt-in is useful when W6 is being brought online before the
    rest of the application's custom metrics. The global switch also enables
    these gauges for existing deployments that already emit all SMIOT metrics.
    """
    detector_enabled = os.getenv("SMIOT_DETECTOR_METRICS_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }
    if not (_enabled() or detector_enabled):
        return
    _send_gauge(metric, value, tags or [])


def emit_count(metric: str, tags: list[str] | None = None, value: int = 1) -> None:
    """Emit a bounded DogStatsD count for real app state transitions."""
    if not _enabled():
        return
    try:
        host = os.getenv("DD_AGENT_HOST", "127.0.0.1")
        port = int(os.getenv("DD_DOGSTATSD_PORT", "8125"))
        message = f"{metric}:{int(value)}|c|#{','.join(tags or [])}".encode("utf-8")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.sendto(message, (host, port))
    except (OSError, TypeError, ValueError):
        return


def emit_node_metrics(farm_key: str, node_id: int, node: dict, source: str = "device_unclassified") -> None:
    """Send a bounded set of sensor gauges to the local DogStatsD endpoint."""
    if not _enabled() or not isinstance(node, dict):
        return

    tags = metric_tags(farm_key, node_id, source)
    measurements = (
        ("at", "air_temperature"),
        ("ah", "air_humidity"),
        ("st", "soil_temperature"),
        ("sh", "soil_humidity"),
        ("sec", "soil_ec"),
    )
    for source_field, metric_name in measurements:
        value = node.get(source_field)
        if value is not None:
            _send_gauge(f"smiot.telemetry.{metric_name}", value, tags)
    try:
        from service.mongodb_showcase import vpd_kpa
        vpd = vpd_kpa(node.get("at"), node.get("ah"))
    except (ImportError, TypeError, ValueError, OverflowError):
        vpd = None
    if vpd is not None:
        _send_gauge("smiot.crop.vpd_kpa", vpd, tags)
    _emit_crop_context_metrics(farm_key, node_id, tags, node, vpd, source=source)


SYNTHETIC_DRILL_SOURCES = frozenset({"velxio_synthetic", "smiot_demo_stream"})


def _band_limits(band: object) -> tuple[float, float] | None:
    if not isinstance(band, dict):
        return None
    low, high = band.get("min"), band.get("max")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in (low, high)):
        return None
    return float(low), float(high)


def _outside_band(value: object, band: object) -> bool | None:
    """True/False against an approved band; None when value or band is unusable."""
    limits = _band_limits(band)
    if limits is None or value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number < limits[0] or number > limits[1]


def review_flags_from_bands(bands: dict, node: dict, vpd: object) -> dict[str, int]:
    """Derive W7/W8 review flags from approved envelope bands only.

    A flag is returned only when both the reading and its band exist, so no
    threshold is assumed. Advisory signals; they never authorize actuation.
    """
    flags: dict[str, int] = {}
    soil_band = next((bands.get(k) for k in ("soil_moisture_pct", "soil_humidity_pct", "sh")
                      if bands.get(k)), None)
    soil = _outside_band(node.get("sh"), soil_band)
    if soil is not None:
        flags["smiot.crop.soil_moisture.review_required"] = int(soil)
    checks = [_outside_band(vpd, bands.get("vpd_kpa")),
              _outside_band(node.get("sec"), bands.get("soil_ec"))]
    known = [c for c in checks if c is not None]
    if known:
        flags["smiot.crop.vpd_ec.review_required"] = int(any(known))
    return flags


def _emit_crop_context_metrics(farm_key: str, node_id: int, tags: list[str],
                               node: dict | None = None, vpd: object = None,
                               source: str = "device_unclassified") -> None:
    """Publish only database-backed crop context used by W7/W8 review workflows.

    A missing or unapproved envelope is emitted as zero instead of being
    silently treated as approved. These signals are advisory gates only; they
    never authorize irrigation, ventilation, drainage, or nutrient actions.
    """
    approved = 0
    stage_valid = 0
    review_flags: dict[str, int] = {}
    synthetic_input = source in SYNTHETIC_DRILL_SOURCES
    drill_used = False
    try:
        from service.mongodb_store import collection
        cycle = collection("crop_cycles").find_one(
            {"farm_key": farm_key, "status": {"$in": ["active", "growing", "in_progress"]}},
            {"_id": 0, "crop_name": 1, "cultivar": 1, "current_stage": 1, "stage_code": 1},
            sort=[("updated_at", -1)],
        )
        if cycle:
            stage = cycle.get("current_stage") or cycle.get("stage_code")
            if stage:
                from service.stage_envelopes import get_effective_stage_envelope
                extra = {"allow_drill": True} if synthetic_input else {}
                envelope = get_effective_stage_envelope(
                    crop=str(cycle.get("crop_name") or "melon"),
                    stage=str(stage), cultivar=cycle.get("cultivar"), **extra,
                )
                # Drill envelopes are valid only for synthetic input data.
                if isinstance(envelope, dict) and envelope.get("drill") and not synthetic_input:
                    envelope = None
                if isinstance(envelope, dict):
                    drill_used = bool(envelope.get("drill"))
                    bands = envelope.get("bands") or {}
                    approved = 1
                    stage_valid = int(bool(bands.get("sh") or bands.get("soil_moisture_pct")
                                           or bands.get("vpd_kpa") or bands.get("soil_ec")))
                    if isinstance(node, dict):
                        review_flags = review_flags_from_bands(bands, node, vpd)
    except Exception:
        # Metrics must never interrupt telemetry persistence when Mongo or the
        # optional crop-context collections are unavailable.
        approved = 0
        stage_valid = 0
        review_flags = {}
        drill_used = False
    if drill_used:
        # Synthetic rehearsal thresholds are not an agronomic approval.
        approved = 0
        review_tags = [t for t in tags if not t.startswith("source:")] + ["source:synthetic_drill"]
    else:
        review_tags = tags
    _send_gauge("smiot.crop.envelope.approved", approved, tags)
    _send_gauge("smiot.crop.stage_context.valid", stage_valid, tags)
    for metric, flag in review_flags.items():
        emit_health_gauge(metric, flag, review_tags)


def emit_provenance_metrics(farm_key: str, node_id: int, source: str,
                            metadata: dict) -> None:
    """Emit only observed reboot/sequence anomalies; identifiers stay out of tags."""
    if not _enabled() or not isinstance(metadata, dict):
        return
    tags = metric_tags(farm_key, node_id, source)
    _emit_provenance_flags(tags, metadata)


def emit_device_provenance_metrics(farm_key: str, device_type: str, source: str,
                                   metadata: dict) -> None:
    """Emit provenance counters for non-node device streams with bounded labels."""
    if not _enabled() or not isinstance(metadata, dict):
        return
    device_aliases = {
        "flow_meter": "flow", "ec_sensor": "ec", "ph_sensor": "ph",
        "drain_sensor": "drain", "ventilation_feedback": "ventilation",
        "virtual_plc": "plc", "inverter": "inverter",
    }
    safe_type = device_aliases.get(device_type, device_type if device_type in {
        "flow", "ec", "ph", "drain", "ventilation", "plc", "inverter",
    } else "other")
    tags = [f"farm:{_tag_value(farm_key)}", f"device_type:{safe_type}",
            f"source:{source if source in {'device', 'wokwi_synthetic', 'velxio_synthetic', 'smiot_demo_stream', 'synthetic_unlabelled', 'device_unclassified', 'unknown', 'other'} else 'other'}"]
    _emit_provenance_flags(tags, metadata)


def _emit_provenance_flags(tags: list[str], metadata: dict) -> None:
    if metadata.get("reboot_detected") is True:
        emit_count("smiot.device.reboot_detected", tags)
    for field, metric in (
        ("sequence_gap", "smiot.telemetry.sequence_gap"),
        ("sequence_duplicate", "smiot.telemetry.sequence_duplicate"),
        ("sequence_regression", "smiot.telemetry.sequence_regression"),
    ):
        value = metadata.get(field)
        if field == "sequence_gap":
            try:
                missing = max(0, int(value or 0))
            except (TypeError, ValueError):
                missing = 0
            if missing:
                emit_count(metric, tags, value=missing)
        elif value is True:
            emit_count(metric, tags)
    uptime = metadata.get("uptime_seconds")
    if uptime is not None:
        _send_gauge("smiot.device.uptime_seconds", uptime, tags)


def emit_actuator_metrics(farm_key: str, feedback: dict,
                          source: str = "device_unclassified") -> None:
    """Emit bounded per-farm pump/valve/flow/pressure feedback gauges."""
    if not _enabled() or not isinstance(feedback, dict):
        return
    tags = [
        f"farm:{_tag_value(farm_key)}",
        f"source:{source if source in {'device', 'wokwi_synthetic', 'velxio_synthetic', 'smiot_demo_stream', 'synthetic_unlabelled', 'device_unclassified', 'unknown', 'other'} else 'other'}",
    ]
    measurements = (
        ("flow_line1_lpm", "smiot.actuator.flow_lpm", ["line:1"]),
        ("flow_line2_lpm", "smiot.actuator.flow_lpm", ["line:2"]),
        ("flow_line1_total_l", "smiot.actuator.total_volume_l", ["line:1"]),
        ("flow_line2_total_l", "smiot.actuator.total_volume_l", ["line:2"]),
        ("pressure_bar", "smiot.actuator.pressure_bar", []),
        ("pump_line1_on", "smiot.actuator.pump_on", ["line:1"]),
        ("pump_line2_on", "smiot.actuator.pump_on", ["line:2"]),
        ("valve_open", "smiot.actuator.valve_open", []),
        ("safe_mode_active", "smiot.actuator.safe_mode_active", []),
        ("fan_rpm", "smiot.actuator.fan_rpm", []),
        ("vent_cmd", "smiot.actuator.vent_command", []),
        ("vent_state", "smiot.actuator.vent_state", []),
    )
    for field, metric, extra_tags in measurements:
        value = feedback.get(field)
        if value is not None:
            _send_gauge(metric, int(value) if isinstance(value, bool) else value,
                        [*tags, *extra_tags])
