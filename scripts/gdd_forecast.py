"""Calculate daily and cumulative GDD from SMIOT MongoDB telemetry.

GDD is calculated independently from soil moisture. If no real planted date is
configured, the script uses a clearly labelled demo assumption (2026-05-31).

Examples:
  py -3.12 scripts/gdd_forecast.py --env-file C:\\path\\to\\atlas-credentials.env
  py -3.12 scripts/gdd_forecast.py --env-file C:\\path\\to\\atlas-credentials.env --publish-datadog --watch
"""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import sys
import time
from datetime import date, datetime, time as datetime_time, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = "smiot"
DEFAULT_COLLECTION = "telemetry"
DEFAULT_DEMO_PLANTED_AT = "2026-05-31"
METRIC_NAME = "smiot.crop.gdd_cumulative"


def load_environment(env_file: str | None) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    if env_file:
        load_dotenv(Path(env_file).expanduser(), override=False)


def resolve_start_date(cli_date: str | None) -> tuple[date, str]:
    configured = cli_date or os.getenv("GDD_PLANTED_AT")
    if configured:
        return date.fromisoformat(configured), "configured_planted_at"
    # This matches the first historical data date used in the existing demo
    # calculation. It is not a claim that planting happened on this date.
    return date.fromisoformat(DEFAULT_DEMO_PLANTED_AT), "demo_assumption"


def daily_gdd_pipeline(
    farm_key: str, start: date, base_temp: float, include_synthetic: bool = False
) -> list[dict[str, Any]]:
    start_utc = datetime.combine(start, datetime_time.min, tzinfo=timezone.utc)
    return [
        {
            "$match": {
                "meta.measurement_type": "node",
                "meta.farm_key": farm_key,
                "timestamp": {"$gte": start_utc},
                "readings.air_temp": {"$type": "number"},
                "meta.node_id": {"$type": "number"},
                **({} if include_synthetic else {"source.synthetic": {"$ne": True}}),
            }
        },
        {
            "$group": {
                "_id": {
                    "farm_key": "$meta.farm_key",
                    "node_id": "$meta.node_id",
                    "day": {"$dateTrunc": {"date": "$timestamp", "unit": "day", "timezone": "UTC"}},
                },
                "mean_air_temp_c": {"$avg": "$readings.air_temp"},
                "samples": {"$sum": 1},
            }
        },
        {
            "$project": {
                "_id": 0,
                "farm_key": "$_id.farm_key",
                "node_id": "$_id.node_id",
                "day": "$_id.day",
                "mean_air_temp_c": 1,
                "gdd": {"$max": [0, {"$subtract": ["$mean_air_temp_c", base_temp]}]},
                "samples": 1,
            }
        },
        {
            "$setWindowFields": {
                "partitionBy": {"farm_key": "$farm_key", "node_id": "$node_id"},
                "sortBy": {"day": 1},
                "output": {
                    "gdd_cumulative": {
                        "$sum": "$gdd",
                        "window": {"documents": ["unbounded", "current"]},
                    }
                },
            }
        },
        {"$sort": {"node_id": 1, "day": 1}},
    ]


def publish_latest_gdd(points: list[dict[str, Any]], farm_key: str, cohort: str) -> int:
    host = os.getenv("DD_AGENT_HOST", "127.0.0.1")
    port = int(os.getenv("DD_DOGSTATSD_PORT", "8125"))
    sent = 0
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for point in points:
            value = float(point["gdd_cumulative"])
            if not math.isfinite(value):
                continue
            node_id = point["node_id"]
            tags = f"farm:{farm_key},node:{node_id},basis:{point['start_date_basis']},cohort:{cohort}"
            packet = f"{METRIC_NAME}:{value}|g|#{tags}".encode("utf-8")
            sock.sendto(packet, (host, port))
            sent += 1
    return sent


