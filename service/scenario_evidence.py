"""Idempotent MongoDB evidence for explicitly acknowledged virtual-device scenarios.

Scenario labels live on this control/ACK path and are never copied into sensor telemetry.
Relationships to incidents and lots are recorded only when explicitly supplied and verified.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any

from pymongo.errors import DuplicateKeyError

SUPPORTED_STATES = {"started", "stopped", "rejected"}
from service.farm_registry import FARM_KEYS
VALID_FARMS = set(FARM_KEYS)
VALID_NODES = {1, 2}

# Only the simulator's explicit, applied scenario-start ACK opens an incident.
# This is a demo incident record, not a claim that a physical device failed.
SCENARIO_INCIDENT_KINDS = {
    "soil_flatline": "soil_humidity_flatline",
    "soil_spike": "soil_humidity_spike",
    "soil_out_of_range": "soil_humidity_out_of_range",
    "water_overrun": "water_overrun",
    "vent_stuck": "ventilation_stuck",
    "pipe_leak": "pipe_leak",
}
SCENARIO_GENERIC_KIND = "scenario_event"

# W1 live Datadog resources, verified 2026-11-10. A safety-trip event is
# correlated to an incident only through its exact simulator run/farm above;
# never infer incident identity from the aggregate metric.
PLC_SAFETY_MONITOR_ID = "342734303"
PLC_SAFETY_WORKFLOW_ID = "b9e72b04-1580-45f8-ae1e-628124a19065"


def _utc(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    return fallback


def _verified_incident_id(db, payload: dict[str, Any], ack_at: datetime) -> str | None:
    """Return explicit incident link only when scope and time overlap are corroborated."""
    raw_id = payload.get("incident_id")
    if not raw_id:
        run_id = str(payload.get("scenario_run_id") or "")
        if not run_id:
            return None
        run = db["scenario_runs"].find_one(
            {"_id": run_id, "farm_key": payload.get("farm_key")}, {"incident_id": 1}
        )
        raw_id = (run or {}).get("incident_id")
        if not raw_id:
            return None
    farm_key = payload.get("farm_key")
    node_id = payload.get("node_id")
    query: dict[str, Any] = {"_id": str(raw_id), "farm_key": farm_key}
    if node_id is not None:
        query["node_id"] = int(node_id)
    incident = db["operational_incidents"].find_one(query, {"opened_at": 1, "recovered_at": 1})
    if not incident:
        return None
    opened_at = incident.get("opened_at")
    recovered_at = incident.get("recovered_at")
    if not isinstance(opened_at, datetime):
        return None
    if opened_at.tzinfo is None:
        opened_at = opened_at.replace(tzinfo=timezone.utc)
    if ack_at < opened_at.astimezone(timezone.utc):
        return None
    if isinstance(recovered_at, datetime):
        if recovered_at.tzinfo is None:
            recovered_at = recovered_at.replace(tzinfo=timezone.utc)
        if ack_at > recovered_at.astimezone(timezone.utc):
            return None
    return str(raw_id)


def _open_scenario_incident(db, payload: dict[str, Any], ack_at: datetime,
                            lot_id: str | None) -> str | None:
    from service.scenario_catalog import resolve_scenario
    kind = SCENARIO_INCIDENT_KINDS.get(str(payload.get("scenario_type") or ""))
    scenario_spec = resolve_scenario(payload.get("scenario_code") or payload.get("scenario_type"))
    if kind is None and scenario_spec:
        kind = SCENARIO_GENERIC_KIND
    run_id = str(payload.get("scenario_run_id") or "")
    farm_key = str(payload.get("farm_key") or "")
    if not kind or not run_id or farm_key not in VALID_FARMS:
        return None
    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:16].upper()
    incident_id = f"INC-SMIOT-SCENARIO-{digest}"
    doc = {
        "_id": incident_id,
        "incident_id": incident_id,
        "kind": kind,
        "status": "open",
        "farm_key": farm_key,
        "node_id": payload.get("node_id"),
        "lot_id": lot_id,
        "scenario_run_id": run_id,
        "scenario": str(payload.get("scenario_type"))[:80],
        "scenario_code": (scenario_spec or {}).get("code") or payload.get("scenario_code"),
        "scenario_group": (scenario_spec or {}).get("group") or (scenario_spec or {}).get("domain"),
        "scenario_title": (scenario_spec or {}).get("title"),
        "scenario_response": (scenario_spec or {}).get("safe_response")
            or (scenario_spec or {}).get("response"),
        "opened_by": "applied_simulator_scenario",
        "opened_at": ack_at,
        "fault_started_at": ack_at,
        "detected_at": None,
        "recovered_at": None,
        "synthetic": True,
        "evidence": {"scenario_run_ids": [run_id], "action_command_ids": []},
        "impact": {"lot_scope_status": "verified_assignment" if lot_id else "unknown"},
        "timeline": [{"at": ack_at, "event": "scenario_started", "by": "simulator_ack"}],
        "updated_at": ack_at,
    }
    db["operational_incidents"].update_one(
        {"_id": incident_id}, {"$setOnInsert": doc}, upsert=True
    )
    return incident_id


def find_scenario_incident(db, scenario_run_id: str, farm_key: str) -> str | None:
    """Resolve an exact simulator run and farm to its persisted incident, if any."""
    run = db["scenario_runs"].find_one(
        {"_id": str(scenario_run_id), "farm_key": str(farm_key)}, {"incident_id": 1}
    )
    incident_id = (run or {}).get("incident_id")
    if not incident_id:
        return None
    incident = db["operational_incidents"].find_one(
        {"_id": str(incident_id), "farm_key": str(farm_key), "scenario_run_id": str(scenario_run_id)},
        {"_id": 1},
    )
    return str(incident_id) if incident else None


def record_virtual_safety_trip(payload: dict[str, Any], *, db=None) -> bool:
    """Persist an observed virtual-PLC trip, correlated only by run ID and farm."""
    if not isinstance(payload, dict) or payload.get("event") not in {
        "virtual_plc_safety_trip", "virtual_plc_water_limit_exceeded",
    }:
        return False
    run_id = str(payload.get("scenario_run_id") or "")
    farm_key = str(payload.get("farm_key") or "")
    command_id = str(payload.get("command_id") or "")
    if not run_id or not command_id or farm_key not in VALID_FARMS:
        return False
    if db is None:
        from service.mongodb_store import database
        db = database()
    incident_id = find_scenario_incident(db, run_id, farm_key)
    if not incident_id:
        return False
    fault_at = _utc(payload.get("timestamp"), datetime.now(timezone.utc))
    event_id = f"{incident_id}:trip:{command_id}"
    evidence = {
        "_id": event_id,
        "incident_id": incident_id,
        "message_id": command_id,
        "event_type": "virtual_plc_safety_trip",
        "summary": ({
            "PIPE_PRESSURE_FLOW_MISMATCH": "PLC ảo phát hiện sai lệch áp suất và lưu lượng",
            "PUMP_PRESSURE_ZERO": "PLC ảo dừng bơm khi áp suất bằng 0",
            "PUMP_FLOW_BELOW_MINIMUM": "PLC ảo dừng bơm khi lưu lượng thấp hơn giới hạn",
        }.get(payload.get("fault_code"), "PLC ảo dừng bơm khi vượt giới hạn thời gian hoặc thể tích")),
        "details": {key: payload.get(key) for key in (
            "fault_code", "reason", "pump_id", "pressure_bar", "flow_lpm",
            "run_seconds", "estimated_volume_l", "synthetic")},
        "received_at": fault_at,
        "synthetic": True,
    }
    result = db["incident_telemetry_evidence"].update_one(
        {"_id": event_id}, {"$setOnInsert": evidence}, upsert=True
    )
    if result.upserted_id is None:
        return False
    db["operational_incidents"].update_one(
        {"_id": incident_id, "status": {"$in": ["open", "holding", "recovering"]}},
        {"$set": {"fault_signal_at": fault_at, "fault_signal": evidence["details"], "updated_at": fault_at,
                   "monitor_id": PLC_SAFETY_MONITOR_ID, "workflow_id": PLC_SAFETY_WORKFLOW_ID},
         "$addToSet": {"evidence.monitor_ids": PLC_SAFETY_MONITOR_ID,
                       "timeline": {"at": fault_at, "event": "safety_trip_observed",
                                    "by": "virtual_plc", "command_id": command_id}}},
    )
    return True


def _verified_lot_id(db, payload: dict[str, Any], ack_at: datetime) -> str | None:
    """Keep a lot link only when an explicit assignment covers this ACK's scope/time."""
    raw_lot = payload.get("lot_id")
    farm_key, node_id = payload.get("farm_key"), payload.get("node_id")
    if not raw_lot or node_id is None:
        return None
    assignment = db["lot_sensor_assignments"].find_one({
        "farm_key": farm_key, "node_id": int(node_id), "lot_id": str(raw_lot),
        "valid_from": {"$lte": ack_at},
        "$or": [{"valid_to": None}, {"valid_to": {"$gte": ack_at}}, {"valid_to": {"$exists": False}}],
    }, {"_id": 1})
    return str(raw_lot)[:128] if assignment else None


