"""Hop den su co (incident black box) tren MongoDB Community 8.0 (self-managed).

Mot aggregation duy nhat bat dau tu ``operational_incidents`` va ``$unionWith`` lan luot:
``incident_telemetry_evidence`` -> ``operational_decisions`` -> ``findings`` -> ``action_ledger`` ->
``scenario_run_events`` (chi khi incident co scenario_run_id ro rang) -> ``telemetry``
(Time Series, loc theo meta.farm_key/meta.node_id + cua so thoi gian, dung ``$setWindowFields``
de danh dau khoang mat mau). Moi nhanh ``$project`` ve dang chuan:

    {ts, kind, source_collection, summary, refs: {log, trace, monitor, workflow, message_id}}

Chi dung tinh nang co tren MongoDB Community 8.0: $unionWith, $setWindowFields ($shift),
partial index, $jsonSchema validator. Khong dung Atlas Search / Vector Search / Triggers.

Phan dung pipeline va tinh moc do la ham thuan (khong can Mongo) de unit test.
Ket noi Mongo chi duoc mo trong ``build_incident_timeline`` / ``list_incidents``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from service.operational_evidence import LEDGER_ACTIONS

INCIDENT_KINDS = (
    "soil_humidity_flatline", "false_offline", "service_down",
    "soil_humidity_spike", "soil_humidity_out_of_range", "water_overrun",
    "ventilation_stuck", "pipe_leak", "scenario_event",
)
ACTIVE_STATUSES = ["open", "holding", "recovering"]
ALL_STATUSES = ["open", "holding", "recovering", "recovered", "closed"]
# Gia tri thuc te da thay trong operational_incidents (do bang scripts/mongo_audit_readonly.py) nhung
# khong thuoc UI/INCIDENT_KINDS. Chi dung cho $jsonSchema canh bao, khong anh huong luong nghiep.
VALIDATOR_EXTRA_KINDS = (
    "actuator_command_unacknowledged", "actuator_no_ack", "ai_provider_failure",
    "dependency_degraded", "detector_heartbeat_missing", "plc_safety_trip",
)
VALIDATOR_EXTRA_STATUSES = ("observed",)
UNKNOWN = "chưa xác định"

DEFAULT_PRE_MINUTES = 15
DEFAULT_POST_MINUTES = 15
DEFAULT_SAMPLE_INTERVAL_SECONDS = 30
GAP_FACTOR = 3  # khoang cach > 3 x chu ky gui mau => danh dau "thieu mau"
MAX_TELEMETRY_SAMPLES = 2000
EXCLUDED_SEED_VERSION = "smiot-demo-history-v1"  # cung bo loc voi auth._history

# ---------------------------------------------------------------------------
# Index + validator (dung chung cho auth.init_db va scripts/explain_before_after.py)
# ---------------------------------------------------------------------------
# Moi muc: (collection, keys, options). Cac index trung voi index da co trong auth.init_db
# duoc liet ke lai voi ten mac dinh de create_index la no-op neu da ton tai.
INCIDENT_INDEX_SPECS: list[tuple[str, list[tuple[str, int]], dict[str, Any]]] = [
    # Partial index: chi index su co dang mo (open/holding/recovering) -> tim su co active theo pham vi.
    ("operational_incidents",
     [("kind", 1), ("farm_key", 1), ("node_id", 1), ("opened_at", -1)],
     {"name": "active_incident_by_scope", "partialFilterExpression": {"status": {"$in": ACTIVE_STATUSES}},
      "_fallback_drop": ["partialFilterExpression"]}),
    ("operational_incidents", [("opened_at", -1)], {"name": "incidents_by_opened_at"}),
    ("incident_telemetry_evidence", [("incident_id", 1), ("received_at", 1)], {"name": "evidence_by_incident_ts"}),
    ("operational_decisions", [("incident_id", 1), ("created_at", -1)], {}),
    ("action_ledger", [("incident_id", 1), ("created_at", -1)], {}),
    ("scenario_runs", [("incident_id", 1), ("status", 1), ("created_at", -1)],
     {"name": "scenario_runs_by_incident"}),
    ("scenario_run_events", [("incident_id", 1), ("scenario_run_id", 1), ("ack_at", 1)],
     {"name": "scenario_events_by_incident_run_ts"}),
    ("scenario_observations", [("incident_id", 1), ("scenario_run_id", 1), ("observed_at", 1)],
     {"name": "scenario_observations_by_incident_run_ts"}),
    ("lot_sensor_assignments", [("farm_key", 1), ("node_id", 1), ("valid_from", -1)], {}),
    # Time Series: index tren meta + timeField la hop le. Index nay da co trong init_db.
    ("telemetry",
     [("meta.farm_key", 1), ("meta.measurement_type", 1), ("meta.node_id", 1), ("timestamp", -1)], {}),
    # Time Series: secondary index tren truong measurement (source.incident_id). Partial filter tren
    # measurement field co the bi tu choi tuy phien ban -> fallback khong partial (xem ensure_incident_indexes).
    ("telemetry",
     [("source.incident_id", 1), ("timestamp", 1)],
     {"name": "telemetry_by_incident_ts",
      "partialFilterExpression": {"source.incident_id": {"$exists": True}},
      "_fallback_drop": ["partialFilterExpression"]}),
]

# Chi them index (additive), khong xoa gi. Tach rieng khoi INCIDENT_INDEX_SPECS de scripts/explain_before_after.py
# (co the xoa index trong danh sach do) khong bao gio dong vao cac index nay.
# Unique chi ap dung cho kind do open_incident() tao (false_offline, service_down). KHONG ap cho
# soil_humidity_flatline/scenario_*: service/scenario_evidence.py tao moi ho so theo scenario_run_id
# (upsert), nhieu run cung kind/farm/node co the dang hoat dong song song hop le.
UNIQUE_ACTIVE_KINDS = ["false_offline", "service_down"]
SCENARIO_API_IDEMPOTENCY_TTL_SECONDS = 7 * 24 * 3600
SCENARIO_API_RATE_LIMIT_TTL_SECONDS = 24 * 3600  # cua so gioi han 60 giay; giu 1 ngay la du
HARDENING_INDEX_SPECS: list[tuple[str, list[tuple[str, int]], dict[str, Any]]] = [
    ("operational_incidents",
     [("kind", 1), ("farm_key", 1), ("node_id", 1)],
     {"name": "active_incident_by_scope_unique", "unique": True,
      "partialFilterExpression": {"status": {"$in": ACTIVE_STATUSES}, "kind": {"$in": UNIQUE_ACTIVE_KINDS}}}),
    ("findings", [("incident_id", 1), ("detected_at", 1)], {"name": "findings_by_incident_detected"}),
    ("action_ledger", [("farm_key", 1), ("updated_at", -1)], {"name": "action_ledger_by_farm_updated"}),
    ("schedule_logs", [("schedule_id", 1), ("start_at", 1)], {"name": "schedule_logs_by_schedule_start"}),
    # TTL chi cho collection ky thuat. notifications/schedules/schedule_logs/telemetry/operational_incidents/
    # action_ledger KHONG co TTL: cho chu he thong chot thoi gian luu giu.
    ("scenario_api_idempotency", [("created_at", 1)],
     {"name": "scenario_api_idempotency_ttl_created_at",
      "expireAfterSeconds": SCENARIO_API_IDEMPOTENCY_TTL_SECONDS}),
    ("scenario_api_rate_limits", [("updated_at", 1)],
     {"name": "scenario_api_rate_limits_ttl_updated_at",
      "expireAfterSeconds": SCENARIO_API_RATE_LIMIT_TTL_SECONDS}),
]

INCIDENT_VALIDATORS: dict[str, dict[str, Any]] = {
    "operational_incidents": {
        "$jsonSchema": {
            "bsonType": "object",
            # incident_id khong bat buoc: ~87% ho so workflow_only khong co truong nay.
            "required": ["kind", "status", "opened_at", "synthetic"],
            "properties": {
                "incident_id": {"bsonType": "string"},
                "kind": {"enum": list(INCIDENT_KINDS) + list(VALIDATOR_EXTRA_KINDS)},
                "status": {"enum": ALL_STATUSES + list(VALIDATOR_EXTRA_STATUSES)},
                "opened_at": {"bsonType": "date"},
                "detected_at": {"bsonType": ["date", "null"]},
                "safe_at": {"bsonType": ["date", "null"]},
                "recovered_at": {"bsonType": ["date", "null"]},
                "farm_key": {"bsonType": ["string", "null"]},
                # Du lieu thuc te co ca int, string va null.
                "node_id": {"bsonType": ["int", "long", "string", "null"]},
                "synthetic": {"bsonType": "bool"},
            },
        }
    },
    "action_ledger": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["command_id", "action", "state", "synthetic"],
            "properties": {
                "command_id": {"bsonType": "string"},
                "incident_id": {"bsonType": ["string", "null"]},
                "action": {"enum": list(LEDGER_ACTIONS)},
                "state": {"enum": ["requested", "published", "acknowledged", "failed", "verified"]},
                "farm_key": {"bsonType": ["string", "null"]},
                "node_id": {"bsonType": ["int", "long", "null"]},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
                "synthetic": {"bsonType": "bool"},
            },
        }
    },
    "notifications": {
        # Tai lieu thong bao khong dong nhat: _id int|string, created_at date|string (da biet, hoan doi kieu).
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["category", "severity", "message"],
            "properties": {
                "id": {"bsonType": ["int", "long", "string"]},
                "category": {"bsonType": "string"},
                "severity": {"bsonType": "string"},
                "message": {"bsonType": "string"},
                "text": {"bsonType": "string"},
                "source": {"bsonType": "string"},
                "read": {"bsonType": "bool"},
                "created_at": {"bsonType": ["date", "string"]},
                "farm_key": {"bsonType": ["string", "null"]},
                "incident_id": {"bsonType": ["string", "null"]},
                "synthetic": {"bsonType": "bool"},
            },
        }
    },
    "scenario_runs": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["scenario_run_id", "scenario_type", "farm_key", "status", "synthetic"],
            "properties": {
                "scenario_run_id": {"bsonType": "string"},
                "scenario_type": {"bsonType": "string"},
                "farm_key": {"bsonType": "string"},
                "node_id": {"bsonType": ["int", "long", "null"]},
                "lot_id": {"bsonType": ["string", "null"]},
                "incident_id": {"bsonType": ["string", "null"]},
                "status": {"enum": ["unknown", "started", "stopped", "rejected"]},
                "synthetic": {"bsonType": "bool"},
            },
        }
    },
    "scenario_observations": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["scenario_run_id", "scenario_code", "farm_key", "observed_at",
                         "status", "synthetic", "execution_mode"],
            "properties": {
                "scenario_run_id": {"bsonType": "string"},
                "scenario_code": {"bsonType": "string"},
                "farm_key": {"bsonType": "string"},
                "node_id": {"bsonType": ["int", "long", "null"]},
                "observed_at": {"bsonType": "date"},
                "status": {"bsonType": "string"},
                "synthetic": {"bsonType": "bool"},
                "execution_mode": {"enum": ["SIMULATED_ONLY"]},
            },
        }
    },
    "scenario_run_events": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["scenario_run_id", "command_id", "status", "scenario_type", "farm_key", "ack_at", "synthetic"],
            "properties": {
                "scenario_run_id": {"bsonType": "string"},
                "command_id": {"bsonType": "string"},
                "status": {"enum": ["started", "stopped", "rejected"]},
                "scenario_type": {"bsonType": "string"},
                "farm_key": {"bsonType": "string"},
                "node_id": {"bsonType": ["int", "long", "null"]},
                "lot_id": {"bsonType": ["string", "null"]},
                "incident_id": {"bsonType": ["string", "null"]},
                "ack_at": {"bsonType": "date"},
                "synthetic": {"bsonType": "bool"},
            },
        }
    },
}


def ensure_incident_indexes(db, logger=None) -> list[dict[str, Any]]:
    """Tao index cho hop den. Khong bao gio nem loi (init app khong duoc crash).

    Sau do tao them HARDENING_INDEX_SPECS (unique/TTL/index bo sung); ket qua chi ghi log,
    khong lam thay doi gia tri tra ve.
    """
    report = _create_index_specs(db, INCIDENT_INDEX_SPECS, logger)
    try:
        extra = _create_index_specs(db, HARDENING_INDEX_SPECS, logger)
        if logger:
            logger.info("hardening indexes: %s", [(r["index"], r["status"]) for r in extra])
    except Exception as exc:  # khong bao gio duoc lam hong init_db
        if logger:
            logger.warning("Bo qua hardening indexes: %s", exc)
    return report


def ensure_hardening_indexes(db, logger=None) -> list[dict[str, Any]]:
    """Chi tao HARDENING_INDEX_SPECS va tra ve bao cao day du (dung cho script thu cong)."""
    return _create_index_specs(db, HARDENING_INDEX_SPECS, logger)


def _create_index_specs(db, specs, logger=None) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for coll_name, keys, options in specs:
        opts = {k: v for k, v in options.items() if not k.startswith("_")}
        try:
            name = db[coll_name].create_index(keys, **opts)
            report.append({"collection": coll_name, "index": name, "status": "ok"})
        except Exception as exc:  # OperationFailure, quyen, Time Series khong ho tro...
            fallback = options.get("_fallback_drop")
            if fallback:
                reduced = {k: v for k, v in opts.items() if k not in fallback}
                try:
                    name = db[coll_name].create_index(keys, **reduced)
                    report.append({"collection": coll_name, "index": name, "status": "ok_fallback",
                                   "note": f"bo {fallback}: {exc}"[:300]})
                    continue
                except Exception as exc2:
                    exc = exc2
            report.append({"collection": coll_name, "index": opts.get("name") or str(keys),
                           "status": "skipped", "error": str(exc)[:300]})
            if logger:
                logger.warning("Bo qua index %s.%s: %s", coll_name, keys, exc)
    return report


def apply_incident_validators(db, logger=None, only: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """Gan $jsonSchema voi validationAction=warn, validationLevel=moderate (an toan: khong chan ghi).

    Can quyen collMod (vd. role dbAdmin) tren DB app; thieu quyen thi chi ghi canh bao.
    """
    report: list[dict[str, Any]] = []
    try:
        existing = set(db.list_collection_names())
    except Exception as exc:
        if logger:
            logger.warning("Khong liet ke duoc collection de gan validator: %s", exc)
        return [{"status": "skipped", "error": str(exc)[:300]}]
    wanted = set(only) if only is not None else None
    for coll_name, validator in INCIDENT_VALIDATORS.items():
        if wanted is not None and coll_name not in wanted:
            continue
        try:
            if coll_name in existing:
                db.command("collMod", coll_name, validator=validator,
                           validationLevel="moderate", validationAction="warn")
            else:
                db.create_collection(coll_name, validator=validator,
                                     validationLevel="moderate", validationAction="warn")
            report.append({"collection": coll_name, "status": "ok"})
        except Exception as exc:
            report.append({"collection": coll_name, "status": "skipped", "error": str(exc)[:300]})
            if logger:
                logger.warning("Bo qua validator %s: %s", coll_name, exc)
    return report


# ---------------------------------------------------------------------------
# Ham thuan: dung pipeline
# ---------------------------------------------------------------------------
def _lit(value: Any) -> dict[str, Any]:
    return {"$literal": value}


def _refs(*, log: Any = None, trace: Any = None, monitor: Any = None,
          workflow: Any = None, message_id: Any = None) -> dict[str, Any]:
    def v(x):
        return _lit(None) if x is None else x
    return {"log": v(log), "trace": v(trace), "monitor": v(monitor), "workflow": v(workflow),
            "message_id": v(message_id)}


def _str(expr: Any, default: str = "?") -> dict[str, Any]:
    return {"$toString": {"$ifNull": [expr, default]}}


def _incident_milestones_stages(incident_id: str) -> list[dict[str, Any]]:
    scope = [" · ", _str("$farm_key"), "/node ", _str("$node_id")]
    first_trace = {"$first": {"$ifNull": ["$evidence.trace_ids", []]}}
    workflow = {"$ifNull": ["$last_workflow_execution_id", "$workflow_id"]}

    def milestone(field: str, kind: str, text: str, **refs: Any) -> dict[str, Any]:
        return {"ts": f"${field}", "kind": kind, "source_collection": "operational_incidents",
                "summary": {"$concat": [text, " ", _str("$kind"), *scope]},
                "synthetic": {"$ifNull": ["$synthetic", None]},
                "refs": _refs(**refs)}

    return [
        {"$match": {"_id": incident_id}},
        {"$project": {"_id": 0, "events": [
            milestone("opened_at", "incident_opened", "Mở sự cố", monitor="$monitor_id", workflow=workflow),
            milestone("fault_started_at", "fault_started", "Bắt đầu lỗi"),
            milestone("detected_at", "detected", "Phát hiện (monitor)", monitor="$monitor_id", workflow=workflow,
                      trace=first_trace),
            milestone("safe_at", "safe_state", "Vào trạng thái an toàn", workflow=workflow),
            milestone("recovered_at", "recovered", "Phục hồi đã xác minh", monitor="$monitor_id", workflow=workflow),
        ]}},
        {"$unwind": "$events"},
        {"$replaceWith": "$events"},
        {"$match": {"ts": {"$type": "date"}}},
    ]


def _evidence_branch(incident_id: str) -> dict[str, Any]:
    return {"$unionWith": {"coll": "incident_telemetry_evidence", "pipeline": [
        {"$match": {"incident_id": incident_id}},
        {"$sort": {"received_at": 1}},
        {"$project": {"_id": 0, "ts": "$received_at",
                      "kind": {"$ifNull": ["$event_type", "fault_sample"]},
                      "source_collection": _lit("incident_telemetry_evidence"),
                      "summary": {"$ifNull": ["$summary", {"$concat": ["Mẫu lỗi ghi nhận, giá trị ", _str("$value")]}]},
                      "value": "$value", "details": "$details",
                      "synthetic": {"$ifNull": ["$synthetic", None]},
                      "refs": _refs(log="$message_id", message_id="$message_id")}},
    ]}}


def _decisions_branch(incident_id: str) -> dict[str, Any]:
    return {"$unionWith": {"coll": "operational_decisions", "pipeline": [
        {"$match": {"incident_id": incident_id}},
        {"$sort": {"created_at": 1}},
        {"$project": {"_id": 0, "ts": "$created_at", "kind": _lit("decision"),
                      "source_collection": _lit("operational_decisions"),
                      "summary": {"$concat": [_str("$decision_type"), ": đề xuất ", _str("$proposed_action"),
                                              " → áp dụng ", _str("$applied_action")]},
                      "value": "$sensor_value_pct", "synthetic": {"$ifNull": ["$synthetic", None]},
                      "refs": _refs(message_id="$source_message_id")}},
    ]}}


def _findings_branch(incident_id: str) -> dict[str, Any]:
    """Join scenario findings into the incident black box by persisted incident ID."""
    return {"$unionWith": {"coll": "findings", "pipeline": [
        {"$match": {"incident_id": incident_id}},
        {"$sort": {"detected_at": 1}},
        {"$project": {"_id": 0, "ts": {"$dateFromString": {"dateString": "$detected_at",
                                                                        "onError": None}},
                      "kind": _lit("telemetry_finding"),
                      "source_collection": _lit("findings"),
                      "summary": {"$concat": [_str("$code"), ": ", _str("$evidence.metric"),
                                              " = ", _str("$evidence.value")]},
                      "severity": 1, "confidence": 1, "evidence": 1,
                      "scenario_run_id": 1, "synthetic": 1,
                      "refs": _refs(message_id="$scenario_run_id")}},
        {"$match": {"ts": {"$type": "date"}}},
    ]}}


def _action_ledger_branch(incident_id: str) -> dict[str, Any]:
    states = ["requested", "published", "acknowledged", "verified", "failed"]
    return {"$unionWith": {"coll": "action_ledger", "pipeline": [
        {"$match": {"incident_id": incident_id}},
        {"$sort": {"created_at": 1}},
        {"$project": {"_id": 0, "action": 1, "command_id": 1, "monitor_id": 1, "synthetic": 1,
                      "workflow": {"$ifNull": ["$execution_id", "$workflow_id"]},
                      "transitions": [{"state": s, "at": f"${s}_at"} for s in states]}},
        {"$unwind": "$transitions"},
        {"$match": {"transitions.at": {"$type": "date"}}},
        {"$project": {"ts": "$transitions.at",
                      "kind": {"$concat": ["action_", {"$toLower": _str("$action")}, "_", "$transitions.state"]},
                      "source_collection": _lit("action_ledger"),
                      "summary": {"$concat": ["Lệnh ", _str("$action"), " → ", "$transitions.state"]},
                      "state": "$transitions.state", "action": "$action",
                      "synthetic": {"$ifNull": ["$synthetic", None]},
                      "refs": _refs(log="$command_id", monitor="$monitor_id", workflow="$workflow",
                                    message_id="$command_id")}},
    ]}}


def _scenario_events_branch(incident_id: str, scenario_run_id: str) -> dict[str, Any]:
    """Replay only the scenario explicitly attached to this incident document."""
    return {"$unionWith": {"coll": "scenario_run_events", "pipeline": [
        {"$match": {"incident_id": incident_id, "scenario_run_id": scenario_run_id}},
        {"$sort": {"ack_at": 1}},
        {"$project": {"_id": 0, "ts": "$ack_at",
                      "kind": {"$concat": ["scenario_", {"$toLower": "$status"}]},
                      "source_collection": _lit("scenario_run_events"),
                      "summary": {"$concat": ["Kịch bản ", _str("$scenario_type"), " → ", _str("$status")]},
                      "scenario_run_id": 1, "command_id": 1, "applied": 1,
                      "lot_id": 1, "farm_key": 1, "node_id": 1, "synthetic": 1,
                      "refs": _refs(message_id="$command_id")}},
    ]}}


def _scenario_observations_branch(incident_id: str, scenario_run_id: str) -> dict[str, Any]:
    """Replay control-plane evaluator evidence for this exact synthetic run."""
    return {"$unionWith": {"coll": "scenario_observations", "pipeline": [
        {"$match": {"incident_id": incident_id, "scenario_run_id": scenario_run_id}},
        {"$sort": {"observed_at": 1}},
        {"$project": {"_id": 0, "ts": "$observed_at",
                      "kind": {"$concat": ["scenario_observation_", {"$toLower": "$status"}]},
                      "source_collection": _lit("scenario_observations"),
                      "summary": {"$concat": ["Kịch bản ", _str("$scenario_code"), " — ",
                                                _str("$status"), " / ", _str("$response")]},
                      "scenario_run_id": 1, "scenario_code": 1, "status": 1,
                      "response": 1, "evidence": 1, "finding": 1,
                      "farm_key": 1, "node_id": 1, "synthetic": 1,
                      "execution_mode": 1, "refs": _refs(message_id="$_id")}},
    ]}}


def _telemetry_branch(farm_key: str, node_id: int | None, window_start: datetime, window_end: datetime,
                      sample_interval_seconds: int, max_samples: int) -> dict[str, Any]:
    match: dict[str, Any] = {
        "meta.farm_key": farm_key,
        "meta.measurement_type": "node",
        "timestamp": {"$gte": window_start, "$lte": window_end},
        "source.demo_seed_version": {"$ne": EXCLUDED_SEED_VERSION},
    }
    if node_id is not None:
        numeric_node = _numeric_node(node_id)
        if numeric_node is not None:
            match["meta.node_id"] = numeric_node
    gap_threshold = float(sample_interval_seconds * GAP_FACTOR)
    sample_event = {
        "ts": "$timestamp", "kind": _lit("telemetry_sample"), "source_collection": _lit("telemetry"),
        "summary": {"$concat": ["Mẫu node ", _str("$meta.node_id"), ": soil_hum=", _str("$readings.soil_hum"),
                                " · nguồn ", _str("$meta.source")]},
        "value": "$readings.soil_hum", "node_id": "$meta.node_id",
        "synthetic": {"$ifNull": ["$source.synthetic", None]},
        "incident_tagged": {"$ifNull": ["$source.incident_id", None]},
        "refs": _refs(message_id="$source.message_id"),
    }
    gap_event = {
        "ts": "$prev_ts", "kind": _lit("telemetry_gap"), "source_collection": _lit("telemetry"),
        "summary": {"$concat": ["THIẾU MẪU node ", _str("$meta.node_id"), ": ",
                                _str({"$round": ["$gap_seconds", 0]}), " s không có dữ liệu"]},
        "gap_start": "$prev_ts", "gap_end": "$timestamp", "gap_seconds": "$gap_seconds",
        "node_id": "$meta.node_id", "missing": _lit(True), "synthetic": _lit(None),
        "refs": _refs(),
    }
    return {"$unionWith": {"coll": "telemetry", "pipeline": [
        {"$match": match},
        {"$sort": {"timestamp": 1}},
        {"$limit": int(max_samples)},
        # Window function: lay timestamp mau truoc trong cung node; mau dau tien so voi dau cua so.
        {"$setWindowFields": {
            "partitionBy": "$meta.node_id",
            "sortBy": {"timestamp": 1},
            "output": {"prev_ts": {"$shift": {"output": "$timestamp", "by": -1, "default": window_start}}},
        }},
        {"$set": {"gap_seconds": {"$divide": [{"$subtract": ["$timestamp", "$prev_ts"]}, 1000]}}},
        {"$set": {"is_gap": {"$gt": ["$gap_seconds", gap_threshold]}}},
        {"$project": {"_id": 0, "events": {"$concatArrays": [
            {"$cond": ["$is_gap", [gap_event], []]},
            [sample_event],
        ]}}},
        {"$unwind": "$events"},
        {"$replaceWith": "$events"},
    ]}}


def build_timeline_pipeline(incident_id: str, *, farm_key: str | None = None, node_id: int | None = None,
                            window_start: datetime | None = None, window_end: datetime | None = None,
                            scenario_run_id: str | None = None,
                            sample_interval_seconds: int = DEFAULT_SAMPLE_INTERVAL_SECONDS,
                            max_telemetry_samples: int = MAX_TELEMETRY_SAMPLES) -> list[dict[str, Any]]:
    """Pipeline thuan cho ``operational_incidents.aggregate``.

    Nhanh telemetry chi duoc them khi biet farm_key va cua so thoi gian (Time Series khong co
    incident_id o meta nen loc theo meta.farm_key/meta.node_id + timestamp). Finding chi noi qua
    incident_id da duoc xac minh trong scenario run; khong suy dien farm/lo tu gia tri cam bien.
    """
    if not incident_id:
        raise ValueError("incident_id is required")
    pipeline = _incident_milestones_stages(incident_id)
    pipeline.append(_evidence_branch(incident_id))
    pipeline.append(_decisions_branch(incident_id))
    pipeline.append(_findings_branch(incident_id))
    pipeline.append(_action_ledger_branch(incident_id))
    if scenario_run_id:
        pipeline.append(_scenario_events_branch(incident_id, scenario_run_id))
        pipeline.append(_scenario_observations_branch(incident_id, scenario_run_id))
    if farm_key and window_start is not None and window_end is not None:
        pipeline.append(_telemetry_branch(farm_key, node_id, window_start, window_end,
                                          sample_interval_seconds, max_telemetry_samples))
    pipeline.append({"$sort": {"ts": 1, "source_collection": 1}})
    return pipeline


def hot_queries(incident: dict[str, Any], window_start: datetime | None = None,
                window_end: datetime | None = None) -> list[dict[str, Any]]:
    """Cac truy van find tuong duong voi $match cua tung nhanh (dung cho explain truoc/sau index)."""
    incident_id = str(incident.get("_id") or incident.get("incident_id"))
    queries = [
        {"label": "Sự cố active theo phạm vi", "collection": "operational_incidents",
         "filter": {"kind": incident.get("kind"), "farm_key": incident.get("farm_key"),
                    "node_id": incident.get("node_id"), "status": {"$in": ACTIVE_STATUSES}},
         "sort": [("opened_at", -1)]},
        {"label": "Bằng chứng mẫu lỗi", "collection": "incident_telemetry_evidence",
         "filter": {"incident_id": incident_id}, "sort": [("received_at", 1)]},
        {"label": "Quyết định vận hành", "collection": "operational_decisions",
         "filter": {"incident_id": incident_id}, "sort": [("created_at", 1)]},
        {"label": "Kịch bản thiết bị đã xác nhận", "collection": "scenario_run_events",
         "filter": {"incident_id": incident_id}, "sort": [("ack_at", 1)]},
        {"label": "Sổ lệnh (action_ledger)", "collection": "action_ledger",
         "filter": {"incident_id": incident_id}, "sort": [("created_at", 1)]},
        {"label": "Telemetry gắn incident_id", "collection": "telemetry",
         "filter": {"source.incident_id": incident_id}, "sort": [("timestamp", 1)]},
    ]
    if incident.get("farm_key") and window_start is not None and window_end is not None:
        tf: dict[str, Any] = {"meta.farm_key": incident["farm_key"], "meta.measurement_type": "node",
                              "timestamp": {"$gte": window_start, "$lte": window_end}}
        if incident.get("node_id") is not None:
            numeric_node = _numeric_node(incident["node_id"])
            if numeric_node is not None:
                tf["meta.node_id"] = numeric_node
        queries.append({"label": "Telemetry quanh sự cố", "collection": "telemetry", "filter": tf,
                        "sort": [("timestamp", 1)]})
    return queries


# ---------------------------------------------------------------------------
# Ham thuan: cua so, noi lo, moc do
# ---------------------------------------------------------------------------
def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _seconds(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None:
        return None
    return round((b - a).total_seconds(), 1)


def _numeric_node(value: Any) -> int | None:
    """Normalize numeric ids and labels such as ``node1`` from evidence imports."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        text = str(value).strip().lower()
        if text.startswith("node"):
            try:
                return int(text[4:])
            except ValueError:
                return None
        return None


