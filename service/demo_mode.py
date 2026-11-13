"""Idempotent demo history seeding and safe, continuous synthetic MQTT telemetry."""

from __future__ import annotations

import json
import logging
import math
import os
import random
import threading
import time
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any

import paho.mqtt.client as mqtt
from pymongo import ReplaceOne, UpdateOne

from service.mongodb_store import collection
from service.scenario_catalog import canonical_type, resolve_scenario, scenario_codes, scenario_types

LOGGER = logging.getLogger("smiot.demo")
# v1 was incorrectly flatlined for every historical hour. Keep those immutable
# time-series measurements for audit, but seed and serve the coherent v2 story.
SEED_VERSION = "smiot-demo-history-v2"
LEGACY_BAD_SEED_VERSION = "smiot-demo-history-v1"
# Fixed six-hour incident window makes the historical narrative stable across restarts.
NODE2_INCIDENT_START = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
NODE2_INCIDENT_END = datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc)
from service.farm_registry import FARM_KEYS

FARMS = FARM_KEYS
# Small centered calibration variation keeps the virtual greenhouses distinct
# without fabricating a large temperature gradient from A through J.
FARM_OFFSETS = {farm: (index - (len(FARMS) - 1) / 2) * 0.12 for index, farm in enumerate(FARMS)}
LOT_PREFIX = "melon-lot-local-demo-"
STAGES = ("sowing", "seedling", "vegetative", "flowering_fruiting", "harvest")
_started = False
_start_lock = threading.Lock()
_virtual_outputs_lock = threading.Lock()
_node2_flatline = False
_active_demo_incident_id: str | None = None
_w6_incidents_by_farm: dict[str, str] = {}
_active_scenarios: dict[str, dict[str, Any]] = {}
_external_source_last_seen: dict[tuple[str, str], float] = {}
_external_source_lock = threading.Lock()
EXTERNAL_SOURCE_LEASE_SECONDS = max(20, int(os.getenv("SMIOT_EXTERNAL_SOURCE_LEASE_SECONDS", "35")))
_farm_actuators: dict[str, dict[str, Any]] = {}
_pump_started_at: dict[tuple[str, int], float] = {}
_pump_volume_l: dict[tuple[str, int], float] = {}
_sample_sequences: dict[tuple[str, int], int] = {}
_sample_sequence = 0  # envelope-level compatibility ID; each node also has its own counter
_device_sequences: dict[tuple[str, str], int] = {}
_publisher_boot_id = f"demo-{os.getpid()}-{int(time.time())}"
_publisher_started_monotonic = time.monotonic()

