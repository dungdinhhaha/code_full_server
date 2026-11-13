from nicegui import ui, app, run
from pages.home import CUSTOM_CSS, sidebar, state, global_topbar
from pages.login import check_login
from service import auth
from service.farm_registry import FARM_LABELS
import re
import time
import json
import math
from datetime import datetime
from service.logger import get_logger
from components.ui_kit import (
    page_header, panel, sim_badge, status_chip, state_panel, stat, stats,
    fmt_num, confirm, source_note,
)
from pages.plc import (
    current_farm_key, authorize_command, fetch_ledger_docs, build_command_rows,
    render_command_rows, rows_signature, JS_ERROR_HOOK,
)

logger = get_logger("INVERTER")

COOLDOWN_SECONDS = 30
MODE_LABELS = {"manual": "Thủ công", "auto": "Tự động"}


def _updated_text(value) -> str:
    """Moc cap nhat dang doc duoc theo gio Viet Nam; chuoi da la HH:MM:SS thi giu nguyen, khong in ISO tho."""
    text = str(value or "").strip()
    if len(text) == 8 and text[2] == ":" and text[5] == ":":
        return text
    from components.ui_kit import fmt_time
    shown = fmt_time(text)
    return text if shown == "chưa có" else shown


@app.get('/api/inverter')
def get_inverter_api():
    return {
        "inverter_status": state.get("inv_status", 0),
        "actual_pressure": state.get("inv_p_cur", 0.0),
        "set_pressure": state.get("inv_p_set", 0.0),
        "input_voltage": state.get("inv_v_in", 0.0),
        "input_current": state.get("inv_i_in", 0.0),
        "output_voltage": state.get("inv_v_out", 0.0),
        "output_current": state.get("inv_i_out", 0.0),
        "frequency": state.get("inv_hz", 0.0),
        "pid_gain": state.get("inv_kp", 0.0),
        "pid_integral": state.get("inv_ki", 0.0),
        "pid_derivative": state.get("inv_kd", 0.0),
        "plc_q7": state.get("q7", 0),
    }


def _on(value) -> bool:
    return value in (1, True, "1")


def inverter_gate(farm_key):
    """Whether the inverter can be started now, with the reason shown to the operator."""
    if farm_key is None:
        return {"live": False, "can_start": False, "kind": "error",
                "title": "Chưa chọn nhà màng hợp lệ",
                "detail": "Chọn nhà màng ở thanh trên. Lệnh chạy biến tần bị khóa."}
    label = FARM_LABELS.get(farm_key, farm_key)
    owner = state.get("_inverter_state_farm")
    if owner and owner != farm_key:
        other = FARM_LABELS.get(owner, owner)
        return {"live": False, "can_start": False, "kind": "stale",
                "title": f"Số liệu biến tần gần nhất thuộc {other}, không phải {label}",
                "detail": "Giá trị trên màn hình chưa phải của nhà màng này. Lệnh chạy biến tần bị khóa, lệnh dừng vẫn gửi được."}
    if not _on(state.get("inv_online", 1)):
        return {"live": False, "can_start": False, "kind": "error",
                "title": f"Biến tần của {label} không trực tuyến",
                "detail": "Lệnh chạy biến tần và đồng bộ PID bị khóa. Lệnh dừng vẫn gửi được."}
    return {"live": True, "can_start": True, "kind": "ok", "title": "", "detail": ""}


def inverter_live_check(rec):
    """(sample token, matches) from the latest inverter sample of the command's farm."""
    if state.get("_inverter_state_farm") != rec.get("farm_key"):
        return None, False
    token = str(state.get("inv_updated") or "")
    target = rec.get("target")
    status = int(_on(state.get("inv_status", 0)))
    try:
        hz = float(state.get("inv_hz") or 0)
    except (TypeError, ValueError):
        hz = 0.0
    if target == 1:
        matches = status == 1 and hz > 0 and _on(state.get("inv_online", 1))
    else:
        matches = status == 0
    return token, matches


def describe_inverter(rec, doc):
    if rec:
        return "Biến tần", "Chạy" if rec.get("target") == 1 else "Dừng"
    return "Đặt biến tần", None


def _finite_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


