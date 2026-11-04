from nicegui import ui, app
from pages.home import CUSTOM_CSS, sidebar, state, global_topbar
import json
from pages.login import check_login
import re

@ui.page('/plc')
def trang_plc():
    if not check_login(): return

    # --- Định nghĩa các hàm xử lý dữ liệu PLC ---
    @ui.refreshable
    def push_plc_data():
        loading_states = {f"pump{i+1}": 1 if i in state.get("plc_pending_cmds", {}) else 0 for i in range(7)}
        data = {
            "pumps": {f"pump{i+1}": state.get(f"bit{i}", 0) for i in range(7)},
            "outputs": {f"q{i}": state.get(f"q{i}", 0) for i in range(7)},
            "plc_online": state.get("plc_online", 0),
            "loading": loading_states,
            "permissions": app.storage.user.get('permissions', [])
        }
        ui.run_javascript(f'if(window.updatePlcData) window.updatePlcData({json.dumps(data)});')

    def check_plc_ui_update():
        if not hasattr(check_plc_ui_update, "last_counter"):
            check_plc_ui_update.last_counter = 0

        current_counter = state.get("_update_counter", 0)
        if current_counter != check_plc_ui_update.last_counter:
            check_plc_ui_update.last_counter = current_counter
            push_plc_data.refresh()
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
    t = ui.timer(2.0, check_plc_ui_update)
    ui.context.client.on_disconnect(t.deactivate)

    # --- Event Handlers (Dùng ui.on để React gửi lệnh lên) ---
    def handle_plc_control(e):
        from service.mqtt import publish_mqtt
        from service.auth import check_permission
        from service.observability import trace_span
        import time
        
        user_id = app.storage.user.get('user_id')
        if not user_id:
            ui.notify('Bạn chưa đăng nhập', color='negative')
            return
            
        payload = e.args
        bit_val = payload.get("bit")
        if bit_val is not None:
            pump_num = bit_val + 1
            perm_key = f"pump_{pump_num}_control"
            
            if not check_permission(user_id, perm_key):
                ui.notify(f'Bạn không có quyền điều khiển Bơm {pump_num}', color='negative')
                return
                
        print(f"➔ [SOCKET] Nhận lệnh PLC từ Client: {payload}")
        with trace_span("smiot.plc.command", resource="farm/control", **{"mqtt.topic": "farm/control", "plc.mode": "ui_demo"}):
            publish_mqtt("farm/control", payload)
        
        # Đăng ký hàng đợi lệnh chờ phản hồi tiếp điểm Q vật lý (Timeout 10 giây)
        if "plc_pending_cmds" not in state:
            state["plc_pending_cmds"] = {}
        for key, val in payload.items():
            if key.startswith("bit"):
                idx = int(key.replace("bit", ""))
                state["plc_pending_cmds"][idx] = {"time": time.time(), "target_val": val}
                
        state["_update_counter"] = state.get("_update_counter", 0) + 1
        push_plc_data.refresh()

    ui.on('plc_control', handle_plc_control)
    
    def handle_plc_locked_click(e):
        pump = e.args.get('pump')
        ui.notify(f'Chức năng Bơm {pump} đã bị khóa cho tài khoản của bạn!', color='warning', position='top')
        
    ui.on('plc_locked_click', handle_plc_locked_click)
    ui.on('plc_ready', lambda: push_plc_data.refresh())
    
    # --- UI Layout ---
    ui.add_head_html(f"""
    <script type="text/javascript">
    window.onerror = function(message, url, line, column, error) {{
        var errorData = {{
            message: message,
            url: url,
            line: line,
            column: column,
            stack: error ? error.stack : ''
        }};
        fetch('/api/js_error', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(errorData)
        }});
    }};
    window.onunhandledrejection = function(event) {{
        var errorData = {{
            message: 'Unhandled Rejection: ' + event.reason,
            url: window.location.href,
            line: 0,
            column: 0,
            stack: event.reason && event.reason.stack ? event.reason.stack : ''
        }};
        fetch('/api/js_error', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(errorData)
        }});
    }};
    </script>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        {CUSTOM_CSS}
        .glass-card {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.6);
            border-radius: 24px;
            box-shadow: 0 10px 40px -10px rgba(0,0,0,0.08);
            transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1), 
                        box-shadow 0.3s cubic-bezier(0.25, 0.8, 0.25, 1),
                        border-color 0.3s ease;
        }}
        .glass-card:hover {{
            transform: translateY(-6px) !important;
            box-shadow: 0 15px 35px rgba(30, 41, 59, 0.12) !important;
            border-color: rgba(91, 95, 239, 0.35) !important;
        }}
        .card-online-border {{ border-color: rgba(34, 197, 94, 0.25); }}
        .card-offline-border {{ border-color: rgba(244, 63, 94, 0.25); }}
        .pump-control-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 12px;
            width: 100%;
        }}
        @media (min-width: 768px) {{
            .pump-control-grid {{
                grid-template-columns: repeat(2, 1fr);
                gap: 14px;
            }}
            .pump-control-grid > div:nth-child(7) {{
                grid-column: 1 / -1;
                max-width: calc(50% - 7px);
                margin: 0 auto;
            }}
        }}
        .pump-row-card {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 18px 22px;
            background: #ffffff;
            border: 1.5px solid #e2e8f0;
            border-radius: 14px;
            cursor: pointer;
            transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
            user-select: none;
        }}
        .pump-row-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px -4px rgba(0,0,0,0.07);
            border-color: #cbd5e1;
        }}
        .pump-row-card:active {{
            transform: translateY(0px);
        }}
        .pump-row-card-on {{
            background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%);
            border-color: rgba(34, 197, 94, 0.35);
            box-shadow: 0 4px 12px -2px rgba(34, 197, 94, 0.1);
        }}
        .pump-row-card-on:hover {{
            border-color: rgba(34, 197, 94, 0.5);
            box-shadow: 0 8px 20px -4px rgba(34, 197, 94, 0.15);
        }}
        .pump-row-card-loading {{
            background: #fffbeb;
            border-color: rgba(245, 158, 11, 0.4);
            animation: card-loading-pulse 1.5s infinite alternate;
        }}
        .pump-row-card-mismatch {{
            background: #fff1f2;
            border-color: rgba(244, 63, 94, 0.5);
            animation: card-mismatch-flash 1.5s infinite alternate;
        }}
        .pump-row-card-locked {{
            background: #f8fafc;
            border-color: #e2e8f0;
            cursor: not-allowed;
            opacity: 0.65;
        }}
        .pump-row-card-locked:hover {{
            transform: none;
            box-shadow: none;
        }}
        .toggle-track {{
            width: 52px;
            height: 28px;
            background: #cbd5e1;
            border-radius: 14px;
            position: relative;
            transition: background 250ms cubic-bezier(0.4, 0, 0.2, 1);
            flex-shrink: 0;
        }}
        .toggle-knob {{
            width: 22px;
            height: 22px;
            background: white;
            border-radius: 50%;
            position: absolute;
            top: 3px;
            left: 3px;
            transition: transform 250ms cubic-bezier(0.4, 0, 0.2, 1),
                        box-shadow 250ms ease;
            box-shadow: 0 1px 4px rgba(0,0,0,0.15);
        }}
        .toggle-on {{
            background: #22c55e;
        }}
        .toggle-on .toggle-knob {{
            transform: translateX(24px);
            box-shadow: 0 0 10px rgba(34, 197, 94, 0.5), 0 1px 4px rgba(0,0,0,0.1);
        }}
        .toggle-loading {{
            background: #f59e0b;
            animation: toggle-bg-pulse 1s infinite alternate;
        }}
        .toggle-loading .toggle-knob {{
            animation: knob-loading-bounce 0.8s infinite alternate ease-in-out;
        }}
        .toggle-mismatch {{
            background: #f43f5e;
            animation: toggle-bg-pulse 0.8s infinite alternate;
        }}
        .toggle-mismatch .toggle-knob {{
            background: #fecdd3;
            transform: translateX(24px);
        }}
        .toggle-locked {{
            background: #94a3b8;
            opacity: 0.4;
        }}
        .status-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #cbd5e1;
            flex-shrink: 0;
            transition: background 200ms ease;
        }}
        .status-dot-active {{
            background: #22c55e;
            animation: dot-pulse 2s infinite ease-in-out;
        }}
        .status-dot-loading {{
            background: #f59e0b;
            animation: dot-pulse 0.6s infinite ease-in-out;
        }}
        .status-dot-mismatch {{
            background: #f43f5e;
            animation: dot-pulse 0.8s infinite ease-in-out;
        }}
        .plc-indicator {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            position: relative;
            width: 14px;
            height: 14px;
        }}
        .plc-indicator .dot-core {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            position: relative;
            z-index: 1;
        }}
        .plc-indicator .dot-ping {{
            position: absolute;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            animation: ping-ring 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
        }}
        .header-icon-pulse {{
            display: inline-block;
            animation: icon-energy 2s infinite alternate ease-in-out;
        }}
        @keyframes icon-energy {{
            0% {{ opacity: 0.6; transform: scale(1); }}
            100% {{ opacity: 1; transform: scale(1.2); }}
        }}
        @keyframes dot-pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.3; }}
        }}
        @keyframes ping-ring {{
            0% {{ transform: scale(1); opacity: 0.75; }}
            75%, 100% {{ transform: scale(2.5); opacity: 0; }}
        }}
        @keyframes toggle-bg-pulse {{
            0% {{ opacity: 0.6; }}
            100% {{ opacity: 1; }}
        }}
        @keyframes knob-loading-bounce {{
            0% {{ transform: translateX(2px); }}
            100% {{ transform: translateX(18px); }}
        }}
        @keyframes card-loading-pulse {{
            0% {{ border-color: rgba(245, 158, 11, 0.2); }}
            100% {{ border-color: rgba(245, 158, 11, 0.6); }}
        }}
        @keyframes card-mismatch-flash {{
            0% {{ box-shadow: 0 0 5px rgba(244, 63, 94, 0.15); }}
            100% {{ box-shadow: 0 0 18px rgba(244, 63, 94, 0.35); }}
        }}
    </style>
    """)
    sidebar('PLC')

    with ui.element("div").classes("main-content"):
        global_topbar("Điều Khiển PLC", "🎛️")
        
        with ui.element("div").classes("content-area"):
            # Khung hiển thị khi không phải Greenhouse A (Chưa có dữ liệu)
            with ui.element("div").style("width:100%").bind_visibility_from(state, 'selected_farm', backward=lambda f: f != "Greenhouse A"):
                with ui.element("div").style(
                    "display:flex;flex-direction:column;align-items:center;justify-content:center;"
                    "min-height:400px;background:white;border-radius:16px;border:1px solid #e2e8f0;"
                    "padding:60px 40px;text-align:center"
                ):
                    ui.label("🎛️").style("font-size:64px;margin-bottom:20px;opacity:0.4")
                    ui.label().style("font-size:22px;font-weight:800;color:#1a1a2e;margin-bottom:8px") \
                        .bind_text_from(state, 'selected_farm')
                    ui.label("Chưa có dữ liệu PLC").style("font-size:16px;font-weight:600;color:#94a3b8;margin-bottom:16px")
                    with ui.element("div").style("background:#f8fafc;border-radius:12px;padding:16px 24px;border:1px dashed #e2e8f0;max-width:420px"):
                        ui.label("Hệ thống PLC cho farm này chưa được kết nối. Hiện tại chỉ Greenhouse A đang hoạt động.").style("font-size:13px;color:#64748b;line-height:1.6")
            
            # Khung hiển thị của Greenhouse A (Có dữ liệu thật)
            with ui.element("div").style("width:100%").bind_visibility_from(state, 'selected_farm', backward=lambda f: f == "Greenhouse A"):
                with ui.card().classes('w-full rounded-2xl shadow-sm border border-gray-100 p-0 overflow-hidden bg-white'):
                    ui.html('<div id="plc-root" class="w-full" style="min-height: 500px;"></div>')

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
