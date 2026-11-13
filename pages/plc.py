from nicegui import ui, app, run
from pages.home import CUSTOM_CSS, sidebar, state, global_topbar
import json
import re
import time
from datetime import datetime, timezone
from uuid import uuid4

from pages.login import check_login
from service import auth
from service.farm_registry import FARM_KEYS, FARM_KEYS_BY_LABEL, FARM_LABELS
from service.scenario_catalog import scenario_catalog
from components.ui_kit import (
    page_header, panel, sim_badge, status_chip, state_panel, stat, stats,
    fmt_time, fmt_age, as_utc, command_chain, confirm, source_note,
)


_CATALOG = scenario_catalog()
SCENARIO_COUNT = len(_CATALOG)
SCENARIO_OPTIONS = {
    code: f"{code} · {spec.get('title') or spec.get('summary') or spec.get('scenario_type')}"
    for code, spec in _CATALOG.items()
}

PUMP_COUNT = 7
FEEDBACK_FRESH_SECONDS = 60
_BIT_KEY = re.compile(r"^bit([0-6])$")


def _is_demo_admin() -> bool:
    user = app.storage.user
    return user.get("role") == "admin" or "manage_users" in user.get("permissions", [])


def _scenario_is_active() -> bool:
    current = state.get("demo_scenario_control") or {}
    return current.get("status") in {"pending_ack", "started", "running", "stop_pending_ack", "ack_timeout"}


def _a4_drill_active() -> bool:
    """A4 (command without ACK) needs pump commands while it runs; every other drill still blocks them."""
    current = state.get("demo_scenario_control") or {}
    codes = {str(current.get("scenario_code") or "").upper(), str(current.get("scenario_type") or "").upper()}
    return _scenario_is_active() and bool(codes & {"A4", "A4_COMMAND_NO_ACK"})


def _scenario_blocks_pump() -> bool:
    return _scenario_is_active() and not _a4_drill_active()


# ── Farm and access (shared with pages/inverter.py) ────────────────────

def current_farm_key() -> str | None:
    """Farm key of the farm picked in the top bar, resolved on the server."""
    key = FARM_KEYS_BY_LABEL.get(state.get("selected_farm"))
    if key:
        return key
    remembered = app.storage.user.get("current_farm")
    return remembered if remembered in FARM_KEYS else None


def _check_access(user_id, farm_key, perm_keys):
    """Blocking (Mongo). Returns an error text, or None when allowed."""
    if farm_key not in (auth.get_user_farms(user_id) or []):
        return f"Tài khoản không được phép điều khiển {FARM_LABELS.get(farm_key, farm_key)}"
    for perm in perm_keys:
        if not auth.check_permission(user_id, perm):
            return perm
    return None


async def authorize_command(perm_keys, perm_names=None):
    """(user_id, farm_key, error). farm_key comes from the server-side selection."""
    user_id = app.storage.user.get("user_id")
    if not user_id:
        return None, None, "Bạn chưa đăng nhập"
    farm_key = current_farm_key()
    if farm_key is None:
        return user_id, None, "Chưa chọn nhà màng hợp lệ"
    denied = await run.io_bound(_check_access, user_id, farm_key, list(perm_keys))
    if denied is None:
        return user_id, farm_key, None
    if denied in (perm_names or {}):
        return user_id, farm_key, f"Bạn không có quyền: {perm_names[denied]}"
    if denied.endswith("_control") or denied.startswith("inverter_"):
        return user_id, farm_key, f"Bạn không có quyền thực hiện thao tác này ({denied})"
    return user_id, farm_key, denied


# ── Command ledger (shared with pages/inverter.py) ─────────────────────

_ACK_MARKS: dict = {}
_VERIFIED_AT: dict = {}


def _trim(store: dict, limit: int = 400) -> None:
    while len(store) > limit:
        store.pop(next(iter(store)), None)


def _ts(value) -> float:
    stamp = as_utc(value)
    return stamp.timestamp() if stamp else 0.0


def fetch_ledger_docs(farm_key: str, actions: list[str], limit: int = 10):
    """Blocking (Mongo). Newest action_ledger rows of one farm, or None if unreadable."""
    try:
        from service.mongodb_store import collection
        cursor = collection("action_ledger").find(
            {"farm_key": farm_key, "action": {"$in": actions}},
            {"command_id": 1, "action": 1, "state": 1, "requested_at": 1, "published_at": 1,
             "acknowledged_at": 1, "verified_at": 1, "failed_at": 1, "error": 1,
             "updated_at": 1, "created_at": 1, "target": 1},
        ).sort("updated_at", -1).limit(limit)
        return list(cursor)
    except Exception:
        return None


