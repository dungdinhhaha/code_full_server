"""Canonical incident context for the synthetic smart-farm safety scenario."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

from service.mongodb_store import collection

LOGGER = logging.getLogger("smiot.incident_lifecycle")
FARM_KEY = "greenhouse_a"
NODE_ID = 2
DEMO_LOT_ID = "melon-lot-local-demo-001"
# Current Datadog US1 resources verified from live workflow/monitor exports on
# 2026-11-10. Keep IDs in one place so new flatline incidents point at the
# current Ca 2 resources rather than the retired organization snapshot.
MONITOR_ID = "342585819"
WORKFLOW_ID = "2f9a3c1d-5292-4bc3-b4b9-cc03d4172724"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_demo_lot_assignment() -> dict[str, Any]:
    """Create the explicit, versioned demo mapping used to scope this incident to a lot."""
    now = utc_now()
    assignment = {
        "_id": f"{FARM_KEY}:node:{NODE_ID}:demo-v1",
        "farm_key": FARM_KEY,
        "node_id": NODE_ID,
        "zone_id": "greenhouse_a_zone_2",
        "lot_id": DEMO_LOT_ID,
        "valid_from": datetime(2026, 10, 1, tzinfo=timezone.utc),
        "valid_to": datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        "mapping_source": "explicit_demo_fixture",
        "synthetic": True,
        "updated_at": now,
    }
    collection("lot_sensor_assignments").update_one(
        {"_id": assignment["_id"]},
        {"$set": assignment, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return assignment


def start_flatline_incident(farm_key: str = FARM_KEY, node_id: int = NODE_ID) -> str:
    """Open or reuse the active flatline incident and return its canonical ID."""
    if farm_key != FARM_KEY or int(node_id) != NODE_ID:
        raise ValueError("this demo incident is scoped to greenhouse_a/node 2")
    now = utc_now()
    incidents = collection("operational_incidents")
    active = incidents.find_one(
        {"farm_key": farm_key, "node_id": int(node_id), "kind": "soil_humidity_flatline", "status": {"$in": ["open", "holding", "recovering"]}},
        sort=[("opened_at", -1)],
    )
    if active:
        _backfill_monitor_workflow(str(active["_id"]), MONITOR_ID, WORKFLOW_ID)
        return str(active["_id"])

    assignment = ensure_demo_lot_assignment()
    incident_id = f"INC-SMIOT-{now:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8].upper()}"
    incident = {
        "_id": incident_id,
        "incident_id": incident_id,
        "kind": "soil_humidity_flatline",
        "status": "open",
        "farm_key": farm_key,
        "node_id": int(node_id),
        "zone_id": assignment["zone_id"],
        "lot_id": assignment["lot_id"],
        "lot_mapping_id": assignment["_id"],
        "lot_mapping_source": assignment["mapping_source"],
        "opened_at": now,
        "detected_at": None,
        "recovered_at": None,
        "monitor_id": MONITOR_ID,
        "workflow_id": WORKFLOW_ID,
        "synthetic": True,
        "scenario": "Node 2 soil humidity freezes at 2.4%; fail safe before irrigation",
        "observed_fault": {"metric": "soil_humidity_pct", "value": 2.4},
        "impact": {
            "proposed_irrigation_decisions": 0,
            "blocked_irrigation_decisions": 0,
            "lot_scope_status": "explicit_demo_mapping",
        },
        "evidence": {"telemetry_message_ids": [], "trace_ids": [], "log_events": [], "workflow_execution_ids": [], "action_command_ids": []},
        "updated_at": now,
    }
    incidents.insert_one(incident)
    _attach_current_trace(incident_id)
    return incident_id


def get_active_incident(farm_key: str = FARM_KEY, node_id: int = NODE_ID) -> dict[str, Any] | None:
    return collection("operational_incidents").find_one(
        {"farm_key": farm_key, "node_id": int(node_id), "kind": "soil_humidity_flatline", "status": {"$in": ["open", "holding", "recovering"]}},
        sort=[("opened_at", -1)],
    )


def set_simulator_mode(mode: str, incident_id: str | None = None) -> None:
    """Persist the publisher's applied mode so a process restart preserves recovery state."""
    if mode not in {"normal", "flatline"}:
        raise ValueError("unsupported simulator mode")
    if not incident_id:
        active = get_active_incident()
        incident_id = str(active.get("incident_id")) if active else None
    if incident_id:
        collection("operational_incidents").update_one(
            {"_id": incident_id, "status": {"$in": ["open", "holding", "recovering"]}},
            {"$set": {"simulator_mode": mode, "mode_applied_at": utc_now(), "updated_at": utc_now(),
                      "status": "recovering" if mode == "normal" else "open"}},
        )


