"""Verify recovered synthetic telemetry, then clear the virtual PLC HOLD latch."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
import requests
from dotenv import load_dotenv
from pymongo import MongoClient, DESCENDING


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)
DD_SITE = os.getenv("DD_SITE", "datadoghq.com").strip().removeprefix("https://").removesuffix("/")
DD_BASE_URL = f"https://api.{DD_SITE}"
DD_HEADERS = {
    "DD-API-KEY": os.getenv("DD_API_KEY", "").strip(),
    "DD-APPLICATION-KEY": os.getenv("DD_APP_KEY", "").strip(),
}


def main() -> int:
    monitor_id = os.getenv("DD_MONITOR_ID", "").strip()
    if not monitor_id or not DD_HEADERS["DD-API-KEY"] or not DD_HEADERS["DD-APPLICATION-KEY"]:
        raise RuntimeError("DD_MONITOR_ID, DD_API_KEY, and DD_APP_KEY are required")

    monitor = requests.get(
        f"{DD_BASE_URL}/api/v1/monitor/{monitor_id}",
        headers=DD_HEADERS,
        params={"group_states": "all"},
        timeout=20,
    )
    monitor.raise_for_status()
    monitor_data = monitor.json()
    monitor_state = str(monitor_data.get("overall_state", "UNKNOWN")).upper()
    if monitor_state != "OK":
        raise RuntimeError(f"Refusing to clear HOLD: Datadog monitor is {monitor_state}, not OK")
    groups = (monitor_data.get("state") or {}).get("groups") or {}
    last_triggered_ts = max(
        (int(group.get("last_triggered_ts", 0)) for group in groups.values()),
        default=0,
    )
    if not last_triggered_ts:
        raise RuntimeError("Refusing to clear HOLD: Datadog did not provide a monitor trigger timestamp")
    monitor_triggered_at = datetime.fromtimestamp(last_triggered_ts, tz=timezone.utc)

    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        raise RuntimeError("MONGODB_URI is required")
    database = os.getenv("MONGODB_DATABASE", "smiot")
    collection_name = os.getenv("MONGODB_TELEMETRY_COLLECTION", "telemetry")
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[database]
    telemetry = db[collection_name]
    ledger = db["action_ledger"]
    now = datetime.now(timezone.utc)
    hold = ledger.find_one(
        {
            "action": "HOLD",
            "source": "datadog_safe_mode_workflow",
            "state": "acknowledged",
            "monitor_id": monitor_id,
            "acknowledged_at": {"$gte": monitor_triggered_at},
        },
        sort=[("acknowledged_at", DESCENDING)],
    )
    if not hold:
        client.close()
        raise RuntimeError("Refusing to clear HOLD: MongoDB has no acknowledged Datadog HOLD for the current monitor incident")
    incident_id = str(hold.get("incident_id") or "")
    if not incident_id or incident_id.startswith("UNMATCHED-"):
        client.close()
        raise RuntimeError("Refusing to clear HOLD: action has no canonical incident_id")
    hold_ack_at = hold.get("acknowledged_at")
    if hold_ack_at and hold_ack_at.tzinfo is None:
        hold_ack_at = hold_ack_at.replace(tzinfo=timezone.utc)

    # A retry after a completed recovery must stay idempotent even when the
    # original recovery samples have rolled out of the five-minute window.
    previous_clear = ledger.find_one(
        {
            "action": "CLEAR",
            "incident_id": incident_id,
            "source": "datadog_safe_mode_recovery_verifier",
            "state": "verified",
        },
        {"command_id": 1, "verification": 1},
    )
    if previous_clear:
        client.close()
        print(json.dumps({
            "result": "already_verified_and_cleared",
            "command_id": previous_clear.get("command_id"),
            "incident_id": incident_id,
            "monitor_state": monitor_state,
            "virtual_pump_outputs_off": True,
            "simulated": True,
        }, ensure_ascii=False))
        return 0

    sample_start = max(now - timedelta(minutes=5), hold_ack_at or monitor_triggered_at)
    recent = list(telemetry.find(
        {
            "meta.farm_key": "greenhouse_a",
            "meta.measurement_type": "node",
            "meta.node_id": 2,
            "source.source": "smiot_demo_stream",
            "source.demo_seed_version": {"$exists": False},
            "source.incident_id": incident_id,
            "timestamp": {"$gte": sample_start, "$lte": now},
            "readings.soil_hum": {"$type": "number", "$ne": 2.4},
        },
        {"timestamp": 1, "readings.soil_hum": 1, "source.message_id": 1, "source.sequence": 1},
    ).sort("timestamp", DESCENDING).limit(20))
    if len(recent) < 6:
        client.close()
        raise RuntimeError(f"Refusing to clear HOLD: only {len(recent)} fresh normal Node 2 samples tied to incident {incident_id}; need at least 6")
    values = [float(row["readings"]["soil_hum"]) for row in recent]
    newest = max(row["timestamp"] for row in recent)
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)
    freshness_seconds = (now - newest).total_seconds()
    if freshness_seconds > 90 or max(values) - min(values) < 0.5:
        client.close()
        raise RuntimeError(
            f"Refusing to clear HOLD: sample freshness={freshness_seconds:.1f}s, "
            f"soil humidity range={max(values)-min(values):.2f}; expected fresh, varying readings"
        )

    broker_host = os.getenv("MQTT_HOST", "127.0.0.1")
    broker_port = int(os.getenv("MQTT_PORT", "1883"))
    command_id = uuid.uuid4().hex
    command = {
        "command_id": command_id,
        "action": "CLEAR",
        "reason": "Datadog monitor OK and six or more fresh, varying Node 2 MongoDB samples verified",
        "source": "datadog_safe_mode_recovery_verifier",
        "workflow_id": hold.get("workflow_id"),
        "execution_id": hold.get("execution_id"),
        "incident_id": incident_id,
        "monitor_id": monitor_id,
        "target": "smiot_virtual_plc",
        "farm_key": "greenhouse_a",
        "node_id": 2,
        "synthetic": True,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    acknowledged = threading.Event()
    ack_data: dict = {}

    def on_connect(mqtt_client, userdata, flags, reason_code, properties=None):
        if getattr(reason_code, "value", reason_code) == 0:
            mqtt_client.subscribe("farm/command/ack", qos=1)

    def on_message(mqtt_client, userdata, message):
        if message.topic != "farm/command/ack":
            return
        try:
            body = json.loads(message.payload.decode("utf-8"))
            if body.get("command_id") == command_id:
                ack_data.update(body)
                acknowledged.set()
        except (UnicodeDecodeError, json.JSONDecodeError):
            return

    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"smiot-recovery-verifier-{command_id[:10]}")
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    try:
        mqtt_client.connect(broker_host, broker_port, keepalive=30)
        mqtt_client.loop_start()
        deadline = time.monotonic() + 8
        while not mqtt_client.is_connected() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not mqtt_client.is_connected():
            raise RuntimeError("Could not connect to the local MQTT broker")
        time.sleep(0.3)
        request = {**command, "ledger_state": "requested"}
        mqtt_client.publish("farm/command/event", json.dumps(request, separators=(",", ":")), qos=1).wait_for_publish(5)
        control = {**command, **{f"bit{i}": 0 for i in range(8)}}
        info = mqtt_client.publish("farm/control", json.dumps(control, separators=(",", ":")), qos=1)
        info.wait_for_publish(timeout=5)
        if not info.is_published():
            raise RuntimeError("MQTT did not confirm the virtual PLC CLEAR command")
        mqtt_client.publish("farm/command/event", json.dumps({**command, "ledger_state": "published"}, separators=(",", ":")), qos=1).wait_for_publish(5)
        if not acknowledged.wait(8):
            raise RuntimeError("The virtual PLC did not acknowledge CLEAR")
        outputs = ack_data.get("virtual_output", {})
        if ack_data.get("safe_mode_active") is not False or any(int(value) != 0 for value in outputs.values()):
            raise RuntimeError("PLC ACK did not confirm safe mode cleared with all simulated pump outputs OFF")

        verification = {
            "incident_id": incident_id,
            "monitor_state": monitor_state,
            "sample_count": len(recent),
            "soil_humidity_range_pct": [min(values), max(values)],
            "newest_sample_at": newest.isoformat(),
            "sample_message_ids": [row.get("source", {}).get("message_id") for row in recent if row.get("source", {}).get("message_id")],
            "sample_freshness_seconds": round(freshness_seconds, 1),
            "virtual_pump_outputs_off": True,
        }
        mqtt_client.publish("farm/command/event", json.dumps({
            **command,
            "ledger_state": "verified",
            "verification": verification,
        }, separators=(",", ":")), qos=1).wait_for_publish(5)
        print(json.dumps({
            "result": "verified_and_cleared",
            "command_id": command_id,
            "prior_hold_command_id": hold.get("command_id"),
            "monitor_state": monitor_state,
            "fresh_normal_samples": len(recent),
            "soil_humidity_range_pct": [round(min(values), 2), round(max(values), 2)],
            "incident_id": incident_id,
            "virtual_pump_outputs": outputs,
            "simulated": True,
        }, ensure_ascii=False))
        return 0
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