# Conservative demo interlocks: virtual pumps stop before either limit is crossed.
# Values can be shortened for a controlled demo, but must remain positive.
VIRTUAL_PLC_MAX_RUN_SECONDS = max(5, int(os.getenv("SMIOT_VIRTUAL_PLC_MAX_RUN_SECONDS", "120")))
VIRTUAL_PLC_MAX_VOLUME_L = max(1.0, float(os.getenv("SMIOT_VIRTUAL_PLC_MAX_VOLUME_L", "20")))
VIRTUAL_PLC_FLOW_LPM = max(0.1, float(os.getenv("SMIOT_VIRTUAL_PLC_FLOW_LPM", "4.5")))
VIRTUAL_PLC_LOW_PRESSURE_BAR = max(0.05, float(os.getenv("SMIOT_VIRTUAL_PLC_LOW_PRESSURE_BAR", "0.5")))
VIRTUAL_PLC_LEAK_FLOW_LPM = max(0.1, float(os.getenv("SMIOT_VIRTUAL_PLC_LEAK_FLOW_LPM", "12.0")))
VIRTUAL_PLC_LEAK_MIN_FLOW_LPM = max(0.1, float(os.getenv("SMIOT_VIRTUAL_PLC_LEAK_MIN_FLOW_LPM", "8.0")))
_w2_demo_cadence = os.getenv("SMIOT_W2_DEMO_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}
_default_node_interval = "10" if _w2_demo_cadence else "60"
DEVICE_INTERVAL_SECONDS = {
    # The 10-second cadence is opt-in for the bounded W2 drill only. Normal
    # operation remains 60 seconds unless SMIOT_W2_DEMO_MODE is explicitly set.
    "node1": max(5, int(os.getenv("SMIOT_SIM_NODE_INTERVAL_SECONDS", _default_node_interval))),
    "node2": max(5, int(os.getenv("SMIOT_SIM_NODE_INTERVAL_SECONDS", _default_node_interval))),
    "flow": max(1, int(os.getenv("SMIOT_SIM_FLOW_ACTIVE_SECONDS", "5"))),
    "ec": max(60, int(os.getenv("SMIOT_SIM_EC_SECONDS", "300"))),
    "ph": max(60, int(os.getenv("SMIOT_SIM_PH_SECONDS", "300"))),
    "drain": max(5, int(os.getenv("SMIOT_SIM_DRAIN_ACTIVE_SECONDS", "10"))),
    "ventilation": max(5, int(os.getenv("SMIOT_SIM_VENTILATION_SECONDS", "15"))),
    "plc": max(2, int(os.getenv("SMIOT_SIM_PLC_SECONDS", "5"))),
    "inverter": max(2, int(os.getenv("SMIOT_SIM_INVERTER_SECONDS", "10"))),
}
FLOW_IDLE_INTERVAL_SECONDS = max(10, int(os.getenv("SMIOT_SIM_FLOW_IDLE_SECONDS", "60")))
DRAIN_IDLE_INTERVAL_SECONDS = max(30, int(os.getenv("SMIOT_SIM_DRAIN_IDLE_SECONDS", "300")))
SUPPORTED_SCENARIOS = set(scenario_codes()) | set(scenario_types()) | {
    "soil_flatline", "soil_spike", "soil_out_of_range", "water_overrun", "pipe_leak", "vent_stuck",
}
VIRTUAL_NODE_IDS = (1, 2)
VIRTUAL_LOT_IDS = {"greenhouse_a": "melon-lot-local-demo-001"}


def _farm_actuator_state(farm_key: str) -> dict[str, Any]:
    """Return isolated virtual control state for one greenhouse."""
    return _farm_actuators.setdefault(str(farm_key), {
        "outputs": [0] * 8,
        "safe_mode_active": False,
        "vent_command": 0,
        "vent_state": 0,
        "vent_stuck": False,
        "valve_command": 0,
        "valve_state": 0,
        "fault": None,
    })


def get_virtual_farm_status(farm_key: str) -> dict[str, Any] | None:
    """Read-only snapshot for the control-room UI; does not create farm state."""
    farm_key = str(farm_key)
    if farm_key not in FARMS:
        return None
    with _virtual_outputs_lock:
        state = _farm_actuators.get(farm_key) or {}
        active_fault = next(
            (run.get("scenario_type") for run in reversed(list(_active_scenarios.values()))
             if run.get("farm_key") == farm_key and run.get("scenario_type") in {"water_overrun", "pipe_leak", "vent_stuck"}),
            None,
        )
        return {
            "farm_key": farm_key,
            "outputs": list(state.get("outputs") or [0] * 8),
            "safe_mode_active": bool(state.get("safe_mode_active", False)),
            "valve_state": int(state.get("valve_state", 0)),
            "fault": state.get("fault") or active_fault,
            "vent_state": int(state.get("vent_state", 0)),
        }


def _scenario_resources_conflict(existing: dict[str, Any], requested: dict[str, Any] | None,
                                 node_id: int | None) -> bool:
    """Allow concurrent faults on independent virtual resources within one farm."""
    if not requested:
        return True
    def resource(code: str) -> str:
        return {
            "C1": "soil_moisture", "C5": "soil_moisture",
            "C2": "climate_air", "C3": "climate_air", "C8": "climate_air",
            "C4": "pump_water_line", "C9": "pump_water_line",
            "C6": "nutrient_ec", "C7": "crop_stage", "C10": "pump_water_line",
            **{f"S{i}": "soil_moisture" for i in range(1, 7)},
            "D1": "measurement_timestamp", "D2": "ui_status",
            "D3": "device_boot_sequence", "D4": "device_boot_sequence",
            "D5": "device_cadence", "D6": "device_identity", "D7": "device_health",
            "A1": "pump_water_line", "A2": "pump_water_line", "A3": "pump_water_line",
            "A4": "pump_command_channel", "A5": "ventilation",
            "A6": "shade", "A7": "pump_water_line",
            "H1": "app_health", "H2": "dependency_health", "H3": "gateway_health",
            "H4": "detector_health", "H5": "host_resources", "H6": "ai_provider",
        }.get(code, code)
    old_code = str(existing.get("scenario_code") or "")
    new_code = str(requested.get("code") or "")
    old_node = existing.get("node_id")
    # Same measured field/device/action channel is exclusive. Independent farm
    # subsystems may have simultaneous runs, each with its own correlation ID.
    if resource(old_code) != resource(new_code):
        return False
    if resource(old_code) in {"soil_moisture", "climate_air", "measurement_timestamp", "ui_status",
                              "device_boot_sequence", "device_cadence", "device_identity", "device_health"}:
        return old_node in (None, node_id) or node_id in (None, old_node)
    return True


def _load_crop_scenario_context(farm_key: str) -> dict[str, Any]:
    """Load only explicitly recorded crop stage and an approved envelope."""
    local_now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    context: dict[str, Any] = {
        "local_time": local_now.isoformat(),
        "is_daytime": 6 <= local_now.hour < 18,
        "now": local_now.isoformat(),
        "hydraulic_policy": {
            "low_pressure_max_bar": VIRTUAL_PLC_LOW_PRESSURE_BAR,
            "high_flow_min_lpm": VIRTUAL_PLC_LEAK_MIN_FLOW_LPM,
        },
    }
    try:
        cycle = collection("crop_cycles").find_one(
            {"farm_key": farm_key, "status": {"$in": ["active", "growing", "in_progress"]}},
            {"_id": 0, "farm_key": 1, "lot_id": 1, "crop_name": 1, "cultivar": 1,
             "current_stage": 1, "stage_code": 1, "fruit_set_at": 1},
            sort=[("updated_at", -1)],
        )
        if not cycle:
            return context
        stage = cycle.get("current_stage") or cycle.get("stage_code")
        context.update({"crop_cycle": cycle, "stage": stage, "lot_id": cycle.get("lot_id")})
        if stage:
            from service.stage_envelopes import get_effective_stage_envelope
            envelope = get_effective_stage_envelope(
                crop=str(cycle.get("crop_name") or "melon"), stage=str(stage),
                cultivar=cycle.get("cultivar"),
            )
            if envelope:
                # The getter only selects approved + field-calibrated records.
                context["stage_envelope"] = {**envelope, "approval_status": "approved"}
    except Exception as exc:
        LOGGER.info("No calibrated crop context available for scenario simulation: %s", type(exc).__name__)
    return context


def _scenario_observation(run: dict[str, Any], payload: dict[str, Any],
                          sample_index: int) -> dict[str, Any]:
    """Build a separate synthetic control/evidence event; never label a finding as real."""
    code = str(run.get("scenario_code") or "")
    base = {
        "event": "scenario_observation", "scenario_code": code,
        "scenario_type": run.get("scenario_type"), "scenario_run_id": run["scenario_run_id"],
        "farm_key": run.get("farm_key"), "node_id": run.get("node_id"),
        "observed_at": payload.get("timestamp") or _utc_now_text(),
        "synthetic": True, "execution_mode": "SIMULATED_ONLY",
        "real_hardware_action_allowed": False, "real_infrastructure_action_allowed": False,
    }
    if code.startswith("C"):
        from service.scenario_domain_crops import evaluate_crop_scenario
        result = evaluate_crop_scenario(
            {**run, "code": code, "simulate": True}, payload,
            context=run.get("crop_context") or {},
        )
        return {**base, "domain": "crop_climate", "status": result.get("status"),
                "response": result.get("response"), "reason": result.get("reason"),
                "evidence": result.get("evidence") or {}, "finding": result.get("finding"),
                "recovery_requirements": result.get("recovery_requirements"),
                "_overlay": result.get("overlay")}
    if code[:1] in {"S", "D"}:
        from service.scenario_domain_sensor_device import (
            apply_sensor_device_scenario, evaluate_sensor_device_scenario,
        )
        from copy import deepcopy
        before_payload = deepcopy(dict(payload))
        state = run.setdefault("scenario_state", {})
        result = apply_sensor_device_scenario(code, payload, run, peer_payload=payload,
                                              sample_index=sample_index)
        observed = result["payload"]
        baseline = state.get("baseline_sample")
        if code in {"D3", "D4"} and not isinstance(baseline, dict):
            baseline = deepcopy(before_payload)
            state["baseline_sample"] = baseline
        history_rows = state.setdefault("detector_history", [])
        evidence = result["evidence"]
        if code == "S2":
            target_key = f"node{run.get('node_id') or 2}"
            before_node = (before_payload.get("id6") or {}).get(target_key) or {}
            history_rows.append({"sh": before_node.get("sh"), "timestamp": before_node.get("timestamp")})
        elif code not in {"D1", "D2", "D3", "D4", "D5", "D6", "D7"}:
            target_key = f"node{run.get('node_id') or 2}"
            current_node = (observed.get("id6") or {}).get(target_key) or {}
            history_rows.append({"sh": current_node.get("sh"), "timestamp": current_node.get("timestamp")})
        del history_rows[:-32]
        context = {
            "node_id": run.get("node_id") or 2,
            "flatline_min_samples": 4, "flatline_epsilon": 0.01,
            "baseline_min_samples": 5, "spike_threshold": 20.0,
            "drift_min_samples": 5, "min_drift_per_sample": 0.4,
            "noise_min_samples": 5, "max_noise_variance": 8.0,
            "physical_min": 0.0, "physical_max": 100.0,
            "stale_after_seconds": max(60, int(DEVICE_INTERVAL_SECONDS["node2"] * 3)),
            "freshness_limit_seconds": max(60, int(DEVICE_INTERVAL_SECONDS["node2"] * 3)),
            "expected_interval_seconds": DEVICE_INTERVAL_SECONDS["node2"],
            "now": payload.get("timestamp"),
        }
        if code == "D2":
            observed = {**observed, "ui_status": "OFFLINE"}
        peer = None
        if code == "S5":
            target_key = f"node{run.get('node_id') or 2}"
            peer_key = "node1" if target_key == "node2" else "node2"
            peer_node = (before_payload.get("id6") or {}).get(peer_key)
            peer = {"id6": {target_key: peer_node}} if isinstance(peer_node, dict) else None
            context.update({"max_peer_difference": 15.0, "peer_time_tolerance_seconds": 10.0})
        evaluation = evaluate_sensor_device_scenario(
            code, observed, history={"samples": history_rows}, peer_observed=peer,
            previous=baseline, context=context,
        )
        if code in {"D3", "D4"} and isinstance(baseline, dict):
            # Keep the pre-fault comparison point stable throughout the run.
            state["baseline_sample"] = baseline
        status = evaluation["status"]
        response = "HOLD_AND_INSPECT" if evaluation["detected"] is True else (
            "WAIT_FOR_MORE_EVIDENCE" if evaluation["detected"] is None else "NO_ACTION"
        )
        if code == "D2" and evaluation["detected"] is True:
            response = "RECONCILE_UI_FROM_FRESH_SAMPLE"
        finding = ({
            "code": f"scenario_{code.lower()}",
            "severity": "warning" if evaluation["detected"] else "unknown",
            "evidence": evaluation["evidence"],
            "reason": evaluation["reason"],
            "synthetic": True,
        } if evaluation["detected"] is True else None)
        event = {**base, "domain": "sensor_device", "status": status,
                 "response": response, "reason": evaluation["reason"],
                 "evidence": {**result["evidence"], "evaluation": evaluation},
                 "finding": finding, "controls": result["controls"],
                 "_overlay_payload": observed}
        return event
    if code[:1] in {"A", "H"}:
        from service.scenario_domain_actuator_infra import (
            build_actuator_infra_overlay, evaluate_actuator_infra,
        )
        overlay = build_actuator_infra_overlay(code)
        observed = (overlay or {}).get("signals") or {}
        finding = evaluate_actuator_infra(code, observed)
        return {**base, "domain": "actuator" if code.startswith("A") else "software_infrastructure",
                "status": "candidate_detected" if finding else "insufficient_evidence",
                "response": (finding or {}).get("response_intent") or "HOLD",
                "evidence": (finding or {}).get("evidence") or observed,
                "finding": finding, "recovery_requirements": (overlay or {}).get("recovery_requirements"),
                "safety_boundary": "record-only synthetic signal; no physical or cloud action"}
    return {**base, "status": "unknown", "response": "HOLD",
            "reason": "No domain evaluator is registered for this scenario."}


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
            {
                "text": row.get("message") or row.get("text", ""),
                "time": str(row.get("created_at", ""))[-8:],
                "read": bool(row.get("read", False)),
                "incident_id": row.get("incident_id"),
                "correlation_status": row.get("correlation_status"),
                "event_id": row.get("event_id"),
                "farm_key": row.get("farm_key"),
                "severity": row.get("severity"),
                "workflow_name": row.get("workflow_name"),
                "workflow_id": row.get("workflow_id"),
                "workflow_run_id": row.get("workflow_run_id"),
                "scenario_run_id": row.get("scenario_run_id"),
                "command_id": row.get("command_id"),
                "node_id": row.get("node_id"),
                "scenario_code": row.get("scenario_code"),
                "monitor_id": row.get("monitor_id"),
                "workflow_status": row.get("workflow_status"),
                "verification_status": row.get("verification_status"),
                "synthetic": bool(row.get("synthetic", False)),
            }
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


def _virtual_plc_payload(farm_key: str = "greenhouse_a") -> dict[str, Any]:
    """Snapshot the cloud-hosted virtual PLC outputs for the app UI."""
    with _virtual_outputs_lock:
        farm_state = _farm_actuator_state(farm_key)
        outputs = list(farm_state["outputs"])
        safe_mode_active = bool(farm_state["safe_mode_active"])
        vent_command = int(farm_state["vent_command"])
        vent_state = int(farm_state["vent_state"])
        vent_stuck = bool(farm_state["vent_stuck"])
        valve_command = int(farm_state["valve_command"])
        valve_state = int(farm_state["valve_state"])
    payload: dict[str, Any] = {
        "device_name": "SMIOT Virtual PLC",
        "device_id": f"smiot-virtual-plc-{farm_key}",
        "farm_key": farm_key,
        "source": "smiot_demo_stream",
        "simulated": True,
        "online": 1,
        "safe_mode_active": safe_mode_active,
        "vent_cmd": vent_command,
        "vent_state": vent_state,
        "fan_rpm": 1450 if vent_state else 0,
        "fault": "vent_feedback_mismatch" if vent_stuck and vent_command != vent_state else None,
        "valve_cmd": valve_command,
        "valve_state": valve_state,
        "event": "plc_status",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    for index, value in enumerate(outputs):
        payload[f"q{index}"] = value
        payload[f"bit{index}"] = value
    return payload


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _publish_scenario_ack(client: mqtt.Client, *, command_id: str, scenario_run_id: str,
                          status: str, applied: bool, scenario_type: str,
                          farm_key: str, node_id: int | None = None,
                          lot_id: str | None = None, seed: int | None = None,
                          scenario_code: str | None = None,
                          reason: str | None = None, started_at: str | None = None,
                          ended_at: str | None = None) -> None:
    """Report applied virtual-device state; the app can persist the scenario truth separately."""
    ack: dict[str, Any] = {
        "event": "scenario_ack", "status": status, "applied": applied,
        "command_id": command_id, "scenario_run_id": scenario_run_id,
        "scenario_type": scenario_type, "farm_key": farm_key,
        "source": "smiot_demo_stream", "synthetic": True,
        "timestamp": _utc_now_text(),
    }
    if node_id is not None:
        ack["node_id"] = node_id
    if scenario_code:
        ack["scenario_code"] = scenario_code
    if lot_id:
        ack["lot_id"] = lot_id
    if seed is not None:
        ack["seed"] = seed
    if reason:
        ack["reason"] = reason
    if started_at:
        ack["started_at"] = started_at
    if ended_at:
        ack["ended_at"] = ended_at
    info = client.publish("farm/demo/status", json.dumps(ack, separators=(",", ":")), qos=1)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"scenario ACK publish failed: rc={info.rc}")


def _scenario_for(farm_key: str, node_id: int | None = None) -> dict[str, Any] | None:
    """Return the newest matching run without exposing its expected label to telemetry."""
    with _virtual_outputs_lock:
        for run in reversed(list(_active_scenarios.values())):
            if run["farm_key"] != farm_key:
                continue
            if run.get("node_id") is not None and node_id is not None and run["node_id"] != node_id:
                continue
            return run
    return None


def _on_virtual_control(client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
    """Apply virtual PLC controls, safe-mode actions, and sensor fault injection."""
    global _node2_flatline, _active_demo_incident_id
    try:
        command = json.loads(message.payload.decode("utf-8"))
        if not isinstance(command, dict):
            return
        if command.get("action") == "EXTERNAL_SOURCE_HEARTBEAT":
            farm_key = str(command.get("farm_key") or "").strip()
            device_key = str(command.get("device_key") or "").strip()
            source = str(command.get("source") or "").strip()
            if farm_key in FARMS and device_key in {"node1", "node2", "flow"} and source == "velxio_synthetic":
                with _external_source_lock:
                    _external_source_last_seen[(farm_key, device_key)] = time.monotonic()
            return
        changed: list[str] = []
        action = str(command.get("action", ""))
        command_id = str(command.get("command_id") or f"virtual-{uuid4()}")[:200]

        # Seeded scenario controls are separate from observation data. Only the
        # opaque scenario_run_id is copied onto telemetry; expected fault labels
        # remain in this virtual-device control/ACK channel for the app ledger.
        if action == "START_SCENARIO":
            requested_type = str(command.get("scenario_type", ""))[:80]
            scenario_spec = resolve_scenario(requested_type)
            scenario_type = canonical_type(requested_type) or requested_type
            scenario_code = str((scenario_spec or {}).get("code") or "")
            scenario_run_id = str(command.get("scenario_run_id") or uuid4())[:128]
            farm_key = str(command.get("farm_key", "greenhouse_a")).strip()[:80]
            node_value = command.get("node_id")
            node_id: int | None = None
            lot_id = str(command.get("lot_id") or "").strip()[:128] or None
            try:
                default_node = ((scenario_spec or {}).get("group") in {"S", "D"}
                                or (scenario_spec or {}).get("domain") == "crop_climate")
                node_id = int(node_value) if node_value is not None else (2 if default_node else None)
                seed = int(command.get("seed", 1))
            except (TypeError, ValueError):
                _publish_scenario_ack(client, command_id=command_id, scenario_run_id=scenario_run_id,
                    status="rejected", applied=False, scenario_type=scenario_type,
                    farm_key=farm_key, node_id=node_id, lot_id=lot_id,
                    scenario_code=scenario_code or None,
                    reason="invalid_node_or_seed")
                return
            if abs(seed) > 2**32 - 1:
                seed = seed % (2**32)
            if scenario_type not in SUPPORTED_SCENARIOS:
                _publish_scenario_ack(client, command_id=command_id, scenario_run_id=scenario_run_id,
                    status="rejected", applied=False, scenario_type=scenario_type,
                    farm_key=farm_key, node_id=node_id, lot_id=lot_id, seed=seed,
                    scenario_code=scenario_code or None,
                    reason="unsupported_scenario")
                return
            if (farm_key not in FARMS or (node_id is not None and node_id not in VIRTUAL_NODE_IDS)
                    or (lot_id is not None and VIRTUAL_LOT_IDS.get(farm_key) != lot_id)):
                _publish_scenario_ack(client, command_id=command_id, scenario_run_id=scenario_run_id,
                    status="rejected", applied=False, scenario_type=scenario_type,
                    farm_key=farm_key, node_id=node_id, lot_id=lot_id, seed=seed,
                    scenario_code=scenario_code or None,
                    reason="invalid_scope")
                return
            with _virtual_outputs_lock:
                farm_state = _farm_actuator_state(farm_key)
                if farm_state["safe_mode_active"] and scenario_type in {
                    "water_overrun", "a1_water_overrun", "a2_pump_pressure_zero",
                    "a3_low_flow", "pipe_leak",
                }:
                    rejected_reason = "safe_mode_active"
                elif scenario_run_id in _active_scenarios:
                    rejected_reason = "scenario_run_already_active"
                elif any(r.get("farm_key") == farm_key and _scenario_resources_conflict(r, scenario_spec, node_id)
                         for r in _active_scenarios.values()):
                    rejected_reason = "scenario_resource_already_active"
                else:
                    rejected_reason = None
                    run = {
                        "scenario_run_id": scenario_run_id,
                        "scenario_type": scenario_type,
                        "scenario_code": scenario_code or None,
                        "scenario_group": (scenario_spec or {}).get("group") or (scenario_spec or {}).get("domain"),
                        "farm_key": farm_key,
                        "node_id": node_id,
                        "lot_id": lot_id,
                        "seed": seed,
                        "rng": random.Random(seed),
                        "started_at": _utc_now_text(),
                        "started_monotonic": time.monotonic(),
                        "remaining_samples": 1 if scenario_type == "soil_spike" else None,
                        "scenario_state": {},
                        "crop_context": _load_crop_scenario_context(farm_key)
                            if str(scenario_code).startswith("C") else {},
                    }
                    _active_scenarios[scenario_run_id] = run
                    if scenario_type == "soil_flatline":
                        if farm_key == "greenhouse_a" and node_id in (None, 2):
                            _node2_flatline = True
                    elif scenario_type in {"water_overrun", "a1_water_overrun", "a2_pump_pressure_zero", "a3_low_flow"}:
                        farm_state["outputs"][0] = 1
                        _pump_started_at[(farm_key, 0)] = time.monotonic()
                        _pump_volume_l[(farm_key, 0)] = 0.0
                        farm_state["valve_command"] = 1
                        farm_state["valve_state"] = 1
                        if scenario_type == "a2_pump_pressure_zero":
                            farm_state["fault"] = "pump_pressure_zero"
                        elif scenario_type == "a3_low_flow":
                            farm_state["fault"] = "pump_low_flow"
                        changed.append("bit0")
                    elif scenario_type == "pipe_leak":
                        farm_state["outputs"][0] = 1
                        _pump_started_at[(farm_key, 0)] = time.monotonic()
                        _pump_volume_l[(farm_key, 0)] = 0.0
                        farm_state["valve_command"] = 1
                        farm_state["valve_state"] = 1
                        farm_state["fault"] = "low_pressure_high_flow"
                        changed.append("bit0")
                    elif scenario_type in {"vent_stuck", "a5_vent_stuck"}:
                        farm_state["vent_stuck"] = True
                        farm_state["vent_command"] = 1
                        farm_state["vent_state"] = 0
                    elif scenario_code == "A7":
                        farm_state["outputs"] = [0] * len(farm_state["outputs"])
                        farm_state["valve_command"] = 0
                        farm_state["valve_state"] = 0
                        farm_state["safe_mode_active"] = True
                        farm_state["fault"] = "tank_level_low"
                        for index in range(len(farm_state["outputs"])):
                            _pump_started_at.pop((farm_key, index), None)
                            _pump_volume_l.pop((farm_key, index), None)
                        changed.append("safe_stop_dry_run")
                    if scenario_code == "D2":
                        try:
                            from pages.home import state as home_state
                            from service.datadog_metrics import emit_health_gauge, metric_tags
                            target_node = node_id or 2
                            status_key = f"node{target_node}_status"
                            run["ui_previous_status"] = home_state.get(status_key)
                            home_state["fault_stale_cache"] = {
                                "node": target_node, "farm": farm_key, "synthetic": True,
                                "label": "synthetic_injected_stale_cache",
                                "scenario_run_id": scenario_run_id,
                                "started_at": time.time(), "expires_at": time.time() + 3600,
                            }
                            home_state[status_key] = "OFFLINE"
                            home_state["_update_counter"] = home_state.get("_update_counter", 0) + 1
                            emit_health_gauge(
                                "smiot.telemetry.status_mismatch", 1,
                                metric_tags(farm_key, target_node, "smiot_demo_stream"),
                            )
                        except Exception as exc:
                            LOGGER.warning("Could not apply synthetic UI-only fault (%s)", type(exc).__name__)
            if rejected_reason:
                _publish_scenario_ack(client, command_id=command_id, scenario_run_id=scenario_run_id,
                    status="rejected", applied=False, scenario_type=scenario_type,
                    farm_key=farm_key, node_id=node_id, lot_id=lot_id, seed=seed,
                    reason=rejected_reason)
                return
            if changed:
                plc_status = _virtual_plc_payload(farm_key)
                plc_status.update({"scenario_run_id": scenario_run_id, "command_id": command_id,
                                   "action": action, "farm_key": farm_key})
                client.publish("farm/status", json.dumps(plc_status, separators=(",", ":")), qos=1)
            _publish_scenario_ack(client, command_id=command_id, scenario_run_id=scenario_run_id,
                status="started", applied=True, scenario_type=scenario_type,
                farm_key=farm_key, node_id=node_id, lot_id=lot_id, seed=seed,
                scenario_code=scenario_code or None,
                started_at=run["started_at"])
            return

        if action == "STOP_SCENARIO":
            scenario_run_id = str(command.get("scenario_run_id", ""))[:128]
            with _virtual_outputs_lock:
                run = _active_scenarios.pop(scenario_run_id, None)
                if run:
                    farm_key = run["farm_key"]
                    farm_state = _farm_actuator_state(farm_key)
                    if run["scenario_type"] == "soil_flatline":
                        _node2_flatline = any(
                            r.get("scenario_type") == "soil_flatline"
                            and r.get("farm_key") == "greenhouse_a"
                            and r.get("node_id") in (None, 2)
                            for r in _active_scenarios.values()
                        )
                    elif run["scenario_type"] in {"water_overrun", "a1_water_overrun",
                                                  "a2_pump_pressure_zero", "a3_low_flow"}:
                        farm_state["outputs"][0] = 0
                        _pump_started_at.pop((farm_key, 0), None)
                        _pump_volume_l.pop((farm_key, 0), None)
                        farm_state["valve_command"] = 0
                        farm_state["valve_state"] = 0
                        if farm_state.get("fault") in {"pump_pressure_zero", "pump_low_flow"}:
                            farm_state["fault"] = None
                    elif run["scenario_type"] == "pipe_leak":
                        farm_state["outputs"] = [0] * len(farm_state["outputs"])
                        farm_state["valve_command"] = 0
                        farm_state["valve_state"] = 0
                        for index in range(len(farm_state["outputs"])):
                            _pump_started_at.pop((farm_key, index), None)
                            _pump_volume_l.pop((farm_key, index), None)
                    elif run["scenario_type"] in {"vent_stuck", "a5_vent_stuck"}:
                        farm_state["vent_stuck"] = False
                        farm_state["vent_command"] = 0
                        farm_state["vent_state"] = 0
                    # Drill finished: release the virtual PLC safety latch that the
                    # interlock or a HOLD set, unless another run is still active on this farm.
                    if not any(r.get("farm_key") == farm_key for r in _active_scenarios.values()):
                        farm_state["safe_mode_active"] = False
                        farm_state["fault"] = None
                    if run.get("scenario_code") == "D2":
                        try:
                            from pages.home import state as home_state
                            from service.datadog_metrics import emit_health_gauge, metric_tags
                            fault = home_state.get("fault_stale_cache") or {}
                            if fault.get("scenario_run_id") == scenario_run_id:
                                home_state.pop("fault_stale_cache", None)
                                status_key = f"node{run.get('node_id') or 2}_status"
                                if run.get("ui_previous_status") is None:
                                    home_state.pop(status_key, None)
                                else:
                                    home_state[status_key] = run["ui_previous_status"]
                                home_state["_update_counter"] = home_state.get("_update_counter", 0) + 1
                            emit_health_gauge(
                                "smiot.telemetry.status_mismatch", 0,
                                metric_tags(farm_key, int(run.get("node_id") or 2), "smiot_demo_stream"),
                            )
                        except Exception as exc:
                            LOGGER.warning("Could not clear synthetic UI-only fault (%s)", type(exc).__name__)
            if run:
                stopped_at = _utc_now_text()
                status_payload = _virtual_plc_payload(run["farm_key"])
                status_payload.update({"scenario_run_id": scenario_run_id, "command_id": command_id,
                    "action": action, "farm_key": run["farm_key"]})
                client.publish("farm/status", json.dumps(status_payload, separators=(",", ":")), qos=1)
                _publish_scenario_ack(client, command_id=command_id, scenario_run_id=scenario_run_id,
                    status="stopped", applied=True, scenario_type=run["scenario_type"],
                    farm_key=run["farm_key"], node_id=run.get("node_id"), lot_id=run.get("lot_id"),
                    seed=run.get("seed"), scenario_code=run.get("scenario_code"),
                    started_at=run.get("started_at"), ended_at=stopped_at)
            else:
                _publish_scenario_ack(client, command_id=command_id, scenario_run_id=scenario_run_id,
                    status="rejected", applied=False, scenario_type="unknown",
                    farm_key=str(command.get("farm_key", "greenhouse_a")),
                    reason="scenario_run_not_active")
            return

        # SYNTHETIC: lenh tiem loi "cache hien thi cu" chi lam sai lop hien thi, khong chan ghi MongoDB.
        ui_fault = command.get("demo_ui_fault")
        if ui_fault in ("stale_cache", "normal"):
            from pages.home import state as home_state
            node = int(command.get("node", 1)); farm = str(command.get("farm", "greenhouse_a"))
            if ui_fault == "stale_cache":
                minutes = max(1, min(int(command.get("minutes", 6)), 30))
                home_state["fault_stale_cache"] = {"node": node, "farm": farm, "synthetic": True,
                    "label": "synthetic_injected_stale_cache",
                    "started_at": time.time(), "expires_at": time.time() + minutes * 60}
                home_state[f"node{node}_status"] = "OFFLINE"
            else:
                home_state.pop("fault_stale_cache", None)
            home_state["_update_counter"] = home_state.get("_update_counter", 0) + 1
            client.publish("farm/demo/status", json.dumps({"demo_ui_fault": ui_fault, "node": node,
                           "farm": farm, "synthetic": True}, separators=(",", ":")), qos=1)
            return
        detector_fault = command.get("demo_detector_fault")
        if detector_fault in ("stalled", "normal"):
            # Synthetic W6-only control: never stops the app or any dependency.
            if command.get("synthetic") is not True:
                return
            farm = str(command.get("farm_key") or command.get("farm") or "").strip()
            from service.detector_heartbeat import set_demo_evaluation_fault
            from service.special_incident_correlation import (
                active_special_incident, ensure_special_incident, record_special_event,
            )
            incident_id = str(command.get("incident_id") or "").strip() or None
            if detector_fault == "stalled":
                incident_id = ensure_special_incident(
                    "detector_heartbeat_missing", farm,
                    incident_id=incident_id, monitor_id=command.get("monitor_id") or "343029221",
                    workflow_id=command.get("workflow_id") or "d8e1b3db-86f3-4d47-9d4c-1e1e4c0f86f3",
                    command_id=command_id,
                    details={"fault": "evaluation_heartbeat_stalled", "detector": "agronomic_advisory"},
                )
                _w6_incidents_by_farm[farm] = incident_id
            elif not incident_id:
                incident_id = _w6_incidents_by_farm.get(farm)
                if not incident_id:
                    active = active_special_incident("detector_heartbeat_missing", farm)
                    incident_id = str(active.get("_id")) if active else None
            applied = set_demo_evaluation_fault(farm, detector_fault == "stalled")
            if incident_id:
                record_special_event(
                    incident_id,
                    "detector_fault_injected" if detector_fault == "stalled" else "detector_recovery_requested",
                    farm_key=farm, details={"command_id": command_id, "mode": detector_fault},
                    status="open" if detector_fault == "stalled" else "recovering",
                )
            ack = {
                "event": "detector_fault_ack",
                "demo_detector_fault": detector_fault,
                "farm_key": farm,
                "mode_applied": bool(applied),
                "applied": bool(applied),
                "command_id": command_id,
                "incident_id": incident_id,
                "source": "smiot_demo_stream",
                "synthetic": True,
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            }
            client.publish("farm/demo/status", json.dumps(ack, separators=(",", ":")), qos=1)
            return
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
                "applied": True,
                "command_id": command_id,
                "source": "smiot_demo_stream",
                "simulated": True,
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            }
            client.publish("farm/demo/status", json.dumps(ack, separators=(",", ":")), qos=1)
        command_farm = str(command.get("farm_key", "greenhouse_a"))
        if command_farm not in FARMS:
            command_farm = "greenhouse_a"
        rejected_on_command = False
        recognized_action = action in {"HOLD", "CLEAR", "SAFE_STOP", "STOP_PUMPS", "SET_VENT", "SET_VALVE"}
        requested_bits: dict[str, int] = {}
        with _virtual_outputs_lock:
            farm_state = _farm_actuator_state(command_farm)
            if action in {"HOLD", "SAFE_STOP", "STOP_PUMPS"}:
                farm_state["safe_mode_active"] = True
                farm_state["valve_command"] = 0
                farm_state["valve_state"] = 0
                for index, current in enumerate(farm_state["outputs"]):
                    if current:
                        changed.append(f"bit{index}")
                    farm_state["outputs"][index] = 0
                    _pump_started_at.pop((command_farm, index), None)
                    _pump_volume_l.pop((command_farm, index), None)
            elif action == "CLEAR":
                # Recovery clears the latch but never turns a pump on.
                farm_state["safe_mode_active"] = False
                farm_state["fault"] = None
            if action == "SET_VENT" or "vent_cmd" in command:
                vent_value = command.get("vent_cmd", command.get("enabled", 0))
                if vent_value in (0, 1, False, True, "0", "1"):
                    farm_state["vent_command"] = int(vent_value in (1, True, "1"))
                    farm_state["vent_state"] = 0 if farm_state["vent_stuck"] else farm_state["vent_command"]
                    changed.append("vent_cmd")
            if action == "SET_VALVE" or "valve_cmd" in command:
                valve_value = command.get("valve_cmd", command.get("enabled", 0))
                if valve_value in (0, 1, False, True, "0", "1"):
                    requested_valve = int(valve_value in (1, True, "1"))
                    if (farm_state["safe_mode_active"] or action == "CLEAR") and requested_valve:
                        rejected_on_command = True
                    else:
                        farm_state["valve_command"] = requested_valve
                        farm_state["valve_state"] = requested_valve
                        changed.append("valve_cmd")
            for index in range(8):
                key = f"bit{index}"
                value = command.get(key)
                if value in (0, 1, False, True, "0", "1"):
                    requested = int(value in (1, True, "1"))
                    requested_bits[key] = requested
                    recognized_action = True
                    if action == "CLEAR" and requested:
                        rejected_on_command = True
                        continue
                    if farm_state["safe_mode_active"] and requested:
                        rejected_on_command = True
                        continue
                    farm_state["outputs"][index] = requested
                    changed.append(key)
                    if requested:
                        _pump_started_at.setdefault((command_farm, index), time.monotonic())
                        _pump_volume_l.setdefault((command_farm, index), 0.0)
                    else:
                        _pump_started_at.pop((command_farm, index), None)
                        _pump_volume_l.pop((command_farm, index), None)
        has_actuator_request = action in {"SET_VENT", "SET_VALVE"} or "vent_cmd" in command or "valve_cmd" in command
        recognized_action = recognized_action or has_actuator_request
        if not changed and not recognized_action and not rejected_on_command:
            return

        response = _virtual_plc_payload(command_farm)
        w9_drill = (command.get("w9_late_ack_drill") is True
                    and command.get("synthetic") is True
                    and command_farm == "greenhouse_j"
                    and action == "SET_OUTPUTS"
                    and requested_bits
                    and all(value == 0 for value in requested_bits.values()))
        if w9_drill:
            from service.special_incident_correlation import ensure_special_incident, record_special_event
            w9_incident_id = ensure_special_incident(
                "actuator_no_ack", command_farm,
                incident_id=command.get("incident_id"), monitor_id=command.get("monitor_id") or "342734743",
                workflow_id=command.get("workflow_id") or "47e95b24-db40-4cd5-b667-5b90e170b667",
                command_id=command_id,
                details={"actuator": "plc_pump", "channel": "q0", "fault": "ack_withheld"},
            )
            command["incident_id"] = w9_incident_id
            # This command is intentionally kept in the same pending-command
            # ledger as a real farm/control command so the timeout checker can
            # emit W9 evidence and a later matching ACK can close it.
            from pages.home import state as home_state
            pending = home_state.setdefault("actuator_pending_by_command", {})
            now = time.time()
            record_id = f"{command_id}|q0"
            pending[record_id] = {
                "command_id": command_id, "farm_key": command_farm,
                "actuator": "plc_pump", "channel": "q0", "target": 0,
                "requested_at": now, "ack_deadline": now + 10.0,
                "status": "pending", "timeout_emitted": False,
                "synthetic": True, "incident_id": w9_incident_id,
                "monitor_id": "342734743",
            }
            record_special_event(w9_incident_id, "actuator_command_sent", farm_key=command_farm,
                                 details={"command_id": command_id, "actuator": "plc_pump", "channel": "q0"})
        response.update({
            "command_id": command_id,
            "action": action or "SET_OUTPUTS",
            "execution_id": command.get("execution_id"),
            "incident_id": command.get("incident_id"),
            "farm_key": command_farm,
            "source": "smiot_demo_stream",
            "synthetic": True,
        })
        # In the W9 drill, status telemetry is intentionally not an ACK. Keep
        # the virtual readback, but omit the command ID so the app cannot close
        # the pending command through its normal device-readback path.
        if w9_drill:
            response.pop("command_id", None)
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
        expected_bits_match = all(response.get(key) == value for key, value in requested_bits.items())
        ack = {
            "event": "virtual_plc_command_ack", "command_id": command_id,
            "action": action or "SET_OUTPUTS", "farm_key": command.get("farm_key", "greenhouse_a"),
            "node_id": command.get("node_id"), "monitor_id": command.get("monitor_id"),
            "workflow_id": command.get("workflow_id"), "execution_id": command.get("execution_id"),
            "incident_id": command.get("incident_id"), "reason": command.get("reason", ""),
            "source": "smiot_demo_stream", "target": "smiot_virtual_plc", "synthetic": True,
            "applied": not rejected_on_command,
            "verified": not rejected_on_command and expected_bits_match
                and all(response[f"bit{i}"] == 0 for i in range(8)
                        if action in {"HOLD", "SAFE_STOP", "STOP_PUMPS"})
                and (action not in {"HOLD", "SAFE_STOP", "STOP_PUMPS"}
                     or response.get("valve_state") == 0),
            "virtual_output": {f"bit{i}": response[f"bit{i}"] for i in range(8)},
            "vent_cmd": response.get("vent_cmd"), "vent_state": response.get("vent_state"),
            "valve_cmd": response.get("valve_cmd"), "valve_state": response.get("valve_state"),
            "safe_mode_active": response["safe_mode_active"],
            "timestamp": response["timestamp"],
        }
        # W9 drill-only path: the virtual PLC applies a bounded all-off command,
        # but deliberately withholds only its ACK. This is synthetic-only and
        # cannot energize an output or affect a physical device.
        if w9_drill:
            LOGGER.warning("W9 synthetic drill applied safe OFF command and withheld ACK: command_id=%s farm=%s",
                           command_id, command_farm)
            return
        ack_info = client.publish("farm/command/ack", json.dumps(ack, separators=(",", ":")), qos=1)
        if ack_info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"virtual-device ACK publish failed: rc={ack_info.rc}")
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


