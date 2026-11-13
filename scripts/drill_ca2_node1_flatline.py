"""CA2 drill helper: START_SCENARIO for the greenhouse_j node1 soil flatline.

Importing this module publishes nothing. Sending happens only when
send_start_scenario() is called explicitly.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from uuid import uuid4

DRILL_FARM_KEY = "greenhouse_j"
DRILL_NODE_ID = 1
DRILL_SEED = 17
DRILL_SCENARIO_TYPES = ("soil_flatline", "S1")
CONTROL_TOPIC = "farm/demo/control"
# Defaults mirror MQTT_BROKER / MQTT_PORT in service/mqtt.py.
DEFAULT_MQTT_BROKER = "localhost"
DEFAULT_MQTT_PORT = 1883


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def build_start_scenario_payload(scenario_type: str = "soil_flatline",
                                 scenario_run_id: str | None = None,
                                 command_id: str | None = None) -> dict:
    """Return the START_SCENARIO command for greenhouse_j node1 (no network I/O)."""
    if scenario_type not in DRILL_SCENARIO_TYPES:
        raise ValueError(f"scenario_type must be one of {DRILL_SCENARIO_TYPES}")
    return {
        "action": "START_SCENARIO",
        "scenario_type": scenario_type,
        "farm_key": DRILL_FARM_KEY,
        "node_id": DRILL_NODE_ID,
        "scenario_run_id": scenario_run_id or str(uuid4()),
        "command_id": command_id or str(uuid4()),
        "seed": DRILL_SEED,
        "synthetic": True,
        "timestamp": _utc_timestamp(),
    }


def send_start_scenario(payload: dict, broker: str | None = None, port: int | None = None,
                        timeout_seconds: float = 5.0) -> bool:
    """Publish one payload to farm/demo/control with paho-mqtt (explicit call only).

    Broker host and port come from the MQTT_BROKER / MQTT_PORT environment
    variables, falling back to the service/mqtt.py defaults. They are not printed.
    """
    import paho.mqtt.client as mqtt

    if payload.get("action") != "START_SCENARIO" or payload.get("farm_key") != DRILL_FARM_KEY:
        raise ValueError("payload is not a greenhouse_j START_SCENARIO command")
    host = broker or os.getenv("MQTT_BROKER") or DEFAULT_MQTT_BROKER
    resolved_port = int(port or os.getenv("MQTT_PORT") or DEFAULT_MQTT_PORT)
    client_id = f"smiot-drill-ca2-{uuid4().hex[:8]}"
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    except AttributeError:
        client = mqtt.Client(client_id=client_id)
    client.connect(host, resolved_port, keepalive=30)
    client.loop_start()
    try:
        info = client.publish(CONTROL_TOPIC, json.dumps(payload, separators=(",", ":")), qos=1)
        info.wait_for_publish(timeout=timeout_seconds)
        return info.rc == mqtt.MQTT_ERR_SUCCESS and info.is_published()
    finally:
        client.loop_stop()
        client.disconnect()
