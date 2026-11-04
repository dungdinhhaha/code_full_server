"""Canonical incident context for the synthetic smart-farm safety scenario."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from service.mongodb_store import collection

FARM_KEY = "greenhouse_a"
NODE_ID = 2
DEMO_LOT_ID = "melon-lot-local-demo-001"
MONITOR_ID = "339977691"
WORKFLOW_ID = "18d1b008-fb24-4713-aa0b-a1432d84ea80"


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
        "sensor_value_pct": float(soil_humidity_pct),
        "nominal_rule": "soil_humidity_below_30_pct_would_request_irrigation",
        "proposed_action": "IRRIGATE" if float(soil_humidity_pct) < 30 else "NO_ACTION",
        "applied_action": "BLOCKED_HOLD",
        "reason": "sensor quality incident is open; irrigation command is not permitted",
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
                       "impact.blocked_irrigation_decisions": 1},
             "$addToSet": {"evidence.action_command_ids": decision_id}, "$set": {"updated_at": now}},
        )
        return True
    return False


def attach_monitor_and_workflow(incident_id: str, *, monitor_id: str, triggered_at: datetime | None = None,
                                workflow_id: str | None = None, execution_id: str | None = None) -> None:
    now = utc_now()
    set_fields: dict[str, Any] = {"monitor_id": str(monitor_id), "detected_at": triggered_at or now, "updated_at": now}
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
        fields["status"] = "holding" if payload.get("action") == "HOLD" else "recovering"
        fields["last_action_acknowledged_at"] = now
        fields["last_action"] = payload.get("action")
    if state == "verified" and payload.get("action") == "CLEAR":
        fields.update({"status": "recovered", "recovered_at": now, "recovery_verification": payload.get("verification")})
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
