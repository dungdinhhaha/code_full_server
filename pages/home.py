from nicegui import ui, app
from pages.login import check_login
from service import auth
from service.weather_api import WeatherAPIClient
from typing import Set, Callable
import asyncio
import os
from datetime import datetime, timedelta

# Bộ lưu trữ các callback refresh cụ thể cho từng client đang kết nối
client_refreshes = {}

# ─────────────────────────────────────────────
# CSS & STYLES
# ─────────────────────────────────────────────
CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
@import url('https://cdn.jsdelivr.net/npm/remixicon@4.2.0/fonts/remixicon.css');

* { box-sizing: border-box; }

html, body, #q-app {
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
    height: 100% !important;
    overflow: hidden !important;
    background: #f4f6f9;
    font-family: 'Inter', sans-serif;
}

/* Ghi đè toàn bộ hệ thống layout của NiceGUI / Quasar để tràn màn hình */
.q-layout, .q-page-container, .q-page, .nicegui-content {
    max-width: none !important;
    width: 100% !important;
    height: 100% !important;
    min-height: 100% !important;
    padding: 0px !important;
    margin: 0px !important;
    gap: 0px !important;
    box-sizing: border-box !important;
    overflow-x: hidden !important;
}

/* Đảm bảo các card trong main-grid có chiều cao bằng nhau và thẳng hàng */
.main-grid > div {
    display: flex !important;
    flex-direction: column !important;
    align-items: stretch !important;
    height: 100% !important;
}
.main-grid > div > .card,
.main-grid > div > .weather-card {
    flex: 1 1 auto !important;
    height: 100% !important;
    width: 100% !important;
}

.sidebar {
    width: 200px; min-height: 100vh;
    background: rgba(255, 255, 255, 0.8);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-right: 1px solid rgba(241, 245, 249, 0.6);
    box-shadow: 4px 0 30px rgba(0,0,0,0.02);
    position: fixed; top: 0; left: 0; z-index: 100;
    display: flex; flex-direction: column;
}

.sidebar-logo {
    display: flex; align-items: center; gap: 8px;
    padding: 20px 16px 16px;
    border-bottom: 1px solid rgba(241, 245, 249, 0.6);
    font-weight: 700; font-size: 15px; color: #1e293b;
    letter-spacing: 0.02em;
}

.sidebar-section { 
    padding: 16px 16px 6px; font-size: 10px;
    color: #94a3b8; font-weight: 600; letter-spacing: 0.08em; 
    text-transform: uppercase; 
}

.nav-item {
    display: flex; align-items: center; gap: 10px;
    padding: 9px 16px; cursor: pointer; border-radius: 10px;
    margin: 3px 12px; color: #64748b; font-size: 13px; font-weight: 500;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1); 
    text-decoration: none;
    position: relative;
}

.nav-item i {
    font-size: 16px;
    color: #94a3b8;
    transition: transform 0.25s, color 0.25s;
}

.nav-item:hover { 
    background: #f1f5f9; 
    color: #5B5FEF; 
}

.nav-item:hover i {
    color: #5B5FEF;
    transform: scale(1.1) rotate(5deg);
}

.nav-item.active { 
    background: #eef2ff; 
    color: #5B5FEF; 
    font-weight: 600; 
}

.nav-item.active i {
    color: #5B5FEF;
}

.nav-item.active::before {
    content: ''; position: absolute; left: 0; top: 20%; height: 60%; width: 4px;
    background: #5B5FEF; border-radius: 0 4px 4px 0;
}

.main-content {
    padding-left: 200px;
    width: 100%;
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    overflow-x: hidden !important;
    background: #f8fafc;
    box-sizing: border-box;
}

.top-bar {
    background: white;
    padding: 10px 20px;
    display: flex; align-items: center; justify-content: space-between;
    border-bottom: 1px solid #e2e8f0;
    flex-shrink: 0;
}

.top-bar-title {
    display: flex; align-items: center; gap: 8px;
    font-size: 14px; font-weight: 700; color: #1a1a2e;
}

.content-area { 
    padding: 16px 20px; 
    flex: 1; 
    overflow-y: auto; 
    display: flex;
    flex-direction: column;
}

.section-header {
    display: flex; align-items: center; gap: 6px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.05em;
    text-transform: uppercase; margin-bottom: 10px;
}