def build_command_rows(farm_key, actuator, docs, live_check, describe, limit=8):
    """Merge in-memory pending records with action_ledger rows of one farm.

    Verified needs evidence read back after the ACK:
      - the ledger says ``verified``; or
      - the device's own farm/status readback for this command matched; or
      - (latest command on the channel only) a newer live sample, seen after this
        command was first seen acknowledged, matches the commanded value.
    An ACK alone is never shown as verified.
    """
    pending = state.get("actuator_pending_by_command") or {}
    records = [(rid, rec) for rid, rec in list(pending.items())
               if rec.get("farm_key") == farm_key and rec.get("actuator") == actuator]
    ledger = {d.get("command_id"): d for d in (docs or []) if d.get("command_id")}
    latest: dict = {}
    for rid, rec in records:
        channel = rec.get("channel")
        if channel not in latest or float(rec.get("requested_at") or 0) >= float(
                pending[latest[channel]].get("requested_at") or 0):
            latest[channel] = rid

    rows = []
    memory_ids = set()
    for rid, rec in records:
        memory_ids.add(rec.get("command_id"))
        led = ledger.get(rec.get("command_id")) or {}
        raw = str(rec.get("status") or "")
        status = "unacknowledged" if raw == "unverified" else raw
        sent_at = rec.get("published_at") or rec.get("requested_at")
        acked_at = rec.get("acknowledged_at")
        verified_at, hint, reason = None, None, None
        if raw == "acknowledged":
            if led.get("state") == "verified":
                status, verified_at = "verified", led.get("verified_at")
            elif rid in _VERIFIED_AT:
                status, verified_at = "verified", _VERIFIED_AT[rid]
            else:
                proven = rec.get("ack_source") == "device_readback" and rec.get("target_matches") is True
                if not proven and latest.get(rec.get("channel")) == rid:
                    token, matches = live_check(rec)
                    mark = _ACK_MARKS.setdefault(rid, token)
                    _trim(_ACK_MARKS)
                    proven = bool(token) and token != mark and bool(matches)
                if proven:
                    _VERIFIED_AT[rid] = time.time()
                    _trim(_VERIFIED_AT)
                    status, verified_at = "verified", _VERIFIED_AT[rid]
                elif rec.get("target_matches") is False:
                    hint = "Bản tin ACK báo trạng thái không khớp lệnh, chưa có số đo xác nhận"
        elif raw in {"pending", "unacknowledged", "unverified"} and led.get("state") == "failed":
            status, reason = "failed", led.get("error") or None
        elif raw == "publish_failed":
            reason = "Không gửi được lệnh tới broker MQTT"
        title, direction = describe(rec, None)
        rows.append({
            "ts": _ts(rec.get("requested_at")), "title": title, "direction": direction,
            "command_id": str(rec.get("command_id") or ""), "status": status,
            "sent_at": sent_at, "acked_at": acked_at, "verified_at": verified_at,
            "verify_hint": hint, "reason": reason,
        })

    for command_id, doc in ledger.items():
        if command_id in memory_ids:
            continue
        title, direction = describe(None, doc)
        rows.append({
            "ts": _ts(doc.get("requested_at") or doc.get("created_at")), "title": title,
            "direction": direction, "command_id": str(command_id),
            "status": doc.get("state"),
            "sent_at": doc.get("published_at") or doc.get("requested_at"),
            "acked_at": doc.get("acknowledged_at"), "verified_at": doc.get("verified_at"),
            "verify_hint": None, "reason": doc.get("error") or None,
        })

    rows.sort(key=lambda row: row["ts"], reverse=True)
    return rows[:limit]


def render_command_rows(rows, empty_title, empty_detail):
    if not rows:
        state_panel("empty", empty_title, empty_detail)
        return
    with ui.element("div").classes("sm-stack").style("gap:0"):
        for row in rows:
            with ui.element("div").style(
                    "padding:10px 0;border-top:1px solid var(--sm-net-soft);width:100%;min-width:0"):
                with ui.element("div").classes("sm-inline"):
                    heading = row["title"] + (f" · {row['direction']}" if row.get("direction") else "")
                    ui.label(heading).style("font-weight:600;font-size:14px;color:var(--sm-ink)")
                    ui.label(row["command_id"]).classes("sm-id")
                command_chain(
                    row["status"], sent_at=row["sent_at"], acked_at=row["acked_at"],
                    verified_at=row["verified_at"], verify_hint=row["verify_hint"], reason=row["reason"],
                )


def rows_signature(rows) -> str:
    return json.dumps(rows, default=str, sort_keys=True)


# ── Pump specifics ─────────────────────────────────────────────────────

def _on(value) -> bool:
    return value in (1, True, "1")


def pump_live_check(rec):
    """(sample token, matches) from the virtual PLC feedback of the command's farm."""
    feedback = state.get("virtual_plc_feedback") or {}
    if feedback.get("farm_key") != rec.get("farm_key"):
        return None, False
    channel = str(rec.get("channel") or "")
    if not re.fullmatch(r"q[0-6]", channel):
        return None, False
    outputs = feedback.get("virtual_output")
    if isinstance(outputs, dict) and f"bit{channel[1:]}" in outputs:
        value = outputs.get(f"bit{channel[1:]}")
    else:
        value = state.get(channel)
    return str(feedback.get("updated_at") or ""), int(_on(value)) == rec.get("target")


def describe_pump(rec, doc):
    if rec:
        channel = str(rec.get("channel") or "")
        number = int(channel[1:]) + 1 if re.fullmatch(r"q\d", channel) else None
        return (f"Bơm {number}" if number else "Bơm", "Bật" if rec.get("target") == 1 else "Tắt")
    action = (doc or {}).get("action")
    if action == "SAFE_STOP":
        return "Dừng an toàn các bơm", None
    return "Đặt đầu ra bơm", None


