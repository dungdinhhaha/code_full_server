"""Bounded W10 provider-failure drill with one Mongo/Datadog incident ID.

Synthetic only: no Gemini request and no actuator call. The script exercises the
same HOLD/fallback evidence contract used by the application and leaves a
recoverable incident record for the web black box.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import socket
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv("/etc/smiot/app.env")
load_dotenv()

# SSM executes scripts from a transient working directory; make the deployed
# application package importable without relying on the caller's cwd.
sys.path.insert(0, "/opt/smiot")

from service.mongodb_store import collection  # noqa: E402
from service.observability import initialize_tracing, trace_span  # noqa: E402

initialize_tracing()


def now() -> datetime:
    return datetime.now(timezone.utc)


def emit(metric: str, value: float, tags: list[str]) -> None:
    packet = f"{metric}:{value}|g|#{','.join(tags)}".encode()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(packet, (os.getenv("DD_AGENT_HOST", "127.0.0.1"), int(os.getenv("DD_DOGSTATSD_PORT", "8125"))))


def main() -> int:
    incident_id = f"INC-SMIOT-W10-{now():%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8].upper()}"
    run_id = str(uuid.uuid4())
    farm = "greenhouse_h"
    monitor_id = "342585824"
    workflow_id = "50b3dc85-dd20-4220-bda1-ec78d2a3d00f"
    incidents = collection("operational_incidents")
    decisions = collection("operational_decisions")
    started = now()
    incidents.insert_one({
        "_id": incident_id, "incident_id": incident_id, "kind": "ai_provider_failure",
        "status": "holding", "farm_key": farm, "node_id": 1, "synthetic": True,
        "scenario": "AI provider failure; safe HOLD/fallback without irrigation",
        "opened_at": started, "detected_at": started, "recovered_at": None,
        "monitor_id": monitor_id, "workflow_id": workflow_id,
        "scenario_run_id": run_id,
        "evidence": {"trace_ids": [], "log_events": [], "workflow_execution_ids": [run_id]},
        "updated_at": started,
    })
    logger = logging.getLogger("smiot.w10.drill")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler("/opt/smiot/logs/system.log")
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    tags = ["farm:greenhouse_h", "source:smiot_w10_correlated", "status:provider_error", "action:hold"]
    emit("smiot.ai.provider_failure", 1, tags)
    emit("smiot.ai.provider_success", 0, tags)
    with trace_span("smiot.ai.provider_failure", resource="gemini.synthetic", **{
        "incident.id": incident_id, "workflow.run_id": run_id, "farm.key": farm,
    }):
        logger.info(json.dumps({"event": "smiot_w10_provider_failure", "incident_id": incident_id,
                                "scenario_run_id": run_id, "farm_key": farm,
                                "decision": "HOLD", "fallback": "safe_no_irrigation", "synthetic": True}, separators=(",", ":")))
    decisions.insert_one({"_id": f"{incident_id}:hold", "incident_id": incident_id,
                          "decision": "HOLD", "action": "SAFE_FALLBACK", "reason": "provider_error",
                          "created_at": now(), "synthetic": True})
    recovered = now()
    emit("smiot.ai.provider_failure", 0, ["farm:greenhouse_h", "source:smiot_w10_correlated", "status:ok", "action:none"])
    emit("smiot.ai.provider_success", 1, ["farm:greenhouse_h", "source:smiot_w10_correlated", "status:ok", "action:none"])
    with trace_span("smiot.ai.recovered", resource="gemini.synthetic", **{
        "incident.id": incident_id, "workflow.run_id": run_id, "farm.key": farm,
    }):
        logger.info(json.dumps({"event": "smiot_w10_provider_recovered", "incident_id": incident_id,
                                "scenario_run_id": run_id, "farm_key": farm,
                                "decision": "CLEAR", "verified": True, "synthetic": True}, separators=(",", ":")))
    incidents.update_one({"_id": incident_id}, {"$set": {"status": "recovered", "recovered_at": recovered,
        "updated_at": recovered, "recovery_evidence": {"provider_success": True, "fallback_verified": True}}})
    # This is a short-lived SSM process; flush custom APM spans before exit.
    try:
        from ddtrace import tracer
        tracer.flush()
    except Exception:
        pass
    print(json.dumps({"workflow": "W10", "incident_id": incident_id, "scenario_run_id": run_id,
                      "status": "recovered", "synthetic": True}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
