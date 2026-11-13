"""Prepare or apply notification actions to the ten SMIOT Datadog workflows.

The HTTP credential lives in a Datadog Action Connection, never in this JSON.
Default mode writes reviewable JSON files only. Pass --apply to PATCH existing
workflows after the app endpoint and HTTP connection have been deployed.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "outputs" / "workflow_imports" / "20261110_published_10_workflows.json"
API = "https://api.datadoghq.com/api/v2/workflows"
APP_URL = "https://13-238-30-218.sslip.io/api/integrations/datadog/notification"
CONNECTION_LABEL = "SMIOT_APP_HTTP"


def _request(method: str, url: str, payload: dict | None = None) -> dict:
    api_key, app_key = os.getenv("DD_API_KEY", ""), os.getenv("DD_APP_KEY", "")
    if not api_key or not app_key:
        raise RuntimeError("Set DD_API_KEY and DD_APP_KEY in the environment; do not put them in files or JSON.")
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=body, method=method, headers={
        "DD-API-KEY": api_key,
        "DD-APPLICATION-KEY": app_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Datadog API returned HTTP {exc.code} for {method} {url.rsplit('/', 1)[-1]}.") from None
    except URLError as exc:
        raise RuntimeError(f"Datadog API request failed: {type(exc.reason).__name__}.") from None


def _notification_step() -> dict:
    # The connection stores Authorization as "Bearer {{ smiotAppToken }}".
    # Workflow run identifiers make Mongo notification writes idempotent.
    request_body = json.dumps({
        # Workflow identity variables are top-level context variables in
        # Datadog ({{InstanceId}}, {{WorkflowName}}, {{WorkflowId}}), not a
        # nested {{Workflow.*}} object. Keep the body JSON serialized as a
        # string so the HTTP action interpolates the complete request body.
        "event_id": "{{InstanceId}}",
        "workflow_name": "{{WorkflowName}}",
        "workflow_id": "{{WorkflowId}}",
        "message": "Datadog đã chạy workflow {{WorkflowName}}. Mở run {{InstanceId}} để xem kết quả và bước tiếp theo.",
        "category": "datadog",
        "severity": "info",
    }, ensure_ascii=False, separators=(",", ":"))
    return {
        "name": "notify_smiot_app",
        "actionId": "com.datadoghq.http.request",
        "connectionLabel": CONNECTION_LABEL,
        "parameters": [
            {"name": "verb", "value": "POST"},
            {"name": "url", "value": APP_URL},
            {"name": "requestHeaders", "value": [
                {"key": "Content-Type", "value": ["application/json"]},
            ]},
            {"name": "body", "value": request_body},
        ],
    }


def prepare(data: dict, connection_id: str) -> dict:
    """Return an API update payload while preserving the existing workflow graph."""
    result = copy.deepcopy(data)
    attributes = result["data"]["attributes"]
    spec = attributes["spec"]
    steps = spec.setdefault("steps", [])
    # Preserve existing AWS/Datadog connections and add one scoped HTTP token
    # connection by label. No credential value is stored in the workflow spec.
    envs = spec.setdefault("connectionEnvs", [])
    default_env = next((env for env in envs if env.get("env") == "default"), None)
    if default_env is None:
        default_env = {"env": "default", "connections": []}
        envs.append(default_env)
    connections = default_env.setdefault("connections", [])
    connections[:] = [item for item in connections if item.get("label") != CONNECTION_LABEL]
    connections.append({"connectionId": connection_id, "label": CONNECTION_LABEL})

    # Normalize an existing notification step as well as new ones. This keeps
    # old drafts compatible with the HTTP action input schema.
    notify = next((step for step in steps if step.get("name") == "notify_smiot_app"), None)
    if notify is None:
        notify = _notification_step()
        steps.append(notify)
    else:
        fresh = _notification_step()
        notify["actionId"] = fresh["actionId"]
        notify["connectionLabel"] = fresh["connectionLabel"]
        notify["parameters"] = fresh["parameters"]

    # Every terminal path reports to the app, including fail-closed branches.
    for step in steps:
        if step.get("name") != "notify_smiot_app" and not step.get("outboundEdges"):
            step["outboundEdges"] = [{"branchName": "main", "nextStepName": "notify_smiot_app"}]

    workflow_id = result["data"].get("id")
    workflow_type = result["data"].get("type", "workflows")
    result["data"] = {
        "id": workflow_id,
        "type": workflow_type,
        "attributes": {
            "name": attributes["name"],
            "description": attributes.get("description", ""),
            "published": attributes.get("published", True),
            "runAs": {"type": "owner"},
            "sensitivePrivileges": attributes.get("sensitivePrivileges", False),
            "tags": attributes.get("tags", []),
            "spec": spec,
        },
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connection-id", required=True, help="Datadog HTTP Action Connection ID; no token value is accepted here.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "workflow_imports" / "app_notifications")
    parser.add_argument("--apply", action="store_true", help="PATCH Datadog after JSON has been prepared and reviewed.")
    args = parser.parse_args()
    if args.connection_id == "CONNECTION_ID_PLACEHOLDER":
        parser.error("Supply the actual Datadog HTTP Action Connection ID.")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prepared_count = 0
    for item in manifest["workflows"]:
        workflow_id = item["id"]
        remote = _request("GET", f"{API}/{workflow_id}")
        prepared = prepare(remote, args.connection_id)
        outfile = args.output_dir / f"{item['handle']}.json"
        outfile.write_text(json.dumps(prepared, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.apply:
            _request("PATCH", f"{API}/{workflow_id}", prepared)
        prepared_count += 1
    print(f"Prepared {prepared_count} workflow JSON files; applied={str(args.apply).lower()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
