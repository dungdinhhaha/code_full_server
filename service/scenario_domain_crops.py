"""Evidence-gated crop/climate scenario evaluation for SMIOT.

This module is deliberately pure: callers pass the scenario run, one telemetry
payload, and explicitly loaded operational context. It does not read or write
MongoDB, emit Datadog telemetry, or operate actuators. Missing agronomic
calibration is represented as UNKNOWN/HOLD, never replaced with guessed limits.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any


def _scenario(code: str, title: str, required: tuple[str, ...], trigger: str,
              recovery: tuple[str, ...], policy: str) -> dict[str, Any]:
    return {
        "code": code,
        "domain": "crop_climate",
        "title": title,
        "required_fields": required,
        "trigger_semantics": trigger,
        "recovery_evidence": recovery,
        "safe_response": policy,
    }


# Required fields describe evidence required to make a positive finding. They
# are not promises that every current device publishes those fields.
CROP_SCENARIOS: dict[str, dict[str, Any]] = {
    "C1": _scenario("C1", "Soil moisture outside approved stage band",
        ("id6.node*.sh", "context.stage", "context.stage_envelope.bands.sh"),
        "A fresh soil-moisture reading is outside an approved, effective,",
        ("fresh soil-moisture readings back inside the same envelope", "envelope version recorded"),
        "HOLD irrigation decisions that depend on an uncalibrated or invalid reading"),
    "C2": _scenario("C2", "VPD outside approved stage band",
        ("id6.node*.at", "id6.node*.ah", "context.stage_envelope.bands.vpd_kpa"),
        "Calculate VPD from valid temperature/RH and compare only with an approved stage band",
        ("fresh valid inputs and VPD back inside the same envelope", "envelope version recorded"),
        "WARN; HOLD climate-dependent control when inputs or calibration are unknown"),
    "C3": _scenario("C3", "Midday heat stress signal",
        ("id6.node*.at history", "context.is_daytime", "context.local_time", "context.heat_policy", "context.stage_envelope.bands.air_temperature_day"),
        "Daytime heat is outside the approved stage/day band for the configured duration",
        ("temperature below configured recovery bound for configured duration", "ventilation feedback if actioned"),
        "Only request configured ventilation response; otherwise WARN/HOLD"),
    "C4": _scenario("C4", "Possible overwatering / poor drainage",
        ("id3 irrigation flow", "id7.drain_l", "id6.node*.sh history", "context.overwatering_policy"),
        "Compare measured irrigation, measured drainage, and soil-moisture trend using configured policy",
        ("drainage and soil trend satisfy configured recovery policy", "operator inspection if required"),
        "HOLD additional irrigation; do not diagnose root waterlogging from one reading"),
    "C5": _scenario("C5", "Possible water deficit during rapid fruit growth",
        ("context.stage", "context.stage_water_balance", "context.stage_envelope.bands.sh"),
        "Configured fruit-growth stage plus measured, complete negative water balance or out-of-band moisture",
        ("water balance and fresh soil readings satisfy configured recovery policy", "irrigation response verified"),
        "WARN and preserve approved irrigation schedule; never invent a water dose"),
    "C6": _scenario("C6", "Drain EC accumulation signal",
        ("id4.ec", "id7.drain_ec_ms_cm history", "context.ec_policy"),
        "Persistent inlet/outlet EC difference meets configured, sourced policy",
        ("valid inlet/outlet samples return within configured difference band", "recipe change requires human approval"),
        "WARN for inspection; never change nutrient recipe automatically"),
    "C7": _scenario("C7", "Pollination window needs attention",
        ("context.crop_cycle.stage", "context.pollination_window", "context.pollination_events"),
        "Only flag a configured window with missing explicit human/device event; never infer pollination failure from climate alone",
        ("authorized pollination event recorded or window corrected with audit trail",),
        "Reminder only; do not assert missed pollination or fruit-set loss"),
    "C8": _scenario("C8", "Prolonged humidity / low-VPD risk",
        ("id6.node*.ah history", "id6.node*.at history", "context.disease_risk_policy"),
        "Configured humidity/VPD condition persists for configured duration",
        ("climate condition clears for configured duration and operator records crop inspection",),
        "WARN for inspection; do not claim disease is present"),
    "C9": _scenario("C9", "Measured rain may reduce future irrigation need",
        ("context.rainfall.observed_mm", "context.irrigation_schedule", "id6.node*.sh"),
        "Observed rainfall plus fresh soil readings satisfy configured schedule-adjustment policy",
        ("new rainfall/soil evidence recorded and schedule adjustment audited",),
        "May propose cancellation of a future safe-to-cancel cycle; never interrupt active irrigation on forecast alone"),
    "C10": _scenario("C10", "Water-system anomaly: pressure/flow or rain ingress",
        ("id3.pressure_bar", "id3.f1/id3.f2", "id3 pump state", "context.rainfall.observed_mm", "id6.node*.sh"),
        "Low-pressure/high-flow can indicate a hydraulic mismatch; rain-linked wetness with pump off is only a possible ingress correlation",
        ("pressure/flow stable after safe-stop; field inspection required to name a physical cause",),
        "Safe-stop only under the existing local interlock; classify evidence as mismatch/possible ingress, never confirmed pipe or roof leak"),
}


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _path(obj: Any, dotted: str) -> Any:
    current = obj
    for part in dotted.split("."):
        if isinstance(current, Mapping):
            current = current.get(part)
        else:
            return None
    return current


def _readings(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize established `id6` node readings without changing the source."""
    nodes = payload.get("id6")
    if not isinstance(nodes, Mapping):
        return {}
    result: dict[str, Any] = {}
    for node, values in nodes.items():
        if not isinstance(values, Mapping):
            continue
        result[str(node).lower()] = {
            "at": _num(values.get("at", values.get("air_temp", values.get("air_temperature")))),
            "ah": _num(values.get("ah", values.get("air_hum", values.get("air_humidity")))),
            "st": _num(values.get("st", values.get("soil_temp", values.get("soil_temperature")))),
            "sh": _num(values.get("sh", values.get("soil_hum", values.get("soil_humidity")))),
            "sec": _num(values.get("sec", values.get("soil_ec", values.get("ec")))),
            "measured_at": values.get("measured_at", values.get("timestamp")),
        }
    return result


