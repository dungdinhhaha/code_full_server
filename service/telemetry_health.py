"""Independent MongoDB-backed telemetry freshness watchdog for Datadog.

Single source of truth for node status: compute_node_status(), based on the
newest sample actually received (persisted) in MongoDB. UI, AI tools and MQTT
callbacks must use it instead of private thresholds.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from service.datadog_metrics import emit_health_gauge, metric_tags
from service.telemetry_provenance import parse_datetime

LOGGER = logging.getLogger("smiot.telemetry_health")
from service.farm_registry import FARM_KEYS as FARMS
NODE_STATUSES = ("ONLINE", "STALE", "OFFLINE", "UNKNOWN")
_thread: threading.Thread | None = None
_lock = threading.Lock()
_last_state: dict[tuple[str, int], str] = {}
_last_flatline_state: dict[tuple[str, int, str], bool] = {}
_last_domain: dict[tuple[str, int], str | None] = {}
_last_mismatch: dict[tuple[str, int], bool] = {}
_open_false_offline: dict[tuple[str, int], str] = {}
_false_offline_reconciled: set[tuple[str, int]] = set()
_broker_last_msg: dict[tuple[str, int], float] = {}
_FLATLINE_SAMPLE_COUNT = 10
_FLATLINE_EPSILON = 0.01
_FLATLINE_LOOKBACK_SECONDS = 600
_SYNC_LOCK = threading.Lock()
_FALSE_OFFLINE_LOCK = threading.Lock()
_last_sync_monotonic = 0.0
# Datadog monitor/workflow linked to the false_offline (Ca 1, node 1) investigation.
# Current Datadog US1 resources verified from live workflow/monitor exports on
# 2026-11-10. These IDs identify the current W4 refusal workflow, not the old
# organization snapshot.
FALSE_OFFLINE_MONITOR_ID = "342585836"
FALSE_OFFLINE_WORKFLOW_ID = "ffd62026-6b63-40e4-9b46-6ac18d2d584f"


def _setting(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _log_json(level: int, payload: dict[str, Any]) -> None:
    LOGGER.log(level, json.dumps(payload, separators=(",", ":"), default=str))


# --------------------------------------------------------------------------
# Pure logic (no Mongo / MQTT) - unit tested in tests/test_node_status.py
# --------------------------------------------------------------------------

def compute_node_status(received_at: Any, now: Any = None, *, last_sequence: Any = None,
                        boot_id: Any = None, stale_after_s: float | None = None,
                        offline_after_s: float | None = None) -> dict[str, Any]:
    """Status from the newest sample actually received (app_received_at/timestamp).

    ONLINE  : age <= stale_after_s (env SMIOT_TELEMETRY_STALE_SECONDS, default 90)
    STALE   : stale < age <= offline_after_s (env SMIOT_NODE_OFFLINE_SECONDS, default 300)
    OFFLINE : age > offline_after_s
    UNKNOWN : no sample received yet (never assume ONLINE).
    """
    now_dt = parse_datetime(now) if now is not None else datetime.now(timezone.utc)
    stale = float(stale_after_s) if stale_after_s is not None else float(_setting("SMIOT_TELEMETRY_STALE_SECONDS", 90))
    offline = float(offline_after_s) if offline_after_s is not None else float(_setting("SMIOT_NODE_OFFLINE_SECONDS", 300))
    offline = max(offline, stale)
    base = {"last_sequence": last_sequence, "boot_id": boot_id}
    stamp = parse_datetime(received_at)
    if stamp is None or now_dt is None:
        return {"status": "UNKNOWN", "reason": "no_sample_received", "age_s": None, **base}
    raw_age = (now_dt - stamp).total_seconds()
    age = round(max(0.0, raw_age), 1)
    if age <= stale:
        reason = "fresh_sample" if raw_age >= -5 else "fresh_sample_clock_skew"
        return {"status": "ONLINE", "reason": reason, "age_s": age, **base}
    if age <= offline:
        return {"status": "STALE", "reason": f"newest_sample_older_than_{int(stale)}s", "age_s": age, **base}
    return {"status": "OFFLINE", "reason": f"newest_sample_older_than_{int(offline)}s", "age_s": age, **base}


def classify_failure_domain(*, mongo_ok: bool | None, mqtt_connected: bool | None, sample_status: str,
                            broker_msg_age_s: float | None = None,
                            stale_after_s: float | None = None) -> dict[str, str] | None:
    """Classify only observed failures; ambiguous/missing evidence is unverified.

    A simultaneous MongoDB and MQTT failure is reported as a common dependency
    failure, never arbitrarily attributed to MongoDB first. A healthy dependency
    pair with stale/unknown samples does not prove a producer fault.
    """
    if mongo_ok is None or mqtt_connected is None:
        return {"domain": "unverified", "reason": "dependency_probe_missing"}
    if not mongo_ok and not mqtt_connected:
        return {"domain": "common_dependency_failure", "reason": "mongodb_and_mqtt_unavailable"}
    if not mongo_ok:
        return {"domain": "mongo", "reason": "mongo_ping_failed"}
    if not mqtt_connected:
        return {"domain": "broker", "reason": "smiot.dependency.mqtt.up=0"}
    if sample_status == "ONLINE":
        return None
    if sample_status not in {"STALE", "OFFLINE"}:
        return {"domain": "unverified", "reason": "sample_status_unknown"}
    stale = float(stale_after_s) if stale_after_s is not None else float(_setting("SMIOT_TELEMETRY_STALE_SECONDS", 90))
    if broker_msg_age_s is not None and 0 <= broker_msg_age_s <= stale:
        return {"domain": "app_ingest", "reason": "broker_messages_received_but_no_new_mongo_sample"}
    if broker_msg_age_s is None:
        return {"domain": "producer", "reason": "no_broker_message_since_offline"}
    return {"domain": "unverified", "reason": "stale_sample_without_recent_broker_evidence"}


def reconcile_display_status(display: dict[str, Any], node_id: int, computed: dict[str, Any],
                             farm: str | None = None) -> dict[str, Any]:
    """Compare the display/cache layer with the Mongo-derived status and correct it.

    display["nodeN_status"] == "UNKNOWN"/missing makes no claim, so it is not a mismatch.
    Returns {mismatch, display, computed, reason, injected}; display is overwritten by computed.
    """
    key = f"node{node_id}_status"
    shown = display.get(key)
    truth = computed["status"]
    mismatch = shown not in (None, "UNKNOWN") and shown != truth and truth != "UNKNOWN"
    fault = display.get("fault_stale_cache")
    injected = None
    # A fault tagged for another farm must not affect this farm's node.
    fault_applies = (isinstance(fault, dict) and fault.get("node") == node_id
                     and (farm is None or fault.get("farm", farm) == farm))
    if fault_applies:
        injected = fault.get("label", "synthetic_injected_stale_cache")
    reason = None
    if mismatch:
        reason = f"display_status_{shown}_but_mongo_status_{truth}:{computed.get('reason')}"
        if injected:
            reason += f";{injected}"
    if fault_applies:
        try:
            held = time.time() < float(fault.get("expires_at", 0))
        except (TypeError, ValueError):
            held = False
        if held:
            # Bounded injected fault: keep the wrong display; mismatch stays True.
            return {"mismatch": mismatch, "display": shown, "computed": truth, "reason": reason, "injected": injected}
        display.pop("fault_stale_cache", None)
    if truth != "UNKNOWN":
        display[key] = truth
    return {"mismatch": mismatch, "display": shown, "computed": truth, "reason": reason, "injected": injected}


# --------------------------------------------------------------------------
# Mongo-backed helpers
# --------------------------------------------------------------------------

def note_broker_message(farm_key: str, node_id: int) -> None:
    """Called by the MQTT callback when a node sample arrives from the broker."""
    _broker_last_msg[(farm_key, int(node_id))] = time.time()


def broker_message_age(farm_key: str, node_id: int) -> float | None:
    stamp = _broker_last_msg.get((farm_key, int(node_id)))
    return None if stamp is None else max(0.0, time.time() - stamp)


_RECOVERY_VERIFY_INTERVAL_SECONDS = 60
_last_recovery_attempt: dict[tuple[str, int], float] = {}
_VERIFIER_PATH = Path(__file__).resolve().parent.parent / "scripts" / "verify_and_clear_demo_safe_mode.py"


def _valid_flatline_verifier_result(details: Any) -> bool:
    """Require explicit, correlated proof from the HOLD/CLEAR verifier output."""
    if not isinstance(details, dict) or details.get("result") not in {
        "verified_and_cleared", "already_verified_and_cleared"
    }:
        return False
    incident_id = str(details.get("incident_id") or "")
    command_id = str(details.get("command_id") or "")
    ack = details.get("clear_ack")
    if (not incident_id or not command_id
            or str(details.get("monitor_state", "")).upper() != "OK"
            or details.get("virtual_pump_outputs_off") is not True
            or details.get("simulated") is not True
            or not isinstance(ack, dict)
            or str(ack.get("command_id") or "") != command_id
            or ack.get("action") != "CLEAR" or ack.get("applied") is not True
            or ack.get("verified") is not True or ack.get("safe_mode_active") is not False
            or ack.get("synthetic") is not True
            or not isinstance(ack.get("timestamp"), str)):
        return False
    outputs = ack.get("virtual_output")
    if (not isinstance(outputs, dict) or set(outputs) != {f"bit{i}" for i in range(8)}
            or any(value not in (0, False, "0") for value in outputs.values())):
        return False
    try:
        sample_count = int(details.get("fresh_normal_samples", 0))
        required_samples = int(details.get("required_samples", 0))
        sample_span = float(details.get("sample_span_seconds", 0))
        stable_seconds = int(details.get("stable_seconds", 0))
        expected_interval = float(details.get("expected_interval_seconds", 60))
        low, high = (float(v) for v in details["soil_humidity_range_pct"])
        freshness = float(details["sample_freshness_seconds"])
    except (TypeError, ValueError, KeyError):
        return False
    # The CLEAR verifier derives its sample count from the configured publisher
    # cadence. Do not re-impose the flatline detector's ten-sample threshold on
    # recovery: at a 60s cadence, six samples already prove the required 300s
    # stable interval. The verifier is authoritative for that cadence proof.
    return (sample_count >= required_samples and required_samples >= 2
            and stable_seconds >= 60 and sample_span >= stable_seconds
            and expected_interval > 0
            and 0 <= freshness <= max(90, expected_interval * 1.5)
            and 0 <= low <= high <= 100 and high - low >= 0.5
            and bool(details.get("newest_sample_at")))


def _track_flatline_recovery(farm: str, node_id: int, source: str, values: list[float],
                             age_seconds: float) -> bool:
    """Khi watchdog thay mau moi on dinh, goi CUNG verifier ma endpoint recovery-clear dung.

    Verifier kiem: monitor Datadog OK, HOLD da ack, va du mau binh thuong theo cadence
    publisher trong it nhat 5 phut gan voi su co, roi moi gui CLEAR toi PLC ao.
    Chi khi verifier dat thi moi dong su co.
    Gioi han goi mot lan moi 60 s moi node de khong spam Datadog/Mongo khi chua dat dieu kien.
    """
    key = (farm, int(node_id))
    now_mono = time.monotonic()
    if now_mono - _last_recovery_attempt.get(key, -1e9) < _RECOVERY_VERIFY_INTERVAL_SECONDS:
        return False
    _last_recovery_attempt[key] = now_mono
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(_VERIFIER_PATH)],
            cwd=str(_VERIFIER_PATH.parent.parent), capture_output=True, text=True, timeout=55, check=False,
        )
    except subprocess.TimeoutExpired:
        LOGGER.error(json.dumps({"event": "smiot_flatline_recovery_timeout", "farm": farm, "node": node_id},
                                separators=(",", ":")))
        return False
    except Exception as exc:
        LOGGER.error(json.dumps({"event": "smiot_flatline_recovery_error", "farm": farm, "node": node_id,
                                 "error_type": type(exc).__name__}, separators=(",", ":")))
        return False
    out_lines = (result.stdout or "").strip().splitlines()
    if result.returncode != 0:
        reason = ((result.stderr or result.stdout or "").strip())[-300:]
        LOGGER.info(json.dumps({"event": "smiot_flatline_recovery_not_verified", "farm": farm, "node": node_id,
                                "reason": reason}, separators=(",", ":")))
        return False
    try:
        details = json.loads(out_lines[-1]) if out_lines else {}
    except json.JSONDecodeError:
        details = {}
    if not _valid_flatline_verifier_result(details):
        LOGGER.info(json.dumps({"event": "smiot_flatline_recovery_not_verified", "farm": farm,
                               "node": node_id, "reason": "verifier_output_missing_required_proof"},
                              separators=(",", ":")))
        return False
    try:
        from service import incident_lifecycle
        evidence = {
            "method": "verified_by_recovery_verifier",
            "rule": "matching_incident_monitor_ok_hold_ack_fresh_varying_samples_clear_ack_outputs_off",
            "incident_id": details["incident_id"],
            "clear_command_id": details["command_id"],
            "prior_hold_command_id": details.get("prior_hold_command_id"),
            "monitor_state": details["monitor_state"],
            "fresh_normal_samples": details.get("fresh_normal_samples"),
            "soil_humidity_range_pct": details.get("soil_humidity_range_pct"),
            "sample_freshness_seconds": details.get("sample_freshness_seconds"),
            "virtual_pump_outputs_off": details["virtual_pump_outputs_off"],
            "watchdog_sample_count": len(values),
            "watchdog_range_pct": [round(min(values), 3), round(max(values), 3)],
            "newest_sample_age_seconds": round(age_seconds, 1),
            "source": source,
            "verifier": details,
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        closed = incident_lifecycle.close_flatline_incident(
            farm, int(node_id), incident_id=str(details["incident_id"]), recovery_evidence=evidence)
    except ValueError:
        return False  # ngoai pham vi ca demo
    except Exception as exc:  # Mongo chua san sang: khong lam hong watchdog
        LOGGER.error(json.dumps({"event": "smiot_flatline_recovery_error", "farm": farm, "node": node_id,
                                 "error_type": type(exc).__name__}, separators=(",", ":")))
        return False
    if closed:
        LOGGER.info(json.dumps({"event": "smiot_flatline_incident_recovered", "farm": farm, "node": node_id,
                                "source": source}, separators=(",", ":")))
    return closed


def _track_flatline_incident(farm: str, node_id: int, flatline: bool, sample_count: int) -> str | None:
    """Mo su co flatline tu dong khi node 2 dung so do that (khong chi khi bam lenh dien tap).

    - Chi ap dung cho greenhouse_a/node 2 (pham vi cua incident flatline hien tai).
    - start_flatline_incident tai su dung su co dang mo, nen goi lai khong tao ban ghi trung.
    - Khi het dung so do, KHONG dong tu dong: viec dong van di qua luong CLEAR da kiem chung
      (xac minh mau moi + ACK) de khong bo qua buoc phuc hoi an toan.
    Tra ve incident_id neu da mo/tai su dung, None neu khong ap dung hoac loi.
    """
    if not flatline:
        return None
    try:
        from service import incident_lifecycle
        incident_id = incident_lifecycle.start_flatline_incident(farm, int(node_id))
    except ValueError:
        return None  # ngoai pham vi ca demo
    except Exception as exc:  # Mongo chua san sang: khong lam hong watchdog
        LOGGER.error(json.dumps({"event": "smiot_flatline_incident_error", "farm": farm, "node": node_id,
                                 "error_type": type(exc).__name__}, separators=(",", ":")))
        return None
    LOGGER.info(json.dumps({"event": "smiot_flatline_incident_tracked", "farm": farm, "node": node_id,
                            "incident_id": incident_id, "sample_count": sample_count},
                           separators=(",", ":")))
    return incident_id


def _latest_node_row(telemetry: Any, farm: str, node_id: int) -> dict[str, Any] | None:
    return telemetry.find_one(
        {"meta.farm_key": farm, "meta.measurement_type": "node", "meta.node_id": node_id,
         "source.demo_seed_version": {"$ne": "smiot-demo-history-v1"}},
        {"timestamp": 1, "source.source": 1, "source.simulator": 1, "source.synthetic": 1,
         "source.sequence": 1, "source.boot_id": 1, "source.app_received_at": 1},
        sort=[("timestamp", -1)],
        max_time_ms=2000,
    )


def _status_from_row(row: dict[str, Any] | None, now: datetime | None = None) -> dict[str, Any]:
    if not row:
        return compute_node_status(None, now)
    src = row.get("source") or {}
    stamp = src.get("app_received_at") or row.get("timestamp")
    return compute_node_status(stamp, now, last_sequence=src.get("sequence"), boot_id=src.get("boot_id"))


def get_node_status(farm_key: str, node_id: int, now: datetime | None = None) -> dict[str, Any]:
    """Authoritative node status from MongoDB; UNKNOWN (reason mongo_error) if Mongo is unreachable."""
    try:
        from service.mongodb_store import collection
        return _status_from_row(_latest_node_row(collection("telemetry"), farm_key, int(node_id)), now)
    except Exception as exc:
        return {"status": "UNKNOWN", "reason": f"mongo_error:{type(exc).__name__}", "age_s": None,
                "last_sequence": None, "boot_id": None}


def _source_label(row: dict[str, Any] | None) -> str:
    if not row:
        return "unknown"
    meta = row.get("source") or {}
    source = str(meta.get("source") or meta.get("simulator") or (
        "synthetic_unlabelled" if meta.get("synthetic") is True else "device_unclassified"))
    if source not in {"device", "wokwi_synthetic", "velxio_synthetic", "smiot_demo_stream", "synthetic_unlabelled", "device_unclassified"}:
        source = "other"
    return source


def _row_received_at(row: dict[str, Any] | None) -> Any:
    if not row:
        return None
    return (row.get("source") or {}).get("app_received_at") or row.get("timestamp")


def _track_false_offline(farm: str, node_id: int, result: dict[str, Any], computed: dict[str, Any],
                         received_at: Any, was_mismatch: bool) -> str | None:
    """Open false_offline on first False->True mismatch; close only with fresh Mongo evidence.

    Never raises. open_incident dedups active incidents, so flapping cannot spawn duplicates.
    """
    key = (farm, node_id)
    # Lock: called from both the watchdog thread and the UI worker thread; without it
    # two callers could both see "not open" and open a duplicate incident.
    with _FALSE_OFFLINE_LOCK:
        try:
            from service import incident_lifecycle
            if result["mismatch"]:
                if key not in _open_false_offline:  # retried next cycle if open failed
                    _open_false_offline[key] = incident_lifecycle.open_incident(
                        "false_offline", farm, node_id, synthetic=bool(result["injected"]),
                        opened_by="telemetry_health",
                        details={"display": result["display"], "computed": result["computed"],
                                 "reason": result["reason"]},
                        monitor_id=FALSE_OFFLINE_MONITOR_ID,
                        workflow_id=FALSE_OFFLINE_WORKFLOW_ID)
                _false_offline_reconciled.discard(key)
            elif computed.get("status") == "ONLINE":
                stamp = parse_datetime(received_at)
                incident_id = _open_false_offline.get(key)
                if not incident_id and key not in _false_offline_reconciled:
                    # The in-memory map is lost on an app restart. Reattach to an
                    # active Mongo incident once per healthy scope, then close it
                    # only from the current fresh Mongo sample and reconciled UI.
                    from service.mongodb_store import collection
                    active = collection("operational_incidents").find_one(
                        {"kind": "false_offline", "farm_key": farm, "node_id": int(node_id),
                         "status": {"$in": ["open", "holding", "recovering"]}},
                        {"_id": 1}, sort=[("opened_at", -1)])
                    incident_id = str(active["_id"]) if active else None
                    if incident_id:
                        _open_false_offline[key] = incident_id
                if incident_id:
                    evidence = {
                        "mongo_newest_received_at": stamp.isoformat() if stamp else None,
                        "age_s": computed.get("age_s"), "display_now": result["display"],
                        "computed_now": "ONLINE", "display_mismatch": False,
                        "last_sequence": computed.get("last_sequence"),
                        "boot_id": computed.get("boot_id"),
                    }
                    if incident_lifecycle.close_incident(incident_id, recovery_evidence=evidence):
                        _open_false_offline.pop(key, None)
                        _false_offline_reconciled.add(key)
                        _log_json(logging.INFO, {
                            "event": "smiot_false_offline_incident_recovered", "incident_id": incident_id,
                            "farm": farm, "node": int(node_id), "mongo_status": "ONLINE",
                            "age_s": computed.get("age_s"), "last_sequence": computed.get("last_sequence"),
                        })
                    else:
                        # Drop a stale in-memory reference only after confirming
                        # that the same incident is no longer active in MongoDB.
                        from service.mongodb_store import collection
                        still_active = collection("operational_incidents").find_one(
                            {"_id": incident_id,
                             "status": {"$in": ["open", "holding", "recovering"]}}, {"_id": 1})
                        if not still_active:
                            _open_false_offline.pop(key, None)
                            _false_offline_reconciled.add(key)
                else:
                    _false_offline_reconciled.add(key)
        except Exception:
            LOGGER.warning("false_offline incident tracking failed", exc_info=True)
        return _open_false_offline.get(key)


def _emit_mismatch(farm: str, node_id: int, source: str, result: dict[str, Any], computed: dict[str, Any],
                   received_at: Any = None) -> None:
    tags = metric_tags(farm, node_id, source)
    emit_health_gauge("smiot.telemetry.status_mismatch", int(result["mismatch"]), tags)
    key = (farm, node_id)
    incident_id = _track_false_offline(farm, node_id, result, computed, received_at,
                                       bool(_last_mismatch.get(key)))
    if result["mismatch"] or _last_mismatch.get(key):
        _log_json(logging.WARNING if result["mismatch"] else logging.INFO, {
            "event": "smiot_status_mismatch" if result["mismatch"] else "smiot_status_mismatch_cleared",
            "farm": farm, "node": node_id, "source": source,
            "display_status": result["display"], "mongo_status": result["computed"],
            "age_s": computed.get("age_s"), "last_sequence": computed.get("last_sequence"),
            "reason": result["reason"], "injected_fault": result["injected"], "incident_id": incident_id,
            "action": "display_overridden_by_mongo_status",
        })
    _last_mismatch[key] = result["mismatch"]


def _farm_key_from_label(label: str) -> str:
    return str(label).strip().lower().replace(" ", "_")


def refresh_selected_farm_status(home_state: dict[str, Any], min_interval_s: float | None = None) -> list[tuple[int, str, str]]:
    """Throttled sync of the home view status from Mongo. Returns [(node, old, new)] transitions."""
    global _last_sync_monotonic
    interval = float(min_interval_s if min_interval_s is not None else _setting("SMIOT_NODE_STATUS_SYNC_SECONDS", 5))
    with _SYNC_LOCK:
        if time.monotonic() - _last_sync_monotonic < interval:
            return []
        _last_sync_monotonic = time.monotonic()
    farm = _farm_key_from_label(home_state.get("selected_farm", "Greenhouse A"))
    transitions: list[tuple[int, str, str]] = []
    try:
        from service.mongodb_store import collection
        telemetry = collection("telemetry")
        now = datetime.now(timezone.utc)
        for node_id in (1, 2):
            row = _latest_node_row(telemetry, farm, node_id)
            computed = _status_from_row(row, now)
            old = str(home_state.get(f"node{node_id}_status", "UNKNOWN"))
            result = reconcile_display_status(home_state, node_id, computed, farm)
            _emit_mismatch(farm, node_id, _source_label(row), result, computed, _row_received_at(row))
            if row and isinstance(row.get("timestamp"), datetime):
                home_state[f"node{node_id}_last_mongo_received_at"] = row["timestamp"].isoformat()
            if computed["status"] != "UNKNOWN" and old != computed["status"]:
                transitions.append((node_id, old, computed["status"]))
    except Exception:
        LOGGER.debug("Could not synchronize node status from MongoDB", exc_info=True)
    return transitions


# --------------------------------------------------------------------------
# Watchdog
# --------------------------------------------------------------------------

def inspect_once() -> list[dict[str, Any]]:
    """Inspect newest sample per farm/node and emit low-cardinality health signals."""
    now = datetime.now(timezone.utc)
    stale_after = _setting("SMIOT_TELEMETRY_STALE_SECONDS", 90)
    base_tags = ["service:smiot-smart-farm", "env:demo"]
    outcomes: list[dict[str, Any]] = []
    from service.mongodb_store import collection, database
    mongo_ok = True
    try:
        database().command("ping")
        emit_health_gauge("smiot.dependency.mongo.up", 1, base_tags)
    except Exception as exc:
        mongo_ok = False
        emit_health_gauge("smiot.dependency.mongo.up", 0, base_tags)
        LOGGER.error(json.dumps({"event": "smiot_dependency_check", "dependency": "mongodb",
                                 "healthy": False, "error_type": type(exc).__name__}, separators=(",", ":")))
    try:
        from service import mqtt
        connected = bool(mqtt.mqtt_client and mqtt.mqtt_client.is_connected())
        emit_health_gauge("smiot.dependency.mqtt.up", int(connected), base_tags)
    except Exception:
        connected = False
        emit_health_gauge("smiot.dependency.mqtt.up", 0, base_tags)

    if not mongo_ok:
        if _last_domain.get(("*", 0)) != "mongo":
            _log_json(logging.ERROR, {"event": "smiot_failure_domain", "domain": "mongo",
                                      "reason": "mongo_ping_failed", "mqtt_up": connected,
                                      "action": "node_status_unknown_until_mongo_recovers"})
            _last_domain[("*", 0)] = "mongo"
        return outcomes
    _last_domain.pop(("*", 0), None)

    telemetry = collection("telemetry")
    try:
        from pages.home import state as home_state
    except Exception:
        home_state = None
    for farm in FARMS:
        for node_id in (1, 2):
            row = _latest_node_row(telemetry, farm, node_id)
            computed = _status_from_row(row, now)
            source = _source_label(row)
            if computed["age_s"] is None:
                age, current = float(stale_after * 10), "missing"
            else:
                age = computed["age_s"]
                current = "fresh" if computed["status"] == "ONLINE" else "stale"
            tags = metric_tags(farm, node_id, source)
            emit_health_gauge("smiot.telemetry.sample_age_seconds", age, tags)
            emit_health_gauge("smiot.telemetry.fresh", int(current == "fresh"), tags)
            # Display/cache layer must follow the newest MongoDB row for that exact
            # farm/node; a mismatch is reported (status_mismatch) and corrected.
            try:
                farm_label = farm.replace("_", " ").title()
                if home_state is not None and home_state.get("selected_farm", "Greenhouse A") == farm_label:
                    result = reconcile_display_status(home_state, node_id, computed, farm)
                    _emit_mismatch(farm, node_id, source, result, computed, _row_received_at(row))
                    if row and isinstance(row.get("timestamp"), datetime):
                        home_state[f"node{node_id}_last_mongo_received_at"] = row["timestamp"].isoformat()
            except Exception:
                LOGGER.debug("Could not synchronize node freshness to home view", exc_info=True)
            # Failure domain explanation (logged on transition only).
            domain = classify_failure_domain(
                mongo_ok=mongo_ok, mqtt_connected=connected, sample_status=computed["status"],
                broker_msg_age_s=broker_message_age(farm, node_id), stale_after_s=stale_after)
            domain_name = domain["domain"] if domain else None
            if domain_name != _last_domain.get((farm, node_id)):
                if domain or (farm, node_id) in _last_domain:
                    _log_json(logging.WARNING if domain else logging.INFO, {
                        "event": "smiot_failure_domain", "farm": farm, "node": node_id, "source": source,
                        "domain": domain_name or "recovered", "reason": (domain or {}).get("reason", "fresh_sample"),
                        "node_status": computed["status"], "age_s": computed["age_s"],
                        "last_sequence": computed["last_sequence"], "boot_id": computed["boot_id"],
                        "mongo_up": mongo_ok, "mqtt_up": connected,
                        "broker_msg_age_s": (None if broker_message_age(farm, node_id) is None
                                             else round(broker_message_age(farm, node_id), 1)),
                    })
                _last_domain[(farm, node_id)] = domain_name
            # Detect a stuck reading from the values actually persisted in Mongo,
            # rather than trusting the simulator's requested mode or a derived
            # Datadog diff() expression. Require ten fresh, consecutive samples
            # so ordinary short-lived stability does not page the operator.
            # The lookback must cover the cadence of all required samples;
            # freshness is independently gated by the newest sample above.
            cutoff = now - timedelta(seconds=max(
                _FLATLINE_LOOKBACK_SECONDS,
                _FLATLINE_SAMPLE_COUNT * _setting("SMIOT_SIM_NODE_INTERVAL_SECONDS", 60) * 2,
            ))
            recent = list(telemetry.find(
                {"meta.farm_key": farm, "meta.measurement_type": "node",
                 "meta.node_id": node_id, "timestamp": {"$gte": cutoff},
                 "readings.soil_hum": {"$type": "number"}},
                {"timestamp": 1, "readings.soil_hum": 1, "source.source": 1,
                 "source.simulator": 1, "source.synthetic": 1},
            ).sort("timestamp", -1).limit(_FLATLINE_SAMPLE_COUNT))
            values = [float((sample.get("readings") or {}).get("soil_hum")) for sample in recent]
            newest_source = (recent[0].get("source") or {}) if recent else {}
            flatline_source = str(newest_source.get("source") or newest_source.get("simulator") or source)
            fresh_sample_count = len(values)
            flatline = (
                current == "fresh"
                and fresh_sample_count == _FLATLINE_SAMPLE_COUNT
                and max(values) - min(values) <= _FLATLINE_EPSILON
            )
            flatline_tags = metric_tags(farm, node_id, flatline_source)
            emit_health_gauge("smiot.telemetry.sensor_flatline", int(flatline), flatline_tags)
            flatline_key = (farm, node_id, flatline_source)
            if flatline != _last_flatline_state.get(flatline_key):
                LOGGER.info(json.dumps({
                    "event": "smiot_sensor_flatline_transition",
                    "farm": farm,
                    "node": node_id,
                    "source": flatline_source,
                    "flatline": flatline,
                    "sample_count": fresh_sample_count,
                    "required_sample_count": _FLATLINE_SAMPLE_COUNT,
                    "soil_humidity_range_pct": (
                        [round(min(values), 3), round(max(values), 3)] if values else None
                    ),
                }, separators=(",", ":")))
                _last_flatline_state[flatline_key] = flatline
                _track_flatline_incident(farm, node_id, flatline, fresh_sample_count)
            if (not flatline and current == "fresh" and fresh_sample_count == _FLATLINE_SAMPLE_COUNT
                    and max(values) - min(values) > _FLATLINE_EPSILON):
                _track_flatline_recovery(farm, node_id, flatline_source, values, age)
            outcome = {"farm": farm, "node": node_id, "source": source, "age_seconds": round(age, 1),
                       "state": current, "node_status": computed["status"], "mqtt_connected": connected,
                       "soil_humidity_flatline": flatline,
                       "flatline_sample_count": fresh_sample_count}
            outcomes.append(outcome)
            key = (farm, node_id)
            if current != _last_state.get(key):
                LOGGER.info(json.dumps({"event": "smiot_telemetry_freshness_transition", **outcome,
                                        "stale_after_seconds": stale_after}, separators=(",", ":")))
                _last_state[key] = current
    return outcomes


def _run() -> None:
    interval = _setting("SMIOT_TELEMETRY_HEALTH_INTERVAL_SECONDS", 30)
    while True:
        try:
            inspect_once()
        except Exception as exc:
            LOGGER.exception("Telemetry freshness inspection failed: %s", type(exc).__name__)
        time.sleep(interval)


def start_telemetry_health_watchdog() -> None:
    global _thread
    with _lock:
        if _thread and _thread.is_alive():
            return
        _thread = threading.Thread(target=_run, name="smiot-telemetry-health", daemon=True)
        _thread.start()
