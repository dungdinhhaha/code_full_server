"""Evidence-gated recovery checks for the 36 virtual SMIOT scenarios.

These functions only classify supplied recovery evidence. They never clear an
incident, restart a process, actuate hardware, or write to MongoDB/Datadog.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


def _actuator_infra_recovery(code: str, evidence: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    stable = _number(evidence.get("stable_samples"))
    required = int(policy.get("minimum_stable_samples", policy.get("stable_samples", 1)))
    if stable is None or stable < required:
        return {"status": "recovering", "recovered": False,
                "reason": "Chưa đủ mẫu ổn định sau khi xử lý.",
                "evidence": {"stable_samples": stable, "required": required}}

    checks: dict[str, bool | None] = {}
    if code == "A1":
        flow, volume = _number(evidence.get("flow_lpm")), _number(evidence.get("volume_l"))
        max_flow, max_volume = _number(evidence.get("max_flow_lpm")), _number(evidence.get("max_volume_l"))
        checks = {"flow_within_limit": flow is not None and max_flow is not None and flow <= max_flow,
                  "volume_within_limit": volume is not None and max_volume is not None and volume <= max_volume,
                  "pump_off": evidence.get("pump_on") is False, "valve_closed": evidence.get("valve_open") is False}
    elif code == "A2":
        pressure, minimum = _number(evidence.get("pressure_bar")), _number(evidence.get("minimum_pressure_bar"))
        checks = {"pressure_readback": pressure is not None and minimum is not None and pressure >= minimum,
                  "pump_off": evidence.get("pump_on") is False}
    elif code == "A3":
        flow, minimum = _number(evidence.get("flow_lpm")), _number(evidence.get("minimum_flow_lpm"))
        checks = {"flow_restored": flow is not None and minimum is not None and flow >= minimum,
                  "pump_state_confirmed": isinstance(evidence.get("pump_on"), bool)}
    elif code == "A4":
        checks = {"matching_ack": evidence.get("ack_received") is True,
                  "command_matches_readback": evidence.get("target_value") is not None
                  and evidence.get("target_value") == evidence.get("observed_value")}
    elif code == "A5":
        checks = {"vent_feedback_matches": evidence.get("vent_command") is not None
                  and evidence.get("vent_command") == evidence.get("vent_state"),
                  "temperature_stable": evidence.get("temperature_stable") is True}
    elif code == "A6":
        checks = {"matching_ack": evidence.get("ack_received") is True,
                  "shade_feedback_matches": evidence.get("shade_command") is not None
                  and evidence.get("shade_command") == evidence.get("shade_position")}
    elif code == "A7":
        level, minimum = _number(evidence.get("tank_level_pct")), _number(evidence.get("tank_recovery_min_pct"))
        checks = {"tank_level_restored": level is not None and minimum is not None and level >= minimum,
                  "tank_sensor_fresh": evidence.get("sensor_fresh") is True,
                  "pumps_remain_blocked_until_review": evidence.get("dry_run_interlock_active") is True}
    elif code == "H1":
        checks = {"app_health": evidence.get("app_up") is True and evidence.get("healthz_status") == 200,
                  "dependencies_healthy": evidence.get("dependencies_healthy") is True}
    elif code == "H2":
        checks = {"dependency_operation_succeeded": evidence.get("dependency_operation_ok") is True,
                  "app_health": evidence.get("app_health_ok") is True}
    elif code == "H3":
        checks = {"gateway_healthy": evidence.get("gateway_up") is True,
                  "children_fresh": evidence.get("all_children_fresh") is True,
                  "topology_confirmed": evidence.get("topology_confirmed") is True}
    elif code == "H4":
        checks = {"detector_heartbeat_fresh": evidence.get("detector_heartbeat_fresh") is True,
                  "input_stream_fresh": evidence.get("input_stream_fresh") is True}
    elif code == "H5":
        disk, disk_min = _number(evidence.get("disk_free_pct")), _number(evidence.get("disk_min_pct"))
        cpu, cpu_max = _number(evidence.get("cpu_pct")), _number(evidence.get("cpu_max_pct"))
        memory, memory_max = _number(evidence.get("memory_pct")), _number(evidence.get("memory_max_pct"))
        checks = {"disk_recovered": disk is not None and disk_min is not None and disk >= disk_min,
                  "cpu_recovered": cpu is not None and cpu_max is not None and cpu <= cpu_max,
                  "memory_recovered": memory is not None and memory_max is not None and memory <= memory_max,
                  "service_healthy": evidence.get("service_healthy") is True}
    elif code == "H6":
        checks = {"provider_healthy": evidence.get("provider_status") == "ok",
                  "output_valid": evidence.get("valid_output") is True,
                  "fallback_or_decision_recorded": bool(evidence.get("decision_recorded"))}
    else:
        return {"status": "unknown", "recovered": False, "reason": "Không có quy tắc phục hồi cho mã này."}

    missing = [name for name, passed in checks.items() if passed is None]
    failed = [name for name, passed in checks.items() if passed is False]
    if missing:
        return {"status": "unknown", "recovered": False,
                "reason": "Thiếu dữ liệu xác nhận phục hồi.", "missing_evidence": missing,
                "checks": checks}
    if failed:
        return {"status": "recovering", "recovered": False,
                "reason": "Một hoặc nhiều điều kiện vẫn chưa bình thường.",
                "failed_checks": failed, "checks": checks}
    if policy.get("require_operator") and evidence.get("operator_reviewed") is not True:
        return {"status": "recovered_pending_review", "recovered": False,
                "reason": "Tín hiệu đã ổn định; cần người vận hành xem xét trước khi đóng sự cố.",
                "checks": checks}
    return {"status": "recovery_verified", "recovered": True,
            "reason": "Đã đủ mẫu ổn định và các điều kiện phục hồi được xác nhận.",
            "checks": checks}


def evaluate_scenario_recovery(scenario: Any, evidence: Mapping[str, Any], *,
                               run: Mapping[str, Any] | None = None,
                               context: Mapping[str, Any] | None = None,
                               normal_samples: int = 0) -> dict[str, Any]:
    """Evaluate recovery evidence for any catalog case without changing state."""
    from service.scenario_catalog import recovery_policy, resolve_scenario
    spec = resolve_scenario(scenario)
    if spec is None or not isinstance(evidence, Mapping):
        return {"status": "unknown", "recovered": False, "reason": "Mã kịch bản hoặc bằng chứng không hợp lệ."}
    code = spec["code"]
    policy = recovery_policy(code) or {}
    if code.startswith("C"):
        from service.scenario_domain_crops import evaluate_recovery
        result = evaluate_recovery(code, evidence, context)
        # Crop checks requiring a field review intentionally remain pending.
        return result
    if code.startswith(("S", "D")):
        from service.scenario_domain_sensor_device import recovery_condition
        result = recovery_condition(
            code, evidence, run or {}, normal_samples=normal_samples,
            freshness_limit_seconds=evidence.get("freshness_limit_seconds"),
        )
        if result.get("ok") and policy.get("require_operator") and evidence.get("operator_reviewed") is not True:
            return {**result, "ok": False, "status": "recovered_pending_review",
                    "reason": "Tín hiệu đã ổn định; cần người vận hành xem xét trước khi đóng sự cố."}
        return {**result, "status": "recovery_verified" if result.get("ok") else "recovering",
                "recovered": result.get("ok") is True}
    return _actuator_infra_recovery(code, evidence, policy)
