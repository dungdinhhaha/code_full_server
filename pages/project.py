"""
pages/project.py — Trang Quản Lý Dự Án
Dashboard tổng quan dự án với các thẻ nhà màng, hoạt động gần đây.
"""

from nicegui import ui, app
from pages.home import CUSTOM_CSS, sidebar, global_topbar
from pages.login import check_login
from service.auth import get_user_farms, get_all_farms

# ─────────────────────────────────────────────
# MOCK DATA — Dữ liệu giả lập dự án
# ─────────────────────────────────────────────
PROJECTS = {
    "greenhouse_a": {
        "name": "Greenhouse A", "emoji": "🌿", "status": "active",
        "location": "Đà Lạt, Lâm Đồng",
        "sensors": 24, "plc": 2, "devices": 18,
        "health": 95, "updated": "2 phút trước",
        "gradient": "linear-gradient(135deg,#d1fae5,#a7f3d0)",
        "has_data": True,
    },
    "greenhouse_b": {
        "name": "Greenhouse B", "emoji": "🍅", "status": "active",
        "location": "Củ Chi, TP.HCM",
        "sensors": 18, "plc": 1, "devices": 12,
        "health": 92, "updated": "Live demo",
        "gradient": "linear-gradient(135deg,#fef3c7,#fde68a)",
        "has_data": True,
    },
    "greenhouse_c": {
        "name": "Greenhouse C", "emoji": "🌱", "status": "active",
        "location": "Đà Lạt, Lâm Đồng",
        "sensors": 32, "plc": 3, "devices": 24,
        "health": 96, "updated": "Live demo",
        "gradient": "linear-gradient(135deg,#dbeafe,#93c5fd)",
        "has_data": True,
    },
    "greenhouse_d": {
        "name": "Greenhouse D", "emoji": "🏚️", "status": "active",
        "location": "Long An",
        "sensors": 8, "plc": 1, "devices": 6,
        "health": 89, "updated": "Live demo",
        "gradient": "linear-gradient(135deg,#f1f5f9,#e2e8f0)",
        "has_data": True,
    },
}

ACTIVITIES = [
    {"icon": "⚠️", "bg": "#fef3c7", "color": "#d97706", "title": "Nhiệt độ cao bất thường", "sub": "Greenhouse B — Node 2", "time": "2 phút"},
    {"icon": "🔴", "bg": "#fee2e2", "color": "#ef4444", "title": "Node mất kết nối",       "sub": "Greenhouse D — Gateway",      "time": "5 phút"},
    {"icon": "✅", "bg": "#dcfce7", "color": "#16a34a", "title": "Bắt đầu tưới tự động",   "sub": "Greenhouse A — Zone 1", "time": "12 phút"},
    {"icon": "🔄", "bg": "#dbeafe", "color": "#2563eb", "title": "Firmware updated",        "sub": "Greenhouse C — PLC-01", "time": "30 phút"},
]

# ─────────────────────────────────────────────
# PROJECT PAGE CSS
# ─────────────────────────────────────────────
PROJECT_CSS = """
.stat-card {
    text-align: center;
    padding: 24px 18px;
    background: white;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    transition: all 0.2s;
}
.stat-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}

.proj-card {
    background: white; border-radius: 12px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    padding: 0; overflow: hidden; cursor: pointer;
    transition: all 0.2s;
}
.proj-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}
.proj-card .proj-thumb {
    height: 100px; display: flex; align-items: center; justify-content: center;
    font-size: 42px; position: relative; overflow: hidden;
}

.badge-active { background: #dcfce7; color: #16a34a; }
.badge-warning { background: #fef3c7; color: #d97706; }
.badge-offline { background: #f1f5f9; color: #94a3b8; }
.badge-admin { background: #fae8ff; color: #9333ea; }
.badge-operator { background: #dbeafe; color: #2563eb; }
.badge-viewer { background: #f1f5f9; color: #6b7280; }

.timeline-item {
    display: flex; gap: 12px; padding: 12px 0;
    border-bottom: 1px solid #f0f0f0;
}
.timeline-item:last-child { border-bottom: none; }
.timeline-dot {
    width: 32px; height: 32px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; flex-shrink: 0;
}
"""