def fault_start_of(incident: dict[str, Any], events: Iterable[dict[str, Any]] = ()) -> datetime | None:
    explicit = _utc(incident.get("fault_started_at"))
    if explicit:
        return explicit
    samples = sorted(_utc(e.get("ts")) for e in events if e.get("kind") == "fault_sample" and _utc(e.get("ts")))
    if samples:
        return min(samples[0], _utc(incident.get("opened_at")) or samples[0])
    return _utc(incident.get("opened_at"))


def compute_window(incident: dict[str, Any], now: datetime | None = None,
                   pre_minutes: int = DEFAULT_PRE_MINUTES, post_minutes: int = DEFAULT_POST_MINUTES
                   ) -> tuple[datetime | None, datetime | None]:
    now = _utc(now) or datetime.now(timezone.utc)
    start = fault_start_of(incident)
    if start is None:
        return None, None
    end_anchor = _utc(incident.get("recovered_at")) or now
    end = min(end_anchor + timedelta(minutes=post_minutes), now)
    return start - timedelta(minutes=pre_minutes), max(end, start)


def match_affected_lots(assignments: Iterable[dict[str, Any]], farm_key: str | None, node_id: Any,
                        start: datetime | None, end: datetime | None) -> list[dict[str, Any]]:
    """Chi noi lo khi farm, node VA khoang thoi gian deu khop; thieu bat ky yeu to nao -> []."""
    if not farm_key or node_id is None or start is None or end is None:
        return []
    node = _numeric_node(node_id)
    if node is None:
        return []
    out = []
    for a in assignments:
        if a.get("farm_key") != farm_key:
            continue
        try:
            if int(a.get("node_id")) != node:
                continue
        except (TypeError, ValueError):
            continue
        vf, vt = _utc(a.get("valid_from")), _utc(a.get("valid_to"))
        if vf is None or vf > end:
            continue
        if vt is not None and vt < start:
            continue
        out.append({"lot_id": a.get("lot_id"), "zone_id": a.get("zone_id"),
                    "assignment_id": str(a.get("_id")) if a.get("_id") is not None else None,
                    "mapping_source": a.get("mapping_source"), "synthetic": a.get("synthetic"),
                    "valid_from": vf, "valid_to": vt})
    return out


