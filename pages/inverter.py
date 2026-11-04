from nicegui import ui, app
from pages.home import CUSTOM_CSS, sidebar, state, global_topbar
from pages.login import check_login
from service import auth
import re
import time
import json
from service.logger import get_logger

logger = get_logger("INVERTER")

@app.get('/api/inverter')
def get_inverter_api():
    from service.mqtt import publish_mqtt # Local import to avoid circular dependency
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

@ui.page('/inverter')
def trang_inverter():
    if not check_login(): return

    # --- Định nghĩa các hàm xử lý dữ liệu Inverter ---
    @ui.refreshable
    def push_inverter_data():
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
            "online": state.get("inv_online", 1),
            "is_locked": state.get("inv_locked", False),
            "cooldown": max(0, 30 - int(time.time() - state.get("inv_lock_time", 0))) if state.get("inv_lock_time") else 0,
            "mode": auth.get_inverter_mode("greenhouse_a"),
            "permissions": app.storage.user.get('permissions', [])
        }
        ui.run_javascript(f'if(window.updateInverterData) window.updateInverterData({json.dumps(data)});')

    def check_ui_update():
        if not hasattr(check_ui_update, "last_counter"):
            check_ui_update.last_counter = 0

        current_counter = state.get("_update_counter", 0)
        if current_counter != check_ui_update.last_counter:
            check_ui_update.last_counter = current_counter
            push_inverter_data.refresh()
            client_id = ui.context.client.id
            try:
                from pages.home import client_refreshes
                if client_id in client_refreshes:
                    for refresh_func in client_refreshes[client_id]:
                        try:
                            refresh_func()
                        except Exception:
                            pass
            except ImportError:
                pass

    # --- Timer đồng bộ (Đặt ở cấp page, ngoài mọi container) ---
    t = ui.timer(2.0, check_ui_update)
    ui.context.client.on_disconnect(t.deactivate)

    # --- Event Handlers ---
    def handle_inverter_control(e):
        from service.mqtt import publish_mqtt
        from service.auth import check_permission, get_inverter_mode
        import time
        
        user_id = app.storage.user.get('user_id')
        if not user_id:
            ui.notify('Bạn chưa đăng nhập', color='negative')
            return
            
        if not check_permission(user_id, "inverter_toggle_control"):
            ui.notify('Bạn không có quyền điều khiển Inverter', color='negative')
            return
            
        mode = get_inverter_mode("greenhouse_a")
        bit_val = e.args.get("bit", 0)
        
        last_time = state.get("inv_lock_time", 0)
        current_time = time.time()
        if current_time - last_time < 30:
            logger.warning("[MANUAL] Lệnh bị bỏ qua do đang trong thời gian chờ 30s")
            # print("➔ [SOCKET] Lệnh bị bỏ qua do đang trong thời gian chờ 30s")
            return
            
        state["inv_locked"] = (bit_val == 1)
        state["inv_lock_time"] = current_time
        
        # Đăng ký hàng đợi chờ phản hồi (Timeout 2 phút)
        state["inv_pending_cmd"] = {"time": current_time, "target_bit": bit_val}
        
        # Payload cho Manual (mặc định từ UI luôn là Manual)
        payload = {"device_name": "Inverter", "bit": bit_val}
        
        logger.info(f"[{mode.upper()}] Gửi lệnh điều khiển Inverter: bit={bit_val} bởi UserID={user_id}")
        # print(f"➔ [SOCKET] Nhận lệnh Inverter ({mode.upper()}): {payload}")
        publish_mqtt("farm/inverter", payload)
        state["_update_counter"] = state.get("_update_counter", 0) + 1
        
        push_inverter_data.refresh()

    ui.on('inverter_control', handle_inverter_control)

    def handle_mode_change(e):
        from service.auth import set_inverter_mode, check_permission
        user_id = app.storage.user.get('user_id')
        
        if not user_id:
            ui.notify('Bạn chưa đăng nhập', color='negative')
            return
            
        if not check_permission(user_id, "inverter_change_mode"):
            ui.notify('Bạn không có quyền thay đổi chế độ tự động hóa', color='negative')
            return
            
        new_mode = e.args.get("mode", "manual")
        set_inverter_mode("greenhouse_a", new_mode)
        ui.notify(f'Đã chuyển sang chế độ {new_mode.upper()}', color='info')
        state["_update_counter"] = state.get("_update_counter", 0) + 1

    ui.on('inverter_mode_change', handle_mode_change)
    
    def handle_inverter_pid_sync(e):
        from service.mqtt import publish_mqtt
        from service.auth import check_permission
        from datetime import datetime
        
        user_id = app.storage.user.get('user_id')
        if not user_id:
            ui.notify('Bạn chưa đăng nhập', color='negative')
            return
            
        if not check_permission(user_id, "inverter_send_data"):
            ui.notify('Bạn không có quyền gửi dữ liệu Inverter', color='negative')
            return
            
        args = e.args
        kp = args.get('kp', 0.0)
        ki = args.get('ki', 0.0)
        kd = args.get('kd', 0.0)
        p_set = args.get('p_set', 0.0)
        
        payload = {
            "_id": "6a02c8afac8cd4d05a47cb45",
            "id": 17833,
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "device_name": "Inverter",
            "online": state.get("inv_online", 1),
            "status": state.get("inv_status", 0),
            "hz": state.get("inv_hz", 0),
            "p_set": p_set,
            "p_cur": state.get("inv_p_cur", 0),
            "v_out": state.get("inv_v_out", 0),
            "i_out": state.get("inv_i_out", 0),
            "v_in": state.get("inv_v_in", 241.77),
            "i_in": state.get("inv_i_in", 0),
            "kp": kp,
            "ki": ki,
            "kd": kd
        }
        
        print(f"➔ [SOCKET] Đồng bộ PID xuống Inverter: {payload}")
        publish_mqtt("farm/pid", payload)
        ui.notify('Đã đồng bộ dữ liệu PID xuống Inverter!', color='positive')
        
    ui.on('inverter_pid_sync', handle_inverter_pid_sync)

    # --- UI Layout ---
    ui.add_head_html("""
    <script type="text/javascript">
    window.onerror = function(message, url, line, column, error) {
        var errorData = {
            message: message,
            url: url,
            line: line,
            column: column,
            stack: error ? error.stack : ''
        };
        fetch('/api/js_error', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(errorData)
        });
    };
    window.onunhandledrejection = function(event) {
        var errorData = {
            message: 'Unhandled Rejection: ' + event.reason,
            url: window.location.href,
            line: 0,
            column: 0,
            stack: event.reason && event.reason.stack ? event.reason.stack : ''
        };
        fetch('/api/js_error', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(errorData)
        });
    };
    </script>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/prop-types@15.7.2/prop-types.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/recharts/2.1.12/Recharts.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        """ + CUSTOM_CSS + """
        .glass-card {
            background: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.6);
            border-radius: 24px;
            box-shadow: 0 10px 40px -10px rgba(0,0,0,0.05);
            transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1), 
                        box-shadow 0.3s cubic-bezier(0.25, 0.8, 0.25, 1),
                        border-color 0.3s ease;
        }
        .glass-card:hover {
            transform: translateY(-6px) !important;
            box-shadow: 0 15px 35px rgba(30, 41, 59, 0.12) !important;
            border-color: rgba(91, 95, 239, 0.35) !important;
        }
        /* Shimmer cho progress bar */
        .progress-bar::after {
            content: '';
            position: absolute;
            top: 0; right: 0; bottom: 0; left: 0;
            background: linear-gradient(
                90deg,
                rgba(255, 255, 255, 0) 0%,
                rgba(255, 255, 255, 0.4) 50%,
                rgba(255, 255, 255, 0) 100%
            );
            animation: progress-shimmer 2s infinite;
            transform: translateX(-100%);
        }
        @keyframes progress-shimmer {
            100% { transform: translateX(100%); }
        }
        /* Hz Activity Glow */
        @keyframes hz-glow-pulse {
            0% {
                box-shadow: 0 4px 6px -1px rgba(245, 158, 11, 0.1), 0 0 0px rgba(245, 158, 11, 0);
                border-color: rgba(245, 158, 11, 0.2);
            }
            50% {
                box-shadow: 0 10px 20px -3px rgba(245, 158, 11, 0.2), 0 0 15px rgba(245, 158, 11, 0.35);
                border-color: rgba(245, 158, 11, 0.6);
            }
            100% {
                box-shadow: 0 4px 6px -1px rgba(245, 158, 11, 0.1), 0 0 0px rgba(245, 158, 11, 0);
                border-color: rgba(245, 158, 11, 0.2);
            }
        }
        .hz-glow {
            animation: hz-glow-pulse 2s infinite ease-in-out;
            background: rgba(254, 243, 199, 0.7) !important;
        }
    </style>
    """)

    sidebar(active="Inverter")
    
    with ui.element("div").classes("main-content"):
        global_topbar("Điều Khiển Inverter", "🔌")
        with ui.element("div").classes("content-area"):
            with ui.element("div").style("width:100%").bind_visibility_from(state, 'selected_farm', backward=lambda f: f != "Greenhouse A"):
                with ui.element("div").style(
                    "display:flex;flex-direction:column;align-items:center;justify-content:center;"
                    "min-height:400px;background:white;border-radius:16px;border:1px solid #e2e8f0;"
                    "padding:60px 40px;text-align:center"
                ):
                    ui.label("🔌").style("font-size:64px;margin-bottom:20px;opacity:0.4")
                    ui.label().style("font-size:22px;font-weight:800;color:#1a1a2e;margin-bottom:8px") \
                        .bind_text_from(state, 'selected_farm')
                    ui.label("Chưa có dữ liệu Inverter").style("font-size:16px;font-weight:600;color:#94a3b8;margin-bottom:16px")
                    with ui.element("div").style("background:#f8fafc;border-radius:12px;padding:16px 24px;border:1px dashed #e2e8f0;max-width:420px"):
                        ui.label("Hệ thống Inverter cho farm này chưa được kết nối. Hiện tại chỉ Greenhouse A đang hoạt động.").style("font-size:13px;color:#64748b;line-height:1.6")

            with ui.element("div").style("width:100%").bind_visibility_from(state, 'selected_farm', backward=lambda f: f == "Greenhouse A"):
                ui.html('<div id="inverter-root" style="width: 100%; min-height: 100%;"></div>')

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
