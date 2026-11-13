"""Emit bounded synthetic DogStatsD signals for W9/W10 workflow drills.

The script is intended to run on the SMIOT host where the Datadog Agent's
DogStatsD socket is reachable. It never calls a pump, actuator, AWS, Gemini,
or Datadog API. A manifest is always written; metrics are sent only with
``--send`` and carry ``source:smiot_synthetic_drill``.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path


def _metric(name: str, value: float, kind: str, tags: list[str]) -> str:
    return f"{name}:{value}|{kind}|#{','.join(tags)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true", help="send synthetic metrics to the local DogStatsD agent")
    parser.add_argument("--w9-normal", action="store_true", help="send a zero W9 signal for recovery")
    parser.add_argument("--w10-normal", action="store_true", help="send a clean provider-success signal for W10 recovery")
    parser.add_argument("--host", default=os.getenv("DD_AGENT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("DD_DOGSTATSD_PORT", "8125")))
    parser.add_argument("--output", type=Path, default=Path("outputs/evidence/w9_w10_metric_manifest.json"))
    args = parser.parse_args()

    source = "smiot_synthetic_drill"
    common = ["farm:greenhouse_a", "actuator:plc_pump", f"source:{source}"]
    metrics = [
        {"workflow": "W9", "metric": "smiot.actuator.command_unacknowledged", "value": 0 if args.w9_normal else 1, "type": "g",
         "tags": [*common, "event:unacknowledged"]},
        {"workflow": "W9", "metric": "smiot.actuator.safe_mode_active", "value": 1, "type": "g",
         "tags": common},
        {"workflow": "W10", "metric": "smiot.ai.provider_failure", "value": 0 if args.w10_normal else 1, "type": "g",
         "tags": [*common, "status:provider_error", "action:hold"]},
        {"workflow": "W10", "metric": "smiot.ai.ask_latency_ms", "value": 250 if args.w10_normal else 6000, "type": "g",
         "tags": [*common, "status:provider_error"]},
        {"workflow": "W10", "metric": "smiot.ai.provider_success", "value": 1 if args.w10_normal else 0, "type": "g",
         "tags": [*common, "status:ok" if args.w10_normal else "status:provider_error", "action:NONE" if args.w10_normal else "action:HOLD"]},
    ]
    manifest = {
        "artifact": "smiot_w9_w10_synthetic_metric_manifest",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "synthetic": True,
        "source": source,
        "sent": bool(args.send),
        "metrics": metrics,
        "external_calls": ["DogStatsD UDP only"] if args.send else [],
        "real_actuator_called": False,
        "gemini_called": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.send:
        payload = "\n".join(_metric(m["metric"], m["value"], m["type"], m["tags"]) for m in metrics).encode("utf-8")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.sendto(payload, (args.host, args.port))
    print(json.dumps({"output": str(args.output), "sent": args.send, "metric_count": len(metrics), "source": source}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
