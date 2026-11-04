"""Idempotently seed the documented harvest-planning demo lot in MongoDB."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import os
import secrets

import boto3
from PIL import Image
from botocore.exceptions import ClientError

from service.mongodb_store import collection
from service.traceability import IMAGE_FILE, STAGE_LABELS, STAGES, image_bucket

FARM_KEY = "greenhouse_a"
LOT_ID = "melon-lot-harvest-demo-2026-01"
CYCLE_ID = "harvest-window-greenhouse-a-v1"
FRUIT_SET_AT = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
STAGE_DATES = {
    "sowing": (datetime(2026, 9, 1, tzinfo=timezone.utc), "recorded"),
    "seedling": (datetime(2026, 9, 8, tzinfo=timezone.utc), "recorded"),
    "vegetative": (datetime(2026, 9, 20, tzinfo=timezone.utc), "recorded"),
    "flowering_fruiting": (FRUIT_SET_AT, "recorded"),
    "harvest": (datetime(2026, 11, 9, tzinfo=timezone.utc), "forecast"),
}


def _stage_assets() -> dict[str, dict[str, str]]:
    if not IMAGE_FILE.is_file():
        raise FileNotFoundError(f"Stage image asset is missing: {IMAGE_FILE}")
    with Image.open(IMAGE_FILE) as contact_sheet:
        image = contact_sheet.convert("RGB")
        width, height = image.size
        s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-southeast-2"))
        assets: dict[str, dict[str, str]] = {}
        for index, stage in enumerate(STAGES):
            left = round(index * width / len(STAGES)) + (1 if index else 0)
            right = round((index + 1) * width / len(STAGES)) - (1 if index < len(STAGES) - 1 else 0)
            output = BytesIO()
            image.crop((left, 0, right, height)).save(output, format="JPEG", quality=91, optimize=True)
            payload = output.getvalue()
            digest = sha256(payload).hexdigest()
            key = f"traceability/stage-assets/{digest[:16]}/{stage}.jpg"
            try:
                existing = s3.head_object(Bucket=image_bucket(), Key=key)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") not in {"404", "NoSuchKey", "NotFound"}:
                    raise
                existing = None
            if not existing or existing.get("Metadata", {}).get("sha256") != digest:
                s3.upload_fileobj(
                    BytesIO(payload), image_bucket(), key,
                    ExtraArgs={"ContentType": "image/jpeg", "ServerSideEncryption": "AES256",
                               "CacheControl": "private, max-age=3600", "Metadata": {"sha256": digest}},
                )
            assets[stage] = {"s3_key": key, "sha256": digest}
    return assets


def main() -> int:
    now = datetime.now(timezone.utc)
    existing = collection("crop_cycles").find_one({"_id": CYCLE_ID}, {"public_share_token": 1}) or {}
    public_token = existing.get("public_share_token") or secrets.token_urlsafe(24)
    assets = _stage_assets()
    cycle = {
        "farm_key": FARM_KEY,
        "lot_id": LOT_ID,
        "crop_name": "Dưa lưới",
        "demo_scenario": "harvest_window_v1",
        "fruit_set_at": FRUIT_SET_AT,
        "fruit_set_basis": "explicit_demo_fixture",
        "harvest_days_min": 33,
        "harvest_days_max": 45,
        "reference_day": 39,
        "reference_cultivar": "Khang Nguyên (Galia) trong nghiên cứu; giống của lô demo chưa xác định",
        "reference_source": "Tạp chí Khoa học Đại học Đồng Tháp, nghiên cứu dưa lưới Khang Nguyên",
        "source_url": "https://dthujs.vn/index.php/dthujs/article/download/971/886/1945",
        "interpretation": "Planning range only; verify fruit maturity in the field.",
        "public_share_token": public_token,
        "public_share_enabled": True,
        "synthetic": True,
        "updated_at": now,
    }
    collection("crop_cycles").update_one(
        {"_id": CYCLE_ID},
        {"$set": cycle, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )

    events = collection("traceability_events")
    media = collection("crop_stage_media")
    for stage_index, stage in enumerate(STAGES, start=1):
        at, date_kind = STAGE_DATES[stage]
        event_id = f"{FARM_KEY}:{LOT_ID}:stage:{stage}"
        asset = assets[stage]
        event = {
            "farm_key": FARM_KEY,
            "lot_id": LOT_ID,
            "crop_cycle_id": CYCLE_ID,
            "stage_code": stage,
            "stage": stage,
            "stage_label": STAGE_LABELS[stage],
            "stage_index": stage_index,
            "stage_at": at,
            "date_kind": date_kind,
            "date_label": "Dự kiến" if date_kind == "forecast" else "Ngày ghi nhận",
            "s3_bucket": image_bucket(),
            "s3_key": asset["s3_key"],
            "image_sha256": asset["sha256"],
            "image_content_type": "image/jpeg",
            "image_captured": False,
            "image_path": None,
            "is_synthetic": True,
            "source": "crop_stage_media_seed_v2",
            "updated_at": now,
        }
        media.update_one({"_id": event_id}, {"$set": event, "$setOnInsert": {"created_at": now}}, upsert=True)
        if date_kind == "recorded":
            trace_event = {**event, "_id": f"{FARM_KEY}:{LOT_ID}:{stage_index}",
                           "event_type": "crop_stage_recorded", "captured_at": at}
            trace_event.pop("s3_bucket", None)
            trace_event.pop("s3_key", None)
            trace_event.pop("image_sha256", None)
            trace_event.pop("image_content_type", None)
            trace_event.pop("date_label", None)
            events.update_one({"_id": trace_event["_id"]},
                              {"$set": trace_event, "$setOnInsert": {"created_at": now}}, upsert=True)

    print(f"Seeded harvest gallery: farm={FARM_KEY}, lot={LOT_ID}, stages={len(STAGES)}, window=33-45 days.")
    print(f"Customer URL: {os.getenv('SMIOT_PUBLIC_BASE_URL', 'https://13-238-30-218.sslip.io').rstrip('/')}/lot/{public_token}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