def plc_gate(farm_key):
    """Whether pump ON commands are allowed, with the reason shown to the operator."""
    if farm_key is None:
        return {"live": False, "can_on": False, "kind": "error",
                "title": "Chưa chọn nhà màng hợp lệ",
                "detail": "Chọn nhà màng ở thanh trên. Lệnh bật bơm đang bị khóa."}
    label = FARM_LABELS.get(farm_key, farm_key)
    feedback = state.get("virtual_plc_feedback") or {}
    if not feedback:
        return {"live": False, "can_on": False, "kind": "empty",
                "title": f"Chưa nhận phản hồi từ PLC ảo của {label}",
                "detail": "Lệnh bật bơm bị khóa cho tới khi có phản hồi. Lệnh tắt vẫn gửi được."}
    if feedback.get("farm_key") != farm_key:
        other = FARM_LABELS.get(feedback.get("farm_key"), feedback.get("farm_key") or "chưa rõ")
        return {"live": False, "can_on": False, "kind": "stale",
                "title": f"Phản hồi PLC ảo gần nhất thuộc {other}, không phải {label}",
                "detail": "Trạng thái bơm trên màn hình chưa phải của nhà màng này. Lệnh bật bơm bị khóa, lệnh tắt vẫn gửi được."}
    if not state.get("plc_online"):
        return {"live": False, "can_on": False, "kind": "error",
                "title": "PLC ảo không trực tuyến",
                "detail": "Lệnh bật bơm bị khóa. Lệnh tắt vẫn gửi được."}
    stamp = as_utc(feedback.get("updated_at"))
    age = (datetime.now(timezone.utc) - stamp).total_seconds() if stamp else None
    if age is None or age > FEEDBACK_FRESH_SECONDS:
        return {"live": False, "can_on": False, "kind": "stale",
                "title": "Phản hồi PLC ảo đã cũ" if age is not None else "Phản hồi PLC ảo không có thời điểm",
                "detail": f"Phản hồi gần nhất: {fmt_age(stamp)}. Lệnh bật bơm bị khóa, lệnh tắt vẫn gửi được."
                          if stamp else "Không xác định được độ mới của phản hồi. Lệnh bật bơm bị khóa."}
    if feedback.get("safe_mode_active") is True:
        return {"live": True, "can_on": False, "kind": "error",
                "title": "Safe mode đang bật",
                "detail": "Lệnh bật bơm bị chặn. Xác minh sự cố và xóa safe mode trước. Lệnh tắt vẫn gửi được."}
    return {"live": True, "can_on": True, "kind": "ok", "title": "", "detail": ""}


def _scenario_note():
    return (f"{SCENARIO_COUNT} tình huống theo nhóm cây trồng, cảm biến, thiết bị, cơ cấu và máy chủ. "
            "Lỗi được mô phỏng; ACK và bằng chứng được ghi theo mã lượt chạy.")


PLC_CSS = """
#plc-root, #plc-root * { font-family: var(--sm-body) !important; }
#plc-root header { display: none !important; }
#plc-root .header-icon-pulse { display: none !important; }
#plc-root .uppercase { text-transform: none !important; }
#plc-root .tracking-widest, #plc-root .tracking-tight { letter-spacing: normal !important; }
#plc-root .font-black, #plc-root .font-extrabold { font-weight: 600 !important; }
#plc-root [class*="shadow"] { box-shadow: none !important; }
#plc-root [class*="rounded"]:not(.rounded-full) { border-radius: var(--sm-r-m) !important; }
#plc-root .rounded-full.border { border-radius: var(--sm-r-s) !important; }
#plc-root .text-slate-800, #plc-root .text-slate-700 { color: var(--sm-ink) !important; }
#plc-root .text-slate-600, #plc-root .text-slate-500 { color: var(--sm-ink-2) !important; }
#plc-root .text-slate-400 { color: var(--sm-ink-3) !important; }
#plc-root .text-green-700, #plc-root .text-green-600, #plc-root .text-green-500 { color: var(--sm-ok) !important; }
#plc-root .text-amber-600, #plc-root .text-amber-500 { color: var(--sm-watch) !important; }
#plc-root .text-red-600, #plc-root .text-red-500, #plc-root .text-red-400 { color: var(--sm-act) !important; }
#plc-root .bg-green-500 { background: var(--sm-ok) !important; }
#plc-root .bg-red-500 { background: var(--sm-act) !important; }
#plc-root .bg-slate-300 { background: var(--sm-net) !important; }
#plc-root .bg-green-50 { background: var(--sm-ok-tint) !important; }
#plc-root .bg-red-50 { background: var(--sm-act-tint) !important; }
#plc-root .border-green-200 { border-color: var(--sm-ok) !important; }
#plc-root .border-red-200 { border-color: var(--sm-act) !important; }
#plc-root .bg-white\\/60 { background: var(--sm-sunken) !important; }
#plc-root .border-gray-100 { border-color: var(--sm-net-soft) !important; }
#plc-root .animate-spin { animation-duration: 1.4s; color: var(--sm-watch) !important; }

.glass-card {
    background: var(--sm-surface);
    border: 1px solid var(--sm-net-soft);
    border-radius: var(--sm-r-l);
    box-shadow: none;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    transition: none;
}
.glass-card:hover { transform: none !important; box-shadow: none !important; border-color: var(--sm-net-soft) !important; }
.card-online-border { border-color: var(--sm-net-soft); }
.card-offline-border { border-color: var(--sm-act); }
.pump-control-grid { display: grid; grid-template-columns: 1fr; gap: 8px; width: 100%; }
@media (min-width: 768px) {
    .pump-control-grid { grid-template-columns: repeat(2, 1fr); gap: 10px; }
    .pump-control-grid > div:nth-child(7) { grid-column: 1 / -1; max-width: calc(50% - 5px); margin: 0 auto; }
}
.pump-row-card {
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
    padding: 12px 14px; min-height: 48px;
    background: var(--sm-surface); border: 1px solid var(--sm-net-soft); border-radius: var(--sm-r-m);
    cursor: pointer; transition: none; user-select: none;
}
.pump-row-card:hover { transform: none; box-shadow: none; border-color: var(--sm-net); }
.pump-row-card:active { transform: none; }
.pump-row-card-on { background: var(--sm-vine-tint); border-color: var(--sm-vine); box-shadow: none; }
.pump-row-card-on:hover { border-color: var(--sm-vine); box-shadow: none; }
.pump-row-card-loading { background: var(--sm-watch-tint); border-color: var(--sm-watch); animation: none; }
.pump-row-card-mismatch { background: var(--sm-act-tint); border-color: var(--sm-act); animation: none; }
.pump-row-card-locked { background: var(--sm-sunken); border-color: var(--sm-net-soft); cursor: not-allowed; opacity: 0.75; }
.pump-row-card-locked:hover { transform: none; box-shadow: none; }
.toggle-track { width: 44px; height: 24px; background: var(--sm-net); border-radius: 12px; position: relative; transition: none; flex-shrink: 0; }
.toggle-knob { width: 18px; height: 18px; background: #fff; border-radius: 50%; position: absolute; top: 3px; left: 3px; transition: none; box-shadow: none; }
.toggle-on { background: var(--sm-vine); }
.toggle-on .toggle-knob { transform: translateX(20px); box-shadow: none; }
.toggle-loading { background: var(--sm-watch-fill); animation: none; }
.toggle-loading .toggle-knob { animation: none; transform: translateX(10px); }
.toggle-mismatch { background: var(--sm-act); animation: none; }
.toggle-mismatch .toggle-knob { background: #fff; transform: translateX(20px); }
.toggle-locked { background: var(--sm-none); opacity: 0.5; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--sm-net); flex-shrink: 0; transition: none; }
.status-dot-active { background: var(--sm-ok); animation: none; }
.status-dot-loading { background: var(--sm-watch-fill); animation: none; }
.status-dot-mismatch { background: var(--sm-act); animation: none; }
.plc-indicator { display: inline-flex; align-items: center; justify-content: center; position: relative; width: 14px; height: 14px; }
.plc-indicator .dot-core { width: 10px; height: 10px; border-radius: 50%; position: relative; z-index: 1; }
.plc-indicator .dot-ping { display: none; }
"""