def affected_lots_filter(farm_key: str | None, node_id: Any, start: datetime | None,
                         end: datetime | None) -> dict[str, Any] | None:
    if not farm_key or node_id is None or start is None or end is None:
        return None
    numeric_node = _numeric_node(node_id)
    if numeric_node is None:
        return None
    return {"farm_key": farm_key, "node_id": numeric_node, "valid_from": {"$lte": end},
            "$or": [{"valid_to": None}, {"valid_to": {"$gte": start}}]}


def add_trailing_gap(events: list[dict[str, Any]], window_end: datetime | None, now: datetime,
                     sample_interval_seconds: int = DEFAULT_SAMPLE_INTERVAL_SECONDS,
                     window_start: datetime | None = None, telemetry_queried: bool = True) -> list[dict[str, Any]]:
    """Danh dau khoang thieu mau o cuoi cua so ($shift chi thay khoang giua hai mau)."""
    if not telemetry_queried or window_end is None:
        return events
    samples = [e for e in events if e.get("kind") == "telemetry_sample" and _utc(e.get("ts"))]
    last = max((_utc(e["ts"]) for e in samples), default=None) or window_start
    if last is None:
        return events
    end = min(window_end, now)
    gap = (end - last).total_seconds()
    if gap > sample_interval_seconds * GAP_FACTOR:
        events = events + [{
            "ts": last, "kind": "telemetry_gap", "source_collection": "telemetry",
            "summary": f"THIẾU MẪU: {round(gap)} s không có dữ liệu đến cuối cửa sổ",
            "gap_start": last, "gap_end": end, "gap_seconds": round(gap, 1), "missing": True,
            "synthetic": None, "refs": {"log": None, "trace": None, "monitor": None, "workflow": None,
                                        "message_id": None}}]
        events.sort(key=lambda e: _utc(e.get("ts")) or datetime.min.replace(tzinfo=timezone.utc))
    return events


