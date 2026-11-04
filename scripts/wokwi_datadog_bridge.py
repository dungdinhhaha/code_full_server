"""Bridge Wokwi telemetry/stage events into SMIOT and mirror safe-mode results.

Demo-only transport: HiveMQ's public MQTT broker is unauthenticated. Never send
credentials or private farm data through it. Use an authenticated TLS broker for
anything beyond this synthetic demonstration.
"""

from __future__ import annotations

import json
import hashlib
import math
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=False)

CHANNEL = os.getenv("WOKWI_CHANNEL", "greenhouse-a-7f38c2d1").strip()
PUBLIC_MQTT_HOST = os.getenv("WOKWI_MQTT_HOST", "broker.hivemq.com").strip()
PUBLIC_MQTT_PORT = int(os.getenv("WOKWI_MQTT_PORT", "1883"))
LOCAL_MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1").strip()
LOCAL_MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
TELEMETRY_TOPIC = f"smiot/wokwi/{CHANNEL}/telemetry"
TRACEABILITY_TOPIC = f"smiot/wokwi/{CHANNEL}/traceability"
COMMAND_TOPIC = f"smiot/wokwi/{CHANNEL}/command"
COMMAND_ACK_TOPIC = f"smiot/wokwi/{CHANNEL}/command/ack"
TRACEABILITY_IMAGE_PATH = PROJECT_ROOT / "static" / "device_images" / "smiot_melon_growth_contact_sheet.jpg"
MONITOR_ID = os.getenv("DD_MONITOR_ID", "").strip()
WORKFLOW_ID = os.getenv("DD_WORKFLOW_ID", "").strip()
POLL_SECONDS = 10

DD_API_KEY = os.getenv("DD_API_KEY", "").strip()
DD_APP_KEY = os.getenv("DD_APP_KEY", "").strip()
DD_SITE = os.getenv("DD_SITE", "datadoghq.com").strip().removeprefix("https://").removesuffix("/")
DD_BASE_URL = f"https://api.{DD_SITE}"
DD_HEADERS = {
    "DD-API-KEY": DD_API_KEY,
    "DD-APPLICATION-KEY": DD_APP_KEY,
}

local_mqtt: mqtt.Client | None = None
cloud_mqtt: mqtt.Client | None = None
hold_active = False
_mongo_client = None
_pending_commands: dict[str, tuple[threading.Event, dict]] = {}
_pending_commands_lock = threading.Lock()
_verified_clear_commands: set[str] = set()


def create_mqtt_client(client_id: str) -> mqtt.Client:
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    except AttributeError:
        return mqtt.Client(client_id=client_id)


def on_local_connect(client, userdata, flags, reason_code, properties=None):
    code = getattr(reason_code, "value", reason_code)
    if code == 0:
        client.subscribe("farm/command/ack", qos=1)
        client.subscribe("farm/command/event", qos=1)


def _publish_wokwi_visual(command: dict, action: str, reason: str) -> bool:
    """Mirror an already verified app action to the optional Wokwi LED only."""
    if cloud_mqtt is None or not cloud_mqtt.is_connected():
        return False
    command_id = str(command.get("command_id") or "")
    wokwi_command = {
        **command,
        "command_id": hashlib.sha256(f"wokwi|{command_id}|{action}".encode("utf-8")).hexdigest()[:32],
        "action": action,
        "reason": reason,
        "target": "wokwi_virtual_led",
        "safe_mode_active": action == "HOLD",
        **{f"bit{i}": 0 for i in range(8)},
    }
    info = cloud_mqtt.publish(COMMAND_TOPIC, json.dumps(wokwi_command, separators=(",", ":")), qos=1, retain=True)
    info.wait_for_publish(timeout=5)
    return info.is_published()