def record_fault_sample(incident_id: str, message_id: str | None, value: float, received_at: datetime | None = None) -> None:
    now = received_at or utc_now()
    if not message_id:
        message_id = f"{incident_id}:{now.isoformat()}"
    sample_id = str(message_id)[:220]
    sample_result = collection("incident_telemetry_evidence").update_one(
        {"_id": sample_id},
        {"$setOnInsert": {"incident_id": incident_id, "message_id": sample_id,
                           "value": float(value), "received_at": now, "synthetic": True}},
        upsert=True,
    )
    if sample_result.upserted_id is not None:
        collection("operational_incidents").update_one(
            {"_id": incident_id, "status": {"$in": ["open", "holding", "recovering"]}},
            {"$set": {"last_fault_sample_at": now, "last_fault_value": float(value), "updated_at": now},
             "$inc": {"fault_sample_count": 1},
             "$addToSet": {"evidence.telemetry_message_ids": sample_id}},
        )


def record_blocked_irrigation_decision(incident_id: str, soil_humidity_pct: float, message_id: str | None) -> bool:
    """Record one idempotent interlock decision; no pump command is sent by this function."""
    incident = collection("operational_incidents").find_one({"_id": incident_id})
    if not incident:
        return False
    stage_context = _irrigation_stage_context(incident, utc_now())
    band = stage_context.get("soil_humidity_band")
    observed = float(soil_humidity_pct)
    if band is None:
        proposed_action = "UNKNOWN"
        nominal_rule = "no_approved_field_calibrated_stage_envelope"
        decision_reason = "Không có dải độ ẩm theo giai đoạn đã được hiệu chuẩn; giữ HOLD và không suy đoán nhu cầu tưới."
    else:
        proposed_action = "IRRIGATE" if observed < float(band["min"]) else "NO_ACTION"
        nominal_rule = "soil_humidity_below_stage_envelope_min"
        decision_reason = (
            "Số đo thấp hơn ngưỡng tối thiểu của dải đã hiệu chuẩn; đề xuất tưới bị chặn do sự cố cảm biến."
            if proposed_action == "IRRIGATE" else
            "Số đo không thấp hơn ngưỡng tối thiểu của dải đã hiệu chuẩn; không đề xuất tưới."
        )
    decision_id = f"{incident_id}:irrigation-interlock"
    now = utc_now()
    decision = {
        "_id": decision_id,
        "decision_id": decision_id,
        "incident_id": incident_id,
        "farm_key": incident["farm_key"],
        "node_id": incident["node_id"],
        "lot_id": incident.get("lot_id"),
        "decision_type": "irrigation_safety_interlock",
        "sensor_value_pct": observed,
        "nominal_rule": nominal_rule,
        "proposed_action": proposed_action,
        "applied_action": "BLOCKED_HOLD",
        "reason": "sensor quality incident is open; irrigation command is not permitted. " + decision_reason,
        "stage_code": stage_context.get("stage_code"),
        "crop_key": stage_context.get("crop_key"),
        "envelope_version": stage_context.get("envelope_version"),
        "envelope_calibration_status": stage_context.get("calibration_status"),
        "envelope_source": stage_context.get("source"),
        "soil_humidity_band": band,
        "threshold_status": stage_context.get("status", "unknown"),
        "source_message_id": str(message_id)[:200] if message_id else None,
        "synthetic": True,
        "created_at": now,
    }
    result = collection("operational_decisions").update_one(
        {"_id": decision_id}, {"$setOnInsert": decision}, upsert=True
    )
    if result.upserted_id is not None:
        collection("operational_incidents").update_one(
            {"_id": incident_id},
            {"$inc": {"impact.proposed_irrigation_decisions": int(decision["proposed_action"] == "IRRIGATE"),
                       "impact.blocked_irrigation_decisions": int(decision["proposed_action"] == "IRRIGATE")},
             "$addToSet": {"evidence.action_command_ids": decision_id}, "$set": {"updated_at": now}},
        )
        return True
    return False