def extract_recovery_evidence(incident: dict[str, Any], events: list[dict[str, Any]],
                              max_samples: int = 5) -> dict[str, Any]:
    clear_events = [e for e in events if str(e.get("kind", "")).startswith("action_clear_")]
    ack = next((e for e in clear_events if e.get("state") in {"acknowledged", "verified"}), None)
    clear_ts = _utc(ack["ts"]) if ack else _utc(incident.get("recovered_at"))
    samples_after: list[dict[str, Any]] = []
    if clear_ts is not None:
        fault_value = (incident.get("observed_fault") or {}).get("value")
        for e in events:
            if e.get("kind") != "telemetry_sample" or (_utc(e.get("ts")) or clear_ts) <= clear_ts:
                continue
            if incident.get("node_id") is not None and e.get("node_id") not in (None, incident.get("node_id")):
                continue
            samples_after.append({**e, "differs_from_fault": (e.get("value") != fault_value)
                                  if fault_value is not None else None})
            if len(samples_after) >= max_samples:
                break
    return {"clear_ts": clear_ts, "clear_events": clear_events, "samples_after_clear": samples_after,
            "verification": incident.get("recovery_verification")}


def _gap_in_incident(event: dict[str, Any], recovered: datetime | None) -> bool:
    """Khoang thieu mau chi tinh cho su co khi bat dau truoc luc phuc hoi.

    Cua so lay du lieu keo dai them sau phuc hoi de co mau "sau phuc hoi"; mot khoang thieu mau
    xay ra sau do (vi du ca khac) khong thuoc su co nay.
    """
    if recovered is None:
        return True
    start = _utc(event.get("gap_start")) or _utc(event.get("ts"))
    return start is None or start <= recovered