INVERTER_CSS = """
#inverter-root, #inverter-root * { font-family: var(--sm-body) !important; }
#inverter-root header { display: none !important; }
#inverter-root .uppercase { text-transform: none !important; }
#inverter-root .tracking-widest, #inverter-root .tracking-tight { letter-spacing: normal !important; }
#inverter-root .font-black, #inverter-root .font-extrabold { font-weight: 600 !important; }
#inverter-root [class*="shadow"] { box-shadow: none !important; }
#inverter-root [class*="rounded"]:not(.rounded-full) { border-radius: var(--sm-r-m) !important; }
#inverter-root .transition-all, #inverter-root .transition-colors, #inverter-root .transition-transform { transition: none !important; }
#inverter-root .hover\\:scale-110:hover, #inverter-root .active\\:scale-90:active { transform: none !important; }
#inverter-root .text-slate-800 { color: var(--sm-ink) !important; }
#inverter-root .text-slate-600, #inverter-root .text-slate-500 { color: var(--sm-ink-2) !important; }
#inverter-root .text-slate-400, #inverter-root .text-slate-300, #inverter-root .text-gray-400 { color: var(--sm-ink-3) !important; }
#inverter-root .text-primary { color: var(--sm-vine) !important; }
#inverter-root .text-success { color: var(--sm-ok) !important; }
#inverter-root .text-danger { color: var(--sm-ink-2) !important; }
#inverter-root .text-amber-600, #inverter-root .text-amber-500, #inverter-root .text-yellow-500 { color: var(--sm-vine) !important; }
#inverter-root .text-cyan-600, #inverter-root .text-cyan-500 { color: var(--sm-info) !important; }
#inverter-root .bg-primary { background: var(--sm-vine) !important; }
#inverter-root .bg-success { background: var(--sm-ok) !important; }
#inverter-root .bg-primary\\/10, #inverter-root .bg-success\\/10 { background: var(--sm-vine-tint) !important; }
#inverter-root .bg-danger\\/10 { background: var(--sm-none-tint) !important; }
#inverter-root .border-primary, #inverter-root .border-primary\\/20 { border-color: var(--sm-vine) !important; }
#inverter-root .bg-amber-400, #inverter-root .bg-amber-500 { background: var(--sm-vine) !important; }
#inverter-root .bg-amber-100 { background: var(--sm-vine-tint) !important; }
#inverter-root .bg-cyan-500 { background: var(--sm-info) !important; }
#inverter-root .bg-cyan-100 { background: var(--sm-info-tint) !important; }
#inverter-root .bg-slate-800, #inverter-root .bg-slate-900 { background: var(--sm-vine) !important; }
#inverter-root .bg-gray-300, #inverter-root .bg-gray-200 { background: var(--sm-net) !important; }
#inverter-root .bg-gray-100, #inverter-root .bg-gray-50, #inverter-root .bg-slate-50 { background: var(--sm-sunken) !important; }
#inverter-root .bg-\\[\\#f8fafc\\], #inverter-root .bg-\\[\\#fffbeb\\] { background: var(--sm-sunken) !important; }
#inverter-root .border-gray-100, #inverter-root .border-gray-100\\/80, #inverter-root .border-gray-200,
#inverter-root .border-slate-100, #inverter-root .border-amber-100, #inverter-root .border-white { border-color: var(--sm-net-soft) !important; }
#inverter-root .border-slate-300 { border-color: var(--sm-net) !important; }
#inverter-root .recharts-area-curve { stroke: var(--sm-vine) !important; }
#inverter-root linearGradient stop { stop-color: var(--sm-vine) !important; }
#inverter-root .recharts-cartesian-grid line { stroke: var(--sm-net-soft) !important; }
#inverter-root .recharts-text, #inverter-root .recharts-cartesian-axis-tick-value { fill: var(--sm-ink-3) !important; }

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
.progress-bar::after { display: none; }
.hz-glow { animation: none; background: var(--sm-watch-tint) !important; border-color: var(--sm-net) !important; }
"""