def vpd_kpa(temperature_c: Any, relative_humidity_pct: Any) -> float | None:
    """Compute physical VPD (Tetens); this does not imply an agronomic limit."""
    temperature, humidity = _num(temperature_c), _num(relative_humidity_pct)
    if temperature is None or humidity is None or not (-80 < temperature <= 80 and 0 <= humidity <= 100):
        return None
    svp = 0.6108 * math.exp(17.27 * temperature / (temperature + 237.3))
    return svp * (1.0 - humidity / 100.0)


def _band(context: Mapping[str, Any], key: str) -> tuple[float | None, float | None, str | None]:
    envelope = context.get("stage_envelope")
    if not isinstance(envelope, Mapping):
        return None, None, None
    # Only a caller that explicitly marks a DB-resolved approved envelope may
    # use it. `effective_from` is caller-controlled input and is not proof of
    # approval by itself. demo_mode adds this marker only after the MongoDB
    # getter has filtered approval and field calibration.
    if envelope.get("approval_status") != "approved" or envelope.get("calibration_status") != "field_calibrated":
        return None, None, None
    version = envelope.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        return None, None, None
    source = envelope.get("source")
    if not isinstance(source, Mapping) or not str(source.get("citation") or "").strip():
        return None, None, None
    bands = envelope.get("bands")
    raw = bands.get(key) if isinstance(bands, Mapping) else None
    if not isinstance(raw, Mapping):
        return None, None, None
    low, high = _num(raw.get("min")), _num(raw.get("max"))
    if low is None or high is None or low > high:
        return None, None, None
    return low, high, str(version)


def _outside(value: float | None, low: float | None, high: float | None) -> str | None:
    if value is None or low is None or high is None:
        return None
    if value < low:
        return "below"
    if value > high:
        return "above"
    return None


def _node_value(readings: Mapping[str, Any], metric: str) -> tuple[str | None, float | None]:
    for node, values in readings.items():
        if isinstance(values, Mapping) and values.get(metric) is not None:
            return node, values[metric]
    return None, None


def _node_environment(readings: Mapping[str, Any]) -> tuple[str | None, float | None, float | None]:
    """Return temperature and RH from the same node/sample only."""
    for node, values in readings.items():
        if not isinstance(values, Mapping):
            continue
        temperature, humidity = _num(values.get("at")), _num(values.get("ah"))
        if temperature is not None and humidity is not None:
            return node, temperature, humidity
    return None, None, None


