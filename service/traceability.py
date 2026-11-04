"""MongoDB lot-stage metadata with private S3 image storage."""
from __future__ import annotations

import base64
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from service.mongodb_store import collection

ASSET_ID = "smiot_melon_growth_contact_sheet_v1"
IMAGE_PATH = "/static/device_images/smiot_melon_growth_contact_sheet.jpg"
IMAGE_FILE = Path(__file__).resolve().parents[1] / "static" / "device_images" / "smiot_melon_growth_contact_sheet.jpg"
STAGES = ("sowing", "seedling", "vegetative", "flowering_fruiting", "harvest")
STAGE_LABELS = {
    "sowing": "Gieo hạt",
    "seedling": "Cây con",
    "vegetative": "Sinh trưởng",
    "flowering_fruiting": "Ra hoa, đậu quả",
    "harvest": "Kiểm tra thu hoạch",
}
_LOT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def image_bucket() -> str:
    return os.getenv("TRACEABILITY_IMAGE_BUCKET", "smiot-demo-920235987407-ap-southeast-2")


@lru_cache(maxsize=1)
def _s3_client():
    import boto3
    return boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-southeast-2"))


def signed_image_url(key: str, expires_in: int = 3600) -> str:
    if not key or not key.startswith("traceability/"):
        raise ValueError("invalid traceability image key")
    return _s3_client().generate_presigned_url(
        "get_object", Params={"Bucket": image_bucket(), "Key": key},
        ExpiresIn=max(60, min(int(expires_in), 3600)),
    )


def stage_images_for_lot(farm_key: str, lot_id: str, include_urls: bool = True) -> list[dict[str, Any]]:
    if not _LOT_ID_RE.fullmatch(str(lot_id)):
        return []
    rows = list(collection("crop_stage_media").find(
        {"farm_key": farm_key, "lot_id": lot_id}, {"_id": 0}
    ).sort("stage_index", 1))
    if include_urls:
        for row in rows:
            row["image_url"] = signed_image_url(str(row.get("s3_key", "")))
    return rows


def customer_lot_by_token(token: str) -> dict[str, Any] | None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,64}", str(token)):
        return None
    cycle = collection("crop_cycles").find_one(
        {"public_share_token": token, "public_share_enabled": True},
        {"_id": 0, "farm_key": 1, "lot_id": 1, "crop_name": 1, "fruit_set_at": 1,
         "harvest_days_min": 1, "harvest_days_max": 1, "reference_day": 1},
    )
    if not cycle:
        return None
    cycle["stage_images"] = stage_images_for_lot(cycle["farm_key"], cycle["lot_id"])
    return cycle


def public_lot_url(token: str) -> str:
    base = os.getenv("SMIOT_PUBLIC_BASE_URL", "https://13-238-30-218.sslip.io").rstrip("/")
    return f"{base}/lot/{token}"


def qr_data_uri(url: str) -> str:
    import qrcode
    from io import BytesIO
    image = qrcode.make(url, box_size=7, border=2)
    output = BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def save_capture_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist one idempotent simulated daily capture record."""
    if payload.get("event") != "daily_photo_capture_simulated" or payload.get("simulated") is not True:
        raise ValueError("only explicitly simulated daily capture events are accepted")
    farm_key = str(payload.get("farm_key", ""))
    lot_id = str(payload.get("lot_id", ""))
    stage = str(payload.get("stage", ""))
    day = int(payload.get("simulated_day", 0))
    panel = int(payload.get("image_panel", 0))
    asset_id = str(payload.get("image_asset_id", ""))
    if farm_key != "greenhouse_a" or not _LOT_ID_RE.fullmatch(lot_id):
        raise ValueError("invalid farm key or lot ID")
    if stage not in STAGES or day < 1 or not 1 <= panel <= 5:
        raise ValueError("invalid simulated day, stage, or image panel")
    if asset_id != ASSET_ID:
        raise ValueError("unknown synthetic image asset")

    now = datetime.now(timezone.utc)
    captured_at = payload.get("captured_at")
    if isinstance(captured_at, str):
        try:
            captured_at = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            if captured_at.tzinfo is None:
                captured_at = captured_at.replace(tzinfo=timezone.utc)
        except ValueError:
            captured_at = now
    else:
        captured_at = now
    event_id = f"{farm_key}:{lot_id}:{day}"
    event = {
        "_id": event_id,
        "farm_key": farm_key,
        "lot_id": lot_id,
        "simulated_day": day,
        "stage": stage,
        "stage_index": panel,
        "image_panel": panel,
        "image_asset_id": asset_id,
        "image_path": IMAGE_PATH,
        "image_content_type": "image/jpeg",
        "image_captured": False,
        "is_synthetic": True,
        "source": "wokwi_demo",
        "captured_at": captured_at,
        "updated_at": now,
    }
    collection("traceability_events").update_one(
        {"_id": event_id}, {"$set": event, "$setOnInsert": {"created_at": now}}, upsert=True
    )
    return event


def recent_events(farm_key: str = "greenhouse_a", limit: int = 100) -> list[dict[str, Any]]:
    rows = collection("traceability_events").find(
        {"farm_key": farm_key}, {"_id": 0}
    ).sort([("captured_at", -1), ("simulated_day", -1)]).limit(max(1, min(int(limit), 500)))
    return list(rows)


def lots_for_farm(farm_key: str = "greenhouse_a", limit: int = 100) -> list[dict[str, Any]]:
    """Return recent lots and their traceability coverage for the UI."""
    pipeline = [
        {"$match": {"farm_key": farm_key}},
        {"$group": {
            "_id": "$lot_id",
            "event_count": {"$sum": 1},
            "last_seen": {"$max": "$captured_at"},
            "stages": {"$addToSet": "$stage"},
            "is_synthetic": {"$max": "$is_synthetic"},
        }},
        {"$sort": {"last_seen": -1, "_id": 1}},
        {"$limit": max(1, min(int(limit), 200))},
    ]
    return list(collection("traceability_events").aggregate(pipeline))


def events_for_lot(farm_key: str, lot_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Return a lot's events in growing-day order for its timeline."""
    if not _LOT_ID_RE.fullmatch(str(lot_id)):
        return []
    rows = collection("traceability_events").find(
        {"farm_key": farm_key, "lot_id": lot_id}, {"_id": 0}
    ).sort([("simulated_day", 1), ("captured_at", 1)]).limit(max(1, min(int(limit), 500)))
    return list(rows)


def incidents_for_lot(farm_key: str, lot_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Only return incidents with an explicit persisted lot assignment."""
    if not _LOT_ID_RE.fullmatch(str(lot_id)):
        return []
    from service.incident_lifecycle import incidents_for_lot as query_incidents
    return query_incidents(farm_key, lot_id, limit)


def unassigned_incidents_for_farm(farm_key: str, limit: int = 50) -> list[dict[str, Any]]:
    """Expose unknown lot scope instead of inferring it from a farm or node name."""
    rows = collection("operational_incidents").find(
        {"farm_key": farm_key, "$or": [{"lot_id": None}, {"lot_id": {"$exists": False}},
                                         {"lot_mapping_source": {"$exists": False}}]},
        {"_id": 0},
    ).sort("opened_at", -1).limit(max(1, min(int(limit), 100)))
    return list(rows)
