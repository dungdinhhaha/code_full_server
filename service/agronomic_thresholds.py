"""Shared melon monitoring guardrails used for advisory status across the app.

These thresholds are monitoring advice only. They must never authorize irrigation,
fan, valve, or pump actions. Soil moisture is intentionally unclassified until the
probe is calibrated to the substrate and its water-holding-capacity basis.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any
from uuid import uuid4

from service.mongodb_store import collection
from service.farm_registry import FARM_LABELS


THRESHOLDS: dict[str, dict[str, Any]] = {
    "air_temp_c": {
        "label": "Nhiệt độ không khí",
        "unit": "°C",
        "below": 10.0,
        "above": 35.0,
        "message_below": "Lạnh hơn mức theo dõi cho dưa lưới",
        "message_above": "Nóng hơn mức theo dõi cho dưa lưới",
        "source": "Penn State Extension: dưới 50°F hoặc trên 95°F có thể làm chậm sinh trưởng",
        "url": "https://extension.psu.edu/cantaloupe-muskmelon-production",
    },
    "air_humidity_pct": {
        "label": "Độ ẩm không khí",
        "unit": "%",
        "above": 85.0,
        "message_above": "Ẩm cao — kiểm tra thông gió và đọng sương",
        "source": "Ngưỡng nhắc kiểm tra do dự án chọn; tài liệu trồng dưa lưới lưu ý ẩm cao làm tăng nguy cơ bệnh lá",
        "url": "https://pau.edu/content/ccil/pf/pp_veg.pdf",
    },
}


def classify_advisory(metric: str, value: Any) -> dict[str, Any]:
    """Classify a reading using shared UI-only thresholds; unknown metrics stay neutral."""
    config = THRESHOLDS.get(metric)
    if not config or isinstance(value, bool):
        return {"state": "unclassified", "message": None, "threshold": None}
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return {"state": "unclassified", "message": None, "threshold": None}
    if not math.isfinite(numeric):
        return {"state": "unclassified", "message": None, "threshold": None}
    if config.get("below") is not None and numeric < config["below"]:
        return {"state": "advisory", "message": config["message_below"], "threshold": config["below"], "source": config["source"], "url": config["url"]}
    if config.get("above") is not None and numeric > config["above"]:
        return {"state": "advisory", "message": config["message_above"], "threshold": config["above"], "source": config["source"], "url": config["url"]}
    return {"state": "within_watch_band", "message": None, "threshold": None, "source": config["source"], "url": config["url"]}


def soil_moisture_calibration_note() -> str:
    return "Độ ẩm đất chưa tô ngưỡng: cần hiệu chuẩn đầu dò theo giá thể và độ giữ nước của lô."


def record_reading_transition(farm_key: str, node_id: int, readings: dict[str, Any]) -> list[dict[str, Any]]:
    """Persist advisory state transitions for every farm; never controls actuators."""
    emitted: list[dict[str, Any]] = []
    mapping = (("air_temp_c", "air_temp"), ("air_humidity_pct", "air_hum"))
    advisories = collection("agronomic_advisories")
    notices = collection("notifications")
    for metric, field in mapping:
        value = readings.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        result = classify_advisory(metric, value)
        key = f"{farm_key}:node{int(node_id)}:{metric}"
        prior = advisories.find_one({"_id": key}, {"status": 1}) or {}
        active = result["state"] == "advisory"
        now = datetime.now(timezone.utc)
        if active and prior.get("status") != "active":
            label = FARM_LABELS.get(farm_key, farm_key)
            message = f"{label} · Node {node_id}: {result['message']} ({float(value):.1f}{THRESHOLDS[metric]['unit']})"
            event = {"_id": str(uuid4()), "message": message, "category": "agronomy",
                     "severity": "warning", "created_at": now.isoformat(), "farm_key": farm_key,
                     "node_id": int(node_id), "advisory_id": key, "metric": metric,
                     "value": float(value), "threshold": result.get("threshold"),
                     "source": "shared_agronomic_thresholds", "synthetic": True}
            notices.insert_one(event)
            emitted.append(event)
        elif not active and prior.get("status") == "active":
            label = FARM_LABELS.get(farm_key, farm_key)
            message = f"{label} · Node {node_id}: {THRESHOLDS[metric]['label']} đã trở lại dải theo dõi."
            event = {"_id": str(uuid4()), "message": message, "category": "agronomy",
                     "severity": "info", "created_at": now.isoformat(), "farm_key": farm_key,
                     "node_id": int(node_id), "advisory_id": key, "metric": metric,
                     "value": float(value), "source": "shared_agronomic_thresholds", "synthetic": True}
            notices.insert_one(event)
            emitted.append(event)
        advisories.update_one(
            {"_id": key},
            {"$set": {"farm_key": farm_key, "node_id": int(node_id), "metric": metric,
                      "status": "active" if active else "clear", "value": float(value),
                      "threshold": result.get("threshold"), "message": result.get("message"),
                      "source": result.get("source"), "source_url": result.get("url"),
                      "updated_at": now, "synthetic": True},
             "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    return emitted