/* ── PULSATING DOT ── */
.dot {
    width: 6px; height: 6px; border-radius: 50%;
    display: inline-block; flex-shrink: 0;
}
.dot-green {
    background: #22c55e;
    animation: pulse-green 2s infinite;
}
.dot-blue  { background: #3b82f6; animation: pulse-blue  2s infinite; }
.dot-red   { background: #ef4444; animation: pulse-red   2.0s infinite; }
.dot-yellow{ background: #f59e0b; animation: pulse-yellow 2.0s infinite; }
@keyframes pulse-green {
    0%  { box-shadow: 0 0 0 0 rgba(34,197,94,0.8); }
    70% { box-shadow: 0 0 0 10px rgba(34,197,94,0); }
    100%{ box-shadow: 0 0 0 0 rgba(34,197,94,0); }
}
@keyframes pulse-blue {
    0%  { box-shadow: 0 0 0 0 rgba(59,130,246,0.8); }
    70% { box-shadow: 0 0 0 10px rgba(59,130,246,0); }
    100%{ box-shadow: 0 0 0 0 rgba(59,130,246,0); }
}
@keyframes pulse-red {
    0%  { box-shadow: 0 0 0 0 rgba(239,68,68,0.8); }
    70% { box-shadow: 0 0 0 10px rgba(239,68,68,0); }
    100%{ box-shadow: 0 0 0 0 rgba(239,68,68,0); }
}
@keyframes pulse-yellow {
    0%  { box-shadow: 0 0 0 0 rgba(245,158,11,0.8); }
    70% { box-shadow: 0 0 0 10px rgba(245,158,11,0); }
    100%{ box-shadow: 0 0 0 0 rgba(245,158,11,0); }
}

/* ── BADGE ── */
.badge {
    display:inline-flex; align-items:center; gap:6px;
    padding: 4px 10px; border-radius: 20px;
    font-size: 11px; font-weight: 700; letter-spacing: 0.04em; text-transform:uppercase;
}
.badge-online  { background: #dcfce7; color: #16a34a; }
.badge-live    { background: #dbeafe; color: #1d4ed8; }
.badge-active  { background: #dcfce7; color: #16a34a; font-size:12px; }

/* ── CARDS ── */
.card {
    background: white; border-radius: 16px;
    border: 1px solid #e8ecf0;
    box-shadow: 0 1px 4px rgba(30,41,59,0.05);
    padding: 18px 20px;
    transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1), 
                box-shadow 0.3s cubic-bezier(0.25, 0.8, 0.25, 1),
                border-color 0.3s ease;
}
.card:hover { 
    box-shadow: 0 15px 35px rgba(30,41,59,0.15);
    transform: translateY(-6px);
    border-color: #cbd5e1;
}

.card-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 14px;
}

.card-title {
    display: flex; align-items: center; gap: 8px;
    font-weight: 700; font-size: 15px; color: #1a1a2e;
}

.sub-section {
    font-size: 10px; font-weight: 700; color: #aaa;
    letter-spacing: 0.1em; text-transform: uppercase;
    margin: 10px 0 6px;
}

.metric-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
}

.metric-box {
    background: #f8fafc; border-radius: 10px; padding: 10px 12px;
}
.metric-label {
    font-size: 10px; color: #aaa; font-weight: 600;
    letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 4px;
}
.metric-value {
    font-size: 18px; font-weight: 800; color: #1a1a2e;
}
.metric-unit { font-size: 11px; color: #999; font-weight: 400; }

.ec-footer {
    display: flex; align-items: center; justify-content: space-between;
    margin-top: 12px; padding-top: 10px;
    border-top: 1px solid #f0f0f0;
    font-size: 12px;
}

/* ── Progress bar ── */
.progress-bar-bg {
    height: 8px; background: #e2e8f0; border-radius: 4px; margin-top: 6px;
}
.progress-bar {
    height: 8px; border-radius: 4px;
    position: relative;
    overflow: hidden;
    transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}
.progress-bar::after {
    content: '';
    position: absolute;
    top: 0; right: 0; bottom: 0; left: 0;
    background: linear-gradient(
        90deg,
        rgba(255, 255, 255, 0) 0%,
        rgba(255, 255, 255, 0.5) 50%,
        rgba(255, 255, 255, 0) 100%
    );
    animation: progress-shimmer 2s infinite;
    transform: translateX(-100%);
}
@keyframes progress-shimmer {
    100% { transform: translateX(100%); }
}
/* ── DYNAMIC EFFECTS (ADDED FOR CARDS) ── */
.hover-elevate {
    transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1), box-shadow 0.3s ease, border-color 0.3s ease !important;
}
.hover-elevate:hover {
    transform: translateY(-6px) !important;
    box-shadow: 0 15px 35px rgba(30,41,59,0.15) !important;
    border-color: #cbd5e1 !important;
}

.glass-card {
    background: rgba(255, 255, 255, 0.85) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(255, 255, 255, 0.6) !important;
}

.neon-glow {
    box-shadow: 0 0 15px rgba(45, 212, 191, 0.2), inset 0 0 20px rgba(45, 212, 191, 0.05) !important;
    transition: box-shadow 0.3s ease !important;
}
.neon-glow:hover {
    box-shadow: 0 0 25px rgba(45, 212, 191, 0.4), inset 0 0 30px rgba(45, 212, 191, 0.1) !important;
}

.shimmer-overlay {
    position: absolute;
    top: 0; left: -150%;
    width: 50%; height: 100%;
    background: linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.4) 50%, rgba(255,255,255,0) 100%);
    transform: skewX(-20deg);
    pointer-events: none;
    z-index: 10;
}
.group:hover .shimmer-overlay {
    animation: shimmer-swipe 0.8s ease-out forwards;
}
@keyframes shimmer-swipe {
    0% { left: -150%; }
    100% { left: 200%; }
}

/* ── Flow Meter card ── */
.flow-lines {
    display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 12px 0;
}
.flow-line-box {
    background: #f8fafc; border-radius: 10px; padding: 12px;
    text-align: center;
}
.flow-total-box {
    background: #1e293b; border-radius: 12px; padding: 14px 18px;
    display: flex; align-items: center; justify-content: space-between; margin-top: 4px;
}
.flow-total-val {
    font-size: 26px; font-weight: 800; color: white;
}

/* ── Weather card ── */
.weather-card {
    background: linear-gradient(135deg, #1e3a8a, #0284c7, #0d9488, #2563eb);
    background-size: 300% 300%;
    animation: weather-gradient-flow 7s ease infinite;
    border-radius: 16px; padding: 20px 22px; color: white;
    transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1), 
                box-shadow 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}
.weather-card:hover {
    transform: translateY(-6px);
    box-shadow: 0 15px 35px rgba(2, 132, 199, 0.35);
}
@keyframes weather-gradient-flow {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
.weather-hourly {
    display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin: 12px 0;
}
.weather-hour-box {
    background: rgba(255,255,255,0.15); border-radius: 12px;
    padding: 12px; text-align: center; backdrop-filter: blur(4px);
}
.weather-daily-stats {
    display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
    background: rgba(255,255,255,0.12); border-radius: 12px; padding: 14px;
}

/* ── AI Card ── */
.ai-card {
    background: #1e293b; border-radius: 16px;
    padding: 20px 22px; color: white;
    box-shadow: 0 4px 20px rgba(13,27,42,0.3);
    border: 1px solid rgba(124, 58, 237, 0.15) !important;
    transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1), 
                box-shadow 0.3s cubic-bezier(0.25, 0.8, 0.25, 1),
                border-color 0.3s ease;
}
.ai-card:hover {
    transform: translateY(-6px);
    box-shadow: 0 0 25px rgba(124, 58, 237, 0.45) !important;
    border-color: rgba(124, 58, 237, 0.6) !important;
}
.ai-row {
    display:flex; align-items:center; justify-content:space-between;
    padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.07);
}
.ai-row:last-child { border-bottom: none; }

/* ── Dashboard grids ── */
.main-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    column-gap: 20px;
    row-gap: 20px;
    align-items: stretch;
}

.sub-grid {
    display: grid;
    grid-template-columns: 1fr;
    column-gap: 20px;
    align-items: stretch;
}

/* Responsive Rules */
@media (max-width: 1200px) {
    .main-grid {
        grid-template-columns: 1fr 1fr;
        row-gap: 20px;
    }
    .sub-grid {
        grid-template-columns: 1fr;
        row-gap: 20px;
    }
}

