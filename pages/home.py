from nicegui import ui, app
from pages.login import check_login
from service import auth
from typing import Set, Callable
import asyncio
import os
from datetime import datetime, timedelta, timezone

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
        padding-left: 0;
        padding-bottom: 80px;
        height: 100vh;
        height: 100dvh;
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
        justify-content: flex-start;
        align-items: center;
        padding: 0;
        overflow-x: auto;
        overflow-y: hidden;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: none;
        background: rgba(255, 255, 255, 0.85);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
    }
    .sidebar::-webkit-scrollbar { display: none; }
    .sidebar-logo, .sidebar-section, .sidebar > div:last-child, .sidebar > div:empty {
        display: none !important;
    }
    .nav-item {
        margin: 0;
        padding: 6px 4px;
        font-size: 11px;
        flex: 0 0 auto;
        min-width: 64px;
        min-height: 48px;
        flex-direction: column;
        gap: 1px;
        text-align: center;
        justify-content: center;
        border-radius: 6px;
        white-space: nowrap;
    }
    .nav-item > div {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 1px;
    }
    .nav-item span { font-size: 11px; }
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
    .top-bar { flex-wrap: wrap !important; gap: 8px; padding: 8px 12px !important; }
    .top-bar .q-field { width: 120px !important; margin-left: 0 !important; }
    .top-bar-title { flex-wrap: wrap; min-width: 0; gap: 8px !important; }
    .top-bar > div:last-child { gap: 8px !important; flex-wrap: wrap; justify-content: flex-end; }
    .content-area { padding: 12px !important; }
}

/* Bảng rộng: cuộn ngang trong khung, không làm tràn trang */
.tbl-scroll { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }

