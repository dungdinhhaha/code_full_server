"""Publish the reviewed W3 spec to the existing Datadog workflow only."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ID = "373ed0c0-4509-4fcd-a067-f54f0becc00e"
API = "https://api.datadoghq.com/api/v2/workflows/" + WORKFLOW_ID

def keys():
    values = {}
    for line in Path(r"D:\attt\APP_KEY.txt").read_text(encoding="utf-8").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            values[k.strip().lower()] = v.strip()
    api = values.get("api_keys") or values.get("api_key") or values.get("key_id")
    app = values.get("app_key") or values.get("application_key")
    if not api or not app:
        raise RuntimeError("Datadog key labels are missing")
    return api, app

def call(method, payload=None):
    api, app = keys()
    body = json.dumps(payload).encode() if payload is not None else None
    req = Request(API, method=method, data=body, headers={
        "DD-API-KEY": api, "DD-APPLICATION-KEY": app,
        "Accept": "application/json", "Content-Type": "application/json",
    })
    with urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())

def main():
    remote = call("GET")
    data = remote["data"]
    attrs = data["attributes"]
    attrs["spec"] = json.loads((ROOT / "infra/datadog-workflows/specs/w3.json").read_text(encoding="utf-8"))
    attrs["published"] = True
    payload = {"data": {"id": data["id"], "type": data.get("type", "workflows"), "attributes": attrs}}
    call("PATCH", payload)
    check = call("GET")["data"]["attributes"]
    spec = check.get("spec", {})
    print(json.dumps({
        "workflow_id": data["id"],
        "published": check.get("published"),
        "step_count": len(spec.get("steps", [])),
        "verifier_retries": next((h.get("retryStrategy", {}).get("linear", {}).get("maxRetries") for s in spec.get("steps", []) if s.get("name") == "verify_smiot_recovery" for h in s.get("errorHandlers", [])), None),
    }))

if __name__ == "__main__":
    main()
