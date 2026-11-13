"""pages/project.py - Tổng quan dự án: nhà màng được cấu hình, tín hiệu gần nhất, quyền truy cập.

Tín hiệu lấy từ MongoDB: chỉ mẫu trong 10 phút gần nhất mới được tính.
"""

from datetime import datetime, timedelta, timezone

from nicegui import app, ui

from components.theme import CHART
from components.ui_kit import page_header, panel, sim_badge, source_note, state_panel, stat, stats, status_chip
from pages.home import CUSTOM_CSS, sidebar, global_topbar
from pages.login import check_login
from service.auth import get_user_farms
from service.farm_registry import FARMS as FARM_REGISTRY
from service.logger import get_logger
from service.mongodb_store import collection

logger = get_logger("PROJECT")

PROJECTS = {
    farm_key: {"name": label, "letter": label.split()[-1][:1].upper()}
    for farm_key, label, _emoji in FARM_REGISTRY
}

ROLE_TEXT = {"admin": "Quản trị", "operator": "Vận hành", "viewer": "Xem"}

# Nhãn hiển thị và mức màu cho trạng thái tín hiệu. LIVE giữ nguyên tên kỹ thuật.
SIGNAL_VIEW = {
    "LIVE": ("LIVE", "ok"),
    "STALE": ("Mẫu cũ", "watch"),
    "NO DATA": ("Không có mẫu", "none"),
    "UNKNOWN": ("Chưa rõ", "stale"),
}


def _load_recent_farm_signals(farm_keys: list[str], now: datetime) -> dict[str, dict] | None:
    """One MongoDB aggregation for configured farms; seeded history is excluded."""
    cutoff = now - timedelta(minutes=10)
    pipeline = [
        {"$match": {"meta.measurement_type": "node", "meta.farm_key": {"$in": farm_keys},
                    "timestamp": {"$gte": cutoff}, "source.demo_seed_version": {"$exists": False}}},
        {"$group": {"_id": "$meta.farm_key", "last_sample_at": {"$max": "$timestamp"},
                    "sample_count_10m": {"$sum": 1}, "nodes": {"$addToSet": "$meta.node_id"}}},
    ]
    try:
        return {row["_id"]: row for row in collection("telemetry").aggregate(pipeline, maxTimeMS=2500)}
    except Exception as ex:
        logger.warning(f"Không đọc được tín hiệu nhà màng: {ex}")
        return None


def _signal_state(row: dict | None, now: datetime) -> tuple[str, str]:
    """Trả về (mã trạng thái, mô tả). Có mẫu trong 10 phút và mới trong 90 giây mới là LIVE."""
    if not row or not row.get("last_sample_at"):
        return "NO DATA", "Chưa nhận mẫu live trong 10 phút"
    stamp = row["last_sample_at"]
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    age_s = max(0, (now - stamp.astimezone(timezone.utc)).total_seconds())
    if age_s <= 90:
        return "LIVE", f"Mẫu mới {int(age_s)} giây trước"
    if age_s <= 300:
        return "STALE", f"Mẫu cuối {int(age_s)} giây trước"
    return "NO DATA", f"Mẫu cuối {int(age_s // 60)} phút trước"


PROJECT_CSS = """
.pj-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; }
.pj-card { display: flex; flex-direction: column; gap: 10px; min-width: 0; padding: 14px 16px;
           background: var(--sm-surface); border: 1px solid var(--sm-net-soft); border-radius: var(--sm-r-m); }
.pj-card-head { display: flex; gap: 12px; align-items: flex-start; justify-content: space-between; }
.pj-card-title { display: flex; gap: 10px; align-items: center; min-width: 0; }
.pj-tile { width: 36px; height: 36px; flex: none; border-radius: var(--sm-r-s); background: var(--sm-vine-tint);
           color: var(--sm-vine-deep); font-family: var(--sm-display); font-weight: 700; font-size: 16px;
           display: flex; align-items: center; justify-content: center; }
.pj-name { font-size: 14px; font-weight: 700; color: var(--sm-ink); line-height: 1.3; }
.pj-metrics { display: flex; gap: 12px; flex-wrap: wrap; font-size: 12px; color: var(--sm-ink-2);
              background: var(--sm-sunken); padding: 8px 10px; border-radius: var(--sm-r-s); }
.pj-links { display: flex; gap: 14px; flex-wrap: wrap; font-size: 13px; }
.pj-users { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr) 90px 120px 150px; gap: 10px;
            align-items: center; min-width: 620px; padding: 10px 0; border-bottom: 1px solid var(--sm-net-soft); }
.pj-users.head { font-size: 11px; color: var(--sm-ink-3); padding-top: 0; }
.pj-person { display: flex; align-items: center; gap: 8px; min-width: 0; }
.pj-avatar { width: 28px; height: 28px; flex: none; border-radius: 50%; display: flex; align-items: center;
             justify-content: center; font-size: 12px; font-weight: 700; color: var(--sm-surface); background: var(--sm-none); }
.pj-avatar.admin { background: var(--sm-vine); }
.pj-avatar.operator { background: var(--sm-info); }
.pj-name-cell { font-size: 13px; font-weight: 600; color: var(--sm-ink); overflow: hidden; text-overflow: ellipsis;
                white-space: nowrap; min-width: 0; }
.pj-muted { font-size: 12px; color: var(--sm-ink-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.pj-role { font-size: 11px; padding: 2px 8px; border-radius: var(--sm-r-s); justify-self: start;
           background: var(--sm-none-tint); color: var(--sm-ink-2); }
.pj-role.admin { background: var(--sm-vine-tint); color: var(--sm-vine-deep); }
.pj-role.operator { background: var(--sm-info-tint); color: var(--sm-info); }
.pj-status { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--sm-ink-2); }
.pj-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--sm-none); }
.pj-dot.on { background: var(--sm-ok); }
@media (max-width: 720px) { .pj-cards { grid-template-columns: 1fr; } }
.pj-kpi { display:grid; grid-template-columns:repeat(auto-fill,minmax(140px,1fr)); gap:10px; }
.pj-users{ min-width:520px; }
"""


