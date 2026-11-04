"""Publish a synthetic Node 2 recovery sequence through MQTT and Datadog.

This sends sensor-only messages to ``farm/sensor``. It never publishes PLC,
inverter, pump, or other hardware-control commands. The normal continuous demo
publisher may continue running and keep Node 2 frozen; this script only creates
a bounded recovery segment for the observability demonstration. It also submits
the same bounded series directly to Datadog with a source tag so the monitor can
evaluate the recovery independently of the background frozen-value publisher.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import paho.mqtt.client as mqtt
from dotenv import load_dotenv


BROKER = "localhost"
PORT = 1883
TOPIC = "farm/sensor"
FARM_KEY = "greenhouse_a"
RECOVERY_VALUES = (40.8, 41.6, 42.3, 41.9, 43.1, 42.6)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def create_client() -> mqtt.Client:
    client_id = f"smiot-node2-recovery-demo-{int(time.time())}"
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    except AttributeError:
        return mqtt.Client(client_id=client_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a bounded synthetic Node 2 recovery sequence.")
    parser.add_argument("--count", type=int, default=len(RECOVERY_VALUES), help="Number of sensor samples (1-6).")
    parser.add_argument("--interval", type=float, default=10.0, help="Seconds between samples.")
    parser.add_argument("--mqtt-host", default="localhost")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    args = parser.parse_args()
    if not 1 <= args.count <= len(RECOVERY_VALUES):
        parser.error(f"--count must be between 1 and {len(RECOVERY_VALUES)}")
    if args.interval < 0:
        parser.error("--interval must be >= 0")

    client = create_client()
    client.connect(args.mqtt_host, args.mqtt_port, keepalive=60)
    client.loop_start()
    deadline = time.monotonic() + 8
    while not client.is_connected() and time.monotonic() < deadline:
        time.sleep(0.1)
    if not client.is_connected():
        client.loop_stop()
        client.disconnect()
        raise RuntimeError(f"MQTT broker did not connect at {args.mqtt_host}:{args.mqtt_port}")

    print(f"SAFE MODE: Node 2 irrigation remains HOLD; publishing synthetic sensor-only recovery on {TOPIC}.", flush=True)
    metric_points: list[list[float]] = []
    try:
        for index, soil_humidity in enumerate(RECOVERY_VALUES[:args.count], start=1):
            now = utc_timestamp()
            metric_points.append([datetime.fromisoformat(now.replace("Z", "+00:00")).timestamp(), soil_humidity])
            payload = {
                "device_name": "Sensor",
                "farm_key": FARM_KEY,
                "timestamp": now,
                "demo_phase": "node2_safe_mode_recovery",
                "synthetic": True,
                "id6": {
                    "node2": {
                        "at": 30.1,
                        "ah": 82.0,
                        "st": 26.5,
                        "sh": soil_humidity,
                        "sec": 1.2,
                        "timestamp": now,
                    }
                },
            }
            result = client.publish(TOPIC, json.dumps(payload), qos=1)
            result.wait_for_publish(timeout=5)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"MQTT publish failed for sample {index}: rc={result.rc}")
            print(f"sample={index}/{args.count}; Node2 soil_humidity={soil_humidity}% (synthetic recovery)", flush=True)
            if index < args.count and args.interval:
                time.sleep(args.interval)
    finally:
        client.loop_stop()
        client.disconnect()

    api_key = os.getenv("DD_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DD_API_KEY is missing; MQTT samples were sent, but Datadog recovery metrics were not.")
    site = os.getenv("DD_SITE", "datadoghq.com").strip()
    endpoint = f"https://api.{site}/api/v1/series"
    metric_payload = {
        "series": [{
            "metric": "smiot.telemetry.soil_humidity",
            "type": "gauge",
            "points": metric_points,
            "tags": ["farm:greenhouse_a", "node:2", "source:synthetic_safe_mode_recovery"],
        }]
    }
    request = Request(
        endpoint,
        data=json.dumps(metric_payload).encode("utf-8"),
        headers={"DD-API-KEY": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            if response.status not in (200, 202):
                raise RuntimeError(f"Datadog rejected recovery metrics: HTTP {response.status}")
            print(f"Datadog accepted {args.count} recovery metric points (source:synthetic_safe_mode_recovery).", flush=True)
    except HTTPError as exc:
        raise RuntimeError(f"Datadog rejected recovery metrics: HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not submit recovery metrics to Datadog: {exc.reason}") from exc

    print("Recovery samples sent. This is synthetic evidence only; it does not confirm a physical probe recovered.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