def on_local_message(client, userdata, message):
    try:
        payload = json.loads(message.payload.decode("utf-8"))
        if message.topic == "farm/command/ack":
            command_id = str(payload.get("command_id", ""))
            with _pending_commands_lock:
                pending = _pending_commands.get(command_id)
            if pending:
                event, result = pending
                result.update(payload)
                event.set()
            return

        if message.topic != "farm/command/event":
            return
        if (
            payload.get("action") != "CLEAR"
            or payload.get("source") != "datadog_safe_mode_recovery_verifier"
            or payload.get("ledger_state") != "verified"
            or payload.get("monitor_id") != MONITOR_ID
            or payload.get("farm_key") != "greenhouse_a"
            or int(payload.get("node_id", 0)) != 2
        ):
            return

        verification = payload.get("verification") or {}
        humidity_range = verification.get("soil_humidity_range_pct") or []
        try:
            humidity_range = [float(value) for value in humidity_range]
            has_varying_samples = len(humidity_range) == 2 and humidity_range[1] - humidity_range[0] >= 0.5
            enough_fresh_samples = (
                int(verification.get("sample_count", 0)) >= 6
                and float(verification.get("sample_freshness_seconds", float("inf"))) <= 90
            )
        except (TypeError, ValueError):
            has_varying_samples = False
            enough_fresh_samples = False
        if not (
            verification.get("monitor_state") == "OK"
            and verification.get("virtual_pump_outputs_off") is True
            and has_varying_samples
            and enough_fresh_samples
        ):
            print("Rejected app CLEAR event: recovery evidence is incomplete", flush=True)
            return

        global hold_active
        command_id = str(payload.get("command_id", ""))
        if not command_id or command_id in _verified_clear_commands:
            return
        _verified_clear_commands.add(command_id)
        hold_active = False
        if _publish_wokwi_visual(payload, "CLEAR", "Application recovery verifier confirmed fresh, varying readings and virtual PLC ACK"):
            print(f"Application recovery verifier confirmed CLEAR; bridge latch released and Wokwi visual output cleared (command_id={command_id})", flush=True)
        else:
            print(f"Application recovery verifier confirmed CLEAR; bridge latch released, but Wokwi visual output is unavailable (command_id={command_id})", flush=True)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return