def _fresh_sample_age(payload: Mapping[str, Any], node: str | None,
                      context: Mapping[str, Any]) -> tuple[float | None, str | None]:
    """Require an explicit freshness limit and a timezone-aware sample time.

    This check is for real W7/W8 evaluations. Synthetic scenario overlays are
    separate and do not use this gate. Missing freshness policy or provenance
    yields unknown/HOLD rather than interpreting an old sample as current.
    """
    limit = _num(context.get("sensor_freshness_limit_seconds"))
    if limit is None or limit <= 0:
        return None, "freshness_limit_missing"
    raw_nodes = payload.get("id6")
    node_reading = next(
        (value for key, value in raw_nodes.items()
         if node and str(key).lower() == str(node).lower()),
        None,
    ) if isinstance(raw_nodes, Mapping) else None
    if not isinstance(node_reading, Mapping):
        return None, "sample_node_missing"
    stamp = node_reading.get("measured_at") or node_reading.get("timestamp") or payload.get("timestamp")
    try:
        sampled_at = _parse_dt(stamp)
        reference = _parse_dt(context.get("now")) if context.get("now") is not None else datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return None, "sample_timestamp_missing_or_invalid"
    age = (reference - sampled_at).total_seconds()
    if age < -30:
        return None, "sample_timestamp_in_future"
    if age > limit:
        return age, "sample_stale"
    return max(0.0, age), None


def _finding(code: str, scenario_run: Mapping[str, Any], payload: Mapping[str, Any],
             evidence: Mapping[str, Any], confidence: float = 0.8) -> dict[str, Any]:
    run_id = scenario_run.get("scenario_run_id", scenario_run.get("run_id"))
    farm = scenario_run.get("farm_key", payload.get("farm_key"))
    out = {
        "group": "crop_climate", "code": code, "status": "candidate",
        "severity": "warning", "confidence": confidence,
        "evidence": dict(evidence),
    }
    if farm is not None:
        out["farm_key"] = str(farm)
    if scenario_run.get("lot_id") is not None:
        out["lot_id"] = str(scenario_run["lot_id"])
    if run_id is not None:
        out["scenario_run_id"] = str(run_id)
    return out


def _run_code(scenario_run: Mapping[str, Any]) -> str | None:
    value = scenario_run.get("code", scenario_run.get("scenario_code", scenario_run.get("scenario_type")))
    if value is None:
        return None
    token = str(value).strip().upper()
    if token in CROP_SCENARIOS:
        return token
    aliases = {"SOIL_MOISTURE_BAND": "C1", "VPD_BAND": "C2", "MIDDAY_HEAT": "C3",
               "OVERWATERING": "C4", "WATER_DEFICIT": "C5", "EC_ACCUMULATION": "C6",
               "POLLINATION_WINDOW": "C7", "DISEASE_RISK": "C8", "RAIN_IRRIGATION": "C9",
               "RAIN_OR_LEAK": "C10"}
    return aliases.get(token)


