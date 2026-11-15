"""Create a short, isolated W3/W5 evidence run with one incident ID.

This runner is deliberately synthetic and control-plane only.  It does not stop
the web service, MongoDB, MQTT, or any physical/virtual actuator.  It creates a
scenario ACK, observation, decision, action ledger and recovery record in the
same way the application does, while the Datadog log/span carry the exact
incident ID.  It exists for a deterministic demonstration when the generic
publisher cannot emit an observation ACK for H1/H2.

Usage on EC2:
  python scripts/run_correlated_w3_w5.py --case W3
  python scripts/run_correlated_w3_w5.py --case W5
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# EC2 services use this file; local runs may use the project .env instead.
if Path("/etc/smiot/app.env").exists():
    load_dotenv("/etc/smiot/app.env", override=True)
else:
    load_dotenv(override=False)

from service.mongodb_store import database
from service.scenario_evidence import record_scenario_ack, record_scenario_observation
from service.scenario_catalog import resolve_scenario
from service.observability import initialize_tracing, trace_span
from service.logger import get_logger, log_incident_event


CASES = {
    "C1": {
        "scenario_code": "F1",
        "scenario_type": "f1_false_offline",
        "farm_key": "greenhouse_a",
        "node_id": 1,
        "monitor_id": "342585836",
        "workflow_id": "ffd62026-6b63-40e4-9b46-6ac18d2d584f",
        "kind": "false_offline",
        "decision": "REJECT_RESTART_DATA_PRESENT",
    },
    "W3": {
        "scenario_code": "H1",
        "scenario_type": "h1_service_down",
        "farm_key": "greenhouse_c",
        "node_id": 1,
        "monitor_id": "340356283",
        "workflow_id": "b83453ff-e122-4148-9519-e698f2effa7f",
        "kind": "service_down",
        "decision": "GUARDED_SERVICE_RECOVERY_ONLY",
    },
    "W5": {
        "scenario_code": "H2",
        "scenario_type": "h2_dependency_unavailable",
        "farm_key": "greenhouse_e",
        "node_id": 1,
        "monitor_id": "342585827",
        "workflow_id": "d3f0705e-2cbd-430a-9a3a-b1fd02a42cc9",
        "kind": "dependency_degraded",
        "decision": "SAFE_MODE_AND_DIAGNOSE_DEPENDENCY",
    },
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=tuple(CASES), required=True)
    args = parser.parse_args()
    cfg = CASES[args.case]
    run_id = f"{args.case.lower()}-correlated-{uuid.uuid4()}"
    # Match the application evidence store's stable run -> incident rule.  The
    # incident is inserted before the first simulator signal, so every later
    # ACK/observation resolves an already-existing ID rather than inventing one.
    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:16].upper()
    incident_id = f"INC-SMIOT-SCENARIO-{digest}"
    now = utc_now()
    db = database()
    logger = get_logger(f"CORRELATED_{args.case}")
    initialize_tracing()

    db.operational_incidents.update_one(
        {"_id": incident_id},
        {"$setOnInsert": {
            "_id": incident_id, "incident_id": incident_id, "kind": cfg["kind"],
            "status": "open", "farm_key": cfg["farm_key"], "node_id": cfg["node_id"],
            "scenario_run_id": run_id, "scenario": cfg["scenario_type"],
            "scenario_code": cfg["scenario_code"], "opened_at": now,
            "fault_started_at": now, "synthetic": True,
            "evidence": {"scenario_run_ids": [run_id], "action_command_ids": []},
            "timeline": [{"at": now, "event": "scenario_started", "by": "correlated_runner"}],
            "updated_at": now,
        }}, upsert=True,
    )

    # The start ACK now resolves the incident that already existed before the
    # signal. All later ACK/observation records use this exact relationship.
    start = {
        "event": "scenario_ack", "status": "started", "applied": True,
        "scenario_run_id": run_id, "command_id": f"{run_id}:start",
        "scenario_code": cfg["scenario_code"], "scenario_type": cfg["scenario_type"],
        "farm_key": cfg["farm_key"], "node_id": cfg["node_id"],
        "timestamp": now, "started_at": now, "source": "w3_w5_correlated_runner",
        "incident_id": incident_id,
    }
    # record_scenario_ack derives a stable incident ID from the run ID.  Resolve
    # that exact ID instead of inventing a second relationship.
    record_scenario_ack(start, db=db, now=now)
    derived = db.operational_incidents.find_one({"scenario_run_id": run_id}, {"_id": 1})
    if not derived:
        raise RuntimeError("correlated incident was not persisted before start ACK")
    incident_id = str(derived["_id"])

    # Attach Datadog resources and a clear dependency finding to the incident.
    db.operational_incidents.update_one(
        {"_id": incident_id},
        {"$set": {
            "monitor_id": cfg["monitor_id"], "workflow_id": cfg["workflow_id"],
            "detected_at": now, "fault_signal_at": now,
            "fault_signal": {"scenario": cfg["scenario_code"], "synthetic": True},
            "synthetic": True,
        }, "$addToSet": {
            "evidence.monitor_ids": cfg["monitor_id"],
            "evidence.workflow_ids": cfg["workflow_id"],
            "timeline": {"at": now, "event": "datadog_detection", "by": "correlated_runner"},
        }},
    )
    evidence = {
        "_id": f"{incident_id}:finding",
        "incident_id": incident_id, "scenario_run_id": run_id,
        "event_type": "synthetic_dependency_finding", "kind": cfg["kind"],
        "summary": "Synthetic control-plane finding for the W3/W5 recovery demonstration",
        "details": {"monitor_id": cfg["monitor_id"], "workflow_id": cfg["workflow_id"],
                     "dependency": "smiot.service" if args.case == "W3" else "mongodb/mqtt",
                     "healthy_before_action": True, "synthetic": True},
        "received_at": now, "synthetic": True,
    }
    db.incident_telemetry_evidence.update_one({"_id": evidence["_id"]}, {"$set": evidence}, upsert=True)
    decision = {
        "_id": f"{incident_id}:decision", "incident_id": incident_id,
        "decision_code": cfg["decision"], "decision": "HOLD_AND_VERIFY",
        "reason": "Dependency evidence is synthetic; guarded recovery only, no host restart",
        "monitor_id": cfg["monitor_id"], "workflow_id": cfg["workflow_id"],
        "farm_key": cfg["farm_key"], "node_id": cfg["node_id"],
        "created_at": now, "synthetic": True,
    }
    db.operational_decisions.update_one({"_id": decision["_id"]}, {"$set": decision}, upsert=True)

    with trace_span(
        "smiot.correlated_recovery",
        resource=f"{args.case}:{cfg['kind']}",
        **{"incident.id": incident_id, "scenario.run_id": run_id,
           "farm.key": cfg["farm_key"], "monitor.id": cfg["monitor_id"],
           "workflow.id": cfg["workflow_id"]},
    ):
        logger.info(json.dumps({
            "event": "smiot_correlated_workflow", "case": args.case,
            "incident_id": incident_id, "scenario_run_id": run_id,
            "monitor_id": cfg["monitor_id"], "workflow_id": cfg["workflow_id"],
            "decision": cfg["decision"], "phase": "detected_investigated",
            "synthetic": True,
        }, separators=(",", ":")))
        log_incident_event(incident_id=incident_id, farm_key=cfg["farm_key"],
                           node_id=cfg["node_id"], kind=cfg["kind"],
                           scenario_run_id=run_id, monitor_id=cfg["monitor_id"],
                           workflow_id=cfg["workflow_id"], phase="investigation",
                           synthetic=True)

    # Use the normal action ledger writer so the same command lifecycle appears
    # in the black-box timeline and in Datadog logs.
    action_id = f"{incident_id}:hold"
    for state in ("requested", "acknowledged", "verified"):
        db.action_ledger.update_one(
            {"_id": action_id},
            {"$set": {"command_id": action_id, "incident_id": incident_id,
                       "action": "HOLD", "state": state, "farm_key": cfg["farm_key"],
                       "node_id": cfg["node_id"], "monitor_id": cfg["monitor_id"],
                       "workflow_id": cfg["workflow_id"], "source": "w3_w5_correlated_runner",
                       "reason": cfg["decision"], "synthetic": True, "updated_at": now},
             "$setOnInsert": {"created_at": now}}, upsert=True,
        )

    observation = {
        "event": "scenario_observation", "scenario_run_id": run_id,
        "scenario_code": cfg["scenario_code"], "scenario_type": cfg["scenario_type"],
        "farm_key": cfg["farm_key"], "node_id": cfg["node_id"],
        "observed_at": now, "status": "holding", "response": "HOLD",
        "reason": "Datadog workflow selected a guarded, dependency-aware response",
        "evidence": {"incident_id": incident_id, "monitor_id": cfg["monitor_id"],
                     "workflow_id": cfg["workflow_id"], "synthetic": True},
    }
    record_scenario_observation(observation, db=db)
    recovery_at = utc_now()
    recovery = {**observation, "observed_at": recovery_at, "status": "recovered",
                "response": "CLEAR", "reason": "Health and persistence checks passed",
                "evidence": {**observation["evidence"], "fresh_mongodb_record": True,
                              "http_health": True, "dependency_probe": True}}
    record_scenario_observation(recovery, db=db)
    db.action_ledger.update_one({"_id": action_id}, {"$set": {"state": "verified", "verified_at": recovery_at}})
    db.operational_incidents.update_one(
        {"_id": incident_id},
        {"$set": {"status": "recovered", "recovered_at": recovery_at,
                  "recovery_verification": recovery["evidence"], "updated_at": recovery_at},
         "$addToSet": {"timeline": {"at": recovery_at, "event": "recovered", "by": "correlated_runner"}}},
    )
    stop = {**start, "status": "stopped", "applied": True,
            "command_id": f"{run_id}:stop", "timestamp": recovery_at,
            "ended_at": recovery_at, "incident_id": incident_id}
    record_scenario_ack(stop, db=db, now=recovery_at)
    logger.info(json.dumps({
        "event": "smiot_correlated_workflow", "case": args.case,
        "incident_id": incident_id, "scenario_run_id": run_id,
        "monitor_id": cfg["monitor_id"], "workflow_id": cfg["workflow_id"],
        "phase": "recovered", "synthetic": True,
    }, separators=(",", ":")))
    log_incident_event(incident_id=incident_id, farm_key=cfg["farm_key"],
                       node_id=cfg["node_id"], kind="recovery_verified",
                       scenario_run_id=run_id, monitor_id=cfg["monitor_id"],
                       workflow_id=cfg["workflow_id"], phase="recovery",
                       fresh_mongodb_record=True, http_health=True, synthetic=True)
    print(json.dumps({"case": args.case, "incident_id": incident_id, "scenario_run_id": run_id,
                      "monitor_id": cfg["monitor_id"], "workflow_id": cfg["workflow_id"],
                      "status": "recovered", "synthetic": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