def _farm_sensor_payload(farm_key: str, rng: random.Random, total: dict[str, Any],
                         device_key: str | None = None) -> dict[str, Any]:
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
    node2 = {
        "at": round(29.7 + offset + rng.uniform(-0.5, 0.5), 1),
        "ah": round(79 + rng.uniform(-2.0, 2.0), 1),
        "st": round(26.2 + offset * 0.2 + rng.uniform(-0.4, 0.4), 1),
        "sh": round(40 + rng.uniform(-1.4, 1.4), 1),
        "sec": round(1.2 + rng.uniform(-0.07, 0.07), 2),
    }
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    monotonic_now = time.monotonic()
    # Initialize farm-scoped cumulative flow counters before any device packet
    # is assembled; node-only packets also carry the current totalizer snapshot.
    total.setdefault(f"__flow_line1_l__:{farm_key}", 0.0)
    total.setdefault(f"__flow_line2_l__:{farm_key}", 0.0)
    active_runs: list[dict[str, Any]] = []
    with _virtual_outputs_lock:
        incident_id = _active_demo_incident_id
        _sample_sequence += 1
        envelope_sequence = _sample_sequence
        for node_id, node in ((1, node1), (2, node2)):
            sequence_key = (farm_key, node_id)
            if device_key in (None, f"node{node_id}"):
                _sample_sequences[sequence_key] = _sample_sequences.get(sequence_key, 0) + 1
            if device_key in (None, f"node{node_id}"):
                node.update({
                "timestamp": timestamp,
                "measured_at": timestamp,
                "boot_id": f"{_publisher_boot_id}:{farm_key}:node{node_id}",
                "sample_sequence": _sample_sequences[sequence_key],
                "uptime_seconds": int(time.monotonic() - _publisher_started_monotonic),
                "device_id": f"smiot-virtual-{farm_key}-node{node_id}",
                "node_id": node_id,
                "farm_key": farm_key,
                "source": "smiot_demo_stream",
                "synthetic": True,
                })
        for run in _active_scenarios.values():
            if run.get("farm_key") == farm_key:
                active_runs.append(run)
        vent_run = next((r for r in reversed(active_runs)
                         if r.get("scenario_type") in {"vent_stuck", "a5_vent_stuck"}), None)
        water_run = next((r for r in reversed(active_runs)
                          if r.get("scenario_type") in {"water_overrun", "a1_water_overrun"}), None)
        pressure_zero_run = next((r for r in reversed(active_runs)
                                  if r.get("scenario_type") == "a2_pump_pressure_zero"), None)
        low_flow_run = next((r for r in reversed(active_runs)
                             if r.get("scenario_type") == "a3_low_flow"), None)
        pipe_leak_run = next((r for r in reversed(active_runs)
                              if r.get("scenario_type") == "pipe_leak"), None)
        farm_state = _farm_actuator_state(farm_key)
        outputs = list(farm_state["outputs"])
        vent_cmd = farm_state["vent_command"]
        vent_state = farm_state["vent_state"]
        vent_stuck = farm_state["vent_stuck"]
        valve_state = farm_state["valve_state"]
        for node_id, node in ((1, node1), (2, node2)):
            if vent_run:
                elapsed = max(0.0, monotonic_now - float(vent_run.get("started_monotonic", monotonic_now)))
                node["at"] = round(min(39.0, 29.5 + elapsed * 0.045), 1)
                node["scenario_run_id"] = vent_run["scenario_run_id"]
        if farm_key == "greenhouse_a" and _node2_flatline:
            # Legacy demo switch remains compatible with the existing incident route.
            node2["sh"] = 2.4

    # Flow is tied to virtual pump outputs. With pumps off, measured flow is zero.
    line1_on = any(outputs[:4]) and bool(valve_state)
    line2_on = any(outputs[4:]) and bool(valve_state)
    flow_rate = (VIRTUAL_PLC_LEAK_FLOW_LPM if pipe_leak_run else
                 0.1 if low_flow_run else
                 12.0 if water_run else VIRTUAL_PLC_FLOW_LPM)
    flow_rng = (pipe_leak_run["rng"] if pipe_leak_run else
                low_flow_run["rng"] if low_flow_run else water_run["rng"] if water_run else rng)
    flow1 = round(flow_rate + flow_rng.uniform(-0.25, 0.25), 2) if line1_on else 0.0
    flow2 = round(flow_rate * 0.82 + flow_rng.uniform(-0.2, 0.2), 2) if line2_on else 0.0
    pressure_bar = (0.0 if pressure_zero_run and (line1_on or line2_on) else
                    0.2 if pipe_leak_run and (line1_on or line2_on) else
                    1.6 if (line1_on or line2_on) else 0.0)
    last_key = f"__flow_last_monotonic__:{farm_key}"
    if device_key in (None, "flow"):
        last_sample = float(total.get(last_key, monotonic_now - FLOW_IDLE_INTERVAL_SECONDS))
        elapsed_seconds = max(0.0, min(300.0, monotonic_now - last_sample))
        total[last_key] = monotonic_now
        total[f"__flow_line1_l__:{farm_key}"] = float(total.get(f"__flow_line1_l__:{farm_key}", 0.0)) + flow1 * elapsed_seconds / 60.0
        total[f"__flow_line2_l__:{farm_key}"] = float(total.get(f"__flow_line2_l__:{farm_key}", 0.0)) + flow2 * elapsed_seconds / 60.0
        runoff_l = round((flow1 + flow2) * elapsed_seconds / 60.0 * 0.14, 3)
    else:
        runoff_l = 0.0
    scenario_run_id = next((r["scenario_run_id"] for r in reversed(active_runs)
                            if r.get("scenario_type") in SUPPORTED_SCENARIOS), None)
    lot_id = next((r.get("lot_id") for r in reversed(active_runs) if r.get("lot_id")), None)
    payload = {
        "device_name": "SMIOT Synthetic Demo", "farm_key": farm_key,
        "timestamp": timestamp, "source": "smiot_demo_stream",
        "device_id": f"smiot-virtual-{farm_key}", "boot_id": _publisher_boot_id,
        "sample_sequence": envelope_sequence, "synthetic": True,
        "id6": {"node1": node1, "node2": node2},
        "id3": {"f1": flow1, "f2": flow2,
                "pressure_bar": pressure_bar,
                "safe_mode_active": bool(farm_state["safe_mode_active"]),
                "fault": farm_state.get("fault") or ("low_pressure_high_flow" if pipe_leak_run else None),
                "t1": round(float(total[f"__flow_line1_l__:{farm_key}"]), 3),
                "t2": round(float(total[f"__flow_line2_l__:{farm_key}"]), 3),
                "pump_line1_on": bool(line1_on), "pump_line2_on": bool(line2_on),
                "valve_open": bool(valve_state),
                "measured_at": timestamp, "timestamp": timestamp, "synthetic": True},
        "id4": {"ec": round(1.35 + (farm_index - (len(FARMS) - 1) / 2) * 0.02 + rng.uniform(-0.08, 0.08), 2), "v": 2.5, "raw": rng.randint(1800, 2300), "online": 1, "timestamp": timestamp},
        "id5": {"ph": round(6.7 + rng.uniform(-0.25, 0.25), 2), "mv": round(130 + rng.uniform(-12, 12), 1), "raw": rng.randint(1700, 2200), "online": 1, "timestamp": timestamp},
        # Independent virtual-device channels. The publisher emits one channel per
        # device identity so farm-level ingestion and per-device freshness stay clear.
        "id7": {"device_type": "drain_sensor", "drain_l": runoff_l,
                "drain_ec_ms_cm": round(1.35 + (farm_index - (len(FARMS) - 1) / 2) * 0.02 + rng.uniform(-0.05, 0.05), 2),
                "timestamp": timestamp, "measured_at": timestamp, "source": "smiot_demo_stream", "synthetic": True},
        "id8": {"device_type": "ventilation_feedback", "command": int(vent_cmd),
                "state": int(vent_state), "fan_rpm": 1450 if vent_state else 0,
                "stuck": bool(vent_stuck), "timestamp": timestamp,
                "measured_at": timestamp, "source": "smiot_demo_stream", "synthetic": True},
    }
    # Apply typed, synthetic domain overlays only in the virtual publisher. Fault
    # labels and detector results travel on the separate evidence topic below.
    scenario_observations: list[dict[str, Any]] = []
    if device_key in {"node1", "node2"}:
        published_node_id = int(device_key[-1])
        for active_run in active_runs:
            code = str(active_run.get("scenario_code") or "")
            if not code:
                continue
            if active_run.get("node_id") not in (None, published_node_id):
                continue
            if code[:1] in {"S", "D"}:
                try:
                    result = _scenario_observation(
                        active_run, payload,
                        int(_sample_sequences.get((farm_key, published_node_id), 0)),
                    )
                    if isinstance(result.get("_overlay_payload"), dict) and code != "D6":
                        payload = result.pop("_overlay_payload")
                        node_key = f"node{published_node_id}"
                        node_evidence = payload.get("id6", {}).get(node_key)
                        if isinstance(node_evidence, dict):
                            node_evidence["scenario_run_id"] = active_run["scenario_run_id"]
                    elif code == "D6":
                        result.pop("_overlay_payload", None)
                        result["status"] = "control_only"
                        result["response"] = "QUARANTINE_UNREGISTERED_DEVICE"
                        result["reason"] = (
                            "No device registry is connected to ingestion, so this scenario remains on "
                            "the control/evidence channel instead of attributing an unknown device to a farm."
                        )
                    result.pop("_overlay", None)
                    scenario_observations.append(result)
                except (ValueError, TypeError) as exc:
                    scenario_observations.append({
                        "event": "scenario_observation", "scenario_code": code,
                        "scenario_type": active_run.get("scenario_type"),
                        "scenario_run_id": active_run["scenario_run_id"],
                        "farm_key": farm_key, "node_id": published_node_id,
                        "observed_at": timestamp, "domain": "sensor_device",
                        "status": "blocked", "response": "HOLD",
                        "reason": str(exc)[:200], "synthetic": True,
                        "execution_mode": "SIMULATED_ONLY",
                    })
            elif code.startswith("C"):
                if device_key != "node2":
                    continue
                result = _scenario_observation(active_run, payload, 0)
                overlay = result.pop("_overlay", None)
                if isinstance(overlay, dict):
                    from service.scenario_domain_crops import apply_scenario_overlay
                    payload = apply_scenario_overlay(payload, overlay)
                    target_key = next(iter(overlay.get("id6", {}) or {}), None)
                    target = (payload.get("id6", {}).get(target_key) if target_key else None)
                    if isinstance(target, dict):
                        target["scenario_run_id"] = active_run["scenario_run_id"]
                scenario_observations.append(result)
            elif code[:1] in {"A", "H"}:
                if device_key != "node2":
                    continue
                # A/H injections are control-plane observations. They never
                # alter EC2, MongoDB, MQTT, or a real actuator.
                scenario_observations.append(_scenario_observation(active_run, payload, 0))
    if scenario_observations:
        payload["_scenario_control_observations"] = scenario_observations
    if scenario_run_id:
        payload["scenario_run_id"] = scenario_run_id
    if lot_id:
        payload["lot_id"] = lot_id
    if farm_key == "greenhouse_a" and incident_id:
        payload["incident_id"] = incident_id
        payload["lot_id"] = lot_id or VIRTUAL_LOT_IDS.get(farm_key)
    if device_key:
        channel_by_device = {
            "node1": ("id6", {"node1": node1}),
            "node2": ("id6", {"node2": node2}),
            "flow": ("id3", payload["id3"]),
            "ec": ("id4", payload["id4"]),
            "ph": ("id5", payload["id5"]),
            "drain": ("id7", payload["id7"]),
            "ventilation": ("id8", payload["id8"]),
        }
        channel, readings = channel_by_device[device_key]
        payload = {key: value for key, value in payload.items()
                   if key not in {"id3", "id4", "id5", "id6", "id7", "id8"}}
        payload[channel] = readings
    return payload