@media (max-width: 480px) {
    .q-menu { max-width: 94vw !important; }
    .flow-lines { grid-template-columns: 1fr; }
    .weather-hourly { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (hover: none) {
    .card:hover, .weather-card:hover, .ai-card:hover { transform: none; }
}

/* Home control room: a fleet dashboard first, individual controls on demand. */
.farm-control-room { width:100%; color:#263d32; }
.farm-control-hero {
    display:flex; align-items:center; justify-content:space-between; gap:18px;
    min-height:116px; padding:22px 26px; color:#f4fbf5;
    background:#173d31; border-radius:16px 16px 0 0;
    border-left:5px solid #8ccf72;
}
.farm-control-title { font-size:25px; line-height:1.15; font-weight:800; color:#fff; }
.farm-control-subtitle { max-width:620px; font-size:13px; line-height:1.5; color:#c7d9cd; }
.farm-control-count { text-align:right; font-size:21px; line-height:1.1; font-weight:800; color:#d7f1c5; }
.farm-control-updated { text-align:right; font-size:10px; color:#c0d1c6; }
.farm-kpi-strip {
    display:grid; grid-template-columns:repeat(5,minmax(0,1fr));
    border:1px solid #e2e9e3; border-top:0; background:#fff;
}
.farm-kpi { min-width:0; padding:13px 16px; border-right:1px solid #e8ede9; }
.farm-kpi:last-child { border-right:0; }
.farm-kpi-label { color:#738178; font-size:10px; font-weight:700; }
.farm-kpi-detail { color:#89948e; font-size:10px; }
.farm-overview-grid {
    display:grid; grid-template-columns:minmax(0,1.25fr) minmax(390px,1fr);
    gap:14px; align-items:start; padding-top:14px;
}
.farm-overview-charts, .farm-overview-list { width:100%; min-width:0; gap:12px; }
.farm-section-title { font-size:15px; font-weight:800; color:#263d32; }
.farm-chart-note { color:#849188; font-size:10px; line-height:1.4; }
.farm-overview-error { display:block; padding:18px; color:#9b3930; }
.farm-active-incidents { display:flex; flex-direction:column; gap:5px; padding:12px 14px; background:#fff5f1; border-left:3px solid #c85b49; border-radius:8px; color:#8d342c; }
.farm-detail-back { margin:0 0 4px 0; color:#397551; font-weight:700; }
.farm-detail-heading { font-size:20px; font-weight:800; color:#203b2d; }
@media (max-width: 1100px) {
    .farm-overview-grid { grid-template-columns:minmax(0,1fr); }
    .farm-overview-list { order:-1; }
}
@media (max-width: 760px) {
    .farm-control-hero { min-height:0; padding:18px; align-items:flex-start; }
    .farm-control-title { font-size:21px; }
    .farm-control-subtitle { font-size:12px; }
    .farm-control-count { font-size:18px; }
    .farm-kpi-strip { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .farm-kpi { padding:10px 12px; border-bottom:1px solid #e8ede9; }
    .farm-kpi:nth-child(2n) { border-right:0; }
    .farm-overview-grid { gap:10px; }
}
@media (max-width: 480px) {
    .farm-control-hero { flex-direction:column; gap:10px; }
    .farm-control-count, .farm-control-updated { text-align:left; }
    .farm-kpi-strip { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .farm-overview-grid > div { width:100%; }
}
"""

# Fonts first (an @import must lead the sheet), theme last so it replaces the legacy look.
from components.theme import THEME_CSS, THEME_FONTS
CUSTOM_CSS = THEME_FONTS + CUSTOM_CSS + THEME_CSS

# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
refresh_callbacks: Set[Callable] = set()

import time

state = {
    "system_last_seen": time.time(),
    # UNKNOWN until a real sample is seen in MongoDB (never assume ONLINE).
    "node1_status": "UNKNOWN",
    "node1_air_temp": 30.3,
    "node1_air_hum": 65.3,
    "node1_soil_temp": 26.0,
    "node1_soil_hum": 50.0,
    "node1_ec": 1.4,
    "node1_updated": "11:23:15",

    "node2_status": "UNKNOWN",
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

    "ai_water_suggest": None,  # None = chưa có dữ liệu/AI lỗi (khác 0 ml hợp lệ)
    "ai_status": "no_data",  # ok | no_water | no_data | provider_error
    "ai_reason": "",
    "van_status": 0,  # 0: Không tưới, 1: Tưới
    "ai_time": "",  # rỗng = chưa nhận dự đoán nào từ AI (không dùng giờ giả)

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
def global_topbar(title, emoji="📊", show_farm_selector=True):
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
    
    label_to_key = {f[1]: f[0] for f in FIXED_FARMS}

    def remember_farm(label):
        # Per-user copy of the choice (farm key) for pages that read app.storage.user.
        try:
            app.storage.user['current_farm'] = label_to_key.get(label, 'greenhouse_a')
        except Exception:
            pass

    with ui.element("div").classes("top-bar"):
        with ui.element("div").classes("top-bar-title").style("display:flex; align-items:center;"):
            # Tiêu đề trang
            ui.label(title).classes("sm-page-title")

            # Dropdown chọn farm (các màn khác); Home có lối vào/ra farm riêng để khỏi lệch lựa chọn.
            if show_farm_selector and len(farm_options) > 1:
                if state.get("selected_farm") not in farm_options:
                    state["selected_farm"] = farm_options[0]
                remember_farm(state["selected_farm"])

                def on_farm_change(e):
                    state["selected_farm"] = e.value
                    remember_farm(e.value)
                    state["_update_counter"] = state.get("_update_counter", 0) + 1

                ui.select(
                    options=farm_options,
                    value=state.get("selected_farm", farm_options[0]),
                    on_change=on_farm_change
                ).props('dense borderless aria-label="Chọn nhà màng"').classes("sm-farm-pick")
            elif show_farm_selector:
                # Chỉ có 1 farm → hiện tĩnh, không cần dropdown
                state["selected_farm"] = farm_options[0]
                remember_farm(farm_options[0])
                ui.label(farm_options[0]).classes("sm-farm-static")

        # Status Badge + Notification Bell + User Profile
        with ui.element("div").style("display:inline-flex;align-items:center;gap:12px;"):
            if os.getenv("SMIOT_DEMO_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}:
                ui.label("Dữ liệu mô phỏng").classes("sm-chip sim")
            @ui.refreshable
            def system_status_indicator():
                # Gateway liveness only: derived from the last message the app received.
                if state.get("system_is_active", True):
                    ui.label("Gateway đang nhận dữ liệu").classes("sm-chip ok")
                else:
                    ui.label("Gateway mất tín hiệu").classes("sm-chip act")

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

                with ui.element('div').classes('sm-bell').props(
                    f'role="button" tabindex="0" aria-label="Thông báo, {unread_count} chưa đọc"'
                ):
                    ui.icon('notifications', size='20px', color='#46574D')

                    if unread_count > 0:
                        ui.label(str(unread_count)).classes('sm-bell-count')

                    # Dropdown Menu
                    with ui.menu().classes('w-80 overflow-hidden mt-2 p-0').props('anchor="bottom right" self="top right" auto-close=false'):
                        # Header
                        with ui.element('div').classes('flex justify-between items-center px-4 py-3').style(
                            'background:var(--sm-sunken);border-bottom:1px solid var(--sm-net-soft)'
                        ):
                            ui.label('Thông báo').classes('sm-h2').style('font-size:15px')
                            if unread_count > 0:
                                def mark_read():
                                    for n in s.get("notifications", []): n["read"] = True
                                    state["_update_counter"] = state.get("_update_counter", 0) + 1
                                ui.label('Đánh dấu đã đọc').classes('sm-link cursor-pointer').style(
                                    'font-size:12px').on('click', mark_read)

                        # Content list
                        with ui.element('div').classes('max-h-[320px] overflow-y-auto p-2'):
                            if not notifications:
                                with ui.element('div').classes('flex flex-col items-center justify-center py-8 opacity-60'):
                                    ui.icon('notifications_off', size='32px', color='#94a3b8').classes('mb-2')
                                    ui.label('Không có thông báo mới').classes('text-sm text-slate-500')
                            else:
                                for notif in notifications:
                                    is_read = notif.get("read", False)
                                    workflow_status = str(notif.get("workflow_status") or "").lower()
                                    verification_status = str(notif.get("verification_status") or "").lower()
                                    severity = str(notif.get("severity") or "").lower()
                                    is_err = (
                                        severity == "error"
                                        or workflow_status in {"failed", "escalated"}
                                        or verification_status == "failed"
                                        or any(word in notif["text"].lower() for word in ["không", "mất", "cảnh báo", "lỗi", "❌"])
                                    )
                                    is_warning = not is_err and (
                                        severity == "warning"
                                        or workflow_status in {"pending_verification", "investigating"}
                                        or verification_status in {"pending", "unknown"}
                                    )
                                    
                                    bg_hover = "hover:bg-slate-50"
                                    bg_base = "bg-white" if is_read else ("bg-red-50/40" if is_err else ("bg-amber-50/40" if is_warning else "bg-green-50/40"))
                                    
                                    icon_name = "error_outline" if is_err else ("warning_amber" if is_warning else "check_circle")
                                    icon_color = "#ef4444" if is_err else ("#d97706" if is_warning else "#22c55e")

                                    with ui.element('div').classes(f'flex items-start gap-3 p-3 mb-1 rounded-xl {bg_base} {bg_hover} transition-colors cursor-default'):
                                        ui.icon(icon_name, size='20px', color=icon_color).classes('mt-0.5 shrink-0')
                                        with ui.element('div').classes('flex-1'):
                                            ui.label(notif["text"]).classes(f'text-[13px] leading-tight mb-1 {"font-medium text-slate-800" if not is_read else "text-slate-600"}')
                                            if notif.get("incident_id") and notif.get("correlation_status") == "verified":
                                                ui.link(
                                                    f"Mở sự cố {notif['incident_id']}",
                                                    f"/incident/{notif['incident_id']}",
                                                ).classes('block text-[11px] text-blue-600 hover:text-blue-800')
                                            elif notif.get("correlation_status") == "unlinked" and notif.get("workflow_id"):
                                                ui.label('Chưa ghép được mã sự cố').classes('block text-[11px] text-amber-700')
                                            if notif.get("workflow_status") or notif.get("verification_status"):
                                                result_line = " · ".join(
                                                    item for item in [
                                                        notif.get("workflow_status"),
                                                        notif.get("verification_status"),
                                                    ] if item
                                                )
                                                ui.label(result_line).classes('block text-[11px] text-slate-500')
                                            workflow_context = " · ".join(
                                                item for item in [
                                                    notif.get("farm_key"),
                                                    notif.get("workflow_name"),
                                                    f"run {notif.get('workflow_run_id')}" if notif.get("workflow_run_id") else None,
                                                    f"scenario {notif.get('scenario_run_id')}" if notif.get("scenario_run_id") else None,
                                                    f"command {notif.get('command_id')}" if notif.get("command_id") else None,
                                                    f"monitor {notif.get('monitor_id')}" if notif.get("monitor_id") else None,
                                                    "dữ liệu mô phỏng" if notif.get("synthetic") else None,
                                                ] if item
                                            )
                                            if workflow_context:
                                                ui.label(workflow_context).classes(
                                                    'block text-[10px] text-slate-400 truncate'
                                                )
                                            ui.label(notif["time"]).classes('text-[11px] text-slate-400 font-medium')
                                        
                                        # Chấm xanh nhỏ báo chưa đọc (nếu chưa đọc)
                                        if not is_read:
                                            ui.element('div').classes('w-2 h-2 rounded-full bg-blue-500 shrink-0 mt-1.5')

            client_bell()
            if client_bell.refresh not in client_refreshes[client_id]:
                client_refreshes[client_id].append(client_bell.refresh)
            
            # User Profile Dropdown (Option 3.1)
            with ui.element("div").classes("sm-user").style("position:relative;") as user_profile:
                ui.image(f"/static/{avatar_file}").style(
                    "width:28px;height:28px;border-radius:50%;object-fit:cover;border:1px solid #e1e7e0;"
                )
                ui.label(fullname).classes("sm-user-name")
                
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

    is_admin = role == "admin"
    can_manage = is_admin or "manage_users" in permissions

    # Groups follow the operator's job: see, act, follow the crop, administer.
    # Each entry: (icon, key passed by pages as `active`, label shown, url, visible).
    groups = [
        ("Quan sát", [
            ("ri-home-4-line", "Home", "Tổng quan", "/", True),
            ("ri-radar-line", "Incident", "Sự cố", "/incident", can_manage),
            ("ri-line-chart-line", "Chart", "Datadog", "/chart", True),
            ("ri-table-line", "Data", "Số đo", "/data", True),
        ]),
        ("Điều khiển", [
            ("ri-drop-line", "PLC", "Bơm", "/plc", True),
            ("ri-broadcast-line", "Inverter", "Biến tần", "/inverter", True),
            ("ri-calendar-line", "Schedule", "Lịch tưới", "/schedule", True),
            ("ri-cpu-line", "Device", "Thiết bị", "/devices", True),
        ]),
        ("Mùa vụ", [
            ("ri-plant-line", "Mùa vụ & truy xuất", "Mùa vụ và truy xuất", "/mongodb-lab", True),
        ]),
        ("Quản trị", [
            ("ri-folder-open-line", "Projects", "Dự án", "/projects", is_admin),
            ("ri-key-2-line", "Permission", "Phân quyền", "/permission", can_manage),
        ]),
    ]

    with ui.element("nav").classes("sidebar").props('aria-label="Điều hướng chính"'):
        with ui.element("div").classes("sidebar-logo"):
            ui.image('/static/logo.png').style("width:30px; height:30px; object-fit: contain; flex:none;")
            with ui.element("div"):
                ui.label("SMIOT").classes("sm-brand")
                ui.label("10 nhà màng dưa lưới").classes("sm-brand-sub")

        for group_label, links in groups:
            links = [link for link in links if link[4]]
            if not links:
                continue
            ui.label(group_label).classes("sidebar-section")
            for icon, key, label, url, _visible in links:
                cls = f"nav-item {'active' if key == active else ''}"
                current = ' aria-current="page"' if key == active else ''
                with ui.element("a").props(f'href="{url}"{current}').classes(cls):
                    ui.html(f'<i class="{icon}"></i><span>{label}</span>')
        ui.element("div").classes("sm-rail-gap").style("flex:1")

        with ui.element("div").classes("sm-rail-foot"):
            ui.label("Thiết bị trong hệ thống là thiết bị ảo. Lệnh chỉ tới bộ mô phỏng.")


# ─────────────────────────────────────────────
# HOME: màn biểu đồ dựng từ MongoDB (pages/farm_overview_component.py giữ truy vấn và các khối hiển thị)
# ─────────────────────────────────────────────
from nicegui import background_tasks, run
from components.ui_kit import farm_tabs, fmt_time, page_header, state_panel, status_chip
from pages import farm_overview_component as fleet
from service.farm_registry import FARM_LABELS

HOME_CSS = """
.sm-home { display: flex; flex-direction: column; gap: 16px; width: 100%; min-width: 0; }
.sm-home > :empty { display: none; }
.sm-col { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.sm-split { display: grid; grid-template-columns: minmax(0, 2.4fr) minmax(0, 1fr); gap: 16px; width: 100%; align-items: stretch; }
.sm-split-wide { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; width: 100%; align-items: stretch; }
.sm-split > .sm-panel, .sm-split-wide > .sm-panel, .sm-cols-2 > .sm-panel { height: 100%; }
.sm-cols-2 { align-items: stretch; }
.sm-clamp { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
@media (max-width: 1100px) { .sm-matrix { min-width: 700px; } }
.sm-charts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; width: 100%; }
@media (max-width: 1100px) {
    .sm-split, .sm-split-wide { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 768px) {
    .sm-home { gap: 12px; padding-bottom: 76px; }
    .sm-charts { grid-template-columns: minmax(0, 1fr); }
}
"""


@ui.page("/")
def trang_chu(farm: str | None = None):
    if not check_login(): return

    farm_keys = tuple(fleet._allowed_farms())
    can_open = fleet.can_open_incident()
    client = ui.context.client
    client_id = client.id

    # Việc đang xem màn nào chỉ thuộc về client này; state toàn cục chỉ nhận farm đã chọn cho các trang khác.
    view = {"farm": None, "hours": 6, "more": set()}  # more: danh sách đang mở rộng của client này
    data: dict = {"fleet": None, "events": None, "lines": None, "extra": None, "series": None, "weather": None}
    seen = {"sig": None}
    busy = {"slow": False}

    if farm and farm in farm_keys:
        view["farm"] = farm
        state["selected_farm"] = FARM_LABELS.get(farm, farm)
        app.storage.user["current_farm"] = farm

    # --- dữ liệu ---
    def cards() -> list[dict]:
        return ((data["fleet"] or {}).get("value") or {}).get("cards", [])

    def current_card() -> dict | None:
        return next((c for c in cards() if c["farm_key"] == view["farm"]), None)

    async def call(fn, *args) -> dict:
        try:
            return await run.io_bound(fn, *args)
        except Exception as exc:
            return {"value": None, "read_at": None, "stale": False,
                    "error": f"Không đọc được dữ liệu ({type(exc).__name__})"}

    async def load_fleet() -> None:
        data["fleet"] = await call(fleet.get_fleet, farm_keys)

    async def fetch_weather() -> None:
        loaded = await call(fleet.get_weather)
        data["weather"] = loaded
        d = loaded.get("value")
        if d:  # trạng thái dùng chung chỉ nhận số thật từ Open-Meteo
            try:
                state["weather_lat"], state["weather_lng"] = str(d["lat"]), str(d["lon"])
                state["weather_solar"], state["weather_eto"] = d["total_radiation_day"], d["total_et0_day"]
                for hour in (1, 2, 3):
                    state[f"weather_{9 + hour}h_temp"] = d[f"t{hour}h"]
                    state[f"weather_{9 + hour}h_rain"] = d[f"h{hour}h"]
            except KeyError:
                pass

    async def load_slow() -> None:
        if busy["slow"]:
            return
        busy["slow"] = True
        try:
            for _ in range(3):
                key, hours = view["farm"], view["hours"]
                if key is None:
                    events, lines = await asyncio.gather(call(fleet.get_events, farm_keys),
                                                         call(fleet.get_fleet_series, farm_keys, hours))
                else:
                    extra, series = await asyncio.gather(call(fleet.get_farm_extra, key),
                                                         call(fleet.get_farm_series, key, hours))
                    await fetch_weather()
                if view["farm"] == key and view["hours"] == hours:
                    if key is None:
                        data["events"], data["lines"] = events, lines
                    else:
                        data["extra"], data["series"] = extra, series
                    break
        finally:
            busy["slow"] = False

    async def slow_then_refresh() -> None:
        await load_slow()
        refresh_slow()

    def retry_slow() -> None:
        fleet.invalidate()
        background_tasks.create(slow_then_refresh())

    async def retry_all() -> None:
        fleet.invalidate()
        await load_fleet()
        refresh_live()
        await slow_then_refresh()

    # --- điều hướng trong trang ---
    def select_farm(key: str | None) -> None:
        if key is not None and key not in farm_keys:
            return
        view["farm"] = key
        data["extra"] = data["series"] = None
        if key is not None:
            state["selected_farm"] = FARM_LABELS.get(key, key)
            app.storage.user["current_farm"] = key
        refresh_live()
        refresh_slow()
        background_tasks.create(slow_then_refresh())

    def toggle_more(key: str) -> None:
        view["more"].symmetric_difference_update({key})
        render_fleet_signals.refresh()
        render_fleet_events.refresh()
        render_farm_extra.refresh()

    def set_hours(hours: int) -> None:
        view["hours"] = hours
        data["lines"] = data["series"] = None
        refresh_slow()
        background_tasks.create(slow_then_refresh())

    def open_incident(incident_id: str) -> None:
        ui.navigate.to(f"/incident/{incident_id}")

    def refresh_live() -> None:
        render_content_area.refresh()
        render_farm_devices.refresh()

    def refresh_slow() -> None:
        for section in (render_fleet_signals, render_fleet_lines, render_fleet_events,
                        render_farm_charts, render_farm_extra):
            section.refresh()

    # --- Timer ---
    async def check_ui_update():
        import time
        from datetime import datetime
        last_seen = state.get("system_last_seen", time.time())
        gateway_timeout = (time.time() - last_seen) > 600

        if gateway_timeout:
            if state.get("system_is_active", True):
                # Gateway silence only flags the gateway; node status comes from MongoDB
                # (telemetry_health.compute_node_status), never forced here.
                state["system_is_active"] = False
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

            # Node status: single source of truth = newest sample in MongoDB
            # (telemetry_health.compute_node_status). Throttled; no RAM-based 600s timeout.
            try:
                from service.telemetry_health import refresh_selected_farm_status
                # Mongo reads run in a worker thread: never block the event loop (/healthz).
                for node_no, old, new in await run.io_bound(refresh_selected_farm_status, state):
                    if new in ("OFFLINE", "STALE"):
                        if "notifications" not in state: state["notifications"] = []
                        text = f"Node cảm biến {node_no}: {new} (mẫu mới nhất trong MongoDB đã cũ)"
                        if not state["notifications"] or state["notifications"][0]["text"] != text:
                            state["notifications"].insert(0, {"time": datetime.now().strftime("%H:%M:%S"), "text": text})
                    state["_update_counter"] = state.get("_update_counter", 0) + 1
            except Exception:
                pass

        current_counter = state.get("_update_counter", 0)
        if current_counter != check_ui_update.__dict__.get("last_counter", 0):
            check_ui_update.last_counter = current_counter
            # Chỉ phần chữ và số liệu vẽ lại theo nhịp này; biểu đồ có nhịp riêng (render_*_slow).
            if client_id in client_refreshes:
                for refresh_func in client_refreshes[client_id]:
                    try:
                        refresh_func()
                    except Exception:
                        pass
        await load_fleet()
        loaded = data["fleet"] or {}
        signature = (loaded.get("read_at"), loaded.get("stale"), loaded.get("error"))
        if signature != seen["sig"]:
            seen["sig"] = signature
            refresh_live()
            render_fleet_signals.refresh()  # bảng nhiệt và biểu đồ tuổi mẫu dùng cùng lần đọc này

    async def first_load() -> None:
        await load_fleet()
        refresh_live()
        render_fleet_signals.refresh()
        render_fleet_events.refresh()  # biểu đồ tuổi mẫu chỉ cần dữ liệu farm, không đợi sự cố
        await slow_then_refresh()

    async def slow_tick() -> None:
        await slow_then_refresh()

    t_first = ui.timer(0.05, first_load, once=True)
    t_slow = ui.timer(20.0, slow_tick)
    t_live = ui.timer(2.0, check_ui_update)

    def cleanup() -> None:
        for timer in (t_first, t_slow, t_live):
            timer.deactivate()
        client_refreshes.pop(client_id, None)

    client.on_disconnect(cleanup)

    ui.add_head_html(f"<style>{CUSTOM_CSS}{HOME_CSS}</style>")
    sidebar(active="Home")

    with ui.element("div").classes("main-content"):

        # Gọi Topbar dùng chung
        global_topbar("Nhà màng · Điều hành", "", show_farm_selector=False)

        with ui.element("div").classes("content-area"):
            with ui.element("div").classes("sm-home"):

                # Tiêu đề, thanh farm, dải trạng thái và số mới nhất: làm mới khi có lần đọc mới.
                @ui.refreshable
                def render_content_area():
                    loaded = data["fleet"]
                    if not farm_keys:
                        page_header("Chưa có nhà màng nào để xem", "Tài khoản này chưa được cấp quyền xem nhà màng.")
                        state_panel("empty", "Tài khoản chưa được cấp nhà màng",
                                    "Nhờ quản trị viên cấp quyền farm trong trang quản lý người dùng.")
                        return
                    if loaded is None:
                        page_header("Đang đọc dữ liệu nhà màng", "Đọc từ MongoDB.")
                        state_panel("loading", "Đang đọc dữ liệu từ MongoDB", "Lần đọc đầu tiên có thể mất vài giây.")
                        return
                    if loaded.get("value") is None:
                        page_header("Không đọc được dữ liệu nhà màng", "Không kết nối được MongoDB.")
                        state_panel("error", "Không đọc được MongoDB", f"{loaded.get('error')}. Kiểm tra kết nối rồi thử lại.",
                                    action_label="Thử lại", on_action=retry_all)
                        return
                    cds = cards()
                    card = current_card()
                    read_text = f"Đọc từ MongoDB lúc {fmt_time(loaded.get('read_at'), with_date=False)}"
                    if card is None:
                        slot = page_header(fleet.fleet_headline(cds), read_text)
                    else:
                        slot = page_header(f"{card['label']}: {fleet.LEVEL_TEXT[card['level']].lower()}", read_text)
                        with slot:
                            status_chip(card["level"], fleet.LEVEL_TEXT[card["level"]])
                    fleet.stale_banner(loaded)
                    farm_tabs(fleet.tab_levels(cds), view["farm"], select_farm)
                    if card is not None:
                        fleet.render_farm_strip(card, _farm_shortcuts(card["farm_key"], can_open), ui.navigate.to)
                        fleet.render_farm_stats(card, data["extra"])

                render_content_area()

                @ui.refreshable
                def render_fleet_signals():
                    loaded = data["fleet"]
                    if view["farm"] is not None or not loaded or loaded.get("value") is None or not cards():
                        return
                    # Hàng 1: năm số tổng. Hàng 2: bảng tín hiệu rộng cạnh khối Cần chú ý.
                    fleet.render_fleet_kpis(cards(), data["events"])
                    with ui.element("div").classes("sm-split"):
                        fleet.render_signal_matrix(cards(), loaded.get("read_at"), select_farm)
                        fleet.render_attention(cards(), loaded.get("read_at"), select_farm, view["more"], toggle_more)

                render_fleet_signals()

                @ui.refreshable
                def render_fleet_lines():
                    if view["farm"] is not None or not cards():
                        return
                    fleet.render_fleet_lines(data["lines"], view["hours"], cards(), set_hours, retry_slow)

                render_fleet_lines()

                @ui.refreshable
                def render_fleet_events():
                    if view["farm"] is not None or not cards():
                        return
                    labels = {c["farm_key"]: c["label"] for c in cards()}
                    # Hàng 3: lưới biểu đồ cùng chiều cao; dưới cùng là hai danh sách đã gộp dòng trùng.
                    with ui.element("div").classes("sm-cols-2"):
                        fleet.render_age_chart(cards(), data["fleet"].get("read_at"))
                        fleet.render_incident_timeline(data["events"], cards(), can_open, open_incident, retry_slow)
                    with ui.element("div").classes("sm-split-wide"):
                        fleet.render_review_queue(data["events"], labels, can_open, open_incident, view["more"], toggle_more)
                        fleet.render_notices(data["fleet"]["value"], None, view["more"], toggle_more)

                render_fleet_events()

                @ui.refreshable
                def render_farm_charts():
                    if view["farm"] is None or current_card() is None:
                        return
                    fleet.render_farm_charts(data["series"], view["hours"], set_hours, retry_slow)

                render_farm_charts()

                @ui.refreshable
                def render_farm_devices():
                    card = current_card()
                    if view["farm"] is None or card is None:
                        return
                    fleet.render_farm_devices(card, data["extra"], state, retry_slow)

                render_farm_devices()

                @ui.refreshable
                def render_farm_extra():
                    card = current_card()
                    if view["farm"] is None or card is None:
                        return
                    with ui.element("div").classes("sm-cols-2"):
                        with ui.element("div").classes("sm-col"):
                            fleet.render_farm_incidents(card, can_open, open_incident)
                            fleet.render_ai_suggestion(data["extra"])
                            fleet.render_notices(data["fleet"]["value"], card["farm_key"], view["more"], toggle_more)
                        fleet.render_weather(data["weather"], lambda: background_tasks.create(_weather_retry()))

                render_farm_extra()

    async def _weather_retry() -> None:
        fleet.invalidate()
        await fetch_weather()
        render_farm_extra.refresh()


def _farm_shortcuts(farm_key: str, can_open: bool) -> list[tuple[str, str]]:
    items = [("Bơm", "/plc"), ("Biến tần", "/inverter"), ("Lịch tưới", "/schedule")]
    if can_open:
        items.append(("Sự cố của farm này", f"/incident?farm={farm_key}"))
    items.append(("Mùa vụ", "/mongodb-lab"))
    return items