def compute_impact(incident: dict[str, Any], events: list[dict[str, Any]],
                   affected_lots: list[dict[str, Any]] | None, now: datetime | None = None) -> dict[str, Any]:
    """Moc do. Gia tri None nghia la "chua xac dinh" (khong doan)."""
    now = _utc(now) or datetime.now(timezone.utc)
    fault_start = fault_start_of(incident, events)
    detected = _utc(incident.get("detected_at"))
    safe = _utc(incident.get("safe_at"))
    if safe is None:
        hold = [e for e in events if e.get("kind") in {"action_hold_acknowledged", "action_hold_verified"}]
        safe = min((_utc(e["ts"]) for e in hold), default=None)
    recovered = _utc(incident.get("recovered_at"))
    if recovered is None:
        clr = [e for e in events if e.get("kind") == "action_clear_verified"]
        recovered = min((_utc(e["ts"]) for e in clr), default=None)

    kind = incident.get("kind")
    unreliable_seconds: float | None = None
    basis = None
    ongoing = False
    explicit_from, explicit_to = _utc(incident.get("unreliable_from")), _utc(incident.get("unreliable_to"))
    if explicit_from is not None:
        end = explicit_to or recovered or now
        ongoing = explicit_to is None and recovered is None
        unreliable_seconds, basis = _seconds(explicit_from, end), "mốc unreliable_from/to đã ghi"
    elif kind == "soil_humidity_flatline" and fault_start is not None:
        samples = [_utc(e["ts"]) for e in events if e.get("kind") == "fault_sample" and _utc(e.get("ts"))]
        end = recovered or (max(samples) if samples else None)
        ongoing = recovered is None
        if end is not None:
            unreliable_seconds, basis = _seconds(fault_start, end), "từ lúc bắt đầu đứng số đến phục hồi/mẫu lỗi cuối"
    elif kind == "service_down":
        gaps = [float(e.get("gap_seconds") or 0) for e in events
                if e.get("kind") == "telemetry_gap" and _gap_in_incident(e, recovered)]
        if gaps:
            unreliable_seconds, basis = round(sum(gaps), 1), "tổng khoảng thiếu mẫu trong Mongo"
    elif kind == "false_offline" and fault_start is not None and recovered is not None:
        unreliable_seconds = _seconds(fault_start, recovered)
        basis = "thời gian trạng thái online/offline không đáng tin (dữ liệu mẫu vẫn vào Mongo)"

    restarts = (incident.get("impact") or {}).get("unnecessary_restarts")
    return {
        "fault_started_at": fault_start,
        "detected_at": detected,
        "safe_at": safe,
        "recovered_at": recovered,
        "detect_seconds": _seconds(fault_start, detected),
        "safe_seconds": _seconds(fault_start, safe),
        "recovery_seconds": _seconds(fault_start, recovered),
        "unreliable_seconds": unreliable_seconds,
        "unreliable_hours": round(unreliable_seconds / 3600, 3) if unreliable_seconds is not None else None,
        "unreliable_basis": basis,
        "unreliable_ongoing": ongoing,
        "false_restart_count": int(restarts) if isinstance(restarts, (int, float)) else None,
        "lots_to_review": len(affected_lots) if affected_lots is not None else None,
        "missing_sample_gaps": sum(1 for e in events
                                   if e.get("kind") == "telemetry_gap" and _gap_in_incident(e, recovered)),
    }


