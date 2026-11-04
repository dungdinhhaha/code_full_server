"""Compare a raw Time Series read with a MongoDB aggregation/window query.

Read-only benchmark for a bounded time window. It reports the result size and
latency of both approaches and checks that per-node sample counts, means, and
humidity ranges agree. It is a workload-specific comparison, not a general
database performance claim.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]


def walk_execution_stats(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        stats = value.get("executionStats")
        if isinstance(stats, dict):
            found.append(stats)
        for child in value.values():
            found.extend(walk_execution_stats(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(walk_execution_stats(child))
    return found


def encodeable(doc: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(doc, default=lambda v: v.isoformat() if hasattr(v, "isoformat") else str(v)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--farm", default="greenhouse_a")
    parser.add_argument("--hours", type=float, default=1.0)
    parser.add_argument("--env-file")
    args = parser.parse_args()
    if args.hours <= 0 or args.hours > 24 * 30:
        parser.error("--hours must be >0 and <=720")

    load_dotenv(ROOT / ".env", override=False)
    if args.env_file:
        load_dotenv(args.env_file, override=False)
    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        parser.error("MONGODB_URI is required via environment or --env-file")

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=args.hours)
    match = {
        "meta.farm_key": args.farm,
        "meta.measurement_type": "node",
        "timestamp": {"$gte": start, "$lt": end},
        "meta.node_id": {"$type": "number"},
        "readings.soil_hum": {"$type": "number"},
    }
    projection = {
        "_id": 0,
        "meta.farm_key": 1,
        "meta.node_id": 1,
        "timestamp": 1,
        "readings.soil_hum": 1,
    }
    pipeline = [
        {"$match": match},
        {"$setWindowFields": {
            "partitionBy": "$meta.node_id",
            "sortBy": {"timestamp": 1},
            "output": {"previous_at": {"$shift": {"output": "$timestamp", "by": -1}}},
        }},
        {"$set": {"gap_seconds": {"$cond": [
            {"$ne": ["$previous_at", None]},
            {"$divide": [{"$subtract": ["$timestamp", "$previous_at"]}, 1000]},
            None,
        ]}}},
        {"$group": {
            "_id": "$meta.node_id",
            "samples": {"$sum": 1},
            "mean_soil_humidity_pct": {"$avg": "$readings.soil_hum"},
            "min_soil_humidity_pct": {"$min": "$readings.soil_hum"},
            "max_soil_humidity_pct": {"$max": "$readings.soil_hum"},
            "max_gap_seconds": {"$max": "$gap_seconds"},
        }},
        {"$sort": {"_id": 1}},
    ]

    client = MongoClient(uri, appname="smiot-mongo-timeseries-benchmark", serverSelectionTimeoutMS=10000)
    try:
        database = client[os.getenv("MONGODB_DATABASE", "smiot")]
        collection_name = os.getenv("MONGODB_TELEMETRY_COLLECTION", "telemetry")
        collection = database[collection_name]

        raw_started = time.perf_counter()
        raw = list(collection.find(match, projection).sort([("meta.node_id", 1), ("timestamp", 1)]))
        raw_latency_ms = (time.perf_counter() - raw_started) * 1000

        aggregate_started = time.perf_counter()
        aggregate = list(collection.aggregate(pipeline, allowDiskUse=True))
        aggregate_latency_ms = (time.perf_counter() - aggregate_started) * 1000

        raw_by_node: dict[str, list[tuple[datetime, float]]] = {}
        for item in raw:
            raw_by_node.setdefault(str(item["meta"]["node_id"]), []).append(
                (item["timestamp"], float(item["readings"]["soil_hum"]))
            )
        raw_summary = {}
        for node, points in raw_by_node.items():
            values = [v for _, v in points]
            gaps = [(points[i][0] - points[i - 1][0]).total_seconds() for i in range(1, len(points))]
            raw_summary[node] = {
                "samples": len(values),
                "mean_soil_humidity_pct": statistics.fmean(values),
                "min_soil_humidity_pct": min(values),
                "max_soil_humidity_pct": max(values),
                "max_gap_seconds": max(gaps) if gaps else None,
            }

        aggregate_summary = {
            str(int(row["_id"])): {
                "samples": int(row["samples"]),
                "mean_soil_humidity_pct": float(row["mean_soil_humidity_pct"]),
                "min_soil_humidity_pct": float(row["min_soil_humidity_pct"]),
                "max_soil_humidity_pct": float(row["max_soil_humidity_pct"]),
                "max_gap_seconds": float(row["max_gap_seconds"]) if row.get("max_gap_seconds") is not None else None,
            }
            for row in aggregate
        }
        exact_counts = {node: value["samples"] for node, value in raw_summary.items()} == {
            node: value["samples"] for node, value in aggregate_summary.items()
        }
        numeric_match = all(
            node in aggregate_summary
            and all(abs(raw_summary[node][key] - aggregate_summary[node][key]) <= 1e-8
                    for key in ("mean_soil_humidity_pct", "min_soil_humidity_pct", "max_soil_humidity_pct"))
            for node in raw_summary
        )
        raw_bytes = len(json.dumps([encodeable(x) for x in raw], separators=(",", ":")).encode("utf-8"))
        aggregate_bytes = len(json.dumps([encodeable(x) for x in aggregate], separators=(",", ":")).encode("utf-8"))

        explain_stats: dict[str, Any] = {"raw": None, "aggregation": None}
        try:
            raw_explain = database.command(
                "explain",
                {"find": collection_name, "filter": match, "projection": projection,
                 "sort": {"meta.node_id": 1, "timestamp": 1}},
                verbosity="executionStats",
            )
            raw_stats = walk_execution_stats(raw_explain)
            if raw_stats:
                explain_stats["raw"] = {k: raw_stats[0].get(k) for k in
                                         ("nReturned", "totalDocsExamined", "totalKeysExamined", "executionTimeMillis")}
        except Exception as exc:  # explain is optional; do not hide successful query comparison
            explain_stats["raw_error"] = type(exc).__name__
        try:
            aggregate_explain = database.command(
                "explain",
                {"aggregate": collection_name, "pipeline": pipeline, "cursor": {}, "allowDiskUse": True},
                verbosity="executionStats",
            )
            stats_rows = walk_execution_stats(aggregate_explain)
            if stats_rows:
                explain_stats["aggregation"] = {k: stats_rows[0].get(k) for k in
                                                 ("nReturned", "totalDocsExamined", "totalKeysExamined", "executionTimeMillis")}
        except Exception as exc:
            explain_stats["aggregation_error"] = type(exc).__name__

        print(json.dumps({
            "farm": args.farm,
            "window_utc": {"start": start.isoformat(), "end": end.isoformat()},
            "method": "read-only; raw cursor versus MongoDB aggregation with $setWindowFields",
            "raw": {"latency_ms": round(raw_latency_ms, 3), "documents_returned": len(raw), "estimated_json_bytes": raw_bytes,
                    "per_node": raw_summary},
            "aggregation": {"latency_ms": round(aggregate_latency_ms, 3), "documents_returned": len(aggregate),
                            "estimated_json_bytes": aggregate_bytes, "per_node": aggregate_summary},
            "checks": {"per_node_sample_counts_match": exact_counts, "humidity_statistics_match": numeric_match},
            "explain_execution_stats": explain_stats,
            "scope_note": "Single live workload/window; timings are not a universal or before-after optimization claim.",
        }, ensure_ascii=False, indent=2, default=lambda v: v.isoformat() if hasattr(v, "isoformat") else str(v)))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