@media (max-width: 768px) {
    .main-content {
        margin-left: 0;
        padding-bottom: 80px;
    }
    .sidebar {
        width: 100%;
        height: 60px;
        min-height: auto;
        position: fixed;
        bottom: 0;
        top: auto;
        left: 0;
        z-index: 100;
        flex-direction: row;
        box-shadow: 0 -4px 20px rgba(0,0,0,0.03);
        border-top: 1px solid rgba(241, 245, 249, 0.8);
        justify-content: space-around;
        align-items: center;
        padding: 0;
        background: rgba(255, 255, 255, 0.85);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
    }
    .sidebar-logo, .sidebar-section, .sidebar div:last-child {
        display: none !important;
    }
    .nav-item {
        margin: 0;
        padding: 6px;
        font-size: 10px;
        flex-direction: column;
        gap: 1px;
        flex: 1;
        text-align: center;
        justify-content: center;
        border-radius: 6px;
    }
    .nav-item i {
        font-size: 18px !important;
        color: #94a3b8;
    }
    .nav-item.active {
        background: #eef2ff;
        color: #5B5FEF;
    }
    .nav-item.active i {
        color: #5B5FEF;
    }
    .nav-item.active::before {
        display: none;
    }
    .main-grid, .sub-grid {
        grid-template-columns: 1fr;
        row-gap: 16px;
    }
}
"""

# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
refresh_callbacks: Set[Callable] = set()

import time

state = {
    "system_last_seen": time.time(),
    "node1_status": "ONLINE",
    "node1_air_temp": 30.3,
    "node1_air_hum": 65.3,
    "node1_soil_temp": 26.0,
    "node1_soil_hum": 50.0,
    "node1_ec": 1.4,
    "node1_updated": "11:23:15",

    "node2_status": "ONLINE",
    "node2_air_temp": 37.5,
    "node2_air_hum": 65.1,
    "node2_soil_temp": 35.7,
    "node2_soil_hum": 38.2,
    "node2_ec": 280,
    "node2_updated": "14:08:28",

    "flow_line1": 0,
    "flow_line2": 0,
    "flow_total": 18.33,
    "flow_updated": "10:48:34",
    "flow_serial": "1560",

    # EC & pH Sensor Cards State
    "ec_val": 0.0,
    "ec_v": 0.0,
    "ec_raw": 0,
    "ec_online": 1,
    "ec_updated": "Chưa cập nhật",

    "ph_val": 7.0,
    "ph_mv": 0.0,
    "ph_raw": 0,
    "ph_online": 1,
    "ph_updated": "Chưa cập nhật",

    "weather_city": "Thành phố Hồ Chí Minh",
    "weather_lat": "10.86",
    "weather_lng": "106.81",
    "weather_10h_temp": 33.1,
    "weather_10h_rain": 50,
    "weather_11h_temp": 33.7,
    "weather_11h_rain": 49,
    "weather_12h_temp": 33.7,
    "weather_12h_rain": 50,
    "weather_solar": 6401,
    "weather_eto": 5.74,

    "ai_water_suggest": 0,
    "van_status": 0,  # 0: Không tưới, 1: Tưới
    "ai_time": "11:23:15",

    # Inverter State
    "inv_online": 0,
    "inv_status": 0,
    "inv_hz": 0.0,
    "inv_p_set": 0.0,
    "inv_p_cur": 0.0,
    "inv_v_out": 0.0,
    "inv_i_out": 0.0,
    "inv_v_in": 0.0,
    "inv_i_in": 0.0,
    "inv_kp": 0.0,
    "inv_ki": 0.0,
    "inv_kd": 0.0,
    "inv_updated": "",
    "inv_has_started": False,
    "ph_value": 7.0,
}
def global_topbar(title, emoji="📊"):
    from pages.home import state
    from service.auth import get_user_farms, FIXED_FARMS, update_user_activity
    fullname = app.storage.user.get('fullname', 'User')
    avatar_file = app.storage.user.get('avatar', 'client.png')
    user_id = app.storage.user.get('user_id')
    role = app.storage.user.get('role', 'viewer')
    
    # Cập nhật thời gian hoạt động
    if user_id:
        update_user_activity(user_id)
    
    # Lấy danh sách farm user được phép dùng
    if role == 'admin':
        farm_options = [f[1] for f in FIXED_FARMS]  # Tất cả farm
    elif user_id:
        user_farm_keys = get_user_farms(user_id)
        farm_map = {f[0]: f[1] for f in FIXED_FARMS}
        farm_options = [farm_map[k] for k in user_farm_keys if k in farm_map]
        if not farm_options:
            farm_options = ["Greenhouse A"]
    else:
        farm_options = ["Greenhouse A"]
    # Khởi tạo selected_farm trong state nếu chưa có
    if "selected_farm" not in state:
        state["selected_farm"] = farm_options[0]
    
    with ui.element("div").classes("top-bar").style("padding: 12px 20px; display: flex; align-items: center; justify-content: space-between;"):
        with ui.element("div").classes("top-bar-title").style("display:flex; align-items:center; gap:12px;"):
            with ui.element("div").style(
                "width:28px;height:28px;background:#f0f4ff;border-radius:8px;"
                "display:flex;align-items:center;justify-content:center;font-size:14px"
            ):
                ui.label(emoji)
            
            # Tiêu đề trang
            ui.label(title).style("font-weight:700; font-size:15px; color:#1a1a2e;")
            
            # Dropdown chọn Greenhouse/Farm (lọc theo quyền)
            if len(farm_options) > 1:
                def on_farm_change(e):
                    state["selected_farm"] = e.value
                    state["_update_counter"] = state.get("_update_counter", 0) + 1
                
                ui.select(
                    options=farm_options,
                    value=state.get("selected_farm", farm_options[0]),
                    on_change=on_farm_change
                ).props('dense borderless').style("font-weight:600; font-size:13px; color:#64748b; width:150px; margin-left:10px;")
            else:
                # Chỉ có 1 farm → hiện tĩnh, không cần dropdown
                state["selected_farm"] = farm_options[0]
                ui.label(f"🏡 {farm_options[0]}").style(
                    "font-weight:600; font-size:13px; color:#64748b; margin-left:10px;"
                    "background:#f0fdf4; padding:4px 10px; border-radius:8px;"
                )

        # Status Badge + Notification Bell + User Profile
        with ui.element("div").style("display:inline-flex;align-items:center;gap:16px;"):
            if os.getenv("SMIOT_DEMO_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}:
                ui.label("DEMO · dữ liệu mô phỏng").style(
                    "display:inline-flex;align-items:center;background:#fff7ed;color:#c2410c;"
                    "padding:5px 9px;border-radius:14px;font-size:10px;font-weight:800;letter-spacing:.03em;"
                )
            @ui.refreshable
            def system_status_indicator():
                is_active = state.get("system_is_active", True)
                if is_active:
                    with ui.element("div").style(
                        "display:inline-flex;align-items:center;gap:6px;background:#dcfce7;padding:4px 10px;border-radius:20px;"
                    ):
                        ui.html('<span class="dot dot-green" style="width:6px;height:6px;"></span>')
                        ui.label("ACTIVE").style("color:#16a34a;font-size:10px;font-weight:800;letter-spacing:0.05em;")
                else:
                    with ui.element("div").style(
                        "display:inline-flex;align-items:center;gap:6px;background:#fee2e2;padding:4px 10px;border-radius:20px;"
                    ):
                        ui.html('<span class="dot" style="width:6px;height:6px;background:#ef4444;"></span>')
                        ui.label("OFFLINE").style("color:#ef4444;font-size:10px;font-weight:800;letter-spacing:0.05em;")
            
            system_status_indicator()
            client_id = ui.context.client.id
            if client_id not in client_refreshes:
                client_refreshes[client_id] = []
            if system_status_indicator.refresh not in client_refreshes[client_id]:
                client_refreshes[client_id].append(system_status_indicator.refresh)
            
            # Định nghĩa và chèn chuông thông báo cục bộ cho client
            @ui.refreshable
            def client_bell():
                s = state
                notifications = s.get("notifications", [])
                unread_count = len([n for n in notifications if not n.get("read")])

                with ui.element('div').classes('relative inline-block cursor-pointer group'):
                    # Bell Icon
                    with ui.element('div').classes(
                        'flex items-center justify-center w-10 h-10 rounded-full bg-white shadow-sm border border-slate-200 '
                        'transition-all duration-300 group-hover:shadow-md group-hover:scale-105 group-hover:border-slate-300'
                    ):
                        ui.icon('notifications', size='22px', color='#64748b').classes('transition-colors group-hover:text-slate-800')

                    # Red badge
                    if unread_count > 0:
                        with ui.element('div').classes(
                            'absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold '
                            'min-w-[18px] h-[18px] flex items-center justify-center rounded-full border-2 border-white shadow-sm'
                        ):
                            ui.label(str(unread_count))

                    # Dropdown Menu
                    with ui.menu().classes('w-80 rounded-2xl shadow-xl border border-slate-100 overflow-hidden mt-2 p-0').props('anchor="bottom right" self="top right" auto-close=false'):
                        # Header
                        with ui.element('div').classes('flex justify-between items-center px-4 py-3 bg-slate-50 border-b border-slate-100'):
                            ui.label('Thông báo').classes('font-bold text-slate-800 text-sm')
                            if unread_count > 0:
                                def mark_read():
                                    for n in s.get("notifications", []): n["read"] = True
                                    state["_update_counter"] = state.get("_update_counter", 0) + 1
                                ui.label('Đánh dấu đã đọc').classes(
                                    'text-xs text-blue-500 font-semibold cursor-pointer hover:text-blue-700 transition-colors'
                                ).on('click', mark_read)

                        # Content list
                        with ui.element('div').classes('max-h-[320px] overflow-y-auto p-2'):
                            if not notifications:
                                with ui.element('div').classes('flex flex-col items-center justify-center py-8 opacity-60'):
                                    ui.icon('notifications_off', size='32px', color='#94a3b8').classes('mb-2')
                                    ui.label('Không có thông báo mới').classes('text-sm text-slate-500')
                            else:
                                for notif in notifications:
                                    is_read = notif.get("read", False)
                                    is_err = any(word in notif["text"].lower() for word in ["không", "mất", "cảnh báo", "lỗi", "❌"])
                                    
                                    bg_hover = "hover:bg-slate-50"
                                    bg_base = "bg-white" if is_read else ("bg-red-50/40" if is_err else "bg-green-50/40")
                                    
                                    icon_name = "error_outline" if is_err else "check_circle"
                                    icon_color = "#ef4444" if is_err else "#22c55e"

                                    with ui.element('div').classes(f'flex items-start gap-3 p-3 mb-1 rounded-xl {bg_base} {bg_hover} transition-colors cursor-default'):
                                        ui.icon(icon_name, size='20px', color=icon_color).classes('mt-0.5 shrink-0')
                                        with ui.element('div').classes('flex-1'):
                                            ui.label(notif["text"]).classes(f'text-[13px] leading-tight mb-1 {"font-medium text-slate-800" if not is_read else "text-slate-600"}')
                                            ui.label(notif["time"]).classes('text-[11px] text-slate-400 font-medium')
                                        
                                        # Chấm xanh nhỏ báo chưa đọc (nếu chưa đọc)
                                        if not is_read:
                                            ui.element('div').classes('w-2 h-2 rounded-full bg-blue-500 shrink-0 mt-1.5')

            client_bell()
            if client_bell.refresh not in client_refreshes[client_id]:
                client_refreshes[client_id].append(client_bell.refresh)
            
            # User Profile Dropdown (Option 3.1)
            with ui.element("div").style("display:flex;align-items:center;gap:8px;cursor:pointer;position:relative;") as user_profile:
                ui.image(f"/static/{avatar_file}").style(
                    "width:28px;height:28px;border-radius:50%;object-fit:cover;border:1px solid #e2e8f0;"
                )
                ui.label(fullname).style("font-size:13px;font-weight:600;color:#1a1a2e;")
                
                with ui.menu() as menu:
                    def logout():
                        app.storage.user.clear()
                        ui.navigate.to('/login')
                    ui.menu_item('Đăng xuất', on_click=logout).style("color:#ff4d4f; font-weight:600;")
                
                user_profile.on('click', menu.open)

def sidebar(active="Home"):
    role = app.storage.user.get('role', 'client')
    fullname = app.storage.user.get('fullname', 'User')
    avatar_file = app.storage.user.get('avatar', 'client.png')
    permissions = app.storage.user.get('permissions', [])

    # ── Application Section ──
    nav_links = [
        ("ri-home-4-line", "Home",      "/"),
        ("ri-cpu-line", "Device",    "/devices"),
    ]
    
    # Riêng Projects chỉ admin mới thấy
    if role == "admin":
        nav_links.insert(1, ("ri-folder-open-line", "Projects",  "/projects"))
        
    # Luôn hiện Inverter và PLC
    nav_links.append(("ri-broadcast-line", "Inverter", "/inverter"))
    nav_links.append(("ri-settings-4-line", "PLC",      "/plc"))
    nav_links.append(("ri-calendar-line", "Schedule", "/schedule"))
    nav_links.append(("ri-line-chart-line", "Chart", "/chart"))
    nav_links.append(("ri-table-line", "Data", "/data"))
    nav_links.append(("ri-database-2-line", "Mùa vụ & truy xuất", "/mongodb-lab"))
    
    # ── Administration Section ──
    admin_links = []
    # Riêng Permission chỉ admin mới thấy
    if role == "admin" or "manage_users" in permissions:
        admin_links.append(("ri-key-2-line", "Permission", "/permission"))

    with ui.element("div").classes("sidebar"):
        with ui.element("div").classes("sidebar-logo"):
            ui.image('/static/logo.png').style("width:32px; height:32px; object-fit: contain;")
            ui.label("SMART FARM").style("font-weight:900;font-size:16px;letter-spacing:0.02em;margin-left:8px;color:#1e293b;line-height:1.2")

        for icon, label, url in nav_links:
            cls = f"nav-item {'active' if label == active else ''}"
            
            # Luôn cho phép tất cả các tài khoản vào xem dữ liệu
            with ui.element("a").props(f'href="{url}"').classes(cls):
                ui.html(f'<i class="{icon}"></i><span>{label}</span>')

        # Administration section
        if admin_links:
            ui.label("Administration").classes("sidebar-section").style("margin-top:10px")
            for icon, label, url in admin_links:
                cls = f"nav-item {'active' if label == active else ''}"
                with ui.element("a").props(f'href="{url}"').classes(cls):
                    ui.html(f'<i class="{icon}"></i><span>{label}</span>')
        ui.element("div").style("flex:1")
        
        with ui.element("div").style("padding:16px;text-align:center;border-top:1px solid rgba(241, 245, 249, 0.6);font-size:10px;color:#94a3b8;font-weight:600"):
            ui.label("SMIOT System v2.0").style("margin-bottom:2px;display:block")
            ui.label("© 2026 Smart Farm").style("opacity:0.8;display:block")


def metric_box(label: str, value, unit: str, bar_pct: float = None, bar_color: str = "#4361ee"):
    with ui.element("div").classes("metric-box"):
        ui.label(label).classes("metric-label")
        with ui.element("div").style("display:flex;align-items:baseline;gap:3px"):
            ui.label(str(value)).classes("metric-value")
            ui.label(unit).classes("metric-unit")
        if bar_pct is not None:
            with ui.element("div").classes("progress-bar-bg"):
                pct = max(0, min(100, bar_pct))
                ui.element("div").classes("progress-bar").style(
                    f"width:{pct}%;background:{bar_color}"
                )


def get_trend_icon(k: str, field: str):
    key = f"{k}_{field}"
    curr = state.get(key, 0.0)
    prev = state.get(f"{key}_old", curr)
    try:
        curr_val = float(curr)
        prev_val = float(prev)
        if curr_val > prev_val:
            return " 📈"
        elif curr_val < prev_val:
            return " 📉"
    except Exception:
        pass
    return ""


def node_card(k: str, title: str):
    s = state
    status = s.get(f"{k}_status", "OFFLINE")
    is_offline = status != "ONLINE"
    
    with ui.element("div").classes("card").style("border-top: 4px solid #20bf6b" if not is_offline else "border-top: 4px solid #ef4444"):
        with ui.element("div").classes("card-header"):
            with ui.element("div").classes("card-title"):
                ui.label("🌿").style("font-size:20px")
                ui.label(title).style("font-size:15px;font-weight:700")
            # Pulsating ONLINE/OFFLINE badge
            if not is_offline:
                with ui.element("div").classes("badge badge-online"):
                    ui.html('<span class="dot dot-green"></span>')
                    ui.label("ONLINE")
            else:
                with ui.element("div").classes("badge").style("background:#fee2e2;color:#ef4444"):
                    ui.html('<span class="dot dot-red"></span>')
                    ui.label("OFFLINE")

        if is_offline:
            with ui.column().classes("w-full items-center py-8 text-rose-500"):
                ui.icon("wifi_off", size="40px")
                ui.label("Mất kết nối cảm biến").classes("text-sm font-bold mt-2")
                ui.label("Kiểm tra nguồn/Lora Node").classes("text-xs text-slate-400 text-center")
                ui.label(f"Cập nhật cuối: {s.get(f'{k}_updated', 'Không rõ')}").style("color:#aaa;font-size:11px;margin-top:12px")
            return

        ui.label("KHÔNG KHÍ").classes("sub-section")
        with ui.element("div").classes("metric-grid"):
            air_temp_trend = get_trend_icon(k, "air_temp")
            air_hum_trend = get_trend_icon(k, "air_hum")
            metric_box("NHIỆT ĐỘ", f"{s[f'{k}_air_temp']}{air_temp_trend}", "°C",
                       bar_pct=s[f"{k}_air_temp"] / 50 * 100, bar_color="#f77f00")
            metric_box("ĐỘ ẨM", f"{s[f'{k}_air_hum']}{air_hum_trend}", "%",
                       bar_pct=s[f"{k}_air_hum"], bar_color="#4cc9f0")

        ui.label("ĐẤT TRỒNG").classes("sub-section")
        with ui.element("div").classes("metric-grid"):
            soil_temp_trend = get_trend_icon(k, "soil_temp")
            soil_hum_trend = get_trend_icon(k, "soil_hum")
            metric_box("NHIỆT ĐỘ", f"{s[f'{k}_soil_temp']}{soil_temp_trend}", "°C",
                       bar_pct=s[f"{k}_soil_temp"] / 50 * 100, bar_color="#f77f00")
            metric_box("ĐỘ ẨM", f"{s[f'{k}_soil_hum']}{soil_hum_trend}", "%",
                       bar_pct=s[f"{k}_soil_hum"], bar_color="#2ec4b6")

        with ui.element("div").classes("ec-footer"):
            ui.label(f"⚡ EC: {s[f'{k}_ec']} mS/cm").style(
                "color:#7c3aed;font-size:12px;font-weight:600")
            ui.label(f"🕐 Cập nhật: {s[f'{k}_updated']}").style("color:#aaa;font-size:11px")



def flow_meter_card():
    s = state
    with ui.element("div").classes("card").style(
        "display:flex;flex-direction:column;justify-content:space-between;height:100%"
    ):
        with ui.element("div").classes("card-header"):
            with ui.element("div").classes("card-title"):
                ui.label("⚡").style("font-size:20px;color:#2196f3")
                ui.label("Flow_Meter").style("font-size:15px;font-weight:700")
            # Pulsating LIVE badge
            with ui.element("div").classes("badge badge-live"):
                ui.html('<span class="dot dot-blue"></span>')
                ui.label("LIVE")

        with ui.element("div").classes("flow-lines"):
            for line, val in [("LINE01", s["flow_line1"]), ("LINE02", s["flow_line2"])]:
                with ui.element("div").classes("flow-line-box"):
                    ui.label(line).style("font-size:10px;font-weight:700;color:#aaa;letter-spacing:0.08em")
                    with ui.element("div").style(
                        "display:flex;align-items:baseline;gap:3px;justify-content:center;margin-top:6px"
                    ):
                        ui.label(str(val)).style("font-size:24px;font-weight:700;color:#1a1a2e")
                        ui.label("L/m").style("font-size:12px;color:#aaa")

        with ui.element("div").classes("flow-total-box"):
            ui.label("📊").style("font-size:18px")
            with ui.element("div"):
                ui.label("TỔNG LƯU LƯỢNG HIỆN TẠI").style(
                    "font-size:9px;color:rgba(255,255,255,0.5);font-weight:700;letter-spacing:0.08em")
                with ui.element("div").style("display:flex;align-items:baseline;gap:4px"):
                    ui.label(str(s["flow_total"])).classes("flow-total-val")
                    ui.label("L").style("font-size:14px;color:rgba(255,255,255,0.5)")
            ui.label("⇄").style("color:rgba(255,255,255,0.3);font-size:18px")

        with ui.element("div").style(
            "display:flex;justify-content:space-between;margin-top:12px;"
            "padding-top:10px;border-top:1px solid #f0f0f0"
        ):
            ui.label(f"🕐 Update: {s['flow_updated']}").style("font-size:11px;color:#aaa")
            ui.label(f"S/N: {s['flow_serial']}").style("font-size:11px;color:#aaa")


def ec_card():
    s = state
    # Lấy trạng thái online của EC
    status = "ONLINE" if s.get("ec_online", 1) == 1 else "OFFLINE"
    is_offline = status != "ONLINE"
    
    with ui.element("div").classes("card").style("border-top: 4px solid #7c3aed" if not is_offline else "border-top: 4px solid #ef4444"):
        with ui.element("div").classes("card-header"):
            with ui.element("div").classes("card-title"):
                ui.label("⚡").style("font-size:20px;color:#7c3aed")
                ui.label("Cảm Biến EC").style("font-size:15px;font-weight:700")
            # Pulsating badge
            if not is_offline:
                with ui.element("div").classes("badge badge-online"):
                    ui.html('<span class="dot dot-green"></span>')
                    ui.label("ONLINE")
            else:
                with ui.element("div").classes("badge").style("background:#fee2e2;color:#ef4444"):
                    ui.html('<span class="dot dot-red"></span>')
                    ui.label("OFFLINE")
                    
        if is_offline:
            with ui.column().classes("w-full items-center py-8 text-rose-500"):
                ui.icon("wifi_off", size="40px")
                ui.label("Mất kết nối cảm biến EC").classes("text-sm font-bold mt-2")
                ui.label(f"Cập nhật cuối: {s.get('ec_updated', 'Không rõ')}").style("color:#aaa;font-size:11px;margin-top:12px")
            return
            
        ui.label("THÔNG SỐ EC").classes("sub-section")
        with ui.element("div").classes("metric-grid"):
            metric_box("ĐỘ DẪN ĐIỆN", f"{s.get('ec_val', 0.0):.2f}", "mS/cm",
                       bar_pct=s.get('ec_val', 0.0) / 5.0 * 100, bar_color="#7c3aed")
            metric_box("ĐIỆN ÁP", f"{s.get('ec_v', 0.0):.2f}", "V",
                       bar_pct=s.get('ec_v', 0.0) / 5.0 * 100, bar_color="#3b82f6")
                       
        with ui.element("div").style("display:flex;justify-content:space-between;margin-top:12px;padding-top:10px;border-top:1px solid #f0f0f0"):
            ui.label(f"Raw: {s.get('ec_raw', 0)}").style("font-size:11px;color:#aaa")
            ui.label(f"🕐 Cập nhật: {s.get('ec_updated', '')}").style("font-size:11px;color:#aaa")


def ph_card():
    s = state
    # Lấy trạng thái online của pH
    status = "ONLINE" if s.get("ph_online", 1) == 1 else "OFFLINE"
    is_offline = status != "ONLINE"
    
    with ui.element("div").classes("card").style("border-top: 4px solid #10b981" if not is_offline else "border-top: 4px solid #ef4444"):
        with ui.element("div").classes("card-header"):
            with ui.element("div").classes("card-title"):
                ui.label("🧪").style("font-size:20px;color:#10b981")
                ui.label("Cảm Biến pH").style("font-size:15px;font-weight:700")
            # Pulsating badge
            if not is_offline:
                with ui.element("div").classes("badge badge-online"):
                    ui.html('<span class="dot dot-green"></span>')
                    ui.label("ONLINE")
            else:
                with ui.element("div").classes("badge").style("background:#fee2e2;color:#ef4444"):
                    ui.html('<span class="dot dot-red"></span>')
                    ui.label("OFFLINE")
                    
        if is_offline:
            with ui.column().classes("w-full items-center py-8 text-rose-500"):
                ui.icon("wifi_off", size="40px")
                ui.label("Mất kết nối cảm biến pH").classes("text-sm font-bold mt-2")
                ui.label(f"Cập nhật cuối: {s.get('ph_updated', 'Không rõ')}").style("color:#aaa;font-size:11px;margin-top:12px")
            return
            
        ui.label("THÔNG SỐ PH").classes("sub-section")
        with ui.element("div").classes("metric-grid"):
            metric_box("ĐỘ pH", f"{s.get('ph_val', 7.0):.2f}", "pH",
                       bar_pct=s.get('ph_val', 7.0) / 14.0 * 100, bar_color="#10b981")
            metric_box("ĐIỆN ÁP MV", f"{s.get('ph_mv', 0.0):.1f}", "mV",
                       bar_pct=abs(s.get('ph_mv', 0.0)) / 1000.0 * 100, bar_color="#f59e0b")
                       
        with ui.element("div").style("display:flex;justify-content:space-between;margin-top:12px;padding-top:10px;border-top:1px solid #f0f0f0"):
            ui.label(f"Raw: {s.get('ph_raw', 0)}").style("font-size:11px;color:#aaa")
            ui.label(f"🕐 Cập nhật: {s.get('ph_updated', '')}").style("font-size:11px;color:#aaa")


def weather_card(on_refresh=None):
    s = state
    with ui.element("div").classes("weather-card"):
        with ui.element("div").style("display:flex;align-items:flex-start;justify-content:space-between"):
            with ui.element("div"):
                ui.label(s["weather_city"]).style("font-size:20px;font-weight:700;color:white")
                ui.label(f"Vị trí: {s['weather_lat']}, {s['weather_lng']}").style(
                    "font-size:11px;color:rgba(255,255,255,0.65);margin-top:3px")
            # Live badge with pulsating blue dot
            with ui.element("div").style(
                "background:rgba(255,255,255,0.2);padding:4px 10px;border-radius:20px;"
                "display:inline-flex;align-items:center;gap:6px"
            ):
                ui.html('<span class="dot dot-blue"></span>')
                ui.label("Live").style("font-size:11px;font-weight:700;color:white")

        ui.label("DỰ BÁO 3 GIỜ TỚI").style(
            "font-size:10px;color:rgba(255,255,255,0.7);font-weight:700;"
            "letter-spacing:0.08em;margin-top:14px;margin-bottom:8px")
        
        now = datetime.now()
        with ui.element("div").classes("weather-hourly"):
            for hour, temp, rain in [
                ((now + timedelta(hours=1)).strftime("%H:00"), s["weather_10h_temp"], s["weather_10h_rain"]),
                ((now + timedelta(hours=2)).strftime("%H:00"), s["weather_11h_temp"], s["weather_11h_rain"]),
                ((now + timedelta(hours=3)).strftime("%H:00"), s["weather_12h_temp"], s["weather_12h_rain"]),
            ]:
                with ui.element("div").classes("weather-hour-box"):
                    ui.label(hour).style("font-size:11px;color:rgba(255,255,255,0.8);font-weight:600")
                    ui.label(f"{temp}°").style("font-size:18px;font-weight:700;color:white;margin:4px 0")
                    ui.label(f"💧 {rain}%").style("font-size:11px;color:rgba(255,255,255,0.8)")

        ui.label("CHỈ SỐ TỔNG HỢP NGÀY").style(
            "font-size:10px;color:rgba(255,255,255,0.7);font-weight:700;"
            "letter-spacing:0.08em;margin-bottom:8px")
        with ui.element("div").classes("weather-daily-stats"):
            with ui.element("div"):
                ui.label("Bức xạ mặt trời").style("font-size:10px;color:rgba(255,255,255,0.7);font-weight:600")
                ui.label(f"{s['weather_solar']:,} W/m²").style("font-size:14px;font-weight:700;color:#ffd166")
            with ui.element("div"):
                ui.label("Thoát hơi nước (ETO)").style("font-size:10px;color:rgba(255,255,255,0.7);font-weight:600")
                ui.label(f"{s['weather_eto']} mm").style("font-size:14px;font-weight:700;color:#a8dadc")

        # Nút refresh thời tiết bằng tay
        def refresh_weather():
            ui.notify('Đang tải dữ liệu thời tiết...', color='info')
            if on_refresh:
                on_refresh()
            
        ui.label("Làm mới dữ liệu").style(
            "display:block;text-align:center;margin-top:12px;"
            "font-size:12px;color:rgba(255,255,255,0.8);cursor:pointer;text-decoration:underline"
        ).on('click', refresh_weather)


def ai_analysis_card():
    s = state
    with ui.element("div").classes("ai-card"):
        ui.label("🤖  Dự đoán từ AI").style("font-size:15px;font-weight:700;color:white;margin-bottom:14px")
        with ui.element("div").style("display:flex;align-items:center;gap:8px;margin-bottom:10px"):
            ui.label("💧").style("font-size:16px")
            ui.label("Lượng nước đề xuất").style("font-size:13px;color:rgba(255,255,255,0.7)")
            ui.label(f"{s['ai_water_suggest']} ml").style(
                "font-size:18px;font-weight:700;color:#2ec4b6;margin-left:4px")

        with ui.element("div").style("display:flex;align-items:center;gap:8px"):
            ui.label("Trạng thái Van :").style("font-size:13px;color:rgba(255,255,255,0.6)")
            ui.element("div").style(
                f"padding:4px 14px;background:{'#20bf6b' if s['van_status'] == 1 else '#555'};"
                f"border-radius:20px;color:white;font-size:12px;font-weight:700")
            ui.label("Đang tưới" if s["van_status"] == 1 else "Không tưới")

        ui.label(s["ai_time"]).style("font-size:11px;color:rgba(255,255,255,0.4);margin-top:14px")


def inverter_summary_card():
    s = state
    is_run = s["inv_status"] == 1
    with ui.element("div").classes("card"):
        with ui.element("div").classes("card-header"):
            with ui.element("div").classes("card-title"):
                ui.label("🔌").style("font-size:20px")
                ui.label("Inverter Status").style("font-size:15px;font-weight:700")
            with ui.element("div").classes("badge badge-online" if is_run else "badge").style(
                "" if is_run else "background:#f1f5f9;color:#94a3b8"
            ):
                ui.html('<span class="dot dot-green"></span>' if is_run else
                        '<span class="dot" style="background:#94a3b8"></span>')
                ui.label("RUNNING" if is_run else "STOPPED")
        
        with ui.element("div").classes("metric-grid"):
            metric_box("TẦN SỐ", s["inv_hz"], "Hz", bar_pct=s["inv_hz"]/50*100, bar_color="#facc15")
            metric_box("ÁP SUẤT", s["inv_p_cur"], "BAR", bar_pct=s["inv_p_cur"]/2*100, bar_color="#3b82f6")
        
        with ui.element("div").classes("ec-footer"):
            ui.label(f"⚡ V_IN: {s['inv_v_in']}V").style("color:#4361ee;font-size:12px;font-weight:600")
            ui.label(f"🕐 {s['inv_updated']}").style("color:#aaa;font-size:11px")

def ph_ec_card():
    s = state
    with ui.element("div").classes("card"):
        with ui.element("div").classes("card-header"):
            with ui.element("div").classes("card-title"):
                ui.label("🧪").style("font-size:20px")
                ui.label("Chỉ số Nước (PH/EC)").style("font-size:15px;font-weight:700")
        
        with ui.element("div").classes("metric-grid"):
            # PH box
            with ui.element("div").classes("metric-box"):
                ui.label("ĐỘ PH").classes("metric-label")
                with ui.element("div").style("display:flex;align-items:baseline;gap:3px"):
                    ui.label(str(s["ph_value"])).classes("metric-value").style("color:#059669")
                with ui.element("div").classes("progress-bar-bg"):
                    pct = (s["ph_value"] / 14) * 100
                    ui.element("div").classes("progress-bar").style(f"width:{pct}%;background:#059669")
            
            # EC box (from id4)
            metric_box("ĐỘ DẪN EC", s["node1_ec"], "mS/cm", bar_pct=s["node1_ec"]/5*100, bar_color="#7c3aed")


def farm_status_header():
    s = state
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    # Lấy thông tin lịch tưới tiếp theo và tổng nước thực tế hôm nay
    schedules = auth.get_schedules("greenhouse_a", date=today_str)
    
    # Tính tổng nước thực tế hôm nay từ schedule_logs
    try:
        total_water_today = auth.get_total_actual_water("greenhouse_a", today_str)
    except Exception:
        total_water_today = 0.0
        
    pending_scheds = [sch for sch in schedules if sch["status"] == "pending" and sch["start_time"] > now.strftime("%H:%M")]
    
    next_irrigation = "Không có"
    if pending_scheds:
        sch = pending_scheds[0]
        try:
            start_dt = datetime.strptime(sch["start_time"], "%H:%M")
            end_dt = start_dt + timedelta(minutes=float(sch["water_amount"]))
            next_irrigation = f"{sch['start_time']}-{end_dt.strftime('%H:%M')} ({sch['water_amount']:.0f}p)"
        except Exception:
            next_irrigation = f"{sch['start_time']} ({sch['water_amount']:.0f}p)"
    else:
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        tomorrow_scheds = auth.get_schedules("greenhouse_a", date=tomorrow_str)
        if tomorrow_scheds:
            sch = tomorrow_scheds[0]
            try:
                start_dt = datetime.strptime(sch["start_time"], "%H:%M")
                end_dt = start_dt + timedelta(minutes=float(sch["water_amount"]))
                next_irrigation = f"Mai {sch['start_time']}-{end_dt.strftime('%H:%M')} ({sch['water_amount']:.0f}p)"
            except Exception:
                next_irrigation = f"Mai {sch['start_time']} ({sch['water_amount']:.0f}p)"

    # Đếm số cảnh báo vật lý đang hoạt động thực tế
    active_warnings = 0
    if not s.get("system_is_active", True):
        active_warnings += 1
    else:
        if s.get("node1_status") == "OFFLINE":
            active_warnings += 1
        if s.get("node2_status") == "OFFLINE":
            active_warnings += 1
            
    if s.get("plc_online", 0) != 1:
        active_warnings += 1
    else:
        # Nếu PLC online, kiểm tra lệch tiếp điểm bơm
        for i in range(8):
            if s.get(f"bit{i}", 0) != s.get(f"q{i}", 0):
                active_warnings += 1
                
    if s.get("inv_online", 1) != 1:
        active_warnings += 1

    # Trạng thái Gateway
    gateway_online = s.get("system_is_active", True)
    gateway_status_text = "Trực tuyến" if gateway_online else "Mất kết nối"
    gateway_class = "dot-green" if gateway_online else "dot-red"
    
    # Trạng thái PLC
    plc_online = s.get("plc_online", 0) == 1
    plc_status_text = "Trực tuyến" if plc_online else "Ngoại tuyến"
    plc_class = "dot-green" if plc_online else "dot-red"

    # Trạng thái Inverter
    inv_running = s.get("inv_status", 0) == 1
    inv_online = s.get("inv_online", 1) == 1
    inv_status_text = "Đang chạy" if (inv_online and inv_running) else ("Đang dừng" if inv_online else "Ngoại tuyến")
    inv_class = "dot-green" if (inv_online and inv_running) else ("dot-yellow" if inv_online else "dot-red")

    # Trạng thái Lora Node 1 & 2
    node1_status = s.get("node1_status", "OFFLINE")
    node1_online = node1_status == "ONLINE"
    node1_status_text = "Trực tuyến" if node1_online else "Ngoại tuyến"
    node1_class = "dot-green" if node1_online else "dot-red"

    # Trạng thái Node 2
    node2_status = s.get("node2_status", "OFFLINE")
    node2_online = node2_status == "ONLINE"
    node2_status_text = "Trực tuyến" if node2_online else "Ngoại tuyến"
    node2_class = "dot-green" if node2_online else "dot-red"

    with ui.element("div").classes(
        "w-full bg-white/80 backdrop-blur-md border border-slate-100 rounded-2xl shadow-sm p-4 mb-5 "
        "flex flex-wrap lg:flex-nowrap items-center justify-between gap-4"
    ):
        # Trạng thái hệ thống (Các nodes & Thiết bị)
        with ui.row().classes("flex-wrap items-center gap-6 divide-x divide-slate-100"):
            # Gateway
            with ui.row().classes("items-center gap-2.5"):
                ui.html("🌐").style("font-size:16px")
                with ui.column().classes("gap-0.5"):
                    ui.label("GATEWAY").style("font-size:9px; font-weight:800; color:#94a3b8; letter-spacing:0.05em")
                    with ui.row().classes("items-center gap-1.5"):
                        ui.html(f'<span class="dot {gateway_class}"></span>')
                        ui.label(gateway_status_text).style("font-size:12px; font-weight:700; color:#1a1a2e")
            
            # PLC
            with ui.row().classes("items-center gap-2.5 pl-6"):
                ui.html("⚙️").style("font-size:16px")
                with ui.column().classes("gap-0.5"):
                    ui.label("PLC SIEMENS").style("font-size:9px; font-weight:800; color:#94a3b8; letter-spacing:0.05em")
                    with ui.row().classes("items-center gap-1.5"):
                        ui.html(f'<span class="dot {plc_class}"></span>')
                        ui.label(plc_status_text).style("font-size:12px; font-weight:700; color:#1a1a2e")

            # Inverter
            with ui.row().classes("items-center gap-2.5 pl-6"):
                ui.html("🔌").style("font-size:16px")
                with ui.column().classes("gap-0.5"):
                    ui.label("BIẾN TẦN GD20").style("font-size:9px; font-weight:800; color:#94a3b8; letter-spacing:0.05em")
                    with ui.row().classes("items-center gap-1.5"):
                        ui.html(f'<span class="dot {inv_class}"></span>')
                        ui.label(inv_status_text).style("font-size:12px; font-weight:700; color:#1a1a2e")

            # Node Lora 1
            with ui.row().classes("items-center gap-2.5 pl-6"):
                ui.html("📡").style("font-size:16px")
                with ui.column().classes("gap-0.5"):
                    ui.label("NODE 1").style("font-size:9px; font-weight:800; color:#94a3b8; letter-spacing:0.05em")
                    with ui.row().classes("items-center gap-1.5"):
                        ui.html(f'<span class="dot {node1_class}"></span>')
                        ui.label(node1_status_text).style("font-size:12px; font-weight:700; color:#1a1a2e")

            # Node Lora 2
            with ui.row().classes("items-center gap-2.5 pl-6"):
                ui.html("📡").style("font-size:16px")
                with ui.column().classes("gap-0.5"):
                    ui.label("NODE 2").style("font-size:9px; font-weight:800; color:#94a3b8; letter-spacing:0.05em")
                    with ui.row().classes("items-center gap-1.5"):
                        ui.html(f'<span class="dot {node2_class}"></span>')
                        ui.label(node2_status_text).style("font-size:12px; font-weight:700; color:#1a1a2e")

        # Thông tin Lịch tưới & Cảnh báo (Phía bên phải thanh bar)
        with ui.row().classes("items-center gap-4 flex-wrap lg:flex-nowrap"):
            # Tổng nước hôm nay
            with ui.element("div").classes("bg-emerald-50/60 border border-emerald-100/50 rounded-xl px-3 py-1.5 flex items-center gap-2"):
                ui.icon("water_drop", color="emerald-500").style("font-size:16px")
                with ui.column().classes("gap-0"):
                    ui.label("TỔNG NƯỚC HÔM NAY").style("font-size:8px; font-weight:800; color:#059669; letter-spacing:0.05em")
                    ui.label(f"{total_water_today:.0f} Lít").style("font-size:11px; font-weight:700; color:#064e3b")

            # Lịch tưới tiếp theo
            with ui.element("div").classes("bg-blue-50/60 border border-blue-100/50 rounded-xl px-3 py-1.5 flex items-center gap-2"):
                ui.html("⏰").style("font-size:14px")
                with ui.column().classes("gap-0"):
                    ui.label("LỊCH TIẾP THEO").style("font-size:8px; font-weight:800; color:#3b82f6; letter-spacing:0.05em")
                    ui.label(next_irrigation).style("font-size:11px; font-weight:700; color:#1d4ed8")

            # Số cảnh báo hoạt động
            with ui.element("div").classes("bg-rose-50/60 border border-rose-100/50 rounded-xl px-3 py-1.5 flex items-center gap-2"):
                ui.html("⚠️").style("font-size:14px")
                with ui.column().classes("gap-0"):
                    ui.label("CẢNH BÁO").style("font-size:8px; font-weight:800; color:#f43f5e; letter-spacing:0.05em")
                    if active_warnings > 0:
                        ui.label(f"{active_warnings} Đang có").style("font-size:11px; font-weight:800; color:#e11d48")
                    else:
                        ui.label("Ổn định").style("font-size:11px; font-weight:700; color:#16a34a")


# (Đã loại bỏ Trung tâm hành động màu vàng theo yêu cầu)


# ─────────────────────────────────────────────
# PAGE DEFINITION
# ─────────────────────────────────────────────
@ui.page("/")
def trang_chu():
    if not check_login(): return

    # --- Định nghĩa các hàm logic và Timer (Đặt ở đầu trang, ngoài mọi container) ---
    def fetch_weather():
        client = WeatherAPIClient()
        res = client.get_weather_data()
        if res.get("status") == "success":
            d = res["data"]
            state["weather_lat"] = str(d["lat"])
            state["weather_lng"] = str(d["lon"])
            state["weather_solar"] = d["total_radiation_day"]
            state["weather_eto"] = d["total_et0_day"]
            state["weather_10h_temp"] = d["t1h"]
            state["weather_10h_rain"] = d["h1h"]
            state["weather_11h_temp"] = d["t2h"]
            state["weather_11h_rain"] = d["h2h"]
            state["weather_12h_temp"] = d["t3h"]
            state["weather_12h_rain"] = d["h3h"]
            render_content_area.refresh()

    def check_ui_update():
        if not hasattr(check_ui_update, "last_counter"):
            check_ui_update.last_counter = 0

        import time
        from datetime import datetime
        last_seen = state.get("system_last_seen", time.time())
        gateway_timeout = (time.time() - last_seen) > 600

        if gateway_timeout:
            if state.get("system_is_active", True):
                state["system_is_active"] = False
                state["node1_status"] = "OFFLINE"
                state["node2_status"] = "OFFLINE"
                if "notifications" not in state: state["notifications"] = []
                text = "Hệ thống gateway không nhận được phản hồi"
                if not state["notifications"] or state["notifications"][0]["text"] != text:
                    state["notifications"].insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "text": text})
                state["_update_counter"] = state.get("_update_counter", 0) + 1
        else:
            if not state.get("system_is_active", True):
                state["system_is_active"] = True
                if "notifications" not in state: state["notifications"] = []
                text = "Hệ thống đã hoạt động trở lại"
                if not state["notifications"] or state["notifications"][0]["text"] != text:
                    state["notifications"].insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "text": text})
                state["_update_counter"] = state.get("_update_counter", 0) + 1

            # Kiểm tra 600s (10 phút) timeout của các Lora Nodes khi Gateway vẫn hoạt động
            node1_last = state.get("node1_last_change_time")
            node2_last = state.get("node2_last_change_time")

            node1_timeout = (time.time() - node1_last) > 600 if node1_last else False
            node2_timeout = (time.time() - node2_last) > 600 if node2_last else False

            if node1_timeout and node2_timeout:
                n1_changed = state.get("node1_status") != "OFFLINE"
                n2_changed = state.get("node2_status") != "OFFLINE"
                if n1_changed or n2_changed:
                    state["node1_status"] = "OFFLINE"
                    state["node2_status"] = "OFFLINE"
                    if "notifications" not in state: state["notifications"] = []
                    text = "⚠️ Node 1 và Node 2 mất kết nối đồng thời"
                    if not state["notifications"] or state["notifications"][0]["text"] != text:
                        state["notifications"].insert(0, {
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "text": text
                        })
                    state["_update_counter"] = state.get("_update_counter", 0) + 1
            else:
                for k in ["node1", "node2"]:
                    node_status_key = f"{k}_status"
                    node_last = node1_last if k == "node1" else node2_last
                    is_timeout = (time.time() - node_last) > 600 if node_last else False
                    if is_timeout:
                        if state.get(node_status_key) != "OFFLINE":
                            state[node_status_key] = "OFFLINE"
                            if "notifications" not in state: state["notifications"] = []
                            node_label = "Node Cảm Biến 1" if k == "node1" else "Node Cảm Biến 2"
                            text = f"⚠️ {node_label} mất kết nối hoặc dữ liệu bị đóng băng (Pin yếu)"
                            if not state["notifications"] or state["notifications"][0]["text"] != text:
                                state["notifications"].insert(0, {
                                    "time": datetime.now().strftime("%H:%M:%S"),
                                    "text": text
                                })
                            state["_update_counter"] = state.get("_update_counter", 0) + 1

        current_counter = state.get("_update_counter", 0)
        
        if current_counter != check_ui_update.last_counter:
            # Lưu lại trạng thái trước khi refresh để tính toán xu hướng
            for k in ["node1", "node2"]:
                for field in ["air_temp", "air_hum", "soil_temp", "soil_hum"]:
                    key = f"{k}_{field}"
                    prev_key = f"{key}_prev"
                    if key in state:
                        if prev_key not in state:
                            state[prev_key] = state[key]
                        elif state[key] != state[prev_key]:
                            state[f"{key}_old"] = state[prev_key]
                            state[prev_key] = state[key]

            check_ui_update.last_counter = current_counter
            render_content_area.refresh()
            client_id = ui.context.client.id
            if client_id in client_refreshes:
                for refresh_func in client_refreshes[client_id]:
                    try:
                        refresh_func()
                    except Exception as e:
                        pass

    # Khởi tạo các timer
    t1 = ui.timer(0.5, fetch_weather, once=True)
    t2 = ui.timer(3600.0, fetch_weather)
    t3 = ui.timer(2.0, check_ui_update)
    ui.context.client.on_disconnect(lambda: (t1.deactivate(), t2.deactivate(), t3.deactivate()))

    ui.add_head_html(f"<style>{CUSTOM_CSS}</style>")
    sidebar(active="Home")

    with ui.element("div").classes("main-content"):

        # Gọi Topbar dùng chung
        global_topbar("Smart Monitoring", "📊")

        with ui.element("div").classes("content-area"):
            with ui.element("div").style("display:flex;flex-direction:column;gap:20px;width:100%"):
                # (Đã di chuyển fetch_weather lên đầu)

                @ui.refreshable
                def render_content_area():
                        selected = state.get("selected_farm", "Greenhouse A")
                        
                        # Nếu không phải Greenhouse A → hiện overlay "Chưa có dữ liệu"
                        if selected != "Greenhouse A":
                            with ui.element("div").style(
                                "display:flex;flex-direction:column;align-items:center;justify-content:center;"
                                "min-height:400px;background:white;border-radius:16px;border:1px solid #e2e8f0;"
                                "padding:60px 40px;text-align:center;width:100%"
                            ):
                                ui.label("📡").style("font-size:64px;margin-bottom:20px;opacity:0.4")
                                ui.label(f"{selected}").style(
                                    "font-size:22px;font-weight:800;color:#1a1a2e;margin-bottom:8px"
                                )
                                ui.label("Chưa có dữ liệu cảm biến").style(
                                    "font-size:16px;font-weight:600;color:#94a3b8;margin-bottom:16px"
                                )
                                with ui.element("div").style(
                                    "background:#f8fafc;border-radius:12px;padding:16px 24px;"
                                    "border:1px dashed #e2e8f0;max-width:420px"
                                ):
                                    ui.label(
                                        "Hệ thống đang chờ kết nối Gateway cho farm này. "
                                        "Hiện tại chỉ Greenhouse A đang hoạt động và có dữ liệu MQTT."
                                    ).style("font-size:13px;color:#64748b;line-height:1.6")
                            return
                        
                        # === Greenhouse A — Hiện dữ liệu thật ===
                        farm_status_header()
                        
                        with ui.element("div").classes("main-grid"):
                            with ui.column().style("gap:10px"):
                                ui.label("📡  CẢM BIẾN NODE 1").classes("section-header").style("color:#20bf6b;margin-bottom:0")
                                node_card("node1", "Node 1")
                            with ui.column().style("gap:10px"):
                                ui.label("📡  CẢM BIẾN NODE 2").classes("section-header").style("color:#20bf6b;margin-bottom:0")
                                node_card("node2", "Node 2")
                            with ui.column().style("gap:10px"):
                                ui.label("⚡  LƯU LƯỢNG").classes("section-header").style("color:#4361ee;margin-bottom:0")
                                flow_meter_card()
                            with ui.column().style("gap:10px"):
                                ui.label("⚡  CẢM BIẾN EC").classes("section-header").style("color:#7c3aed;margin-bottom:0")
                                ec_card()
                            with ui.column().style("gap:10px"):
                                ui.label("🧪  CẢM BIẾN pH").classes("section-header").style("color:#10b981;margin-bottom:0")
                                ph_card()
                            with ui.column().style("gap:10px"):
                                ui.label("☁️  THỜI TIẾT").classes("section-header").style("color:#f77f00;margin-bottom:0")
                                weather_card(on_refresh=fetch_weather)

                        # Row 2: AI Analysis
                        with ui.element("div").classes("w-full").style("margin-top:20px"):
                            with ui.column().classes("w-full").style("gap:10px"):
                                ui.label("🤖  AI ANALYSIS").classes("section-header").style("color:#7c3aed;margin-bottom:0")
                                ai_analysis_card()

                render_content_area()
            
            # (Đã di chuyển check_ui_update lên đầu)
