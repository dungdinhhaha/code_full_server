from service.observability import initialize_tracing

initialize_tracing()

from nicegui import ui, app
from pathlib import Path
import asyncio
import hashlib
import json
import os
import secrets
import subprocess
import sys
import threading
import time

# Serve thư mục static (chứa ảnh thiết bị)
app.add_static_files('/static', Path(__file__).parent / 'static')

# ── Khởi tạo Database Auth (tạo bảng users, permissions nếu chưa có) ──
from service.auth import init_db
init_db()

# Import các trang để router NiceGUI nhận diện
import pages.login
import pages.home
import pages.project
import pages.inverter
import pages.plc
import pages.devices
import pages.permission
import pages.schedule
import pages.chart
import pages.data_table
import pages.traceability
import pages.mongodb_lab
import pages.public_lot

# Trang incident dang do agent khac tao: thieu module thi chi canh bao, khong chan app.
try:
    import pages.incident  # noqa: F401
except ImportError as exc:
    from service.logger import get_logger as _get_early_logger
    _get_early_logger("SYSTEM").warning("Bo qua pages.incident (chua san sang): %s", exc)

# Server startup configs
from service.mqtt import start_mqtt, publish_mqtt
start_mqtt()

from service.scheduler import start_background_scheduler
start_background_scheduler()

# Demo data is isolated by stable demo identifiers and contains no pump commands.
from service.demo_mode import start_demo_mode
start_demo_mode()

# Poll Mongo independently from MQTT so a silent telemetry stream stays observable.
from service.telemetry_health import start_telemetry_health_watchdog
start_telemetry_health_watchdog()

# Publish detector liveness independently from MQTT callbacks/findings.
from service.detector_heartbeat import start_detector_heartbeat
start_detector_heartbeat()

# ── 1. Thêm Middleware Access Log ──
from service.middleware import AccessLogMiddleware
app.add_middleware(AccessLogMiddleware)

# ── 2. Cấu hình Global Exception Handler (Bắt mọi lỗi gửi qua Telegram) ──
import sys
import threading
import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from fastapi.responses import JSONResponse
from fastapi.responses import Response
from fastapi import Request
from service.logger import get_logger

system_logger = get_logger("SYSTEM")
_recovery_clear_lock = threading.Lock()
_w9_late_ack_lock = threading.Lock()

def notify_error_to_telegram(exc_type, exc_value, exc_traceback, source="System"):
    """Ghi lỗi ra error.log và gửi cảnh báo lên Telegram qua MQTT."""
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    tb_text = "".join(tb_lines)
    
    # 1. Ghi ra logs/error.log (nhờ system_logger gọi error_handler)
    system_logger.error(f"[{source}] Unhandled Exception:\n{tb_text}")
    
    # 2. Rút gọn Traceback để gửi Telegram không bị quá dài
    short_tb = tb_text[-600:].replace('<', '&lt;').replace('>', '&gt;')
    msg = f"<b>🚨 FATAL CRASH ({source})</b>\n<code>{exc_type.__name__}: {exc_value}</code>\n<pre>{short_tb}</pre>"
    
    now_str = datetime.now().strftime("%H:%M:%S")
    publish_mqtt("farm/notify", {
        "message": msg,
        "category": "system",
        "severity": "error",
        "time": now_str
    })

def global_sys_excepthook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    notify_error_to_telegram(exc_type, exc_value, exc_traceback, "MainThread")

def global_thread_excepthook(args):
    thread_name = args.thread.name if args.thread else "UnknownThread"
    notify_error_to_telegram(args.exc_type, args.exc_value, args.exc_traceback, thread_name)

# Gắn hook bắt lỗi cho luồng chính và luồng ngầm
sys.excepthook = global_sys_excepthook
threading.excepthook = global_thread_excepthook

# Bắt lỗi HTTP Requests của FastAPI
@app.exception_handler(Exception)
async def fastapi_exception_handler(request: Request, exc: Exception):
    notify_error_to_telegram(type(exc), exc, exc.__traceback__, f"Web (Path: {request.url.path})")
    return JSONResponse(
        status_code=500,
        content={"message": "Lỗi hệ thống nội bộ! Đã báo cáo cho Admin."}
    )
# Báo lỗi JS từ Client
@app.post('/api/js_error')
async def post_js_error(request: Request):
    try:
        data = await request.json()
        system_logger.error(f"[JS CLIENT ERROR] {data.get('message')} at {data.get('url')}:{data.get('line')}:{data.get('column')} - Stack: {data.get('stack')}")
        logs_dir = Path(__file__).parent / "logs"
        logs_dir.mkdir(exist_ok=True)
        with open(logs_dir / 'js_error.log', 'a', encoding='utf-8') as f:
            import json
            import time
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {json.dumps(data)}\n")
        return {"status": "ok"}
    except Exception as e:
        print(f"Error handling JS error log: {e}")
        return {"status": "error"}


# ── Health endpoint: không cần đăng nhập, không trả lỗi chi tiết, URI hay secret ──
from service.mongodb_store import collection, database

HEALTHZ_MONGO_TIMEOUT_SECONDS = 2.0


