"""Pure scenario definitions for actuator (A1-A7) and software-infrastructure (H1-H6) faults.

This module does not operate real services or physical hardware. Its overlay values are
synthetic and may be consumed only by the virtual-device/demo dispatcher. A production
signal must be separately observed and corroborated before it can drive a real action.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any


ACTUATOR_INFRA_SCENARIOS: dict[str, dict[str, Any]] = {
    "A1": {
        "scenario_type": "a1_water_overrun",
        "group": "A",
        "title": "Tràn nước / quá lượng",
        "summary": "Lưu lượng hoặc thể tích cấp vượt giới hạn tưới đã cấu hình.",
        "fields": ["flow_line1_lpm", "flow_line1_total_l", "pump_line1_on", "valve_open"],
        "required_evidence": ["flow", "pump_state", "valve_state", "run_id"],
        "response": "SAFE_STOP",
        "recovery": {"stable_samples": 3, "require_operator": True, "auto_reopen": False},
    },
    "A2": {
        "scenario_type": "a2_pump_pressure_zero",
        "group": "A",
        "title": "Bơm chạy nhưng áp suất bằng 0",
        "summary": "Phản hồi áp suất bằng 0 trong khi bơm được xác nhận đang chạy.",
        "fields": ["pressure_bar", "pump_line1_on", "flow_line1_lpm"],
        "required_evidence": ["pressure", "pump_state", "command_id"],
        "response": "SAFE_STOP",
        "recovery": {"stable_samples": 3, "require_operator": True, "auto_reopen": False},
    },
    "A3": {
        "scenario_type": "a3_low_flow",
        "group": "A",
        "title": "Lưu lượng thấp khi bơm được lệnh chạy",
        "summary": "Lưu lượng thấp hơn mức tối thiểu cấu hình sau thời gian chờ.",
        "fields": ["flow_line1_lpm", "pump_line1_on", "valve_open"],
        "required_evidence": ["flow", "pump_state", "valve_state", "command_id"],
        "response": "HOLD_AND_INSPECT",
        "recovery": {"stable_samples": 3, "require_operator": True, "auto_reopen": False},
    },
    "A4": {
        "scenario_type": "a4_command_no_ack",
        "group": "A",
        "title": "Lệnh chấp hành không có ACK",
        "summary": "Không có phản hồi khớp command_id trong timeout cấu hình.",
        "fields": ["command_id", "ack_received", "target_value", "observed_value"],
        "required_evidence": ["command_id", "command_at", "ack_deadline"],
        "response": "DO_NOT_RETRY_UNSAFE_COMMAND",
        "recovery": {"stable_samples": 1, "require_operator": False, "auto_reopen": False},
    },
    "A5": {
        "scenario_type": "a5_vent_stuck",
        "group": "A",
        "title": "Quạt/thông gió kẹt",
        "summary": "Lệnh thông gió bật nhưng feedback/RPM không đổi hoặc nhiệt tiếp tục tăng.",
        "fields": ["vent_cmd", "vent_state", "fan_rpm", "air_temp_c"],
        "required_evidence": ["vent_command", "vent_feedback", "temperature_trend"],
        "response": "SAFE_VENTILATION_ESCALATE",
        "recovery": {"stable_samples": 3, "require_operator": True, "auto_reopen": False},
    },
    "A6": {
        "scenario_type": "a6_shade_no_ack",
        "group": "A",
        "title": "Lưới che không phản hồi",
        "summary": "Vị trí lưới che báo về không khớp lệnh trong timeout cấu hình.",
        "fields": ["shade_command", "shade_position", "ack_received"],
        "required_evidence": ["command_id", "shade_command", "shade_feedback"],
        "response": "STOP_CONFLICTING_COMMANDS",
        "recovery": {"stable_samples": 1, "require_operator": True, "auto_reopen": False},
    },
    "A7": {
        "scenario_type": "a7_tank_low",
        "group": "A",
        "title": "Mực bồn thấp",
        "summary": "Cảm biến mực bồn báo dưới giới hạn an toàn cấu hình.",
        "fields": ["tank_level_pct", "pump_line1_on", "pump_line2_on"],
        "required_evidence": ["tank_level", "sensor_freshness"],
        "response": "BLOCK_DRY_RUN",
        "recovery": {"stable_samples": 3, "require_operator": True, "auto_reopen": False},
    },
    "H1": {
        "scenario_type": "h1_service_down",
        "group": "H",
        "title": "Ứng dụng không phản hồi",
        "summary": "Probe ngoài không nhận health response trong cửa sổ cấu hình.",
        "fields": ["app_up", "healthz_status", "probe_at"],
        "required_evidence": ["external_probe", "mongo_health", "mqtt_health"],
        "response": "GUARDED_SERVICE_RECOVERY_ONLY",
        "recovery": {"stable_samples": 2, "require_operator": False, "auto_reopen": False},
    },
    "H2": {
        "scenario_type": "h2_dependency_unavailable",
        "group": "H",
        "title": "MongoDB hoặc MQTT không sẵn sàng",
        "summary": "Ứng dụng không thể xác nhận trạng thái dependency bằng health/operation check.",
        "fields": ["dependency", "available", "operation_error"],
        "required_evidence": ["dependency_name", "health_check", "app_error"],
        "response": "SAFE_MODE_AND_DIAGNOSE_DEPENDENCY",
        "recovery": {"stable_samples": 2, "require_operator": False, "auto_reopen": False},
    },
    "H3": {
        "scenario_type": "h3_common_gateway_down",
        "group": "H",
        "title": "Mất kết nối thiết bị đồng loạt",
        "summary": "Nhiều node cùng mất heartbeat và topology xác nhận chung gateway/broker.",
        "fields": ["gateway_up", "affected_device_count", "last_seen_at"],
        "required_evidence": ["gateway_health", "child_device_freshness", "topology_edge"],
        "response": "GROUP_CHILD_SYMPTOMS_KEEP_EVIDENCE",
        "recovery": {"stable_samples": 2, "require_operator": False, "auto_reopen": False},
    },
    "H4": {
        "scenario_type": "h4_detector_silent",
        "group": "H",
        "title": "Bộ phát hiện im lặng",
        "summary": "Heartbeat của detector mất dù nguồn dữ liệu đầu vào vẫn đến.",
        "fields": ["detector_name", "heartbeat_at", "input_sample_at"],
        "required_evidence": ["independent_watchdog", "detector_id", "input_freshness"],
        "response": "MARK_STATE_UNKNOWN_ESCALATE",
        "recovery": {"stable_samples": 2, "require_operator": False, "auto_reopen": False},
    },
    "H5": {
        "scenario_type": "h5_resource_pressure",
        "group": "H",
        "title": "Thiếu tài nguyên máy chủ",
        "summary": "Đĩa/CPU/RAM chạm ngưỡng cảnh báo đã cấu hình và ảnh hưởng dịch vụ.",
        "fields": ["disk_free_pct", "cpu_pct", "memory_pct", "service_health"],
        "required_evidence": ["host_metrics", "service_health", "resource_trend"],
        "response": "ALERT_AND_GUARDED_MITIGATION",
        "recovery": {"stable_samples": 3, "require_operator": True, "auto_reopen": False},
    },
    "H6": {
        "scenario_type": "h6_ai_provider_error",
        "group": "H",
        "title": "AI provider lỗi hoặc quá tải",
        "summary": "Provider timeout/lỗi hoặc output không vượt qua schema validation.",
        "fields": ["provider_status", "error_class", "latency_ms", "valid_output"],
        "required_evidence": ["provider_call", "response_validation", "fallback_decision"],
        "response": "HOLD_AND_USE_DETERMINISTIC_RULES",
        "recovery": {"stable_samples": 1, "require_operator": False, "auto_reopen": False},
    },
}


_DEFAULT_OVERLAYS: dict[str, dict[str, Any]] = {
    "A1": {"flow_line1_lpm": 12.0, "flow_line1_total_l": 20.5, "pump_line1_on": True, "valve_open": True},
    "A2": {"pressure_bar": 0.0, "pump_line1_on": True, "flow_line1_lpm": 0.0},
    "A3": {"flow_line1_lpm": 0.1, "pump_line1_on": True, "valve_open": True},
    "A4": {"ack_received": False, "ack_delay_s": None, "target_value": 1, "observed_value": 0},
    "A5": {"vent_cmd": 1, "vent_state": 0, "fan_rpm": 0, "air_temp_c": 39.0},
    "A6": {"shade_command": 1, "shade_position": 0, "ack_received": False},
    "A7": {"tank_level_pct": 2.0, "pump_line1_on": True, "pump_line2_on": True},
    "H1": {"app_up": 0, "healthz_status": 503},
    "H2": {"dependency": "mongodb", "available": False, "operation_error": "synthetic_dependency_unavailable"},
    "H3": {"gateway_up": 0, "affected_device_count": 3},
    "H4": {"detector_name": "telemetry_quality", "heartbeat_at": None, "input_sample_at": "now"},
    "H5": {"disk_free_pct": 3.0, "cpu_pct": 95.0, "memory_pct": 93.0, "service_health": "degraded"},
    "H6": {"provider_status": "error", "error_class": "provider_unavailable", "latency_ms": 5000, "valid_output": False},
}


_OBSERVATION_REQUIREMENTS: dict[str, dict[str, Any]] = {
    code: {
        "required_fields": list(spec["required_evidence"]),
        "minimum_stable_samples": int(spec["recovery"]["stable_samples"]),
        "require_operator": bool(spec["recovery"]["require_operator"]),
        "auto_reopen": False,
        "auto_restart": False,
        "require_fresh_evidence": True,
        "max_automated_attempts": 0,
        "synthetic_only": True,
    }
    for code, spec in ACTUATOR_INFRA_SCENARIOS.items()
}


def _normalized_code(code_or_type: str) -> str | None:
    raw = str(code_or_type or "").strip()
    upper = raw.upper()
    if upper in ACTUATOR_INFRA_SCENARIOS:
        return upper
    for code, spec in ACTUATOR_INFRA_SCENARIOS.items():
        if raw == spec["scenario_type"]:
            return code
    return None


def actuator_infra_scenarios() -> dict[str, dict[str, Any]]:
    """Return a defensive copy of the A/H registry for dispatcher/UI integration."""
    return deepcopy(ACTUATOR_INFRA_SCENARIOS)


def build_actuator_infra_overlay(code_or_type: str,
                                  context: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    """Build deterministic synthetic signals; never executes real system/hardware actions.

    `context` can override individual signal values for scripted demonstrations. The result
    deliberately includes a top-level synthetic marker and response intent so callers cannot
    mistake a generated event for observed hardware state.
    """
    code = _normalized_code(code_or_type)
    if code is None:
        return None
    spec = ACTUATOR_INFRA_SCENARIOS[code]
    override = context if isinstance(context, Mapping) else {}
    signals = deepcopy(_DEFAULT_OVERLAYS[code])
    signals.update({key: value for key, value in override.items() if key in spec["fields"]})
    return {
        "scenario_code": code,
        "scenario_type": spec["scenario_type"],
        "group": spec["group"],
        "signals": signals,
        "synthetic": True,
        "source": "scenario_overlay",
        "execution_mode": "SIMULATED_ONLY",
        "real_hardware_action_allowed": False,
        "real_infrastructure_action_allowed": False,
        "response_intent": spec["response"],
        "recovery_requirements": deepcopy(_OBSERVATION_REQUIREMENTS[code]),
    }


def evaluate_actuator_infra(code_or_type: str, observed: Mapping[str, Any] | None = None,
                            context: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    """Return a finding candidate when a scenario's signal conjunction is observed.

    This is intentionally a pure evaluator: it neither writes MongoDB nor sends commands.
    The caller persists with its incident/run id and executes only permitted local virtual
    safety actions. Real devices and AWS services are never changed here.
    """
    code = _normalized_code(code_or_type)
    if code is None:
        return None
    spec = ACTUATOR_INFRA_SCENARIOS[code]
    values: dict[str, Any] = {}
    if isinstance(observed, Mapping):
        values.update(observed)
    if isinstance(context, Mapping):
        values.update(context)
    if not values:
        values.update(_DEFAULT_OVERLAYS[code])

    detected = False
    if code == "A1":
        flow = _number(values.get("flow_line1_lpm"))
        volume = _number(values.get("flow_line1_total_l"))
        max_flow = _number(values.get("max_flow_lpm", 10.0))
        max_volume = _number(values.get("max_volume_l", 20.0))
        detected = bool(values.get("pump_line1_on")) and (
            (flow is not None and max_flow is not None and flow > max_flow)
            or (volume is not None and max_volume is not None and volume > max_volume)
        )
    elif code == "A2":
        pressure = _number(values.get("pressure_bar"))
        detected = bool(values.get("pump_line1_on")) and pressure is not None and pressure <= 0
    elif code == "A3":
        flow = _number(values.get("flow_line1_lpm"))
        minimum = _number(values.get("min_flow_lpm", 0.5))
        detected = bool(values.get("pump_line1_on")) and flow is not None and minimum is not None and flow < minimum
    elif code == "A4":
        detected = values.get("ack_received") is False or values.get("ack_timed_out") is True
    elif code == "A5":
        vent_cmd = values.get("vent_cmd")
        vent_state = values.get("vent_state")
        rpm = _number(values.get("fan_rpm"))
        rising = values.get("temperature_rising") is True
        detected = vent_cmd in (1, True) and (
            vent_state in (0, False) or (rpm is not None and rpm <= 0) or rising
        )
    elif code == "A6":
        target = values.get("shade_command")
        actual = values.get("shade_position")
        detected = values.get("ack_received") is False or (
            target is not None and actual is not None and target != actual
        )
    elif code == "A7":
        level = _number(values.get("tank_level_pct"))
        threshold = _number(values.get("tank_min_pct", 5.0))
        detected = level is not None and threshold is not None and level <= threshold
    elif code == "H1":
        detected = values.get("app_up") in (0, False) or _number(values.get("healthz_status")) in (500, 502, 503, 504)
    elif code == "H2":
        detected = values.get("available") is False or values.get("health_ok") is False
    elif code == "H3":
        affected = int(_number(values.get("affected_device_count")) or 0)
        detected = values.get("gateway_up") in (0, False) and affected >= int(values.get("minimum_affected_devices", 2))
    elif code == "H4":
        heartbeat_age = _number(values.get("heartbeat_age_s"))
        stale_after = _number(values.get("heartbeat_stale_after_s", 90.0))
        detected = (
            values.get("heartbeat_missing") is True
            or values.get("heartbeat_at") is None
            or (heartbeat_age is not None and stale_after is not None and heartbeat_age > stale_after)
        )
    elif code == "H5":
        disk = _number(values.get("disk_free_pct"))
        cpu = _number(values.get("cpu_pct"))
        memory = _number(values.get("memory_pct"))
        disk_min = _number(values.get("disk_min_pct", 5.0))
        resource_max = _number(values.get("resource_max_pct", 95.0))
        detected = bool(
            (disk is not None and disk_min is not None and disk < disk_min)
            or (cpu is not None and resource_max is not None and cpu >= resource_max)
            or (memory is not None and resource_max is not None and memory >= resource_max)
        )
    elif code == "H6":
        detected = values.get("provider_status") in {"error", "timeout", "unavailable"} or values.get("valid_output") is False

    if not detected:
        return None

    return {
        "code": code,
        "group": spec["group"],
        "scenario_type": spec["scenario_type"],
        "title": spec["title"],
        "summary": spec["summary"],
        "severity": _severity(code),
        "evidence": {key: values.get(key) for key in spec["fields"] if key in values},
        "response_intent": spec["response"],
        "execution_mode": "SIMULATED_ONLY",
        "real_hardware_action_allowed": False,
        "real_infrastructure_action_allowed": False,
        "recovery_requirements": deepcopy(_OBSERVATION_REQUIREMENTS[code]),
        "synthetic": True,
    }


def recovery_requirements(code_or_type: str) -> dict[str, Any] | None:
    """Return recovery proof requirements; no entry permits automatic pump/valve reopening."""
    code = _normalized_code(code_or_type)
    if code is None:
        return None
    return deepcopy(_OBSERVATION_REQUIREMENTS[code])


def _severity(code: str) -> str:
    if code in {"A1", "A2", "A7", "H1", "H2", "H5"}:
        return "critical"
    if code in {"A3", "A4", "A5", "H3", "H4", "H6"}:
        return "high"
    return "warning"


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if result == result and abs(result) != float("inf") else None