@ui.page('/inverter')
def trang_inverter():
    if not check_login(): return

    ledger_cache = {"docs": None, "error": False, "farm": None, "at": 0.0}
    mode_cache = {"farm": None, "mode": "manual", "at": 0.0}
    last = {"counter": None, "farm": None, "push_sig": None, "ledger_sig": None}
    farm_chip_holder = {}

    def cached_mode(farm_key):
        return mode_cache["mode"] if mode_cache["farm"] == farm_key else "manual"

    # --- Dữ liệu đẩy sang React ---
    def push_inverter_data(force=False):
        farm_key = current_farm_key()
        gate = inverter_gate(farm_key)
        running = _on(state.get("inv_locked")) or _on(state.get("inv_status"))
        permissions = list(app.storage.user.get('permissions', []))
        if not gate["can_start"] and not running:
            permissions = [p for p in permissions if p != "inverter_toggle_control"]
        if not gate["live"]:
            permissions = [p for p in permissions if p != "inverter_send_data"]
        data = {
            "inverter_status": state.get("inv_status", 0),
            "actual_pressure": state.get("inv_p_cur", 0.0),
            "set_pressure": state.get("inv_p_set", 0.0),
            "input_voltage": state.get("inv_v_in", 0.0),
            "input_current": state.get("inv_i_in", 0.0),
            "output_voltage": state.get("inv_v_out", 0.0),
            "output_current": state.get("inv_i_out", 0.0),
            "frequency": state.get("inv_hz", 0.0),
            "pid_gain": state.get("inv_kp", 0.0),
            "pid_integral": state.get("inv_ki", 0.0),
            "pid_derivative": state.get("inv_kd", 0.0),
            "plc_q7": state.get("q7", 0),
            "online": 1 if gate["live"] else 0,
            "is_locked": state.get("inv_locked", False),
            "cooldown": max(0, COOLDOWN_SECONDS - int(time.time() - state.get("inv_lock_time", 0))) if state.get("inv_lock_time") else 0,
            "mode": cached_mode(farm_key),
            "permissions": permissions,
        }
        ui.run_javascript(f'if(window.updateInverterData) window.updateInverterData({json.dumps(data)});')

    def lock_signature():
        farm_key = current_farm_key()
        gate = inverter_gate(farm_key)
        return json.dumps([farm_key, gate["kind"], cached_mode(farm_key),
                           bool(state.get("inv_locked")), state.get("inv_status")], default=str)

    # --- Sổ lệnh ---
    def ledger_rows():
        farm_key = current_farm_key()
        if farm_key is None:
            return []
        docs = ledger_cache["docs"] if ledger_cache["farm"] == farm_key else None
        return build_command_rows(farm_key, "inverter", docs, inverter_live_check, describe_inverter)

    async def load_ledger():
        farm_key = current_farm_key()
        if farm_key is None:
            return
        docs = await run.io_bound(fetch_ledger_docs, farm_key, ["SET_INVERTER"])
        ledger_cache.update(docs=docs or [], error=docs is None, farm=farm_key, at=time.time())

    async def load_mode():
        farm_key = current_farm_key()
        if farm_key is None:
            return
        try:
            mode = await run.io_bound(auth.get_inverter_mode, farm_key)
        except Exception:
            mode = "manual"
        mode_cache.update(farm=farm_key, mode=mode if mode in MODE_LABELS else "manual", at=time.time())

    @ui.refreshable
    def ledger_view():
        if ledger_cache["error"]:
            source_note("Không đọc được sổ lệnh trong cơ sở dữ liệu. Chỉ hiện lệnh đang giữ trong bộ nhớ máy chủ.")
        render_command_rows(
            ledger_rows(), "Chưa có lệnh biến tần nào của nhà màng này",
            "Lệnh chạy hoặc dừng biến tần sẽ hiện ở đây cùng ba bước: đã gửi, thiết bị ACK, kết quả xác minh.")

    @ui.refreshable
    def status_view():
        farm_key = current_farm_key()
        gate = inverter_gate(farm_key)
        mine = state.get("_inverter_state_farm") == farm_key
        running = _on(state.get("inv_status")) if mine else None
        with stats():
            stat("Biến tần", "Trực tuyến" if gate["live"] else "Không trực tuyến",
                 meta="Theo bản tin mới nhất", level=None if gate["live"] else "act")
            stat("Trạng thái chạy", None if running is None else ("Đang chạy" if running else "Đang dừng"),
                 meta=f"Cập nhật {_updated_text(state.get('inv_updated'))}" if mine and state.get("inv_updated") else None)
            stat("Tần số", fmt_num(state.get("inv_hz")) if mine else None, "Hz")
            stat("Áp suất thực tế", fmt_num(state.get("inv_p_cur"), 2) if mine else None, "bar",
                 meta=f"Đặt {fmt_num(state.get('inv_p_set'), 2)} bar" if mine and fmt_num(state.get("inv_p_set"), 2) else None)
            stat("Chế độ", MODE_LABELS.get(cached_mode(farm_key), "Thủ công"),
                 meta="Tự động: lịch tưới điều khiển" if cached_mode(farm_key) == "auto" else "Chạy và dừng bằng tay")
        if gate["kind"] != "ok":
            state_panel(gate["kind"], gate["title"], gate["detail"])

    async def check_ui_update():
        farm_key = current_farm_key()
        counter = state.get("_update_counter", 0)
        changed = counter != last["counter"] or farm_key != last["farm"]
        last["counter"], last["farm"] = counter, farm_key
        if changed:
            chip = farm_chip_holder.get("chip")
            if chip is not None:
                chip.set_text(f"Đang điều khiển: {FARM_LABELS.get(farm_key, 'chưa chọn nhà màng')}")
        if changed or mode_cache["farm"] != farm_key or time.time() - mode_cache["at"] > 10:
            await load_mode()
        if changed or ledger_cache["farm"] != farm_key or time.time() - ledger_cache["at"] > 6:
            await load_ledger()
        status_view.refresh()
        signature = lock_signature()
        if changed or signature != last["push_sig"]:
            last["push_sig"] = signature
            push_inverter_data()
        rows_sig = rows_signature(ledger_rows())
        if changed or rows_sig != last["ledger_sig"]:
            last["ledger_sig"] = rows_sig
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
    t = ui.timer(2.0, check_ui_update)
    ui.context.client.on_disconnect(t.deactivate)

    # --- Event Handlers ---
    async def handle_inverter_control(e):
        from service.mqtt import publish_mqtt, prepare_actuator_command

        args = e.args if isinstance(e.args, dict) else {}
        if args.get("bit") not in (0, 1, True, False, "0", "1"):
            ui.notify('Lệnh biến tần không hợp lệ; không gửi gì tới thiết bị.', color='negative')
            push_inverter_data()
            return
        bit_val = int(_on(args.get("bit")))

        user_id, farm_key, error = await authorize_command(
            ["inverter_toggle_control"], {"inverter_toggle_control": "bật hoặc tắt biến tần"})
        if error:
            ui.notify(error, color='negative')
            push_inverter_data()
            return

        mode = await run.io_bound(auth.get_inverter_mode, farm_key)
        if mode == "auto":
            ui.notify('Đang ở chế độ Tự động; chuyển sang Thủ công trước khi điều khiển tay.', color='warning')
            push_inverter_data()
            return

        def cooldown_left():
            return COOLDOWN_SECONDS - (time.time() - state.get("inv_lock_time", 0))

        if cooldown_left() > 0:
            logger.warning("[MANUAL] Lệnh bị bỏ qua do đang trong thời gian chờ 30s")
            ui.notify(f'Vừa có lệnh biến tần; chờ {int(cooldown_left()) + 1} giây rồi gửi lại.', color='warning')
            push_inverter_data()
            return

        if bit_val == 1:
            gate = inverter_gate(farm_key)
            if not gate["can_start"]:
                ui.notify(f"{gate['title']}. Không gửi lệnh chạy.", color='negative')
                push_inverter_data()
                return
            ok = await confirm(
                "Chạy biến tần?",
                f"Lệnh gửi tới biến tần ảo của {FARM_LABELS.get(farm_key, farm_key)}. "
                "Thiết bị có tối đa 120 giây để ACK; ACK và kết quả đọc lại được hiện riêng trong sổ lệnh.",
                "Chạy biến tần")
            if not ok:
                push_inverter_data()
                return
            if (current_farm_key() != farm_key or not inverter_gate(farm_key)["can_start"]
                    or cooldown_left() > 0):
                ui.notify('Điều kiện an toàn đã thay đổi; lệnh chạy chưa được gửi.', color='warning')
                push_inverter_data()
                return

        try:
            payload = prepare_actuator_command("farm/inverter", {
                "device_name": "Inverter", "bit": bit_val, "farm_key": farm_key,
            }, timeout_seconds=120)
        except ValueError:
            ui.notify('Nhà màng không hợp lệ; chưa gửi lệnh.', color='negative')
            push_inverter_data()
            return

        logger.info(f"[{mode.upper()}] Gửi lệnh điều khiển Inverter: bit={bit_val} bởi UserID={user_id}")
        published = publish_mqtt("farm/inverter", payload)
        if published:
            now = time.time()
            state["inv_locked"] = (bit_val == 1)
            state["inv_lock_time"] = now
            # Giữ chỉ báo cũ của giao diện, vẫn gắn mã lệnh và farm.
            state["inv_pending_cmd"] = {
                "time": now, "target_bit": bit_val,
                "farm_key": farm_key, "command_id": payload.get("command_id"),
                "ack_deadline": now + 120,
            }
            ui.notify('Đã gửi lệnh. Chờ thiết bị ACK, chưa phải kết quả đã xác minh.', color='info')
        else:
            ui.notify('Không gửi được lệnh tới broker MQTT.', color='negative')
        state["_update_counter"] = state.get("_update_counter", 0) + 1
        push_inverter_data()
        ledger_view.refresh()

    ui.on('inverter_control', handle_inverter_control)

    async def handle_mode_change(e):
        args = e.args if isinstance(e.args, dict) else {}
        new_mode = args.get("mode")
        if new_mode not in MODE_LABELS:
            ui.notify('Chế độ không hợp lệ.', color='negative')
            push_inverter_data()
            return

        user_id, farm_key, error = await authorize_command(
            ["inverter_change_mode"], {"inverter_change_mode": "đổi chế độ tự động hóa"})
        if error:
            ui.notify(error, color='negative')
            push_inverter_data()
            return

        current = await run.io_bound(auth.get_inverter_mode, farm_key)
        if current == new_mode:
            push_inverter_data()
            return
        ok = await confirm(
            f"Chuyển sang chế độ {MODE_LABELS[new_mode]}?",
            f"Áp dụng cho {FARM_LABELS.get(farm_key, farm_key)}. "
            + ("Ở chế độ Tự động, biến tần chạy theo lịch tưới và nút chạy, dừng tay bị khóa."
               if new_mode == "auto" else
               "Ở chế độ Thủ công, lịch tưới không còn tự điều khiển biến tần."),
            f"Chuyển sang {MODE_LABELS[new_mode]}")
        if not ok:
            push_inverter_data()
            return
        if current_farm_key() != farm_key:
            ui.notify('Nhà màng đã đổi trong lúc chờ xác nhận; chưa đổi chế độ.', color='warning')
            push_inverter_data()
            return
        await run.io_bound(auth.set_inverter_mode, farm_key, new_mode)
        mode_cache.update(farm=farm_key, mode=new_mode, at=time.time())
        logger.info(f"Đổi chế độ biến tần {farm_key} -> {new_mode} bởi UserID={user_id}")
        ui.notify(f'Đã chuyển sang chế độ {MODE_LABELS[new_mode]}', color='info')
        state["_update_counter"] = state.get("_update_counter", 0) + 1
        push_inverter_data()

    ui.on('inverter_mode_change', handle_mode_change)

    async def handle_inverter_pid_sync(e):
        from service.mqtt import publish_mqtt

        args = e.args if isinstance(e.args, dict) else {}
        values = {name: _finite_float(args.get(name)) for name in ("kp", "ki", "kd", "p_set")}
        if any(v is None for v in values.values()):
            ui.notify('Giá trị PID hoặc áp suất đặt không hợp lệ; chưa gửi.', color='negative')
            push_inverter_data()
            return

        user_id, farm_key, error = await authorize_command(
            ["inverter_send_data"], {"inverter_send_data": "gửi dữ liệu PID xuống biến tần"})
        if error:
            ui.notify(error, color='negative')
            push_inverter_data()
            return
        mode = await run.io_bound(auth.get_inverter_mode, farm_key)
        if mode == "auto":
            ui.notify('Đang ở chế độ Tự động; chuyển sang Thủ công trước khi đồng bộ PID.', color='warning')
            push_inverter_data()
            return
        gate = inverter_gate(farm_key)
        if not gate["live"]:
            ui.notify(f"{gate['title']}. Không gửi PID.", color='negative')
            push_inverter_data()
            return

        ok = await confirm(
            "Đồng bộ PID xuống biến tần?",
            f"Kp {values['kp']:g}, Ki {values['ki']:g}, Kd {values['kd']:g}, áp suất đặt {values['p_set']:g} bar, "
            f"cho {FARM_LABELS.get(farm_key, farm_key)}. Bản tin PID không có mã lệnh nên chưa có ACK để đối chiếu.",
            "Gửi PID")
        if not ok:
            push_inverter_data()
            return
        if current_farm_key() != farm_key or not inverter_gate(farm_key)["live"]:
            ui.notify('Điều kiện đã thay đổi; PID chưa được gửi.', color='warning')
            push_inverter_data()
            return

        # Giữ nguyên cấu trúc bản tin farm/pid mà bên nhận hiện đang đọc.
        payload = {
            "_id": "6a02c8afac8cd4d05a47cb45",
            "id": 17833,
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "device_name": "Inverter",
            "online": state.get("inv_online", 1),
            "status": state.get("inv_status", 0),
            "hz": state.get("inv_hz", 0),
            "p_set": values["p_set"],
            "p_cur": state.get("inv_p_cur", 0),
            "v_out": state.get("inv_v_out", 0),
            "i_out": state.get("inv_i_out", 0),
            "v_in": state.get("inv_v_in", 241.77),
            "i_in": state.get("inv_i_in", 0),
            "kp": values["kp"],
            "ki": values["ki"],
            "kd": values["kd"],
        }
        logger.info(f"Đồng bộ PID xuống Inverter {farm_key} bởi UserID={user_id}: kp={values['kp']} ki={values['ki']} kd={values['kd']} p_set={values['p_set']}")
        if publish_mqtt("farm/pid", payload):
            ui.notify('Đã gửi PID xuống biến tần. Chưa có ACK từ thiết bị cho bản tin này.', color='info')
        else:
            ui.notify('Không gửi được PID tới broker MQTT.', color='negative')
        push_inverter_data()

    ui.on('inverter_pid_sync', handle_inverter_pid_sync)

    # --- UI Layout ---
    ui.add_head_html(
        JS_ERROR_HOOK
        + '<script src="https://unpkg.com/prop-types@15.7.2/prop-types.min.js"></script>'
        + '<script src="https://cdnjs.cloudflare.com/ajax/libs/recharts/2.1.12/Recharts.min.js"></script>'
        + "<style>" + CUSTOM_CSS + INVERTER_CSS + "</style>"
    )

    sidebar(active="Inverter")

    with ui.element("div").classes("main-content"):
        global_topbar("Biến tần", "")
        with ui.element("div").classes("content-area"):
            with ui.element("div").classes("sm-stack"):
                slot = page_header(
                    "Biến tần",
                    "Chạy, dừng biến tần và chỉnh PID của nhà màng đang chọn; theo dõi từng lệnh: đã gửi, thiết bị ACK, kết quả xác minh.")
                with slot:
                    farm_chip_holder["chip"] = status_chip(
                        "info", f"Đang điều khiển: {FARM_LABELS.get(current_farm_key(), 'chưa chọn nhà màng')}")
                    sim_badge()

                status_view()

                with panel("Bảng biến tần", "Chạy và dừng cần bước xác nhận khi chạy; đổi chế độ và đồng bộ PID đều hỏi lại."):
                    ui.html('<div id="inverter-root" style="width:100%;min-height:420px;"></div>', sanitize=False)

                with panel("Sổ lệnh biến tần", "Các lệnh gần nhất của nhà màng đang chọn"):
                    ledger_view()
                    source_note("ACK chỉ cho biết biến tần ảo đã nhận lệnh. Kết quả chỉ được tính là đã xác minh khi trạng thái chạy "
                                "và tần số đọc lại sau ACK khớp lệnh. Bản tin PID không có ACK.")

    # Load React Script (dùng Babel.transform inline để tránh xung đột với NiceGUI scripts)
    try:
        with open('static/test_inverter.html', 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r'<script type="text/babel">(.*?)</script>', content, re.DOTALL)
            if match:
                react_code = match.group(1)
                react_code = react_code.replace("document.getElementById('root')", "document.getElementById('inverter-root')")
                # Dùng json.dumps để escape an toàn thành chuỗi JS (tránh lỗi backtick/template literal)
                safe_code = json.dumps(react_code)
                ui.add_body_html(f'''<script type="text/javascript">
(function() {{
    function initInverter() {{
        if (window.Babel && window.React && window.ReactDOM && window.Recharts && document.getElementById('inverter-root')) {{
            try {{
                var _code = {safe_code};
                var _out = Babel.transform(_code, {{ presets: [["react", {{ "runtime": "classic" }}]] }}).code;
                var _script = document.createElement('script');
                _script.textContent = _out;
                document.body.appendChild(_script);
                console.log('[Inverter] React component initialized successfully!');
            }} catch(e) {{
                console.error('[Inverter] Babel transform error:', e);
            }}
        }} else {{
            setTimeout(initInverter, 50);
        }}
    }}
    initInverter();
}})();
</script>''')
    except Exception as e:
        print(f"Error loading Inverter React: {e}")

    push_inverter_data()