def validate_telemetry(payload: object) -> dict:
    if not isinstance(payload, dict) or payload.get("farm_key") != "greenhouse_a":
        raise ValueError("expected a JSON object for farm_key greenhouse_a")
    nodes = payload.get("id6")
    if not isinstance(nodes, dict):
        raise ValueError("missing id6 node readings")
    for node_name in ("node1", "node2"):
        node = nodes.get(node_name)
        if not isinstance(node, dict):
            raise ValueError(f"missing {node_name} readings")
        for key in ("at", "ah", "st", "sh", "sec"):
            value = float(node[key])
            if not math.isfinite(value):
                raise ValueError(f"{node_name}.{key} must be a finite number")
        if not 0 <= float(node["sh"]) <= 100:
            raise ValueError(f"{node_name}.sh must be between 0 and 100")
    payload["device_name"] = "Wokwi SMIOT Demo"
    payload["source"] = "wokwi_synthetic"
    payload["synthetic"] = True
    payload["bridge_received_at"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return payload


def on_cloud_connect(client, userdata, flags, reason_code, properties=None):
    code = getattr(reason_code, "value", reason_code)
    if code == 0:
        client.subscribe(TELEMETRY_TOPIC, qos=1)
        client.subscribe(TRACEABILITY_TOPIC, qos=1)
        client.subscribe(COMMAND_ACK_TOPIC, qos=1)
        print(f"Connected to public MQTT; listening on {TELEMETRY_TOPIC} and {TRACEABILITY_TOPIC}", flush=True)
    else:
        print(f"Public MQTT connection failed: {reason_code}", flush=True)


def on_telemetry(client, userdata, message):
    try:
        payload = validate_telemetry(json.loads(message.payload.decode("utf-8")))
        if local_mqtt is None or not local_mqtt.is_connected():
            raise RuntimeError("local SMIOT MQTT broker is disconnected")
        info = local_mqtt.publish("farm/sensor", json.dumps(payload, separators=(",", ":")), qos=1)
        info.wait_for_publish(timeout=5)
        if not info.is_published():
            raise RuntimeError("local MQTT relay did not confirm publish")
        print(
            f"Relayed Wokwi sample: Node1 soil={payload['id6']['node1']['sh']}%, "
            f"Node2 soil={payload['id6']['node2']['sh']}% -> farm/sensor",
            flush=True,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        print(f"Rejected/failed Wokwi telemetry: {exc}", flush=True)


def on_traceability(client, userdata, message):
    """Forward synthetic stage metadata; the app serves the image from its image store."""
    try:
        event = json.loads(message.payload.decode("utf-8"))
        if (
            not isinstance(event, dict)
            or event.get("event") != "daily_photo_capture_simulated"
            or event.get("simulated") is not True
            or event.get("farm_key") != "greenhouse_a"
            or event.get("image_asset_id") != "smiot_melon_growth_contact_sheet_v1"
        ):
            raise ValueError("unexpected or non-synthetic traceability event")
        day = int(event["simulated_day"])
        panel = int(event["image_panel"])
        if day < 1 or not 1 <= panel <= 5 or not isinstance(event.get("stage"), str):
            raise ValueError("invalid simulated day, stage, or image panel")
        if local_mqtt is None or not local_mqtt.is_connected():
            raise RuntimeError("local SMIOT MQTT broker is disconnected")
        if not TRACEABILITY_IMAGE_PATH.is_file():
            raise FileNotFoundError(f"image asset is missing: {TRACEABILITY_IMAGE_PATH}")

        metadata = {
            **event,
            "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "image_content_type": "image/jpeg",
        }
        event_info = local_mqtt.publish(
            "farm/traceability/event",
            json.dumps(metadata, separators=(",", ":")),
            qos=1,
            retain=False,
        )
        event_info.wait_for_publish(timeout=10)
        if not event_info.is_published():
            raise RuntimeError("local MQTT broker did not confirm traceability event publish")
        print(
            f"Relayed synthetic growth image: lot={event['lot_id']} day={day} "
            f"stage={event['stage']} panel={panel}; MongoDB receives image path metadata only",
            flush=True,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError, OSError, RuntimeError) as exc:
        print(f"Rejected/failed Wokwi traceability event: {exc}", flush=True)


def on_cloud_message(client, userdata, message):
    if message.topic == TRACEABILITY_TOPIC:
        on_traceability(client, userdata, message)
    elif message.topic == TELEMETRY_TOPIC:
        on_telemetry(client, userdata, message)
    elif message.topic == COMMAND_ACK_TOPIC:
        try:
            ack = json.loads(message.payload.decode("utf-8"))
            if ack.get("source") != "wokwi_synthetic" or ack.get("synthetic") is not True:
                raise ValueError("refusing an unlabelled or non-synthetic device ACK")
            if local_mqtt is None or not local_mqtt.is_connected():
                raise RuntimeError("local SMIOT MQTT broker is disconnected")
            info = local_mqtt.publish("farm/command/ack", json.dumps(ack, separators=(",", ":")), qos=1)
            info.wait_for_publish(timeout=5)
            if not info.is_published():
                raise RuntimeError("local broker did not accept the device ACK")
            print(f"Virtual device ACK recorded: command_id={ack.get('command_id')} output={ack.get('virtual_output')}", flush=True)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, RuntimeError) as exc:
            print(f"Rejected/failed virtual device ACK: {exc}", flush=True)


def publish_command(action: str, reason: str, execution_id: str | None = None) -> None:
    if local_mqtt is None or not local_mqtt.is_connected():
        print(f"Cannot publish virtual PLC safe-mode {action}: local MQTT is disconnected", flush=True)
        return
    incident_id = get_active_mongo_incident_id()
    if not incident_id:
        # Preserve fail-safe behavior, but explicitly leave the event unmatched;
        # never pretend a workflow execution UUID is the incident identity.
        incident_id = f"UNMATCHED-{MONITOR_ID}-{int(time.time())}"
        print("No open Mongo incident found; publishing fail-safe HOLD with no lot association", flush=True)
    else:
        try:
            from service.incident_lifecycle import attach_monitor_and_workflow
            attach_monitor_and_workflow(incident_id, monitor_id=MONITOR_ID,
                                        workflow_id=WORKFLOW_ID, execution_id=execution_id)
        except Exception as exc:
            print(f"Could not attach workflow metadata to Mongo incident: {type(exc).__name__}", flush=True)
    identity = f"{action}|{WORKFLOW_ID}|{incident_id}"
    command_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
    command = {
        "command_id": command_id,
        "action": action,
        "reason": reason,
        "source": "datadog_safe_mode_workflow",
        "workflow_id": WORKFLOW_ID,
        "execution_id": execution_id,
        "incident_id": incident_id,
        "monitor_id": MONITOR_ID,
        "target": "smiot_virtual_plc",
        "farm_key": "greenhouse_a",
        "node_id": 2,
        "synthetic": True,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    event = threading.Event()
    ack_result: dict = {}
    with _pending_commands_lock:
        _pending_commands[command_id] = (event, ack_result)
    request = {**command, "ledger_state": "requested"}
    req_info = local_mqtt.publish("farm/command/event", json.dumps(request, separators=(",", ":")), qos=1)
    req_info.wait_for_publish(timeout=5)
    control = {
        **command,
        **{f"bit{i}": 0 for i in range(8)},
    }
    info = local_mqtt.publish("farm/control", json.dumps(control, separators=(",", ":")), qos=1)
    info.wait_for_publish(timeout=5)
    if not info.is_published():
        failure = {**command, "ledger_state": "failed", "error": "local MQTT did not acknowledge the safe-mode command"}
        local_mqtt.publish("farm/command/event", json.dumps(failure, separators=(",", ":")), qos=1).wait_for_publish(timeout=5)
        print(f"Virtual PLC command {action} was not acknowledged by MQTT", flush=True)
        with _pending_commands_lock:
            _pending_commands.pop(command_id, None)
        return
    published = {**command, "ledger_state": "published"}
    local_mqtt.publish("farm/command/event", json.dumps(published, separators=(",", ":")), qos=1).wait_for_publish(timeout=5)
    if not event.wait(8):
        print(f"Virtual PLC command {action} published, but device ACK was not received (command_id={command_id})", flush=True)
    else:
        outputs = ack_result.get("virtual_output", {})
        print(
            f"Virtual PLC ACK: action={action}, safe_mode={ack_result.get('safe_mode_active')}, "
            f"outputs_on={sum(int(v) for v in outputs.values()) if isinstance(outputs, dict) else 'unknown'}, "
            f"command_id={command_id}", flush=True,
        )

    # Wokwi remains an optional visual endpoint. The in-app virtual PLC is the
    # authoritative actuator simulation and does not depend on an active Wokwi session.
    if _publish_wokwi_visual(command, action, reason):
        print(f"Wokwi visual command published: {action} ({execution_id or reason})", flush=True)
    with _pending_commands_lock:
        _pending_commands.pop(command_id, None)


def get_monitor_state() -> str:
    response = requests.get(
        f"{DD_BASE_URL}/api/v1/monitor/{MONITOR_ID}",
        headers=DD_HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    return str(response.json().get("overall_state", "UNKNOWN")).upper()


def get_monitor_incident_id() -> str:
    """Return a stable per-alert identity for fail-safe HOLDs before workflow completion."""
    response = requests.get(
        f"{DD_BASE_URL}/api/v1/monitor/{MONITOR_ID}",
        headers=DD_HEADERS,
        params={"group_states": "all"},
        timeout=20,
    )
    response.raise_for_status()
    groups = (response.json().get("state") or {}).get("groups") or {}
    triggered = [
        int(group.get("last_triggered_ts", 0))
        for group in groups.values()
        if int(group.get("last_triggered_ts", 0)) > 0
    ]
    if triggered:
        return f"{MONITOR_ID}-{max(triggered)}"
    # The alert workflow may arrive before Datadog exposes group state. Keep
    # the fallback unique by minute instead of reusing a prior incident key.
    return f"{MONITOR_ID}-{int(time.time() // 60)}"


def get_active_mongo_incident_id() -> str | None:
    """Use the publisher's persistent canonical ID, not a workflow-run ID."""
    global _mongo_client
    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        return None
    try:
        if _mongo_client is None:
            from pymongo import MongoClient
            _mongo_client = MongoClient(uri, appname="smiot-safe-mode-bridge", serverSelectionTimeoutMS=3000)
        db = _mongo_client[os.getenv("MONGODB_DATABASE", "smiot")]
        row = db["operational_incidents"].find_one(
            {"farm_key": "greenhouse_a", "node_id": 2, "kind": "soil_humidity_flatline",
             "status": {"$in": ["open", "holding", "recovering"]}},
            {"incident_id": 1}, sort=[("opened_at", -1)],
        )
        return str(row.get("incident_id") or row.get("_id")) if row else None
    except Exception as exc:
        print(f"Mongo incident lookup unavailable: {type(exc).__name__}", flush=True)
        return None


def recent_instances() -> list[dict]:
    if not WORKFLOW_ID:
        return []
    response = requests.get(
        f"{DD_BASE_URL}/api/v2/workflows/{WORKFLOW_ID}/instances",
        headers=DD_HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    return response.json().get("data", [])


def from_target_monitor(attributes: dict) -> bool:
    handle = (attributes.get("source") or {}).get("handle") or {}
    return str(handle.get("kind", "")).upper() == "MONITOR" and str(handle.get("id", "")) == MONITOR_ID


def status_name(attributes: dict) -> str:
    return str((attributes.get("instanceStatus") or {}).get("displayName", "")).lower()


def main() -> int:
    global local_mqtt, cloud_mqtt, hold_active

    if not CHANNEL or not DD_API_KEY or not DD_APP_KEY or not MONITOR_ID:
        raise RuntimeError("Set DD_API_KEY, DD_APP_KEY and DD_MONITOR_ID for the selected Datadog site")

    # Establish a baseline so old successful workflow runs are never replayed.
    existing_ids = {item.get("id") for item in recent_instances() if item.get("id")}
    initial_state = get_monitor_state()

    local_mqtt = create_mqtt_client(f"smiot-wokwi-local-{int(time.time())}")
    local_mqtt.on_connect = on_local_connect
    local_mqtt.on_message = on_local_message
    local_mqtt.connect(LOCAL_MQTT_HOST, LOCAL_MQTT_PORT, keepalive=60)
    local_mqtt.loop_start()

    cloud_mqtt = create_mqtt_client(f"smiot-wokwi-bridge-{int(time.time())}")
    cloud_mqtt.on_connect = on_cloud_connect
    cloud_mqtt.on_message = on_cloud_message
    cloud_mqtt.connect(PUBLIC_MQTT_HOST, PUBLIC_MQTT_PORT, keepalive=60)
    cloud_mqtt.loop_start()

    connection_deadline = time.monotonic() + 20
    while time.monotonic() < connection_deadline:
        if local_mqtt.is_connected() and cloud_mqtt.is_connected():
            break
        time.sleep(0.2)
    if not local_mqtt.is_connected() or not cloud_mqtt.is_connected():
        cloud_mqtt.loop_stop()
        local_mqtt.loop_stop()
        cloud_mqtt.disconnect()
        local_mqtt.disconnect()
        raise RuntimeError("Could not connect to both the local broker and the Wokwi public broker")

    print(f"Wokwi channel: {CHANNEL}", flush=True)
    print(f"Telemetry: {TELEMETRY_TOPIC}", flush=True)
    print(f"Virtual output: {COMMAND_TOPIC}", flush=True)
    print("This bridge relays synthetic sensor readings, generated JPEG stage assets, and virtual LED commands; no physical actuator commands.", flush=True)

    if initial_state == "ALERT":
        publish_command("HOLD", "monitor already Alert when bridge started")
        hold_active = True

    try:
        while True:
            try:
                state_now = get_monitor_state()
                for item in recent_instances():
                    instance_id = str(item.get("id", ""))
                    if not instance_id or instance_id in existing_ids:
                        continue
                    attrs = item.get("attributes", {})
                    if from_target_monitor(attrs):
                        current_status = status_name(attrs)
                        if current_status == "success":
                            if state_now == "ALERT":
                                if hold_active:
                                    incident_id = get_active_mongo_incident_id()
                                    if incident_id:
                                        try:
                                            from service.incident_lifecycle import attach_monitor_and_workflow, record_workflow_observation
                                            hold_command_id = hashlib.sha256(f"HOLD|{WORKFLOW_ID}|{incident_id}".encode("utf-8")).hexdigest()[:32]
                                            attach_monitor_and_workflow(incident_id, monitor_id=MONITOR_ID,
                                                                        workflow_id=WORKFLOW_ID, execution_id=instance_id)
                                            record_workflow_observation(
                                                incident_id, workflow_id=WORKFLOW_ID, execution_id=instance_id,
                                                status="success", disposition="hold_already_latched_duplicate_suppressed",
                                                command_id=hold_command_id,
                                            )
                                        except Exception as exc:
                                            print(f"Could not persist workflow outcome on incident: {type(exc).__name__}", flush=True)
                                    print(f"Datadog workflow {instance_id} succeeded while monitor is Alert; HOLD is already active, so duplicate command was suppressed", flush=True)
                                else:
                                    publish_command("HOLD", "Datadog Node 2 flatline workflow succeeded while monitor is Alert", instance_id)
                                    hold_active = True
                            elif state_now == "OK":
                                print("Recovery workflow succeeded while monitor is OK; application verifier owns CLEAR, so no new HOLD was sent.", flush=True)
                        elif current_status in {"failed", "error", "canceled"}:
                            print(f"Datadog workflow {instance_id} ended as {current_status}; no Wokwi output command sent", flush=True)
                    # Keep running instances visible until their terminal update.
                    if status_name(attrs) not in {"running", "pending", ""}:
                        existing_ids.add(instance_id)

                if state_now == "ALERT" and not hold_active:
                    # Fail safe if the workflow run is delayed: the virtual
                    # pump indicator remains off while the monitor is Alert.
                    publish_command("HOLD", "flatline monitor is Alert")
                    hold_active = True
                elif state_now == "OK" and hold_active:
                    # Monitor recovery alone does not prove that a sensor is trustworthy.
                    print("Monitor is OK, but HOLD remains latched pending explicit recovery verification.", flush=True)
            except requests.RequestException as exc:
                print(f"Datadog API polling error: {exc}", flush=True)
            except (KeyError, TypeError, ValueError) as exc:
                print(f"Unexpected Datadog response: {exc}", flush=True)
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("Stopped Wokwi bridge.", flush=True)
        return 0
    finally:
        cloud_mqtt.loop_stop()
        local_mqtt.loop_stop()
        cloud_mqtt.disconnect()
        local_mqtt.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