def _irrigation_stage_context(incident: dict[str, Any], effective_at: datetime) -> dict[str, Any]:
    """Resolve only an approved, field-calibrated envelope; otherwise return unknown."""
    result: dict[str, Any] = {"status": "unknown", "soil_humidity_band": None}
    farm_key, lot_id = incident.get("farm_key"), incident.get("lot_id")
    if not farm_key or not lot_id:
        result["status"] = "missing_lot_context"
        return result
    try:
        cycle = collection("crop_cycles").find_one(
            {"farm_key": farm_key, "lot_id": lot_id},
            {"crop_name": 1, "cultivar": 1, "current_stage": 1},
        )
        if not cycle:
            result["status"] = "crop_cycle_not_found"
            return result
        stage = cycle.get("current_stage")
        if not stage:
            event = collection("traceability_events").find_one(
                {"farm_key": farm_key, "lot_id": lot_id, "event_type": "crop_stage_recorded",
                 "captured_at": {"$lte": effective_at}},
                {"stage_code": 1, "stage": 1}, sort=[("captured_at", -1)],
            )
            stage = (event or {}).get("stage_code") or (event or {}).get("stage")
        if not stage:
            result["status"] = "stage_unknown"
            return result
        from service.stage_envelopes import canonical_crop_key, get_effective_stage_envelope
        crop_key = canonical_crop_key(cycle.get("crop_name"))
        envelope = get_effective_stage_envelope(
            crop=str(cycle.get("crop_name") or ""), stage=str(stage),
            effective_at=effective_at, cultivar=cycle.get("cultivar"),
        )
        result.update({"crop_key": crop_key, "stage_code": str(stage)})
        if not envelope:
            result["status"] = "no_approved_field_calibrated_envelope"
            return result
        bands = envelope.get("bands") or {}
        band = bands.get("soil_moisture_pct") or bands.get("soil_humidity_pct")
        if not isinstance(band, dict) or not isinstance(band.get("min"), (int, float)):
            result["status"] = "envelope_missing_soil_moisture_band"
            return result
        result.update({
            "soil_humidity_band": {"min": float(band["min"]), "max": float(band["max"])},
            "envelope_version": envelope.get("version"),
            "calibration_status": envelope.get("calibration_status"),
            "source": envelope.get("source"),
            "status": "field_calibrated_envelope_applied",
        })
        return result
    except Exception as exc:
        LOGGER.warning("could not resolve stage envelope for irrigation decision (%s)", type(exc).__name__)
        result["status"] = "envelope_lookup_failed"
        return result


def attach_monitor_and_workflow(incident_id: str, *, monitor_id: str, triggered_at: datetime | None = None,
                                workflow_id: str | None = None, execution_id: str | None = None) -> None:
    now = utc_now()
    set_fields: dict[str, Any] = {"monitor_id": str(monitor_id), "updated_at": now}
    # Gio phat hien chi duoc ghi mot lan: khong ghi de len moc da co (gan lien ket muon, backfill,
    # hay HOLD trung deu goi ham nay va khong duoc lam sai lech "phat hien luc").
    if triggered_at is not None:
        set_fields["detected_at"] = triggered_at
    else:
        existing = collection("operational_incidents").find_one({"_id": incident_id}, {"detected_at": 1}) or {}
        if not existing.get("detected_at"):
            set_fields["detected_at"] = now
    if workflow_id:
        set_fields["workflow_id"] = str(workflow_id)
    if execution_id:
        set_fields["last_workflow_execution_id"] = str(execution_id)
    add_fields: dict[str, Any] = {"evidence.monitor_ids": str(monitor_id)}
    if execution_id:
        add_fields["evidence.workflow_execution_ids"] = str(execution_id)
    collection("operational_incidents").update_one(
        {"_id": incident_id},
        {"$set": set_fields, "$addToSet": add_fields},
    )


def record_workflow_observation(incident_id: str, *, workflow_id: str, execution_id: str,
                                status: str, disposition: str, command_id: str | None = None) -> None:
    """Record a workflow's actual outcome, including a safe duplicate-action suppression."""
    if not incident_id or not execution_id:
        return
    now = utc_now()
    observation = {
        "workflow_id": str(workflow_id)[:100],
        "execution_id": str(execution_id)[:120],
        "status": str(status)[:40],
        "disposition": str(disposition)[:80],
        "command_id": str(command_id)[:120] if command_id else None,
        "observed_at": now,
        "synthetic": True,
    }
    collection("operational_incidents").update_one(
        {"_id": incident_id},
        {"$set": {"workflow_id": observation["workflow_id"],
                   "last_workflow_execution_id": observation["execution_id"],
                   "last_workflow_status": observation["status"],
                   "last_workflow_disposition": observation["disposition"],
                   "updated_at": now},
         "$addToSet": {"evidence.workflow_execution_ids": observation["execution_id"],
                       "evidence.workflow_observations": observation}},
    )