def evaluate_crop_scenario(
    scenario_run: Mapping[str, Any],
    telemetry_payload: Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive a simulation overlay and evidence-backed candidate for C1-C10.

    The overlay is an explicit proposed sensor-field patch for a simulator. It
    is never merged into or written over the supplied payload. C1/C2/C3/C5 can
    only create out-of-band stimuli from a trusted calibrated envelope. Other
    cases require measured/context evidence and are not faked by this module.
    """
    if not isinstance(scenario_run, Mapping) or not isinstance(telemetry_payload, Mapping):
        raise TypeError("scenario_run and telemetry_payload must be mappings")
    context = context if isinstance(context, Mapping) else {}
    code = _run_code(scenario_run)
    if code is None:
        return {"scenario_id": None, "status": "unknown", "response": "HOLD",
                "overlay": None, "finding": None, "reason": "Unknown crop scenario code."}
    meta = CROP_SCENARIOS[code]
    readings = _readings(telemetry_payload)
    soil_node, sh = _node_value(readings, "sh")
    air_node, at, ah = _node_environment(readings)
    node = air_node if code == "C2" else soil_node
    stage = context.get("stage") or _path(context, "crop_cycle.stage")
    crop_cycle = context.get("crop_cycle")
    verified_lot_id = (scenario_run.get("lot_id") or context.get("lot_id")
                       or (crop_cycle.get("lot_id") if isinstance(crop_cycle, Mapping) else None))
    finding_run = scenario_run
    if scenario_run.get("lot_id") is None and verified_lot_id is not None:
        finding_run = {**scenario_run, "lot_id": verified_lot_id}
    low_sh, high_sh, envelope_version = _band(context, "sh")
    overlay: dict[str, Any] | None = None
    finding: dict[str, Any] | None = None
    reason = ""
    status = "unknown"
    response = "HOLD"
    evidence: dict[str, Any] = {}

    # A threshold comparison is only meaningful for a recent measurement.
    # Require the caller to supply its cadence-derived freshness limit; never
    # guess that an old or untagged sample still represents current conditions.
    freshness_age = None
    freshness_error = None
    if code in {"C1", "C2", "C5"} and not bool(scenario_run.get("simulate", False)):
        freshness_age, freshness_error = _fresh_sample_age(telemetry_payload, node, context)
        if freshness_error:
            evidence = {"freshness_status": freshness_error,
                        **({"sample_age_seconds": round(freshness_age, 1)} if freshness_age is not None else {})}
            reason = "Freshness cannot be confirmed; keep the crop decision on HOLD."

    if code in {"C1", "C5"}:
        if freshness_error:
            pass
        elif not stage:
            reason = "Crop stage is not explicitly assigned."
        elif low_sh is None or high_sh is None:
            reason = "No approved, field-calibrated soil-moisture envelope is available."
        elif code == "C5" and str(stage).lower() not in {"fruit_growth", "rapid_fruit_growth", "fruit_filling"}:
            status, response = "not_applicable", "WARN"
            reason = "The configured crop stage is not a rapid-fruit-growth stage."
        elif bool(scenario_run.get("simulate", False)):
            direction = str(scenario_run.get("direction", "below")).lower()
            target = math.nextafter(low_sh, -math.inf) if direction == "below" else math.nextafter(high_sh, math.inf)
            node = node or "node1"
            overlay = {"synthetic": True, "scenario_code": code, "id6": {node: {"sh": target}},
                       "envelope_version": envelope_version}
            status, response = "triggered", "HOLD"
            reason = "Simulation stimulus is derived just outside the calibrated band; no threshold is invented."
            evidence = {"metric": "soil_humidity", "value": target,
                        "bound": low_sh if direction == "below" else high_sh,
                        "side": direction, "stage": stage, "envelope_version": envelope_version,
                        "synthetic": True}
            finding = _finding(code, finding_run, telemetry_payload, evidence)
        else:
            side = _outside(sh, low_sh, high_sh)
            if side:
                status, response = "triggered", "HOLD"
                reason = "Fresh soil-moisture value is outside the approved stage band."
                evidence = {"metric": "soil_humidity", "value": sh,
                            "bound": low_sh if side == "below" else high_sh,
                            "side": side, "node": node, "stage": stage,
                            "envelope_version": envelope_version,
                            "sample_age_seconds": round(freshness_age, 1) if freshness_age is not None else None,
                            "measured_at": _path(telemetry_payload, f"id6.{node}.measured_at") if node else None}
                finding = _finding(code, finding_run, telemetry_payload, evidence)
            else:
                status, response, reason = "not_triggered", "NONE", "Reading is inside the approved stage band."

    elif code == "C2":
        low, high, envelope_version = _band(context, "vpd_kpa")
        vpd = vpd_kpa(at, ah)
        if freshness_error:
            pass
        elif low is None or high is None:
            reason = "No approved, field-calibrated VPD band is available."
        elif vpd is None:
            reason = "Temperature/RH input is absent or outside physical validity."
        elif bool(scenario_run.get("simulate", False)):
            direction = str(scenario_run.get("direction", "above")).lower()
            target = math.nextafter(low, -math.inf) if direction == "below" else math.nextafter(high, math.inf)
            svp = 0.6108 * math.exp(17.27 * at / (at + 237.3))  # at is valid because vpd_kpa succeeded
            synthetic_rh = (1.0 - target / svp) * 100.0
            if not 0 <= synthetic_rh <= 100:
                reason = "Configured VPD band cannot be represented by valid RH at the current temperature."
            else:
                node = node or "node1"
                overlay = {"synthetic": True, "scenario_code": code, "id6": {node: {"ah": synthetic_rh}},
                           "envelope_version": envelope_version}
                status, response = "triggered", "WARN"
                reason = "Simulation RH is derived from a configured VPD boundary and observed temperature."
                evidence = {"metric": "vpd_kpa", "value": target,
                            "bound": low if direction == "below" else high,
                            "side": direction, "temperature_c": at,
                            "synthetic": True, "envelope_version": envelope_version}
                finding = _finding(code, finding_run, telemetry_payload, evidence)
        else:
            side = _outside(vpd, low, high)
            if side:
                status, response = "triggered", "WARN"
                reason = "Calculated VPD is outside the approved stage band."
                evidence = {"metric": "vpd_kpa", "value": vpd,
                            "bound": low if side == "below" else high, "side": side,
                            "temperature_c": at, "relative_humidity_pct": ah,
                            "sample_age_seconds": round(freshness_age, 1) if freshness_age is not None else None,
                            "envelope_version": envelope_version}
                finding = _finding(code, finding_run, telemetry_payload, evidence)
            else:
                status, response, reason = "not_triggered", "NONE", "VPD is inside the approved stage band."

    elif code == "C3":
        low, high, envelope_version = _band(context, "air_temperature_day")
        if context.get("is_daytime") is not True or not context.get("local_time"):
            reason = "A timezone-aware daytime classification is required; midpoint cannot be inferred from an unlabelled timestamp."
        elif high is None:
            reason = "No approved, field-calibrated daytime temperature band is available."
        elif at is None:
            reason = "No valid air-temperature reading is available."
        elif bool(scenario_run.get("simulate", False)):
            node = node or "node1"
            target = math.nextafter(high, math.inf)
            overlay = {"synthetic": True, "scenario_code": code, "id6": {node: {"at": target}},
                       "envelope_version": envelope_version}
            status, response = "triggered", "WARN"
            reason = "Synthetic heat stimulus is derived from the approved daytime upper band."
            evidence = {"metric": "air_temperature", "value": target, "bound": high,
                        "stage": stage, "local_time": context.get("local_time"),
                        "envelope_version": envelope_version, "synthetic": True}
            finding = _finding(code, finding_run, telemetry_payload, evidence)
        else:
            heat_policy = context.get("heat_policy")
            history = context.get("history")
            min_duration = _num(heat_policy.get("min_duration_minutes")) if isinstance(heat_policy, Mapping) else None
            if min_duration is None or not isinstance(history, Sequence) or isinstance(history, (str, bytes)):
                reason = "A configured heat duration and timestamped history are required; one hot sample is insufficient."
            else:
                qualifying: list[datetime] = []
                for item in history:
                    if not isinstance(item, Mapping):
                        continue
                    value = _num(item.get("at"))
                    if value is None or value <= high:
                        qualifying = []
                        continue
                    try:
                        qualifying.append(_parse_dt(item.get("timestamp")))
                    except (TypeError, ValueError):
                        qualifying = []
                duration_min = (qualifying[-1] - qualifying[0]).total_seconds() / 60 if len(qualifying) > 1 else 0
                if at > high and duration_min >= min_duration:
                    status, response = "triggered", "WARN"
                    reason = "Daytime temperature remained above the approved band for the configured duration."
                    evidence = {"metric": "air_temperature", "value": at, "bound": high,
                                "duration_minutes": duration_min, "configured_duration_minutes": min_duration,
                                "local_time": context.get("local_time"), "envelope_version": envelope_version}
                    finding = _finding(code, finding_run, telemetry_payload, evidence)
                elif at <= high:
                    status, response, reason = "not_triggered", "NONE", "Temperature is inside the approved daytime band."
                else:
                    reason = "Configured high-temperature duration has not elapsed."
    else:
        # Scenarios depending on time series, irrigation actions, rain, or
        # explicit crop events require caller-supplied evidence/policy.
        status, response, reason, evidence = _evaluate_context_case(code, scenario_run, telemetry_payload, context, readings)
        if status == "triggered":
            finding = _finding(code, finding_run, telemetry_payload, evidence)

    return {
        "scenario_id": code,
        "metadata": meta,
        "status": status,
        "response": response,
        "overlay": overlay,
        "finding": finding,
        # Stable, non-actuating decision evidence for downstream review. In
        # particular, UNKNOWN must remain visible when the approved crop-stage
        # envelope or scenario policy is absent; it must never become a guessed
        # threshold or a control recommendation.
        "decision_event": {
            "event": "crop_decision_evidence",
            "scenario_code": code,
            "farm_key": str(scenario_run.get("farm_key", telemetry_payload.get("farm_key", ""))),
            "lot_id": str(verified_lot_id) if verified_lot_id is not None else None,
            "scenario_run_id": scenario_run.get("scenario_run_id", scenario_run.get("run_id")),
            "status": status,
            "requires_human_review": status == "unknown",
            "automatic_recommendation": None,
            "response": response,
            "reason": reason,
            "evidence": dict(evidence),
            "envelope_version": envelope_version,
            "source": telemetry_payload.get("source"),
            "observed_at": telemetry_payload.get("timestamp"),
        },
        "evidence": evidence,
        "recovery_requirements": list(meta["recovery_evidence"]),
        "reason": reason,
    }


def apply_scenario_overlay(
    telemetry_payload: Mapping[str, Any], overlay: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Return a copied payload with an explicitly synthetic overlay applied.

    The original telemetry and nested readings remain untouched. An overlay
    without the synthetic marker is rejected so generated inputs cannot be
    silently presented as observed device data.
    """
    if not isinstance(telemetry_payload, Mapping):
        raise TypeError("telemetry_payload must be a mapping")
    result = dict(telemetry_payload)
    if overlay is None:
        return result
    if not isinstance(overlay, Mapping) or overlay.get("synthetic") is not True:
        raise ValueError("scenario overlay must be explicitly marked synthetic")
    patch = overlay.get("id6")
    if not isinstance(patch, Mapping):
        raise ValueError("overlay must contain an id6 node patch")
    original_id6 = telemetry_payload.get("id6")
    merged_id6 = {key: dict(value) if isinstance(value, Mapping) else value
                  for key, value in original_id6.items()} if isinstance(original_id6, Mapping) else {}
    for node, fields in patch.items():
        if not isinstance(fields, Mapping):
            raise ValueError("overlay node patch must be an object")
        current = merged_id6.get(node, {})
        current = dict(current) if isinstance(current, Mapping) else {}
        current.update(fields)
        merged_id6[node] = current
    result["id6"] = merged_id6
    result["scenario_overlay"] = {"synthetic": True,
                                   "scenario_code": overlay.get("scenario_code"),
                                   "envelope_version": overlay.get("envelope_version")}
    return result


def _evaluate_context_case(code: str, run: Mapping[str, Any], payload: Mapping[str, Any],
                           context: Mapping[str, Any], readings: Mapping[str, Any]
                           ) -> tuple[str, str, str, dict[str, Any]]:
    if code == "C4":
        policy = context.get("overwatering_policy")
        drain = _num(_path(payload, "id7.drain_l"))
        irrigation_volume = _num(context.get("irrigation_volume_l"))
        ratio_min = _num(policy.get("drain_to_irrigation_ratio_min")) if isinstance(policy, Mapping) else None
        if not isinstance(policy, Mapping) or ratio_min is None or irrigation_volume is None or drain is None:
            return "unknown", "HOLD", "Drainage readings or a configured comparison policy are missing.", {}
        if irrigation_volume <= 0:
            return "not_triggered", "NONE", "No active irrigation flow to compare.", {}
        ratio = drain / irrigation_volume
        if ratio >= ratio_min:
            return "triggered", "HOLD", "Observed drain-to-irrigation volume ratio meets configured policy; this is not a diagnosis of root damage.", {"irrigation_volume_l": irrigation_volume, "drain_l": drain, "ratio": ratio, "configured_min": ratio_min}
        return "not_triggered", "NONE", "Observed ratio is below configured policy.", {"irrigation_volume_l": irrigation_volume, "drain_l": drain, "ratio": ratio}
    if code == "C6":
        policy = context.get("ec_policy")
        inlet = _num(_path(payload, "id4.ec"))
        outlet = _num(_path(payload, "id7.drain_ec_ms_cm"))
        diff = _num(policy.get("outlet_minus_inlet_min_ms_cm")) if isinstance(policy, Mapping) else None
        if not isinstance(policy, Mapping) or diff is None or inlet is None or outlet is None:
            return "unknown", "HOLD", "Inlet/outlet EC or an approved comparison policy is missing.", {}
        delta = outlet - inlet
        if delta >= diff:
            return "triggered", "WARN", "Measured EC difference meets configured policy; nutrient recipe remains unchanged.", {"inlet_ec_ms_cm": inlet, "outlet_ec_ms_cm": outlet, "delta_ms_cm": delta, "configured_min": diff}
        return "not_triggered", "NONE", "Measured EC difference is below configured policy.", {"delta_ms_cm": delta}
    if code == "C7":
        window = context.get("pollination_window")
        events = context.get("pollination_events")
        if not isinstance(window, Mapping) or not window.get("start") or not window.get("end") or not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
            return "unknown", "HOLD", "A configured pollination window and explicit event list are required.", {}
        now = context.get("now") or payload.get("timestamp")
        try:
            now_dt = _parse_dt(now)
            start, end = _parse_dt(window["start"]), _parse_dt(window["end"])
        except (TypeError, ValueError):
            return "unknown", "HOLD", "Pollination window timestamps are invalid.", {}
        if not start <= now_dt <= end:
            return "not_triggered", "NONE", "Current time is outside the configured pollination window.", {"now": now_dt.isoformat()}
        if events:
            return "not_triggered", "NONE", "An explicit pollination event is recorded.", {"event_count": len(events)}
        return "triggered", "WARN", "Configured pollination window is active without an explicit event; this is a reminder, not proof of missed pollination.", {"window_start": start.isoformat(), "window_end": end.isoformat(), "event_count": 0, "claim_limit": "absence of record is not proof of biological failure"}
    if code == "C8":
        policy = context.get("disease_risk_policy")
        history = context.get("history")
        if not isinstance(policy, Mapping) or not isinstance(history, Sequence) or isinstance(history, (str, bytes)):
            return "unknown", "HOLD", "Time-series history and configured humidity/VPD duration policy are required.", {}
        min_hours = _num(policy.get("min_duration_hours"))
        max_gap_hours = _num(policy.get("max_gap_hours"))
        max_vpd = _num(policy.get("vpd_max_kpa"))
        min_rh = _num(policy.get("relative_humidity_min_pct"))
        if min_hours is None or max_gap_hours is None or max_gap_hours <= 0 or max_vpd is None or min_rh is None:
            return "unknown", "HOLD", "The risk policy lacks configured duration, continuity, or climate bands.", {}
        qualifying: list[datetime] = []
        for item in history:
            if not isinstance(item, Mapping):
                continue
            vpd = vpd_kpa(item.get("at"), item.get("ah"))
            rh = _num(item.get("ah"))
            stamp = item.get("timestamp")
            if vpd is None or rh is None or vpd > max_vpd or rh < min_rh:
                qualifying = []
                continue
            try:
                parsed_stamp = _parse_dt(stamp)
                if qualifying and (parsed_stamp - qualifying[-1]).total_seconds() > max_gap_hours * 3600:
                    qualifying = []
                qualifying.append(parsed_stamp)
            except (TypeError, ValueError):
                qualifying = []
        duration = (qualifying[-1] - qualifying[0]).total_seconds() / 3600 if len(qualifying) > 1 else 0.0
        if duration >= min_hours:
            return "triggered", "WARN", "Configured climate-risk condition persisted; no disease diagnosis is made.", {"duration_hours": duration, "configured_min_hours": min_hours, "sample_count": len(qualifying), "claim_limit": "risk signal only"}
        return "not_triggered", "NONE", "Configured duration condition was not met.", {"duration_hours": duration, "configured_min_hours": min_hours, "sample_count": len(qualifying)}
    if code == "C9":
        rainfall = context.get("rainfall")
        schedule = context.get("irrigation_schedule")
        policy = context.get("rain_irrigation_policy")
        rain_mm = _num(rainfall.get("observed_mm")) if isinstance(rainfall, Mapping) else None
        rain_source = rainfall.get("source") if isinstance(rainfall, Mapping) else None
        rain_at = rainfall.get("observed_at") if isinstance(rainfall, Mapping) else None
        threshold = _num(policy.get("rain_mm_min")) if isinstance(policy, Mapping) else None
        if rain_mm is None or not rain_source or not rain_at or not isinstance(schedule, Mapping) or threshold is None:
            return "unknown", "HOLD", "Observed rainfall, its source/time, schedule, and configured policy are required; forecast alone is insufficient.", {}
        _, soil = _node_value(readings, "sh")
        if rain_mm >= threshold:
            return "triggered", "WARN", "Observed rainfall meets configured policy; propose review of future irrigation only.", {"observed_rain_mm": rain_mm, "rain_source": rain_source, "observed_at": rain_at, "soil_moisture": soil, "schedule_id": schedule.get("schedule_id"), "active_irrigation_untouched": True}
        return "not_triggered", "NONE", "Observed rainfall is below configured policy.", {"observed_rain_mm": rain_mm}
    if code == "C10":
        hydraulic = context.get("hydraulic_policy")
        pressure = _num(_path(payload, "id3.pressure_bar"))
        flow = max([v for v in (_num(_path(payload, "id3.f1")), _num(_path(payload, "id3.f2"))) if v is not None], default=None)
        pump_on = bool(_path(payload, "id3.pump_line1_on") or _path(payload, "id3.pump_line2_on"))
        pmax = _num(hydraulic.get("low_pressure_max_bar")) if isinstance(hydraulic, Mapping) else None
        fmin = _num(hydraulic.get("high_flow_min_lpm")) if isinstance(hydraulic, Mapping) else None
        rain = context.get("rainfall")
        rain_mm = _num(rain.get("observed_mm")) if isinstance(rain, Mapping) else None
        rain_min = _num(hydraulic.get("rain_mm_min")) if isinstance(hydraulic, Mapping) else None
        if pressure is not None and flow is not None and pump_on and pmax is not None and fmin is not None and pressure <= pmax and flow >= fmin:
            return "triggered", "SAFE_STOP", "Observed pressure/flow mismatch meets configured hydraulic interlock policy; cause is unconfirmed.", {"pressure_bar": pressure, "flow_lpm": flow, "pump_on": True, "configured_pressure_max": pmax, "configured_flow_min": fmin, "classification": "hydraulic_mismatch_not_confirmed_pipe_leak"}
        if not pump_on and rain_mm is not None and rain_min is not None and rain_mm >= rain_min:
            _, soil = _node_value(readings, "sh")
            return "triggered", "WARN", "Rain and wetness context may be correlated; roof ingress is unconfirmed and needs inspection.", {"observed_rain_mm": rain_mm, "soil_moisture": soil, "pump_on": False, "classification": "possible_rain_linked_wetness_not_confirmed_roof_leak"}
        if pressure is None or flow is None or pmax is None or fmin is None:
            return "unknown", "HOLD", "Measured hydraulic values or configured interlock thresholds are missing.", {}
        return "not_triggered", "NONE", "No configured hydraulic mismatch or observed rain-linked context was found.", {"pressure_bar": pressure, "flow_lpm": flow, "pump_on": pump_on}
    return "unknown", "HOLD", "No evaluator is defined for this scenario.", {}


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("timestamp required")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return dt.astimezone(timezone.utc)


def evaluate_recovery(
    scenario_code: str,
    recovery_payload: Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate supplied recovery evidence; never clear an incident itself.

    For calibrated crop-band checks, caller provides `recovery_samples` and a
    policy-defined `recovery_samples_required`; all samples must be fresh and
    inside the same envelope version. For context cases, required proof is
    domain-specific and any absent item produces UNKNOWN.
    """
    code = str(scenario_code or "").upper()
    if code not in CROP_SCENARIOS:
        return {"status": "unknown", "recovered": False, "reason": "Unknown crop scenario."}
    context = context if isinstance(context, Mapping) else {}
    evidence: list[str] = []
    reason = ""
    samples = recovery_payload.get("recovery_samples") if isinstance(recovery_payload, Mapping) else None
    if code in {"C1", "C2", "C3", "C5"}:
        metric = {"C1": "sh", "C2": "vpd_kpa", "C3": "at", "C5": "sh"}[code]
        band_key = {"C1": "sh", "C2": "vpd_kpa", "C3": "air_temperature_day", "C5": "sh"}[code]
        low, high, version = _band(context, band_key)
        required = context.get("recovery_samples_required")
        try:
            required = int(required)
        except (TypeError, ValueError):
            required = None
        if low is None or high is None or required is None or required < 1 or not isinstance(samples, Sequence) or isinstance(samples, (str, bytes)):
            return {"status": "unknown", "recovered": False, "reason": "Calibrated envelope, sample window, or explicit recovery sample count is missing.", "evidence": evidence}
        if len(samples) < required:
            return {"status": "recovering", "recovered": False, "reason": "Not enough post-action samples to verify recovery.", "evidence": ["sample_count"]}
        chosen = list(samples)[-required:]
        values: list[float] = []
        for sample in chosen:
            if not isinstance(sample, Mapping):
                return {"status": "unknown", "recovered": False, "reason": "Malformed recovery sample.", "evidence": evidence}
            if sample.get("envelope_version") != version:
                return {"status": "unknown", "recovered": False, "reason": "Recovery evidence uses a different or missing envelope version.", "evidence": ["envelope_version"]}
            if metric == "vpd_kpa":
                value = vpd_kpa(sample.get("at"), sample.get("ah"))
            else:
                value = _num(sample.get(metric))
            if value is None:
                return {"status": "unknown", "recovered": False, "reason": "Recovery sample lacks valid sensor input.", "evidence": evidence}
            values.append(value)
        inside = all(low <= value <= high for value in values)
        if inside:
            evidence.extend(["fresh_samples", "same_envelope_version", "values_inside_approved_band"])
            return {"status": "recovered", "recovered": True, "reason": "Configured count of fresh samples is inside the approved envelope.", "evidence": evidence, "envelope_version": version}
        return {"status": "recovering", "recovered": False, "reason": "One or more recovery samples remain outside the approved envelope.", "evidence": ["out_of_band_sample"], "envelope_version": version}

    # Context-only scenarios require explicit evidence instead of assumed
    # sensor recovery. Field-inspection-dependent cases cannot be auto-cleared.
    requirements = {
        "C4": ("drainage_policy_satisfied", "soil_trend_recovered", "operator_inspection_confirmed"),
        "C6": ("ec_policy_satisfied", "valid_sample_count"),
        "C7": ("authorized_pollination_event_or_window_correction",),
        "C8": ("climate_condition_stable", "operator_crop_inspection_confirmed"),
        "C9": ("rainfall_and_soil_rechecked", "schedule_change_audited"),
        "C10": ("hydraulic_values_stable", "field_cause_inspection_confirmed"),
    }.get(code, ())
    missing = [key for key in requirements if not recovery_payload.get(key)]
    if missing:
        return {"status": "unknown", "recovered": False, "reason": "Required recovery evidence is absent; do not clear automatically.", "missing_evidence": missing}
    return {"status": "recovered_pending_review", "recovered": False,
            "reason": "Evidence checklist is complete; caller must record authorized review before incident closure.",
            "evidence": list(requirements)}