# ---------------------------------------------------------------------------
# Truy cap Mongo
# ---------------------------------------------------------------------------
def _db(db=None):
    if db is not None:
        return db
    from service.mongodb_store import database
    return database()


def list_incidents(limit: int = 50, db=None) -> list[dict[str, Any]]:
    rows = _db(db)["operational_incidents"].find(
        {}, {"kind": 1, "status": 1, "farm_key": 1, "node_id": 1, "opened_at": 1, "detected_at": 1,
             "recovered_at": 1, "synthetic": 1, "scenario": 1, "bits_investigation_id": 1,
             "monitor_id": 1, "workflow_id": 1, "last_workflow_execution_id": 1, "recovery_verification": 1, "recovery_evidence": 1},
    ).sort("opened_at", -1).limit(max(1, min(int(limit), 500)))
    return [{**r, "incident_id": str(r.get("_id"))} for r in rows]


CASES = {
    1: {"kind": "false_offline", "title": "Ca 1: báo offline sai",
        "summary": "Mẫu vẫn vào MongoDB nhưng giao diện báo offline; phải từ chối restart.",
        "monitor_id": "342585836",
        "workflow_id": "ffd62026-6b63-40e4-9b46-6ac18d2d584f"},
    2: {"kind": "soil_humidity_flatline", "title": "Ca 2: node 2 đứng số đo",
        "summary": "Node 2 vẫn gửi mẫu nhưng độ ẩm kẹt ở 2,4%; HOLD đến khi xác minh phục hồi.",
        "monitor_id": "342585819", "workflow_id": "2f9a3c1d-5292-4bc3-b4b9-cc03d4172724"},
    3: {"kind": "service_down", "title": "Ca 3: smiot.service dừng",
        "summary": "App dừng khi MongoDB/MQTT khỏe; chỉ khởi động app sau kiểm tra an toàn.",
        "monitor_id": "342585838", "workflow_id": "373ed0c0-4509-4fcd-a067-f54f0becc00e"},
    4: {"kind": "soil_humidity_spike", "title": "W7 · Rủi ro độ ẩm đất",
        "summary": "Giữ tư vấn/HOLD khi độ ẩm tăng bất thường; không tự quyết định tưới.",
        "monitor_id": "343594187", "workflow_id": "bb86206c-6df8-4b1d-8016-175a2fc62e49"},
    5: {"kind": "soil_humidity_out_of_range", "title": "W8 · Rủi ro VPD/EC",
        "summary": "Giữ quyết định an toàn khi chỉ số canh tác vượt ngưỡng; cần người duyệt.",
        "monitor_id": "343594185", "workflow_id": "593a670c-d59c-4104-8658-df260245a21e"},
    6: {"kind": "dependency_degraded", "title": "W5 · MongoDB/MQTT suy giảm",
        "summary": "Phân biệt dependency lỗi, kiểm tra trước–sau rồi mới kết luận phục hồi.",
        "monitor_id": "342585827", "workflow_id": "d3f0705e-2cbd-430a-9a3a-b1fd02a42cc9"},
    7: {"kind": "detector_heartbeat_missing", "title": "W6 · Detector mất heartbeat",
        "summary": "Cô lập đúng farm, chờ heartbeat mới và không restart toàn hệ thống.",
        "monitor_id": "343029221", "workflow_id": "d8e1b3db-1a54-4b4f-9be3-bf7e270a86f3"},
    8: {"kind": "plc_safety_trip", "title": "W1 · PLC safety trip",
        "summary": "SAFE_STOP, đóng van và xác minh ACK/ledger trước khi cho chạy lại.",
        "monitor_id": "342734303", "workflow_id": "b9e72b04-1580-45f8-ae1e-628124a19065"},
    9: {"kind": "actuator_command_unacknowledged", "title": "W9 · Actuator không ACK",
        "summary": "Chờ ACK muộn đúng command/farm; không retry mù và giữ output OFF.",
        "monitor_id": "342734743", "workflow_id": "47e95b24-db40-4cd5-b667-5b90e170b667"},
    10: {"kind": "ai_provider_failure", "title": "W10 · AI provider lỗi",
        "summary": "Chuyển HOLD/fallback an toàn khi provider lỗi; không dùng quyết định AI chưa xác minh.",
        "monitor_id": "342585824", "workflow_id": "50b3dc85-dd20-4220-bda1-ec78d2a3d00f"},
}