def record_incident_action(payload: dict[str, Any], state: str) -> None:
    incident_id = str(payload.get("incident_id") or "")
    if not incident_id:
        return
    now = utc_now()
    command_id = str(payload.get("command_id") or "")
    fields: dict[str, Any] = {"updated_at": now}
    if state == "acknowledged":
        action = payload.get("action")
        fields["status"] = "holding" if action in {"HOLD", "SAFE_STOP"} else "recovering"
        fields["last_action_acknowledged_at"] = now
        fields["last_action"] = action
        if action == "SAFE_STOP":
            fields["safe_at"] = now
            fields["safety_verification"] = payload.get("verification") or {
                "outputs_off": payload.get("outputs_off"),
                "valve_closed": payload.get("valve_closed"),
                "safe_mode_active": payload.get("safe_mode_active"),
                "synthetic": bool(payload.get("synthetic", True)),
            }
    if state == "verified" and payload.get("action") == "CLEAR":
        # Do not let a broker event alone close an incident. The exact
        # command must already exist as a verified CLEAR in the action ledger
        # (including its earlier ACK), and carry the complete app-verifier
        # evidence contract emitted by verify_and_clear_demo_safe_mode.py.
        verification = payload.get("verification")
        ledger_entry = collection("action_ledger").find_one(
            {"_id": command_id, "incident_id": incident_id, "action": "CLEAR", "state": "verified"},
            {"acknowledged_at": 1, "verification": 1, "target": 1},
        ) if command_id else None
        valid = isinstance(verification, dict) and bool(ledger_entry)
        if valid:
            value_range = verification.get("soil_humidity_range_pct")
            try:
                low, high = float(value_range[0]), float(value_range[1])
                sample_count = int(verification.get("sample_count", 0))
                freshness = float(verification.get("sample_freshness_seconds"))
            except (TypeError, ValueError, IndexError, KeyError):
                valid = False
            else:
                valid = (
                    ledger_entry.get("acknowledged_at") is not None
                    and ledger_entry.get("target") == "smiot_virtual_plc"
                    and ledger_entry.get("verification") == verification
                    and str(verification.get("incident_id") or "") == incident_id
                    and str(verification.get("monitor_state") or "").upper() == "OK"
                    and sample_count >= 10
                    and verification.get("virtual_pump_outputs_off") is True
                    and bool(verification.get("newest_sample_at"))
                    and 0 <= freshness <= 90
                    and low <= high
                    and high - low >= 0.5
                )
        if not valid:
            LOGGER.warning(
                "refusing incident recovery without complete verified CLEAR evidence incident_id=%s command_id=%s",
                incident_id, command_id or "missing",
            )
            return
        fields.update({"status": "recovered", "recovered_at": now, "recovery_verification": verification})
    update: dict[str, Any] = {"$set": fields}
    if command_id:
        update["$addToSet"] = {"evidence.action_command_ids": command_id}
    collection("operational_incidents").update_one({"_id": incident_id}, update)


def add_incident_trace_evidence(incident_id: str, *, trace_id: str | None = None, message_id: str | None = None) -> None:
    adds: dict[str, str] = {}
    if trace_id:
        adds["evidence.trace_ids"] = str(trace_id)[:100]
    if message_id:
        adds["evidence.telemetry_message_ids"] = str(message_id)[:200]
    if adds:
        collection("operational_incidents").update_one(
            {"_id": incident_id}, {"$addToSet": adds, "$set": {"updated_at": utc_now()}},
        )


def current_trace_id() -> str | None:
    """Trace id of the active Datadog span, or None when ddtrace is absent or no span is active."""
    try:
        from ddtrace import tracer  # noqa: WPS433 - optional dependency
        trace_id = tracer.current_trace_id()
    except Exception:
        return None
    return str(trace_id) if trace_id else None


def _attach_current_trace(incident_id: str) -> None:
    """Best effort: store the current trace id as incident evidence. Never raises."""
    try:
        trace_id = current_trace_id()
        if trace_id:
            add_incident_trace_evidence(incident_id, trace_id=trace_id)
    except Exception:
        LOGGER.warning("could not attach trace evidence to incident", exc_info=True)


def _backfill_monitor_workflow(incident_id: str, monitor_id: str | None, workflow_id: str | None) -> None:
    """Set monitor_id/workflow_id on a reused incident only where they are still missing. Never raises."""
    try:
        incidents = collection("operational_incidents")
        for field, value in (("monitor_id", monitor_id), ("workflow_id", workflow_id)):
            if value:
                incidents.update_one({"_id": incident_id, field: {"$exists": False}},
                                     {"$set": {field: str(value), "updated_at": utc_now()}})
    except Exception:
        LOGGER.warning("could not backfill monitor/workflow on incident", exc_info=True)


