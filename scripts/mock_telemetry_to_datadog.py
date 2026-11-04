"""Send continuously simulated SMIOT node gauges to Datadog.

By default, this publishes DogStatsD metrics directly. With --publish-mqtt it
publishes sensor-only messages to the app's farm/sensor topic; the running app
persists those node readings to SQLite and, when enabled, MongoDB. It never
publishes PLC/control commands. Stop it with Ctrl+C.
"""

from __future__ import annotations

import random
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service.datadog_metrics import emit_node_metrics


def create_mqtt_client():
    import paho.mqtt.client as mqtt

    client_id = f"smiot-gdd-demo-{int(time.time())}"
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    except AttributeError:
        return mqtt.Client(client_id=client_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish synthetic SMIOT sensor readings.")
    parser.add_argument(
        "--publish-mqtt",
        action="store_true",
        help="Publish node readings to farm/sensor so the app persists them to SQLite/MongoDB.",
    )
    parser.add_argument("--mqtt-host", default="localhost")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    args = parser.parse_args()

    rng = random.Random()
    sample = 0
    mqtt_client = None
    if args.publish_mqtt:
        mqtt_client = create_mqtt_client()
        mqtt_client.connect(args.mqtt_host, args.mqtt_port, keepalive=60)
        mqtt_client.loop_start()
        deadline = time.monotonic() + 8
        while not mqtt_client.is_connected() and time.monotonic() < deadline:
            time.sleep(0.1)
        if not mqtt_client.is_connected():
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
            raise RuntimeError(f"MQTT broker did not connect at {args.mqtt_host}:{args.mqtt_port}")
        print(f"Publishing synthetic sensor-only MQTT messages to farm/sensor at {args.mqtt_host}:{args.mqtt_port}.")
    else:
        print("Sending synthetic SMIOT metrics every 10 seconds; stop with Ctrl+C.")
    try:
        while True:
            sample += 1
            node1 = {
                "at": round(29.5 + rng.uniform(-0.4, 0.4), 1),
                "ah": round(78.0 + rng.uniform(-1.0, 1.0), 1),
                "st": round(27.1 + rng.uniform(-0.3, 0.3), 1),
                "sh": round(43.2 + rng.uniform(-0.8, 0.8), 1),
                "sec": round(1.3 + rng.uniform(-0.05, 0.05), 2),
            }
            node2 = {
                "at": round(30.1 + rng.uniform(-0.4, 0.4), 1),
                "ah": round(82.0 + rng.uniform(-1.0, 1.0), 1),
                "st": round(26.5 + rng.uniform(-0.3, 0.3), 1),
                "sh": 2.4,  # Deliberately frozen for the flatline demo.
                "sec": round(1.2 + rng.uniform(-0.05, 0.05), 2),
            }
            if mqtt_client:
                payload = {
                    "device_name": "Sensor",
                    "farm_key": "greenhouse_a",
                    "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                    "id6": {"node1": node1, "node2": node2},
                }
                info = mqtt_client.publish("farm/sensor", json.dumps(payload), qos=1)
                info.wait_for_publish(timeout=5)
            else:
                emit_node_metrics("greenhouse_a", 1, node1)
                emit_node_metrics("greenhouse_a", 2, node2)
            now = datetime.now().astimezone().strftime("%H:%M:%S")
            print(
                f"[{now}] sample={sample}; Node1 soil_humidity={node1['sh']}%; "
                "Node2 soil_humidity=2.4% (frozen)",
                flush=True,
            )
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nStopped synthetic SMIOT metrics publisher.", flush=True)
    finally:
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()


if __name__ == "__main__":
    main()
