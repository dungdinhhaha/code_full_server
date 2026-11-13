"""SYNTHETIC: inject or clear a stale-cache UI fault for one node (Ca 1 drill).

SYNTHETIC: chi lam sai lop hien thi (pages/home.py) trong thoi gian co han.
Khong chan du lieu vao MongoDB, khong sua telemetry that.

Usage:
  py -3.12 -X utf8 scripts/set_demo_ui_fault.py stale_cache --node 1 --minutes 6
  py -3.12 -X utf8 scripts/set_demo_ui_fault.py normal --node 1
"""

from __future__ import annotations

import argparse
import json
import os
import threading

import paho.mqtt.client as mqtt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("stale_cache", "normal"),
                        help="stale_cache: UI keeps showing OFFLINE for a while; normal: clear the fault")
    parser.add_argument("--node", type=int, default=1, help="node id to affect (default 1)")
    parser.add_argument("--minutes", type=int, default=6, help="fault duration in minutes, 1-30 (default 6)")
    parser.add_argument("--farm", default="greenhouse_a", help="farm key (default greenhouse_a)")
    parser.add_argument("--host", default=None, help="MQTT host (defaults to MQTT_HOST or localhost)")
    parser.add_argument("--port", type=int, default=None, help="MQTT port (defaults to MQTT_PORT or 1883)")
    args = parser.parse_args()
    minutes = max(1, min(args.minutes, 30))

    # Khong goi load_dotenv(): khong doc file .env. Dung bien moi truong hoac tham so --host/--port.
    host = args.host or os.getenv("MQTT_HOST", "localhost")
    port = args.port or int(os.getenv("MQTT_PORT", "1883"))
    client_id = f"smiot-demo-ui-fault-{os.getpid()}"
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    except AttributeError:
        client = mqtt.Client(client_id=client_id)

    connected = threading.Event()
    ack_event = threading.Event()
    received: dict[str, object] = {}

    def on_connect(mqtt_client, userdata, flags, reason_code, properties=None):
        if reason_code not in (None, 0):
            return
        mqtt_client.subscribe("farm/demo/status", 1)
        connected.set()

    def on_message(mqtt_client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if isinstance(payload, dict) and payload.get("demo_ui_fault") == args.mode and payload.get("node") == args.node:
            received["ack"] = payload
            ack_event.set()

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(host, port, keepalive=30)
    client.loop_start()
    if not connected.wait(timeout=8):
        client.loop_stop()
        raise RuntimeError(f"Could not connect to MQTT broker at {host}:{port}")

    command = {"demo_ui_fault": args.mode, "node": args.node, "minutes": minutes,
               "farm": args.farm, "synthetic": True}
    info = client.publish("farm/demo/control", json.dumps(command, separators=(",", ":")), qos=1)
    info.wait_for_publish(timeout=5)
    if info.rc != mqtt.MQTT_ERR_SUCCESS or not info.is_published():
        client.disconnect()
        client.loop_stop()
        raise RuntimeError(f"MQTT did not confirm the UI fault command: rc={info.rc}")

    acked = ack_event.wait(timeout=8)
    client.disconnect()
    client.loop_stop()
    if not acked:
        raise RuntimeError("Command was published, but the app did not confirm it on farm/demo/status")

    if args.mode == "stale_cache":
        print(f"SYNTHETIC: UI stale_cache applied to node {args.node} for {minutes} minutes (display only).")
    else:
        print(f"SYNTHETIC: UI fault cleared for node {args.node}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
