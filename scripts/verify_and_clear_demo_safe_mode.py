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
    # group.get(key, 0) only supplies 0 when the key is MISSING; Datadog sends
    # "last_triggered_ts": null for a group that has never triggered, so the
    # key is present with value None and `or 0` is needed to avoid int(None).
    last_triggered_ts = max(
        (int(group.get("last_triggered_ts") or 0) for group in groups.values()),
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
    # Identify the HOLD by what it IS (target/farm/node/monitor), not by "source".
    # wokwi_datadog_bridge.publish_command tags the *request* with
    # source="datadog_safe_mode_workflow", but the ledger's "acknowledged"
    # transition is written from the virtual PLC's own ACK payload, which
    # self-reports its publisher source (e.g. "smiot_demo_stream") and
    # overwrites that field. Matching on "source" at this stage silently
    # never finds the record, so every automatic recovery is refused.
    hold_identity = {
        "action": "HOLD", "state": "acknowledged", "monitor_id": monitor_id,
        "target": "smiot_virtual_plc", "farm_key": "greenhouse_a", "node_id": 2,
    }
    hold = ledger.find_one(
        {**hold_identity, "acknowledged_at": {"$gte": monitor_triggered_at}},
        sort=[("acknowledged_at", DESCENDING)],
    )
    if not hold:
        # Bridge bo qua HOLD trung khi HOLD cu van dang giu (log: "duplicate command was suppressed"),
        # nen alert moi co the khong co ban ghi ack moi. Chap nhan HOLD da ack gan nhat cua monitor
        # CHI KHI chua co CLEAR da xac minh sau do, va gan kiem chung vao su co dang mo.
        latest = ledger.find_one(hold_identity, sort=[("acknowledged_at", DESCENDING)])
        if latest:
            cleared_after = ledger.find_one(
                {"action": "CLEAR", "state": "verified", "acknowledged_at": {"$gte": latest.get("acknowledged_at")}},
                {"_id": 1},
            )
            open_incident = db["operational_incidents"].find_one(
                {"kind": "soil_humidity_flatline", "farm_key": "greenhouse_a", "node_id": 2,
                 "status": {"$in": ["open", "holding", "recovering"]}},
                {"_id": 1}, sort=[("opened_at", DESCENDING)],
            )
            if not cleared_after and open_incident:
                hold = dict(latest)
                hold["incident_id"] = str(open_incident["_id"])
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
        previous_verification = previous_clear.get("verification") or {}
        try:
            previous_range = [float(v) for v in previous_verification["soil_humidity_range_pct"]]
            previous_count = int(previous_verification["sample_count"])
            previous_freshness = float(previous_verification["sample_freshness_seconds"])
            # A CLEAR recorded before this script started saving these two
            # fields has neither key; defaulting them to 10 / 0 made the
            # count/span checks below fail for every such pre-existing CLEAR
            # (previous_count was always < the invented default of 10),
            # permanently refusing to report a recovery that already happened
            # and was otherwise fully proven by clear_ack. Fall back to the
            # record's own sample_count/the 300 s stability bar it must have
            # already met, instead of a stricter value it never reported.
            previous_required = int(previous_verification.get("required_samples", previous_count))
            previous_span = float(previous_verification.get("sample_span_seconds", 300))
        except (TypeError, ValueError, KeyError):
            client.close()
            raise RuntimeError("Refusing to report an already-cleared incident: prior CLEAR lacks complete telemetry proof")
        prior_ack = previous_verification.get("clear_ack") or {}
        prior_outputs = prior_ack.get("virtual_output") or {}
        if (previous_verification.get("incident_id") != incident_id
                or str(previous_verification.get("monitor_state", "")).upper() != "OK"
                or previous_verification.get("virtual_pump_outputs_off") is not True
                or previous_count < previous_required or previous_required < 2
                or previous_span < 300 or not (0 <= previous_freshness <= 90)
                or len(previous_range) != 2 or not (0 <= previous_range[0] <= previous_range[1] <= 100)
                or previous_range[1] - previous_range[0] < 0.5
                or not previous_verification.get("newest_sample_at")
                or not previous_clear.get("command_id")
                or prior_ack.get("command_id") != previous_clear.get("command_id")
                or prior_ack.get("action") != "CLEAR" or prior_ack.get("applied") is not True
                or prior_ack.get("verified") is not True or prior_ack.get("safe_mode_active") is not False
                or prior_ack.get("synthetic") is not True
                or set(prior_outputs) != {f"bit{i}" for i in range(8)}
                or any(value not in (0, False, "0") for value in prior_outputs.values())
                or not prior_ack.get("timestamp")):
            client.close()
            raise RuntimeError("Refusing to report an already-cleared incident: prior CLEAR proof is incomplete or mismatched")
        client.close()
        print(json.dumps({
            "result": "already_verified_and_cleared",
            "command_id": previous_clear.get("command_id"),
            "incident_id": incident_id,
            # The caller (telemetry_health._track_flatline_recovery) runs this
            # script once per farm/node pair it is itself polling, but this
            # verifier only ever checks greenhouse_a/node 2; without these two
            # fields the caller closed whichever incident its own loop
            # iteration happened to be on, not the one actually verified here.
            "farm_key": "greenhouse_a",
            "node_id": 2,
            "monitor_state": monitor_state,
            "fresh_normal_samples": previous_count,
            # telemetry_health._valid_flatline_verifier_result requires
            # required_samples/stable_seconds too (it treats a missing
            # required_samples as 0, which then fails its own ">= 2" check);
            # the fresh-clear branch below already reports these, so this
            # branch must match the same shape.
            "required_samples": previous_required,
            "stable_seconds": max(60, int(os.getenv("SMIOT_FLATLINE_STABLE_SECONDS", "300"))),
            "expected_interval_seconds": previous_verification.get(
                "expected_interval_seconds", max(1, int(os.getenv("SMIOT_SIM_NODE_INTERVAL_SECONDS", "60")))),
            "sample_span_seconds": previous_span,
            "soil_humidity_range_pct": previous_range,
            "newest_sample_at": previous_verification.get("newest_sample_at"),
            "sample_freshness_seconds": round(previous_freshness, 1),
            "clear_ack": prior_ack,
            "virtual_pump_outputs_off": True,
            "simulated": True,
        }, ensure_ascii=False))
        return 0

    # Require five minutes of stable recovery, but derive sample count from the
    # simulator's configured cadence. With the default 60s cadence, 10 samples
    # cannot fit in the old six-minute query window (they span at least 9 min).
    expected_interval = max(1, int(os.getenv("SMIOT_SIM_NODE_INTERVAL_SECONDS", "60")))
    stable_seconds = max(60, int(os.getenv("SMIOT_FLATLINE_STABLE_SECONDS", "300")))
    required_samples = (stable_seconds + expected_interval - 1) // expected_interval + 1
    query_window_seconds = stable_seconds + expected_interval + 60
    sample_start = max(now - timedelta(seconds=query_window_seconds), hold_ack_at or monitor_triggered_at)
    recent = list(telemetry.find(
        {
            "meta.farm_key": "greenhouse_a",
            "meta.measurement_type": "node",
            "meta.node_id": 2,
            "source.source": "smiot_demo_stream",
            "source.demo_seed_version": {"$exists": False},
            # Mau cua su co do watchdog mo thuong khong gan incident_id; chap nhan them
            # mau khong nhan trong cua so da nam sau luc HOLD duoc ack (sample_start).
            "$or": [{"source.incident_id": incident_id}, {"source.incident_id": {"$exists": False}}, {"source.incident_id": None}],
            "timestamp": {"$gte": sample_start, "$lte": now},
            "readings.soil_hum": {"$type": "number", "$ne": 2.4},
        },
        {"timestamp": 1, "readings.soil_hum": 1, "source.message_id": 1,
         "source.sequence": 1, "source.boot_id": 1},
    ).sort("timestamp", DESCENDING).limit(20))
    # Keep only distinct, sequenced samples from the latest publisher boot.
    # A reboot resets the per-device sequence, so samples from two boots must
    # not be combined to claim a continuous recovery period.
    newest_boot = next((row.get("source", {}).get("boot_id") for row in recent
                        if row.get("source", {}).get("boot_id")), None)
    stable = [row for row in recent
              if row.get("source", {}).get("boot_id") == newest_boot
              and isinstance(row.get("source", {}).get("sequence"), int)
              and row.get("source", {}).get("message_id")]
    stable = list({row["source"]["message_id"]: row for row in stable}.values())
    stable.sort(key=lambda row: row["timestamp"])
    sequences = [int(row["source"]["sequence"]) for row in stable]
    if len(stable) < required_samples:
        client.close()
        raise RuntimeError(
            f"Refusing to clear HOLD: only {len(stable)} unique sequenced normal Node 2 samples "
            f"for boot {newest_boot or 'unknown'} tied to incident {incident_id}; "
            f"need {required_samples} at {expected_interval}s cadence for {stable_seconds}s stability"
        )
    if any(b <= a for a, b in zip(sequences, sequences[1:])):
        client.close()
        raise RuntimeError("Refusing to clear HOLD: Node 2 sample sequence is not strictly increasing")
    # Use the latest contiguous recovery window, not old samples from earlier
    # in the query range, to evaluate stability and freshness.
    stable = stable[-required_samples:]
    values = [float(row["readings"]["soil_hum"]) for row in stable]
    newest = stable[-1]["timestamp"]
    oldest = stable[0]["timestamp"]
    for label, stamp in (("newest", newest), ("oldest", oldest)):
        if stamp.tzinfo is None:
            if label == "newest":
                newest = stamp.replace(tzinfo=timezone.utc)
            else:
                oldest = stamp.replace(tzinfo=timezone.utc)
    span_seconds = (newest - oldest).total_seconds()
    freshness_seconds = (now - newest).total_seconds()
    if span_seconds < stable_seconds or freshness_seconds > max(90, expected_interval * 1.5) or max(values) - min(values) < 0.5:
        client.close()
        raise RuntimeError(
            f"Refusing to clear HOLD: stable span={span_seconds:.1f}s, "
            f"freshness={freshness_seconds:.1f}s, humidity range={max(values)-min(values):.2f}; "
            f"expected at least {stable_seconds}s of fresh, varying readings"
        )

    broker_host = os.getenv("MQTT_HOST", "127.0.0.1")
    broker_port = int(os.getenv("MQTT_PORT", "1883"))
    command_id = uuid.uuid4().hex
    command = {
        "command_id": command_id,
        "action": "CLEAR",
        "reason": f"Datadog monitor OK and {required_samples} unique sequenced Node 2 MongoDB samples verified over {stable_seconds}s",
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
        outputs = ack_data.get("virtual_output")
        expected_outputs = {f"bit{i}" for i in range(8)}
        if (not isinstance(outputs, dict) or set(outputs) != expected_outputs
                or any(value not in (0, False, "0") for value in outputs.values())
                or ack_data.get("safe_mode_active") is not False
                or ack_data.get("applied") is not True
                or ack_data.get("verified") is not True
                or ack_data.get("action") != "CLEAR"
                or str(ack_data.get("incident_id") or "") != incident_id
                or ack_data.get("farm_key") != "greenhouse_a"
                or ack_data.get("target") != "smiot_virtual_plc"
                or ack_data.get("synthetic") is not True):
            raise RuntimeError("PLC ACK did not prove the matching CLEAR, readback, and all eight outputs OFF")
        try:
            ack_at = datetime.fromisoformat(str(ack_data.get("timestamp", "")).replace("Z", "+00:00"))
            if ack_at.tzinfo is None:
                ack_at = ack_at.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise RuntimeError("PLC CLEAR ACK timestamp is missing or invalid") from exc
        if abs((datetime.now(timezone.utc) - ack_at).total_seconds()) > 30:
            raise RuntimeError("PLC CLEAR ACK timestamp is outside the current verification window")

        verification = {
            "incident_id": incident_id,
            "monitor_state": monitor_state,
            "sample_count": len(stable),
            # Persisted so a later run's idempotent re-check (which reads this
            # same "verification" document back from MongoDB) compares the
            # actual run's own required_samples/span, not a guessed default -
            # required_samples can be below 10 depending on SMIOT_SIM_NODE_
            # INTERVAL_SECONDS, and omitting it here made every idempotent
            # retry fail with "prior CLEAR proof is incomplete or mismatched".
            "required_samples": required_samples,
            "sample_span_seconds": round(span_seconds, 1),
            "soil_humidity_range_pct": [min(values), max(values)],
            "newest_sample_at": newest.isoformat(),
            "sample_message_ids": [row.get("source", {}).get("message_id") for row in stable if row.get("source", {}).get("message_id")],
            "sample_freshness_seconds": round(freshness_seconds, 1),
            "expected_interval_seconds": expected_interval,
            "virtual_pump_outputs_off": True,
            "clear_ack": {
                "command_id": ack_data.get("command_id"),
                "action": ack_data.get("action"),
                "applied": ack_data.get("applied"),
                "verified": ack_data.get("verified"),
                "safe_mode_active": ack_data.get("safe_mode_active"),
                "virtual_output": outputs,
                "timestamp": ack_at.isoformat(),
                "synthetic": ack_data.get("synthetic"),
            },
        }
        mqtt_client.publish("farm/command/event", json.dumps({
            **command,
            "ledger_state": "verified",
            "verification": verification,
        }, separators=(",", ":")), qos=1).wait_for_publish(5)
        print(json.dumps({
            "result": "verified_and_cleared",
            "command_id": command_id,
            # See the matching comment in the already-cleared branch above.
            "farm_key": "greenhouse_a",
            "node_id": 2,
            "prior_hold_command_id": hold.get("command_id"),
            "monitor_state": monitor_state,
            "fresh_normal_samples": len(stable),
            "sample_span_seconds": round(span_seconds, 1),
            "required_samples": required_samples,
            "stable_seconds": stable_seconds,
            "expected_interval_seconds": expected_interval,
            "soil_humidity_range_pct": [round(min(values), 2), round(max(values), 2)],
            "newest_sample_at": newest.isoformat(),
            "sample_freshness_seconds": round(freshness_seconds, 1),
            "clear_ack": verification["clear_ack"],
            "incident_id": incident_id,
            "virtual_pump_outputs": outputs,
            "virtual_pump_outputs_off": all(int(value) == 0 for value in outputs.values()),
            "monitor_state": monitor_state,
            "simulated": True,
        }, ensure_ascii=False))
        return 0
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
