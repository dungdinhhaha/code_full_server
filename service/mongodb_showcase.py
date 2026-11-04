"""MongoDB backed harvest-window story built from crop-cycle and telemetry evidence."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from time import perf_counter
from typing import Any

from service.mongodb_store import collection, database

BASE_TEMP_C = 10.0  # context indicator only; cultivar-specific agronomy is not configured
EXPECTED_SAMPLES_PER_DAY = 24  # seeded history cadence is hourly
MIN_COVERAGE = 0.80
MAX_GAP_SECONDS = 3 * 60 * 60


def harvest_pipeline(farm_key: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Aggregate raw sensor samples into daily coverage and heat context in MongoDB."""
    return [
        {"$match": {
            "meta.measurement_type": "node", "meta.farm_key": farm_key,
            "timestamp": {"$gte": start, "$lt": end},
            "readings.air_temp": {"$type": "number"}, "meta.node_id": {"$type": "number"},
            "source.demo_seed_version": "smiot-demo-history-v2",
        }},
        {"$setWindowFields": {
            "partitionBy": {"farm": "$meta.farm_key", "node": "$meta.node_id"},
            "sortBy": {"timestamp": 1},
            "output": {"previous_sample_at": {"$shift": {"output": "$timestamp", "by": -1}}},
        }},
        {"$set": {"sample_gap_seconds": {"$cond": [
            {"$ne": ["$previous_sample_at", None]},
            {"$divide": [{"$subtract": ["$timestamp", "$previous_sample_at"]}, 1000]}, None,
        ]}}},
        {"$group": {
            "_id": {"farm": "$meta.farm_key", "node": "$meta.node_id",
                    "day": {"$dateTrunc": {"date": "$timestamp", "unit": "day", "timezone": "UTC"}}},
            "samples": {"$sum": 1}, "first_sample": {"$min": "$timestamp"},
            "last_sample": {"$max": "$timestamp"}, "max_gap_seconds": {"$max": "$sample_gap_seconds"},
            "mean_air_temp_c": {"$avg": "$readings.air_temp"},
            "min_air_temp_c": {"$min": "$readings.air_temp"}, "max_air_temp_c": {"$max": "$readings.air_temp"},
            "synthetic_samples": {"$sum": {"$cond": [{"$eq": ["$source.synthetic", True]}, 1, 0]}},
        }},
        {"$setWindowFields": {
            "partitionBy": {"farm": "$_id.farm", "node": "$_id.node"},
            "sortBy": {"_id.day": 1},
            "output": {"previous_last_sample": {"$shift": {"output": "$last_sample", "by": -1}}},
        }},
        {"$set": {
            "boundary_gap_seconds": {"$cond": [
                {"$ne": ["$previous_last_sample", None]},
                {"$divide": [{"$subtract": ["$first_sample", "$previous_last_sample"]}, 1000]}, 0,
            ]},
            "coverage_pct": {"$min": [100, {"$multiply": [{"$divide": ["$samples", EXPECTED_SAMPLES_PER_DAY]}, 100]}]},
        }},
        {"$set": {
            "max_observed_gap_seconds": {"$max": ["$max_gap_seconds", "$boundary_gap_seconds"]},
            "day_complete": {"$and": [
                {"$gte": ["$coverage_pct", MIN_COVERAGE * 100]},
                {"$lte": [{"$max": ["$max_gap_seconds", "$boundary_gap_seconds"]}, MAX_GAP_SECONDS]},
            ]},
        }},
        {"$set": {
            "gdd_context": {"$cond": ["$day_complete", {"$max": [0, {"$subtract": ["$mean_air_temp_c", BASE_TEMP_C]}]}, None]},
            "eligible_mean_air_temp_c": {"$cond": ["$day_complete", "$mean_air_temp_c", None]},
        }},
        {"$setWindowFields": {
            "partitionBy": {"farm": "$_id.farm", "node": "$_id.node"},
            "sortBy": {"_id.day": 1},
            "output": {
                "cumulative_gdd_context": {"$sum": "$gdd_context", "window": {"documents": ["unbounded", "current"]}},
                "rolling_7d_mean_temp_c": {"$avg": "$eligible_mean_air_temp_c", "window": {"documents": [-6, "current"]}},
            },
        }},
        {"$project": {"_id": 0, "node_id": "$_id.node", "day": "$_id.day", "samples": 1,
                       "first_sample": 1, "last_sample": 1, "mean_air_temp_c": 1, "min_air_temp_c": 1,
                       "max_air_temp_c": 1, "coverage_pct": 1, "max_observed_gap_seconds": 1,
                       "day_complete": 1, "gdd_context": 1, "cumulative_gdd_context": 1,
                       "rolling_7d_mean_temp_c": 1, "synthetic_samples": 1}},
        {"$sort": {"node_id": 1, "day": 1}},
    ]


