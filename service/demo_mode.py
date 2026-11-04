"""Idempotent demo history seeding and safe, continuous synthetic MQTT telemetry."""

from __future__ import annotations

import json
import logging
import math
import os
import random
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import paho.mqtt.client as mqtt
from pymongo import ReplaceOne, UpdateOne

from service.mongodb_store import collection

LOGGER = logging.getLogger("smiot.demo")
# v1 was incorrectly flatlined for every historical hour. Keep those immutable
# time-series measurements for audit, but seed and serve the coherent v2 story.
SEED_VERSION = "smiot-demo-history-v2"
LEGACY_BAD_SEED_VERSION = "smiot-demo-history-v1"
# Fixed six-hour incident window makes the historical narrative stable across restarts.
NODE2_INCIDENT_START = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
NODE2_INCIDENT_END = datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc)
FARMS = ("greenhouse_a", "greenhouse_b", "greenhouse_c", "greenhouse_d")
FARM_OFFSETS = {farm: index * 2.7 for index, farm in enumerate(FARMS)}
LOT_PREFIX = "melon-lot-local-demo-"
STAGES = ("sowing", "seedling", "vegetative", "flowering_fruiting", "harvest")
_started = False
_start_lock = threading.Lock()
_virtual_outputs = [0] * 8
_virtual_outputs_lock = threading.Lock()
_node2_flatline = False
_safe_mode_active = False
_active_demo_incident_id: str | None = None
_sample_sequence = 0
_publisher_boot_id = f"demo-{int(time.time())}"