def _virtual_plc_watchdog_loop(client: mqtt.Client, stop_event: threading.Event) -> None:
    """Enforce pump runtime and volume limits independently for every virtual farm."""
    last_tick = time.monotonic()
    while not stop_event.wait(0.5):
        if not client.is_connected():
            return
        now = time.monotonic()
        elapsed = max(0.0, now - last_tick)
        last_tick = now
        trips: list[dict[str, Any]] = []
        with _virtual_outputs_lock:
            for farm_key in FARMS:
                farm_state = _farm_actuator_state(farm_key)
                water_run = next((r for r in _active_scenarios.values()
                                  if r.get("farm_key") == farm_key
                                  and r.get("scenario_type") in {"water_overrun", "a1_water_overrun"}), None)
                pipe_leak_run = next((r for r in _active_scenarios.values()
                                      if r.get("farm_key") == farm_key and r.get("scenario_type") == "pipe_leak"), None)
                pressure_zero_run = next((r for r in _active_scenarios.values()
                                          if r.get("farm_key") == farm_key
                                          and r.get("scenario_type") == "a2_pump_pressure_zero"), None)
                low_flow_run = next((r for r in _active_scenarios.values()
                                     if r.get("farm_key") == farm_key
                                     and r.get("scenario_type") == "a3_low_flow"), None)
                rate = (VIRTUAL_PLC_LEAK_FLOW_LPM if pipe_leak_run else
                        0.1 if low_flow_run else
                        12.0 if water_run else VIRTUAL_PLC_FLOW_LPM)
                for pump_id, is_on in enumerate(farm_state["outputs"]):
                    pump_key = (farm_key, pump_id)
                    if not is_on:
                        _pump_started_at.pop(pump_key, None)
                        _pump_volume_l.pop(pump_key, None)
                        continue
                    started_at = _pump_started_at.setdefault(pump_key, now)
                    volume = _pump_volume_l.get(pump_key, 0.0) + rate * elapsed / 60.0
                    _pump_volume_l[pump_key] = volume
                    run_seconds = now - started_at
                    observed_pressure_bar = 0.0 if pressure_zero_run else 0.2 if pipe_leak_run else 1.6
                    leak_trip = bool(
                        pipe_leak_run
                        and rate >= VIRTUAL_PLC_LEAK_MIN_FLOW_LPM
                        and observed_pressure_bar <= VIRTUAL_PLC_LOW_PRESSURE_BAR
                    )
                    pressure_trip = bool(pressure_zero_run and observed_pressure_bar <= 0.0)
                    low_flow_trip = bool(low_flow_run and run_seconds >= 5 and rate < 0.5)
                    if (leak_trip or pressure_trip or low_flow_trip
                            or run_seconds >= VIRTUAL_PLC_MAX_RUN_SECONDS
                            or volume >= VIRTUAL_PLC_MAX_VOLUME_L):
                        trip_reason = ("low_pressure_high_flow" if leak_trip else
                                       "pump_pressure_zero" if pressure_trip else
                                       "pump_low_flow" if low_flow_trip else
                                       "max_runtime" if run_seconds >= VIRTUAL_PLC_MAX_RUN_SECONDS else "max_volume")
                        trips.append({
                            "pump_id": pump_id, "run_seconds": round(run_seconds, 2),
                            "volume_l": round(volume, 3),
                            "scenario_run_id": (pipe_leak_run or pressure_zero_run or low_flow_run or water_run).get("scenario_run_id")
                                if (pipe_leak_run or pressure_zero_run or low_flow_run or water_run) else None,
                            "farm_key": farm_key,
                            "reason": trip_reason,
                            "event": "virtual_plc_safety_trip" if (leak_trip or pressure_trip or low_flow_trip)
                                     else "virtual_plc_water_limit_exceeded",
                            "pressure_bar": observed_pressure_bar,
                            "flow_lpm": round(rate, 2),
                        })
                        farm_state["outputs"] = [0] * len(farm_state["outputs"])
                        farm_state["valve_command"] = 0
                        farm_state["valve_state"] = 0
                        farm_state["safe_mode_active"] = True
                        farm_state["fault"] = trip_reason
                        for index in range(len(farm_state["outputs"])):
                            _pump_started_at.pop((farm_key, index), None)
                            _pump_volume_l.pop((farm_key, index), None)
                        break
        for trip in trips:
            command_id = f"virtual-interlock-{uuid4()}"
            stamp = _utc_now_text()
            plc_status = _virtual_plc_payload(trip["farm_key"])
            plc_status.update({
                "event": trip["event"],
                "fault_code": ({
                    "low_pressure_high_flow": "PIPE_PRESSURE_FLOW_MISMATCH",
                    "pump_pressure_zero": "PUMP_PRESSURE_ZERO",
                    "pump_low_flow": "PUMP_FLOW_BELOW_MINIMUM",
                }.get(trip["reason"], "PUMP_RUNTIME_OR_VOLUME_LIMIT")),
                "reason": trip["reason"], "pump_id": trip["pump_id"],
                "run_seconds": trip["run_seconds"], "estimated_volume_l": trip["volume_l"],
                "pressure_bar": trip["pressure_bar"], "flow_lpm": trip["flow_lpm"],
                "scenario_run_id": trip["scenario_run_id"], "farm_key": trip["farm_key"],
                "command_id": command_id, "source": "smiot_demo_stream", "synthetic": True,
                "timestamp": stamp,
            })
            client.publish("farm/status", json.dumps(plc_status, separators=(",", ":")), qos=1)
            ack = {
                "event": "virtual_interlock_ack",
                "fault_code": ({
                    "low_pressure_high_flow": "PIPE_PRESSURE_FLOW_MISMATCH",
                    "pump_pressure_zero": "PUMP_PRESSURE_ZERO",
                    "pump_low_flow": "PUMP_FLOW_BELOW_MINIMUM",
                }.get(trip["reason"], "PUMP_RUNTIME_OR_VOLUME_LIMIT")),
                "command_id": command_id,
                "action": "SAFE_STOP", "applied": True, "verified": True,
                "farm_key": trip["farm_key"], "scenario_run_id": trip["scenario_run_id"],
                "target": "smiot_virtual_plc", "pump_id": trip["pump_id"],
                "reason": trip["reason"], "estimated_volume_l": trip["volume_l"],
                "pressure_bar": trip["pressure_bar"], "flow_lpm": trip["flow_lpm"],
                "run_seconds": trip["run_seconds"], "safe_mode_active": True,
                "outputs_off": True, "valve_closed": True,
                "source": "smiot_demo_stream", "synthetic": True, "timestamp": stamp,
            }
            client.publish("farm/command/ack", json.dumps(ack, separators=(",", ":")), qos=1)
            LOGGER.warning("Virtual PLC safety interlock stopped %s pump %s: %s",
                           trip["farm_key"], trip["pump_id"], trip["reason"])


