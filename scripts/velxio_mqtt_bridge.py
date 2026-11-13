#!/usr/bin/env python3
"""Safe adapter for the Velxio three-device synthetic MQTT demo.

This adapter is additive: the existing Wokwi bridge and topics remain intact.
Velxio messages are normalized to the SMIOT ``farm/sensor`` contract and all
control-plane correlation fields are carried end-to-end.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import signal
import threading
import time
from datetime import datetime, timezone
from typing import Any

try:
    import paho.mqtt.client as mqtt
except ImportError:  # Contract helpers remain importable in a test-only install.
    mqtt = None

SOURCE = "velxio_synthetic"
DEFAULT_FARM_KEY = "greenhouse_j"
ALLOWED_ACTIONS = {"SET_OUTPUTS", "HOLD", "CLEAR"}
VIRTUAL_DEVICES = ("node1", "node2", "flow")
# Scenario code or legacy type -> the only virtual devices that receive SET_PROFILE.
SCENARIO_DEVICES: dict[str, tuple[str, ...]] = {
    "A1": ("node2", "flow"), "a1_water_overrun": ("node2", "flow"),
    "A2": ("node2",), "a2_pump_pressure_zero": ("node2",),
    "A3": ("flow",), "a3_low_flow": ("flow",),
    "C10": ("flow",), "pipe_leak": ("flow",),
    "A4": ("node2",), "a4_command_no_ack": ("node2",),
    "S2": ("node1",), "soil_spike": ("node1",),
    "S3": ("node1",), "soil_out_of_range": ("node1",),
    # C2 (VPD outside stage band) and C6 (drain EC rise) are catalog scenarios served by node1.
    "C2": ("node1",), "C6": ("node1",),
    # W8 / vpd_ec_risk are kept for compatibility but are not in the scenario catalog
    # (W8 is a workflow, not a scenario code).
    "W8": ("node1",), "vpd_ec_risk": ("node1",),
}
_SCENARIO_DEVICES_BY_KEY = {key.lower(): devices for key, devices in SCENARIO_DEVICES.items()}
LOGGER = logging.getLogger("smiot.velxio.bridge")


def config() -> dict[str, Any]:
    """Read bridge settings from env without exposing credentials."""
    return {
        "farm_key": os.getenv("VELXIO_FARM_KEY", DEFAULT_FARM_KEY),
        "channel": os.getenv("VELXIO_CHANNEL", "smiot-course-20261112-a91d4b"),
        "remote_host": os.getenv("VELXIO_PUBLIC_HOST", "broker.hivemq.com"),
        "remote_port": int(os.getenv("VELXIO_PUBLIC_PORT", "1883")),
        "local_host": os.getenv("VELXIO_LOCAL_HOST", "127.0.0.1"),
        "local_port": int(os.getenv("VELXIO_LOCAL_PORT", "1883")),
        "username": os.getenv("VELXIO_MQTT_USERNAME") or None,
        "password": os.getenv("VELXIO_MQTT_PASSWORD") or None,
    }


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _bit(value: object) -> int | None:
    if value in (0, False, "0"):
        return 0
    if value in (1, True, "1"):
        return 1
    return None


def _finite(value: object, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def _correlation(payload: dict[str, Any]) -> dict[str, str]:
    """Copy correlation IDs only when supplied; never invent an incident ID."""
    result: dict[str, str] = {}
    for key in ("command_id", "incident_id", "scenario_run_id", "scenario_code"):
        value = payload.get(key)
        if value is not None and str(value).strip():
            result[key] = str(value)[:128]
    return result


def build_profile_command(payload: dict[str, Any], farm_key: str, device: str, profile: str) -> dict[str, Any]:
    """Build a farm-scoped profile switch for one Velxio virtual device."""
    if device not in VIRTUAL_DEVICES or profile not in {"normal", "fault"}:
        raise ValueError("invalid virtual device profile target")
    if str(payload.get("farm_key") or "") != farm_key:
        raise ValueError("profile farm_key does not match bridge farm")
    command_id = str(payload.get("command_id") or "").strip()
    if not command_id:
        raise ValueError("profile command_id is required")
    return {
        **_correlation(payload),
        "action": "SET_PROFILE", "profile": profile, "farm_key": farm_key,
        "target_device_id": device,
        "command_id": f"{command_id[:112]}:profile:{device}",
        "source_command_id": command_id,
        "source": SOURCE, "synthetic": True, "timestamp": stamp(),
    }


def scenario_token(payload: dict[str, Any]) -> str:
    return str(payload.get("scenario_code") or payload.get("scenario_type") or "").strip()


def profile_commands(payload: dict[str, Any], farm_key: str, profile: str) -> list[dict[str, Any]]:
    """Build SET_PROFILE commands only for devices mapped to the scenario.

    An unmapped scenario sends nothing; it never falls back to all devices.
    """
    token = scenario_token(payload)
    devices = _SCENARIO_DEVICES_BY_KEY.get(token.lower())
    if devices is None:
        LOGGER.warning("velxio_profile_unmapped scenario=%s", token[:64] or "none")
        return []
    return [build_profile_command(payload, farm_key, device, profile) for device in devices]


def scenario_profile(payload: dict[str, Any], topic: str) -> str | None:
    action = str(payload.get("action") or "").upper()
    if topic == "farm/demo/status" and payload.get("event") == "scenario_ack" and payload.get("applied") is True:
        if payload.get("status") == "started":
            return "fault"
        if payload.get("status") == "stopped":
            return "normal"
    if topic == "farm/control" and action == "CLEAR":
        return "normal"
    return None


def normalize_profile_ack(payload: dict[str, Any], expected: dict[str, Any], farm_key: str) -> dict[str, Any]:
    if str(payload.get("farm_key") or "") != farm_key:
        raise ValueError("profile ACK farm mismatch")
    if str(payload.get("command_id") or "") != expected["command_id"]:
        raise ValueError("profile ACK command mismatch")
    device_aliases = {"node1": {"node1", "velxio-node1"},
                      "node2": {"node2", "velxio-virtual-pump-01"},
                      "flow": {"flow", "velxio-flow-monitor-01"}}
    target = expected["target_device_id"]
    if str(payload.get("device_id") or "") not in device_aliases.get(target, {target}):
        raise ValueError("profile ACK device mismatch")
    if str(payload.get("profile") or "") != expected["profile"]:
        raise ValueError("profile ACK state mismatch")
    return {**_correlation(expected), "event": "virtual_device_profile_ack",
            "command_id": expected["source_command_id"],
            "profile_command_id": expected["command_id"],
            "device_id": str(payload.get("device_id")),
            "node_id": str(payload.get("node_id") or expected["target_device_id"]),
            "farm_key": farm_key, "profile": expected["profile"],
            "dataset_id": str(payload.get("dataset_id") or "")[:80],
            "applied": payload.get("applied") is True,
            "verified": payload.get("verified") is True,
            "source": SOURCE, "synthetic": True, "timestamp": stamp()}


def normalize_command(payload: dict[str, Any], farm_key: str) -> dict[str, Any]:
    """Validate an SMIOT command and produce the Velxio public command."""
    if not isinstance(payload, dict) or str(payload.get("farm_key")) != farm_key:
        raise ValueError("command farm_key does not match bridge farm")
    command_id = str(payload.get("command_id") or "").strip()
    if not command_id:
        raise ValueError("command_id is required")
    action = str(payload.get("action") or "SET_OUTPUTS").upper()
    if action in {"SAFE_STOP", "STOP_PUMPS"}:
        action = "HOLD"
    if action not in ALLOWED_ACTIONS:
        raise ValueError("action is not allowlisted")
    bits: dict[str, int] = {}
    for index in range(8):
        key = f"bit{index}"
        if key in payload:
            value = _bit(payload[key])
            if value is None:
                raise ValueError(f"{key} must be 0 or 1")
            bits[key] = value
    if action in {"HOLD", "CLEAR"}:
        bits = {f"bit{i}": 0 for i in range(8)}
    if action == "SET_OUTPUTS" and not bits:
        raise ValueError("SET_OUTPUTS needs at least one output")
    return {
        "command_id": command_id,
        "action": action,
        "farm_key": farm_key,
        "device_id": "velxio-virtual-plc-01",
        "source": SOURCE,
        "synthetic": True,
        "timestamp": stamp(),
        **_correlation(payload),
        **bits,
    }


def build_node_envelope(payload: dict[str, Any], node_id: str, farm_key: str) -> dict[str, Any]:
    if node_id not in {"node1", "node2"} or payload.get("node_id") != node_id:
        raise ValueError("unexpected node_id")
    readings = {field: _finite(payload[field], field) for field in ("at", "ah", "st", "sh", "sec")}
    if not 0 <= readings["ah"] <= 100 or not 0 <= readings["sh"] <= 100:
        raise ValueError("humidity is outside 0..100")
    now = stamp()
    return {
        "device_name": "Velxio SMIOT course demo",
        "device_id": str(payload.get("device_id") or node_id)[:64],
        "boot_id": str(payload.get("boot_id") or "velxio-boot")[:64],
        "sample_sequence": int(payload.get("sequence") or 0),
        "device_uptime_ms": int(payload.get("uptime_ms") or 0),
        "farm_key": farm_key,
        "id6": {node_id: {**readings, "timestamp": now,
                           "profile": str(payload.get("profile") or "normal"),
                           "dataset_id": str(payload.get("dataset_id") or f"{node_id}-normal-v1")}},
        "device_profile": str(payload.get("profile") or "normal"),
        "dataset_id": str(payload.get("dataset_id") or f"{node_id}-normal-v1"),
        "scenario_code": payload.get("scenario_code"),
        "incident_id": payload.get("incident_id"),
        "scenario_run_id": payload.get("scenario_run_id"),
        "source": SOURCE,
        "synthetic": True,
        "timestamp": now,
    }


def build_flow_envelope(payload: dict[str, Any], farm_key: str) -> dict[str, Any]:
    readings = {field: _finite(payload.get(field, 0.0), field)
                for field in ("f1", "f2", "pressure_bar", "t1", "t2")}
    now = stamp()
    return {
        "device_name": "Velxio Flow Monitor",
        "device_id": str(payload.get("device_id") or "velxio-flow-monitor-01")[:64],
        "farm_key": farm_key,
        "id3": {**readings,
                "device_profile": str(payload.get("profile") or "normal"),
                "dataset_id": str(payload.get("dataset_id") or "flow-normal-v1"),
                "safe_mode_active": bool(payload.get("safe_mode_active", False)),
                "fault": str(payload.get("fault") or "none")[:64],
                "pump_line1_on": bool(payload.get("pump_line1_on", False)),
                "pump_line2_on": bool(payload.get("pump_line2_on", False)),
                "valve_open": bool(payload.get("valve_open", False)),
                "timestamp": now, "measured_at": now, "synthetic": True},
        "device_profile": str(payload.get("profile") or "normal"),
        "dataset_id": str(payload.get("dataset_id") or "flow-normal-v1"),
        "scenario_code": payload.get("scenario_code"), "incident_id": payload.get("incident_id"),
        "scenario_run_id": payload.get("scenario_run_id"),
        "source": SOURCE, "synthetic": True, "timestamp": now,
    }


def build_ack_payload(payload: dict[str, Any], expected: dict[str, Any], farm_key: str) -> dict[str, Any]:
    """Normalize an ACK and preserve exact command/incident/run correlation."""
    if str(payload.get("farm_key")) != farm_key or str(payload.get("command_id")) != str(expected["command_id"]):
        raise ValueError("ACK does not match pending farm/command")
    observed = payload.get("virtual_output")
    if not isinstance(observed, dict):
        raise ValueError("ACK virtual_output is required")
    normalized = {}
    for index in range(8):
        value = _bit(observed.get(f"bit{index}"))
        if value is None:
            raise ValueError("ACK output contains an invalid bit")
        normalized[f"bit{index}"] = value
    matches = all(normalized.get(k) == v for k, v in expected.get("bits", {}).items())
    return {**payload, **_correlation(expected), "farm_key": farm_key,
            "device_id": "velxio-virtual-plc-01", "source": SOURCE,
            "synthetic": True, "virtual_output": normalized,
            "applied": bool(payload.get("applied") is True and matches),
            "verified": bool(payload.get("verified") is True and matches),
            "timestamp": stamp()}


def run(channel: str | None = None) -> None:
    if mqtt is None:
        raise RuntimeError("paho-mqtt is required to run the bridge")
    settings = config()
    channel = channel or settings["channel"]
    farm_key = settings["farm_key"]
    prefix = f"smiot/velxio/{channel}"
    sensor_topics = {f"{prefix}/sensor/{node}": node for node in ("node1", "node2", "flow")}
    command_topic, ack_topic = f"{prefix}/actuator/command", f"{prefix}/actuator/ack"
    local = mqtt.Client(client_id="smiot-velxio-local")
    cloud = mqtt.Client(client_id="smiot-velxio-public-bridge")
    if settings["username"]:
        cloud.username_pw_set(settings["username"], settings["password"])
    pending: dict[str, dict[str, Any]] = {}
    pending_profiles: dict[str, dict[str, Any]] = {}
    lock = threading.Lock()

    def local_connect(client, userdata, flags, reason_code, properties=None):
        if getattr(reason_code, "value", reason_code) == 0:
            client.subscribe("farm/control", qos=1)
            client.subscribe("farm/demo/control", qos=1)
            client.subscribe("farm/demo/status", qos=1)
            client.subscribe("farm/demo/profile-command", qos=1)

    def cloud_connect(client, userdata, flags, reason_code, properties=None):
        if getattr(reason_code, "value", reason_code) == 0:
            for topic in (*sensor_topics, ack_topic):
                client.subscribe(topic, qos=1)

    def local_message(client, userdata, message):
        try:
            payload = json.loads(message.payload.decode())
            if message.topic == "farm/demo/profile-command":
                # Workflow recovery is restricted to one explicitly correlated
                # greenhouse-J sensor profile switch. Never fan out to pump/flow.
                if (farm_key != "greenhouse_j"
                        or payload.get("farm_key") != "greenhouse_j"
                        or payload.get("target_device_id") not in {"node1", "node2"}
                        or payload.get("profile") != "normal"
                        or not payload.get("incident_id")
                        or not payload.get("scenario_run_id")):
                    LOGGER.warning("velxio_profile_command_rejected reason=scope_or_profile")
                    return
                device = str(payload["target_device_id"])
                item = build_profile_command(payload, farm_key, device, "normal")
                with lock:
                    pending_profiles[item["command_id"]] = item
                result = cloud.publish(command_topic, json.dumps(item, separators=(",", ":")), qos=1)
                if getattr(result, "rc", 0) != 0:
                    with lock:
                        pending_profiles.pop(item["command_id"], None)
                    LOGGER.warning("velxio_profile_command_publish_failed device=%s rc=%s",
                                   device, getattr(result, "rc", "unknown"))
                return
            if message.topic == "farm/demo/control":
                return  # Wait for the simulator's accepted/rejected ACK.
            profile = scenario_profile(payload, message.topic)
            if profile:
                for item in profile_commands(payload, farm_key, profile):
                    device = item["target_device_id"]
                    with lock:
                        pending_profiles[item["command_id"]] = item
                    result = cloud.publish(command_topic, json.dumps(item, separators=(",", ":")), qos=1)
                    if getattr(result, "rc", 0) != 0:
                        LOGGER.warning("velxio_profile_command_publish_failed device=%s rc=%s",
                                       device, getattr(result, "rc", "unknown"))
                # Scenario control remains owned by the local simulator. For
                # CLEAR, also pass the actuator instruction to the pump board.
                if message.topic == "farm/demo/status":
                    return
                if str(payload.get("action") or "").upper() != "CLEAR":
                    return
            item = normalize_command(payload, farm_key)
            with lock:
                pending[item["command_id"]] = {"command_id": item["command_id"],
                                                "bits": {k: item[k] for k in item if k.startswith("bit")},
                                                **_correlation(item)}
            cloud.publish(command_topic, json.dumps(item, separators=(",", ":")), qos=1)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            return

    def cloud_message(client, userdata, message):
        try:
            payload = json.loads(message.payload.decode())
            if message.topic in sensor_topics:
                node = sensor_topics[message.topic]
                envelope = build_flow_envelope(payload, farm_key) if node == "flow" else build_node_envelope(payload, node, farm_key)
                # Lease ownership of this exact farm/device stream to Velxio only
                # while real simulator samples keep arriving. The EC2 publisher
                # resumes automatically after the lease expires.
                local.publish("farm/demo/control", json.dumps({
                    "action": "EXTERNAL_SOURCE_HEARTBEAT",
                    "farm_key": farm_key,
                    "device_key": node,
                    "source": SOURCE,
                    "synthetic": True,
                    "timestamp": stamp(),
                }, separators=(",", ":")), qos=1)
                local.publish("farm/sensor", json.dumps(envelope, separators=(",", ":")), qos=1)
            elif message.topic == ack_topic:
                if payload.get("event") == "virtual_device_profile_ack":
                    with lock:
                        expected = pending_profiles.get(str(payload.get("command_id")))
                    if expected is None:
                        LOGGER.warning("velxio_profile_ack_rejected reason=no_pending_command device=%s",
                                       str(payload.get("node_id") or "unknown")[:32])
                        return
                    try:
                        ack = normalize_profile_ack(payload, expected, farm_key)
                    except (KeyError, TypeError, ValueError) as exc:
                        LOGGER.warning("velxio_profile_ack_rejected reason=%s device=%s",
                                       str(exc)[:80], str(payload.get("node_id") or "unknown")[:32])
                        return
                    result = local.publish("farm/demo/device_profile/ack",
                                           json.dumps(ack, separators=(",", ":")), qos=1)
                    if getattr(result, "rc", 0) != 0:
                        LOGGER.warning("velxio_profile_ack_forward_failed device=%s rc=%s",
                                       ack["node_id"], getattr(result, "rc", "unknown"))
                        return
                    LOGGER.info("velxio_profile_ack_forwarded device=%s profile=%s verified=%s",
                                ack["node_id"], ack["profile"], ack["verified"])
                    with lock:
                        pending_profiles.pop(str(payload.get("command_id")), None)
                    return
                with lock:
                    expected = pending.get(str(payload.get("command_id")))
                if expected is None:
                    return
                ack = build_ack_payload(payload, expected, farm_key)
                status = {"event": "plc_status", "device_name": "SMIOT Virtual PLC",
                          "device_id": ack["device_id"], "command_id": ack["command_id"],
                          "action": ack.get("action", "SET_OUTPUTS"), "farm_key": farm_key,
                          "virtual_output": ack["virtual_output"],
                          "safe_mode_active": bool(ack.get("safe_mode_active")),
                          "source": SOURCE, "synthetic": True, "timestamp": ack["timestamp"],
                          **_correlation(ack)}
                local.publish("farm/status", json.dumps(status, separators=(",", ":")), qos=1)
                local.publish("farm/command/ack", json.dumps(ack, separators=(",", ":")), qos=1)
                with lock:
                    pending.pop(str(payload.get("command_id")), None)
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return

    local.on_connect, local.on_message = local_connect, local_message
    cloud.on_connect, cloud.on_message = cloud_connect, cloud_message
    local.connect(settings["local_host"], settings["local_port"], 60)
    cloud.connect(settings["remote_host"], settings["remote_port"], 60)
    local.loop_start(); cloud.loop_start()
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    try:
        while not stopped.wait(1):
            pass
    finally:
        local.loop_stop(); cloud.loop_stop(); local.disconnect(); cloud.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", default=None)
    run(parser.parse_args().channel)