def list_harvest_lots(farm_key: str = "greenhouse_a") -> list[dict[str, Any]]:
    return list(collection("crop_cycles").find({"farm_key": farm_key}, {"_id": 0, "lot_id": 1, "crop_name": 1, "fruit_set_at": 1}).sort("fruit_set_at", -1))


def load_harvest_story(farm_key: str = "greenhouse_a", lot_id: str | None = None) -> dict[str, Any]:
    """Load one explicitly seeded crop-cycle and its MongoDB telemetry evidence."""
    cycle_query = {"farm_key": farm_key}
    if lot_id:
        cycle_query["lot_id"] = lot_id
    else:
        cycle_query["demo_scenario"] = "harvest_window_v1"
    cycle = collection("crop_cycles").find_one(cycle_query, {"_id": 0})
    if not cycle:
        return {"farm_key": farm_key, "crop_cycle": None, "days": [], "nodes": [], "raw_count": 0,
                "note": "Chưa có mốc ra hoa/thụ phấn được ghi cho nhà kính này; chưa thể tính cửa sổ thu hoạch."}

    pollinated_at = cycle["fruit_set_at"]
    if pollinated_at.tzinfo is None:
        pollinated_at = pollinated_at.replace(tzinfo=timezone.utc)
    today = datetime.now(timezone.utc).date()
    pollination_day = pollinated_at.astimezone(timezone.utc).date()
    start = datetime.combine(pollination_day, time.min, timezone.utc)
    end = datetime.combine(today, time.min, timezone.utc)  # only closed UTC days for coverage
    telemetry = collection("telemetry")
    query = {"meta.measurement_type": "node", "meta.farm_key": farm_key,
             "timestamp": {"$gte": start, "$lt": end}, "readings.air_temp": {"$type": "number"},
             "meta.node_id": {"$type": "number"}, "source.demo_seed_version": "smiot-demo-history-v2"}
    count_started = perf_counter()
    raw_count = telemetry.count_documents(query)
    count_ms = (perf_counter() - count_started) * 1000
    aggregate_started = perf_counter()
    daily = list(telemetry.aggregate(harvest_pipeline(farm_key, start, end), allowDiskUse=True))
    aggregate_ms = (perf_counter() - aggregate_started) * 1000

    by_node: dict[int, dict[date, dict[str, Any]]] = {}
    for row in daily:
        by_node.setdefault(int(row["node_id"]), {})[row["day"].date()] = row
    elapsed_days = max(0, (today - pollination_day).days)
    dates = [pollination_day + timedelta(days=offset) for offset in range(elapsed_days)]
    nodes: list[dict[str, Any]] = []
    heat_by_node: list[dict[str, Any]] = []
    chart_days: list[dict[str, Any]] = []
    for node_id, indexed in sorted(by_node.items()):
        complete_count = sum(bool(row.get("day_complete")) for row in indexed.values())
        heat_by_node.append({"node_id": node_id,
                             "gdd": round(sum(float(row.get("gdd_context") or 0) for row in indexed.values()), 1)})
        node_rows = []
        for day in dates:
            row = indexed.get(day)
            item = {"date": day, "day_number": (day - pollination_day).days + 1,
                    "node_id": node_id, "complete": bool(row and row.get("day_complete")),
                    "samples": int(row.get("samples", 0)) if row else 0,
                    "coverage_pct": round(float(row.get("coverage_pct", 0)), 1) if row else 0,
                    "mean_air_temp_c": round(float(row["mean_air_temp_c"]), 2) if row else None,
                    "rolling_7d_mean_temp_c": round(float(row["rolling_7d_mean_temp_c"]), 2) if row and row.get("rolling_7d_mean_temp_c") is not None else None,
                    "gdd_context": round(float(row["gdd_context"]), 2) if row and row.get("gdd_context") is not None else None,
                    "cumulative_gdd_context": round(float(row["cumulative_gdd_context"]), 2) if row and row.get("cumulative_gdd_context") is not None else None}
            node_rows.append(item)
            if row:
                chart_days.append(item)
        nodes.append({"node_id": node_id, "complete_days": complete_count, "expected_days": elapsed_days,
                      "missing_days": [row["date"].isoformat() for row in node_rows if not row["complete"]],
                      "coverage_pct": round((complete_count / elapsed_days) * 100, 1) if elapsed_days else 0,
                      "daily": node_rows})

    early = pollination_day + timedelta(days=int(cycle["harvest_days_min"]))
    late = pollination_day + timedelta(days=int(cycle["harvest_days_max"]))
    days_to_early = (early - today).days
    days_to_late = (late - today).days
    latest_query = {"meta.measurement_type": "node", "meta.farm_key": farm_key,
                    "readings.air_temp": {"$type": "number"}, "meta.node_id": {"$type": "number"},
                    "source.demo_seed_version": {"$exists": False}}
    latest = telemetry.find_one(latest_query, {"_id": 0, "timestamp": 1, "meta.node_id": 1, "readings.air_temp": 1}, sort=[("timestamp", -1)])
    latest_at = latest["timestamp"] if latest else None
    if latest_at and latest_at.tzinfo is None:
        latest_at = latest_at.replace(tzinfo=timezone.utc)
    freshness_minutes = round((datetime.now(timezone.utc) - latest_at.astimezone(timezone.utc)).total_seconds() / 60, 1) if latest_at else None

    return {
        "farm_key": farm_key, "crop_cycle": cycle, "pollination_day": pollination_day,
        "harvest_early": early, "harvest_late": late, "days_since_pollination": elapsed_days,
        "reference_day": pollination_day + timedelta(days=int(cycle.get("reference_day", 39))),
        "days_to_early": days_to_early, "days_to_late": days_to_late,
        "raw_count": raw_count, "daily_count": len(daily), "raw_count_ms": round(count_ms, 2),
        "aggregation_ms": round(aggregate_ms, 2), "nodes": nodes, "chart_days": chart_days,
        "heat_by_node": heat_by_node,
        "latest_freshness_minutes": freshness_minutes,
        "complete_node_days": sum(node["complete_days"] for node in nodes),
        "possible_node_days": sum(node["expected_days"] for node in nodes),
        "coverage_pct": round(sum(node["complete_days"] for node in nodes) / max(1, sum(node["expected_days"] for node in nodes)) * 100, 1),
        "pipeline": [
            {"stage": "$match", "purpose": "Chọn đúng nhà kính, node, mốc thụ phấn và dữ liệu nhiệt độ."},
            {"stage": "$setWindowFields + $group", "purpose": "Tính khoảng cách bản tin rồi gom mẫu theo ngày trong MongoDB."},
            {"stage": "$set", "purpose": "Chấm độ phủ ngày; chỉ ngày đủ mẫu và không có khoảng trống dài mới tính nhiệt tích lũy."},
            {"stage": "$setWindowFields", "purpose": "Tạo GDD ngữ cảnh lũy kế và nhiệt độ trung bình trượt 7 ngày theo node."},
        ],
        "note": "Các ngày 33, 36, 39, 42, 45 là mốc lấy mẫu của nghiên cứu giống dưa lưới Khang Nguyên (Galia), không phải khoảng thu hoạch áp dụng cho mọi giống. Giống của lô diễn tập chưa được xác nhận; lịch này chỉ nhắc kiểm tra quả, không dự báo ngày hái đã hiệu chuẩn. Tích nhiệt chỉ dùng chuỗi lịch sử gieo theo giờ v2; độ tươi bản tin được xem riêng từ luồng mô phỏng live, không trộn hai nhịp lấy mẫu.",
    }