def _farm_card(p: dict) -> None:
    key = p["key"]
    row = p["signal"]
    count = int((row or {}).get("sample_count_10m", 0))
    nodes = [n for n in (row or {}).get("nodes", []) if n is not None]
    label, level = SIGNAL_VIEW.get(p["text"], SIGNAL_VIEW["UNKNOWN"])
    with ui.element("article").classes("pj-card"):
        with ui.element("div").classes("pj-card-head"):
            with ui.element("div").classes("pj-card-title"):
                ui.label(p["letter"]).classes("pj-tile")
                with ui.element("div").style("min-width:0"):
                    ui.label(p["name"]).classes("pj-name")
                    ui.label(p["detail"]).classes("sm-note")
            status_chip(level, label)
        with ui.element("div").classes("pj-metrics"):
            ui.label(f"{count} mẫu trong 10 phút")
            ui.label(f"{len(nodes)} node có dữ liệu")
        with ui.element("div").classes("pj-links"):
            ui.link("Mở farm", f"/?farm={key}").classes("sm-link")
            ui.link("Bơm", "/plc").classes("sm-link")
            ui.link("Sự cố", f"/incident?farm={key}").classes("sm-link")


@ui.page('/projects')
def trang_projects():
    if not check_login():
        return

    ui.add_head_html(f"<style>{CUSTOM_CSS}{PROJECT_CSS}</style>")
    sidebar(active="Projects")

    from service import auth

    now = datetime.now(timezone.utc)
    users_data = []
    users_error = False
    try:
        for user in auth.get_all_users():
            username, role, la_str = user.get("username") or "—", user.get("role") or "viewer", user.get("last_active")
            is_online = False
            last_active_display = "Chưa rõ"
            if la_str:
                try:
                    la_dt = datetime.strptime(str(la_str), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    is_online = (now - la_dt).total_seconds() < 120
                    last_active_display = la_dt.strftime("%H:%M:%S %d/%m/%Y")
                except (TypeError, ValueError):
                    pass
            farm_names = [PROJECTS[fk]["name"] for fk in auth.get_user_farms(user["id"]) if fk in PROJECTS]
            users_data.append({
                "name": username,
                "initial": (username[:1] or "?").upper(),
                "farms": ", ".join(farm_names) if farm_names else ("Toàn quyền" if role == "admin" else "Chưa gán"),
                "role": role,
                "is_online": is_online,
                "last_active": last_active_display,
            })
    except Exception as ex:
        users_error = True
        logger.warning(f"Không đọc được danh sách người dùng: {ex}")

    # Nhà màng hiển thị cho tài khoản hiện tại
    current_user_id = app.storage.user.get('user_id')
    current_role = app.storage.user.get('role', 'viewer')
    if current_role == 'admin':
        visible_farm_keys = list(PROJECTS.keys())
    elif current_user_id:
        visible_farm_keys = get_user_farms(current_user_id) or ["greenhouse_a"]
    else:
        visible_farm_keys = ["greenhouse_a"]

    visible_projects = [{"key": k, **PROJECTS[k]} for k in visible_farm_keys if k in PROJECTS]
    farm_signals = _load_recent_farm_signals([p["key"] for p in visible_projects], now)
    signal_ok = farm_signals is not None
    for p in visible_projects:
        p["signal"] = farm_signals.get(p["key"]) if signal_ok else None
        if signal_ok:
            p["text"], p["detail"] = _signal_state(p["signal"], now)
        else:
            p["text"], p["detail"] = "UNKNOWN", "Không đọc được MongoDB"

    total_farms = len(visible_projects)
    live_count = sum(1 for p in visible_projects if p["text"] == "LIVE")
    stale_count = sum(1 for p in visible_projects if p["text"] == "STALE")
    unknown_count = sum(1 for p in visible_projects if p["text"] == "UNKNOWN")
    recent_samples = sum(int((p["signal"] or {}).get("sample_count_10m", 0)) for p in visible_projects)

    with ui.element("div").classes("main-content"):
        global_topbar("Dự án", "")

        with ui.element("div").classes("content-area"):
            slot = page_header(
                "Dự án",
                "Nhà màng được cấu hình, tín hiệu gần nhất và quyền truy cập của tài khoản.",
            )
            with slot:
                sim_badge()

            with stats():
                stat("Nhà màng được cấu hình", total_farms)
                stat("Đang có mẫu live", live_count if signal_ok else None,
                     meta="Mẫu trong 90 giây gần nhất")
                stat("Mẫu đang cũ", stale_count if signal_ok else None,
                     level="watch" if stale_count else None, meta="Mẫu cuối từ 90 đến 300 giây trước")
                stat("Mẫu trong 10 phút", recent_samples if signal_ok else None,
                     meta="Tổng mẫu telemetry của các nhà màng")
                stat("Chưa đọc được", unknown_count, level="act" if unknown_count else None,
                     meta="Lỗi truy vấn MongoDB" if not signal_ok else "Không đủ dữ liệu để xác định")

            with ui.element("div").style("margin-top:16px"):
                with panel("Tín hiệu theo nhà màng",
                           note="Chỉ tính mẫu trong 10 phút gần nhất. Dữ liệu seed không làm nhà màng hiện LIVE."):
                    if not signal_ok:
                        state_panel('error', 'Không đọc được MongoDB',
                                    'Trạng thái nhà màng chưa xác định. Kiểm tra kết nối rồi làm mới trang.')
                    elif not visible_projects:
                        state_panel('empty', 'Chưa có nhà màng nào được gán',
                                    'Quản trị viên gán nhà màng cho tài khoản này.')
                    else:
                        with ui.element("div").classes("pj-cards"):
                            for p in visible_projects:
                                _farm_card(p)
                        ui.echart({
                            "animation": False,
                            "textStyle": {"fontFamily": CHART["font"], "color": CHART["ink"]},
                            "tooltip": {"trigger": "axis"},
                            "grid": {"left": 45, "right": 20, "top": 20, "bottom": 32},
                            "xAxis": {"type": "category", "data": [p["name"] for p in visible_projects],
                                      "axisLabel": {"color": CHART["muted"]},
                                      "axisLine": {"lineStyle": {"color": CHART["grid"]}}},
                            "yAxis": {"type": "value", "name": "Mẫu / 10 phút", "minInterval": 1,
                                      "splitLine": {"lineStyle": {"color": CHART["grid"]}},
                                      "axisLabel": {"color": CHART["muted"]}},
                            "series": [{"type": "bar", "barMaxWidth": 54,
                                        "data": [int((p["signal"] or {}).get("sample_count_10m", 0))
                                                 for p in visible_projects],
                                        "itemStyle": {"color": CHART["series"][0]}}],
                        }).style("height:240px;width:100%;margin-top:12px")
                        source_note(f"Đọc từ MongoDB lúc {datetime.now().strftime('%H:%M:%S %d/%m')}")

            with ui.element("div").style("margin-top:16px"):
                with panel("Quyền truy cập và người dùng",
                           note="Trực tuyến: hoạt động trong 2 phút gần nhất."):
                    if users_error:
                        state_panel('error', 'Không đọc được danh sách người dùng',
                                    'Kiểm tra kết nối MongoDB rồi làm mới trang.')
                    elif not users_data:
                        state_panel('empty', 'Chưa có người dùng nào', 'Thêm người dùng trong trang quyền.')
                    else:
                        with ui.element("div").classes("sm-scroll-x"):
                            with ui.element("div").classes("pj-users head"):
                                ui.label("Người dùng")
                                ui.label("Nhà màng được phép")
                                ui.label("Vai trò")
                                ui.label("Trạng thái")
                                ui.label("Hoạt động gần nhất")
                            for pu in users_data:
                                with ui.element("div").classes("pj-users"):
                                    with ui.element("div").classes("pj-person"):
                                        ui.label(pu["initial"]).classes(f"pj-avatar {pu['role']}")
                                        ui.label(pu["name"]).classes("pj-name-cell")
                                    ui.label(pu["farms"]).classes("pj-muted")
                                    ui.label(ROLE_TEXT.get(pu["role"], pu["role"])).classes(f"pj-role {pu['role']}")
                                    with ui.element("div").classes("pj-status"):
                                        ui.element("span").classes("pj-dot on" if pu["is_online"] else "pj-dot")
                                        ui.label("Trực tuyến" if pu["is_online"] else "Ngoại tuyến")
                                    ui.label(pu["last_active"]).classes("pj-muted")
