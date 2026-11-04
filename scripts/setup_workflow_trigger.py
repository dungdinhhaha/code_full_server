"""Attach the published Node 2 safe-mode workflow to its Datadog monitor."""

from __future__ import annotations

import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)

DD_API_KEY = os.getenv("DD_API_KEY", "").strip()
DD_APP_KEY = os.getenv("DD_APP_KEY", "").strip()
DD_SITE = os.getenv("DD_SITE", "datadoghq.com").strip()
BASE_URL = f"https://api.{DD_SITE}"
MONITOR_NAME = "SMIOT | greenhouse_a Node 2 soil humidity flatline (synthetic demo)"
WORKFLOW_NAME = "SMIOT Node 2 Safe Mode - Hold and Verify"
HEADERS = {
    "DD-API-KEY": DD_API_KEY,
    "DD-APPLICATION-KEY": DD_APP_KEY,
    "Content-Type": "application/json",
}


def workflow_handle(name: str) -> str:
    """Datadog workflow mentions use the workflow handle/name, not its UUID."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return f"@workflow-{slug}"


def main() -> None:
    if not DD_API_KEY or not DD_APP_KEY:
        raise RuntimeError("DD_API_KEY and DD_APP_KEY must be configured in the project .env")

    monitors_response = requests.get(
        f"{BASE_URL}/api/v1/monitor",
        headers=HEADERS,
        params={"name": MONITOR_NAME},
        timeout=20,
    )
    monitors_response.raise_for_status()
    monitor = next(
        (item for item in monitors_response.json() if item.get("name") == MONITOR_NAME),
        None,
    )
    if not monitor:
        raise RuntimeError(f"Could not find monitor: {MONITOR_NAME}")

    workflows_response = requests.get(
        f"{BASE_URL}/api/v2/workflows",
        headers=HEADERS,
        params={"query": WORKFLOW_NAME},
        timeout=20,
    )
    workflows_response.raise_for_status()
    workflows = workflows_response.json().get("data", [])
    workflow = next(
        (item for item in workflows if item.get("attributes", {}).get("name") == WORKFLOW_NAME),
        None,
    )
    if not workflow:
        raise RuntimeError(f"Could not find workflow: {WORKFLOW_NAME}")
    workflow_detail = requests.get(
        f"{BASE_URL}/api/v2/workflows/{workflow['id']}",
        headers=HEADERS,
        timeout=20,
    )
    workflow_detail.raise_for_status()
    workflow = workflow_detail.json().get("data", workflow)
    attributes = workflow.get("attributes", {})
    if not attributes.get("published"):
        raise RuntimeError("The safe-mode workflow is not published")
    spec = attributes.get("spec") or {}
    triggers = spec.get("triggers", [])
    if not any("monitorTrigger" in trigger for trigger in triggers):
        raise RuntimeError("The workflow has no monitor trigger")

    handle = workflow_handle(WORKFLOW_NAME)
    handle_value = handle.removeprefix("@workflow-")
    if spec.get("handle") != handle_value:
        # Datadog requires a workflow handle in the published spec for
        # @workflow-<handle> monitor notifications to trigger executions.
        spec["handle"] = handle_value
        update_workflow = requests.patch(
            f"{BASE_URL}/api/v2/workflows/{workflow['id']}",
            headers=HEADERS,
            json={
                "data": {
                    "id": workflow["id"],
                    "type": "workflows",
                    "attributes": {"spec": spec, "published": True},
                }
            },
            timeout=30,
        )
        update_workflow.raise_for_status()
        verify_workflow = requests.get(
            f"{BASE_URL}/api/v2/workflows/{workflow['id']}",
            headers=HEADERS,
            timeout=20,
        )
        verify_workflow.raise_for_status()
        workflow = verify_workflow.json().get("data", workflow)
        verified_attributes = workflow.get("attributes", {})
        if not verified_attributes.get("published") or (verified_attributes.get("spec") or {}).get("handle") != handle_value:
            raise RuntimeError("Datadog did not retain the published workflow handle")

    monitor_id = monitor["id"]
    monitor_url = f"{BASE_URL}/api/v1/monitor/{monitor_id}"
    current = requests.get(monitor_url, headers=HEADERS, timeout=20)
    current.raise_for_status()
    monitor = current.json()
    message = monitor.get("message", "")

    if handle not in message:
        # Put the workflow mention inside the alert-only template so recovery
        # notifications do not run the safe-mode workflow.
        alert_close = "{{/is_alert}}"
        if alert_close in message:
            message = message.replace(alert_close, f" {handle}\r\n{alert_close}", 1)
        else:
            message = f"{message.rstrip()}\r\n{handle}"

        # Datadog monitor updates require preserving the monitor's definition;
        # sending only `message` can be rejected or accidentally drop fields.
        payload = {
            key: monitor[key]
            for key in ("name", "type", "query", "message", "options", "tags", "priority")
            if key in monitor
        }
        update = requests.put(monitor_url, headers=HEADERS, json=payload, timeout=20)
        update.raise_for_status()

    verify = requests.get(monitor_url, headers=HEADERS, timeout=20)
    verify.raise_for_status()
    if handle not in verify.json().get("message", ""):
        raise RuntimeError("Datadog did not retain the workflow mention in the monitor message")

    print(f"Monitor: {MONITOR_NAME} (ID {monitor_id}, state {verify.json().get('overall_state', 'unknown')})")
    print(f"Workflow: {WORKFLOW_NAME} (ID {workflow['id']}, published)")
    print(f"Verified mention: {handle}")
    print("The workflow records the safe HOLD decision; it does not send hardware commands.")


if __name__ == "__main__":
    main()
