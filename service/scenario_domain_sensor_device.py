"""Pure simulation overlays and recovery predicates for sensor/network cases.

This module intentionally does not open incidents, publish MQTT, write MongoDB,
or call Datadog. The caller owns orchestration and must correlate by
scenario_run_id + farm + device/node + event time. Every overlay is synthetic
and should be applied only to simulator-produced payloads.
"""

from __future__ import annotations

import copy
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


SCENARIO_DEFINITIONS: dict[str, dict[str, Any]] = {
    "S1": {
        "scenario_type": "soil_flatline", "group": "S", "code": "S1",
        "title": "Cảm biến đất đứng số", "target": "soil_humidity",
        "overlay": "hold_first_value", "recovery_samples": 3,
        "recovery": "Ba mẫu mới liên tiếp phải khác giá trị kẹt và còn trong miền hợp lệ.",
    },
    "S2": {
        "scenario_type": "soil_spike", "group": "S", "code": "S2",
        "title": "Cảm biến đất tăng đột biến", "target": "soil_humidity",
        "overlay": "seeded_step_spike", "recovery_samples": 3,
        "recovery": "Ba mẫu mới liên tiếp không còn là spike và nằm trong miền cảm biến.",
    },
    "S3": {
        "scenario_type": "soil_out_of_range", "group": "S", "code": "S3",
        "title": "Cảm biến đất ngoài miền vật lý", "target": "soil_humidity",
        "overlay": "out_of_physical_range", "recovery_samples": 3,
        "recovery": "Ba mẫu mới liên tiếp nằm trong miền hợp lệ đã cấu hình.",
    },
    "S4": {
        "scenario_type": "sensor_drift", "group": "S", "code": "S4",
        "title": "Cảm biến trôi dần", "target": "soil_humidity",
        "overlay": "gradual_bounded_drift", "recovery_samples": 3,
        "recovery": "Cần đối chiếu chuẩn hoặc cảm biến tham chiếu; không tự xoá offset.",
    },
    "S5": {
        "scenario_type": "sibling_sensor_mismatch", "group": "S", "code": "S5",
        "title": "Hai cảm biến cùng khu đo lệch nhau", "target": "soil_humidity",
        "overlay": "peer_offset", "recovery_samples": 3,
        "recovery": "Chỉ xác nhận sau khi hai node được đối chiếu cùng thời điểm hoặc hiệu chuẩn.",
    },
    "S6": {
        "scenario_type": "sensor_noise", "group": "S", "code": "S6",
        "title": "Cảm biến nhiễu", "target": "soil_humidity",
        "overlay": "seeded_noise", "recovery_samples": 5,
        "recovery": "Phương sai giảm dưới giới hạn đã cấu hình qua năm mẫu mới.",
    },
    "D1": {
        "scenario_type": "device_stale", "group": "D", "code": "D1",
        "title": "Bản tin thiết bị cũ", "target": "measured_at",
        "overlay": "old_measurement_timestamp", "recovery_samples": 1,
        "recovery": "Một bản tin mới được đọc lại từ Mongo với tuổi nhỏ hơn freshness limit.",
    },
    "D2": {
        "scenario_type": "false_offline", "group": "D", "code": "D2",
        "title": "Giao diện báo offline sai", "target": "ui_status",
        "overlay": "stale_ui_status_only", "recovery_samples": 1,
        "recovery": "UI đọc lại trạng thái từ mẫu mới; không restart thiết bị.",
    },
    "D3": {
        "scenario_type": "device_reboot", "group": "D", "code": "D3",
        "title": "Thiết bị khởi động lại", "target": "boot_id/uptime_seconds",
        "overlay": "new_boot_epoch", "recovery_samples": 2,
        "recovery": "Cùng boot_id mới có sequence tăng và mẫu tiếp tục đến.",
    },
    "D4": {
        "scenario_type": "sequence_anomaly", "group": "D", "code": "D4",
        "title": "Sequence hụt, trùng hoặc lùi", "target": "sample_sequence",
        "overlay": "sequence_gap_duplicate_or_regression", "recovery_samples": 2,
        "recovery": "Sequence mới tăng hợp lệ; khoảng hụt cũ vẫn được giữ làm bằng chứng.",
    },
    "D5": {
        "scenario_type": "reduced_publish_rate", "group": "D", "code": "D5",
        "title": "Thiết bị gửi chậm", "target": "publisher cadence",
        "overlay": "cadence_multiplier", "recovery_samples": 3,
        "recovery": "Ba chu kỳ liên tiếp nằm trong cadence cấu hình.",
    },
    "D6": {
        "scenario_type": "unknown_device", "group": "D", "code": "D6",
        "title": "Thiết bị chưa đăng ký", "target": "device_id",
        "overlay": "unregistered_identity", "recovery_samples": 1,
        "recovery": "Thiết bị được đăng ký rõ farm/device type và gửi mẫu mới đúng phạm vi.",
    },
    "D7": {
        "scenario_type": "device_health_low", "group": "D", "code": "D7",
        "title": "Pin, sóng hoặc điện áp yếu", "target": "battery/rssi/voltage",
        "overlay": "low_device_health", "recovery_samples": 3,
        "recovery": "Chỉ đóng khi có dải hồi phục theo loại thiết bị và ba mẫu khỏe mới.",
    },
}

