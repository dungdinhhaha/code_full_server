from service.observability import initialize_tracing

initialize_tracing()

from nicegui import ui, app
from pathlib import Path
import asyncio
import json
import os
import secrets
import subprocess
import sys
import threading

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

# ── 1. Thêm Middleware Access Log ──
from service.middleware import AccessLogMiddleware
app.add_middleware(AccessLogMiddleware)

# ── 2. Cấu hình Global Exception Handler (Bắt mọi lỗi gửi qua Telegram) ──
import sys
import threading
import traceback
from datetime import datetime
from fastapi.responses import JSONResponse
from fastapi.responses import Response
from fastapi import Request
from service.logger import get_logger

system_logger = get_logger("SYSTEM")
_recovery_clear_lock = threading.Lock()

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

if __name__ in {"__main__", "__mp_main__"}:
    storage_secret = os.getenv("NICEGUI_STORAGE_SECRET")
    if not storage_secret:
        if os.getenv("APP_ENV", "development").lower() == "production":
            raise RuntimeError("NICEGUI_STORAGE_SECRET must be configured in production")
        storage_secret = secrets.token_urlsafe(48)
    ui.run(
        title='SMIOT System',
        port=8080,
        favicon='📊',
        reload=False,
        storage_secret=storage_secret
    )