def build_healthz_payload(*, mongo_ok, mqtt_ok, newest_sample_at, now):
    """Dựng JSON /healthz từ kết quả kiểm tra. Hàm thuần: test được mà không cần Mongo."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age = None
    if isinstance(newest_sample_at, datetime):
        stamp = newest_sample_at
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        age = round(max(0.0, (now - stamp.astimezone(timezone.utc)).total_seconds()), 1)
    return {
        "app": "ok",
        "mongo": "ok" if mongo_ok else "fail",
        "mqtt": "ok" if mqtt_ok else "fail",
        "newest_sample_age_seconds": age,
        "time_utc": now.astimezone(timezone.utc).isoformat(),
    }


async def _read_mongo_health(timeout=HEALTHZ_MONGO_TIMEOUT_SECONDS):
    """Ping Mongo và đọc mẫu mới nhất trong thread, có timeout ngắn. Trả (ok, newest_timestamp)."""
    def _probe():
        database().command("ping")
        row = collection("telemetry").find_one({}, {"timestamp": 1, "_id": 0}, sort=[("timestamp", -1)])
        return row.get("timestamp") if row else None
    try:
        newest = await asyncio.wait_for(asyncio.to_thread(_probe), timeout=timeout)
        return True, newest
    except Exception:
        return False, None


def _mqtt_connected():
    try:
        from service import mqtt as mqtt_service
        return bool(mqtt_service.mqtt_client and mqtt_service.mqtt_client.is_connected())
    except Exception:
        return False


def _demo_control_authorized(request: Request) -> bool:
    """External demo-control API is opt-in and uses a separate bearer secret."""
    expected = os.getenv("SMIOT_DEMO_CONTROL_TOKEN", "").strip()
    supplied = request.headers.get("authorization", "")
    return bool(expected and supplied.lower().startswith("bearer ") and
                secrets.compare_digest(supplied[7:].strip(), expected))


def _demo_control_store():
    from service.mongodb_store import database
    return database()


def _take_demo_api_rate_limit(db, token_scope: str, route: str, limit: int, *, now=None):
    """Apply a Mongo-backed fixed-window limit shared by app workers.

    One document per token scope and route avoids an unbounded per-request
    counter collection. The update pipeline is atomic and requires MongoDB 4.2+.
    """
    current = now or datetime.now(timezone.utc)
    key = hashlib.sha256(f"{token_scope}:{route}".encode("utf-8")).hexdigest()
    elapsed_ms = {"$subtract": [current, "$window_started_at"]}
    expired = {"$gte": [elapsed_ms, 60_000]}
    doc = db["scenario_api_rate_limits"].find_one_and_update(
        {"_id": key},
        [
            {"$set": {
                "window_started_at": {"$ifNull": ["$window_started_at", current]},
                "request_count": {"$ifNull": ["$request_count", 0]},
            }},
            {"$set": {
                "window_started_at": {"$cond": [expired, current, "$window_started_at"]},
                "request_count": {"$cond": [expired, 1, {"$add": ["$request_count", 1]}]},
                "updated_at": current,
            }},
        ],
        upsert=True,
        return_document=True,
    )
    count = int((doc or {}).get("request_count", limit + 1))
    return count <= limit


def _finish_demo_idempotency(db, request_id: str, code: int, body: dict[str, Any], *, run_id: str | None = None):
    db["scenario_api_idempotency"].update_one(
        {"_id": request_id, "state": "processing"},
        {"$set": {"state": "finished", "http_status": int(code), "response": body,
                  "scenario_run_id": run_id, "finished_at": datetime.now(timezone.utc)}},
    )


def _demo_run_for_farm(db, run_id: str, farm_key: str):
    return db["scenario_runs"].find_one({"_id": run_id, "farm_key": farm_key},
                                       {"_id": 1, "status": 1, "farm_key": 1})


def _release_terminal_demo_lock(db, farm_key: str, run_id: str) -> None:
    run = _demo_run_for_farm(db, run_id, farm_key)
    if run and run.get("status") in {"stopped", "rejected"}:
        db["scenario_api_farm_locks"].delete_one({"_id": farm_key, "scenario_run_id": run_id})


@app.post('/api/demo/scenarios')
async def control_virtual_scenario(request: Request):
    """Start/stop an isolated virtual-IoT scenario from an external demo client.

    Requires SMIOT_DEMO_CONTROL_TOKEN. This API only publishes to the virtual
    simulator control topic; it does not issue commands to physical actuators.
    Idempotency-Key is required. A 202 response means queued for the simulator,
    not acknowledged/applied; GET the returned status_url for the device ACK.
    """
    if not os.getenv("SMIOT_DEMO_CONTROL_TOKEN", "").strip():
        return JSONResponse(status_code=503, content={"status": "unavailable", "reason": "demo_control_not_configured"})
    if not _demo_control_authorized(request):
        return JSONResponse(status_code=401, content={"status": "unauthorized"})
    try:
        raw = await request.body()
        if len(raw) > 4096:
            return JSONResponse(status_code=413, content={"status": "invalid_request"})
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return JSONResponse(status_code=400, content={"status": "invalid_json"})
    if not isinstance(payload, dict):
        return JSONResponse(status_code=400, content={"status": "invalid_request"})

    idempotency_key = str(request.headers.get("idempotency-key") or "").strip()
    if not idempotency_key or len(idempotency_key) > 200:
        return JSONResponse(status_code=400, content={"status": "idempotency_key_required"})
    # The idempotency namespace is scoped to the configured bearer token without
    # storing the token itself; rotating tokens naturally starts a fresh namespace.
    token_scope = hashlib.sha256(os.getenv("SMIOT_DEMO_CONTROL_TOKEN", "").strip().encode("utf-8")).hexdigest()
    try:
        db = _demo_control_store()
        if not _take_demo_api_rate_limit(db, token_scope, "write", 20):
            return JSONResponse(status_code=429, content={"status": "rate_limited", "retry_after_seconds": 60},
                                headers={"Retry-After": "60"})
    except Exception as exc:
        system_logger.warning("External virtual scenario rate limit store unavailable (%s)", type(exc).__name__)
        return JSONResponse(status_code=503, content={"status": "unavailable", "reason": "rate_limit_store_unavailable"})
    request_id = hashlib.sha256(f"{token_scope}:{idempotency_key}".encode("utf-8")).hexdigest()
    request_fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    try:
        try:
            db["scenario_api_idempotency"].insert_one({
                "_id": request_id, "request_fingerprint": request_fingerprint,
                "state": "processing", "created_at": datetime.now(timezone.utc),
            })
        except Exception as exc:
            from pymongo.errors import DuplicateKeyError
            if not isinstance(exc, DuplicateKeyError):
                raise
            previous = db["scenario_api_idempotency"].find_one({"_id": request_id}) or {}
            if previous.get("request_fingerprint") != request_fingerprint:
                return JSONResponse(status_code=409, content={"status": "idempotency_key_conflict"})
            if previous.get("state") != "finished":
                return JSONResponse(status_code=409, content={"status": "idempotency_request_in_progress"})
            replay = dict(previous.get("response") or {})
            replay["idempotent_replay"] = True
            return JSONResponse(status_code=int(previous.get("http_status", 202)), content=replay)
    except Exception as exc:
        system_logger.warning("External virtual scenario idempotency store unavailable (%s)", type(exc).__name__)
        return JSONResponse(status_code=503, content={"status": "unavailable", "reason": "idempotency_store_unavailable"})

    def finish(code: int, body: dict[str, Any], run_id: str | None = None):
        _finish_demo_idempotency(db, request_id, code, body, run_id=run_id)
        return JSONResponse(status_code=code, content=body)

    action = str(payload.get("action") or "").strip().lower()
    if action not in {"start", "stop"}:
        return finish(400, {"status": "invalid_action", "allowed": ["start", "stop"]})
    if not _mqtt_connected():
        return finish(503, {"status": "unavailable", "reason": "mqtt_disconnected"})

    from service.farm_registry import FARM_KEYS
    farm_key = str(payload.get("farm_key") or "greenhouse_a").strip()
    if farm_key not in FARM_KEYS:
        return finish(400, {"status": "invalid_farm"})

    command_id = f"api-{uuid4()}"
    command: dict[str, Any] = {
        "action": "START_SCENARIO" if action == "start" else "STOP_SCENARIO",
        "command_id": command_id,
        "farm_key": farm_key,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "requested_by": "external_demo_api",
        "source": "external_demo_api",
        "synthetic": True,
    }
    if action == "start":
        from service.scenario_catalog import canonical_type, resolve_scenario
        from service.demo_mode import SUPPORTED_SCENARIOS, VIRTUAL_NODE_IDS
        requested_type = str(payload.get("scenario_type") or "").strip()
        scenario = resolve_scenario(requested_type)
        scenario_type = canonical_type(requested_type)
        if not scenario or not scenario_type or scenario_type not in SUPPORTED_SCENARIOS:
            return finish(400, {"status": "unsupported_scenario"})
        node_id = payload.get("node_id")
        if node_id is not None:
            try:
                node_id = int(node_id)
            except (TypeError, ValueError):
                return finish(400, {"status": "invalid_node"})
            if node_id not in VIRTUAL_NODE_IDS:
                return finish(400, {"status": "invalid_node"})
        try:
            seed = int(payload.get("seed", 17))
        except (TypeError, ValueError):
            return finish(400, {"status": "invalid_seed"})
        if abs(seed) > 2**32 - 1:
            return finish(400, {"status": "invalid_seed"})
        run_id = str(payload.get("scenario_run_id") or uuid4()).strip()
        if not run_id or len(run_id) > 128:
            return finish(400, {"status": "invalid_run_id"})
        if db["scenario_runs"].find_one({"_id": run_id}, {"_id": 1}) or db["scenario_run_events"].find_one(
            {"scenario_run_id": run_id}, {"_id": 1}
        ):
            return finish(409, {"status": "scenario_run_id_already_used", "scenario_run_id": run_id})
        command.update({"scenario_type": scenario_type, "scenario_code": scenario["code"],
                        "scenario_run_id": run_id, "node_id": node_id, "seed": seed})
        if payload.get("lot_id") is not None:
            lot_id = str(payload.get("lot_id")).strip()
            if not lot_id or len(lot_id) > 128:
                return finish(400, {"status": "invalid_lot_id"})
            command["lot_id"] = lot_id
        # Reconcile a previous API lock before reserving this farm. Existing runs
        # started in the UI/CLI also count as active and cannot be overlapped.
        existing_lock = db["scenario_api_farm_locks"].find_one({"_id": farm_key})
        if existing_lock:
            _release_terminal_demo_lock(db, farm_key, str(existing_lock.get("scenario_run_id") or ""))
            existing_lock = db["scenario_api_farm_locks"].find_one({"_id": farm_key})
        active_run = db["scenario_runs"].find_one(
            {"farm_key": farm_key, "status": "started"}, {"_id": 1}
        )
        if existing_lock or active_run:
            active_id = str((existing_lock or active_run or {}).get("scenario_run_id") or
                            (active_run or {}).get("_id") or "unknown")
            return finish(409, {"status": "farm_scenario_already_active", "farm_key": farm_key,
                                "active_scenario_run_id": active_id})
        lock_doc = {"_id": farm_key, "scenario_run_id": run_id, "state": "queued",
                    "created_at": datetime.now(timezone.utc)}
        try:
            db["scenario_api_farm_locks"].insert_one(lock_doc)
        except Exception as exc:
            from pymongo.errors import DuplicateKeyError
            if isinstance(exc, DuplicateKeyError):
                return finish(409, {"status": "farm_scenario_already_active", "farm_key": farm_key})
            raise
    else:
        run_id = str(payload.get("scenario_run_id") or "").strip()
        if not run_id or len(run_id) > 128:
            return finish(400, {"status": "invalid_run_id"})
        requested_farm = db["scenario_runs"].find_one(
            {"_id": run_id}, {"_id": 1, "farm_key": 1, "status": 1}
        )
        if not requested_farm or requested_farm.get("farm_key") != farm_key:
            return finish(404, {"status": "scenario_run_not_found", "scenario_run_id": run_id})
        if requested_farm.get("status") != "started":
            return finish(409, {"status": "scenario_not_active", "scenario_run_id": run_id,
                                "run_status": requested_farm.get("status", "unknown")})
        command["scenario_run_id"] = run_id

    try:
        from service import mqtt as mqtt_service
        info = mqtt_service.mqtt_client.publish(
            "farm/demo/control", json.dumps(command, separators=(",", ":")), qos=1
        )
        info.wait_for_publish(timeout=3)
        if info.rc != 0 or not info.is_published():
            if action == "start":
                db["scenario_api_farm_locks"].delete_one({"_id": farm_key, "scenario_run_id": run_id})
            return finish(503, {"status": "publish_failed"}, run_id)
    except Exception as exc:
        system_logger.warning("External virtual scenario publish failed (%s)", type(exc).__name__)
        if action == "start":
            db["scenario_api_farm_locks"].delete_one({"_id": farm_key, "scenario_run_id": run_id})
        return finish(503, {"status": "publish_failed"}, run_id)

    system_logger.info("smiot_virtual_scenario_command action=%s run_id=%s command_id=%s farm=%s source=external_api",
                       action, run_id, command_id, farm_key)
    body = {
        "status": "queued", "acknowledged": False, "synthetic": True,
        "scenario_run_id": run_id, "command_id": command_id,
        "farm_key": farm_key, "status_url": f"/api/demo/scenarios/{run_id}",
    }
    return finish(202, body, run_id)


@app.get('/api/demo/scenarios/{scenario_run_id}')
async def virtual_scenario_status(scenario_run_id: str, request: Request):
    """Read back persisted simulator ACK for an externally started scenario."""
    if not os.getenv("SMIOT_DEMO_CONTROL_TOKEN", "").strip():
        return JSONResponse(status_code=503, content={"status": "unavailable", "reason": "demo_control_not_configured"})
    if not _demo_control_authorized(request):
        return JSONResponse(status_code=401, content={"status": "unauthorized"})
    if len(scenario_run_id) > 128:
        return JSONResponse(status_code=400, content={"status": "invalid_run_id"})
    try:
        db = _demo_control_store()
        token_scope = hashlib.sha256(os.getenv("SMIOT_DEMO_CONTROL_TOKEN", "").strip().encode("utf-8")).hexdigest()
        if not _take_demo_api_rate_limit(db, token_scope, "read", 120):
            return JSONResponse(status_code=429, content={"status": "rate_limited", "retry_after_seconds": 60},
                                headers={"Retry-After": "60"})
        run = db["scenario_runs"].find_one(
            {"_id": scenario_run_id},
            {"_id": 1, "status": 1, "farm_key": 1, "scenario_type": 1, "scenario_code": 1,
             "incident_id": 1, "started_at": 1, "ended_at": 1, "last_ack_at": 1,
             "last_rejection_reason": 1, "synthetic": 1},
        )
    except Exception as exc:
        system_logger.warning("External virtual scenario status read failed (%s)", type(exc).__name__)
        return JSONResponse(status_code=503, content={"status": "unavailable", "reason": "status_store_unavailable"})
    if not run:
        return JSONResponse(status_code=202, content={"status": "pending_ack", "acknowledged": False,
                                                      "scenario_run_id": scenario_run_id})
    farm_key = str(run.get("farm_key") or "")
    if run.get("status") in {"stopped", "rejected"}:
        _release_terminal_demo_lock(db, farm_key, scenario_run_id)
    ack = db["scenario_run_events"].find_one(
        {"scenario_run_id": scenario_run_id}, sort=[("ack_at", -1)],
        projection={"_id": 0, "command_id": 1, "status": 1, "applied": 1, "reason": 1, "ack_at": 1},
    )
    return {
        "status": run.get("status", "unknown"), "acknowledged": bool(ack),
        "synthetic": bool(run.get("synthetic", True)),
        "scenario_run_id": scenario_run_id, "farm_key": run.get("farm_key"),
        "scenario_type": run.get("scenario_type"), "scenario_code": run.get("scenario_code"),
        "incident_id": run.get("incident_id"), "started_at": run.get("started_at"),
        "ended_at": run.get("ended_at"), "last_ack_at": run.get("last_ack_at"),
        "reason": run.get("last_rejection_reason"),
        "latest_ack": ({"command_id": ack.get("command_id"), "status": ack.get("status"),
                        "applied": ack.get("applied"), "reason": ack.get("reason"),
                        "acknowledged_at": ack.get("ack_at").isoformat() if hasattr(ack.get("ack_at"), "isoformat") else ack.get("ack_at")}
                       if ack else None),
    }


@app.post('/api/demo/w9/late-ack')
async def run_w9_late_ack_drill(request: Request):
    """Admin-token-only, virtual-PLC-only bounded W9 late-ACK acceptance drill.

    The only command this route can create is all outputs OFF on greenhouse_j.
    The virtual PLC applies that safe state but withholds the first ACK; this
    app process waits until the ordinary timeout worker marks the command
    unacknowledged, then publishes a matching synthetic ACK and reads the
    Mongo action ledger. It cannot reach physical actuator topics/devices.
    """
    if os.getenv("SMIOT_DEMO_MODE", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        return JSONResponse(status_code=404, content={"status": "unavailable"})
    expected = os.getenv("SMIOT_DEMO_CONTROL_TOKEN", "").strip()
    if not expected:
        return JSONResponse(status_code=503, content={"status": "unavailable", "reason": "demo_control_not_configured"})
    if not _demo_control_authorized(request):
        return JSONResponse(status_code=401, content={"status": "unauthorized"})
    if not _w9_late_ack_lock.acquire(blocking=False):
        return JSONResponse(status_code=409, content={"status": "drill_in_progress"})

    command_id = uuid4().hex
    farm_key = "greenhouse_j"
    timeout_seconds = 6
    started = datetime.now(timezone.utc)
    try:
        try:
            db = _demo_control_store()
            token_scope = hashlib.sha256(expected.encode("utf-8")).hexdigest()
            if not _take_demo_api_rate_limit(db, token_scope, "w9-late-ack", 1):
                return JSONResponse(status_code=429, content={"status": "rate_limited", "retry_after_seconds": 60},
                                    headers={"Retry-After": "60"})
        except Exception as exc:
            system_logger.warning("W9 drill rate-limit store unavailable (%s)", type(exc).__name__)
            return JSONResponse(status_code=503, content={"status": "unavailable", "reason": "rate_limit_store_unavailable"})

        from service import mqtt as mqtt_service
        if not _mqtt_connected():
            return JSONResponse(status_code=503, content={"status": "unavailable", "reason": "mqtt_disconnected"})
        # Touch one virtual output only; never issue a blanket multi-channel
        # command in the drill. The target is explicitly OFF.
        bits = {"bit0": 0}
        command = {
            **bits, "action": "SET_OUTPUTS", "farm_key": farm_key,
            "command_id": command_id, "monitor_id": "342734743",
            "reason": "W9 bounded synthetic late-ACK drill; keep virtual pump output OFF",
            "source": "smiot_w9_admin_drill", "target": "smiot_virtual_plc",
            "synthetic": True, "w9_late_ack_drill": True,
        }
        command = mqtt_service.prepare_actuator_command("farm/control", command,
                                                        timeout_seconds=timeout_seconds)
        if not command.get("command_id") or command["command_id"] != command_id:
            return JSONResponse(status_code=500, content={"status": "failed", "reason": "command_registration_failed"})

        from service.operational_evidence import record_action_event
        record_action_event(command, "requested")
        if not mqtt_service.publish_mqtt("farm/control", command):
            record_action_event({**command, "error": "mqtt_publish_failed"}, "failed")
            return JSONResponse(status_code=503, content={"status": "failed", "reason": "publish_failed",
                                                          "command_id": command_id, "farm_key": farm_key})
        record_action_event(command, "published")

        deadline = time.monotonic() + 35
        pending = mqtt_service.state.setdefault("actuator_pending_by_command", {})
        records = [row for row in pending.values()
                   if row.get("command_id") == command_id and row.get("farm_key") == farm_key]
        while time.monotonic() < deadline and not records:
            await asyncio.sleep(0.2)
            records = [row for row in pending.values()
                       if row.get("command_id") == command_id and row.get("farm_key") == farm_key]
        while time.monotonic() < deadline and records and not all(row.get("status") == "unacknowledged" for row in records):
            if any(row.get("status") not in {"pending", "unacknowledged"} for row in records):
                return JSONResponse(status_code=409, content={"status": "failed", "reason": "unexpected_command_state",
                                                              "command_id": command_id, "farm_key": farm_key})
            await asyncio.sleep(0.25)
        if not records or not all(row.get("status") == "unacknowledged" for row in records):
            return JSONResponse(status_code=504, content={"status": "timeout_not_observed",
                                                          "command_id": command_id, "farm_key": farm_key})

        # Exact ID + farm + OFF readback are required by the receiver matcher.
        ack = {
            "event": "virtual_plc_command_ack", "command_id": command_id,
            "action": "SET_OUTPUTS", "farm_key": farm_key, "monitor_id": "342734743",
            "source": "smiot_w9_admin_drill_late_ack", "target": "smiot_virtual_plc",
            "synthetic": True, "applied": True, "verified": True,
            "virtual_output": bits, "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        info = mqtt_service.mqtt_client.publish("farm/command/ack", json.dumps(ack, separators=(",", ":")), qos=1)
        if getattr(info, "rc", 1) != 0:
            return JSONResponse(status_code=503, content={"status": "failed", "reason": "late_ack_publish_failed",
                                                          "command_id": command_id, "farm_key": farm_key})
        while time.monotonic() < deadline:
            if records and all(row.get("status") == "acknowledged" and row.get("late_ack") is True
                               and row.get("target_matches") is True and row.get("ack_verified") is True
                               for row in records):
                break
            await asyncio.sleep(0.2)
        accepted = bool(records) and all(
            row.get("status") == "acknowledged" and row.get("late_ack") is True
            and row.get("target_matches") is True and row.get("ack_verified") is True for row in records
        )
        ledger = db["action_ledger"].find_one({"_id": command_id}, {"_id": 0})
        response = {
            "status": "verified" if accepted and ledger and ledger.get("state") == "acknowledged" else "failed",
            "synthetic": True, "farm_key": farm_key, "command_id": command_id,
            "target": "smiot_virtual_plc", "target_output_off": True,
            "late_ack": all(row.get("late_ack") is True for row in records),
            "matching_command_and_farm": all(row.get("command_id") == command_id and row.get("farm_key") == farm_key for row in records),
            "target_matches": all(row.get("target_matches") is True for row in records),
            "ack_verified": all(row.get("ack_verified") is True for row in records),
            "ledger_state": (ledger or {}).get("state"),
            "ledger_synthetic": (ledger or {}).get("synthetic"),
            "elapsed_seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 2),
            "metrics_emitted": ["smiot.actuator.command_unacknowledged", "smiot.actuator.command_late_acknowledged"],
            "monitor_id": "342734743",
        }
        return JSONResponse(status_code=200 if response["status"] == "verified" else 500, content=response)
    except Exception as exc:
        system_logger.exception("W9 late-ACK drill failed (%s)", type(exc).__name__)
        return JSONResponse(status_code=500, content={"status": "failed", "reason": "drill_error",
                                                      "command_id": command_id, "farm_key": farm_key})
    finally:
        _w9_late_ack_lock.release()


@app.get('/healthz')
async def healthz():
    mongo_ok, newest = await _read_mongo_health()
    payload = build_healthz_payload(
        mongo_ok=mongo_ok,
        mqtt_ok=_mqtt_connected(),
        newest_sample_at=newest,
        now=datetime.now(timezone.utc),
    )
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


@app.post('/api/integrations/datadog/w2-greenhouse-j/recover')
async def recover_w2_greenhouse_j(request: Request):
    """Request an exact scenario stop; never claim recovery on the request."""
    expected = os.getenv("DATADOG_APP_NOTIFICATION_TOKEN", "").strip()
    supplied = request.headers.get("authorization", "")
    if not expected:
        return JSONResponse(status_code=503, content={"status": "unavailable", "reason": "recovery_not_configured"})
    if not supplied.lower().startswith("bearer ") or not secrets.compare_digest(supplied[7:].strip(), expected):
        return JSONResponse(status_code=401, content={"status": "unauthorized"})
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"status": "invalid_request"})
    if not isinstance(payload, dict) or str(payload.get("monitor_id") or "") != "W2-GREENHOUSE-J":
        return JSONResponse(status_code=400, content={"status": "invalid_scope"})
    workflow_run_id = str(payload.get("workflow_run_id") or "").strip()
    if not workflow_run_id or len(workflow_run_id) > 128:
        return JSONResponse(status_code=400, content={"status": "workflow_run_id_required"})
    if not _mqtt_connected():
        return JSONResponse(status_code=503, content={"status": "unavailable", "reason": "mqtt_disconnected"})
    try:
        from service.mongodb_store import database
        db = database()
        # Node 1 is the Velxio sensor. Node 2 is the pump board and cannot
        # provide soil samples for this verifier.
        active = list(db.operational_incidents.find(
            {"farm_key": "greenhouse_j", "node_id": 1,
             "kind": "soil_humidity_flatline", "status": {"$in": ["open", "holding"]},
             "scenario_run_id": {"$exists": True}},
            {"_id": 1, "node_id": 1, "scenario_run_id": 1, "status": 1},
        ).limit(2))
        if len(active) != 1:
            return JSONResponse(status_code=409, content={"status": "refused", "reason": "active_incident_not_unique"})
        incident = active[0]
        run_id = str(incident["scenario_run_id"])
        if (not db.scenario_runs.find_one({"_id": run_id, "farm_key": "greenhouse_j",
                                           "node_id": 1, "scenario_type": "soil_flatline",
                                           "status": "started"})):
            return JSONResponse(status_code=409, content={"status": "refused", "reason": "scenario_run_not_current"})
        from pymongo.errors import DuplicateKeyError
        request_id = str(incident["_id"])
        command_id = f"w2-ghj-stop-{uuid4()}"
        try:
            db.w2_greenhouse_j_recovery.insert_one({
                "_id": request_id, "incident_id": request_id,
                "scenario_run_id": run_id, "workflow_run_id": workflow_run_id,
                "stop_command_id": command_id, "state": "stop_requested",
                "created_at": datetime.now(timezone.utc), "synthetic": True,
            })
        except DuplicateKeyError:
            prior = db.w2_greenhouse_j_recovery.find_one({"_id": request_id}) or {}
            if prior.get("workflow_run_id") != workflow_run_id:
                return JSONResponse(status_code=409, content={"status": "refused", "reason": "recovery_already_owned"})
            return JSONResponse(status_code=202, content={"status": "pending_verification",
                                                          "incident_id": request_id, "scenario_run_id": run_id})
        command = {"action": "STOP_SCENARIO", "command_id": command_id,
                   "incident_id": request_id, "scenario_run_id": run_id,
                   "farm_key": "greenhouse_j", "requested_by": "datadog_w2_workflow",
                   "source": "datadog_workflow", "synthetic": True}
        from service import mqtt as mqtt_service
        info = mqtt_service.mqtt_client.publish("farm/demo/control",
                                                 json.dumps(command, separators=(",", ":")), qos=1)
        info.wait_for_publish(timeout=3)
        if info.rc != 0 or not info.is_published():
            db.w2_greenhouse_j_recovery.delete_one({"_id": request_id, "state": "stop_requested"})
            return JSONResponse(status_code=503, content={"status": "failed", "reason": "publish_failed"})
        return JSONResponse(status_code=202, content={"status": "stop_requested",
                                                      "incident_id": request_id, "scenario_run_id": run_id})
    except Exception as exc:
        system_logger.warning("W2 greenhouse-J stop failed (%s)", type(exc).__name__)
        return JSONResponse(status_code=500, content={"status": "failed", "reason": "recovery_error"})


@app.post('/api/integrations/datadog/w2-greenhouse-j/verify')
async def verify_w2_greenhouse_j(request: Request):
    """Verify STOP ACK, exact profile ACK and three fresh varying sensor samples."""
    expected = os.getenv("DATADOG_APP_NOTIFICATION_TOKEN", "").strip()
    supplied = request.headers.get("authorization", "")
    if not expected:
        return JSONResponse(status_code=503, content={"status": "unavailable", "reason": "recovery_not_configured"})
    if not supplied.lower().startswith("bearer ") or not secrets.compare_digest(supplied[7:].strip(), expected):
        return JSONResponse(status_code=401, content={"status": "unauthorized"})
    try:
        payload = await request.json()
        workflow_run_id = str(payload.get("workflow_run_id") or "").strip()
        if not workflow_run_id or len(workflow_run_id) > 128:
            return JSONResponse(status_code=400, content={"status": "workflow_run_id_required"})
        from service.mongodb_store import database
        db = database()
        recovery = db.w2_greenhouse_j_recovery.find_one({"workflow_run_id": workflow_run_id})
        if not recovery:
            return JSONResponse(status_code=409, content={"status": "unverified", "reason": "request_not_found"})
        incident_id = recovery["incident_id"]
        run_id = recovery["scenario_run_id"]
        if recovery.get("state") == "verified":
            return {"status": "verified", "incident_id": incident_id, "scenario_run_id": run_id}
        stopped = db.scenario_run_events.find_one({
            "scenario_run_id": run_id, "command_id": recovery["stop_command_id"],
            "farm_key": "greenhouse_j", "node_id": 1, "status": "stopped", "applied": True,
        })
        if not stopped:
            return JSONResponse(status_code=202, content={"status": "pending_verification", "reason": "stop_ack_missing"})
        if not db.scenario_runs.find_one({"_id": run_id, "farm_key": "greenhouse_j", "status": "stopped"}):
            return JSONResponse(status_code=202, content={"status": "pending_verification", "reason": "run_not_stopped"})
        profile_command_id = recovery.get("profile_command_id")
        if not profile_command_id:
            profile_command_id = f"w2-ghj-profile-{uuid4()}"
            db.w2_greenhouse_j_recovery.update_one(
                {"_id": incident_id, "profile_command_id": {"$exists": False}},
                {"$set": {"profile_command_id": profile_command_id}},
            )
            recovery = db.w2_greenhouse_j_recovery.find_one({"_id": incident_id}) or recovery
            profile_command_id = recovery.get("profile_command_id")
        ack = db.device_profile_events.find_one({
            "command_id": profile_command_id, "incident_id": incident_id,
            "scenario_run_id": run_id, "farm_key": "greenhouse_j", "node_id": "node1",
            "profile": "normal", "applied": True, "verified": True,
        })
        if not ack:
            if not _mqtt_connected():
                return JSONResponse(status_code=202, content={"status": "pending_verification", "reason": "mqtt_disconnected"})
            command = {"event": "workflow_profile_recovery", "command_id": profile_command_id,
                       "incident_id": incident_id, "scenario_run_id": run_id,
                       "farm_key": "greenhouse_j", "target_device_id": "node1",
                       "profile": "normal", "source": "datadog_workflow", "synthetic": True}
            from service import mqtt as mqtt_service
            info = mqtt_service.mqtt_client.publish("farm/demo/profile-command",
                                                     json.dumps(command, separators=(",", ":")), qos=1)
            info.wait_for_publish(timeout=3)
            if info.rc != 0 or not info.is_published():
                return JSONResponse(status_code=202, content={"status": "pending_verification", "reason": "profile_publish_failed"})
            return JSONResponse(status_code=202, content={"status": "pending_verification", "reason": "profile_ack_missing"})
        samples = list(db.telemetry.find(
            {"meta.farm_key": "greenhouse_j", "meta.measurement_type": "node",
             "meta.node_id": 1, "source.source": "velxio_synthetic",
             "source.device_profile": "normal", "source.scenario_run_id": run_id,
             "source.incident_id": incident_id, "timestamp": {"$gt": ack["received_at"]},
             "readings.soil_hum": {"$type": "number"}},
            {"readings.soil_hum": 1, "timestamp": 1, "source.sequence": 1, "_id": 0},
        ).sort("timestamp", -1).limit(3))
        vals = [float(s["readings"]["soil_hum"]) for s in samples]
        if len(vals) < 3 or len({s["timestamp"] for s in samples}) < 3 or max(vals) - min(vals) < 0.5:
            return JSONResponse(status_code=202, content={"status": "pending_verification",
                                                          "reason": "normal_samples_insufficient",
                                                          "fresh_normal_sample_count": len(vals)})
        verified_at = datetime.now(timezone.utc)
        evidence = {"verified": True, "method": "velxio_profile_ack_and_three_fresh_varying_mongodb_samples",
                    "incident_id": incident_id, "scenario_run_id": run_id,
                    "stop_command_id": recovery["stop_command_id"],
                    "profile_command_id": profile_command_id,
                    "farm_key": "greenhouse_j", "node_id": 1,
                    "profile_ack_id": ack.get("_id"), "sample_count": len(vals),
                    "soil_humidity_range_pct": [min(vals), max(vals)], "synthetic": True,
                    "verified_at": verified_at}
        result = db.operational_incidents.update_one(
            {"_id": incident_id, "farm_key": "greenhouse_j", "scenario_run_id": run_id,
             "status": "recovering"},
            {"$set": {"status": "recovered", "recovered_at": verified_at,
                      "recovery_verification": evidence, "updated_at": verified_at},
             "$push": {"timeline": {"at": verified_at, "event": "profile_recovery_verified", "by": "datadog_w2_workflow"}}},
        )
        if not result.modified_count:
            return JSONResponse(status_code=409, content={"status": "unverified", "reason": "incident_state_changed"})
        db.scenario_runs.update_one({"_id": run_id, "farm_key": "greenhouse_j", "status": "stopped"},
                                    {"$set": {"status": "recovered", "recovered_at": verified_at,
                                              "recovery_verification": evidence}})
        db.w2_greenhouse_j_recovery.update_one({"_id": incident_id},
                                                {"$set": {"state": "verified", "verified_at": verified_at}})
        return {"status": "verified", "synthetic": True, "farm_key": "greenhouse_j", "node_id": 1,
                "incident_id": incident_id, "scenario_run_id": run_id,
                "profile": "normal", "fresh_normal_sample_count": len(vals)}
    except Exception as exc:
        system_logger.warning("W2 greenhouse-J verification failed (%s)", type(exc).__name__)
        return JSONResponse(status_code=500, content={"status": "failed", "reason": "recovery_error"})


@app.post('/api/integrations/datadog/recovery-verification')
async def verify_datadog_ec2_recovery(request: Request):
    """Read SSM completion and re-check app dependencies; never starts a service.

    Payload contract: {"workflow_run_id": "<Datadog InstanceId>", "instance_id": "<EC2 instance>"}.
    The current SSM document receives Datadog's InstanceId as IncidentId. The bridge
    uses that echoed value to find exactly one command for the configured instance,
    avoiding reliance on an unverified SendCommand output binding. The app role needs
    ssm:ListCommands and ssm:GetCommandInvocation; denied access is reported unknown.
    """
    expected = os.getenv("DATADOG_APP_NOTIFICATION_TOKEN", "").strip()
    if not expected:
        return JSONResponse(status_code=503, content={"status": "unavailable", "reason": "verifier_not_configured"})
    supplied = request.headers.get("authorization", "")
    if not supplied.lower().startswith("bearer ") or not secrets.compare_digest(supplied[7:].strip(), expected):
        return JSONResponse(status_code=401, content={"status": "unauthorized"})

    try:
        raw = await request.body()
        if len(raw) > 4096:
            return JSONResponse(status_code=413, content={"status": "invalid_request"})
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return JSONResponse(status_code=400, content={"status": "invalid_request"})
    if not isinstance(payload, dict):
        return JSONResponse(status_code=400, content={"status": "invalid_request"})

    from service.w3_recovery_verification import (
        classify_live_health,
        classify_ssm_invocation,
        find_unique_command,
        validate_instance_id,
        validate_workflow_run_id,
    )

    expected_instance = os.getenv("SMIOT_RECOVERY_INSTANCE_ID", "").strip()
    workflow_run_id = payload.get("workflow_run_id")
    instance_id = payload.get("instance_id")
    if not validate_workflow_run_id(workflow_run_id) or not validate_instance_id(instance_id, expected_instance):
        return JSONResponse(status_code=400, content={"status": "invalid_request", "reason": "workflow_run_or_instance_not_allowed"})
    workflow_run_id = workflow_run_id.strip()
    instance_id = instance_id.strip()

    def _get_invocation():
        import boto3
        from botocore.config import Config
        region = os.getenv("AWS_REGION", "ap-southeast-2").strip() or "ap-southeast-2"
        client = boto3.client(
            "ssm",
            region_name=region,
            config=Config(
                connect_timeout=2,
                read_timeout=3,
                retries={"total_max_attempts": 1, "mode": "standard"},
            ),
        )
        paginator = client.get_paginator("list_commands")
        match = {"status": "pending", "reason": "ssm_command_not_visible_yet"}
        commands = []
        import time as _time
        visibility_deadline = _time.monotonic() + 15.0
        while _time.monotonic() < visibility_deadline:
            commands = []
            for page in paginator.paginate(
                InstanceId=instance_id,
                Filters=[{"key": "DocumentName", "value": "SMIOT-GuardedStartApp"}],
                PaginationConfig={"PageSize": 50, "MaxItems": 501},
            ):
                commands.extend(page.get("Commands", []))
            if len(commands) > 500:
                return {"_bridge_status": "not_verified", "reason": "ssm_command_search_limit_reached"}
            match = find_unique_command(commands, workflow_run_id, instance_id)
            if match["status"] == "matched":
                break
            _time.sleep(2.0)
        if match["status"] != "matched":
            return {"_bridge_status": match["status"], "reason": match.get("reason")}
        invocation = client.get_command_invocation(CommandId=match["command_id"], InstanceId=instance_id)
        # SendCommand returns before the SSM document finishes. Poll the same
        # correlated invocation briefly so the verifier does not classify a
        # still-running guarded start as a failed recovery.
        if invocation.get("Status") in {"Pending", "InProgress", "Delayed"}:
            import time as _time
            deadline = _time.monotonic() + 15.0
            while _time.monotonic() < deadline:
                _time.sleep(2.0)
                invocation = client.get_command_invocation(CommandId=match["command_id"], InstanceId=instance_id)
                if invocation.get("Status") not in {"Pending", "InProgress", "Delayed"}:
                    break
        invocation["_smiot_expected_command_id"] = match["command_id"]
        return invocation

    try:
        invocation = await asyncio.wait_for(asyncio.to_thread(_get_invocation), timeout=40)
    except Exception as exc:
        # SSM command listings can lag shortly after SendCommand; AccessDenied
        # and transport errors are also unknown, never evidence of recovery.
        error_code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if error_code in {"InvocationDoesNotExist", "InvalidCommandId"}:
            return JSONResponse(status_code=202, content={"status": "pending", "verified": False, "phase": "ssm_result_not_visible_yet"})
        system_logger.warning("smiot_w3_verification status=unknown reason=ssm_read_unavailable")
        return JSONResponse(status_code=503, content={"status": "unknown", "reason": "ssm_read_unavailable"})

    if invocation.get("_bridge_status") == "pending":
        return JSONResponse(status_code=202, content={"status": "pending", "verified": False, "phase": "ssm_command_not_visible_yet"})
    if invocation.get("_bridge_status") == "not_verified":
        return JSONResponse(
            status_code=422,
            content={
                "status": "not_verified",
                "verified": False,
                "reason": invocation.get("reason", "ssm_command_not_unique"),
            },
        )
    expected_command_id = invocation.pop("_smiot_expected_command_id", None)
    result = classify_ssm_invocation(
        invocation,
        expected_run_id=workflow_run_id,
        expected_command_id=expected_command_id,
        expected_instance_id=instance_id,
    )
    if result["status"] == "pending":
        return JSONResponse(status_code=202, content={"status": "pending", "verified": False, "phase": "ssm_command_running"})
    if result["status"] == "not_verified":
        system_logger.warning("smiot_w3_verification status=not_verified reason=%s", result.get("reason", "unknown"))
        return JSONResponse(
            status_code=422,
            content={
                "status": "not_verified",
                "verified": False,
                "reason": result.get("reason", "guard_did_not_verify"),
                "ssm_status": result.get("ssm_status"),
            },
        )

    mongo_ok, newest = await _read_mongo_health()
    live_health = build_healthz_payload(
        mongo_ok=mongo_ok,
        mqtt_ok=_mqtt_connected(),
        newest_sample_at=newest,
        now=datetime.now(timezone.utc),
    )
    if not classify_live_health(live_health):
        return JSONResponse(
            status_code=202,
            content={"status": "pending", "verified": False, "phase": "waiting_for_live_health_and_fresh_telemetry", "health": live_health},
        )
    outcome = "recovered" if result["status"] == "recovery_action_verified" else "already_healthy"
    system_logger.info("smiot_w3_verification status=%s run_id=%s", outcome, result.get("run_id", "unknown"))
    return {
        "status": outcome,
        "verified": True,
        "ssm_status": "Success",
        "guard_run_id": result.get("run_id"),
        "guard_timestamp": result.get("guard_timestamp"),
        "health": live_health,
    }


@app.post('/api/internal/safe-mode/recovery-clear')
async def verify_recovery_and_clear_safe_mode(request: Request):
    """Datadog recovery workflow entrypoint; app verifier owns all recovery checks."""
    expected = os.getenv("SAFE_MODE_RECOVERY_TOKEN", "").strip()
    if not expected:
        return JSONResponse(status_code=503, content={"result": "disabled", "reason": "recovery endpoint is not configured"})
    supplied = request.headers.get("authorization", "")
    if not supplied.lower().startswith("bearer ") or not secrets.compare_digest(supplied[7:].strip(), expected):
        return JSONResponse(status_code=401, content={"result": "unauthorized"})
    if not _recovery_clear_lock.acquire(blocking=False):
        return JSONResponse(status_code=409, content={"result": "already_running"})
    try:
        verifier = Path(__file__).parent / "scripts" / "verify_and_clear_demo_safe_mode.py"
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-X", "utf8", str(verifier)],
                cwd=str(Path(__file__).parent),
                capture_output=True,
                text=True,
                timeout=55,
                check=False,
            )
        except subprocess.TimeoutExpired:
            system_logger.error("smiot_recovery_verification result=timeout source=datadog_workflow")
            return JSONResponse(status_code=504, content={"result": "timeout"})
        output = result.stdout.strip().splitlines()
        details = {}
        if output:
            try:
                details = json.loads(output[-1])
            except json.JSONDecodeError:
                details = {"result": "invalid_verifier_output"}
        if result.returncode != 0:
            reason = (result.stderr or result.stdout or "recovery verifier rejected CLEAR")[-1000:].strip()
            # Policy guard rejections are expected when this action runs on Alert
            # or before recovery is proven. Infrastructure/verifier errors remain
            # non-2xx so Datadog marks the action failed and responders can see it.
            guarded = "Refusing to clear HOLD:" in reason
            system_logger.warning("smiot_recovery_verification result=%s source=datadog_workflow reason=%s", "not_cleared" if guarded else "verifier_error", reason)
            return JSONResponse(
                status_code=200 if guarded else 503,
                content={"result": "verification_not_passed" if guarded else "verifier_error", "details": details, "reason": reason},
            )
        system_logger.info("smiot_recovery_verification source=datadog_workflow details=%s", json.dumps(details, separators=(",", ":")))
        return {"source": "application_recovery_verifier", **details}
    finally:
        _recovery_clear_lock.release()


@app.post('/api/integrations/datadog/notification')
async def receive_datadog_notification(request: Request):
    """Persist an authenticated Datadog workflow event in the app notification bell.

    Configure DATADOG_APP_NOTIFICATION_TOKEN on the app and store the matching
    value in a Datadog HTTP Connection; never place it in workflow JSON.
    """
    expected = os.getenv("DATADOG_APP_NOTIFICATION_TOKEN", "").strip()
    if not expected:
        return JSONResponse(status_code=503, content={"result": "disabled"})
    supplied = request.headers.get("authorization", "")
    if not supplied.lower().startswith("bearer ") or not secrets.compare_digest(
        supplied[7:].strip(), expected
    ):
        return JSONResponse(status_code=401, content={"result": "unauthorized"})

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 8192:
                return JSONResponse(status_code=413, content={"result": "payload_too_large"})
        except ValueError:
            return JSONResponse(status_code=400, content={"result": "invalid_content_length"})
    try:
        raw_body = await request.body()
        if len(raw_body) > 8192:
            return JSONResponse(status_code=413, content={"result": "payload_too_large"})
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return JSONResponse(status_code=400, content={"result": "invalid_json"})
    from service.datadog_notifications import NotificationValidationError, normalize_datadog_notification
    try:
        payload = normalize_datadog_notification(payload)
    except NotificationValidationError as exc:
        return JSONResponse(status_code=exc.status_code, content={"result": exc.result})

    event_id = payload["event_id"]
    message = payload["message"]
    farm_key = payload["farm_key"] or ""
    if farm_key:
        from service.farm_registry import FARM_KEYS
        if farm_key not in FARM_KEYS:
            return JSONResponse(status_code=422, content={"result": "unknown_farm"})
    category = payload["category"]
    severity = payload["severity"]

    # Treat a supplied incident ID as a candidate link until MongoDB confirms
    # the incident exists and belongs to the supplied farm. Never let a
    # workflow close/recover an incident through this notification endpoint.
    linked_incident = None
    correlation_status = "unlinked"
    requested_incident_id = payload["incident_id"]
    if requested_incident_id:
        try:
            linked_incident = collection("operational_incidents").find_one(
                {"_id": requested_incident_id},
                {"_id": 1, "farm_key": 1, "status": 1},
            )
        except Exception as exc:
            system_logger.warning("datadog_notification_incident_lookup_failed error=%s", type(exc).__name__)
            linked_incident = None
        if linked_incident:
            incident_farm = str(linked_incident.get("farm_key") or "")
            if incident_farm and (not farm_key or incident_farm == farm_key):
                correlation_status = "verified"
                farm_key = farm_key or incident_farm
            else:
                linked_incident = None

    now = datetime.now(timezone.utc)
    # Event IDs are caller supplied; hash them so arbitrary characters never
    # enter Mongo _id values and repeated workflow deliveries stay idempotent.
    import hashlib
    dedupe_id = "datadog:" + hashlib.sha256(event_id.encode("utf-8")).hexdigest()
    document = {
        "_id": dedupe_id,
        "id": dedupe_id,
        "source": "datadog_workflow",
        "event_id": event_id,
        "message": message,
        "text": message,
        "category": category,
        "severity": severity,
        "farm_key": farm_key or None,
        "incident_id": str(linked_incident["_id"]) if linked_incident else None,
        "correlation_status": correlation_status,
        "workflow_status": payload["status"],
        "decision_code": payload["decision_code"],
        "action_code": payload["action_code"],
        "verification_status": payload["verification_status"],
        "monitor_id": payload["monitor_id"],
        "workflow_run_id": payload["workflow_run_id"] or event_id,
        "scenario_run_id": payload["scenario_run_id"],
        "command_id": payload["command_id"],
        "device_id": payload["device_id"],
        "node_id": payload["node_id"],
        "scenario_code": payload["scenario_code"],
        "event_time": payload["event_time"],
        "synthetic": payload["synthetic"],
        "evidence_refs": payload["evidence_refs"],
        "workflow_name": payload["workflow_name"],
        "workflow_id": payload["workflow_id"],
        "created_at": now,
        "time": now.astimezone().strftime("%H:%M:%S"),
        "read": False,
    }
    try:
        result = collection("notifications").update_one(
            {"_id": dedupe_id}, {"$setOnInsert": document}, upsert=True
        )
    except Exception as exc:
        system_logger.exception("datadog_app_notification_persist_failed")
        return JSONResponse(status_code=503, content={"result": "storage_unavailable", "error": type(exc).__name__})

    inserted = result.upserted_id is not None
    if linked_incident:
        # Persist workflow evidence on the matched incident, but do not modify
        # its lifecycle status. The app recovery verifier remains the sole
        # authority allowed to mark an incident recovered.
        workflow_run_id = payload["workflow_run_id"] or event_id
        observation = {
            "event_id": event_id,
            "workflow_id": payload["workflow_id"],
            "workflow_run_id": workflow_run_id,
            "scenario_run_id": payload["scenario_run_id"],
            "command_id": payload["command_id"],
            "device_id": payload["device_id"],
            "node_id": payload["node_id"],
            "scenario_code": payload["scenario_code"],
            "event_time": payload["event_time"],
            "synthetic": payload["synthetic"],
            "monitor_id": payload["monitor_id"],
            "status": payload["status"] or "unknown",
            "decision_code": payload["decision_code"],
            "action_code": payload["action_code"],
            "verification_status": payload["verification_status"] or "unknown",
            "evidence_refs": payload["evidence_refs"],
            "observed_at": now,
        }
        incident_set = {"updated_at": now, "last_workflow_observation": observation}
        if payload["workflow_id"]:
            incident_set["workflow_id"] = payload["workflow_id"]
        if payload["monitor_id"]:
            incident_set["monitor_id"] = payload["monitor_id"]
        try:
            incident_update = {
                "$set": incident_set,
                "$addToSet": {
                    "evidence.workflow_execution_ids": workflow_run_id,
                    "evidence.workflow_observations": observation,
                },
            }
            if payload["monitor_id"]:
                incident_update["$addToSet"]["evidence.monitor_ids"] = payload["monitor_id"]
            if payload["evidence_refs"]:
                incident_update["$addToSet"]["evidence.workflow_refs"] = {"$each": payload["evidence_refs"]}
            collection("operational_incidents").update_one(
                {"_id": str(linked_incident["_id"]), "farm_key": farm_key}, incident_update
            )
        except Exception as exc:
            system_logger.exception("datadog_workflow_incident_evidence_persist_failed")
            return JSONResponse(status_code=503, content={"result": "incident_evidence_unavailable", "error": type(exc).__name__})
    if inserted:
        from pages.home import state
        state.setdefault("notifications", []).insert(0, {
            "time": document["time"], "text": message,
            "incident_id": document["incident_id"],
            "event_id": document["event_id"],
            "farm_key": document["farm_key"],
            "severity": document["severity"],
            "workflow_name": document["workflow_name"],
            "workflow_id": document["workflow_id"],
            "workflow_run_id": document["workflow_run_id"],
            "scenario_run_id": document["scenario_run_id"],
            "command_id": document["command_id"],
            "device_id": document["device_id"],
            "node_id": document["node_id"],
            "scenario_code": document["scenario_code"],
            "synthetic": document["synthetic"],
            "workflow_status": document["workflow_status"],
            "monitor_id": document["monitor_id"],
            "decision_code": document["decision_code"],
            "action_code": document["action_code"],
            "verification_status": document["verification_status"],
            "correlation_status": document["correlation_status"],
        })
        state["notifications"] = state["notifications"][:20]
        state["_update_counter"] = state.get("_update_counter", 0) + 1
    return JSONResponse(
        status_code=202 if inserted else 200,
        content={"result": "received" if inserted else "duplicate", "stored": True, "app_bell_updated": inserted},
    )

def _seconds_from_env(name, default):
    try:
        return max(1.0, float(os.getenv(name, str(default))))
    except ValueError:
        return float(default)


if __name__ in {"__main__", "__mp_main__"}:
    from service.session_security import resolve_storage_secret, session_middleware_kwargs
    storage_secret = resolve_storage_secret(os.environ, system_logger)
    ui.run(
        session_middleware_kwargs=session_middleware_kwargs(os.environ),
        title='SMIOT System',
        port=8080,
        favicon='📊',
        reload=False,
        storage_secret=storage_secret,
        reconnect_timeout=_seconds_from_env("SMIOT_RECONNECT_TIMEOUT", 90),
    )