def add_incident_log_evidence(incident_id: str, message_id: str, event_name: str) -> None:
    """Store correlation keys for app log events without inventing Datadog log IDs."""
    collection("operational_incidents").update_one(
        {"_id": incident_id},
        {"$addToSet": {"evidence.log_events": {"event": str(event_name)[:80], "message_id": str(message_id)[:200]}},
         "$set": {"updated_at": utc_now()}},
    )


def incidents_for_lot(farm_key: str, lot_id: str, limit: int = 50) -> list[dict[str, Any]]:
    rows = collection("operational_incidents").find(
        {"farm_key": farm_key, "lot_id": lot_id}, {"_id": 0}
    ).sort("opened_at", -1).limit(max(1, min(int(limit), 200)))
    return list(rows)


# Mo/dong incident chung (false_offline, service_down). Khong dung cho flatline.
GENERIC_KINDS = ("false_offline", "service_down")
ACTIVE = ["open", "holding", "recovering"]


def open_incident(kind: str, farm_key: str, node_id: int | None, *, synthetic: bool = True,
                  opened_by: str = "app", details: dict[str, Any] | None = None,
                  detected_at: datetime | None = None, monitor_id: str | None = None,
                  workflow_id: str | None = None) -> str:
    """Mo (hoac dung lai) incident dang active cung kind/farm/node. Tra incident_id.

    monitor_id/workflow_id la tuy chon; chi ghi vao document khi co gia tri.
    """
    if kind not in GENERIC_KINDS:
        raise ValueError(f"kind khong ho tro: {kind}")
    incidents = collection("operational_incidents")
    q = {"kind": kind, "farm_key": farm_key, "node_id": node_id, "status": {"$in": ACTIVE}}
    active = incidents.find_one(q, sort=[("opened_at", -1)])
    if active:
        _backfill_monitor_workflow(str(active["_id"]), monitor_id, workflow_id)
        return str(active["_id"])
    now = utc_now()
    incident_id = f"INC-SMIOT-{now:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8].upper()}"
    doc: dict[str, Any] = {"_id": incident_id, "incident_id": incident_id, "kind": kind,
        "status": "open", "farm_key": farm_key, "node_id": node_id, "synthetic": bool(synthetic),
        "opened_by": opened_by, "opened_at": now, "detected_at": detected_at or now,
        "details": details or {}, "timeline": [{"at": now, "event": "opened", "by": opened_by}]}
    if monitor_id:
        doc["monitor_id"] = str(monitor_id)
    if workflow_id:
        doc["workflow_id"] = str(workflow_id)
    try:
        incidents.insert_one(doc)
    except DuplicateKeyError:
        # Unique partial index active_incident_by_scope_unique: another writer opened the same
        # scope between our find_one and insert. Reuse that incident instead of failing the caller.
        winner = incidents.find_one(q, sort=[("opened_at", -1)])
        if not winner:
            raise
        LOGGER.info("open_incident reused concurrently opened incident kind=%s farm=%s", kind, farm_key)
        _backfill_monitor_workflow(str(winner["_id"]), monitor_id, workflow_id)
        return str(winner["_id"])
    _attach_current_trace(incident_id)
    return incident_id


def close_flatline_incident(farm_key: str, node_id: int, *, incident_id: str,
                            recovery_evidence: dict[str, Any]) -> bool:
    """Close only the exact flatline incident linked by the verifier's CLEAR ACK."""
    if farm_key != FARM_KEY or int(node_id) != NODE_ID:
        raise ValueError("this demo incident is scoped to greenhouse_a/node 2")
    incident_id = str(incident_id or "").strip()
    if not incident_id or str((recovery_evidence or {}).get("incident_id") or "") != incident_id:
        return False
    active = collection("operational_incidents").find_one(
        {"_id": incident_id, "farm_key": farm_key, "node_id": int(node_id),
         "kind": "soil_humidity_flatline", "status": {"$in": ["open", "holding", "recovering"]}},
        {"_id": 1},
    )
    if not active:
        return False
    return close_incident(incident_id, recovery_evidence=recovery_evidence,
                          closed_by="auto_flatline_verifier")


def close_incident(incident_id: str, *, recovery_evidence: dict[str, Any], closed_by: str = "app") -> bool:
    """Chi dong khi co bang chung phuc hoi (vd. mau Mongo moi). Tra True neu da dong."""
    if not recovery_evidence:
        return False
    now = utc_now()
    r = collection("operational_incidents").update_one(
        {"_id": incident_id, "status": {"$in": ACTIVE}},
        {"$set": {"status": "recovered", "recovered_at": now, "recovery_verification": recovery_evidence,
                  "updated_at": now},
         "$push": {"timeline": {"at": now, "event": "recovered", "by": closed_by}}})
    return r.modified_count == 1
