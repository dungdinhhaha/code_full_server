"""Publish a complete synthetic melon-lot timeline through the local MQTT app."""

from __future__ import annotations

import json
import os
import sys
import time
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=False)

from service.mongodb_store import collection
from service.traceability import ASSET_ID, IMAGE_FILE, STAGES

FARM_KEY = "greenhouse_a"
LOT_PREFIX = "melon-lot-local-demo-"
TOPIC = "farm/traceability/event"


def make_client() -> mqtt.Client:
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"smiot-traceability-demo-{int(time.time())}")
    except AttributeError:
        return mqtt.Client(client_id=f"smiot-traceability-demo-{int(time.time())}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Send repeatable synthetic traceability history through the local SMIOT MQTT app.")
    parser.add_argument("--lots", type=int, default=10, help="number of demo lots to populate (default: 10)")
    parser.add_argument("--days", type=int, default=15, help="simulated daily records per lot (default: 15)")
    args = parser.parse_args()
    if not 1 <= args.lots <= 50 or not 5 <= args.days <= 90:
        parser.error("--lots must be 1..50 and --days must be 5..90")

    if not IMAGE_FILE.is_file():
        raise FileNotFoundError(f"Synthetic image asset is missing: {IMAGE_FILE}")

    host = os.getenv("MQTT_HOST", "127.0.0.1").strip()
    port = int(os.getenv("MQTT_PORT", "1883"))
    client = make_client()
    client.connect(host, port, keepalive=30)
    client.loop_start()
    try:
        time.sleep(0.5)
        now = datetime.now(timezone.utc)
        expected_ids: set[str] = set()
        for lot_number in range(1, args.lots + 1):
            lot_id = f"{LOT_PREFIX}{lot_number:03d}"
            for day in range(1, args.days + 1):
                stage_index = min(day - 1, len(STAGES) - 1)
                stage = STAGES[stage_index]
                payload = {
                    "event": "daily_photo_capture_simulated",
                    "farm_key": FARM_KEY,
                    "lot_id": lot_id,
                    "simulated_day": day,
                    "stage": stage,
                    "stage_index": stage_index + 1,
                    "simulated": True,
                    "image_captured": False,
                    "capture_kind": "synthetic_asset",
                    "image_asset_id": ASSET_ID,
                    "image_panel": stage_index + 1,
                    "captured_at": (now - timedelta(days=(args.lots - lot_number) * 2 + (args.days - day))).isoformat(timespec="seconds").replace("+00:00", "Z"),
                    "source": "local_traceability_demo",
                }
                info = client.publish(TOPIC, json.dumps(payload, separators=(",", ":")), qos=1, retain=False)
                info.wait_for_publish(timeout=5)
                if not info.is_published():
                    raise RuntimeError(f"Local MQTT did not confirm event for {lot_id} day {day}")
                expected_ids.add(f"{FARM_KEY}:{lot_id}:{day}")
            print(f"Published {args.days} simulated daily events for {lot_id}", flush=True)

        deadline = time.monotonic() + 20
        found: list[dict] = []
        while time.monotonic() < deadline:
            found = list(collection("traceability_events").find(
                {"farm_key": FARM_KEY, "lot_id": {"$regex": f"^{LOT_PREFIX}"}},
                {"_id": 1, "lot_id": 1, "stage": 1, "simulated_day": 1, "image_path": 1},
            ))
            if expected_ids.issubset({row["_id"] for row in found}):
                break
            time.sleep(1)

        received = {row["_id"] for row in found}
        if not expected_ids.issubset(received):
            missing = sorted(expected_ids - received)
            raise RuntimeError(
                "MQTT publish completed but the running SMIOT app did not save every event to MongoDB. "
                f"Received {len(received)}/{len(expected_ids)}; first missing IDs: {missing[:10]}. "
                "Confirm the app subscriber and MongoDB connection are running."
            )

        lot_ids = sorted({row["lot_id"] for row in found})
        print(f"Verified {len(expected_ids)} daily events in MongoDB across {len(lot_ids)} demo lots.", flush=True)
        print(f"Open the app at /traceability and choose one of {LOT_PREFIX}001–{LOT_PREFIX}{args.lots:03d}.", flush=True)
        print(f"Image asset: /static/device_images/{IMAGE_FILE.name}", flush=True)
        return 0
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
