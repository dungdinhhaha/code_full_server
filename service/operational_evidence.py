"""Idempotent MongoDB evidence for monitor-triggered virtual safety actions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError
from service.mongodb_store import collection

STATES = {"requested", "published", "acknowledged", "failed", "verified"}
ORDER = {"requested": 1, "published": 2, "acknowledged": 3, "verified": 4, "failed": 5}


def record_action_event(payload: dict[str, Any], event_state: str) -> bool:
    """Upsert by stable command_id; broker delivery is recorded separately from device ACK."""
    if event_state not in STATES:
        raise ValueError("unsupported action ledger state")
    command_id = str(payload.get("command_id", ""))
    if not command_id or len(command_id) > 200:
        raise ValueError("command_id is required")
    action = str(payload.get("action", ""))
    if action not in {"HOLD", "CLEAR"}:
        raise ValueError("only the virtual HOLD/CLEAR actions are accepted")
    farm_key = str(payload.get("farm_key", "greenhouse_a"))
    if farm_key not in {"greenhouse_a", "greenhouse_b", "greenhouse_c", "greenhouse_d"}:
        raise ValueError("invalid farm scope for action ledger")
    try:
        node_id = int(payload.get("node_id", 2))
    except (TypeError, ValueError):
        raise ValueError("invalid node scope for action ledger")
    if node_id not in {1, 2}:
        raise ValueError("invalid node scope for action ledger")
    now = datetime.now(timezone.utc)
    ledger = collection("action_ledger")
    existing = ledger.find_one({"_id": command_id}, {"state": 1, "created_at": 1})
    old_state = (existing or {}).get("state")
    # QoS 1 delivery and the bridge's polling fallback may replay the same
    # transition. Preserve its first timestamp instead of rewriting evidence.
    if old_state == event_state:
        return False
    if old_state in {"acknowledged", "verified"} and event_state in {"requested", "published"}:
        return False
    if old_state == "failed" and event_state in {"requested", "published"}:
        return False
    if old_state and old_state != event_state and ORDER.get(event_state, 0) < ORDER.get(old_state, 0):
        return False
    doc = {
        "_id": command_id,
        "command_id": command_id,
        "incident_id": payload.get("incident_id"),
        "action": action,
        "state": event_state,
        "source": str(payload.get("source", "unknown"))[:80],
        "workflow_id": str(payload.get("workflow_id", ""))[:100] or None,
        "execution_id": str(payload.get("execution_id", ""))[:120] or None,
        "reason": str(payload.get("reason", ""))[:500],
        "target": str(payload.get("target", "wokwi_virtual_led"))[:80],
        "farm_key": farm_key,
        "node_id": node_id,
        "monitor_id": str(payload.get("monitor_id", ""))[:64] or None,
        "synthetic": True,
        "ack_kind": "device_simulation" if event_state == "acknowledged" else None,
        "device_uptime_ms": payload.get("device_uptime_ms"),
        "updated_at": now,
    }
    if event_state == "requested":
        doc["requested_at"] = now
    elif event_state == "published":
        doc["published_at"] = now
    elif event_state == "acknowledged":
        doc["acknowledged_at"] = now
        doc["virtual_output"] = payload.get("virtual_output")
    elif event_state == "failed":
        doc["failed_at"] = now
        doc["error"] = str(payload.get("error", ""))[:500]
    elif event_state == "verified":
        doc["verified_at"] = now
        doc["verification"] = payload.get("verification")
    doc.pop("_id", None)
    query = {"_id": command_id}
    if existing:
        query["state"] = old_state
    try:
        result = ledger.update_one(query, {"$set": doc, "$setOnInsert": {"created_at": now}}, upsert=existing is None)
    except DuplicateKeyError:
        # Another MQTT callback already wrote a newer transition for this ID.
        return False
    if existing and result.matched_count == 0:
        return False
    try:
        from service.incident_lifecycle import record_incident_action
        record_incident_action({**payload, "command_id": command_id}, event_state)
        if payload.get("incident_id"):
            from service.incident_lifecycle import add_incident_log_evidence
            add_incident_log_evidence(str(payload["incident_id"]), command_id, f"action_{action.lower()}_{event_state}")
        from service.logger import log_incident_event
        log_incident_event(
            incident_id=str(payload["incident_id"]) if payload.get("incident_id") else None,
            farm_key=farm_key,
            node_id=node_id,
            kind="action_transition",
            command_id=command_id,
            action=action,
            state=event_state,
            source=payload.get("source"),
            virtual_output=payload.get("virtual_output"),
        )
    except Exception:
        # Preserve the action ledger even if incident roll-up is temporarily unavailable.
        from service.logger import get_logger
        get_logger("INCIDENT").exception("Could not roll action event into incident document")
    from service.datadog_metrics import emit_count, metric_tags
    source_tag = str(payload.get("source", "other"))
    tags = metric_tags(doc["farm_key"], doc["node_id"], source_tag)
    tags.extend([f"action:{action.lower()}", f"state:{event_state}"])
    emit_count("smiot.safe_mode.transition", tags)
    return True
