"""Validation helpers for authenticated Datadog workflow notifications."""

from __future__ import annotations

from typing import Any


class NotificationValidationError(ValueError):
    """A notification payload error with a safe API result and status code."""

    def __init__(self, result: str, status_code: int):
        self.result = result
        self.status_code = status_code
        super().__init__(result)


_CATEGORIES = {"system", "sensor", "plc", "inverter", "schedule", "datadog"}
_SEVERITIES = {"info", "warning", "error"}
_WORKFLOW_STATUSES = {
    "investigating", "refused", "action_started", "pending_verification",
    "recovered", "already_healthy", "escalated", "failed",
}
_VERIFICATION_STATUSES = {"unknown", "pending", "passed", "failed", "not_applicable"}


def _optional_text(payload: dict[str, Any], key: str, limit: int) -> str | None:
    value = payload.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise NotificationValidationError("invalid_" + key, 422)
    value = value.strip()
    if len(value) > limit or any(ord(char) < 32 for char in value):
        raise NotificationValidationError("invalid_" + key, 422)
    return value or None


def normalize_datadog_notification(payload: Any) -> dict[str, Any]:
    """Validate and normalize the app-facing event without touching MongoDB.

    Required fields are string ``event_id`` and ``message``. Event IDs are
    bounded and control-character free so they can safely serve as the
    idempotency key. Unknown category/severity values fall back to fixed
    labels to keep UI styling and metrics cardinality bounded.
    """
    if not isinstance(payload, dict):
        raise NotificationValidationError("invalid_payload", 400)

    event_id = payload.get("event_id")
    message = payload.get("message")
    if not isinstance(event_id, str) or not isinstance(message, str):
        raise NotificationValidationError("event_id_and_message_required", 422)
    event_id, message = event_id.strip(), message.strip()
    if not event_id or len(event_id) > 160 or any(ord(char) < 32 for char in event_id):
        raise NotificationValidationError("invalid_event_id", 422)
    if not message or len(message) > 500 or any(ord(char) < 32 and char not in "\n\r\t" for char in message):
        raise NotificationValidationError("invalid_message", 422)

    category = payload.get("category", "system")
    severity = payload.get("severity", "info")
    if not isinstance(category, str):
        category = "datadog"
    if not isinstance(severity, str):
        severity = "warning"
    category = category.strip().lower()
    severity = severity.strip().lower()
    if category not in _CATEGORIES:
        category = "datadog"
    if severity not in _SEVERITIES:
        severity = "warning"

    farm_key = _optional_text(payload, "farm_key", 100)
    if farm_key:
        from service.farm_registry import FARM_KEYS
        if farm_key not in FARM_KEYS:
            raise NotificationValidationError("invalid_farm_key", 422)
    incident_id = _optional_text(payload, "incident_id", 160)
    workflow_name = _optional_text(payload, "workflow_name", 160)
    workflow_id = _optional_text(payload, "workflow_id", 80)
    workflow_run_id = _optional_text(payload, "workflow_run_id", 160)
    scenario_run_id = _optional_text(payload, "scenario_run_id", 160)
    command_id = _optional_text(payload, "command_id", 160)
    device_id = _optional_text(payload, "device_id", 120)
    node_id = _optional_text(payload, "node_id", 80)
    scenario_code = _optional_text(payload, "scenario_code", 100)
    event_time = _optional_text(payload, "event_time", 64)
    monitor_id = _optional_text(payload, "monitor_id", 40)
    status = _optional_text(payload, "status", 40)
    if status and status not in _WORKFLOW_STATUSES:
        raise NotificationValidationError("invalid_status", 422)
    decision_code = _optional_text(payload, "decision_code", 80)
    action_code = _optional_text(payload, "action_code", 80)
    verification_status = _optional_text(payload, "verification_status", 32)
    if verification_status and verification_status not in _VERIFICATION_STATUSES:
        raise NotificationValidationError("invalid_verification_status", 422)
    # A recovery-looking event is only valid after the app verifier reports a
    # positive result. This keeps an action-started or pending workflow from
    # appearing as a recovered incident in the notification bell.
    if status in {"recovered", "already_healthy"} and verification_status != "passed":
        raise NotificationValidationError("recovery_requires_verification", 422)
    evidence_refs_raw = payload.get("evidence_refs", [])
    if not isinstance(evidence_refs_raw, list) or len(evidence_refs_raw) > 10:
        raise NotificationValidationError("invalid_evidence_refs", 422)
    evidence_refs: list[str] = []
    for item in evidence_refs_raw:
        if not isinstance(item, str):
            raise NotificationValidationError("invalid_evidence_refs", 422)
        item = item.strip()
        if not item or len(item) > 160 or any(ord(char) < 32 for char in item):
            raise NotificationValidationError("invalid_evidence_refs", 422)
        evidence_refs.append(item)

    synthetic = payload.get("synthetic", False)
    if not isinstance(synthetic, bool):
        raise NotificationValidationError("invalid_synthetic", 422)

    return {
        "event_id": event_id,
        "message": message,
        "category": category,
        "severity": severity,
        "farm_key": farm_key,
        "incident_id": incident_id,
        "workflow_name": workflow_name,
        "workflow_id": workflow_id,
        "workflow_run_id": workflow_run_id,
        "scenario_run_id": scenario_run_id,
        "command_id": command_id,
        "device_id": device_id,
        "node_id": node_id,
        "scenario_code": scenario_code,
        "event_time": event_time,
        "synthetic": synthetic,
        "monitor_id": monitor_id,
        "status": status,
        "decision_code": decision_code,
        "action_code": action_code,
        "verification_status": verification_status,
        "evidence_refs": evidence_refs,
    }