def case_for_kind(kind: str | None) -> int | None:
    return next((number for number, case in CASES.items() if case["kind"] == kind), None)


def latest_by_case(rows: Iterable[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    latest: dict[int, dict[str, Any]] = {}
    for row in rows:
        number = case_for_kind(row.get("kind"))
        if number is not None and (number not in latest or
                                   (_utc(row.get("opened_at")) or datetime.min.replace(tzinfo=timezone.utc)) >
                                   (_utc(latest[number].get("opened_at")) or datetime.min.replace(tzinfo=timezone.utc))):
            latest[number] = row
    return latest


def build_incident_timeline(incident_id: str, *, pre_minutes: int = DEFAULT_PRE_MINUTES,
                            post_minutes: int = DEFAULT_POST_MINUTES,
                            sample_interval_seconds: int = DEFAULT_SAMPLE_INTERVAL_SECONDS,
                            now: datetime | None = None, db=None) -> dict[str, Any]:
    """Doc header su co (find_one, de biet cua so thoi gian) roi chay MOT aggregation $unionWith."""
    database = _db(db)
    now = _utc(now) or datetime.now(timezone.utc)
    incident = database["operational_incidents"].find_one({"_id": incident_id})
    if not incident:
        return {"found": False, "incident_id": incident_id, "events": [], "affected_lots": [],
                "affected_lots_status": UNKNOWN, "recovery_evidence": {}, "impact": {}}
    # Imported/demo records may use the human label ``node1`` while the
    # telemetry and assignment collections use the numeric node id.  Keep the
    # stored record untouched, but normalize the copy used by the timeline so
    # every page/query follows the same type and never raises ``int('node1')``.
    normalized_node = _numeric_node(incident.get("node_id"))
    if normalized_node is not None and incident.get("node_id") != normalized_node:
        incident = {**incident, "node_id": normalized_node}
    window_start, window_end = compute_window(incident, now, pre_minutes, post_minutes)
    pipeline = build_timeline_pipeline(
        incident_id, farm_key=incident.get("farm_key"), node_id=incident.get("node_id"),
        window_start=window_start, window_end=window_end,
        scenario_run_id=incident.get("scenario_run_id"),
        sample_interval_seconds=sample_interval_seconds)
    events = list(database["operational_incidents"].aggregate(pipeline, allowDiskUse=True))
    for e in events:
        e["ts"] = _utc(e.get("ts"))
        for k in ("gap_start", "gap_end"):
            if k in e:
                e[k] = _utc(e[k])
    telemetry_queried = bool(incident.get("farm_key") and window_start is not None)
    events = add_trailing_gap(events, window_end, now, sample_interval_seconds, window_start, telemetry_queried)

    lot_start = fault_start_of(incident, events)
    lot_end = _utc(incident.get("recovered_at")) or now
    flt = affected_lots_filter(incident.get("farm_key"), incident.get("node_id"), lot_start, lot_end)
    if flt is None:
        affected_lots, lots_status = [], UNKNOWN
    else:
        rows = list(database["lot_sensor_assignments"].find(flt))
        affected_lots = match_affected_lots(rows, incident.get("farm_key"), incident.get("node_id"), lot_start, lot_end)
        lots_status = "khớp lot_sensor_assignments" if affected_lots else UNKNOWN

    impact = compute_impact(incident, events, affected_lots if flt is not None else None, now)
    return {
        "found": True,
        "incident_id": incident_id,
        "incident": incident,
        "synthetic": bool(incident.get("synthetic", True)),
        "window_start": window_start,
        "window_end": window_end,
        "events": events,
        "affected_lots": affected_lots,
        "affected_lots_status": lots_status,
        "recovery_evidence": extract_recovery_evidence(incident, events),
        "impact": impact,
        "pipeline_stage_count": len(pipeline),
    }
