"""Correlation helpers for the specialized W6 and W9 drills.

These drills do not use the generic scenario runner.  They still need the
same evidence contract: one incident id is carried by the injector, app
events, MongoDB record, and Datadog log/trace.  All records created here are
explicitly synthetic and farm-scoped.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from service.mongodb_store import collection
from service.observability import trace_span


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"INC-SMIOT-{prefix}-{_now():%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8].upper()}"


def ensure_special_incident(
    kind: str,
    farm_key: str,
    *,
    incident_id: str | None = None,
    monitor_id: str | None = None,
    workflow_id: str | None = None,
    command_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    """Create or reuse one W6/W9 incident without guessing its scope."""
    farm_key = str(farm_key or "").strip()
    if not farm_key:
        raise ValueError("farm_key is required")
    incidents = collection("operational_incidents")
    wanted = str(incident_id or "").strip()
    if wanted:
        existing = incidents.find_one({"_id": wanted}, {"_id": 1})
        if existing:
            return wanted
    if not wanted:
        existing = incidents.find_one(
            {"kind": kind, "farm_key": farm_key,
             "status": {"$in": ["open", "holding", "recovering"]}},
            sort=[("opened_at", -1)],
        )
        if existing:
            return str(existing["_id"])
        wanted = _new_id("W6" if kind == "detector_heartbeat_missing" else "W9")

    now = _now()
    doc: dict[str, Any] = {
        "_id": wanted,
        "incident_id": wanted,
        "kind": kind,
        "status": "open",
        "farm_key": farm_key,
        "opened_at": now,
        "detected_at": now,
        "recovered_at": None,
        "monitor_id": str(monitor_id) if monitor_id else None,
        "workflow_id": str(workflow_id) if workflow_id else None,
        "synthetic": True,
        "source": "specialized_drill",
        "details": details or {},
        "timeline": [{"at": now, "event": "opened", "by": "synthetic_injector"}],
        "evidence": {
            "telemetry_message_ids": [], "trace_ids": [], "log_events": [],
            "workflow_execution_ids": [], "action_command_ids": [],
        },
        "updated_at": now,
    }
    if command_id:
        doc["details"]["command_id"] = str(command_id)[:128]
    try:
        incidents.insert_one(doc)
    except Exception:
        # A concurrent retry may have inserted the requested id.  Never create
        # a second incident just because the acknowledgement was duplicated.
        if not incidents.find_one({"_id": wanted}, {"_id": 1}):
            raise
    return wanted


def record_special_event(
    incident_id: str,
    event: str,
    *,
    farm_key: str,
    details: dict[str, Any] | None = None,
    status: str | None = None,
) -> None:
    """Persist one idempotent timeline event and emit a correlated span/log."""
    incident_id = str(incident_id or "").strip()
    if not incident_id:
        return
    now = _now()
    event_doc = {"at": now, "event": str(event)[:100], "details": details or {}}
    update: dict[str, Any] = {"$push": {"timeline": event_doc}, "$set": {"updated_at": now}}
    if status:
        update["$set"]["status"] = status
    collection("operational_incidents").update_one({"_id": incident_id, "farm_key": farm_key}, update)
    with trace_span(
        f"smiot.{event}",
        resource="specialized_drill",
        **{"incident.id": incident_id, "farm.key": farm_key, "event.name": event},
    ):
        # The span context is also recorded by the app logger, so the same
        # incident can be searched in Datadog logs and traces.
        import logging
        logging.getLogger("smiot.special_drill").info(json.dumps(
            {"event": event, "incident_id": incident_id, "farm_key": farm_key,
             "synthetic": True, **(details or {})}, separators=(",", ":")
        ))


def recover_special_incident(
    incident_id: str,
    *,
    farm_key: str,
    verification: dict[str, Any],
    event: str = "recovered",
) -> bool:
    """Close only the exact incident after a positive app-side verification."""
    incident_id = str(incident_id or "").strip()
    if not incident_id or not verification:
        return False
    now = _now()
    result = collection("operational_incidents").update_one(
        {"_id": incident_id, "farm_key": farm_key,
         "status": {"$in": ["open", "holding", "recovering"]}},
        {"$set": {"status": "recovered", "recovered_at": now,
                   "recovery_verification": verification, "updated_at": now},
         "$push": {"timeline": {"at": now, "event": event, "by": "app_verifier"}}},
    )
    if result.modified_count:
        with trace_span(
            "smiot.special_drill.recovery",
            resource="recovery_verification",
            **{"incident.id": incident_id, "farm.key": farm_key},
        ):
            import logging
            logging.getLogger("smiot.special_drill").info(json.dumps(
                {"event": event, "incident_id": incident_id, "farm_key": farm_key,
                 "synthetic": True, **verification}, separators=(",", ":")
            ))
        return True
    return False


def active_special_incident(kind: str, farm_key: str) -> dict[str, Any] | None:
    return collection("operational_incidents").find_one(
        {"kind": kind, "farm_key": str(farm_key),
         "status": {"$in": ["open", "holding", "recovering"]}},
        sort=[("opened_at", -1)],
    )
