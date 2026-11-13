"""
pages/schedule.py - Lịch tưới của nhà màng đang chọn.

Thiết bị ảo: lệnh và số đo là dữ liệu mô phỏng, hiển thị kèm nhãn rõ ràng.
"""

import datetime
import os
import tempfile

from nicegui import app, ui

from components.theme import CHART
from components.ui_kit import (
    confirm, page_header, panel, sim_badge, source_note, state_panel, stat, stats, status_chip,
)
from pages.home import CUSTOM_CSS, sidebar, state, global_topbar
from pages.login import check_login
from service import auth
from service.farm_registry import FARM_KEYS_BY_LABEL, FARM_LABELS
from service.logger import get_logger

logger = get_logger("SCHEDULE")

DAY_NAMES = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]
DAY_SHORT = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
STATUS_TEXT = {"completed": "Hoàn thành", "running": "Đang chạy", "pending_run": "Đang gửi lệnh", "failed": "Lỗi"}

SCHEDULE_CSS = """
.sch-grid { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr); gap: 16px; align-items: start; }
.sch-days { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; }
.sch-day { display: flex; flex-direction: column; gap: 4px; min-width: 0; padding: 10px; text-align: left;
           background: var(--sm-surface); border: 1px solid var(--sm-net-soft); border-radius: var(--sm-r-s);
           color: var(--sm-ink); font: inherit; cursor: pointer; }
.sch-day.sel { border-color: var(--sm-vine); box-shadow: inset 0 0 0 1px var(--sm-vine); }
.sch-day.today { border-style: dashed; border-color: var(--sm-ok); }
.sch-day-name { font-size: 12px; color: var(--sm-ink-3); }
.sch-day-count { font-family: var(--sm-display); font-size: 20px; font-weight: 700; line-height: 1.1; }
.sch-track { height: 4px; background: var(--sm-sunken); border-radius: 2px; overflow: hidden; }
.sch-track > i { display: block; height: 100%; background: var(--sm-vine); }
.sch-line { font-size: 11px; color: var(--sm-ink-2); }
.sch-log { display: grid; grid-template-columns: 10px minmax(0, 1fr); gap: 10px; padding: 10px 0;
           border-bottom: 1px solid var(--sm-net-soft); }
.sch-log:last-child { border-bottom: 0; }
.sch-dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 6px; background: var(--sm-none); }
.sch-dot.running { background: var(--sm-info); }
.sch-dot.completed { background: var(--sm-ok); }
.sch-dot.pending_run { background: var(--sm-watch); }
.sch-dot.failed { background: var(--sm-act); }
.sch-st { display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: var(--sm-r-s);
          background: var(--sm-none-tint); color: var(--sm-ink-2); }
.sch-st.completed { background: var(--sm-ok-tint); color: var(--sm-ok); }
.sch-st.running { background: var(--sm-info-tint); color: var(--sm-info); }
.sch-st.pending_run { background: var(--sm-watch-tint); color: var(--sm-watch); }
.sch-st.failed { background: var(--sm-act-tint); color: var(--sm-act); }
.sch-dayrow { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 6px; }
.sch-chip { height: 40px; border: 1px solid var(--sm-net-soft); border-radius: var(--sm-r-s);
            background: var(--sm-surface); color: var(--sm-ink-2); font: inherit; font-weight: 600; cursor: pointer; }
.sch-chip.on { background: var(--sm-vine); color: var(--sm-surface); border-color: var(--sm-vine); }
.sch-preview { background: var(--sm-sunken); border: 1px dashed var(--sm-net); border-radius: var(--sm-r-s);
               padding: 12px; font-size: 13px; color: var(--sm-ink-2); line-height: 1.5; }
.sch-dlg-head { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px;
                border-bottom: 1px solid var(--sm-net-soft); }
.sch-dlg-body { display: flex; flex-direction: column; gap: 16px; padding: 20px; }
.sch-dlg-foot { display: flex; justify-content: flex-end; gap: 8px; padding-top: 12px;
                border-top: 1px solid var(--sm-net-soft); }
@media (max-width: 1200px) { .sch-grid { grid-template-columns: 1fr; } }
@media (max-width: 720px) {
    .sch-days { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .sch-dayrow { gap: 4px; }
    .sch-chip { height: 36px; }
}
"""