_ALIASES = {
    "soil_flatline": "S1", "soil_spike": "S2", "soil_out_of_range": "S3",
    "sensor_drift": "S4", "sibling_sensor_mismatch": "S5", "sensor_noise": "S6",
    "device_stale": "D1", "stale_data": "D1", "false_offline": "D2",
    "demo_ui_fault": "D2", "device_reboot": "D3", "sequence_anomaly": "D4",
    "sequence_gap": "D4", "sequence_duplicate": "D4", "sequence_regression": "D4",
    "reduced_publish_rate": "D5", "cadence_drop": "D5", "unknown_device": "D6",
    "device_health_low": "D7", "low_battery": "D7",
}

_READING_FIELDS = {
    "soil_humidity": "sh",
    "air_humidity": "ah",
    "air_temperature": "at",
    "soil_temperature": "st",
    "soil_ec": "sec",
}


def resolve_scenario(scenario_type: Any) -> dict[str, Any] | None:
    """Return a detached scenario definition for a code or supported alias."""
    key = str(scenario_type or "").strip()
    alias = _ALIASES.get(key.lower())
    code = key.upper() if key.upper() in SCENARIO_DEFINITIONS else alias
    definition = SCENARIO_DEFINITIONS.get(code or "")
    return copy.deepcopy(definition) if definition else None


def scenario_codes() -> tuple[str, ...]:
    """Stable order for CLI menus and UI selectors."""
    return tuple(SCENARIO_DEFINITIONS)


