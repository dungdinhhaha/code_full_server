"""Report daily telemetry coverage and GDD eligibility from MongoDB.

The cadence is a declared operational assumption, not inferred ground truth.
Synthetic records are excluded unless --include-synthetic is explicit. Missing
calendar days are emitted as rows so a partial history cannot look complete.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]


def pipeline(farm: str, start: date, end: date, include_synthetic: bool) -> list[dict]:
    match = {
        "meta.farm_key": farm,
        "meta.measurement_type": "node",
        # v1 history incorrectly held greenhouse_a/node2 at 2.4 for all 30 days.
        # Preserve it in Mongo for audit but exclude it from operational reports.
        "source.demo_seed_version": {"$ne": "smiot-demo-history-v1"},
        "timestamp": {
            "$gte": datetime.combine(start, time.min, timezone.utc),
            "$lt": datetime.combine(end + timedelta(days=1), time.min, timezone.utc),
        },
        "readings.air_temp": {"$type": "number"},
        "meta.node_id": {"$type": "number"},
    }
    # Do not mistake migrated records with no source declaration for physical
    # measurements. Only a declared device source is treated as physical.
    if not include_synthetic:
        match["source.source"] = "device"
        match["source.synthetic"] = {"$ne": True}
    else:
        match["$or"] = [{"source.source": "device"}, {"source.synthetic": True}]
    return [
        {"$match": match},
        {"$setWindowFields": {
            "partitionBy": {"farm": "$meta.farm_key", "node": "$meta.node_id"},
            "sortBy": {"timestamp": 1},
            "output": {"previous_sample_at": {"$shift": {"output": "$timestamp", "by": -1}}},
        }},
        {"$set": {"sample_gap_seconds": {"$cond": [
            {"$ne": ["$previous_sample_at", None]},
            {"$divide": [{"$subtract": ["$timestamp", "$previous_sample_at"]}, 1000]},
            None,
        ]}}},
        {"$group": {
            "_id": {
                "farm": "$meta.farm_key",
                "node": "$meta.node_id",
                "day": {"$dateTrunc": {"date": "$timestamp", "unit": "day", "timezone": "UTC"}},
            },
            "samples": {"$sum": 1},
            "first_sample": {"$min": "$timestamp"},
            "last_sample": {"$max": "$timestamp"},
            "mean_air_temp_c": {"$avg": "$readings.air_temp"},
            "min_air_temp_c": {"$min": "$readings.air_temp"},
            "max_air_temp_c": {"$max": "$readings.air_temp"},
            "air_temp_stddev_c": {"$stdDevPop": "$readings.air_temp"},
            "mean_soil_humidity_pct": {"$avg": "$readings.soil_hum"},
            "min_soil_humidity_pct": {"$min": "$readings.soil_hum"},
            "max_soil_humidity_pct": {"$max": "$readings.soil_hum"},
            "soil_humidity_stddev_pct": {"$stdDevPop": "$readings.soil_hum"},
            "max_gap_seconds": {"$max": "$sample_gap_seconds"},
            "synthetic_samples": {"$sum": {"$cond": [{"$eq": ["$source.synthetic", True]}, 1, 0]}},
        }},
        {"$project": {
            "_id": 0, "farm": "$_id.farm", "node": "$_id.node", "day": "$_id.day",
            "samples": 1, "first_sample": 1, "last_sample": 1,
            "mean_air_temp_c": 1, "min_air_temp_c": 1, "max_air_temp_c": 1,
            "air_temp_stddev_c": 1,
            "mean_soil_humidity_pct": 1, "min_soil_humidity_pct": 1,
            "max_soil_humidity_pct": 1, "soil_humidity_stddev_pct": 1,
            "max_gap_seconds": 1, "synthetic_samples": 1,
        }},
        {"$setWindowFields": {
            "partitionBy": {"farm": "$farm", "node": "$node"},
            "sortBy": {"day": 1},
            "output": {
                "previous_day": {"$shift": {"output": "$day", "by": -1}},
                "previous_last_sample": {"$shift": {"output": "$last_sample", "by": -1}},
            },
        }},
        {"$sort": {"node": 1, "day": 1}},
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--farm", default="greenhouse_a")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--base-temp", type=float, default=10.0)
    parser.add_argument("--expected-interval-seconds", type=int, default=3600,
                        help="Declared cadence used only to score coverage; default 3600 is the observed hourly seed cadence.")
    parser.add_argument("--coverage-threshold", type=float, default=0.8)
    parser.add_argument("--max-gap-hours", type=float, default=3.0)
    parser.add_argument("--include-synthetic", action="store_true")
    parser.add_argument("--env-file")
    args = parser.parse_args()
    if args.end < args.start or args.expected_interval_seconds < 1 or not 0 < args.coverage_threshold <= 1:
        parser.error("end must be on/after start, interval positive, coverage threshold in (0, 1]")

    load_dotenv(ROOT / ".env", override=False)
    if args.env_file:
        load_dotenv(args.env_file, override=False)
    uri = os.getenv("MONGODB_URI")
    if not uri:
        parser.error("MONGODB_URI is required; set it in .env or --env-file")

    expected = max(1, round(86400 / args.expected_interval_seconds))
    client = MongoClient(uri, appname="smiot-telemetry-quality", serverSelectionTimeoutMS=10000)
    try:
        rows = list(client[os.getenv("MONGODB_DATABASE", "smiot")][os.getenv("MONGODB_TELEMETRY_COLLECTION", "telemetry")].aggregate(
            pipeline(args.farm, args.start, args.end, args.include_synthetic), allowDiskUse=True
        ))
    finally:
        client.close()

    by_node: dict[int, dict[date, dict]] = {}
    for row in rows:
        node = int(row["node"])
        day = row["day"].date()
        by_node.setdefault(node, {})[day] = row

    results = []
    for node in sorted(by_node or {1: {}, 2: {}}):
        indexed = by_node.get(node, {})
        cumulative = 0.0
        cumulative_valid = True
        previous_last = None
        day = args.start
        while day <= args.end:
            row = indexed.get(day)
            if row is None:
                cumulative_valid = False
                results.append({"day": day.isoformat(), "farm": args.farm, "node": node,
                                "status": "missing_data", "samples": 0, "expected_samples": expected,
                                "coverage_pct": 0.0, "daily_gdd_c": None, "gdd_cumulative_c": None,
                                "cumulative_status": "blocked_by_missing_day"})
                previous_last = None
                day += timedelta(days=1)
                continue
            count = int(row["samples"])
            coverage = min(1.0, count / expected)
            first = row["first_sample"]
            last = row["last_sample"]
            previous = row.get("previous_last_sample")
            gaps = [float(row["max_gap_seconds"])] if row.get("max_gap_seconds") is not None else []
            if first and previous:
                gaps.append(max(0.0, (first - previous).total_seconds()))
            if previous_last and first:
                gaps.append(max(0.0, (first - previous_last).total_seconds()))
            max_gap_seconds = max(gaps) if gaps else None
            gap_ok = max_gap_seconds is None or max_gap_seconds <= args.max_gap_hours * 3600
            complete = coverage >= args.coverage_threshold and gap_ok
            gdd = max(0.0, float(row["mean_air_temp_c"]) - args.base_temp) if complete else None
            if gdd is None:
                cumulative_valid = False
            elif cumulative_valid:
                cumulative += gdd
            results.append({
                "day": day.isoformat(), "farm": args.farm, "node": node,
                "status": "eligible" if complete else "incomplete_coverage_or_gap",
                "samples": count, "expected_samples": expected,
                "coverage_pct": round(coverage * 100, 2),
                "max_observed_boundary_gap_hours": round(max_gap_seconds / 3600, 3) if max_gap_seconds is not None else None,
                "mean_air_temp_c": round(float(row["mean_air_temp_c"]), 3),
                "air_temp_stddev_c": round(float(row["air_temp_stddev_c"] or 0), 3),
                "mean_soil_humidity_pct": round(float(row["mean_soil_humidity_pct"]), 3) if row.get("mean_soil_humidity_pct") is not None else None,
                "soil_humidity_stddev_pct": round(float(row["soil_humidity_stddev_pct"] or 0), 3),
                "soil_humidity_range_pct": [row.get("min_soil_humidity_pct"), row.get("max_soil_humidity_pct")],
                "daily_gdd_c": round(gdd, 3) if gdd is not None else None,
                "gdd_cumulative_c": round(cumulative, 3) if cumulative_valid else None,
                "cumulative_status": "complete_since_start" if cumulative_valid else "blocked_by_missing_or_incomplete_day",
                "synthetic_samples": int(row.get("synthetic_samples", 0)),
            })
            previous_last = last
            day += timedelta(days=1)

    report = {
        "farm": args.farm, "period": {"start": args.start.isoformat(), "end": args.end.isoformat()},
        "provenance_filter": "declared device plus explicitly synthetic; unclassified legacy records excluded" if args.include_synthetic else "declared physical source=device only; synthetic and unclassified legacy records excluded",
        "cadence_assumption_seconds": args.expected_interval_seconds,
        "coverage_threshold_pct": round(args.coverage_threshold * 100, 2),
        "max_gap_hours": args.max_gap_hours,
        "base_temp_c": args.base_temp,
        "note": "Coverage depends on the declared sensor cadence; no readings are interpolated. Missing/incomplete days block cumulative GDD.",
        "daily": results,
    }
    print(json.dumps(report, ensure_ascii=False, default=lambda v: v.isoformat() if isinstance(v, datetime) else v, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
