r"""Start or stop a repeatable virtual-IoT fault run over MQTT.

Examples:
  py -3.12 scripts\demo_scenario.py start water_overrun --seed 17
  py -3.12 scripts\demo_scenario.py start pipe_leak --seed 17 --farm greenhouse_a
  py -3.12 scripts\demo_scenario.py start S4 --seed 17 --node 2
  py -3.12 scripts\demo_scenario.py start H6 --seed 17
  py -3.12 scripts\demo_scenario.py stop --run-id <scenario-run-id>
  py -3.12 scripts\demo_scenario.py recovery-check A2 --evidence-json '{...}'

The virtual publisher and app MQTT receiver must already be running. The script
waits for applied ACK, a correlated sample, and an app ACK that its separate
scenario observation was persisted. STOP moves the incident to recovery review;
it does not itself verify or close the incident.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
from uuid import uuid4

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from service.scenario_catalog import resolve_scenario, scenario_codes, scenario_types


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    start = subparsers.add_parser("start", help="start a deterministic fault scenario")
    stop = subparsers.add_parser("stop", help="stop an active scenario")
    recovery = subparsers.add_parser("recovery-check", help="classify supplied recovery evidence; never closes an incident")
    for subparser in (start, stop):
        subparser.add_argument("--host", default=None, help="MQTT host (defaults to MQTT_HOST or localhost)")
        subparser.add_argument("--port", type=int, default=None, help="MQTT port (defaults to MQTT_PORT or 1883)")
        subparser.add_argument("--timeout", type=float, default=12.0)
    start.add_argument("scenario", choices=tuple(dict.fromkeys(
        (*scenario_codes(), *scenario_types(),
         "soil_flatline", "soil_spike", "soil_out_of_range", "water_overrun", "pipe_leak", "vent_stuck")
    )), help="36 case code (C1-C10, S1-S6, D1-D7, A1-A7, H1-H6) or compatible legacy name")
    start.add_argument("--seed", type=int, default=1)
    start.add_argument("--farm", default="greenhouse_a")
    start.add_argument("--node", type=int, choices=(1, 2), default=None)
    start.add_argument("--lot-id", default=None)
    stop.add_argument("--run-id", required=True)
    stop.add_argument("--farm", default="greenhouse_a")
    recovery.add_argument("scenario", choices=scenario_codes())
    recovery.add_argument("--evidence-json", required=True, help="JSON object with fresh post-action evidence")
    recovery.add_argument("--run-json", default="{}", help="JSON object with run baselines/configuration")
    recovery.add_argument("--context-json", default="{}", help="JSON object with approved domain context")
    recovery.add_argument("--normal-samples", type=int, default=0)
    args = parser.parse_args()

    if args.operation == "recovery-check":
        from service.scenario_recovery import evaluate_scenario_recovery

        def parse_object(raw: str, label: str) -> dict:
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{label} must be valid JSON: {exc}")
            if not isinstance(value, dict):
                raise SystemExit(f"{label} must be a JSON object")
            return value

        result = evaluate_scenario_recovery(
            args.scenario,
            parse_object(args.evidence_json, "--evidence-json"),
            run=parse_object(args.run_json, "--run-json"),
            context=parse_object(args.context_json, "--context-json"),
            normal_samples=max(0, args.normal_samples),
        )
        print(json.dumps({"scenario_code": args.scenario, **result}, ensure_ascii=False, indent=2))
        return 0 if result.get("recovered") else 3

    load_dotenv()
    host = args.host or os.getenv("MQTT_HOST", "localhost")
    port = args.port or int(os.getenv("MQTT_PORT", "1883"))
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"smiot-scenario-control-{os.getpid()}")
    except AttributeError:
        client = mqtt.Client(client_id=f"smiot-scenario-control-{os.getpid()}")

    connected = threading.Event()
    ack_ready = threading.Event()
    sample_ready = threading.Event()
    observation_ack_ready = threading.Event()
    safety_trip_ready = threading.Event()
    safety_ack_ready = threading.Event()
    run_id = str(args.run_id) if args.operation == "stop" else str(uuid4())
    command_id = str(uuid4())
    received: dict[str, dict] = {}

    def on_connect(mqtt_client, userdata, flags, reason_code, properties=None):
        if reason_code not in (None, 0):
            return
        mqtt_client.subscribe([("farm/demo/status", 1), ("farm/demo/evidence/ack", 1), ("farm/sensor", 1),
                               ("farm/status", 1), ("farm/command/ack", 1)])
        connected.set()

    def on_message(mqtt_client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if message.topic == "farm/demo/status" and payload.get("scenario_run_id") == run_id:
            received["ack"] = payload
            if payload.get("command_id") == command_id:
                ack_ready.set()
        elif (message.topic == "farm/sensor" and payload.get("scenario_run_id") == run_id
              and payload.get("farm_key") == getattr(args, "farm", "greenhouse_a")):
            received["sample"] = payload
            sample_ready.set()
        elif (message.topic == "farm/demo/evidence/ack"
              and payload.get("scenario_run_id") == run_id):
            received["observation_ack"] = payload
            if payload.get("persisted") is True:
                observation_ack_ready.set()
        elif (message.topic == "farm/status" and payload.get("event") == "virtual_plc_safety_trip"
              and payload.get("scenario_run_id") == run_id):
            received["safety_trip"] = payload
            safety_trip_ready.set()
        elif (message.topic == "farm/command/ack" and payload.get("event") == "virtual_interlock_ack"
              and payload.get("scenario_run_id") == run_id):
            received["safety_ack"] = payload
            safety_ack_ready.set()

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(host, port, keepalive=30)
    client.loop_start()
    try:
        if not connected.wait(timeout=8):
            raise RuntimeError(f"Could not connect to MQTT broker at {host}:{port}")
        if args.operation == "start":
            command = {
                "action": "START_SCENARIO", "scenario_type": args.scenario,
                "scenario_run_id": run_id, "command_id": command_id,
                "farm_key": args.farm, "node_id": args.node,
                "lot_id": args.lot_id, "seed": args.seed,
            }
        else:
            command = {"action": "STOP_SCENARIO", "scenario_run_id": run_id,
                       "command_id": command_id, "farm_key": args.farm}
        info = client.publish("farm/demo/control", json.dumps(command, separators=(",", ":")), qos=1)
        info.wait_for_publish(timeout=5)
        if info.rc != mqtt.MQTT_ERR_SUCCESS or not info.is_published():
            raise RuntimeError(f"MQTT command publish failed: rc={info.rc}")
        if not ack_ready.wait(timeout=args.timeout):
            raise RuntimeError("No matching simulator ACK received; confirm the continuous demo publisher is running")
        ack = received["ack"]
        print(json.dumps({"operation": args.operation, "scenario_run_id": run_id, "ack": ack}, indent=2))
        if not ack.get("applied"):
            return 2
        if args.operation == "start":
            node_interval = max(1, int(os.getenv("SMIOT_SIM_NODE_INTERVAL_SECONDS", "60")))
            if not sample_ready.wait(timeout=max(args.timeout, node_interval + 5)):
                raise RuntimeError("Simulator ACKed the run but no correlated telemetry arrived afterward")
            sample = received["sample"]
            node_key = f"node{args.node or 2}"
            print(json.dumps({"first_correlated_sample": {
                "farm_key": sample.get("farm_key"), "lot_id": sample.get("lot_id"),
                "scenario_run_id": sample.get("scenario_run_id"),
                "timestamp": sample.get("timestamp"), "node": sample.get("id6", {}).get(node_key),
                "flow": sample.get("id3"), "drain": sample.get("id7"),
                "ventilation": sample.get("id8"),
            }}, indent=2))
            if not observation_ack_ready.wait(timeout=max(8.0, args.timeout)):
                ack_result = received.get("observation_ack") or {}
                if ack_result.get("duplicate_or_rejected"):
                    raise RuntimeError("Scenario observation was rejected or duplicated before storage confirmation")
                raise RuntimeError("No MongoDB persistence ACK for the scenario observation")
            print(json.dumps({"mongo_evidence_ack": received["observation_ack"]}, indent=2))
            scenario_spec = resolve_scenario(args.scenario) or {}
            scenario_code = scenario_spec.get("code")
            expects_interlock = args.scenario == "pipe_leak" or scenario_code in {"A1", "A2", "A3"}
            if expects_interlock:
                max_volume_l = max(1.0, float(os.getenv("SMIOT_VIRTUAL_PLC_MAX_VOLUME_L", "20")))
                flow_lpm = max(0.1, float(os.getenv("SMIOT_VIRTUAL_PLC_FLOW_LPM", "4.5")))
                expected_flow = 12.0 if scenario_code == "A1" or args.scenario == "water_overrun" else flow_lpm
                trip_timeout = max(args.timeout, max_volume_l * 60.0 / expected_flow + 12.0)
                if not safety_trip_ready.wait(timeout=trip_timeout):
                    raise RuntimeError("No correlated virtual-PLC safety trip was observed")
                if not safety_ack_ready.wait(timeout=args.timeout):
                    raise RuntimeError("Local interlock tripped but no matching SAFE_STOP ACK was received")
                trip, safety_ack = received["safety_trip"], received["safety_ack"]
                safe_verified = (
                    safety_ack.get("applied") is True and safety_ack.get("verified") is True
                    and safety_ack.get("outputs_off") is True
                    and safety_ack.get("valve_closed") is True
                    and safety_ack.get("safe_mode_active") is True
                )
                print(json.dumps({"local_safety_trip": trip, "local_safety_ack": safety_ack,
                                  "safe_stop_verified": safe_verified}, indent=2))
                if not safe_verified:
                    raise RuntimeError("Interlock ACK did not prove pumps OFF, valve closed, and safe mode latched")
            print("The application confirmed the evaluator observation was persisted in MongoDB.")
        return 0
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    raise SystemExit(main())
