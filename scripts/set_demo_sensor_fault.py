"""Switch the continuous demo publisher between normal and Node 2 flatline modes."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time

import paho.mqtt.client as mqtt
from dotenv import load_dotenv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("normal", "flatline"), help="normal readings or fixed 2.4%% soil humidity")
    parser.add_argument("--host", default=None, help="MQTT host (defaults to MQTT_HOST or localhost)")
    parser.add_argument("--port", type=int, default=None, help="MQTT port (defaults to MQTT_PORT or 1883)")
    args = parser.parse_args()

    load_dotenv()
    host = args.host or os.getenv("MQTT_HOST", "localhost")
    port = args.port or int(os.getenv("MQTT_PORT", "1883"))
    client_id = f"smiot-demo-fault-control-{os.getpid()}"
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    except AttributeError:
        client = mqtt.Client(client_id=client_id)

    connected = threading.Event()
    mode_ack = threading.Event()
    sensor_sample = threading.Event()
    received: dict[str, object] = {}

    def on_connect(mqtt_client, userdata, flags, reason_code, properties=None):
        if reason_code not in (None, 0):
            return
        mqtt_client.subscribe([("farm/demo/status", 1), ("farm/sensor", 1)])
        connected.set()

    def on_message(mqtt_client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if message.topic == "farm/demo/status" and payload.get("demo_node2_fault") in ("normal", "flatline"):
            received["ack"] = payload
            mode_ack.set()
        elif mode_ack.is_set() and message.topic == "farm/sensor" and payload.get("farm_key") == "greenhouse_a":
            node2 = payload.get("id6", {}).get("node2", {})
            if isinstance(node2, dict) and isinstance(node2.get("sh"), (int, float)):
                received["sample"] = {"timestamp": node2.get("timestamp", payload.get("timestamp")), "soil_humidity": node2["sh"]}
                sensor_sample.set()

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(host, port, keepalive=30)
    client.loop_start()
    if not connected.wait(timeout=8):
        client.loop_stop()
        raise RuntimeError(f"Could not connect to MQTT broker at {host}:{port}")

    info = client.publish(
        "farm/demo/control",
        json.dumps({"demo_node2_fault": args.mode}, separators=(",", ":")),
        qos=1,
    )
    info.wait_for_publish(timeout=5)
    if info.rc != mqtt.MQTT_ERR_SUCCESS or not info.is_published():
        client.disconnect()
        client.loop_stop()
        raise RuntimeError(f"MQTT did not confirm the mode command: rc={info.rc}")

    if not mode_ack.wait(timeout=8):
        client.disconnect()
        client.loop_stop()
        raise RuntimeError("Command was published, but the demo publisher did not confirm applying it on farm/demo/status")
    ack = received["ack"]
    if not sensor_sample.wait(timeout=45):
        client.disconnect()
        client.loop_stop()
        raise RuntimeError("Publisher confirmed the mode, but no following greenhouse_a sensor sample arrived within 45 seconds")
    sample = received["sample"]
    client.disconnect()
    client.loop_stop()

    if args.mode == "flatline":
        expected = 2.4
        print("Publisher ACK: Node 2 flatline mode applied.")
    else:
        expected = None
        print("Publisher ACK: Node 2 normal mode applied.")
    print(f"First sensor sample after change: soil_humidity={sample['soil_humidity']}%, timestamp={sample['timestamp']}.")
    if args.mode == "flatline" and sample["soil_humidity"] != expected:
        raise RuntimeError("Publisher ACKed flatline mode, but the first sensor sample was not 2.4%")
    if args.mode == "normal" and sample["soil_humidity"] == 2.4:
        raise RuntimeError("Publisher ACKed normal mode, but the first sensor sample remained at 2.4%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
