"""Unified catalog for the 36 explicitly scoped SMIOT drill scenarios.

This module is deliberately metadata-only. Domain evaluators produce candidate
findings; scenario ACKs and telemetry remain separate evidence channels.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from service.scenario_domain_crops import CROP_SCENARIOS
from service.scenario_domain_sensor_device import SCENARIO_DEFINITIONS as SENSOR_DEVICE_SCENARIOS
from service.scenario_domain_actuator_infra import actuator_infra_scenarios

_A_H = actuator_infra_scenarios()
_CROP_TITLES = {
    "C1": "Độ ẩm đất lệch mốc của giai đoạn",
    "C2": "Không khí khô hoặc ẩm bất thường",
    "C3": "Nóng cao điểm trong ngày",
    "C4": "Nước tưới và nước thoát không cân đối",
    "C5": "Có dấu hiệu thiếu nước lúc quả lớn nhanh",
    "C6": "EC nước thoát tăng so với nước tưới",
    "C7": "Sắp hết thời gian thụ phấn",
    "C8": "Ẩm kéo dài, cần kiểm tra nguy cơ bệnh",
    "C9": "Mưa có thể làm đổi lịch tưới",
    "C10": "Áp suất và lưu lượng nước không khớp",
}
_GROUPS: dict[str, dict[str, dict[str, Any]]] = {
    **{code: {**deepcopy(spec), "title": _CROP_TITLES.get(code, spec.get("title"))}
       for code, spec in CROP_SCENARIOS.items()},
    **{code: deepcopy(spec) for code, spec in SENSOR_DEVICE_SCENARIOS.items()},
    **{code: deepcopy(spec) for code, spec in _A_H.items()},
}
_ALIASES: dict[str, str] = {
    str(spec.get("scenario_type")): code for code, spec in _GROUPS.items()
    if spec.get("scenario_type")
}
_ALIASES.update({
    "soil_flatline": "S1", "soil_spike": "S2", "soil_out_of_range": "S3",
    "water_overrun": "A1", "pipe_leak": "C10", "vent_stuck": "A5",
    "demo_ui_fault": "D2", "stale_data": "D1", "sequence_gap": "D4",
    "sequence_duplicate": "D4", "sequence_regression": "D4", "cadence_drop": "D5",
    "low_battery": "D7",
})


def scenario_catalog() -> dict[str, dict[str, Any]]:
    """Return a defensive copy of all 36 cases."""
    return deepcopy(_GROUPS)


def resolve_scenario(value: Any) -> dict[str, Any] | None:
    """Resolve a public code or compatible legacy scenario type."""
    token = str(value or "").strip()
    code = token.upper() if token.upper() in _GROUPS else _ALIASES.get(token)
    if code is None:
        # Sensor resolver owns a few backwards-compatible aliases.
        from service.scenario_domain_sensor_device import resolve_scenario as resolve_sensor
        resolved = resolve_sensor(token)
        if resolved:
            code = str(resolved.get("code"))
    spec = _GROUPS.get(code) if code else None
    return {"code": code, **deepcopy(spec)} if spec else None


def scenario_types() -> tuple[str, ...]:
    """Canonical simulator scenario types, one for every catalog entry."""
    return tuple(str(spec.get("scenario_type") or code) for code, spec in _GROUPS.items())


def canonical_type(value: Any) -> str | None:
    """Return the compatibility type used by the simulator and evidence store."""
    token = str(value or "").strip()
    scenario = resolve_scenario(token)
    if not scenario:
        return None
    # Keep deployed demo names stable so existing monitors, ledgers and scripts
    # continue to recognize the original six scenarios.
    if token in {"soil_flatline", "soil_spike", "soil_out_of_range", "water_overrun", "pipe_leak", "vent_stuck"}:
        return token
    return str(scenario.get("scenario_type") or scenario["code"])


def scenario_codes() -> tuple[str, ...]:
    return tuple(_GROUPS)


def recovery_policy(value: Any) -> dict[str, Any] | None:
    """Return the domain-owned evidence requirements; never implies auto-clear."""
    scenario = resolve_scenario(value)
    if not scenario:
        return None
    code = scenario["code"]
    if code in CROP_SCENARIOS:
        return deepcopy(CROP_SCENARIOS[code].get("recovery_evidence", ()))
    if code in SENSOR_DEVICE_SCENARIOS:
        return deepcopy(SENSOR_DEVICE_SCENARIOS[code].get("recovery", {}))
    return deepcopy(_A_H.get(code, {}).get("recovery", {}))
