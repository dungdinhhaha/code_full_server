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
    allowed_sources = {"device", "wokwi_synthetic", "smiot_demo_stream", "synthetic_unlabelled", "device_unclassified", "unknown", "other"}
    source_value = source if source in allowed_sources else "other"
    return [f"farm:{_tag_value(farm_key)}", f"node:{_tag_value(node_id)}", f"source:{source_value}"]


def emit_health_gauge(metric: str, value: object, tags: list[str] | None = None) -> None:
    """Emit a bounded operational gauge through the existing optional DogStatsD path."""
    if not _enabled():
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
