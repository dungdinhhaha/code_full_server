"""
pages/schedule.py — Irrigation Scheduling Page
Layout đúng pattern hệ thống: sidebar + main-content + global_topbar
"""

from nicegui import ui, app
from pages.home import CUSTOM_CSS, sidebar, state, global_topbar
from pages.login import check_login
from service import auth
import datetime
from service.logger import get_logger

logger = get_logger("SCHEDULE")

# CSS riêng cho Schedule page
SCHEDULE_CSS = """
.timeline-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    position: absolute;
    left: -21px; top: 4px;
    border: 2px solid white;
    box-shadow: 0 0 0 2px #e2e8f0;
}
.timeline-dot-green { background: #22c55e; box-shadow: 0 0 0 2px #dcfce7; }
.timeline-dot-cyan { background: #06b6d4; box-shadow: 0 0 0 2px #cffafe; animation: pulse-cyan 2s infinite; }

@keyframes pulse-cyan {
    0% { box-shadow: 0 0 0 2px #cffafe; }
    50% { box-shadow: 0 0 0 6px rgba(6,182,212,0.2); }
    100% { box-shadow: 0 0 0 2px #cffafe; }
}

.stats-dark-box {
    background: #1e293b;
    border-radius: 14px;
    padding: 16px 20px;
    color: white;
}

.day-card {
    background: white;
    border: 1px solid #e8ecf0;
    border-radius: 14px;
    padding: 14px;
    transition: transform 0.25s cubic-bezier(0.25, 0.8, 0.25, 1),
                box-shadow 0.25s cubic-bezier(0.25, 0.8, 0.25, 1),
                border-color 0.2s ease,
                background-color 0.2s ease;
}
.day-card:hover {
    border-color: #cbd5e1;
    box-shadow: 0 8px 20px rgba(0,0,0,0.08);
    transform: translateY(-4px);
}
.day-card-active {
    background: #eff6ff !important;
    border-color: #3b82f6 !important;
    box-shadow: 0 8px 25px rgba(59, 130, 246, 0.25) !important;
    transform: translateY(-4px);
}
.day-card-today {
    position: relative;
    border-style: dashed !important;
    border-color: #10b981 !important;
}
.day-card-today::before {
    content: 'Hôm nay';
    position: absolute;
    top: 6px;
    right: 8px;
    font-size: 8px;
    font-weight: 800;
    background: #10b981;
    color: white;
    padding: 2px 6px;
    border-radius: 6px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    z-index: 10;
}

.status-badge-running {
    background: #06b6d4 !important;
    animation: status-pulse 1.5s infinite;
}
@keyframes status-pulse {
    0% { opacity: 1; }
    50% { opacity: 0.7; }
    100% { opacity: 1; }
}

/* Industrial Modal Styles */
.industrial-modal {
    background-color: white !important;
    color: #1a1a2e !important;
    border: 1px solid #e2e8f0;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.1) !important;
}
.industrial-section-label {
    font-size: 10px;
    font-weight: 800;
    color: #64748b;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.industrial-input {
    border-radius: 8px;
}
.preview-box {
    background: #f0f9ff;
    border: 1px dashed #bae6fd;
    border-radius: 12px;
    padding: 16px;
    color: #0369a1;
    font-size: 13px;
    line-height: 1.6;
}

.day-chip {
    width: 44px;
    height: 44px;
    border-radius: 8px;
    font-weight: 700;
    font-size: 13px;
    transition: all 0.2s;
    border: 1px solid #e2e8f0;
    background: #f8fafc;
    color: #64748b;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
}
.day-chip-active {
    background: #0ea5e9 !important;
    color: white !important;
    border-color: #0ea5e9 !important;
}
"""