# ─────────────────────────────────────────────
# PAGE
# ─────────────────────────────────────────────
@ui.page('/projects')
def trang_projects():
    if not check_login(): return

    ui.add_head_html(f"<style>{CUSTOM_CSS}{PROJECT_CSS}</style>")
    sidebar(active="Projects")

    # Đọc danh sách user và farm từ MongoDB.
    import datetime
    from service import auth
    users_data = []
    now = datetime.datetime.now()
    try:
        for user in auth.get_all_users():
            username, role, la_str = user.get("username"), user.get("role"), user.get("last_active")
            is_online = False
            last_active_display = "Chưa rõ"
            if la_str:
                try:
                    la_dt = datetime.datetime.strptime(str(la_str), "%Y-%m-%d %H:%M:%S")
                    is_online = (now - la_dt).total_seconds() < 120
                    last_active_display = la_dt.strftime("%H:%M:%S %d/%m/%Y")
                except (TypeError, ValueError):
                    pass
            farm_names = [PROJECTS[fk]["name"] for fk in auth.get_user_farms(user["id"]) if fk in PROJECTS]
            bg_color = "#4361ee" if role == "admin" else "#10b981" if role == "operator" else "#6b7280"
            users_data.append({"name": username, "farms": ", ".join(farm_names) if farm_names else ("Toàn quyền" if role == "admin" else "Chưa gán"), "role": role, "bg": bg_color, "is_online": is_online, "last_active": last_active_display})
    except Exception as e:
        print(f"❌ [LỖI TRANG PROJECT] {e}")

    # Lấy thông tin farm cho user hiện tại
    current_user_id = app.storage.user.get('user_id')
    current_role = app.storage.user.get('role', 'viewer')
    if current_role == 'admin':
        visible_farm_keys = list(PROJECTS.keys())
    elif current_user_id:
        visible_farm_keys = get_user_farms(current_user_id)
        if not visible_farm_keys: visible_farm_keys = ["greenhouse_a"]
    else:
        visible_farm_keys = ["greenhouse_a"]

    visible_projects = [PROJECTS[k] for k in visible_farm_keys if k in PROJECTS]

    # Tính stats
    total_farms = len(visible_projects)
    total_sensors = sum(p["sensors"] for p in visible_projects)
    total_devices = sum(p["devices"] for p in visible_projects)
    active_count = sum(1 for p in visible_projects if p["has_data"])
    
    online_users = sum(1 for u in users_data if u["is_online"])
    total_users_count = len(users_data)

    STATS = [
        {"icon": "🏡", "value": str(total_farms),    "label": "Total Farms",  "bg": "linear-gradient(135deg,#dbeafe,#eff6ff)"},
        {"icon": "📡", "value": str(total_sensors),   "label": "Sensors",      "bg": "linear-gradient(135deg,#dcfce7,#f0fdf4)"},
        {"icon": "⚙️", "value": str(total_devices),   "label": "Devices",      "bg": "linear-gradient(135deg,#fef3c7,#fffbeb)"},
        {"icon": "✅", "value": f"{active_count}/{total_farms}", "label": "Online", "bg": "linear-gradient(135deg,#e0e7ff,#eef2ff)"},
        {"icon": "👥", "value": f"{online_users}/{total_users_count}", "label": "Users Online", "bg": "linear-gradient(135deg,#fae8ff,#fdf4ff)"},
    ]

    with ui.element("div").classes("main-content"):
        global_topbar("Quản Lý Dự Án", "📂")

        with ui.element("div").classes("content-area"):
            with ui.element("div").style("display:flex;flex-direction:column;gap:20px;width:100%"):

                # ── Stats Row (5 columns) ──
                with ui.element("div").style("width:100%"):
                    ui.label("📊  TỔNG QUAN HỆ THỐNG").classes("section-header").style("color:#4361ee;margin-bottom:12px")
                    with ui.element("div").style("display:grid;grid-template-columns:repeat(5,1fr);gap:16px;"):
                        for s in STATS:
                            with ui.element("div").classes("stat-card"):
                                with ui.element("div").style("display:flex;align-items:center;gap:14px;justify-content:center;"):
                                    with ui.element("div").style(f"background:{s['bg']};width:44px;height:44px;border-radius:10px;display:flex;align-items:center;justify-content:center;"):
                                        ui.label(s["icon"]).style("font-size:20px")
                                    with ui.element("div").style("text-align:left;"):
                                        ui.label(s["value"]).style("font-size:26px;font-weight:800;color:#1a1a2e;line-height:1;")
                                        ui.label(s["label"]).style("font-size:11px;color:#94a3b8;font-weight:600;letter-spacing:.06em;text-transform:uppercase;margin-top:4px;")

                # ── Projects Grid ──
                with ui.element("div").style("width:100%"):
                    ui.label("🏡  DANH SÁCH NHÀ MÀNG").classes("section-header").style("color:#10b981;margin-bottom:12px")
                    num_cols = min(len(visible_projects), 4)
                    with ui.element("div").style(f"display:grid;grid-template-columns:repeat({num_cols},1fr);gap:16px;"):
                        for p in visible_projects:
                            with ui.element("div").classes("proj-card"):
                                with ui.element("div").classes("proj-thumb").style(f"background:{p['gradient']};"):
                                    ui.label(p["emoji"]).style("font-size:42px")
                                with ui.element("div").style("padding:16px 18px;"):
                                    with ui.element("div").style("display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"):
                                        ui.label(p["name"]).style("font-weight:700;font-size:15px;color:#1a1a2e;")
                                        badge_class = f"badge badge-{p['status']}"
                                        with ui.element("span").classes(badge_class).style("display:inline-flex;align-items:center;padding:3px 10px;border-radius:20px;font-size:10px;font-weight:700;text-transform:uppercase"):
                                            ui.label(p["status"].capitalize())
                                    ui.label(f"📍 {p['location']}").style("font-size:12px;color:#94a3b8;margin-bottom:10px")
                                    # Status message... (đã có từ trước)
                                    if p["has_data"]:
                                        with ui.element("div").style("background:#dcfce7;padding:8px 12px;border-radius:8px;display:flex;align-items:center;gap:6px;margin-bottom:10px"):
                                            ui.label("✅").style("font-size:12px")
                                            ui.label("Đang hoạt động — Có dữ liệu").style("font-size:12px;color:#16a34a;font-weight:600")
                                    elif p["status"] == "warning":
                                        with ui.element("div").style("background:#fef3c7;padding:8px 12px;border-radius:8px;display:flex;align-items:center;gap:6px;margin-bottom:10px"):
                                            ui.label("⚠️").style("font-size:12px")
                                            ui.label("Cảnh báo — Chưa có dữ liệu").style("font-size:12px;color:#d97706;font-weight:600")
                                    else:
                                        with ui.element("div").style("background:#f1f5f9;padding:8px 12px;border-radius:8px;display:flex;align-items:center;gap:6px;margin-bottom:10px"):
                                            ui.label("📡").style("font-size:12px")
                                            ui.label("Chưa kết nối — Chưa có dữ liệu").style("font-size:12px;color:#94a3b8;font-weight:600")
                                    with ui.element("div").style("display:flex;gap:12px;font-size:12px;color:#64748b;background:#f8fafc;padding:8px 10px;border-radius:8px;"):
                                        ui.label(f"📡 {p['sensors']} Sensors")
                                        ui.label(f"⚙️ {p['plc']} PLC")
                                        ui.label(f"📱 {p['devices']} Devices")

                # ── Bottom: Activity + Permission Summary ──
                with ui.element("div").style("width:100%"):
                    ui.label("📋  HOẠT ĐỘNG & TRẠNG THÁI NGƯỜI DÙNG").classes("section-header").style("color:#7c3aed;margin-bottom:12px")
                    with ui.element("div").style("display:grid;grid-template-columns:1.2fr 2fr;gap:16px;"):
                        # Recent Activity
                        with ui.element("div").classes("card").style("padding:18px;"):
                            ui.label("⚡  RECENT ACTIVITY").classes("section-header").style("color:#f59e0b;font-size:13px;margin-bottom:12px;")
                            for a in ACTIVITIES:
                                with ui.element("div").classes("timeline-item").style("padding:10px 0;"):
                                    with ui.element("div").classes("timeline-dot").style(f"background:{a['bg']};color:{a['color']};width:28px;height:28px;font-size:13px;"):
                                        ui.label(a["icon"])
                                    with ui.element("div").style("flex:1"):
                                        ui.label(a["title"]).style("font-size:13px;font-weight:600;color:#1a1a2e")
                                        ui.label(a["sub"]).style("font-size:11px;color:#94a3b8")
                                    ui.label(a["time"]).style("font-size:11px;color:#aaa;white-space:nowrap")

                        # Permission Summary (5 cột)
                        with ui.element("div").classes("card").style("padding:18px;"):
                            ui.label("👥  USER ONLINE STATUS").classes("section-header").style("color:#7c3aed;font-size:13px;margin-bottom:12px;")
                            with ui.element("div").style("display:grid;grid-template-columns:1fr 1.2fr 0.7fr 0.5fr 1fr;gap:10px;padding:8px 0;border-bottom:1px solid #f0f0f0;font-size:11px;color:#94a3b8;font-weight:600;text-transform:uppercase"):
                                ui.label("User")
                                ui.label("Farm Access")
                                ui.label("Role")
                                ui.label("Status")
                                ui.label("Last Active")
                            for pu in users_data:
                                with ui.element("div").style("display:grid;grid-template-columns:1fr 1.2fr 0.7fr 0.5fr 1fr;gap:10px;padding:10px 0;border-bottom:1px solid #f8f8f8;align-items:center"):
                                    with ui.element("div").style("display:flex;align-items:center;gap:8px;overflow:hidden"):
                                        initials = pu["name"].split()
                                        init_str = "+".join(initials)
                                        ui.image(f"https://ui-avatars.com/api/?name={init_str}&background={pu['bg'].replace('#','')}&color=fff&size=28").style("width:28px;height:28px;border-radius:50%")
                                        ui.label(pu["name"]).style("font-weight:600;font-size:13px;color:#1a1a2e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")
                                    ui.label(pu["farms"]).style("color:#64748b;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;")
                                    badge_cls = f"badge badge-{pu['role']}"
                                    ui.label(pu["role"].capitalize()).classes(badge_cls).style("display:inline-flex;align-items:center;padding:3px 10px;border-radius:20px;font-size:10px;font-weight:700;text-transform:uppercase")
                                    
                                    # Status Dot pulsing
                                    dot_class = "dot-green" if pu["is_online"] else "dot-red"
                                    with ui.element("div").style("display:flex;justify-content:center"):
                                        ui.element("div").classes(dot_class).style("width:8px;height:8px;border-radius:50%")
                                    ui.label(pu["last_active"]).style("font-size:11px;color:#94a3b8")
