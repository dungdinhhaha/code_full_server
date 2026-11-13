"""Pure candidate detectors for the SMIOT operations center.

Candidate evaluators do not open incidents or emit telemetry. The explicit
scenario persistence helper stores only findings corroborated by a matching
MongoDB scenario run; callers provide versioned target bands where available.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Mapping, Sequence


def _emit_finding_telemetry(*, findings_dispatched: int = 0, cycle_succeeded: bool = False) -> None:
    """Emit bounded dispatcher/heartbeat signals without finding identifiers."""
    try:
        from service.datadog_metrics import emit_count

        if findings_dispatched:
            emit_count("smiot.findings.dispatched", value=findings_dispatched)
        if cycle_succeeded:
            # This path runs only after a run-scoped scenario evaluation; keep
            # it separate from the per-sample advisory heartbeat emitted by
            # the MQTT ingestion pipeline.
            emit_count("smiot.detector.scenario_evaluation.completed")
    except Exception:
        # Metrics must never interrupt detection or persistence.
        return


_READING_NAMES = {
    "at": "air_temperature",
    "ah": "air_humidity",
    "st": "soil_temperature",
    "sh": "soil_humidity",
    "sec": "soil_ec",
}
_ALIASES = {
    "at": ("at", "air_temp", "air_temperature"),
    "ah": ("ah", "air_hum", "air_humidity"),
    "st": ("st", "soil_temp", "soil_temperature"),
    "sh": ("sh", "soil_hum", "soil_humidity"),
    "sec": ("sec", "ec", "soil_ec"),
}


def _utc_iso(value: Any = None) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            parsed = datetime.now(timezone.utc)
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _metric_value(readings: Mapping[str, Any], key: str) -> float | None:
    for alias in _ALIASES.get(key, (key,)):
        value = _number(readings.get(alias))
        if value is not None:
            return value
    return None


def _bounds(envelope: Any, metric: str) -> tuple[float | None, float | None, str | None]:
    """Accept {bands:{metric:{min,max}}} or a direct metric-to-band mapping."""
    if not isinstance(envelope, Mapping):
        return None, None, None
    bands = envelope.get("bands", envelope)
    if not isinstance(bands, Mapping):
        return None, None, None
    raw = None
    for alias in _ALIASES.get(metric, (metric,)):
        if alias in bands:
            raw = bands[alias]
            break
    low = high = None
    if isinstance(raw, Mapping):
        low = _number(raw.get("min", raw.get("low")))
        high = _number(raw.get("max", raw.get("high")))
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)) and len(raw) >= 2:
        low, high = _number(raw[0]), _number(raw[1])
    version = envelope.get("version")
    return low, high, str(version)[:100] if version is not None else None


def _stable_key(*parts: Any) -> str:
    encoded = "|".join("" if value is None else str(value) for value in parts).encode("utf-8")
    return hashlib.blake2s(encoded, digest_size=12).hexdigest()


def _candidate(*, farm_key: str, node_id: int | None, lot_id: Any, group: str,
               code: str, severity: str, confidence: float, evidence: dict[str, Any],
               detected_at: Any, scenario_run_id: Any = None,
               envelope_version: Any = None) -> dict[str, Any]:
    return {
        "finding_key": _stable_key(farm_key, node_id, group, code, evidence.get("metric"), scenario_run_id),
        "farm_key": farm_key,
        **({"lot_id": str(lot_id)[:100]} if lot_id is not None else {}),
        **({"node_id": node_id} if node_id is not None else {}),
        "group": group,
        "code": code,
        "severity": severity,
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "evidence": evidence,
        **({"envelope_version": str(envelope_version)[:100]} if envelope_version is not None else {}),
        "detected_at": _utc_iso(detected_at),
        **({"scenario_run_id": str(scenario_run_id)[:100]} if scenario_run_id is not None else {}),
        "status": "candidate",
    }


def _node_envelope(envelopes: Mapping[str, Any] | None, node_id: int) -> Mapping[str, Any] | None:
    if not isinstance(envelopes, Mapping):
        return None
    by_node = envelopes.get(node_id, envelopes.get(str(node_id)))
    return by_node if isinstance(by_node, Mapping) else envelopes


def _history_values(history: Mapping[str, Any] | None, node_id: int, metric: str) -> list[float]:
    if not isinstance(history, Mapping):
        return []
    by_node = history.get(node_id, history.get(str(node_id), history))
    if not isinstance(by_node, Mapping):
        return []
    raw = None
    for alias in _ALIASES.get(metric, (metric,)):
        if alias in by_node:
            raw = by_node[alias]
            break
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [number for item in raw if (number := _number(item)) is not None]


def evaluate_findings(
    payload: Mapping[str, Any],
    *,
    envelopes: Mapping[str, Any] | None = None,
    history: Mapping[str, Any] | None = None,
    provenance: Mapping[Any, Mapping[str, Any]] | None = None,
    detected_at: Any = None,
    min_history: int = 8,
    robust_z_limit: float = 6.5,
    flatline_epsilon_by_metric: Mapping[str, Any] | None = None,
    flatline_min_samples: int = 8,
) -> list[dict[str, Any]]:
    """Return evidence-backed sensor finding candidates; never persist or page.

    `envelopes` must come from a versioned crop-stage source. No limits are
    fabricated when absent. `history` maps node id -> metric -> prior values,
    ordered oldest to newest; robust spikes are skipped without enough history
    or when historical MAD is zero. Flatline checks require an explicit epsilon
    per metric. `provenance` may contain per-node metadata
    produced by `metadata_for_payload`; this avoids advancing its sequence
    tracker twice for one MQTT message.
    """
    farm = str(payload.get("farm_key") or "unknown")[:100]
    lot_id = payload.get("lot_id")  # only an explicit assignment is accepted
    scenario_run_id = payload.get("scenario_run_id")
    stamp = detected_at or payload.get("timestamp")
    nodes = payload.get("id6") or {}
    if not isinstance(nodes, Mapping):
        return []

    findings: list[dict[str, Any]] = []
    for node_key, raw_node in nodes.items():
        if not isinstance(raw_node, Mapping):
            continue
        try:
            node_id = int(str(node_key).lower().replace("node", ""))
        except (TypeError, ValueError):
            continue
        readings = raw_node
        meta = (provenance or {}).get(node_id, (provenance or {}).get(str(node_id), {}))
        if not isinstance(meta, Mapping):
            meta = {}
        node_stamp = raw_node.get("measured_at") or raw_node.get("timestamp") or stamp
        envelope = _node_envelope(envelopes, node_id)
        envelope_version = envelope.get("version") if isinstance(envelope, Mapping) else None

        # Transport provenance findings are emitted only from observed tracker flags.
        transport_codes = (
            ("reboot_detected", "device_reboot", "warning", 0.96),
            ("sequence_gap", "sample_sequence_gap", "warning", 0.91),
            ("sequence_duplicate", "duplicate_sample", "warning", 0.9),
            ("sequence_regression", "sample_sequence_regression", "error", 0.96),
        )
        for flag, code, severity, confidence in transport_codes:
            if meta.get(flag) or readings.get(flag):
                ev = {"boot_id": readings.get("boot_id", meta.get("boot_id")),
                      "sample_sequence": readings.get("sample_sequence", meta.get("sequence")),
                      "source": payload.get("source", meta.get("source"))}
                if flag == "sequence_gap":
                    ev["missing_count"] = meta.get(flag, readings.get(flag))
                if flag == "reboot_detected":
                    ev["previous_boot_id"] = meta.get("previous_boot_id")
                findings.append(_candidate(
                    farm_key=farm, node_id=node_id, lot_id=lot_id, group="telemetry_integrity",
                    code=code, severity=severity, confidence=confidence, evidence=ev,
                    detected_at=node_stamp, scenario_run_id=scenario_run_id,
                ))

        # Stage-specific out-of-band checks: skip entirely without a supplied envelope.
        for short_name, metric in _READING_NAMES.items():
            value = _metric_value(readings, short_name)
            if value is None:
                continue
            # Relative humidity/soil-moisture percentages have a physical range
            # independent of cultivar or agronomic calibration. This check is
            # intentionally limited to those percentage channels.
            if short_name in {"ah", "sh"} and not 0.0 <= value <= 100.0:
                findings.append(_candidate(
                    farm_key=farm, node_id=node_id, lot_id=lot_id, group="sensor_integrity",
                    code="measurement_out_of_physical_range", severity="critical", confidence=0.99,
                    evidence={"metric": metric, "value": value, "unit": _unit(short_name),
                              "physical_min": 0.0, "physical_max": 100.0,
                              "source": payload.get("source")},
                    detected_at=node_stamp, scenario_run_id=scenario_run_id,
                ))
            low, high, version = _bounds(envelope, short_name)
            if (low is None and high is None) or (low is not None and high is not None and low > high):
                continue
            below = low is not None and value < low
            above = high is not None and value > high
            if below or above:
                distance = (low - value) if below else (value - high)
                span = (high - low) if low is not None and high is not None else max(abs(value), 1.0)
                fraction = distance / max(abs(span), 1e-9)
                findings.append(_candidate(
                    farm_key=farm, node_id=node_id, lot_id=lot_id, group="crop_environment",
                    code="measurement_out_of_stage_band", severity="critical" if fraction >= 0.5 else "warning",
                    confidence=min(0.99, 0.82 + fraction * 0.1),
                    evidence={"metric": metric, "value": value, "unit": _unit(short_name),
                              "bound": low if below else high, "side": "below" if below else "above",
                              "crop": envelope.get("crop") if isinstance(envelope, Mapping) else None,
                              "stage": envelope.get("stage") if isinstance(envelope, Mapping) else None,
                              "source": payload.get("source")},
                    detected_at=node_stamp, scenario_run_id=scenario_run_id,
                    envelope_version=version,
                ))

            # Robust short-term spike check uses only caller-supplied persisted history.
            values = _history_values(history, node_id, short_name)
            flatline_epsilon = _configured_metric_value(flatline_epsilon_by_metric, short_name)
            flatline_count = max(2, int(flatline_min_samples))
            if flatline_epsilon is not None and len(values) >= flatline_count - 1:
                recent = (values + [value])[-flatline_count:]
                recent_range = max(recent) - min(recent)
                if recent_range <= flatline_epsilon:
                    findings.append(_candidate(
                        farm_key=farm, node_id=node_id, lot_id=lot_id, group="sensor_anomaly",
                        code="measurement_flatline", severity="warning", confidence=0.94,
                        evidence={"metric": metric, "value": recent[-1], "unit": _unit(short_name),
                                  "sample_count": len(recent), "range": recent_range,
                                  "epsilon": flatline_epsilon, "source": payload.get("source")},
                        detected_at=node_stamp, scenario_run_id=scenario_run_id,
                        envelope_version=envelope_version,
                    ))
            if len(values) < max(4, int(min_history)):
                continue
            center = median(values)
            deviations = [abs(sample - center) for sample in values]
            mad = median(deviations)
            if mad <= 0:
                continue
            robust_z = 0.6745 * (value - center) / mad
            if abs(robust_z) > max(1.0, float(robust_z_limit)):
                findings.append(_candidate(
                    farm_key=farm, node_id=node_id, lot_id=lot_id, group="sensor_anomaly",
                    code="measurement_spike", severity="warning", confidence=min(0.99, 0.75 + abs(robust_z) / 100),
                    evidence={"metric": metric, "value": value, "unit": _unit(short_name),
                              "baseline_median": center, "baseline_mad": mad,
                              "robust_z": round(robust_z, 2), "history_count": len(values),
                              "source": payload.get("source")},
                    detected_at=node_stamp, scenario_run_id=scenario_run_id,
                    envelope_version=envelope_version,
                ))
    return findings


def evaluate_and_persist_scenario_findings(payload: Mapping[str, Any], *, db=None,
                                           history_window_minutes: int = 30,
                                           history_limit: int = 32) -> list[dict[str, Any]]:
    """Evaluate soil spike/range findings against recent normal samples and exact run evidence.

    Only findings with a scenario_run_id acknowledged for the same farm/node and a
    detection timestamp inside that run are persisted. A finding may remain
    unlinked to an incident if the run has no verified incident mapping.
    """
    if not isinstance(payload, Mapping):
        return []
    from service.mongodb_store import database as get_database
    from service.telemetry_provenance import parse_datetime
    db = db or get_database()
    farm = str(payload.get("farm_key") or "")
    nodes = payload.get("id6") or {}
    if not farm or not isinstance(nodes, Mapping):
        return []
    persisted: list[dict[str, Any]] = []
    for node_key, raw_node in nodes.items():
        if not isinstance(raw_node, Mapping):
            continue
        run_id = str(raw_node.get("scenario_run_id") or "").strip()
        if not run_id:
            continue
        try:
            node_id = int(str(node_key).lower().replace("node", ""))
        except (TypeError, ValueError):
            continue
        stamp = parse_datetime(raw_node.get("measured_at") or raw_node.get("timestamp") or payload.get("timestamp"))
        if stamp is None:
            continue
        start = stamp - timedelta(minutes=max(1, int(history_window_minutes)))
        query = {
            "meta.farm_key": farm,
            "meta.measurement_type": "node",
            "meta.node_id": node_id,
            "timestamp": {"$gte": start, "$lt": stamp},
            "readings.soil_hum": {"$type": "number"},
            "source.scenario_run_id": {"$exists": False},
            "source.demo_seed_version": {"$exists": False},
        }
        history_rows = list(db["telemetry"].find(query, {"_id": 0, "readings.soil_hum": 1})
                            .sort("timestamp", -1).limit(max(8, min(int(history_limit), 128))))
        history_values = [
            float(row["readings"]["soil_hum"])
            for row in reversed(history_rows)
            if isinstance((row.get("readings") or {}).get("soil_hum"), (int, float))
        ]
        run = db["scenario_runs"].find_one(
            {"_id": run_id, "farm_key": farm},
            {"started_at": 1, "ended_at": 1, "incident_id": 1, "scenario_type": 1, "node_id": 1},
        )
        if not run:
            continue
        run_node = run.get("node_id")
        if run_node is not None and int(run_node) != node_id:
            continue
        started_at = _parse_time(run.get("started_at"))
        ended_at = _parse_time(run.get("ended_at"))
        if started_at is None or stamp < started_at or (ended_at is not None and stamp > ended_at):
            continue
        scoped_payload = {**payload, "scenario_run_id": run_id, "id6": {node_key: dict(raw_node)}}
        candidates = evaluate_findings(
            scoped_payload, history={node_id: {"sh": history_values}}, detected_at=stamp,
            min_history=8, robust_z_limit=4.0,
        )
        for finding in candidates:
            if finding.get("code") not in {"measurement_spike", "measurement_out_of_physical_range"}:
                continue
            finding_id = str(finding["finding_key"])
            doc = {
                "_id": finding_id,
                **finding,
                "scenario_type": run.get("scenario_type"),
                "incident_id": run.get("incident_id"),
                "status": "open",
                "synthetic": True,
                "created_at": stamp,
                "evidence_source": "persisted_recent_normal_telemetry",
            }
            result = db["findings"].update_one(
                {"_id": finding_id}, {"$setOnInsert": doc}, upsert=True
            )
            if result.upserted_id is not None:
                persisted.append(doc)
    # Reaching here means every eligible node completed its real evaluation and
    # persistence path, including a successful cycle with no new findings.
    _emit_finding_telemetry(findings_dispatched=len(persisted), cycle_succeeded=True)
    return persisted


def evaluate_freshness(
    *, farm_key: str, node_id: int, latest_sample: Mapping[str, Any] | None,
    now: Any = None, stale_after_s: float,
) -> list[dict[str, Any]]:
    """Evaluate freshness from the actual latest persisted Mongo sample.

    The caller supplies a row returned by its Mongo latest-sample query and an
    explicit freshness SLA. Missing or malformed rows are not labeled stale.
    """
    if not isinstance(latest_sample, Mapping):
        return []
    persisted_meta = latest_sample.get("source")
    if not isinstance(persisted_meta, Mapping):
        persisted_meta = {}
    sample_at = _parse_time(
        latest_sample.get("app_received_at")
        or persisted_meta.get("app_received_at")
        or latest_sample.get("timestamp")
    )
    current = _parse_time(now) or datetime.now(timezone.utc)
    if sample_at is None:
        return []
    age_s = max(0.0, (current - sample_at).total_seconds())
    if age_s <= max(0.0, float(stale_after_s)):
        return []
    return [_candidate(
        farm_key=str(farm_key)[:100], node_id=_int_or_none(node_id),
        lot_id=latest_sample.get("lot_id"), group="telemetry_freshness",
        code="persisted_sample_stale", severity="error", confidence=0.98,
        evidence={"sample_at": _utc_iso(sample_at), "age_seconds": round(age_s, 2),
                  "stale_after_seconds": float(stale_after_s),
                  "sample_sequence": persisted_meta.get("sequence", latest_sample.get("sample_sequence")),
                  "boot_id": persisted_meta.get("boot_id", latest_sample.get("boot_id")),
                  "source": persisted_meta.get("source", latest_sample.get("source_name"))},
        detected_at=current, scenario_run_id=latest_sample.get("scenario_run_id"),
    )]


def _configured_metric_value(config: Mapping[str, Any] | None, metric: str) -> float | None:
    if not isinstance(config, Mapping):
        return None
    for alias in _ALIASES.get(metric, (metric,)):
        if alias in config:
            value = _number(config.get(alias))
            return max(0.0, value) if value is not None else None
    return None


def _unit(short_name: str) -> str:
    return {"at": "°C", "ah": "%", "st": "°C", "sh": "%", "sec": "mS/cm"}.get(short_name, "")


def evaluate_irrigation_feedback(
    command: Mapping[str, Any] | None,
    ack: Mapping[str, Any] | None,
    *,
    feedback: Mapping[str, Any] | None = None,
    flow_lpm: Any = None,
    pressure_bar: Any = None,
    now: Any = None,
    ack_timeout_s: float | None = None,
    slow_ack_limit_ms: float | None = None,
    no_flow_grace_s: float | None = None,
) -> list[dict[str, Any]]:
    """Find action feedback issues only for a correlated command/ACK/evidence set.

    Deadlines and grace periods are supplied by the caller. No finding is
    produced from a telemetry value alone or from a mismatched command id.
    """
    if not isinstance(command, Mapping) or not command.get("command_id"):
        return []
    command_id = str(command["command_id"])
    farm = str(command.get("farm_key") or "unknown")[:100]
    node_id = _int_or_none(command.get("node_id"))
    lot_id = command.get("lot_id")
    scenario_id = command.get("scenario_run_id")
    requested_at = _parse_time(command.get("requested_at") or command.get("timestamp"))
    current = _parse_time(now) or datetime.now(timezone.utc)
    findings: list[dict[str, Any]] = []

    if ack is None:
        if ack_timeout_s is None or requested_at is None:
            return []
        elapsed = (current - requested_at).total_seconds()
        if elapsed >= max(0.0, float(ack_timeout_s)):
            findings.append(_candidate(
                farm_key=farm, node_id=node_id, lot_id=lot_id, group="irrigation_control",
                code="command_ack_timeout", severity="error", confidence=0.96,
                evidence={"command_id": command_id, "requested_at": _utc_iso(requested_at),
                          "elapsed_seconds": round(elapsed, 2), "timeout_seconds": float(ack_timeout_s)},
                detected_at=current, scenario_run_id=scenario_id,
            ))
        return findings

    if str(ack.get("command_id") or "") != command_id:
        return []
    ack_at = _parse_time(ack.get("timestamp") or ack.get("acknowledged_at"))
    status = str(ack.get("status") or ack.get("result") or "acknowledged").lower()
    if requested_at and ack_at and slow_ack_limit_ms is not None:
        latency_ms = (ack_at - requested_at).total_seconds() * 1000
        if latency_ms > max(0.0, float(slow_ack_limit_ms)):
            findings.append(_candidate(
                farm_key=farm, node_id=node_id, lot_id=lot_id, group="irrigation_control",
                code="command_ack_slow", severity="warning", confidence=0.9,
                evidence={"command_id": command_id, "requested_at": _utc_iso(requested_at),
                          "acknowledged_at": _utc_iso(ack_at), "latency_ms": round(latency_ms, 1),
                          "limit_ms": float(slow_ack_limit_ms), "ack_status": status},
                detected_at=ack_at, scenario_run_id=scenario_id,
            ))

    if no_flow_grace_s is None or status in {"failed", "rejected", "error"}:
        return findings
    output_on = any(_number(value) == 1 for key, value in command.items()
                    if str(key).startswith(("bit", "q"))) or str(command.get("action", "")).upper() in {"ON", "START", "PUMP_ON"}
    if not output_on or ack_at is None:
        return findings
    # A zero reading counts only if its evidence envelope is correlated to this
    # command and was measured after its acknowledgement.
    if not isinstance(feedback, Mapping) or str(feedback.get("command_id") or "") != command_id:
        return findings
    feedback_at = _parse_time(feedback.get("timestamp") or feedback.get("measured_at"))
    if feedback_at is None or feedback_at < ack_at:
        return findings
    flow = _number(feedback.get("flow_lpm", flow_lpm))
    pressure = _number(feedback.get("pressure_bar", pressure_bar))
    evidence_at = feedback_at
    elapsed_after_ack = (evidence_at - ack_at).total_seconds()
    if elapsed_after_ack < max(0.0, float(no_flow_grace_s)) or (flow is None and pressure is None):
        return findings
    if (flow is not None and flow <= 0) or (pressure is not None and pressure <= 0):
        findings.append(_candidate(
            farm_key=farm, node_id=node_id, lot_id=lot_id, group="irrigation_control",
            code="pump_on_without_water_feedback", severity="critical", confidence=0.95,
            evidence={"command_id": command_id, "acknowledged_at": _utc_iso(ack_at),
                      "ack_status": status, "elapsed_after_ack_s": round(elapsed_after_ack, 2),
                      "flow_lpm": flow, "pressure_bar": pressure,
                      "grace_seconds": float(no_flow_grace_s)},
            detected_at=evidence_at, scenario_run_id=scenario_id,
        ))
    return findings


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