def current_farm_key() -> str:
    """Nhà màng đang chọn. Đọc lại mỗi lần làm mới, không giữ từ lúc mở trang."""
    try:
        key = app.storage.user.get('current_farm')
    except Exception:
        key = None
    if key in FARM_LABELS:
        return key
    return FARM_KEYS_BY_LABEL.get(state.get("selected_farm", ""), "greenhouse_a")


def farm_name(key: str) -> str:
    return FARM_LABELS.get(key, key)


def _mongo_failed(ex: Exception, what: str) -> None:
    logger.warning(f"Không đọc được {what}: {ex}")


@ui.page('/schedule')
def trang_schedule():
    if not check_login():
        return

    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    user_id = app.storage.user.get('user_id')
    try:
        if 'schedule_state' not in app.storage.user:
            app.storage.user['schedule_state'] = {'selected_date': today_str, 'week_offset': 0}
        page_state = app.storage.user['schedule_state']
    except Exception:
        page_state = {'selected_date': today_str, 'week_offset': 0}

    # ── Refresh ─────────────────────────────────────────────────
    def refresh_all():
        scope_line.refresh()
        stats_block.refresh()
        table_block.refresh()
        timeline_block.refresh()
        week_block.refresh()

    def bump_and_refresh():
        state["_update_counter"] = state.get("_update_counter", 0) + 1
        refresh_all()

    def select_day(day_str: str):
        page_state["selected_date"] = day_str
        refresh_all()

    def shift_week(step: int):
        page_state["week_offset"] = page_state.get("week_offset", 0) + step
        refresh_all()

    # ── Xuất Excel ──────────────────────────────────────────────
    def do_export():
        uid = app.storage.user.get('user_id')
        if not auth.check_permission(uid, "export_schedule_logs"):
            ui.notify('Tài khoản của bạn không có quyền xuất báo cáo Excel', color='negative')
            return
        fk = current_farm_key()
        try:
            from service.auth import get_all_schedule_logs
            logs = get_all_schedule_logs(fk)
        except Exception as ex:
            _mongo_failed(ex, "nhật ký tưới")
            ui.notify('Không đọc được nhật ký từ MongoDB', color='negative')
            return
        if not logs:
            ui.notify('Không có dữ liệu để xuất', color='warning')
            return
        status_map = {"completed": "HOÀN THÀNH", "running": "ĐANG CHẠY", "failed": "LỖI", "pending": "CHỜ"}
        try:
            import pandas as pd
            rows = []
            for i, log in enumerate(logs):
                raw_status = log.get('status', '')
                rows.append({
                    "STT": i + 1,
                    "Mã Lịch": f"#{log['id']}",
                    "Ngày Dự Kiến": log.get('schedule_date', ''),
                    "Giờ Dự Kiến": log.get('start_time', ''),
                    "Bắt Đầu Thực Tế": log.get('start_at', '') or '-',
                    "Kết Thúc Thực Tế": log.get('end_at', '') or '-',
                    "Thời Lượng (Phút)": log.get('target_water', 0),
                    "Nước Thực Tế (L)": log.get('actual_water', 0) or 0,
                    "Trạng Thái": status_map.get(raw_status, str(raw_status)).upper(),
                    "Khu Vực": log.get('farm_key', ''),
                })
            filepath = os.path.join(tempfile.gettempdir(), f"NhatKyTuoiTieu_{fk}.xlsx")
            pd.DataFrame(rows).to_excel(filepath, index=False)
            ui.download(filepath)
            ui.notify('Đã tạo báo cáo Excel', color='positive')
        except Exception as e:
            ui.notify(f'Lỗi tạo file Excel: {e}', color='negative')

    # ── Lên lịch hàng loạt ──────────────────────────────────────
    def open_bulk_create_dialog():
        selected_days = set(range(7))
        watering_configs = [{"start_time": "06:00", "end_time": "06:10"}]

        page_state["dialog_open"] = True
        with ui.dialog().props('persistent').on(
                'hide', lambda: page_state.update({"dialog_open": False})) as dialog, \
                ui.card().props("flat bordered").style("width:560px;max-width:94vw;padding:0"):
            with ui.element("div").classes("sch-dlg-head"):
                ui.label("Lên lịch tưới").classes("sm-h2")
                ui.button(icon="close", on_click=dialog.close).props("flat round dense")

            chips = []

            def update_ui():
                for idx, btn in chips:
                    btn.classes(add="on" if idx in selected_days else "",
                                remove="" if idx in selected_days else "on")
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
                    days_txt = ", ".join(DAY_SHORT[i] for i in sorted(selected_days))
                    preview_label.text = (f"{len(watering_configs)} khung giờ mỗi ngày vào {days_txt}, "
                                          f"trong 31 ngày từ {start_date.value}: {details_txt}.")
                else:
                    preview_label.text = (f"{len(watering_configs)} khung giờ, một lần vào ngày "
                                          f"{start_date.value}: {details_txt}.")
                create_btn.set_enabled(valid_configs and len(watering_configs) > 0)

            async def save():
                uid = app.storage.user.get('user_id')
                if not auth.check_permission(uid, "manage_schedule"):
                    ui.notify("Bạn không có quyền tạo lịch trình", color="negative")
                    return
                try:
                    s_date = datetime.datetime.strptime(start_date.value, "%Y-%m-%d")
                except (TypeError, ValueError):
                    ui.notify("Ngày áp dụng chưa đúng định dạng", color="warning")
                    return
                if selected_days:
                    dates_to_add = [
                        (s_date + datetime.timedelta(days=d)).strftime("%Y-%m-%d")
                        for d in range(31)
                        if (s_date + datetime.timedelta(days=d)).weekday() in selected_days
                    ]
                else:
                    dates_to_add = [start_date.value]
                fk = current_farm_key()
                total = len(dates_to_add) * len(watering_configs)
                ok = await confirm(
                    "Tạo lịch tưới hàng loạt?",
                    f"Tạo {total} lịch cho {farm_name(fk)}, bắt đầu từ ngày {start_date.value}. "
                    "Có thể xóa từng lịch sau khi tạo.",
                    "Tạo lịch",
                )
                if not ok:
                    return
                try:
                    for cfg in watering_configs:
                        start_dt = datetime.datetime.strptime(cfg["start_time"], "%H:%M")
                        end_dt = datetime.datetime.strptime(cfg["end_time"], "%H:%M")
                        duration_mins = (end_dt - start_dt).total_seconds() / 60.0
                        auth.bulk_add_schedules(fk, dates_to_add, cfg["start_time"],
                                                float(duration_mins), user_id=uid)
                except Exception as ex:
                    _mongo_failed(ex, "ghi lịch tưới")
                    ui.notify("Không ghi được lịch vào MongoDB", color="negative")
                    return
                ui.notify(f"Đã tạo {total} lịch trình", color="positive")
                dialog.close()
                bump_and_refresh()

            with ui.element("div").classes("sch-dlg-body"):
                ui.label("Ngày và giờ").classes("sm-note")
                start_date = ui.input("Ngày áp dụng", value=today_str, on_change=update_ui) \
                    .props('type=date outlined dense').classes("w-full")

                @ui.refreshable
                def configs_list_ui():
                    with ui.column().classes("w-full gap-2"):
                        for idx, cfg in enumerate(watering_configs):
                            with ui.row().classes("w-full gap-3 items-center"):
                                ui.input("Bắt đầu", value=cfg["start_time"],
                                         on_change=lambda e, i=idx: (watering_configs[i].update({"start_time": e.value}), update_ui())) \
                                    .props('outlined dense mask="##:##" fill-mask placeholder="00:00"').style("width:120px")
                                ui.input("Kết thúc", value=cfg["end_time"],
                                         on_change=lambda e, i=idx: (watering_configs[i].update({"end_time": e.value}), update_ui())) \
                                    .props('outlined dense mask="##:##" fill-mask placeholder="00:00"').style("width:120px")
                                if len(watering_configs) > 1:
                                    ui.button(icon="delete", on_click=lambda i=idx: (
                                        watering_configs.pop(i), configs_list_ui.refresh(), update_ui())) \
                                        .props("flat round dense")
                        ui.button("Thêm khung giờ", icon="add", on_click=lambda: (
                            watering_configs.append({"start_time": "08:00", "end_time": "08:10"}),
                            configs_list_ui.refresh(), update_ui())).props("flat no-caps dense").classes("sm-btn-quiet")

                configs_list_ui()

                ui.label("Chu kỳ lặp lại").classes("sm-note")
                with ui.element("div").classes("sch-dayrow"):
                    for i, name in enumerate(DAY_SHORT):
                        def toggle(idx=i):
                            if idx in selected_days:
                                selected_days.remove(idx)
                            else:
                                selected_days.add(idx)
                            update_ui()
                        btn = ui.element("button").classes("sch-chip").props('type="button"')
                        with btn:
                            ui.label(name)
                        btn.on("click", lambda _e, t=toggle: t())
                        chips.append((i, btn))

                with ui.element("div").classes("sch-preview"):
                    preview_label = ui.label("")

                has_manage = auth.check_permission(user_id, "manage_schedule")
                has_export = auth.check_permission(user_id, "export_schedule_logs")
                with ui.row().classes("items-center gap-2"):
                    status_chip("ok" if has_manage else "none",
                                "Có quyền quản lý lịch" if has_manage else "Không có quyền quản lý lịch")
                    status_chip("ok" if has_export else "none",
                                "Có quyền xuất Excel" if has_export else "Không có quyền xuất Excel")

                with ui.element("div").classes("sch-dlg-foot"):
                    ui.button("Hủy", on_click=dialog.close).props("flat no-caps").classes("sm-btn-quiet")
                    create_btn = ui.button("Tạo lịch trình", on_click=save).props("unelevated no-caps").classes("sm-btn")

            update_ui()
        dialog.open()

    # ── Sửa, xóa, xóa nhật ký ───────────────────────────────────
    async def delete_schedule_entry(e):
        schedule_id = e.args
        uid = app.storage.user.get('user_id')
        ok = await confirm(
            f"Xóa lịch #{schedule_id}?",
            f"Lịch tưới này sẽ bị xóa khỏi {farm_name(current_farm_key())}. Thao tác không hoàn tác.",
            "Xóa lịch", danger=True,
        )
        if not ok:
            return
        if auth.delete_schedule(schedule_id, user_id=uid):
            ui.notify('Đã xóa lịch tưới.', color='info')
            bump_and_refresh()
        else:
            ui.notify('Bạn không có quyền xóa lịch trình', color='negative')

    async def clear_logs():
        uid = app.storage.user.get('user_id')
        if not auth.check_permission(uid, "manage_schedule"):
            ui.notify("Bạn không có quyền xóa lịch sử", color="negative")
            return
        fk = current_farm_key()
        ok = await confirm(
            "Xóa lịch sử tưới hôm nay?",
            f"Nhật ký hoạt động hôm nay của {farm_name(fk)} sẽ bị xóa. Thao tác không hoàn tác.",
            "Xóa lịch sử", danger=True,
        )
        if not ok:
            return
        auth.clear_today_logs(fk)
        ui.notify("Đã xóa lịch sử tưới hôm nay.")
        refresh_all()

    def open_edit_dialog(e):
        sch = e.args
        try:
            start_dt = datetime.datetime.strptime(sch['start_time'], "%H:%M")
            end_time_str = (start_dt + datetime.timedelta(minutes=float(sch['water_amount']))).strftime("%H:%M")
        except (KeyError, TypeError, ValueError):
            end_time_str = sch.get('start_time', '')

        page_state["dialog_open"] = True
        with ui.dialog().props('persistent').on(
                'hide', lambda: page_state.update({"dialog_open": False})) as dialog, \
                ui.card().props("flat bordered").style("width:400px;max-width:94vw;padding:0"):
            with ui.element("div").classes("sch-dlg-head"):
                ui.label(f"Sửa lịch #{sch['id']}").classes("sm-h2")
                ui.button(icon="close", on_click=dialog.close).props("flat round dense")

            with ui.element("div").classes("sch-dlg-body"):
                edit_time = ui.input("Giờ bắt đầu", value=sch['start_time']) \
                    .props('outlined dense mask="##:##" fill-mask placeholder="00:00"').classes("w-full")
                edit_end_time = ui.input("Giờ kết thúc", value=end_time_str) \
                    .props('outlined dense mask="##:##" fill-mask placeholder="00:00"').classes("w-full")

                def save_edit():
                    uid = app.storage.user.get('user_id')
                    try:
                        time_val = edit_time.value
                        end_val = edit_end_time.value
                        if not time_val or not end_val:
                            ui.notify("Vui lòng điền đủ giờ bắt đầu và kết thúc", color="warning")
                            return
                        start_dt = datetime.datetime.strptime(time_val, "%H:%M")
                        end_dt = datetime.datetime.strptime(end_val, "%H:%M")
                        if end_dt <= start_dt:
                            ui.notify("Giờ kết thúc phải lớn hơn giờ bắt đầu", color="warning")
                            return
                        water_val = (end_dt - start_dt).total_seconds() / 60.0
                        if auth.edit_schedule(sch['id'], time_val, float(water_val), user_id=uid):
                            ui.notify(f"Đã cập nhật lịch #{sch['id']}", color="positive")
                            dialog.close()
                            bump_and_refresh()
                        else:
                            ui.notify("Bạn không có quyền chỉnh sửa", color="negative")
                    except Exception as ex:
                        ui.notify(f"Lỗi: {ex}", color="negative")

                with ui.element("div").classes("sch-dlg-foot"):
                    ui.button("Hủy", on_click=dialog.close).props("flat no-caps").classes("sm-btn-quiet")
                    ui.button("Lưu thay đổi", on_click=save_edit).props("unelevated no-caps").classes("sm-btn")
        dialog.open()

    # ── Khối hiển thị ───────────────────────────────────────────
    @ui.refreshable
    def scope_line():
        fk = current_farm_key()
        with ui.row().classes("items-center gap-2"):
            status_chip("info", f"Nhà màng: {farm_name(fk)}")
            ui.label(f"Ngày {page_state['selected_date']}").classes("sm-note")

    @ui.refreshable
    def stats_block():
        fk = current_farm_key()
        try:
            scheds = auth.get_schedules(fk, date=today_str)
            water = float(auth.get_total_actual_water(fk, today_str) or 0)
        except Exception as ex:
            _mongo_failed(ex, "số liệu hôm nay")
            state_panel('error', 'Không đọc được số liệu hôm nay từ MongoDB',
                        'Kiểm tra kết nối rồi làm mới trang.')
            return
        total = len(scheds)
        done = sum(1 for s in scheds if s.get('status') == 'completed')
        failed = sum(1 for s in scheds if s.get('status') == 'failed')
        with stats():
            stat("Lần tưới hôm nay", f"{done}/{total}", meta=f"Hoàn thành / tổng lịch, {farm_name(fk)}")
            stat("Tổng nước hôm nay", f"{water:.0f}", unit="L", meta="Nước thực tế đã ghi nhận")
            stat("Lịch lỗi hôm nay", failed, meta="Cần thử lại hoặc kiểm tra thiết bị ảo",
                 level="act" if failed else None)

    @ui.refreshable
    def table_block():
        fk = current_farm_key()
        uid = app.storage.user.get('user_id')
        can_manage = auth.check_permission(uid, "manage_schedule")
        date_sel = page_state['selected_date']
        try:
            schedules = auth.get_schedules(fk, date=date_sel)
            farm_has_any = bool(schedules) or bool(auth.get_schedules(fk))
        except Exception as ex:
            _mongo_failed(ex, "lịch tưới")
            state_panel('error', 'Không đọc được lịch tưới từ MongoDB', 'Kiểm tra kết nối rồi làm mới trang.')
            return

        if not schedules:
            if farm_has_any:
                state_panel('empty', f'Chưa có lịch tưới ngày {date_sel}',
                            'Chọn ngày khác trên lịch tuần, hoặc lên lịch mới.')
            else:
                state_panel('empty', 'Farm này chưa có lịch tưới', 'Tạo lịch đầu tiên.',
                            action_label='Lên lịch' if can_manage else None,
                            on_action=open_bulk_create_dialog if can_manage else None)
            return

        formatted = []
        for sch in schedules:
            row = dict(sch)
            try:
                start_dt = datetime.datetime.strptime(sch["start_time"], "%H:%M")
                end_dt = start_dt + datetime.timedelta(minutes=float(sch["water_amount"]))
                row["time_range"] = f"{sch['start_time']} - {end_dt.strftime('%H:%M')}"
            except Exception:
                row["time_range"] = sch.get("start_time", "")
            water_val = sch.get('actual_water')
            row['water'] = f"{water_val} L" if sch.get('status') == 'completed' and water_val is not None else "-"
            formatted.append(row)

        columns = [
            {'name': 'id', 'label': 'Mã', 'field': 'id', 'align': 'left'},
            {'name': 'time_range', 'label': 'Thời gian tưới', 'field': 'time_range', 'align': 'left'},
            {'name': 'water', 'label': 'Nước', 'field': 'water', 'align': 'center'},
            {'name': 'status', 'label': 'Trạng thái', 'field': 'status', 'align': 'center'},
            {'name': 'action', 'label': '', 'field': 'id', 'align': 'right'},
        ]
        with ui.element("div").classes("sm-scroll-x"):
            tbl = ui.table(columns=columns, rows=formatted).props('flat bordered dense separator=cell') \
                .classes("w-full").style("min-width:520px")
        tbl.add_slot('body-cell-status', '''
            <q-td :props="props">
                <span :class="'sch-st ' + props.value">{{props.value==='completed'?'Hoàn thành':props.value==='running'?'Đang chạy':props.value==='pending_run'?'Đang gửi lệnh':props.value==='failed'?'Lỗi':'Chờ'}}</span>
            </q-td>
        ''')
        if can_manage:
            tbl.add_slot('body-cell-action', '''
                <q-td :props="props" class="text-right">
                    <q-btn v-if="props.row.status==='failed'" flat round dense icon="replay" size="sm"
                           @click="$parent.$emit('retry', props.row)"><q-tooltip>Thử lại lịch đã lỗi</q-tooltip></q-btn>
                    <q-btn flat round dense icon="edit" size="sm" @click="$parent.$emit('edit', props.row)"><q-tooltip>Sửa lịch</q-tooltip></q-btn>
                    <q-btn flat round dense icon="delete" size="sm" @click="$parent.$emit('delete', props.value)"><q-tooltip>Xóa lịch</q-tooltip></q-btn>
                </q-td>
            ''')
        else:
            tbl.add_slot('body-cell-action', '''
                <q-td :props="props" class="text-right">
                    <q-btn flat round dense icon="edit" size="sm" disable><q-tooltip>Bạn không có quyền sửa</q-tooltip></q-btn>
                    <q-btn flat round dense icon="delete" size="sm" disable><q-tooltip>Bạn không có quyền xóa</q-tooltip></q-btn>
                </q-td>
            ''')

        def retry_schedule_entry(e):
            sch_row = e.args
            if auth.reset_schedule_to_pending(sch_row['id'], user_id=uid):
                ui.notify(f"Lịch #{sch_row['id']} đã được đặt lại trạng thái chờ", color="positive")
                bump_and_refresh()
            else:
                ui.notify("Bạn không có quyền thực hiện hành động này", color="negative")

        tbl.on('retry', retry_schedule_entry)
        tbl.on('edit', open_edit_dialog)
        tbl.on('delete', delete_schedule_entry)

    @ui.refreshable
    def timeline_block():
        fk = current_farm_key()
        uid = app.storage.user.get('user_id')
        can_manage = auth.check_permission(uid, "manage_schedule")
        try:
            logs = auth.get_today_logs(fk)
        except Exception as ex:
            _mongo_failed(ex, "dòng hoạt động")
            state_panel('error', 'Không đọc được dòng hoạt động từ MongoDB', 'Kiểm tra kết nối rồi làm mới trang.')
            return

        with ui.row().classes("w-full items-center justify-between"):
            ui.label(f"Hôm nay, {farm_name(fk)}").classes("sm-note")
            clear_btn = ui.button("Xóa lịch sử hôm nay", on_click=clear_logs) \
                .props("flat no-caps dense").classes("sm-btn-quiet")
            if not can_manage:
                clear_btn.set_enabled(False)

        if not logs:
            state_panel('empty', 'Chưa có hoạt động hôm nay', 'Hoạt động sẽ hiện ở đây khi có lệnh tưới chạy.')
            return

        with ui.column().classes("w-full gap-0"):
            for log in logs[:10]:
                status = log.get('status') or ''
                with ui.element("div").classes("sch-log"):
                    ui.element("span").classes(f"sch-dot {status}")
                    with ui.element("div").style("min-width:0"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label(str(log.get('start_at', ''))[-8:]).classes("sm-stat-m")
                            ui.label(f"Lịch #{log.get('schedule_id') or '?'}") \
                                .style("font-size:13px;font-weight:600;color:var(--sm-ink)")
                            ui.label(STATUS_TEXT.get(status, "Chờ")).classes(f"sch-st {status}")

    @ui.refreshable
    def week_block():
        fk = current_farm_key()
        now = datetime.datetime.now()
        monday = now - datetime.timedelta(days=now.weekday()) + datetime.timedelta(weeks=page_state['week_offset'])
        sunday = monday + datetime.timedelta(days=6)
        try:
            days = []
            for i in range(7):
                d_str = (monday + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                day_scheds = auth.get_schedules(fk, date=d_str)
                done = sum(1 for s in day_scheds if s.get('status') == 'completed')
                days.append({
                    "str": d_str, "scheds": day_scheds, "total": len(day_scheds), "done": done,
                    "water": float(auth.get_total_actual_water(fk, d_str) or 0),
                })
        except Exception as ex:
            _mongo_failed(ex, "lịch tuần")
            state_panel('error', 'Không đọc được lịch tuần từ MongoDB', 'Kiểm tra kết nối rồi làm mới trang.')
            return

        with ui.row().classes("w-full items-center justify-between gap-2"):
            with ui.row().classes("items-center gap-1"):
                ui.button(icon="chevron_left", on_click=lambda: shift_week(-1)).props("flat round dense")
                ui.label(f"{monday.strftime('%d/%m')} - {sunday.strftime('%d/%m/%Y')}") \
                    .style("font-size:14px;font-weight:600;color:var(--sm-ink)")
                ui.button(icon="chevron_right", on_click=lambda: shift_week(1)).props("flat round dense")
            ui.button("Về tuần này", on_click=lambda: (page_state.update({"week_offset": 0}), refresh_all())) \
                .props("flat no-caps dense").classes("sm-btn-quiet")

        with ui.element("div").classes("sch-days").style("margin-top:12px"):
            for i, day in enumerate(days):
                pct = (day["done"] / day["total"] * 100) if day["total"] else 0
                classes = "sch-day"
                if day["str"] == page_state['selected_date']:
                    classes += " sel"
                if day["str"] == today_str:
                    classes += " today"
                btn = ui.element("button").classes(classes).props('type="button"') \
                    .on("click", lambda _e, ds=day["str"]: select_day(ds))
                with btn:
                    ui.label(DAY_NAMES[i]).classes("sch-day-name")
                    ui.label(f"{day['done']}/{day['total']}").classes("sch-day-count")
                    with ui.element("div").classes("sch-track"):
                        ui.element("i").style(f"width:{pct:.0f}%")
                    for s in day["scheds"][:2]:
                        try:
                            s_st = datetime.datetime.strptime(s['start_time'], "%H:%M")
                            s_end = s_st + datetime.timedelta(minutes=float(s['water_amount']))
                            range_str = f"{s['start_time']} - {s_end.strftime('%H:%M')}"
                        except Exception:
                            range_str = s.get('start_time', '')
                        ui.label(range_str).classes("sch-line")
                    if day["total"] > 2:
                        ui.label(f"+ {day['total'] - 2} lịch khác").classes("sm-note")

        ui.echart({
            "animation": False,
            "textStyle": {"fontFamily": CHART["font"], "color": CHART["ink"]},
            "tooltip": {"trigger": "axis"},
            "grid": {"left": 44, "right": 16, "top": 16, "bottom": 30},
            "xAxis": {"type": "category", "data": DAY_NAMES,
                      "axisLine": {"lineStyle": {"color": CHART["grid"]}},
                      "axisLabel": {"color": CHART["muted"]}},
            "yAxis": {"type": "value", "name": "Lít",
                      "splitLine": {"lineStyle": {"color": CHART["grid"]}},
                      "axisLabel": {"color": CHART["muted"]}},
            "series": [{"type": "bar", "barMaxWidth": 40,
                        "data": [round(d["water"], 1) for d in days],
                        "itemStyle": {"color": CHART["series"][0]}}],
        }).style("height:240px;width:100%;margin-top:12px")
        source_note(f"Đọc từ MongoDB lúc {datetime.datetime.now().strftime('%H:%M:%S')}, "
                    "nước thực tế của thiết bị ảo")

    # ── Layout ─────────────────────────────────────────────────
    ui.add_head_html(f"<style>{CUSTOM_CSS}{SCHEDULE_CSS}</style>")
    sidebar(active="Schedule")

    with ui.element("div").classes("main-content"):
        can_manage = auth.check_permission(user_id, "manage_schedule")
        can_export = auth.check_permission(user_id, "export_schedule_logs")

        global_topbar("Lịch tưới", "")

        with ui.element("div").classes("content-area"):
            slot = page_header(
                "Lịch hôm nay",
                "Lịch tưới của nhà màng đang chọn. Thiết bị ảo: lệnh và số đo là dữ liệu mô phỏng.",
            )
            with slot:
                sim_badge()
                export_btn = ui.button("Xuất Excel", icon="download", on_click=do_export) \
                    .props("flat no-caps").classes("sm-btn-quiet")
                if not can_export:
                    export_btn.set_enabled(False)
                    export_btn.tooltip("Bạn không có quyền xuất Excel")
                add_btn = ui.button("Lên lịch", icon="add", on_click=open_bulk_create_dialog) \
                    .props("unelevated no-caps").classes("sm-btn")
                if not can_manage:
                    add_btn.set_enabled(False)
                    add_btn.tooltip("Bạn không có quyền quản lý lịch trình")

            stats_block()

            with ui.element("div").classes("sch-grid").style("margin-top:16px"):
                with panel("Lịch tưới trong ngày"):
                    scope_line()
                    table_block()

                with ui.element("div").style("display:flex;flex-direction:column;gap:16px;min-width:0"):
                    with panel("Dòng hoạt động"):
                        timeline_block()

            with panel("Lưu lượng nước theo tuần", note="Tổng nước thực tế mỗi ngày"):
                week_block()

            with panel("Quyền của tài khoản"):
                with ui.row().classes("items-center gap-2"):
                    status_chip("ok" if can_manage else "none",
                                "Quản lý lịch trình tưới" if can_manage else "Không quản lý được lịch")
                    status_chip("ok" if can_export else "none",
                                "Xuất báo cáo Excel" if can_export else "Không xuất được Excel")

    # ── Timer ──────────────────────────────────────────────────
    last_seen = {"counter": state.get("_update_counter", 0), "farm": current_farm_key()}

    def check_schedule_ui_update():
        if page_state.get("dialog_open", False):
            return
        counter = state.get("_update_counter", 0)
        farm_now = current_farm_key()
        if counter == last_seen["counter"] and farm_now == last_seen["farm"]:
            return
        last_seen.update(counter=counter, farm=farm_now)
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

    ui.timer(1.0, refresh_all, once=True)