@ui.page('/schedule')
def trang_schedule():
    if not check_login():
        return

    # --- Config ---
    farm_key = app.storage.user.get('current_farm', 'greenhouse_a')
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    try:
        if 'schedule_state' not in app.storage.user:
            app.storage.user['schedule_state'] = {'selected_date': today_str, 'week_offset': 0}
        page_state = app.storage.user['schedule_state']
    except Exception:
        page_state = {'selected_date': today_str, 'week_offset': 0}

    # --- Backend Logic ---
    def refresh_all():
        card_1_header.refresh()
        schedule_table_container.refresh()
        timeline_section.refresh()
        weekly_section.refresh()
        stats_summary.refresh()

    def open_bulk_create_dialog():
        selected_days = set([0, 1, 2, 3, 4, 5, 6])
        day_names_vi = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
        watering_configs = [{"start_time": "06:00", "end_time": "06:10"}]

        page_state["dialog_open"] = True
        with ui.dialog().props('persistent').on('hide', lambda: page_state.update({"dialog_open": False})) as dialog, ui.card().classes("industrial-modal").style("width:560px; padding:0; border-radius:16px"):
            with ui.element("div").style("background:#f8fafc; padding:20px 24px; border-bottom:1px solid #e2e8f0"):
                with ui.row().classes("items-center justify-between w-full"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("settings_suggest", color="sky-500").style("font-size:24px")
                        ui.label("LÊN LỊCH CHẠY INVERTER").style("font-weight:900; font-size:16px")
                    ui.button(icon="close", on_click=dialog.close).props("flat round dense")

            def update_ui():
                for idx, btn in chips:
                    btn.classes(add="day-chip-active" if idx in selected_days else "", remove="day-chip-active" if idx not in selected_days else "")
                
                preview_details = []
                valid_configs = True
                for cfg in watering_configs:
                    try:
                        start_dt = datetime.datetime.strptime(cfg["start_time"], "%H:%M")
                        end_dt = datetime.datetime.strptime(cfg["end_time"], "%H:%M")
                        if end_dt <= start_dt:
                            valid_configs = False
                        preview_details.append(f"{cfg['start_time']} - {cfg['end_time']}")
                    except Exception:
                        valid_configs = False
                        preview_details.append(f"{cfg.get('start_time', '')} - {cfg.get('end_time', '')}")
                details_txt = ", ".join(preview_details)

                if selected_days:
                    days_txt = ", ".join([day_names_vi[i] for i in sorted(list(selected_days))])
                    preview_label.text = f"Vận hành {len(watering_configs)} lần mỗi ngày vào {days_txt} hàng tuần trong 30 ngày tới từ {start_date.value}: {details_txt}."
                else:
                    preview_label.text = f"Vận hành {len(watering_configs)} lần duy nhất vào ngày {start_date.value}: {details_txt}."
                
                create_btn.set_enabled(valid_configs and len(watering_configs) > 0)

            def save():
                try:
                    user_id = app.storage.user.get('user_id')
                    if not auth.check_permission(user_id, "manage_schedule"):
                        ui.notify("Bạn không có quyền tạo lịch trình", color="negative")
                        return

                    s_date = datetime.datetime.strptime(start_date.value, "%Y-%m-%d")
                    dates_to_add = []
                    
                    if not selected_days:
                        dates_to_add.append(start_date.value)
                    else:
                        for d in range(31):
                            curr = s_date + datetime.timedelta(days=d)
                            if curr.weekday() in selected_days:
                                dates_to_add.append(curr.strftime("%Y-%m-%d"))
                    
                    for cfg in watering_configs:
                        start_dt = datetime.datetime.strptime(cfg["start_time"], "%H:%M")
                        end_dt = datetime.datetime.strptime(cfg["end_time"], "%H:%M")
                        duration_mins = (end_dt - start_dt).total_seconds() / 60.0
                        auth.bulk_add_schedules(farm_key, dates_to_add, cfg["start_time"], float(duration_mins), user_id=user_id)
                    
                    ui.notify(f"✅ Đã tạo {len(dates_to_add) * len(watering_configs)} lịch trình!", color="positive")
                    dialog.close()
                    # Trigger cập nhật card 'Lịch tiếp theo' trên trang Home
                    state["_update_counter"] = state.get("_update_counter", 0) + 1
                    refresh_all()
                except Exception as ex: 
                    ui.notify(f"Lỗi: {ex}", color="negative")

            with ui.column().classes("w-full p-6 gap-6"):
                # Time Section
                with ui.column().classes("w-full gap-2"):
                    ui.label("📅 NGÀY & GIỜ VẬN HÀNH").classes("industrial-section-label")
                    start_date = ui.input("Ngày áp dụng", value=today_str, on_change=update_ui).props('type=date standout dense').classes("w-full")
                    
                    @ui.refreshable
                    def configs_list_ui():
                        with ui.column().classes("w-full gap-3 mt-2"):
                            for idx, cfg in enumerate(watering_configs):
                                with ui.row().classes("w-full gap-3 items-center"):
                                    ui.input("Bắt đầu", value=cfg["start_time"], on_change=lambda e, i=idx: (watering_configs[i].update({"start_time": e.value}), update_ui())) \
                                        .props('standout dense mask="##:##" fill-mask placeholder="00:00"') \
                                        .style("width: 120px")
                                    
                                    ui.input("Kết thúc", value=cfg["end_time"], on_change=lambda e, i=idx: (watering_configs[i].update({"end_time": e.value}), update_ui())) \
                                        .props('standout dense mask="##:##" fill-mask placeholder="00:00"') \
                                        .style("width: 120px")
                                    
                                    if len(watering_configs) > 1:
                                        ui.button(icon="delete", on_click=lambda i=idx: (watering_configs.pop(i), configs_list_ui.refresh(), update_ui())).props("flat round dense color=red-4")
                            
                            ui.button("THÊM KHUNG GIỜ CHẠY", icon="add_circle", on_click=lambda: (watering_configs.append({"start_time": "08:00", "end_time": "08:10"}), configs_list_ui.refresh(), update_ui())).props("flat dense").style("color:#0ea5e9; font-weight:800")
                    configs_list_ui()

                # Repeat Section
                with ui.column().classes("w-full gap-2"):
                    ui.label("🔄 CHU KỲ LẶP LẠI").classes("industrial-section-label")
                    with ui.row().classes("w-full justify-between"):
                        chips = []
                        for i, name in enumerate(day_names_vi):
                            def toggle(idx=i):
                                if idx in selected_days:
                                    selected_days.remove(idx)
                                else:
                                    selected_days.add(idx)
                                update_ui()
                            chips.append((i, ui.label(name).classes("day-chip").on("click", toggle)))

                # Preview
                with ui.element("div").classes("preview-box w-full"):
                    preview_label = ui.label("").style("font-size:12px")
                
                # Card thông báo quyền hạn mới ở dưới cùng
                with ui.element("div").classes("schedule-card w-full mt-6"):
                    ui.label("QUYỀN HẠN CỦA TÀI KHOẢN").style("font-size:10px; font-weight:800; color:#94a3b8; letter-spacing:0.1em; margin-bottom:16px")
                    with ui.row().classes("w-full gap-8"):
                        # Quyền Manage Schedule
                        has_manage = auth.check_permission(user_id, "manage_schedule")
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle" if has_manage else "cancel", color="emerald-500" if has_manage else "rose-400").style("font-size:20px")
                            ui.label("Quản lý lịch trình tưới").classes("text-sm font-bold " + ("text-slate-700" if has_manage else "text-slate-400"))
                        
                        # Quyền Export Excel
                        has_export = auth.check_permission(user_id, "export_schedule_logs")
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle" if has_export else "cancel", color="emerald-500" if has_export else "rose-400").style("font-size:20px")
                            ui.label("Xuất bản file báo cáo Excel").classes("text-sm font-bold " + ("text-slate-700" if has_export else "text-slate-400"))

                with ui.row().classes("w-full justify-end gap-3 mt-8 pt-4 border-t border-slate-100"):
                    ui.button("HỦY", on_click=dialog.close).props("flat").classes("text-slate-500 font-bold")
                    create_btn = ui.button("TẠO LỊCH TRÌNH", on_click=save).style("background:#0ea5e9; color:white; font-weight:800; border-radius:10px; padding:0 24px")

            update_ui()
        dialog.open()

    def delete_schedule_entry(e):
        if auth.delete_schedule(e.args, user_id=user_id):
            ui.notify('🗑️ Đã xóa lịch tưới.', color='info')
            # Trigger cập nhật card 'Lịch tiếp theo' trên trang Home
            state["_update_counter"] = state.get("_update_counter", 0) + 1
            refresh_all()
        else:
            ui.notify('Bạn không có quyền xóa lịch trình', color='negative')

    def open_edit_dialog(e):
        sch = e.args
        import datetime
        try:
            start_dt = datetime.datetime.strptime(sch['start_time'], "%H:%M")
            end_dt = start_dt + datetime.timedelta(minutes=float(sch['water_amount']))
            end_time_str = end_dt.strftime("%H:%M")
        except:
            end_time_str = sch['start_time']

        page_state["dialog_open"] = True
        with ui.dialog().props('persistent').on('hide', lambda: page_state.update({"dialog_open": False})) as dialog, ui.card().classes("industrial-modal").style("width:400px; padding:0; border-radius:16px"):
            with ui.element("div").style("background:#f8fafc; padding:16px 20px; border-bottom:1px solid #e2e8f0"):
                with ui.row().classes("items-center justify-between w-full"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("edit", color="sky-500").style("font-size:22px")
                        ui.label(f"CHỈNH SỬA LỊCH #{sch['id']}").style("font-weight:900; font-size:15px")
                    ui.button(icon="close", on_click=dialog.close).props("flat round dense")
            
            with ui.column().classes("w-full p-6 gap-4"):
                edit_time = ui.input("Giờ bắt đầu", value=sch['start_time']).props('standout dense mask="##:##" fill-mask placeholder="00:00"').style("width: 100%")
                edit_end_time = ui.input("Giờ kết thúc", value=end_time_str).props('standout dense mask="##:##" fill-mask placeholder="00:00"').style("width: 100%")
                
                def save_edit():
                    try:
                        time_val = edit_time.value
                        end_val = edit_end_time.value
                        if not time_val or not end_val:
                            ui.notify("Vui lòng điền thông tin hợp lệ!", color="warning")
                            return
                        start_dt = datetime.datetime.strptime(time_val, "%H:%M")
                        end_dt = datetime.datetime.strptime(end_val, "%H:%M")
                        if end_dt <= start_dt:
                            ui.notify("Giờ kết thúc phải lớn hơn giờ bắt đầu!", color="warning")
                            return
                        water_val = (end_dt - start_dt).total_seconds() / 60.0
                            
                        success = auth.edit_schedule(sch['id'], time_val, float(water_val), user_id=user_id)
                        if success:
                            ui.notify(f"✅ Đã cập nhật lịch trình #{sch['id']}!", color="positive")
                            dialog.close()
                            # Trigger cập nhật card 'Lịch tiếp theo' trên trang Home
                            state["_update_counter"] = state.get("_update_counter", 0) + 1
                            refresh_all()
                        else:
                            ui.notify("Bạn không có quyền chỉnh sửa!", color="negative")
                    except Exception as ex:
                        ui.notify(f"Lỗi: {ex}", color="negative")
                
                with ui.row().classes("w-full justify-end gap-3 mt-4 pt-4 border-t border-slate-100"):
                    ui.button("HỦY", on_click=dialog.close).props("flat").classes("text-slate-500 font-bold")
                    ui.button("LƯU THAY ĐỔI", on_click=save_edit).style("background:#0ea5e9; color:white; font-weight:800; border-radius:10px; padding:0 24px")
        dialog.open()

    # ─── UI Layout (Tối ưu vị trí và kích thước) ────────────────
    ui.add_head_html(f"""
    <style>
    {CUSTOM_CSS}
    {SCHEDULE_CSS}
    /* Animations for status badges */
    @keyframes pulse-green {{
        0% {{ box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); }}
        70% {{ box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }}
    }}
    @keyframes pulse-cyan {{
        0% {{ box-shadow: 0 0 0 0 rgba(6, 182, 212, 0.4); }}
        70% {{ box-shadow: 0 0 0 8px rgba(6, 182, 212, 0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(6, 182, 212, 0); }}
    }}
    @keyframes pulse-orange {{
        0% {{ box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4); }}
        70% {{ box-shadow: 0 0 0 8px rgba(245, 158, 11, 0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }}
    }}
    @keyframes pulse-red {{
        0% {{ box-shadow: 0 0 0 0 rgba(244, 63, 94, 0.4); }}
        70% {{ box-shadow: 0 0 0 8px rgba(244, 63, 94, 0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(244, 63, 94, 0); }}
    }}

    .badge-completed {{ animation: pulse-green 2s infinite; }}
    .badge-running {{ animation: pulse-cyan 1.5s infinite; }}
    .badge-pending {{ animation: pulse-orange 2.5s infinite; }}
    .badge-failed {{ animation: pulse-red 1.5s infinite; }}

    /* Responsive Grid - Cố định 60/40 cho màn hình lớn */
    .schedule-grid {{
        display: grid;
        grid-template-columns: 1.5fr 1fr;
        gap: 24px;
        width: 100%;
        align-items: stretch;
    }}
    
    .schedule-card {{
        background: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.5);
        border-radius: 32px;
        padding: 24px;
        box-shadow: 0 8px 32px rgba(31, 38, 135, 0.05);
        transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1),
                    box-shadow 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    }}
    
    .schedule-card:hover {{
        box-shadow: 0 15px 35px rgba(31, 38, 135, 0.12);
        transform: translateY(-6px);
    }}

    @media (max-width: 1200px) {{
        .schedule-grid {{
            grid-template-columns: 1fr;
        }}
    }}
    </style>
    """)
    sidebar(active="Schedule")

    with ui.element("div").classes("main-content"):
        user_id = app.storage.user.get('user_id')
        can_manage = auth.check_permission(user_id, "manage_schedule")
        can_export = auth.check_permission(user_id, "export_schedule_logs")

        # Gọi trực tiếp global_topbar rộng 100% bám sát cạnh trang
        global_topbar("Quản Lý Lịch Trình", "⏰")
        
        with ui.element("div").classes("content-area"):
            # ── SECTION HEADER (Sub-topbar dưới Topbar chính) ──
            with ui.element("div").classes(
                "w-full bg-white/80 backdrop-blur-md border border-slate-100 rounded-2xl shadow-sm p-4 mb-5 "
                "flex items-center gap-4"
            ):
                ui.label("📅  QUẢN LÝ LỊCH TRÌNH TƯỚI").style(
                    "font-size:13px; font-weight:800; color:#059669;"
                    "letter-spacing:0.05em; text-transform:uppercase"
                )

            # ── ROW 1: CONTROL CENTER (1.5) & STATS/TIMELINE (1) ──
            with ui.element("div").classes("schedule-grid"):
                
                # ═══ CỘT TRÁI: Control Center ═══
                with ui.element("div").classes("h-full"):
                    with ui.element("div").classes("schedule-card h-full").style("min-height:450px"):
                        def export_excel():
                            if not auth.check_permission(user_id, "export_schedule_logs"):
                                ui.notify('Tài khoản của bạn không có quyền xuất báo cáo Excel', color='negative')
                                return
                            
                            try:
                                import pandas as pd
                                import os
                                from service.auth import get_all_schedule_logs
                                
                                logs = get_all_schedule_logs(farm_key)
                                if not logs:
                                    ui.notify('Không có dữ liệu để xuất', color='warning')
                                    return
                                    
                                formatted_data = []
                                for i, log in enumerate(logs):
                                    status_map = {
                                        "completed": "HOÀN THÀNH",
                                        "running": "ĐANG CHẠY",
                                        "failed": "LỖI",
                                        "pending": "CHỜ"
                                    }
                                    formatted_data.append({
                                        "STT": i + 1,
                                        "Mã Lịch": f"#{log['id']}",
                                        "Ngày Dự Kiến": log.get('schedule_date', ''),
                                        "Giờ Dự Kiến": log.get('start_time', ''),
                                        "Bắt Đầu Thực Tế": log.get('start_at', '') or '-',
                                        "Kết Thúc Thực Tế": log.get('end_at', '') or '-',
                                        "Thời Lượng (Phút)": log.get('target_water', 0),
                                        "Nước Thực Tế (L)": log.get('actual_water', 0) or 0,
                                        "Trạng Thái": status_map.get(log.get('status', ''), log.get('status', '')).upper(),
                                        "Khu Vực": log.get('farm_key', '')
                                    })
                                    
                                df = pd.DataFrame(formatted_data)
                                os.makedirs('/tmp', exist_ok=True)
                                filepath = f"/tmp/NhatKyTuoiTieu_{farm_key}.xlsx"
                                
                                df.to_excel(filepath, index=False)
                                ui.download(filepath)
                                ui.notify('Đã tải xuống báo cáo Excel thành công', color='positive')
                            except Exception as e:
                                ui.notify(f'Lỗi tạo file Excel: {e}', color='negative')

                        @ui.refreshable
                        def card_1_header():
                            user_id = app.storage.user.get('user_id')
                            can_manage = auth.check_permission(user_id, "manage_schedule")
                            can_export = auth.check_permission(user_id, "export_schedule_logs")

                            with ui.row().classes("w-full justify-between items-center mb-4"):
                                with ui.row().classes("items-center gap-3"):
                                    ui.label("📋").classes("bg-blue-50 p-2 rounded-lg")
                                    with ui.column().classes("gap-0"):
                                        ui.label("Control Center").style("font-size:16px; font-weight:700; color:#1a1a2e")
                                        ui.label(f"Ngày đang xem: {page_state['selected_date']}").style("font-size:11px; color:#64748b; font-weight:600")

                                with ui.row().classes("gap-2"):
                                    export_btn = ui.button("XUẤT EXCEL", on_click=export_excel).style(
                                        "background:#f0fdf4; color:#166534; border:1px solid #bbf7d0; "
                                        "border-radius:8px; font-size:11px; font-weight:700; "
                                        "padding:8px 16px; letter-spacing:0.05em"
                                    ).props("flat icon=download")
                                    if not can_export:
                                        export_btn.classes("opacity-50 cursor-not-allowed grayscale")
                                        export_btn.tooltip("Bạn không có quyền xuất Excel")
                                    
                                    add_btn = ui.button("LÊN LỊCH", on_click=open_bulk_create_dialog).style(
                                        "background:white; color:#1e293b; border:1px solid #e2e8f0; "
                                        "border-radius:8px; font-size:11px; font-weight:700; "
                                        "padding:8px 20px; letter-spacing:0.05em"
                                    ).props("flat icon=add")
                                    if not can_manage:
                                        add_btn.classes("opacity-50 cursor-not-allowed grayscale")
                                        add_btn.tooltip("Bạn không có quyền quản lý lịch trình")
                        card_1_header()

                        @ui.refreshable
                        def schedule_table_container():
                            import datetime
                            user_id = app.storage.user.get('user_id')
                            can_manage = auth.check_permission(user_id, "manage_schedule")
                            
                            schedules = auth.get_schedules(farm_key, date=page_state['selected_date'])
                            if not schedules:
                                with ui.column().classes("w-full items-center py-16 text-slate-400"):
                                    ui.label("📭").style("font-size:48px; margin-bottom:12px")
                                    ui.label("Chưa có lịch tưới nào").classes("text-sm font-bold")
                                    ui.label("Nhấn 'LÊN LỊCH' để tạo lịch trình mới").classes("text-xs")
                                return

                            formatted_schedules = []
                            for sch in schedules:
                                sch_copy = dict(sch)
                                try:
                                    start_dt = datetime.datetime.strptime(sch["start_time"], "%H:%M")
                                    end_dt = start_dt + datetime.timedelta(minutes=float(sch["water_amount"]))
                                    sch_copy["time_range"] = f"{sch['start_time']} - {end_dt.strftime('%H:%M')}"
                                except Exception:
                                    sch_copy["time_range"] = sch["start_time"]
                                water_val = sch.get('actual_water')
                                if sch['status'] == 'completed' and water_val is not None:
                                    sch_copy['water'] = f"{water_val} L"
                                else:
                                    sch_copy['water'] = "-"
                                formatted_schedules.append(sch_copy)

                            columns = [
                                {'name': 'id', 'label': 'ID', 'field': 'id', 'align': 'left'},
                                {'name': 'time_range', 'label': 'Thời gian tưới', 'field': 'time_range', 'align': 'left'},
                                {'name': 'water', 'label': 'Nước (L)', 'field': 'water', 'align': 'center'},
                                {'name': 'status', 'label': 'Trạng thái', 'field': 'status', 'align': 'center'},
                                {'name': 'action', 'label': '', 'field': 'id', 'align': 'right'},
                            ]
                            tbl = ui.table(columns=columns, rows=formatted_schedules).props('flat bordered dense separator=cell').classes("w-full mt-2")
                            tbl.add_slot('body-cell-status', '''
                                <q-td :props="props">
                                    <q-badge :color="props.value==='completed'?'green':props.value==='running'?'cyan':props.value==='pending_run'?'amber':props.value==='failed'?'red':'orange'" 
                                             :class="'badge-' + props.value"
                                             style="padding:4px 10px; border-radius:12px; font-weight:800; text-transform:uppercase; font-size:10px">
                                        {{props.value==='completed'?'HOÀN THÀNH':props.value==='running'?'ĐANG CHẠY':props.value==='pending_run'?'ĐANG GỬI LỆNH':props.value==='failed'?'LỖI':'CHỜ'}}
                                    </q-badge>
                                </q-td>
                            ''')
                            
                            # Cấu hình nút sửa, xóa và retry có phân quyền
                            edit_btn_props = 'flat round dense icon="edit" size="sm" class="mr-1"'
                            del_btn_props = 'flat round dense icon="delete" size="sm"'
                            retry_btn_props = 'flat round dense icon="replay" size="sm" class="mr-1"'
                            if can_manage:
                                tbl.add_slot('body-cell-action', f'''
                                    <q-td :props="props" class="text-right">
                                        <q-btn v-if="props.row.status==='failed'" {retry_btn_props} color="orange-7" @click="$parent.$emit('retry', props.row)">
                                            <q-tooltip>Thử lại lịch đã lỗi</q-tooltip>
                                        </q-btn>
                                        <q-btn {edit_btn_props} color="sky-500" @click="$parent.$emit('edit', props.row)" />
                                        <q-btn {del_btn_props} color="red-4" @click="$parent.$emit('delete', props.value)" />
                                    </q-td>
                                ''')
                            else:
                                tbl.add_slot('body-cell-action', f'''
                                    <q-td :props="props" class="text-right">
                                        <q-btn {edit_btn_props} color="grey-4" class="cursor-not-allowed opacity-50"><q-tooltip>Bạn không có quyền sửa</q-tooltip></q-btn>
                                        <q-btn {del_btn_props} color="grey-4" class="cursor-not-allowed opacity-50"><q-tooltip>Bạn không có quyền xóa</q-tooltip></q-btn>
                                    </q-td>
                                ''')
                            
                            def retry_schedule_entry(e):
                                sch_row = e.args
                                if auth.reset_schedule_to_pending(sch_row['id'], user_id=user_id):
                                    ui.notify(f"🔄 Lịch #{sch_row['id']} đã được đặt lại trạng thái CHỜ", color="positive")
                                    state["_update_counter"] = state.get("_update_counter", 0) + 1
                                    refresh_all()
                                else:
                                    ui.notify("Bạn không có quyền thực hiện hành động này", color="negative")

                            tbl.on('retry', retry_schedule_entry)
                            tbl.on('edit', open_edit_dialog)
                            tbl.on('delete', delete_schedule_entry)
                        
                        schedule_table_container()

                # ═══ CỘT PHẢI: Stats & Timeline ═══
                with ui.element("div").classes("h-full"):
                    with ui.column().classes("gap-4 w-full h-full"):
                        # Card Thống kê (Đưa vào đây để cân đối)
                        @ui.refreshable
                        def stats_summary():
                            schedules = auth.get_schedules(farm_key, date=today_str)
                            total = len(schedules)
                            done = len([s for s in schedules if s['status'] == 'completed'])
                            try:
                                water = auth.get_total_actual_water(farm_key, today_str)
                            except Exception:
                                water = 0.0
                            with ui.column().classes("stats-dark-box w-full"):
                                with ui.row().classes("w-full justify-between items-center"):
                                    with ui.column().classes("gap-0"):
                                        ui.label(f"{done}/{total}").classes("text-3xl font-black")
                                        ui.label("LẦN TƯỚI HÔM NAY").classes("text-[9px] font-bold text-slate-400 letter-spacing-1")
                                    with ui.column().classes("items-end gap-0"):
                                        ui.label(f"{water:.0f}L").classes("text-3xl font-black text-cyan-400")
                                        ui.label("TỔNG NƯỚC").classes("text-[9px] font-bold text-slate-400 letter-spacing-1")
                        stats_summary()

                        # Card Activity Timeline (Co giãn theo chiều cao bằng flex-1)
                        with ui.element("div").classes("schedule-card w-full flex-1 flex flex-col").style("min-height:300px"):
                            @ui.refreshable
                            def timeline_section():
                                logs = auth.get_today_logs(farm_key)
                                with ui.row().classes("w-full justify-between items-center mb-4"):
                                    ui.label("Activity Timeline").classes("font-bold text-slate-800 text-base")
                                    def clear_logs():
                                        if not auth.check_permission(user_id, "manage_schedule"):
                                            ui.notify("Bạn không có quyền xóa lịch sử", color="negative")
                                            return
                                        auth.clear_today_logs(farm_key)
                                        ui.notify("🗑️ Đã xóa lịch sử tưới hôm nay.")
                                        refresh_all()
                                    
                                    clear_btn = ui.button(icon="delete_sweep", on_click=clear_logs).props("flat round dense size=sm color=red-3").tooltip("Xóa lịch sử hôm nay")
                                    if not can_manage:
                                        clear_btn.classes("opacity-30 cursor-not-allowed grayscale")

                                if not logs:
                                    ui.label("Chưa có hoạt động hôm nay").classes("text-xs text-slate-400 italic py-4")
                                    return
                                    
                                with ui.column().classes("gap-3 pl-8 ml-2 relative flex-1 overflow-y-auto"):
                                    # Đường kẻ dọc absolute không bị cắt bởi overflow-y-auto
                                    ui.element("div").classes("absolute bg-slate-100").style("width: 2px; left: 11px; top: 0; bottom: 0; z-index: 0")
                                    
                                    for log in logs[:10]:
                                        status = log.get('status')
                                        st_label = "HOÀN THÀNH" if status == 'completed' else "ĐANG TƯỚI" if status == 'running' else "ĐANG GỬI LỆNH" if status == 'pending_run' else "LỖI"
                                        dot_color = "cyan-500" if status == 'running' else "amber-500" if status == 'pending_run' else ("green-500" if status == 'completed' else "red-500")
                                        
                                        with ui.column().classes("gap-0 relative").style("z-index: 1"):
                                            # Dấu chấm tròn đè lên đường kẻ dọc
                                            ui.element("div").classes(f"absolute w-2.5 h-2.5 rounded-full bg-{dot_color} border-2 border-white").style("left: -25px; top: 4px")
                                            ui.label(log.get('start_at', '')[-8:]).classes("text-[9px] font-bold text-slate-400")
                                            
                                            with ui.row().classes("items-center gap-2"):
                                                ui.label(f"Lịch #{log.get('schedule_id') or '?'}").classes("text-xs font-bold text-slate-700")
                                                if status == 'running':
                                                    ui.label("ĐANG CHẠY").classes("text-[7px] px-1 bg-cyan-100 text-cyan-600 font-black rounded")
                                                elif status == 'completed':
                                                    ui.label("HOÀN THÀNH").classes("text-[7px] px-1 bg-emerald-100 text-emerald-600 font-black rounded")
                                                elif status == 'pending_run':
                                                    ui.label("ĐANG GỬI LỆNH").classes("text-[7px] px-1 bg-amber-100 text-amber-600 font-black rounded")
                                                else:
                                                    ui.label("LỖI").classes("text-[7px] px-1 bg-rose-100 text-rose-600 font-black rounded")
                            timeline_section()

            # ── ROW 2: WEEKLY OVERVIEW (Tràn 100% chiều ngang) ──
            @ui.refreshable
            def weekly_section():
                now = datetime.datetime.now()
                monday = now - datetime.timedelta(days=now.weekday()) + datetime.timedelta(weeks=page_state['week_offset'])
                day_names = ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'CN']
                
                with ui.element("div").classes("schedule-card mt-6 w-full"):
                    with ui.row().classes("w-full justify-between items-center mb-8"):
                        with ui.column().classes("gap-0"):
                            ui.label("Weekly Irrigation Overview").classes("font-bold text-slate-800 text-lg")
                            ui.label("THỐNG KÊ CHI TIẾT TỪNG NGÀY TRONG TUẦN").classes("text-[10px] font-bold text-slate-400")
                        
                        with ui.row().classes("items-center gap-4 bg-slate-50 p-2 rounded-xl border border-slate-100"):
                            ui.button(icon="chevron_left", on_click=lambda: (page_state.update({"week_offset": page_state['week_offset']-1}), refresh_all())).props("flat round dense")
                            ui.label(f"{monday.strftime('%d/%m')} - {(monday+datetime.timedelta(days=6)).strftime('%d/%m')}").classes("text-sm font-black text-slate-700")
                            ui.button(icon="chevron_right", on_click=lambda: (page_state.update({"week_offset": page_state['week_offset']+1}), refresh_all())).props("flat round dense")

                    # Lưới các ngày dàn đều 100% chuẩn CSS Grid
                    with ui.element("div").classes("w-full grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4"):
                        for i in range(7):
                            d_date = monday + datetime.timedelta(days=i)
                            d_str = d_date.strftime("%Y-%m-%d")
                            is_sel = (d_str == page_state['selected_date'])
                            is_today = (d_str == today_str)
                            
                            day_scheds = auth.get_schedules(farm_key, date=d_str)
                            total = len(day_scheds)
                            done = len([s for s in day_scheds if s['status'] == 'completed'])
                            pct = (done/total*100) if total > 0 else 0
                            
                            card_classes = "day-card cursor-pointer w-full hover-elevate relative overflow-hidden group"
                            if is_sel:
                                card_classes += " day-card-active"
                            if is_today:
                                card_classes += " day-card-today neon-glow"
                                
                            with ui.column().classes(card_classes).style("min-height:160px").on("click", lambda _, ds=d_str: (page_state.update({"selected_date": ds}), refresh_all())):
                                ui.element("div").classes("shimmer-overlay")
                                ui.label(day_names[i]).classes(f"text-[10px] font-black uppercase tracking-wider {'text-blue-500' if is_sel else 'text-slate-400'}")
                                ui.label(f"{done}/{total}").classes("text-2xl font-black text-slate-800 my-1")
                                
                                # Progress bar
                                with ui.element("div").classes("w-full h-2 bg-slate-100 rounded-full overflow-hidden mb-3"):
                                    ui.element("div").classes("progress-bar").style(f"width:{pct}%; height:100%; background:#3b82f6")
                                
                                # Tóm tắt lịch
                                if day_scheds:
                                    with ui.column().classes("gap-1"):
                                        for s in day_scheds[:2]:
                                            try:
                                                s_st = datetime.datetime.strptime(s['start_time'], "%H:%M")
                                                s_end = s_st + datetime.timedelta(minutes=float(s['water_amount']))
                                                range_str = f"{s['start_time']} - {s_end.strftime('%H:%M')}"
                                            except:
                                                range_str = s['start_time']
                                            ui.label(f"⏰ {range_str}").classes("text-[9px] font-bold text-slate-500")
                                        if total > 2:
                                            ui.label(f"+ {total-2} lịch khác").classes("text-[8px] italic text-slate-400")
                                else:
                                    ui.label("—").classes("text-slate-300")

                    # 📊 BIỂU ĐỒ THỐNG KÊ LƯU LƯỢNG NƯỚC (Căn chỉnh tránh tràn)
                    with ui.element("div").style("margin-top:32px; height:320px; width:100%; border-top:1px solid #f1f5f9; padding-top:24px; box-sizing:border-box; overflow:hidden"):
                        chart_data = []
                        for i in range(7):
                            day_date = monday + datetime.timedelta(days=i)
                            day_str = day_date.strftime("%Y-%m-%d")
                            # Tính tổng nước thực tế từ DB
                            total_actual = auth.get_total_actual_water(farm_key, day_str)
                            chart_data.append(float(total_actual))

                        ui.echart({
                            'title': {'text': 'Lưu lượng nước thực tế (Lít)', 'left': 'center', 'textStyle': {'fontSize': 12, 'color': '#64748b'}},
                            'tooltip': {'trigger': 'axis'},
                            'xAxis': {'type': 'category', 'data': day_names},
                            'yAxis': {'type': 'value'},
                            'series': [{
                                'data': chart_data,
                                'type': 'bar',
                                'itemStyle': {'color': '#3b82f6', 'borderRadius': [4, 4, 0, 0]},
                                'barWidth': '40%'
                            }],
                            'grid': {'top': 40, 'bottom': 20, 'left': 40, 'right': 10}
                        }).style("height:100%")
            weekly_section()

            # ── ROW 2: ACCOUNT PERMISSIONS SUMMARY ──
            with ui.element("div").classes("schedule-card w-full mt-4"):
                ui.label("QUYỀN HẠN CỦA TÀI KHOẢN").style("font-size:10px; font-weight:800; color:#94a3b8; letter-spacing:0.1em; margin-bottom:12px")
                with ui.row().classes("w-full gap-12"):
                    # Manage Schedule
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("check_circle" if can_manage else "cancel", color="emerald-500" if can_manage else "rose-400").style("font-size:22px")
                        ui.label("Quản lý lịch trình tưới").classes("text-sm font-bold " + ("text-slate-700" if can_manage else "text-slate-400"))
                    
                    # Export Logs
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("check_circle" if can_export else "cancel", color="emerald-500" if can_export else "rose-400").style("font-size:22px")
                        ui.label("Xuất bản file báo cáo Excel").classes("text-sm font-bold " + ("text-slate-700" if can_export else "text-slate-400"))

    # ─── Timers & Logic Ngầm ──────────────────────────────
    # ─── Timers & Logic Ngầm ──────────────────────────────
    def check_schedule_ui_update():
        if page_state.get("dialog_open", False):
            return
            
        if not hasattr(check_schedule_ui_update, "last_counter"):
            check_schedule_ui_update.last_counter = 0
            
        current_counter = state.get("_update_counter", 0)
        if current_counter != check_schedule_ui_update.last_counter:
            check_schedule_ui_update.last_counter = current_counter
            refresh_all()
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

    t_ui_sync = ui.timer(2.0, check_schedule_ui_update)
    ui.context.client.on_disconnect(t_ui_sync.deactivate)

    # Khởi tạo dữ liệu lần đầu
    ui.timer(1.0, lambda: refresh_all(), once=True)

