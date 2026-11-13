"""Save sanitized read-back evidence for the bounded W7/W8 advisory drills."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def keys() -> dict[str, str]:
    values = {}
    for line in Path(r"D:\attt\APP_KEY.txt").read_text(encoding="utf-8").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            values[k.strip().lower()] = v.strip()
    return {"DD-API-KEY": values.get("api_keys") or values.get("key_id", ""),
            "DD-APPLICATION-KEY": values.get("app_key") or values.get("application_key", ""),
            "Accept": "application/json"}


H = keys()


def get(url: str) -> dict:
    with urlopen(Request(url, headers=H), timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def monitor(mid: str) -> dict:
    data = get(f"https://api.datadoghq.com/api/v1/monitor/{mid}?group_states=all")
    groups = (data.get("state") or {}).get("groups") or {}
    return {"id": mid, "name": data.get("name"), "query": data.get("query"),
            "overall_state": data.get("overall_state"),
            "groups": {k: v.get("status") for k, v in groups.items()}}


def workflow(wid: str, run_id: str) -> dict:
    data = get(f"https://api.datadoghq.com/api/v2/workflows/{wid}/instances/{run_id}")
    attrs = data.get("data", {}).get("attributes", {})
    status = attrs.get("instanceStatus") or {}
    source = attrs.get("source") or {}
    handle = source.get("handle") or {}
    return {"workflow_id": wid, "run_id": run_id,
            "status": status.get("detailsKind") or status.get("displayName"),
            "end_timestamp": attrs.get("endTimestamp"),
            "monitor_id": handle.get("id"), "monitor_kind": handle.get("kind")}


def main() -> int:
    artifact = {
        "artifact": "smiot_w7_w8_advisory_drills",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "synthetic": True,
        "real_actuator_called": False,
        "real_irrigation_schedule_changed": False,
        "target": {"farm": "greenhouse_j", "node": 1},
        "w7": {"monitor": monitor("343594187"),
               "workflow": workflow("bb86206c-6df8-4b1d-8016-175a2fc62e49", "2e137be3-3e6f-4c6e-8592-4bce06f4b1d5"),
               "ssm_start_command": "ab792727-d5ec-41a7-8391-bfe916fcd723"},
        "w8": {"monitor": monitor("343594185"),
               "workflow": workflow("593a670c-d59c-4104-8658-df260245a21e", "297e3e4b-6afb-4db6-a1ed-99cd54315b53"),
               "ssm_start_command": "f5263242-1d70-4e4d-8e0c-82123141eb40"},
        "normalization": {"w7_w8_clear_ssm_command": "9ec3d4fe-a022-4f63-b760-afb619234775"},
    }
    out = Path("outputs/evidence/w7_w8_advisory_drills_runtime.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "w7_monitor": artifact["w7"]["monitor"]["overall_state"],
                      "w8_monitor": artifact["w8"]["monitor"]["overall_state"],
                      "w7_workflow": artifact["w7"]["workflow"]["status"],
                      "w8_workflow": artifact["w8"]["workflow"]["status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
