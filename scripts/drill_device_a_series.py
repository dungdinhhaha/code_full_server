#!/usr/bin/env python3
"""Build synthetic A-series drill payloads for the Velxio virtual pump and flow board.

Default mode only prints the payloads as JSON. ``--send`` publishes them with paho
to MQTT_BROKER/MQTT_PORT from ``service/mqtt.py``. No credentials are read or printed.

Cases:
  A2  -> W1 PLC safety trip (pump runs but pressure is zero)
  C10 -> W1 PLC safety trip (pipe leak / pressure-flow mismatch)
  A4  -> W9 actuator command without ACK (the pump suppresses its command ACK)
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone

SOURCE = "velxio_synthetic"
DEFAULT_FARM_KEY = "greenhouse_j"
SCENARIO_CONTROL_TOPIC = "farm/demo/control"
ACTUATOR_CONTROL_TOPIC = "farm/control"

DRILL_CASES: dict[str, dict[str, str]] = {
    "A2": {"workflow": "W1", "scenario_type": "a2_pump_pressure_zero"},
    "C10": {"workflow": "W1", "scenario_type": "pipe_leak"},
    "A4": {"workflow": "W9", "scenario_type": "a4_command_no_ack"},
}


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _correlation(case: str, run_id: str, incident_id: str) -> dict[str, str]:
    return {"scenario_code": case, "scenario_run_id": run_id, "incident_id": incident_id}


def build_drill_plan(
    case: str,
    farm_key: str = DEFAULT_FARM_KEY,
    *,
    run_id: str | None = None,
    incident_id: str | None = None,
    command_id: str | None = None,
    timestamp: str | None = None,
) -> list[tuple[str, dict[str, object]]]:
    """Return ``(topic, payload)`` pairs for one drill case. Nothing is sent here.

    The start command always comes first. W9 (A4) adds one safe OFF command on the
    actuator channel; the pump is expected to apply it without returning an ACK.
    """
    code = str(case or "").strip().upper()
    if code not in DRILL_CASES:
        raise ValueError(f"unknown drill case: {case!r}")
    farm = str(farm_key or "").strip()
    if not farm:
        raise ValueError("farm_key is required")
    run = str(run_id or uuid.uuid4())
    incident = str(incident_id or f"INC-DRILL-{code}-{run[:8]}")
    stamp = timestamp or _stamp()
    start_command = str(command_id or uuid.uuid4())

    start = {
        "action": "START_SCENARIO",
        "scenario_type": DRILL_CASES[code]["scenario_type"],
        "command_id": start_command,
        "farm_key": farm,
        "source": SOURCE,
        "synthetic": True,
        "timestamp": stamp,
        **_correlation(code, run, incident),
    }
    plan: list[tuple[str, dict[str, object]]] = [(SCENARIO_CONTROL_TOPIC, start)]

    if DRILL_CASES[code]["workflow"] == "W9":
        plan.append((ACTUATOR_CONTROL_TOPIC, {
            "action": "SET_OUTPUTS",
            "bit0": 0,
            "command_id": f"{start_command}:a4-cmd",
            "farm_key": farm,
            "source": SOURCE,
            "synthetic": True,
            "timestamp": stamp,
            **_correlation(code, run, incident),
        }))
    return plan


def publish_plan(plan: list[tuple[str, dict[str, object]]]) -> None:
    """Publish a plan over paho. Imports are local so payload tests need no broker."""
    import paho.mqtt.client as mqtt

    from service.mqtt import MQTT_BROKER, MQTT_PORT

    client_id = f"smiot-drill-a-series-{uuid.uuid4().hex[:8]}"
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    except AttributeError:
        client = mqtt.Client(client_id=client_id)
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=30)
    client.loop_start()
    try:
        for topic, payload in plan:
            info = client.publish(topic, json.dumps(payload, separators=(",", ":")), qos=1)
            info.wait_for_publish(timeout=5)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"publish to {topic} failed rc={info.rc}")
    finally:
        client.loop_stop()
        client.disconnect()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("case", choices=sorted(DRILL_CASES))
    parser.add_argument("--farm", default=DEFAULT_FARM_KEY)
    parser.add_argument("--send", action="store_true", help="publish over MQTT (default: print payloads only)")
    args = parser.parse_args(argv)
    plan = build_drill_plan(args.case, farm_key=args.farm)
    if not args.send:
        print(json.dumps([{"topic": topic, "payload": payload} for topic, payload in plan],
                         ensure_ascii=False, indent=2))
        return 0
    publish_plan(plan)
    print(json.dumps({"case": args.case, "published": len(plan)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