JS_ERROR_HOOK = """
<script type="text/javascript">
window.onerror = function(message, url, line, column, error) {
    var errorData = { message: message, url: url, line: line, column: column, stack: error ? error.stack : '' };
    fetch('/api/js_error', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(errorData) });
};
window.onunhandledrejection = function(event) {
    var errorData = { message: 'Unhandled Rejection: ' + event.reason, url: window.location.href, line: 0, column: 0,
        stack: event.reason && event.reason.stack ? event.reason.stack : '' };
    fetch('/api/js_error', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(errorData) });
};
</script>
<script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
<script src="https://cdn.tailwindcss.com"></script>
"""


@ui.page('/plc')
def trang_plc():
    if not check_login(): return

    ledger_cache = {"docs": None, "error": False, "loaded": False, "farm": None, "at": 0.0}
    last = {"counter": None, "farm": None, "pushed": None, "ledger_sig": None}

    # --- Dữ liệu đẩy sang React ---
    def push_plc_data():
        farm_key = current_farm_key()
        gate = plc_gate(farm_key)
        pumps = {f"pump{i+1}": int(_on(state.get(f"bit{i}", 0))) for i in range(PUMP_COUNT)}
        permissions = list(app.storage.user.get('permissions', []))
        if not gate["can_on"]:
            # Chỉ còn lệnh tắt: khóa công tắc của các bơm đang tắt (React phát plc_locked_click).
            permissions = [
                p for p in permissions
                if not (re.fullmatch(r"pump_[1-7]_control", p) and pumps.get(f"pump{p.split('_')[1]}", 0) == 0)
            ]
        pending = state.get("plc_pending_cmds") or {}
        data = {
            "pumps": pumps,
            "outputs": {f"q{i}": state.get(f"q{i}", 0) for i in range(PUMP_COUNT)},
            "plc_online": 1 if gate["live"] else 0,
            "loading": {f"pump{i+1}": 1 if (i in pending and pending[i].get("farm_key") == farm_key) else 0
                        for i in range(PUMP_COUNT)},
            "permissions": permissions,
        }
        encoded = json.dumps(data)
        last["pushed"] = encoded
        ui.run_javascript(f'if(window.updatePlcData) window.updatePlcData({encoded});')

    # --- Sổ lệnh ---
    def ledger_rows():
        farm_key = current_farm_key()
        if farm_key is None:
            return []
        docs = ledger_cache["docs"] if ledger_cache["farm"] == farm_key else None
        return build_command_rows(farm_key, "plc_pump", docs, pump_live_check, describe_pump)

    async def load_ledger():
        farm_key = current_farm_key()
        if farm_key is None:
            return
        docs = await run.io_bound(fetch_ledger_docs, farm_key, ["SET_OUTPUTS", "SAFE_STOP"])
        ledger_cache.update(docs=docs or [], error=docs is None, loaded=True,
                            farm=farm_key, at=time.time())

    @ui.refreshable
    def ledger_view():
        rows = ledger_rows()
        if ledger_cache["error"]:
            source_note("Không đọc được sổ lệnh trong cơ sở dữ liệu. Chỉ hiện lệnh đang giữ trong bộ nhớ máy chủ.")
        render_command_rows(
            rows, "Chưa có lệnh bơm nào của nhà màng này",
            "Lệnh bật hoặc tắt bơm sẽ hiện ở đây cùng ba bước: đã gửi, thiết bị ACK, kết quả xác minh.")

    @ui.refreshable
    def status_view():
        farm_key = current_farm_key()
        gate = plc_gate(farm_key)
        feedback = state.get("virtual_plc_feedback") or {}
        mine = bool(farm_key) and feedback.get("farm_key") == farm_key
        on_count = sum(1 for i in range(PUMP_COUNT) if _on(state.get(f"bit{i}", 0))) if mine else None
        safe = feedback.get("safe_mode_active") if mine else None
        with stats():
            stat("PLC ảo", "Trực tuyến" if gate["live"] else "Không trực tuyến",
                 meta="Theo phản hồi mới nhất", level=None if gate["live"] else "act")
            stat("Phản hồi gần nhất", fmt_age(feedback.get("updated_at")) if mine else None,
                 meta=fmt_time(feedback.get("updated_at")) if mine else None)
            stat("Bơm đang bật", f"{on_count}/{PUMP_COUNT}" if on_count is not None else None,
                 meta="Theo phản hồi PLC ảo")
            stat("Safe mode", "Bật" if safe is True else "Tắt" if safe is False else None,
                 level="act" if safe is True else None)
        if gate["kind"] != "ok":
            state_panel(gate["kind"], gate["title"], gate["detail"])
        if _a4_drill_active():
            state_panel("stale", "Đang diễn tập A4: lệnh không có ACK",
                        "Lệnh bơm được phép trong lúc diễn tập A4. Thiết bị sẽ không gửi ACK cho lệnh bơm.")
        elif _scenario_is_active():
            state_panel("stale", "Đang diễn tập lỗi thiết bị",
                        "Dừng diễn tập trước khi điều khiển bơm. Mọi lệnh bơm tạm thời bị chặn.")

    farm_chip_holder = {}

    async def check_plc_ui_update():
        farm_key = current_farm_key()
        counter = state.get("_update_counter", 0)
        changed = counter != last["counter"] or farm_key != last["farm"]
        last["counter"], last["farm"] = counter, farm_key
        if changed:
            chip = farm_chip_holder.get("chip")
            if chip is not None:
                chip.set_text(f"Đang điều khiển: {FARM_LABELS.get(farm_key, 'chưa chọn nhà màng')}")
        stale_ledger = (time.time() - ledger_cache["at"]) > 6 or ledger_cache["farm"] != farm_key
        if changed or stale_ledger:
            await load_ledger()
        status_view.refresh()
        push_plc_data()
        signature = rows_signature(ledger_rows())
        if signature != last["ledger_sig"] or changed:
            last["ledger_sig"] = signature
            ledger_view.refresh()
        if changed:
            client_id = ui.context.client.id
            try:
                from pages.home import client_refreshes
                for refresh_func in client_refreshes.get(client_id, []):
                    try:
                        refresh_func()
                    except Exception:
                        pass
            except ImportError:
                pass

    # --- Timer đồng bộ (cấp page, ngoài mọi container) ---
    t = ui.timer(2.0, check_plc_ui_update)
    ui.context.client.on_disconnect(t.deactivate)

    # --- Event Handlers (React gửi lệnh lên qua ui.on) ---
    async def handle_plc_control(e):
        from service.mqtt import publish_mqtt, prepare_actuator_command
        from service.observability import trace_span

        args = e.args if isinstance(e.args, dict) else {}
        requests = []
        for key, value in args.items():
            match = _BIT_KEY.match(str(key))
            if match and value in (0, 1, True, False, "0", "1"):
                requests.append((int(match.group(1)), int(_on(value))))
        if not requests:
            ui.notify('Lệnh bơm không hợp lệ; không gửi gì tới thiết bị.', color='negative')
            push_plc_data()
            return

        perm_keys = [f"pump_{idx + 1}_control" for idx, _ in requests]
        names = {f"pump_{idx + 1}_control": f"điều khiển Bơm {idx + 1}" for idx, _ in requests}
        user_id, farm_key, error = await authorize_command(perm_keys, names)
        if error:
            ui.notify(error, color='negative')
            push_plc_data()
            return

        if _scenario_blocks_pump():
            ui.notify('Đang diễn tập lỗi thiết bị. Hãy dừng diễn tập trước khi điều khiển bơm.', color='warning')
            push_plc_data()
            return

        wants_on = [idx for idx, value in requests if value == 1]
        if wants_on:
            gate = plc_gate(farm_key)
            if not gate["can_on"]:
                ui.notify(f"{gate['title']}. Không gửi lệnh bật.", color='negative')
                push_plc_data()
                return
            names_on = ", ".join(f"Bơm {idx + 1}" for idx in wants_on)
            ok = await confirm(
                f"Bật {names_on}?",
                f"Lệnh gửi tới PLC ảo của {FARM_LABELS.get(farm_key, farm_key)}. "
                "Thiết bị ACK là một bước, kết quả đọc lại là bước khác; màn hình sẽ tách riêng từng bước.",
                f"Bật {names_on}")
            if not ok:
                push_plc_data()
                return
            # Trạng thái có thể đã đổi trong lúc chờ xác nhận.
            if current_farm_key() != farm_key or not plc_gate(farm_key)["can_on"] or _scenario_is_active():
                ui.notify('Điều kiện an toàn đã thay đổi; lệnh bật chưa được gửi.', color='warning')
                push_plc_data()
                return

        payload = {f"bit{idx}": value for idx, value in requests}
        payload["farm_key"] = farm_key
        try:
            payload = prepare_actuator_command("farm/control", payload, timeout_seconds=10)
        except ValueError:
            ui.notify('Nhà màng không hợp lệ; chưa gửi lệnh.', color='negative')
            push_plc_data()
            return
        with trace_span("smiot.plc.command", resource="farm/control",
                        **{"mqtt.topic": "farm/control", "plc.mode": "ui_demo"}):
            published = publish_mqtt("farm/control", payload)

        if published:
            pending = state.setdefault("plc_pending_cmds", {})
            for idx, value in requests:
                pending[idx] = {
                    "time": time.time(), "target_val": value, "farm_key": farm_key,
                    "command_id": payload.get("command_id"), "ack_deadline": time.time() + 10,
                }
            ui.notify('Đã gửi lệnh. Chờ thiết bị ACK, chưa phải kết quả đã xác minh.', color='info')
        else:
            ui.notify('Không gửi được lệnh tới broker MQTT.', color='negative')

        state["_update_counter"] = state.get("_update_counter", 0) + 1
        push_plc_data()
        ledger_view.refresh()

    ui.on('plc_control', handle_plc_control)

    def handle_plc_locked_click(e):
        args = e.args if isinstance(e.args, dict) else {}
        try:
            pump = int(args.get('pump'))
        except (TypeError, ValueError):
            return
        if not 1 <= pump <= PUMP_COUNT:
            return
        if f"pump_{pump}_control" not in app.storage.user.get('permissions', []):
            ui.notify(f'Tài khoản của bạn không có quyền điều khiển Bơm {pump}.', color='warning', position='top')
            return
        gate = plc_gate(current_farm_key())
        reason = gate["title"] or "Điều kiện an toàn chưa đủ"
        ui.notify(f'Bơm {pump} đang khóa lệnh bật: {reason}. Lệnh tắt vẫn gửi được.', color='warning', position='top')

    ui.on('plc_locked_click', handle_plc_locked_click)
    ui.on('plc_ready', lambda: push_plc_data())

    # --- UI Layout ---
    ui.add_head_html(JS_ERROR_HOOK + "<style>" + CUSTOM_CSS + PLC_CSS + "</style>")
    sidebar('PLC')

    with ui.element("div").classes("main-content"):
        global_topbar("Bơm", "")

        with ui.element("div").classes("content-area"):
            with ui.element("div").classes("sm-stack"):
                slot = page_header(
                    "Bơm",
                    "Bật, tắt 7 bơm của nhà màng đang chọn và theo dõi từng lệnh: đã gửi, thiết bị ACK, kết quả xác minh.")
                with slot:
                    farm_chip_holder["chip"] = status_chip(
                        "info", f"Đang điều khiển: {FARM_LABELS.get(current_farm_key(), 'chưa chọn nhà màng')}")
                    sim_badge()

                status_view()

                with panel("Bảng bơm", "Công tắc gửi lệnh tới bộ mô phỏng PLC. Bật bơm cần xác nhận; tắt bơm gửi ngay."):
                    ui.html('<div id="plc-root" style="width:100%;min-height:360px;"></div>', sanitize=False)

                with panel("Sổ lệnh bơm", "Các lệnh gần nhất của nhà màng đang chọn"):
                    ledger_view()
                    source_note("ACK chỉ cho biết thiết bị ảo đã nhận lệnh. Kết quả chỉ được tính là đã xác minh khi phản hồi đọc lại "
                                "(q0 đến q6 hoặc phản hồi PLC ảo) khớp trạng thái đã lệnh.")

                # Kịch bản diễn tập chỉ dành cho admin, tách khỏi điều khiển bơm.
                if _is_demo_admin():
                    with panel("Diễn tập thiết bị ảo", _scenario_note()):
                        with ui.element("div").classes("sm-inline").style("align-items:flex-end;width:100%"):
                            scenario_select = ui.select(SCENARIO_OPTIONS, value='A1', label='Kịch bản') \
                                .classes('w-full').style('flex:1 1 260px;min-width:0')
                            seed_input = ui.number('Seed lặp lại', value=17, min=0, max=2**31 - 1, precision=0) \
                                .style('flex:0 1 140px;min-width:0')
                        run_state = ui.label('Chưa chạy diễn tập').classes('sm-note').style('margin-top:8px')
                        with ui.element("div").classes("sm-inline").style("margin-top:8px"):
                            start_button = ui.button('Chạy kịch bản').props('unelevated no-caps').classes('sm-btn')
                            stop_button = ui.button('Dừng kịch bản').props('flat no-caps').classes('sm-btn-quiet')
                        feedback_label = ui.label('Phản hồi thiết bị: chưa nhận được').classes('sm-note').style('margin-top:8px')
                        sample_label = ui.label('Mẫu cảm biến sau lệnh: đang chờ bản tin cùng mã diễn tập').classes('sm-note')
                        evidence_label = ui.label('Kết quả phân tích: đang chờ dữ liệu và bằng chứng cần thiết.').classes('sm-note')

                        async def start_scenario():
                            if not _is_demo_admin():
                                ui.notify('Chỉ admin được chạy diễn tập.', color='negative')
                                return
                            if _scenario_is_active():
                                ui.notify('Đã có một diễn tập đang chờ hoặc đang chạy.', color='warning')
                                return
                            farm_key = current_farm_key()
                            if farm_key is None:
                                ui.notify('Chưa chọn nhà màng hợp lệ; chưa gửi lệnh.', color='negative')
                                return
                            code = scenario_select.value
                            if code not in _CATALOG:
                                ui.notify('Kịch bản không hợp lệ.', color='negative')
                                return
                            ok = await confirm(
                                f"Chạy kịch bản {code}?",
                                f"Kịch bản mô phỏng lỗi sẽ chạy trên {FARM_LABELS.get(farm_key, farm_key)} "
                                "và chặn lệnh bơm thủ công cho tới khi dừng.",
                                "Chạy kịch bản")
                            if not ok:
                                return
                            if _scenario_is_active():
                                ui.notify('Đã có một diễn tập đang chờ hoặc đang chạy.', color='warning')
                                return
                            try:
                                from service import mqtt as mqtt_service
                                client = mqtt_service.mqtt_client
                                if not client or not client.is_connected():
                                    ui.notify('MQTT chưa kết nối; chưa gửi lệnh.', color='negative')
                                    return
                                scenario_run_id = f"demo-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
                                command_id = f"cmd-{uuid4()}"
                                payload = {
                                    'action': 'START_SCENARIO',
                                    'scenario_type': code,
                                    'scenario_run_id': scenario_run_id,
                                    'command_id': command_id,
                                    'farm_key': farm_key,
                                    'seed': int(seed_input.value or 17),
                                    'requested_at': datetime.now(timezone.utc).isoformat(),
                                    'requested_by': str(app.storage.user.get('username') or 'admin'),
                                }
                                state['demo_scenario_control'] = {
                                    **payload, 'status': 'pending_ack', 'applied': None,
                                    'message': 'Đã gửi lệnh; đang chờ thiết bị xác nhận.',
                                }
                                mqtt_service.publish_mqtt('farm/demo/control', payload)
                                state['_update_counter'] = state.get('_update_counter', 0) + 1
                                refresh_scenario_status()
                            except Exception as exc:
                                state['demo_scenario_control'] = {
                                    'status': 'send_failed', 'applied': False,
                                    'message': f'Không gửi được lệnh: {type(exc).__name__}',
                                }
                                refresh_scenario_status()
                                ui.notify('Không gửi được lệnh diễn tập.', color='negative')

                        async def stop_scenario():
                            if not _is_demo_admin():
                                ui.notify('Chỉ admin được dừng diễn tập.', color='negative')
                                return
                            current = state.get('demo_scenario_control') or {}
                            if not current.get('scenario_run_id'):
                                ui.notify('Không có diễn tập để dừng.', color='warning')
                                return
                            if current.get('status') in {'stopped', 'rejected', 'send_failed'}:
                                ui.notify('Diễn tập hiện không ở trạng thái có thể dừng.', color='warning')
                                return
                            ok = await confirm(
                                "Dừng kịch bản diễn tập?",
                                f"Gửi lệnh dừng cho lượt chạy {current.get('scenario_run_id')}. "
                                "Thiết bị ảo cần ACK lệnh dừng.",
                                "Dừng kịch bản")
                            if not ok:
                                return
                            try:
                                from service import mqtt as mqtt_service
                                client = mqtt_service.mqtt_client
                                if not client or not client.is_connected():
                                    ui.notify('MQTT chưa kết nối; chưa gửi lệnh dừng.', color='negative')
                                    return
                                command_id = f"cmd-{uuid4()}"
                                payload = {
                                    'action': 'STOP_SCENARIO',
                                    'scenario_run_id': current['scenario_run_id'],
                                    'command_id': command_id,
                                    'farm_key': current.get('farm_key', 'greenhouse_a'),
                                    'requested_at': datetime.now(timezone.utc).isoformat(),
                                    'requested_by': str(app.storage.user.get('username') or 'admin'),
                                }
                                current.update({'status': 'stop_pending_ack', 'stop_command_id': command_id,
                                                'stop_requested_at': payload['requested_at'],
                                                'message': 'Đã gửi lệnh dừng; đang chờ thiết bị xác nhận.'})
                                state['demo_scenario_control'] = current
                                mqtt_service.publish_mqtt('farm/demo/control', payload)
                                state['_update_counter'] = state.get('_update_counter', 0) + 1
                                refresh_scenario_status()
                            except Exception as exc:
                                ui.notify(f'Không gửi được lệnh dừng ({type(exc).__name__}).', color='negative')

                        start_button.on('click', start_scenario)
                        stop_button.on('click', stop_scenario)

                        def refresh_scenario_status():
                            current = state.get('demo_scenario_control') or {}
                            status = current.get('status', 'idle')
                            requested_at = current.get('stop_requested_at') if status == 'stop_pending_ack' else current.get('requested_at')
                            waiting_seconds = None
                            if requested_at and status in {'pending_ack', 'stop_pending_ack'}:
                                try:
                                    requested_dt = datetime.fromisoformat(str(requested_at).replace('Z', '+00:00'))
                                    waiting_seconds = max(0, (datetime.now(timezone.utc) - requested_dt).total_seconds())
                                except (TypeError, ValueError):
                                    waiting_seconds = None
                            message = current.get('message') or {
                                'started': 'Thiết bị đã ACK: kịch bản đang chạy.',
                                'running': 'Thiết bị xác nhận kịch bản đang chạy.',
                                'stopped': 'Thiết bị đã ACK dừng kịch bản.',
                                'rejected': 'Thiết bị từ chối lệnh.',
                                'pending_ack': 'Đã gửi lệnh; đang chờ ACK của thiết bị.',
                                'stop_pending_ack': 'Đã gửi lệnh dừng; đang chờ ACK của thiết bị.',
                            }.get(status, 'Chưa chạy diễn tập.')
                            if waiting_seconds is not None and waiting_seconds >= 15:
                                message = ('Chưa nhận ACK sau 15 giây; trạng thái thiết bị chưa xác định. '
                                           'Không coi lệnh là đã áp dụng.')
                            run_id = current.get('scenario_run_id')
                            scenario_name = SCENARIO_OPTIONS.get(
                                current.get('scenario_code') or current.get('scenario_type'),
                                current.get('scenario_type', ''),
                            )
                            suffix = f" · {scenario_name}" if scenario_name else ''
                            if run_id:
                                suffix += f" · {run_id}"
                            if current.get('applied') is True:
                                suffix += ' · thiết bị đã áp dụng'
                            elif current.get('applied') is False:
                                suffix += ' · không được áp dụng'
                            run_state.set_text(f'{message}{suffix}')
                            observation = (state.get('demo_scenario_observation_by_run') or {}).get(run_id)
                            if observation:
                                result_text = observation.get('status') or 'unknown'
                                result_text += f" · {observation.get('response') or 'HOLD'}"
                                if observation.get('reason'):
                                    result_text += f" · {observation['reason']}"
                                evidence_label.set_text(f'Kết quả phân tích mô phỏng: {result_text}')
                            active = _scenario_is_active() or status == 'stop_pending_ack'
                            start_button.set_enabled(not active)
                            stop_button.set_enabled(bool(run_id) and status not in {'stopped', 'rejected', 'send_failed'})
                            feedback = state.get('virtual_plc_feedback') or {}
                            if feedback:
                                outputs = feedback.get('virtual_output') or {
                                    f'bit{i}': feedback.get(f'bit{i}', feedback.get(f'q{i}', 0)) for i in range(7)
                                }
                                pumps_on = sum(1 for i in range(7) if outputs.get(f'bit{i}', 0) in (1, True, '1'))
                                safe = feedback.get('safe_mode_active')
                                valve = feedback.get('valve_state')
                                vent_cmd, vent_state = feedback.get('vent_cmd'), feedback.get('vent_state')
                                text = f"Phản hồi thiết bị: {pumps_on}/7 bơm đang bật"
                                text += f" · Van: {'mở' if valve == 1 else 'đóng' if valve == 0 else 'chưa rõ'}"
                                text += f" · Quạt: lệnh {vent_cmd if vent_cmd is not None else '—'} / thực tế {vent_state if vent_state is not None else '—'}"
                                text += f" · Safe mode: {'bật' if safe else 'tắt' if safe is False else 'chưa rõ'}"
                                if feedback.get('fault'):
                                    text += f" · Lỗi: {feedback['fault']}"
                                feedback_label.set_text(text)
                            first_sample = state.get('demo_scenario_first_sample') or {}
                            if run_id and first_sample.get('scenario_run_id') == run_id:
                                sample_time = first_sample.get('timestamp') or first_sample.get('received_at') or 'thời điểm chưa rõ'
                                sample_value = first_sample.get('soil_humidity')
                                if sample_value is None:
                                    node_data = first_sample.get('id6') or {}
                                    sample_value = (node_data.get('node2') or {}).get('sh')
                                sample_label.set_text(
                                    f"Mẫu đầu tiên sau lệnh: {sample_value if sample_value is not None else 'đã nhận'}"
                                    f" · {sample_time}"
                                )

                        status_timer = ui.timer(1.0, refresh_scenario_status)
                        ui.context.client.on_disconnect(status_timer.deactivate)
                        refresh_scenario_status()

    # Load React Script (dùng Babel.transform inline để tránh xung đột với NiceGUI scripts)
    try:
        with open('static/test_plc.html', 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r'<script type="text/babel">(.*?)</script>', content, re.DOTALL)
            if match:
                react_code = match.group(1)
                react_code = react_code.replace("document.getElementById('root')", "document.getElementById('plc-root')")
                # Dùng json.dumps để escape an toàn thành chuỗi JS (tránh lỗi backtick/template literal)
                safe_code = json.dumps(react_code)
                ui.add_body_html(f'''<script type="text/javascript">
(function() {{
    function initPlc() {{
        if (window.Babel && window.React && window.ReactDOM && document.getElementById('plc-root')) {{
            try {{
                var _code = {safe_code};
                var _out = Babel.transform(_code, {{ presets: [["react", {{ "runtime": "classic" }}]] }}).code;
                var _script = document.createElement('script');
                _script.textContent = _out;
                document.body.appendChild(_script);
                console.log('[PLC] React component initialized successfully!');
            }} catch(e) {{
                console.error('[PLC] Babel transform error:', e);
            }}
        }} else {{
            setTimeout(initPlc, 50);
        }}
    }}
    initPlc();
}})();
</script>''')
    except Exception as e:
        print(f"Error loading PLC React: {e}")

    push_plc_data()
