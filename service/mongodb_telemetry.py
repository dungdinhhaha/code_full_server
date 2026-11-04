"""Best-effort live mirror for node telemetry stored in MongoDB Time Series."""

from __future__ import annotations

import logging
import math
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_client: Any = None
_client_lock = threading.Lock()
_logger = logging.getLogger("smiot.mongodb_telemetry")

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass


def _enabled() -> bool:
    return os.getenv("MONGODB_LIVE_INGEST_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _mongo_collection() -> Any | None:
    global _client
    uri = os.getenv("MONGODB_URI")
    if not _enabled() or not uri:
        return None
    if _client is None:
        with _client_lock:
            if _client is None:
                from pymongo import MongoClient

                _client = MongoClient(
                    uri,
                    serverSelectionTimeoutMS=1200,
                    connectTimeoutMS=1200,
                    socketTimeoutMS=2500,
                    appname="smiot-smart-farm-live-telemetry",
                )
    return _client[os.getenv("MONGODB_DATABASE", "smiot")][
        os.getenv("MONGODB_TELEMETRY_COLLECTION", "telemetry")
    ]


def _as_number(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def mirror_node_telemetry(
    *,
    farm_key: str,
    node_id: int,
    timestamp: str,
    source_row_id: int,
    readings: dict[str, object],
) -> bool:
    """Mirror one SQLite node row; failures never roll back SQLite persistence."""
    collection = _mongo_collection()
    if collection is None:
        return False

    try:
        measured_at = datetime.fromisoformat(timestamp.strip().replace("Z", "+00:00"))
        if measured_at.tzinfo is None:
            # SQLite CURRENT_TIMESTAMP values in this app are UTC.
            measured_at = measured_at.replace(tzinfo=timezone.utc)
        else:
            measured_at = measured_at.astimezone(timezone.utc)

        numeric_readings = {
            name: number
            for name, value in readings.items()
            if (number := _as_number(value)) is not None
        }
        if not numeric_readings:
            return False

        collection.insert_one(
            {
                "timestamp": measured_at,
                "meta": {
                    "farm_key": farm_key,
                    "source_table": "telemetry_node_live",
                    "measurement_type": "node",
                    "node_id": int(node_id),
                },
                "readings": numeric_readings,
                "source": {"table": "telemetry_node_live", "row_id": int(source_row_id)},
            }
        )
        return True
    except Exception as exc:
        # Keep the MQTT/SQLite path alive if Atlas is temporarily unreachable.
        _logger.warning("MongoDB live telemetry mirror failed: %s", exc)
        return False