def main() -> int:
    parser = argparse.ArgumentParser(description="Calculate SMIOT daily and cumulative GDD from MongoDB.")
    parser.add_argument("--env-file", help="Optional env file containing MONGODB_URI")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--farm", default="greenhouse_a")
    parser.add_argument("--planted-at", help="Real/configured planted date (YYYY-MM-DD); otherwise use GDD_PLANTED_AT")
    parser.add_argument("--base-temp", type=float, default=10.0, help="Crop base temperature in Celsius")
    parser.add_argument("--threshold", type=float, default=900.0, help="Illustrative GDD threshold")
    parser.add_argument("--include-synthetic", action="store_true", help="Explicitly include simulator/demo readings (not suitable for real crop reporting)")
    parser.add_argument("--cohort", default="historical_reference", help="Metric tag separating historical and live demo crop cohorts")
    parser.add_argument("--publish-datadog", action="store_true", help="Send latest cumulative GDD per node to local DogStatsD")
    parser.add_argument("--watch", action="store_true", help="Recalculate periodically; use with --publish-datadog")
    parser.add_argument("--interval", type=int, default=300, help="Watch interval in seconds (minimum 30)")
    args = parser.parse_args()

    if args.watch and not args.publish_datadog:
        parser.error("--watch requires --publish-datadog")
    if args.interval < 30:
        parser.error("--interval must be at least 30 seconds")

    load_environment(args.env_file)
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        print("ERROR: MONGODB_URI is missing. Put it in the project .env or pass --env-file.", file=sys.stderr)
        return 2
    try:
        from pymongo import MongoClient
        from pymongo.errors import PyMongoError
    except ImportError:
        print("ERROR: PyMongo is missing. Install the project dependencies with: py -3.12 -m pip install -r requirements.txt", file=sys.stderr)
        return 2

    planted_at, date_basis = resolve_start_date(args.planted_at)
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
    try:
        collection = client[args.database][args.collection]
        try:
            while True:
                pipeline = daily_gdd_pipeline(args.farm, planted_at, args.base_temp, include_synthetic=args.include_synthetic)
                points = list(collection.aggregate(pipeline, allowDiskUse=True))
                latest_by_node: dict[int, dict[str, Any]] = {}
                for point in points:
                    latest_by_node[int(point["node_id"])] = point
                latest = []
                for node_id in sorted(latest_by_node):
                    point = latest_by_node[node_id]
                    point["start_date"] = planted_at.isoformat()
                    point["start_date_basis"] = date_basis
                    point["threshold_gdd"] = args.threshold
                    point["estimated_threshold_reached"] = float(point["gdd_cumulative"]) >= args.threshold
                    latest.append(point)

                if not latest:
                    print(f"No numeric readings.air_temp found for farm={args.farm} from {planted_at.isoformat()}.", file=sys.stderr)
                else:
                    report = {
                        "farm_key": args.farm,
                        "base_temp_c": args.base_temp,
                        "threshold_gdd": args.threshold,
                        "start_date": planted_at.isoformat(),
                        "start_date_basis": date_basis,
                        "forecast_note": "Synthetic readings are excluded by default. A demo planting-date assumption is not verified crop history.",
                        "includes_synthetic_readings": bool(args.include_synthetic),
                        "node_results": latest,
                    }
                    print(json.dumps(report, ensure_ascii=False, default=lambda value: value.isoformat() if isinstance(value, datetime) else value, indent=2), flush=True)
                    if args.publish_datadog:
                        count = publish_latest_gdd(latest, args.farm, args.cohort)
                        print(f"Published {count} latest GDD gauge(s) as {METRIC_NAME} to DogStatsD {os.getenv('DD_AGENT_HOST', '127.0.0.1')}:{os.getenv('DD_DOGSTATSD_PORT', '8125')}.", flush=True)

                if not args.watch:
                    break
                time.sleep(args.interval)
        except PyMongoError as exc:
            print(f"MongoDB read failed: {exc}. Check Atlas network access, TLS connectivity, and read permissions.", file=sys.stderr)
            return 1
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