def record_scenario_ack(payload: dict[str, Any], *, db=None, now: datetime | None = None) -> bool:
    """Persist one simulator ACK and update its run projection.

    Returns True when a new ACK event was inserted, False for an exact replay. This is
    deliberately not a Mongo transaction: the append-only event is the evidence source;
    ``scenario_runs`` is a rebuildable current-state projection.
    """
    if not isinstance(payload, dict) or payload.get("event") != "scenario_ack":
        raise ValueError("scenario_ack event is required")
    state = str(payload.get("status", ""))
    if state not in SUPPORTED_STATES:
        raise ValueError("unsupported scenario ACK state")
    run_id = str(payload.get("scenario_run_id", "")).strip()
    command_id = str(payload.get("command_id", "")).strip()
    scenario_type = str(payload.get("scenario_type", "")).strip()
    farm_key = str(payload.get("farm_key", "")).strip()
    if not run_id or len(run_id) > 128 or not command_id or len(command_id) > 200:
        raise ValueError("scenario_run_id and command_id are required")
    if not scenario_type or len(scenario_type) > 80 or farm_key not in VALID_FARMS:
        raise ValueError("invalid scenario type or farm scope")
    node_id = payload.get("node_id")
    if node_id is not None:
        try:
            node_id = int(node_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid node scope") from exc
        if node_id not in VALID_NODES:
            raise ValueError("invalid node scope")
    now = now or datetime.now(timezone.utc)
    now = _utc(now, datetime.now(timezone.utc))
    ack_at = _utc(payload.get("timestamp"), now)
    started_at = _utc(payload.get("started_at"), ack_at) if state == "started" else None
    ended_at = _utc(payload.get("ended_at"), ack_at) if state == "stopped" else None

    if db is None:
        from service.mongodb_store import database
        db = database()

    lot_id = _verified_lot_id(db, payload, ack_at)
    incident_id = _verified_incident_id(db, payload, ack_at)
    if state == "started" and payload.get("applied") is True:
        incident_id = _open_scenario_incident(db, payload, ack_at, lot_id) or incident_id
    event_id = f"{run_id}:{command_id}"
    event: dict[str, Any] = {
        "_id": event_id,
        "scenario_run_id": run_id,
        "command_id": command_id,
        "status": state,
        "scenario_type": scenario_type,
        "scenario_code": str(payload.get("scenario_code") or "")[:20] or None,
        "farm_key": farm_key,
        "node_id": node_id,
        "lot_id": lot_id,
        "incident_id": incident_id,
        "ack_at": ack_at,
        "applied": bool(payload.get("applied")),
        "reason": str(payload.get("reason", ""))[:200] or None,
        "source": str(payload.get("source", "smiot_demo_stream"))[:80],
        "synthetic": True,
    }
    events = db["scenario_run_events"]
    try:
        result = events.update_one({"_id": event_id}, {"$setOnInsert": event}, upsert=True)
    except DuplicateKeyError:
        return False
    inserted = result.upserted_id is not None
    if not inserted:
        return False

    run_doc: dict[str, Any] = {
        "_id": run_id,
        "scenario_run_id": run_id,
        "scenario_type": scenario_type,
        "scenario_code": str(payload.get("scenario_code") or "")[:20] or None,
        "farm_key": farm_key,
        "node_id": node_id,
        "lot_id": event["lot_id"],
        "incident_id": incident_id,
        "status": "unknown",
        "seed": payload.get("seed") if isinstance(payload.get("seed"), int) else None,
        "source": event["source"],
        "synthetic": True,
        "created_at": ack_at,
        "updated_at": ack_at,
    }
    runs = db["scenario_runs"]
    runs.update_one({"_id": run_id}, {"$setOnInsert": run_doc}, upsert=True)

    # Monotonic projection: a late duplicate start/rejection cannot undo a stopped run.
    base = {"_id": run_id}
    if state == "started":
        runs.update_one({**base, "status": {"$in": ["unknown", "rejected", "started"]}},
                        {"$set": {"status": "started", "started_at": started_at or ack_at,
                                  "updated_at": ack_at,
                                  "last_ack_at": ack_at, "incident_id": incident_id},
                         "$addToSet": {"event_ids": event_id}})
    elif state == "stopped":
        runs.update_one({**base, "status": {"$in": ["unknown", "started", "stopped"]}},
                        {"$set": {"status": "stopped", "ended_at": ended_at or ack_at,
                                  "updated_at": ack_at,
                                  "last_ack_at": ack_at, "incident_id": incident_id},
                         "$addToSet": {"event_ids": event_id}})
        if incident_id:
            db["operational_incidents"].update_one(
                {"_id": incident_id, "status": {"$in": ["open", "holding", "recovering"]}},
                {"$set": {"status": "recovering", "scenario_stopped_at": ended_at or ack_at,
                          "updated_at": ack_at},
                 "$addToSet": {"timeline": {"at": ended_at or ack_at,
                                               "event": "scenario_stopped", "by": "simulator_ack"}}},
            )
            # W2 on the Velxio sensor needs a matching profile ACK and several
            # new normal samples. The generic one-sample verifier must not
            # close it before the dedicated workflow has checked those facts.
            if not (farm_key == "greenhouse_j" and scenario_type == "soil_flatline"):
                _verify_post_scenario_telemetry(
                    db, incident_id=incident_id, run_id=run_id, farm_key=farm_key,
                    node_id=node_id, stopped_at=ended_at or ack_at,
                )
    else:
        runs.update_one({**base, "status": {"$in": ["unknown", "rejected"]}},
                        {"$set": {"status": "rejected", "updated_at": ack_at, "last_ack_at": ack_at,
                                  "last_rejection_reason": event["reason"]},
                         "$addToSet": {"event_ids": event_id}})
    return True


def _verify_post_scenario_telemetry(db, *, incident_id: str, run_id: str,
                                    farm_key: str, node_id: int | None,
                                    stopped_at: datetime) -> bool:
    """Close a synthetic scenario only after a fresh post-stop sample exists.

    A simulator ACK alone is not recovery.  The verifier requires a telemetry
    sample received after the exact stop time and matching the farm/node scope.
    """
    query: dict[str, Any] = {
        "meta.farm_key": farm_key,
        "timestamp": {"$gt": stopped_at},
    }
    if node_id is not None:
        query["$or"] = [{"meta.node_id": node_id}, {"source.node_id": node_id}]
    try:
        samples = list(db.telemetry.find(query, {"timestamp": 1, "meta": 1, "source": 1, "_id": 0})
                        .sort("timestamp", -1).limit(3).max_time_ms(2500))
    except Exception:
        return False
    if not samples:
        return False
    verified_at = samples[0].get("timestamp") or datetime.now(timezone.utc)
    verification = {
        "verified": True,
        "method": "post_scenario_telemetry",
        "scenario_run_id": run_id,
        "farm_key": farm_key,
        "node_id": node_id,
        "sample_count": len(samples),
        "verified_at": verified_at,
        "synthetic": True,
    }
    result = db.operational_incidents.update_one(
        {"_id": incident_id, "farm_key": farm_key,
         "status": {"$in": ["open", "holding", "recovering"]}},
        {"$set": {"status": "recovered", "recovered_at": verified_at,
                   "recovery_verification": verification, "updated_at": verified_at},
         "$addToSet": {"timeline": {"at": verified_at,
                                      "event": "scenario_recovery_verified",
                                      "by": "post_stop_telemetry",
                                      "sample_count": len(samples)}}},
    )
    if result.modified_count:
        db.scenario_runs.update_one(
            {"_id": run_id, "farm_key": farm_key},
            {"$set": {"status": "recovered", "recovered_at": verified_at,
                      "recovery_verification": verification}},
        )
        return True
    return False


def record_scenario_observation(payload: dict[str, Any], *, db=None) -> bool:
    """Append an idempotent simulator observation linked to one acknowledged run.

    This stores control-plane evaluation evidence, not sensor telemetry. The
    observation can never close an incident or authorize real-device action.
    """
    if not isinstance(payload, dict) or payload.get("event") != "scenario_observation":
        return False
    run_id = str(payload.get("scenario_run_id") or "").strip()
    farm_key = str(payload.get("farm_key") or "").strip()
    code = str(payload.get("scenario_code") or "").strip().upper()
    if not run_id or len(run_id) > 128 or farm_key not in VALID_FARMS or not code:
        return False
    from service.scenario_catalog import resolve_scenario
    scenario = resolve_scenario(code)
    if not scenario:
        return False
    if db is None:
        from service.mongodb_store import database
        db = database()
    run = db["scenario_runs"].find_one({"_id": run_id, "farm_key": farm_key},
                                       {"scenario_code": 1, "scenario_type": 1,
                                        "incident_id": 1, "status": 1})
    if not run:
        return False
    if run.get("scenario_code") and run["scenario_code"] != code:
        return False
    observed_at = _utc(payload.get("observed_at"), datetime.now(timezone.utc))
    digest = hashlib.sha256(
        f"{run_id}|{code}|{observed_at.isoformat()}|{payload.get('node_id')}".encode("utf-8")
    ).hexdigest()[:32]
    incident_id = run.get("incident_id")
    observation = {
        "_id": f"OBS-{digest}",
        "scenario_run_id": run_id,
        "scenario_code": code,
        "scenario_type": str(payload.get("scenario_type") or run.get("scenario_type") or "")[:80],
        "scenario_title": scenario.get("title"),
        "domain": str(payload.get("domain") or scenario.get("group") or scenario.get("domain") or "")[:40],
        "farm_key": farm_key,
        "node_id": payload.get("node_id"),
        "incident_id": incident_id,
        "observed_at": observed_at,
        "status": str(payload.get("status") or "unknown")[:40],
        "response": str(payload.get("response") or "HOLD")[:80],
        "reason": str(payload.get("reason") or "")[:240] or None,
        "evidence": payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {},
        "finding": payload.get("finding") if isinstance(payload.get("finding"), dict) else None,
        "recovery_requirements": payload.get("recovery_requirements"),
        "synthetic": True,
        "execution_mode": "SIMULATED_ONLY",
        "real_hardware_action_allowed": False,
        "real_infrastructure_action_allowed": False,
    }
    result = db["scenario_observations"].update_one(
        {"_id": observation["_id"]}, {"$setOnInsert": observation}, upsert=True
    )
    inserted = result.upserted_id is not None
    if inserted:
        db["scenario_runs"].update_one(
            {"_id": run_id, "farm_key": farm_key},
            {"$set": {"last_observation_at": observed_at},
             "$addToSet": {"observation_ids": observation["_id"]}},
        )
        if incident_id:
            db["operational_incidents"].update_one(
                {"_id": incident_id, "scenario_run_id": run_id},
                {"$addToSet": {"timeline": {
                    "at": observed_at, "event": "scenario_observation",
                    "observation_id": observation["_id"], "status": observation["status"],
                    "by": "synthetic_domain_evaluator",
                }}},
            )
    return inserted


def record_virtual_safety_ack(payload: dict[str, Any], *, db=None) -> bool:
    """Persist a simulator-confirmed safe stop; this is not recovery or restart evidence."""
    if not isinstance(payload, dict) or payload.get("event") != "virtual_interlock_ack":
        return False
    if payload.get("applied") is not True or payload.get("verified") is not True:
        return False
    run_id = str(payload.get("scenario_run_id") or "")
    farm_key = str(payload.get("farm_key") or "")
    command_id = str(payload.get("command_id") or "")
    if not run_id or not command_id or farm_key not in VALID_FARMS:
        return False
    if db is None:
        from service.mongodb_store import database
        db = database()
    incident_id = find_scenario_incident(db, run_id, farm_key)
    if not incident_id:
        return False
    ack_at = _utc(payload.get("timestamp"), datetime.now(timezone.utc))
    event_id = f"{incident_id}:safe-stop:{command_id}"
    evidence = {
        "_id": event_id,
        "incident_id": incident_id,
        "message_id": command_id,
        "event_type": "virtual_safety_stop_verified",
        "summary": "PLC ảo xác nhận đã dừng bơm và đóng van",
        "details": {key: payload.get(key) for key in (
            "fault_code", "reason", "pump_id", "pressure_bar", "flow_lpm",
            "safe_mode_active", "outputs_off", "valve_closed", "synthetic")},
        "received_at": ack_at,
        "synthetic": True,
    }
    result = db["incident_telemetry_evidence"].update_one(
        {"_id": event_id}, {"$setOnInsert": evidence}, upsert=True
    )
    if result.upserted_id is None:
        return False
    incident = db["operational_incidents"].find_one({"_id": incident_id}, {"status": 1}) or {}
    if incident.get("status") in {"open", "holding", "recovering"}:
        db["operational_incidents"].update_one(
            {"_id": incident_id, "status": {"$in": ["open", "holding", "recovering"]}},
            {"$set": {"status": "holding", "safe_at": ack_at, "updated_at": ack_at,
                      "safe_stop_command_id": command_id,
                      "safety_verification": evidence["details"],
                      "monitor_id": PLC_SAFETY_MONITOR_ID,
                      "workflow_id": PLC_SAFETY_WORKFLOW_ID},
             "$addToSet": {"evidence.action_command_ids": command_id,
                           "evidence.monitor_ids": PLC_SAFETY_MONITOR_ID,
                           "timeline": {"at": ack_at, "event": "safe_stop_verified",
                                        "by": "virtual_plc_ack", "command_id": command_id}}},
        )
    return True