def _target_node(payload: dict[str, Any], run: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Locate a sensor object in legacy ID6, a channel map/list, or flat sample.

    The helper mutates only the selected channel in the copied envelope. A
    publisher may pass its entire MQTT envelope, including unrelated devices.
    """
    node_id = run.get("node_id")
    channel_name = run.get("channel") or run.get("channel_id")
    channels = payload.get("channels")
    if isinstance(channels, dict):
        candidates = list(channels.items())
        if channel_name is not None:
            candidates = [(str(channel_name), channels.get(channel_name))]
        elif node_id is not None:
            preferred = (f"node{node_id}", str(node_id), f"id{node_id}")
            candidates.sort(key=lambda pair: (pair[0] not in preferred, pair[0]))
        for _key, candidate in candidates:
            if isinstance(candidate, dict) and _looks_like_sensor(candidate):
                return candidate, None
        if channel_name is not None:
            raise ValueError(f"requested channel is absent or not sensor-shaped: {channel_name}")
    elif isinstance(channels, list):
        candidates = channels
        if channel_name is not None:
            candidates = [item for item in channels if isinstance(item, dict)
                          and str(item.get("channel") or item.get("device_id")) == str(channel_name)]
        elif node_id is not None:
            candidates = [item for item in channels if isinstance(item, dict)
                          and str(item.get("node_id")) == str(node_id)] or channels
        for candidate in candidates:
            if isinstance(candidate, dict) and _looks_like_sensor(candidate):
                return candidate, None
        if channel_name is not None:
            raise ValueError(f"requested channel is absent or not sensor-shaped: {channel_name}")

    # Current application envelopes: id6.node1/node2 plus additive id3-id8 channels.
    data = payload.get("id6")
    if isinstance(data, dict):
        key = f"node{node_id}" if node_id is not None else "node2"
        node = data.get(key)
        if isinstance(node, dict):
            return node, data.get("node1" if key == "node2" else "node2")

    if channel_name is not None:
        candidate = payload.get(str(channel_name))
        if isinstance(candidate, dict) and _looks_like_sensor(candidate):
            return candidate, None
        raise ValueError(f"requested channel is absent or not sensor-shaped: {channel_name}")
    for key in ("id3", "id4", "id5", "id7", "id8"):
        candidate = payload.get(key)
        if isinstance(candidate, dict) and _looks_like_sensor(candidate):
            return candidate, None
    if _looks_like_sensor(payload):
        return payload, None
    raise ValueError("scenario payload does not contain a target sensor channel")


def _looks_like_sensor(candidate: Mapping[str, Any]) -> bool:
    readings = candidate.get("readings")
    fields = readings if isinstance(readings, Mapping) else candidate
    return any(name in fields for name in (
        "sh", "soil_humidity", "soil_hum", "ah", "at", "st", "sample_sequence",
        "sequence", "measured_at", "battery_pct", "rssi_dbm", "voltage_v",
    ))


def _readings(target: dict[str, Any]) -> dict[str, Any]:
    """Return channel readings when wrapped, otherwise the flat channel."""
    nested = target.get("readings")
    return nested if isinstance(nested, dict) else target


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _stable_rng(run: Mapping[str, Any], code: str, sample_index: int) -> random.Random:
    seed = run.get("seed", 1)
    try:
        seed_int = int(seed)
    except (TypeError, ValueError):
        seed_int = 1
    return random.Random((seed_int * 1_000_003) ^ (sample_index * 9176) ^ sum(ord(c) for c in code))


def apply_sensor_device_scenario(
    scenario_type: Any,
    payload: Mapping[str, Any],
    run: Mapping[str, Any],
    *,
    peer_payload: Mapping[str, Any] | None = None,
    sample_index: int = 0,
) -> dict[str, Any]:
    """Apply one deterministic sensor/device fault without persisting or publishing.

    Result shape: ``{code, scenario_type, payload, controls, evidence, synthetic}``.
    `controls` informs the caller about non-payload effects (UI status, publish
    cadence); it must not be copied into ordinary sensor readings.
    """
    definition = resolve_scenario(scenario_type)
    if definition is None:
        raise ValueError(f"unsupported sensor/device scenario: {scenario_type}")
    result = copy.deepcopy(dict(payload))
    target, peer = _target_node(result, run)
    readings = _readings(target)
    code = definition["code"]
    reading_key = definition.get("target")
    field = _READING_FIELDS.get(str(reading_key))
    before = _number(readings.get(field)) if field else None
    controls: dict[str, Any] = {
        # Expected fault identity belongs to the orchestration/control plane.
        # Do not copy these labels into regular telemetry fields or metric tags.
        "expected_fault": {"code": code, "scenario_type": definition["scenario_type"]},
        "scenario_run_id": str(run.get("scenario_run_id") or "")[:100],
    }
    evidence: dict[str, Any] = {
        "code": code,
        "scenario_run_id": str(run.get("scenario_run_id") or ""),
        "farm_key": str(run.get("farm_key") or result.get("farm_key") or ""),
        "node_id": run.get("node_id"),
        "sample_index": max(0, int(sample_index)),
        "synthetic": True,
    }

    if code == "S1":
        if field is None:
            raise ValueError("S1 requires a numeric sensor field")
        state = run.get("scenario_state")
        if not isinstance(state, dict):
            state = {}
        fixed = _number(state.get("flatline_value"))
        if fixed is None:
            fixed = before if before is not None else 50.0
            # Caller owns this run state and uses it for the rest of the scenario.
            state["flatline_value"] = fixed
            if isinstance(run, dict):
                run["scenario_state"] = state
        readings[field] = fixed
        evidence.update({"metric": reading_key, "before": before, "value": fixed,
                         "reason": "same sensor value repeated across this scenario run"})

    elif code == "S2":
        if field is None:
            raise ValueError("S2 requires a numeric sensor field")
        rng = _stable_rng(run, code, sample_index)
        magnitude = _number(run.get("spike_magnitude"))
        if magnitude is None:
            magnitude = 25.0
        direction = 1.0 if str(run.get("direction", "up")).lower() != "down" else -1.0
        injected = (before if before is not None else 50.0) + direction * abs(magnitude) + rng.uniform(-0.5, 0.5)
        readings[field] = round(injected, 2)
        evidence.update({"metric": reading_key, "before": before, "value": readings[field],
                         "configured_step": direction * abs(magnitude)})

    elif code == "S3":
        if field is None:
            raise ValueError("S3 requires a numeric sensor field")
        # This is an intentionally invalid synthetic reading. The detector's
        # configured physical range remains the authority; 105 is not a crop band.
        injected = _number(run.get("out_of_range_value"))
        readings[field] = injected if injected is not None else 105.0
        evidence.update({"metric": reading_key, "before": before, "value": readings[field],
                         "note": "synthetic value outside nominal 0..100 humidity domain"})

    elif code == "S4":
        if field is None:
            raise ValueError("S4 requires a numeric sensor field")
        state = run.get("scenario_state")
        if not isinstance(state, dict):
            state = {}
        baseline = _number(state.get("baseline"))
        if baseline is None:
            baseline = before if before is not None else 50.0
            state["baseline"] = baseline
            if isinstance(run, dict):
                run["scenario_state"] = state
        drift = abs(_number(run.get("drift_per_sample")) or 0.5) * (sample_index + 1)
        direction = 1.0 if str(run.get("direction", "up")).lower() != "down" else -1.0
        readings[field] = round(max(0.0, min(100.0, baseline + direction * drift)), 2)
        evidence.update({"metric": reading_key, "baseline": baseline, "value": readings[field],
                         "drift_per_sample": direction * abs(_number(run.get("drift_per_sample")) or 0.5)})

    elif code == "S5":
        if field is None:
            raise ValueError("S5 requires a numeric sensor field")
        peer_node = None
        if isinstance(peer_payload, Mapping):
            peer_copy = dict(peer_payload)
            try:
                peer_node, _ = _target_node(peer_copy, {"node_id": 1 if run.get("node_id") == 2 else 2})
            except ValueError:
                peer_node = None
        if peer_node is None and isinstance(peer, dict):
            peer_node = peer
        peer_value = _number(peer_node.get(field)) if isinstance(peer_node, Mapping) else None
        if peer_value is None:
            raise ValueError("S5 requires a peer-node sample; no peer value will be fabricated")
        offset = _number(run.get("peer_offset"))
        if offset is None:
            offset = 25.0
        direction = 1.0 if str(run.get("direction", "up")).lower() != "down" else -1.0
        readings[field] = round(max(0.0, min(100.0, peer_value + direction * abs(offset))), 2)
        evidence.update({"metric": reading_key, "peer_value": peer_value, "value": readings[field],
                         "configured_offset": direction * abs(offset), "peer_timestamp": (peer_node or {}).get("timestamp")})

    elif code == "S6":
        if field is None:
            raise ValueError("S6 requires a numeric sensor field")
        rng = _stable_rng(run, code, sample_index)
        amplitude = abs(_number(run.get("noise_amplitude")) or 8.0)
        base = before if before is not None else 50.0
        readings[field] = round(max(0.0, min(100.0, base + rng.uniform(-amplitude, amplitude))), 2)
        evidence.update({"metric": reading_key, "baseline": base, "value": readings[field],
                         "noise_amplitude": amplitude})

    elif code == "D1":
        # Do not alter current timestamp in place; move measured_at back so the
        # pipeline can distinguish a stale measurement from late transport.
        event_time = _parse_utc(target.get("measured_at") or target.get("timestamp") or result.get("timestamp"))
        age = max(1, int(_number(run.get("stale_age_seconds")) or 300))
        if event_time is None:
            event_time = datetime.now(timezone.utc)
        stale_time = event_time - timedelta(seconds=age)
        target["measured_at"] = stale_time.isoformat().replace("+00:00", "Z")
        evidence.update({"measured_at": target["measured_at"], "age_seconds": age,
                         "transport_timestamp_preserved": target.get("timestamp") or result.get("timestamp")})

    elif code == "D2":
        controls["ui_status_override"] = "offline"
        controls["ui_override_scope"] = {"farm_key": evidence["farm_key"], "node_id": run.get("node_id")}
        evidence.update({"ui_status": "offline", "sensor_payload_mutated": False,
                         "expected_fresh_sample": before is not None})

    elif code == "D3":
        base_boot = str(target.get("boot_id") or result.get("boot_id") or "virtual-boot")
        new_boot = str(run.get("new_boot_id") or f"{base_boot}:scenario:{run.get('scenario_run_id', 'reboot')}")[:100]
        old_boot, old_uptime = target.get("boot_id"), target.get("uptime_seconds")
        target["boot_id"] = new_boot
        target["uptime_seconds"] = max(0, int(sample_index))
        target["sample_sequence"] = max(1, int(sample_index) + 1)
        evidence.update({"previous_boot_id": old_boot, "boot_id": new_boot,
                         "previous_uptime_seconds": old_uptime, "uptime_seconds": target["uptime_seconds"],
                         "sample_sequence": target["sample_sequence"]})

    elif code == "D4":
        mode = str(run.get("sequence_mode", "gap")).lower()
        if mode not in {"gap", "duplicate", "regression"}:
            mode = "gap"
        prior = _number(run.get("previous_sequence"))
        if prior is None:
            prior = _number(target.get("sample_sequence", target.get("sequence")))
        if prior is None:
            prior = float(sample_index + 10)
        if mode == "gap":
            current = int(prior) + max(2, int(_number(run.get("gap_size")) or 3))
        elif mode == "duplicate":
            current = int(prior)
        else:
            current = max(0, int(prior) - max(1, int(_number(run.get("regression_size")) or 1)))
        target["sample_sequence"] = current
        if "sample_sequence" in result:
            result["sample_sequence"] = current
        evidence.update({"sequence_mode": mode, "previous_sequence": int(prior), "sample_sequence": current,
                         "gap_size": max(0, current - int(prior) - 1) if mode == "gap" else 0})

    elif code == "D5":
        base_interval = max(1, int(_number(run.get("base_interval_seconds")) or 60))
        multiplier = max(2, int(_number(run.get("cadence_multiplier")) or 5))
        controls.update({"cadence_multiplier": multiplier,
                         "publish_interval_seconds": base_interval * multiplier})
        evidence.update({"base_interval_seconds": base_interval,
                         "simulated_interval_seconds": base_interval * multiplier,
                         "cadence_multiplier": multiplier})

    elif code == "D6":
        prior_id = target.get("device_id") or result.get("device_id")
        unknown_id = str(run.get("unknown_device_id") or f"unregistered-{run.get('scenario_run_id', 'scenario')}")[:100]
        target["device_id"] = unknown_id
        evidence.update({"previous_device_id": prior_id, "device_id": unknown_id,
                         "farm_key": evidence["farm_key"], "registration_status": "unknown"})

    elif code == "D7":
        health = {
            "battery_pct": _bounded(_number(run.get("battery_pct")), 7.0, 0.0, 100.0),
            "rssi_dbm": _bounded(_number(run.get("rssi_dbm")), -112.0, -140.0, 0.0),
            "voltage_v": _bounded(_number(run.get("voltage_v")), 2.7, 0.0, 60.0),
        }
        readings.update(health)
        evidence.update(health)

    return {
        "code": code,
        "scenario_type": definition["scenario_type"],
        "payload": result,
        "controls": controls,
        "evidence": evidence,
        "synthetic": True,
    }


def recovery_condition(
    scenario_type: Any,
    payload: Mapping[str, Any],
    run: Mapping[str, Any],
    *,
    normal_samples: int = 0,
    freshness_limit_seconds: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a conservative, evidence-based recovery decision.

    A scenario being stopped is never recovery evidence. Device-health recovery
    limits and calibrated domains must be supplied by the caller; if absent the
    result remains pending and asks for human verification.
    """
    definition = resolve_scenario(scenario_type)
    if definition is None:
        return {"ok": False, "reason": "unsupported_scenario", "evidence": {}}
    code = definition["code"]
    try:
        target, _peer = _target_node(dict(payload), run)
    except ValueError:
        target = dict(payload)
    readings = _readings(target)
    required = int(definition.get("recovery_samples", 1))
    if normal_samples < required:
        return {"ok": False, "reason": "insufficient_normal_samples",
                "evidence": {"normal_samples": normal_samples, "required_samples": required}}

    if code in {"S1", "S2", "S3", "S4", "S5", "S6"}:
        field = _READING_FIELDS["soil_humidity"]
        value = _number(readings.get(field))
        if value is None:
            return {"ok": False, "reason": "soil_humidity_missing", "evidence": {}}
        low = _number(run.get("physical_min", 0.0))
        high = _number(run.get("physical_max", 100.0))
        if low is None or high is None or not low <= value <= high:
            return {"ok": False, "reason": "reading_outside_configured_physical_range",
                    "evidence": {"value": value, "min": low, "max": high}}
        if code in {"S4", "S5"} and not run.get("human_or_reference_check"):
            return {"ok": False, "reason": "reference_check_required",
                    "evidence": {"value": value, "required": "calibration_or_peer_confirmation"}}
        if code == "S1" and value == _number((run.get("scenario_state") or {}).get("flatline_value")):
            return {"ok": False, "reason": "still_at_flatline_value", "evidence": {"value": value}}
        if code == "S2":
            baseline = _number(run.get("baseline"))
            threshold = abs(_number(run.get("spike_recovery_delta")) or 8.0)
            if baseline is None or abs(value - baseline) > threshold:
                return {"ok": False, "reason": "spike_recovery_baseline_required_or_not_restored",
                        "evidence": {"value": value, "baseline": baseline, "max_delta": threshold}}
        if code == "S6":
            variance = _number(run.get("observed_variance"))
            maximum = _number(run.get("max_variance"))
            if variance is None or maximum is None or variance > maximum:
                return {"ok": False, "reason": "noise_variance_not_verified",
                        "evidence": {"observed_variance": variance, "max_variance": maximum}}
        return {"ok": True, "reason": "configured_sensor_recovery_samples_validated",
                "evidence": {"value": value, "normal_samples": normal_samples}}

    if code == "D1":
        stamp = _parse_utc(target.get("measured_at") or target.get("timestamp") or payload.get("timestamp"))
        if stamp is None:
            return {"ok": False, "reason": "measurement_time_unknown", "evidence": {}}
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        limit = max(1, int(freshness_limit_seconds or run.get("freshness_limit_seconds") or 120))
        age = (current - stamp).total_seconds()
        return {"ok": age <= limit, "reason": "fresh_sample" if age <= limit else "sample_still_stale",
                "evidence": {"age_seconds": round(age, 2), "limit_seconds": limit}}
    if code == "D2":
        online = payload.get("ui_online", target.get("online"))
        stamp = _parse_utc(target.get("measured_at") or target.get("timestamp") or payload.get("timestamp"))
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        limit = max(1, int(freshness_limit_seconds or run.get("freshness_limit_seconds") or 120))
        age = (current - stamp).total_seconds() if stamp else None
        is_online = online in (True, 1, "online", "ONLINE")
        fresh = age is not None and age <= limit
        return {"ok": is_online and fresh,
                "reason": "fresh_ui_readback_online" if is_online and fresh else "fresh_sample_and_ui_readback_required",
                "evidence": {"ui_online": online, "age_seconds": round(age, 2) if age is not None else None,
                             "freshness_limit_seconds": limit}}
    if code == "D3":
        boot_id = target.get("boot_id")
        uptime = _number(target.get("uptime_seconds"))
        previous_boot = run.get("previous_boot_id")
        if boot_id and uptime is not None and uptime > 0 and previous_boot and str(boot_id) != str(previous_boot):
            return {"ok": True, "reason": "new_boot_epoch_emitting", "evidence": {"boot_id": boot_id, "uptime_seconds": uptime}}
        return {"ok": False, "reason": "post_reboot_samples_required", "evidence": {"boot_id": boot_id, "uptime_seconds": uptime}}
    if code == "D4":
        sequence = _number(target.get("sample_sequence", target.get("sequence")))
        previous = _number(run.get("previous_sequence"))
        anomaly = any(target.get(flag) for flag in ("sequence_gap", "sequence_duplicate", "sequence_regression"))
        ok = sequence is not None and previous is not None and sequence > previous and not anomaly
        return {"ok": ok, "reason": "sequence_advancing" if ok else "sequence_progression_not_verified",
                "evidence": {"sample_sequence": sequence, "previous_sequence": previous, "anomaly": anomaly}}
    if code == "D5":
        observed = _number(run.get("observed_interval_seconds"))
        expected = _number(run.get("base_interval_seconds"))
        if observed is None or expected is None:
            return {"ok": False, "reason": "cadence_measurement_required", "evidence": {}}
        ok = observed <= expected * 1.5
        return {"ok": ok, "reason": "cadence_restored" if ok else "cadence_still_slow",
                "evidence": {"observed_interval_seconds": observed, "expected_interval_seconds": expected}}
    if code == "D6":
        registered = target.get("registered") is True or run.get("registration_confirmed") is True
        return {"ok": registered, "reason": "registration_confirmed" if registered else "registration_required",
                "evidence": {"device_id": target.get("device_id"), "registered": registered}}
    if code == "D7":
        thresholds = run.get("recovery_thresholds")
        if not isinstance(thresholds, Mapping):
            return {"ok": False, "reason": "device_specific_health_limits_required",
                    "evidence": {"battery_pct": target.get("battery_pct"), "rssi_dbm": target.get("rssi_dbm"),
                                 "voltage_v": target.get("voltage_v")}}
        checks = []
        for field, threshold, comparator in (
            ("battery_pct", "battery_min", "min"),
            ("rssi_dbm", "rssi_min", "min"),
            ("voltage_v", "voltage_min", "min"),
        ):
            limit = _number(thresholds.get(threshold))
            value = _number(readings.get(field))
            if limit is not None and value is not None:
                checks.append(value >= limit)
        ok = bool(checks) and all(checks)
        return {"ok": ok, "reason": "health_back_in_configured_range" if ok else "health_not_verified",
                "evidence": {"battery_pct": target.get("battery_pct"), "rssi_dbm": target.get("rssi_dbm"),
                             "voltage_v": target.get("voltage_v"), "thresholds_configured": True}}
    return {"ok": False, "reason": "no_recovery_rule", "evidence": {}}


def _parse_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        stamp = value
    elif isinstance(value, str) and value.strip():
        try:
            stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)


