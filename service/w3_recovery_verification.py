"""Read-only W3 recovery verification against the guarded SSM command output."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping


_COMMAND_ID = re.compile(r"^[0-9a-fA-F-]{36}$")
_INSTANCE_ID = re.compile(r"^i-[0-9a-fA-F]{8,17}$")
_WORKFLOW_RUN_ID = re.compile(r"^[0-9a-fA-F-]{36}$")
SSM_DOCUMENT_NAME = "SMIOT-GuardedStartApp"
_PENDING_STATUSES = {"Pending", "InProgress", "Delayed", "Cancelling"}
_FAILED_STATUSES = {"Cancelled", "TimedOut", "Failed", "DeliveryTimedOut", "ExecutionTimedOut", "Undeliverable", "Terminated"}


def validate_instance_id(instance_id: Any, expected_instance_id: str) -> bool:
    """Accept only the configured EC2 instance."""
    if not isinstance(instance_id, str) or not _INSTANCE_ID.fullmatch(instance_id.strip()):
        return False
    return bool(expected_instance_id) and instance_id.strip() == expected_instance_id.strip()


def validate_workflow_run_id(workflow_run_id: Any) -> bool:
    """Datadog's InstanceId workflow template variable is expected to be a UUID."""
    return isinstance(workflow_run_id, str) and bool(_WORKFLOW_RUN_ID.fullmatch(workflow_run_id.strip()))


def find_unique_command(commands: list[Mapping[str, Any]], workflow_run_id: str,
                        instance_id: str) -> dict[str, Any]:
    """Match only the guard document, target instance, and echoed IncidentId."""
    matches = []
    for command in commands:
        parameters = command.get("Parameters") or {}
        incident_values = parameters.get("IncidentId") or []
        instance_ids = command.get("InstanceIds") or []
        if (
            command.get("DocumentName") == SSM_DOCUMENT_NAME
            and instance_id in instance_ids
            and workflow_run_id in incident_values
        ):
            matches.append(command)
    if not matches:
        return {"status": "pending", "reason": "ssm_command_not_visible_yet"}
    if len(matches) != 1:
        return {"status": "not_verified", "reason": "multiple_matching_ssm_commands"}
    command_id = matches[0].get("CommandId")
    if not isinstance(command_id, str) or not _COMMAND_ID.fullmatch(command_id):
        return {"status": "not_verified", "reason": "ssm_command_id_invalid"}
    return {"status": "matched", "command_id": command_id}


def parse_guard_result(stdout: Any, *, expected_run_id: str | None = None) -> dict[str, Any]:
    """Parse a guard result and bind it to the expected workflow run."""
    if not validate_workflow_run_id(expected_run_id):
        return {"status": "not_verified", "reason": "expected_workflow_run_id_missing_or_invalid"}
    if not isinstance(stdout, str) or not stdout.strip():
        return {"status": "not_verified", "reason": "guard_result_missing"}
    try:
        result = json.loads(stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"status": "not_verified", "reason": "guard_result_invalid"}
    if not isinstance(result, dict) or result.get("event") != "smiot.guarded_recovery":
        return {"status": "not_verified", "reason": "guard_event_mismatch"}
    # The live SSM document predates the current shell helper and emits
    # `incident_id/status/detail` rather than `run_id/action/result`. Bind either
    # schema to the Datadog execution identifier before accepting its outcome.
    output_run_id = str(result.get("run_id") or result.get("incident_id") or "")
    if output_run_id != expected_run_id:
        return {"status": "not_verified", "reason": "guard_run_id_mismatch"}
    if result.get("result") == "verified" and result.get("action") == "start":
        status = "recovery_action_verified"
    elif result.get("result") == "verified_healthy" and result.get("action") == "none":
        status = "already_healthy"
    elif result.get("status") == "recovered" and result.get("detail") == "app_active_http_healthy_mongodb_ping_and_new_fresh_telemetry":
        status = "recovery_action_verified"
    elif result.get("status") == "skipped" and result.get("detail") == "app_already_active":
        status = "already_healthy"
    else:
        return {
            "status": "not_verified",
            "reason": str(result.get("reason") or result.get("detail") or result.get("status") or "guard_did_not_verify")[:120],
            "run_id": output_run_id[:64],
        }
    return {
        "status": status,
        "run_id": output_run_id[:64],
        "action": result.get("action") or ("start" if status == "recovery_action_verified" else "none"),
        "guard_timestamp": str(result.get("timestamp") or "")[:40],
    }


def classify_ssm_invocation(
    invocation: Mapping[str, Any], *, expected_run_id: str | None,
    expected_command_id: str | None, expected_instance_id: str | None,
) -> dict[str, Any]:
    """Return a result only for the exact SSM command/run/instance we requested.

    Missing correlation is unverified, including when a caller accidentally uses
    this helper without the expected command identifiers.
    """
    if not validate_workflow_run_id(expected_run_id):
        return {"status": "not_verified", "reason": "expected_workflow_run_id_missing_or_invalid"}
    if not isinstance(expected_command_id, str) or not _COMMAND_ID.fullmatch(expected_command_id):
        return {"status": "not_verified", "reason": "expected_command_id_missing_or_invalid"}
    if not isinstance(expected_instance_id, str) or not _INSTANCE_ID.fullmatch(expected_instance_id):
        return {"status": "not_verified", "reason": "expected_instance_id_missing_or_invalid"}
    if invocation.get("CommandId") != expected_command_id:
        return {"status": "not_verified", "reason": "ssm_command_id_mismatch"}
    if invocation.get("InstanceId") != expected_instance_id:
        return {"status": "not_verified", "reason": "ssm_instance_id_mismatch"}
    status = invocation.get("Status")
    if status in _PENDING_STATUSES:
        return {"status": "pending", "ssm_status": str(status),
                "command_id": expected_command_id, "instance_id": expected_instance_id,
                "run_id": expected_run_id}
    if status in _FAILED_STATUSES:
        return {"status": "not_verified", "reason": "ssm_command_failed", "ssm_status": str(status)}
    if status != "Success" or invocation.get("ResponseCode") != 0:
        return {"status": "not_verified", "reason": "ssm_command_not_successful", "ssm_status": str(status or "unknown")}
    guard = parse_guard_result(
        invocation.get("StandardOutputContent"), expected_run_id=expected_run_id
    )
    if guard["status"] not in {"recovery_action_verified", "already_healthy"}:
        return {**guard, "ssm_status": "Success"}
    return {**guard, "ssm_status": "Success", "command_id": expected_command_id,
            "instance_id": expected_instance_id, "run_id": expected_run_id}


def classify_live_health(health: Mapping[str, Any], *, max_sample_age_seconds: float = 180.0) -> bool:
    """Require current app, Mongo, MQTT, and a fresh persisted sample."""
    try:
        age = float(health.get("newest_sample_age_seconds"))
    except (TypeError, ValueError):
        return False
    return (
        health.get("app") == "ok"
        and health.get("mongo") == "ok"
        and health.get("mqtt") == "ok"
        and 0 <= age <= max_sample_age_seconds
    )