def _device_payload(farm_key: str, device_key: str, rng: random.Random,
                    totals: dict[str, Any]) -> dict[str, Any]:
    """Build one independently identified device sample for a farm."""
    payload = _farm_sensor_payload(farm_key, rng, totals, device_key=device_key)
    now = _utc_now_text()
    sequence_key = (farm_key, device_key)
    with _virtual_outputs_lock:
        _device_sequences[sequence_key] = _device_sequences.get(sequence_key, 0) + 1
        sequence = _device_sequences[sequence_key]
    payload.update({
        "device_id": f"smiot-virtual-{farm_key}-{device_key}",
        "device_name": f"SMIOT Virtual {device_key.upper()}",
        "boot_id": f"{_publisher_boot_id}:{farm_key}:{device_key}",
        "sample_sequence": sequence,
        "timestamp": now,
        "measured_at": now,
        "farm_key": farm_key,
        "source": "smiot_demo_stream",
        "synthetic": True,
    })
    return payload


def _publish_loop() -> None:
    rng = random.Random()
    totals: dict[str, Any] = {}
    due: dict[tuple[str, str], float] = {}
    previous_irrigation: dict[str, bool] = {}
    devices = ("node1", "node2", "flow", "ec", "ph", "drain", "ventilation", "plc", "inverter")
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
        watchdog_stop = threading.Event()
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
            result, _ = client.subscribe([("farm/control", 1), ("farm/demo/control", 1)])
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"virtual devices could not subscribe to control topics: rc={result}")
            LOGGER.info("Virtual devices subscribed to farm/control and farm/demo/control")
            LOGGER.info("Publishing %s virtual farms; node cadence=%ss, EC/pH=%ss, PLC=%ss",
                        len(FARMS), DEVICE_INTERVAL_SECONDS["node1"], DEVICE_INTERVAL_SECONDS["ec"],
                        DEVICE_INTERVAL_SECONDS["plc"])
            threading.Thread(target=_virtual_plc_watchdog_loop,
                             args=(client, watchdog_stop),
                             name="smiot-virtual-plc-watchdog", daemon=True).start()
            due.clear()
            while True:
                now_mono = time.monotonic()
                for farm_key in FARMS:
                    with _virtual_outputs_lock:
                        farm_state = _farm_actuator_state(farm_key)
                        irrigation_active = any(farm_state["outputs"]) and bool(farm_state["valve_state"])
                    if previous_irrigation.get(farm_key) != irrigation_active:
                        due[(farm_key, "flow")] = now_mono
                        due[(farm_key, "drain")] = now_mono
                        previous_irrigation[farm_key] = irrigation_active
                    for device_key in devices:
                        interval = DEVICE_INTERVAL_SECONDS.get(device_key, 60)
                        if device_key == "flow":
                            interval = DEVICE_INTERVAL_SECONDS["flow"] if irrigation_active else FLOW_IDLE_INTERVAL_SECONDS
                        elif device_key == "drain":
                            interval = DEVICE_INTERVAL_SECONDS["drain"] if irrigation_active else DRAIN_IDLE_INTERVAL_SECONDS
                        key = (farm_key, device_key)
                        if device_key in {"node1", "node2", "flow"}:
                            with _external_source_lock:
                                last_external_sample = _external_source_last_seen.get(key)
                            if last_external_sample is not None and now_mono - last_external_sample < EXTERNAL_SOURCE_LEASE_SECONDS:
                                # Velxio owns this exact farm/device stream while its
                                # sensor heartbeat is fresh. Schedule EC2 exactly at
                                # lease expiry so fallback does not wait another cadence.
                                due[key] = last_external_sample + EXTERNAL_SOURCE_LEASE_SECONDS
                                continue
                        if now_mono < due.get(key, 0.0):
                            continue
                        due[key] = now_mono + interval
                        if device_key in {"node1", "node2", "flow", "ec", "ph", "drain"}:
                            payload = _device_payload(farm_key, device_key, rng, totals)
                            control_observations = payload.pop("_scenario_control_observations", [])
                            for observation in control_observations:
                                client.publish("farm/demo/evidence",
                                               json.dumps(observation, separators=(",", ":")), qos=1)
                            info = client.publish("farm/sensor", json.dumps(payload, separators=(",", ":")), qos=1)
                            info.wait_for_publish(timeout=5)
                        elif device_key == "ventilation":
                            payload = _device_payload(farm_key, device_key, rng, totals)
                            control_observations = payload.pop("_scenario_control_observations", [])
                            for observation in control_observations:
                                client.publish("farm/demo/evidence",
                                               json.dumps(observation, separators=(",", ":")), qos=1)
                            client.publish("farm/sensor", json.dumps(payload, separators=(",", ":")), qos=1)
                        elif device_key == "plc":
                            client.publish("farm/status", json.dumps(_virtual_plc_payload(farm_key), separators=(",", ":")), qos=1)
                        elif device_key == "inverter":
                            with _virtual_outputs_lock:
                                current = _farm_actuator_state(farm_key)
                                active = int(any(current["outputs"]))
                            inverter = {
                                "device_name": "Inverter", "device_id": f"smiot-virtual-inverter-{farm_key}",
                                "farm_key": farm_key, "online": 1, "status": active, "bit": active,
                                "hz": 50.0 if active else 0.0, "p_set": 50.0 if active else 0.0,
                                "p_cur": 49.8 if active else 0.0, "v_in": 220.0,
                                "i_in": 2.1 if active else 0.0, "v_out": 220.0 if active else 0.0,
                                "i_out": 2.0 if active else 0.0, "source": "smiot_demo_stream",
                                "synthetic": True, "timestamp": _utc_now_text(),
                            }
                            client.publish("farm/data", json.dumps(inverter, separators=(",", ":")), qos=1)
                time.sleep(0.25)
        except Exception as exc:
            LOGGER.warning("Synthetic demo stream cannot reach local MQTT; retrying in 5s: %s", exc)
            watchdog_stop.set()
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