def _bounded(value: float | None, fallback: float, low: float, high: float) -> float:
    selected = fallback if value is None else value
    return round(max(low, min(high, selected)), 2)


def evaluate_sensor_device_scenario(
    scenario_type: Any,
    observed: Mapping[str, Any],
    *,
    history: Any = None,
    peer_observed: Mapping[str, Any] | None = None,
    previous: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate observed data, never the injector's expected-fault label.

    detected is True/False/None; None means UNKNOWN because evidence or
    configuration is insufficient. Inputs are read-only and never mutated.
    """
    definition = resolve_scenario(scenario_type)
    if definition is None:
        return _evaluation(None, "unsupported_scenario", {}, [])
    ctx = context if isinstance(context, Mapping) else {}
    try:
        target, _ = _target_node(dict(observed), ctx)
    except (TypeError, ValueError):
        target = dict(observed)
    values_now = _readings(target)
    rows = _history_rows(history)
    code = definition["code"]

    if code in {"S1", "S2", "S4", "S6"}:
        vals = [v for v in (_sample_value(row, "sh", ctx) for row in rows) if v is not None]
        current = _sensor_value(values_now, "sh")
        if code == "S1":
            needed = max(3, int(_number(ctx.get("flatline_min_samples")) or 4))
            if len(vals) < needed:
                return _evaluation(None, "insufficient_flatline_history", {"valid_samples": len(vals)}, ["history"])
            eps = abs(_number(ctx.get("flatline_epsilon")) or 0.01)
            result = max(vals) - min(vals) <= eps
            return _evaluation(result, "repeated_values" if result else "values_vary",
                               {"valid_samples": len(vals), "range": max(vals) - min(vals), "epsilon": eps}, [])
        if code == "S2":
            needed = max(3, int(_number(ctx.get("baseline_min_samples")) or 5))
            threshold = _number(ctx.get("spike_threshold"))
            if current is None or len(vals) < needed or threshold is None:
                return _evaluation(None, "spike_sample_baseline_or_threshold_missing",
                                   {"current": current, "baseline_samples": len(vals)}, ["current", "history", "spike_threshold"])
            center = _median(vals)
            delta = abs(current - center)
            return _evaluation(delta >= threshold, "baseline_deviation" if delta >= threshold else "within_threshold",
                               {"current": current, "baseline_median": center, "delta": delta, "threshold": threshold}, [])
        if code == "S4":
            needed = max(4, int(_number(ctx.get("drift_min_samples")) or 5))
            threshold = _number(ctx.get("min_drift_per_sample"))
            if len(vals) < needed or threshold is None:
                return _evaluation(None, "drift_history_or_threshold_missing",
                                   {"valid_samples": len(vals), "threshold": threshold}, ["history", "min_drift_per_sample"])
            slope = _linear_slope(vals)
            result = abs(slope) >= abs(threshold)
            return _evaluation(result, "sustained_drift" if result else "slope_within_limit",
                               {"slope_per_sample": slope, "threshold": abs(threshold), "valid_samples": len(vals)}, [])
        needed = max(3, int(_number(ctx.get("noise_min_samples")) or 5))
        maximum = _number(ctx.get("max_noise_variance"))
        if len(vals) < needed or maximum is None:
            return _evaluation(None, "noise_history_or_limit_missing",
                               {"valid_samples": len(vals), "max_variance": maximum}, ["history", "max_noise_variance"])
        variance = _variance(vals)
        result = variance > maximum
        return _evaluation(result, "variance_exceeded" if result else "variance_within_limit",
                           {"variance": variance, "max_variance": maximum, "valid_samples": len(vals)}, [])

    if code == "S3":
        value = _sensor_value(values_now, "sh")
        low, high = _number(ctx.get("physical_min")), _number(ctx.get("physical_max"))
        if value is None or low is None or high is None:
            return _evaluation(None, "reading_or_configured_range_missing",
                               {"value": value, "min": low, "max": high}, ["reading", "physical_range"])
        result = not low <= value <= high
        return _evaluation(result, "outside_configured_range" if result else "within_configured_range",
                           {"value": value, "min": low, "max": high}, [])

    if code == "S5":
        try:
            peer, _ = _target_node(dict(peer_observed or {}), ctx)
        except (TypeError, ValueError):
            peer = dict(peer_observed or {})
        left, right = _sensor_value(values_now, "sh"), _sensor_value(_readings(peer), "sh")
        threshold = _number(ctx.get("max_peer_difference"))
        ta, tb = _measurement_stamp(observed), _measurement_stamp(peer_observed or {})
        tolerance = _number(ctx.get("peer_time_tolerance_seconds"))
        if left is None or right is None or threshold is None or ta is None or tb is None or tolerance is None:
            return _evaluation(None, "peer_values_alignment_or_limit_missing",
                               {"value": left, "peer_value": right, "max_difference": threshold},
                               ["peer_sample", "timestamps", "peer_limit"])
        time_delta = abs((ta - tb).total_seconds())
        if time_delta > tolerance:
            return _evaluation(None, "peer_samples_not_time_aligned",
                               {"time_delta_seconds": time_delta, "tolerance_seconds": tolerance}, [])
        delta = abs(left - right)
        result = delta > threshold
        return _evaluation(result, "peer_difference_exceeded" if result else "peer_difference_within_limit",
                           {"difference": delta, "max_difference": threshold, "time_delta_seconds": time_delta}, [])

    if code == "D1":
        measured, limit = _measurement_stamp(observed), _number(ctx.get("stale_after_seconds"))
        now = _parse_utc(ctx.get("now")) or datetime.now(timezone.utc)
        if measured is None or limit is None:
            return _evaluation(None, "measurement_time_or_freshness_limit_missing", {}, ["measurement_time", "stale_after_seconds"])
        age = (now - measured).total_seconds()
        received = _received_stamp(observed)
        delay = (received - measured).total_seconds() if received else None
        result = age > limit
        return _evaluation(result, "measurement_stale" if result else "measurement_fresh",
                           {"age_seconds": age, "limit_seconds": limit, "transport_delay_seconds": delay}, [])

    if code == "D2":
        measured = _measurement_stamp(observed)
        limit, ui = _number(ctx.get("freshness_limit_seconds")), observed.get("ui_status", observed.get("status"))
        now = _parse_utc(ctx.get("now")) or datetime.now(timezone.utc)
        if measured is None or limit is None or ui is None:
            return _evaluation(None, "fresh_sample_or_ui_state_missing", {}, ["measurement_time", "freshness_limit", "ui_status"])
        age = (now - measured).total_seconds()
        conflict = age <= limit and str(ui).lower() in {"offline", "down", "disconnected"}
        return _evaluation(conflict, "fresh_data_ui_offline_conflict" if conflict else "no_freshness_status_conflict",
                           {"sample_age_seconds": age, "freshness_limit_seconds": limit, "ui_status": ui}, [])

    if code in {"D3", "D4"}:
        current_boot = _provenance_value(observed, "boot_id")
        old_boot = _provenance_value(previous or {}, "boot_id")
        seq = _number(_provenance_value(observed, "sample_sequence", "sequence"))
        old_seq = _number(_provenance_value(previous or {}, "sample_sequence", "sequence"))
        if seq is None or old_seq is None:
            return _evaluation(None, "current_or_previous_sequence_missing", {}, ["current_sequence", "previous_sample"])
        if code == "D3":
            uptime = _number(_provenance_value(observed, "uptime_seconds"))
            if not current_boot or not old_boot:
                return _evaluation(None, "boot_epoch_comparison_missing", {}, ["current_boot_id", "previous_boot_id"])
            reboot = str(current_boot) != str(old_boot)
            if not reboot:
                return _evaluation(False, "boot_epoch_unchanged", {"boot_id": current_boot}, [])
            # Sequence numbers may legitimately restart at 1 with a new boot_id.
            # Require positive uptime and a valid new-boot sequence, not a
            # numerical comparison across different boot epochs.
            if uptime is None or uptime <= 0 or seq < 1:
                return _evaluation(None, "reboot_seen_post_boot_progress_unverified",
                                   {"boot_id": current_boot, "sequence": seq, "uptime_seconds": uptime},
                                   ["new_boot_sequence", "positive_uptime"])
            return _evaluation(True, "boot_epoch_changed_with_progress",
                               {"previous_boot_id": old_boot, "boot_id": current_boot, "sequence": seq, "uptime_seconds": uptime}, [])
        if current_boot and old_boot and str(current_boot) != str(old_boot):
            return _evaluation(None, "sequence_comparison_crosses_boot_epoch", {}, ["same_boot_comparison"])
        delta = seq - old_seq
        kind = "duplicate" if delta == 0 else "regression" if delta < 0 else "gap" if delta > 1 else "consecutive"
        return _evaluation(delta != 1, "sequence_" + kind, {"sequence": seq, "previous_sequence": old_seq, "delta": delta}, [])

    if code == "D5":
        stamps = [stamp for stamp in (_received_stamp(row) for row in rows) if stamp is not None]
        expected = _number(ctx.get("expected_interval_seconds"))
        if len(stamps) < 3 or expected is None:
            return _evaluation(None, "cadence_history_or_baseline_missing",
                               {"timestamps": len(stamps), "expected_interval_seconds": expected},
                               ["receive_timestamps", "expected_interval_seconds"])
        intervals = [(b - a).total_seconds() for a, b in zip(stamps, stamps[1:])]
        measured = _median(intervals)
        factor = max(1.0, _number(ctx.get("slowdown_factor")) or 1.5)
        result = measured > expected * factor
        return _evaluation(result, "cadence_slow" if result else "cadence_within_limit",
                           {"median_interval_seconds": measured, "expected_interval_seconds": expected, "factor": factor}, [])

    if code == "D6":
        device = _provenance_value(observed, "device_id") or observed.get("device_id")
        registered = ctx.get("registered_device_ids")
        if not device or not isinstance(registered, (list, tuple, set, frozenset)):
            return _evaluation(None, "device_id_or_registry_missing", {"device_id": device},
                               ["device_id", "registered_device_ids"])
        result = str(device) not in {str(item) for item in registered}
        return _evaluation(result, "device_unknown" if result else "device_registered", {"device_id": str(device)}, [])

    if code == "D7":
        limits = ctx.get("device_health_limits")
        if not isinstance(limits, Mapping):
            return _evaluation(None, "device_specific_health_limits_missing", {}, ["device_health_limits"])
        checks = []
        for field, lower, upper in (("battery_pct", "battery_min", "battery_max"),
                                    ("rssi_dbm", "rssi_min", "rssi_max"),
                                    ("voltage_v", "voltage_min", "voltage_max")):
            value = _number(values_now.get(field))
            low, high = _number(limits.get(lower)), _number(limits.get(upper))
            if value is not None and (low is not None or high is not None):
                checks.append((field, value, (low is not None and value < low) or (high is not None and value > high)))
        if not checks:
            return _evaluation(None, "health_values_or_device_limits_missing", {}, ["health_values", "matching_limits"])
        bad = [field for field, _value, outside in checks if outside]
        return _evaluation(bool(bad), "health_limit_exceeded" if bad else "health_within_limits",
                           {"checks": [{"field": f, "value": v, "outside": x} for f, v, x in checks]}, [])
    return _evaluation(None, "no_evaluator", {}, [])


def _evaluation(detected: bool | None, reason: str, evidence: Mapping[str, Any], missing: list[str]) -> dict[str, Any]:
    status = "UNKNOWN" if detected is None else ("DETECTED" if detected else "NOT_DETECTED")
    return {"detected": detected, "status": status, "reason": reason,
            "evidence": dict(evidence), "missing": list(missing)}


def _history_rows(history: Any) -> list[Mapping[str, Any]]:
    rows = history.get("samples") or history.get("rows") or history.get("history") or [] if isinstance(history, Mapping) else history
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, (list, tuple)) else []


def _sample_value(sample: Mapping[str, Any], field: str, context: Mapping[str, Any]) -> float | None:
    try:
        target, _ = _target_node(dict(sample), context)
    except (TypeError, ValueError):
        target = dict(sample)
    return _sensor_value(_readings(target), field)


def _sensor_value(readings: Mapping[str, Any], field: str) -> float | None:
    names = ("sh", "soil_humidity", "soil_hum") if field == "sh" else (field,)
    for name in names:
        value = _number(readings.get(name))
        if value is not None:
            return value
    return None


def _provenance_value(sample: Mapping[str, Any], *keys: str) -> Any:
    for name in ("", "source", "provenance", "meta", "metadata"):
        container = sample if not name else sample.get(name)
        if isinstance(container, Mapping):
            for key in keys:
                if container.get(key) is not None:
                    return container[key]
    return None


def _measurement_stamp(sample: Mapping[str, Any]) -> datetime | None:
    try:
        target, _ = _target_node(dict(sample), {})
    except (TypeError, ValueError):
        target = dict(sample)
    readings = _readings(target)
    return _parse_utc(readings.get("measured_at") or target.get("measured_at")
                      or readings.get("timestamp") or target.get("timestamp") or sample.get("timestamp"))


def _received_stamp(sample: Mapping[str, Any]) -> datetime | None:
    source = sample.get("source")
    nested = source.get("app_received_at") if isinstance(source, Mapping) else None
    return _parse_utc(sample.get("app_received_at") or sample.get("received_at") or nested or sample.get("timestamp"))


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _variance(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _linear_slope(values: list[float]) -> float:
    x_mean, y_mean = (len(values) - 1) / 2, sum(values) / len(values)
    denominator = sum((x - x_mean) ** 2 for x in range(len(values)))
    return sum((x - x_mean) * (y - y_mean) for x, y in enumerate(values)) / denominator if denominator else 0.0