def _enabled() -> bool:
    return os.getenv("SMIOT_DEMO_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}


def _seed_telemetry(days: int = 30) -> int:
    telemetry = collection("telemetry")
    existing = {
        row.get("source", {}).get("demo_seed_key")
        for row in telemetry.find(
            {"source.demo_seed_version": SEED_VERSION},
            {"source.demo_seed_key": 1},
        )
    }
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    pending: list[dict[str, Any]] = []

    for hour_offset in range(days * 24 - 1, -1, -1):
        timestamp = end - timedelta(hours=hour_offset)
        hour_index = int(timestamp.timestamp() // 3600)
        for farm_index, farm_key in enumerate(FARMS):
            offset = FARM_OFFSETS[farm_key]
            phase = hour_index / 8.0 + farm_index
            for node_id in (1, 2):
                node_phase = phase + node_id * 0.8
                is_node2_incident = (
                    farm_key == "greenhouse_a"
                    and node_id == 2
                    and NODE2_INCIDENT_START <= timestamp < NODE2_INCIDENT_END
                )
                soil_humidity = 2.4 if is_node2_incident else 42.0 + 7.0 * math.sin(node_phase / 3.0)
                readings = {
                    "air_temp": round(28.5 + offset + 2.2 * math.sin(node_phase / 5.0), 1),
                    "air_hum": round(73.0 + 7.0 * math.sin(node_phase / 6.0), 1),
                    "soil_temp": round(25.5 + offset * 0.25 + 1.4 * math.sin(node_phase / 4.0), 1),
                    "soil_hum": round(soil_humidity, 1),
                    "ec": round(1.2 + 0.12 * math.sin(node_phase / 7.0), 2),
                }
                key = f"{SEED_VERSION}:{farm_key}:node:{node_id}:{timestamp:%Y%m%d%H}"
                if key not in existing:
                    pending.append({
                        "timestamp": timestamp,
                        "meta": {"farm_key": farm_key, "source_table": "telemetry_node", "measurement_type": "node", "node_id": node_id},
                        "readings": readings,
                        "source": {
                            "table": "telemetry_node", "demo_seed_key": key,
                            "demo_seed_version": SEED_VERSION, "synthetic": True,
                            **({"incident_id": "greenhouse-a-node2-flatline-20261101"} if is_node2_incident else {}),
                        },
                    })

            water_key = f"{SEED_VERSION}:{farm_key}:water:{timestamp:%Y%m%d%H}"
            if water_key not in existing:
                pending.append({
                    "timestamp": timestamp,
                    "meta": {"farm_key": farm_key, "source_table": "telemetry_water", "measurement_type": "water"},
                    "readings": {"ph_val": round(6.4 + 0.45 * math.sin(phase / 6.0), 2), "ec_val": round(1.25 + 0.22 * math.sin(phase / 5.0), 2)},
                    "source": {"table": "telemetry_water", "demo_seed_key": water_key, "demo_seed_version": SEED_VERSION, "synthetic": True},
                })

            flow_key = f"{SEED_VERSION}:{farm_key}:flow:{timestamp:%Y%m%d%H}"
            if flow_key not in existing:
                base = 4.0 + 2.0 * abs(math.sin(phase / 2.0))
                pending.append({
                    "timestamp": timestamp,
                    "meta": {"farm_key": farm_key, "source_table": "telemetry_flow", "measurement_type": "flow"},
                    "readings": {"flow_f1": round(base, 2), "flow_f2": round(base * 0.82, 2), "flow_t1": round(base * 60, 2), "flow_t2": round(base * 110, 2)},
                    "source": {"table": "telemetry_flow", "demo_seed_key": flow_key, "demo_seed_version": SEED_VERSION, "synthetic": True},
                })

    for start in range(0, len(pending), 1000):
        telemetry.insert_many(pending[start:start + 1000], ordered=False)
    return len(pending)


def _seed_schedules(days: int = 30) -> int:
    schedules = collection("schedules")
    logs = collection("schedule_logs")
    now = datetime.now()
    schedule_ops = []
    log_ops = []
    for farm_index, farm_key in enumerate(FARMS):
        for day_ago in range(days):
            for slot in range(3):
                # All demo runs are already completed. No pending/running record can start a pump.
                event_time = now - timedelta(days=day_ago, hours=(2 - slot) * 4 + 1, minutes=(farm_index * 7 + slot * 11) % 60)
                schedule_id = 9_100_000 + farm_index * 100_000 + day_ago * 10 + slot
                log_id = 9_500_000 + farm_index * 100_000 + day_ago * 10 + slot
                duration = 8 + ((day_ago + slot + farm_index) % 9)
                actual_water = round(duration * (3.1 + farm_index * 0.12) + ((slot + day_ago) % 4) * 0.7, 1)
                stamp = event_time.strftime("%Y-%m-%d %H:%M:%S")
                end_at = (event_time + timedelta(minutes=duration)).strftime("%Y-%m-%d %H:%M:%S")
                schedule_doc = {
                    "_id": schedule_id, "id": schedule_id, "farm_key": farm_key,
                    "schedule_date": event_time.strftime("%Y-%m-%d"), "start_time": event_time.strftime("%H:%M"),
                    "water_amount": duration, "status": "completed", "created_at": stamp,
                    "source": "demo_seed", "demo_seed_version": SEED_VERSION,
                }
                log_doc = {
                    "_id": log_id, "id": log_id, "schedule_id": schedule_id, "farm_key": farm_key,
                    "start_at": stamp, "end_at": end_at, "target_water": duration,
                    "actual_water": actual_water, "status": "completed",
                    "source": "demo_seed", "demo_seed_version": SEED_VERSION,
                }
                schedule_ops.append(ReplaceOne({"_id": schedule_id}, schedule_doc, upsert=True))
                log_ops.append(ReplaceOne({"_id": log_id}, log_doc, upsert=True))
    if schedule_ops:
        schedules.bulk_write(schedule_ops, ordered=False)
    if log_ops:
        logs.bulk_write(log_ops, ordered=False)
    return len(schedule_ops)


def _seed_notifications() -> int:
    notifications = collection("notifications")
    now = datetime.now(timezone.utc)
    rows = [
        ("SMIOT demo: cảm biến greenhouse_a đang phát dữ liệu tổng hợp.", "system", "info"),
        ("SMIOT demo: Node 2 greenhouse_a giữ độ ẩm đất 2,4% để minh họa cảnh báo flatline.", "sensor", "warning"),
        ("SMIOT demo: nhật ký tưới lịch sử đã được seed; không gửi lệnh tới máy bơm.", "schedule", "info"),
        ("SMIOT demo: PLC và biến tần đang ở trạng thái ảo, tất cả đầu ra đều tắt.", "plc", "info"),
    ]
    for index, (message, category, severity) in enumerate(rows, start=1):
        created_at = now - timedelta(minutes=index * 4)
        doc = {
            "_id": 9_900_000 + index, "id": 9_900_000 + index,
            "message": message, "category": category, "severity": severity,
            "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "source": "demo_seed", "demo_seed_version": SEED_VERSION,
        }
        notifications.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    return len(rows)


def _seed_traceability(lots: int = 10, days: int = 15) -> int:
    """Do not invent daily image events; stage records come from the harvest seed."""
    return 0


def seed_demo_history() -> dict[str, int]:
    """Fill gaps in a fixed synthetic dataset; reruns update only demo-owned IDs."""
    telemetry_count = _seed_telemetry()
    schedule_count = _seed_schedules()
    notification_count = _seed_notifications()
    traceability_count = _seed_traceability()
    try:
        from pages.home import state

        state["notifications"] = [
            {"text": row.get("message", ""), "time": str(row.get("created_at", ""))[-8:], "read": False}
            for row in collection("notifications").find({}).sort("created_at", -1).limit(20)
        ]
    except Exception:
        LOGGER.debug("Could not hydrate notification bell from MongoDB", exc_info=True)
    return {
        "telemetry_documents_inserted": telemetry_count,
        "schedule_records_seeded": schedule_count,
        "notifications_seeded": notification_count,
        "traceability_events_seeded": traceability_count,
    }


def _mqtt_client() -> mqtt.Client:
    client_id = f"smiot-demo-stream-{os.getpid()}"
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    except AttributeError:
        return mqtt.Client(client_id=client_id)


def _virtual_plc_payload() -> dict[str, Any]:
    """Snapshot the cloud-hosted virtual PLC outputs for the app UI."""
    with _virtual_outputs_lock:
        outputs = list(_virtual_outputs)
        safe_mode_active = _safe_mode_active
    payload: dict[str, Any] = {
        "device_name": "SMIOT Virtual PLC",
        "device_id": "smiot-virtual-plc-ec2",
        "source": "smiot_demo_stream",
        "simulated": True,
        "online": 1,
        "safe_mode_active": safe_mode_active,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    for index, value in enumerate(outputs):
        payload[f"q{index}"] = value
        payload[f"bit{index}"] = value
    return payload


def _on_virtual_control(client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
    """Apply virtual PLC controls, safe-mode actions, and sensor fault injection."""
    try:
        command = json.loads(message.payload.decode("utf-8"))
        if not isinstance(command, dict):
            return
        global _node2_flatline, _safe_mode_active, _active_demo_incident_id
        changed: list[str] = []
        fault_mode = command.get("demo_node2_fault")
        if fault_mode in ("normal", "flatline"):
            incident_id = command.get("incident_id")
            with _virtual_outputs_lock:
                _node2_flatline = fault_mode == "flatline"
                applied_mode = _node2_flatline
            if applied_mode and not incident_id:
                from service.incident_lifecycle import start_flatline_incident
                incident_id = start_flatline_incident()
            if applied_mode and incident_id:
                _active_demo_incident_id = str(incident_id)
            if incident_id:
                from service.incident_lifecycle import set_simulator_mode
                set_simulator_mode("flatline" if applied_mode else "normal", str(incident_id))
            LOGGER.warning(
                "Demo sensor mode changed: greenhouse_a node2 soil_humidity=%s",
                "2.4%% flatline" if applied_mode else "variable normal readings",
            )
            ack = {
                "device_name": "SMIOT Synthetic Demo",
                "farm_key": "greenhouse_a",
                "node": 2,
                "demo_node2_fault": "flatline" if applied_mode else "normal",
                "soil_humidity": 2.4 if applied_mode else None,
                "incident_id": _active_demo_incident_id,
                "mode_applied": True,
                "source": "smiot_demo_stream",
                "simulated": True,
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            }
            client.publish("farm/demo/status", json.dumps(ack, separators=(",", ":")), qos=1)
        action = command.get("action")
        command_id = str(command.get("command_id", ""))[:200]
        rejected_on_command = False
        with _virtual_outputs_lock:
            if action == "HOLD":
                _safe_mode_active = True
                for index, current in enumerate(_virtual_outputs):
                    if current:
                        changed.append(f"bit{index}")
                    _virtual_outputs[index] = 0
            elif action == "CLEAR":
                # Recovery clears the latch but never turns a pump on.
                _safe_mode_active = False
            for index in range(8):
                key = f"bit{index}"
                value = command.get(key)
                if value in (0, 1, False, True, "0", "1"):
                    requested = int(value in (1, True, "1"))
                    if _safe_mode_active and requested:
                        rejected_on_command = True
                        continue
                    _virtual_outputs[index] = requested
                    changed.append(key)
        is_safe_mode_action = action in {"HOLD", "CLEAR"} and bool(command_id)
        if not changed and not is_safe_mode_action and not rejected_on_command:
            return

        response = _virtual_plc_payload()
        if is_safe_mode_action:
            response.update({
                "command_id": command_id,
                "action": action,
                "execution_id": command.get("execution_id"),
                "incident_id": command.get("incident_id"),
            })
        if rejected_on_command:
            response["command_rejected"] = "safe_mode_active"
        info = client.publish("farm/status", json.dumps(response, separators=(",", ":")), qos=1)
        # This callback runs on Paho's network-loop thread. Waiting for the
        # publish here would prevent that same thread from sending the ACK.
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"virtual PLC status publish failed: rc={info.rc}")
        LOGGER.info(
            "Virtual PLC applied command and returned feedback: fields=%s outputs_on=%s safe_mode=%s rejected_on=%s",
            ",".join(changed), sum(response[f"bit{i}"] for i in range(8)),
            response.get("safe_mode_active"), rejected_on_command,
        )
        if is_safe_mode_action:
            ack = {
                "command_id": command_id,
                "action": action,
                "farm_key": command.get("farm_key", "greenhouse_a"),
                "node_id": command.get("node_id", 2),
                "monitor_id": command.get("monitor_id"),
                "workflow_id": command.get("workflow_id"),
                "execution_id": command.get("execution_id"),
                "incident_id": command.get("incident_id"),
                "reason": command.get("reason", ""),
                "source": command.get("source", "unknown"),
                "target": "smiot_virtual_plc",
                "synthetic": True,
                "virtual_output": {f"bit{i}": response[f"bit{i}"] for i in range(8)},
                "safe_mode_active": response["safe_mode_active"],
                "timestamp": response["timestamp"],
            }
            ack_info = client.publish("farm/command/ack", json.dumps(ack, separators=(",", ":")), qos=1)
            if ack_info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"safe-mode ACK publish failed: rc={ack_info.rc}")
            if action == "CLEAR" and command.get("incident_id") == _active_demo_incident_id:
                _active_demo_incident_id = None
    except Exception as exc:
        LOGGER.warning("Virtual PLC rejected control message: %s", type(exc).__name__)


def _on_virtual_connect(client: mqtt.Client, userdata: Any, flags: Any,
                        reason_code: Any = None, properties: Any = None) -> None:
    if reason_code not in (None, 0):
        LOGGER.warning("Virtual PLC MQTT connection failed: %s", reason_code)
        return
    client.subscribe([("farm/control", 1), ("farm/demo/control", 1)])
    LOGGER.info("Virtual devices online; subscribed to farm/control and farm/demo/control")


def _farm_sensor_payload(farm_key: str, rng: random.Random, total: dict[str, float]) -> dict[str, Any]:
    global _sample_sequence
    farm_index = FARMS.index(farm_key)
    offset = FARM_OFFSETS[farm_key]
    node1 = {
        "at": round(29.2 + offset + rng.uniform(-0.5, 0.5), 1),
        "ah": round(76 + rng.uniform(-2.0, 2.0), 1),
        "st": round(26.5 + offset * 0.2 + rng.uniform(-0.4, 0.4), 1),
        "sh": round(42 + rng.uniform(-1.5, 1.5), 1),
        "sec": round(1.3 + rng.uniform(-0.07, 0.07), 2),
    }
    with _virtual_outputs_lock:
        node2_flatline = _node2_flatline
    node2 = {
        "at": round(29.7 + offset + rng.uniform(-0.5, 0.5), 1),
        "ah": round(79 + rng.uniform(-2.0, 2.0), 1),
        "st": round(26.2 + offset * 0.2 + rng.uniform(-0.4, 0.4), 1),
        "sh": (
            2.4 if farm_key == "greenhouse_a" and node2_flatline
            else round(40 + rng.uniform(-1.4, 1.4), 1)
        ),
        "sec": round(1.2 + rng.uniform(-0.07, 0.07), 2),
    }
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    with _virtual_outputs_lock:
        _sample_sequence += 1
        sample_sequence = _sample_sequence
        incident_id = _active_demo_incident_id
    for node in (node1, node2):
        node["timestamp"] = timestamp
    flow1 = round(4.5 + rng.uniform(-0.7, 0.7), 2)
    flow2 = round(3.4 + rng.uniform(-0.5, 0.5), 2)
    total[farm_key] = total.get(farm_key, 0.0) + flow2 / 360.0
    payload = {
        "device_name": "SMIOT Synthetic Demo", "farm_key": farm_key,
        "timestamp": timestamp, "source": "smiot_demo_stream",
        "device_id": f"smiot-virtual-{farm_key}", "boot_id": _publisher_boot_id,
        "sample_sequence": sample_sequence, "synthetic": True,
        "id6": {"node1": node1, "node2": node2},
        "id3": {"f1": flow1, "f2": flow2, "t1": round(total[farm_key] * 1.15, 2), "t2": round(total[farm_key], 2), "timestamp": timestamp},
        "id4": {"ec": round(1.35 + farm_index * 0.08 + rng.uniform(-0.08, 0.08), 2), "v": 2.5, "raw": rng.randint(1800, 2300), "online": 1, "timestamp": timestamp},
        "id5": {"ph": round(6.7 + rng.uniform(-0.25, 0.25), 2), "mv": round(130 + rng.uniform(-12, 12), 1), "raw": rng.randint(1700, 2200), "online": 1, "timestamp": timestamp},
    }
    if farm_key == "greenhouse_a" and incident_id:
        payload["incident_id"] = incident_id
        payload["lot_id"] = "melon-lot-local-demo-001"
    return payload


def _publish_loop() -> None:
    rng = random.Random()
    totals: dict[str, float] = {}
    interval = max(10, int(os.getenv("SMIOT_DEMO_INTERVAL_SECONDS", "30")))
    global _active_demo_incident_id, _node2_flatline
    try:
        from service.incident_lifecycle import get_active_incident
        active = get_active_incident()
        if active:
            _active_demo_incident_id = str(active["incident_id"])
            _node2_flatline = active.get("simulator_mode") == "flatline"
    except Exception:
        LOGGER.exception("Could not resume active incident context")
    while True:
        client = _mqtt_client()
        try:
            client.connect(os.getenv("MQTT_HOST", "localhost"), int(os.getenv("MQTT_PORT", "1883")), keepalive=60)
            client.on_connect = _on_virtual_connect
            client.on_message = _on_virtual_control
            client.loop_start()
            deadline = time.monotonic() + 10
            while not client.is_connected() and time.monotonic() < deadline:
                time.sleep(0.1)
            if not client.is_connected():
                raise RuntimeError("local MQTT broker did not connect")
            # Subscribe explicitly after the socket is connected as well as in
            # on_connect, so reconnects and Paho callback API variations cannot
            # leave the virtual device publishing telemetry but deaf to commands.
            result, _ = client.subscribe([("farm/control", 1), ("farm/demo/control", 1)])
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"virtual devices could not subscribe to control topics: rc={result}")
            LOGGER.info("Virtual devices subscribed to farm/control and farm/demo/control")
            LOGGER.info("Synthetic demo stream is publishing each %ss", interval)
            while True:
                for farm_key in FARMS:
                    payload = _farm_sensor_payload(farm_key, rng, totals)
                    info = client.publish("farm/sensor", json.dumps(payload, separators=(",", ":")), qos=1)
                    info.wait_for_publish(timeout=5)
                timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
                plc = _virtual_plc_payload()
                plc["timestamp"] = timestamp
                client.publish("farm/status", json.dumps(plc, separators=(",", ":")), qos=1)
                # The virtual output state is preserved between telemetry cycles.
                inverter = {"device_name": "Inverter", "online": 1, "status": 0, "bit": 0,
                            "hz": 0.0, "p_set": 0.0, "p_cur": 0.0, "v_in": 220.0,
                            "i_in": 0.0, "v_out": 0.0, "i_out": 0.0, "timestamp": timestamp}
                client.publish("farm/data", json.dumps(inverter, separators=(",", ":")), qos=1)
                time.sleep(interval)
        except Exception as exc:
            LOGGER.warning("Synthetic demo stream cannot reach local MQTT; retrying in 5s: %s", exc)
            try:
                client.loop_stop()
                client.disconnect()
            except Exception:
                pass
            time.sleep(5)


def start_demo_mode() -> None:
    """Seed demo history and run a continuous bidirectional virtual-IoT MQTT loop."""
    global _started
    if not _enabled():
        LOGGER.info("Synthetic demo mode is disabled")
        return
    with _start_lock:
        if _started:
            return
        _started = True
    try:
        counts = seed_demo_history()
        LOGGER.info("Synthetic demo history ready: %s", counts)
    except Exception:
        LOGGER.exception("Could not seed full demo history; starting the application anyway")
    thread = threading.Thread(target=_publish_loop, name="smiot-demo-stream", daemon=True)
    thread.start()

