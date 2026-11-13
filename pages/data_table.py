from nicegui import ui, app
from pages.login import check_login
from pages.home import global_topbar, sidebar, CUSTOM_CSS
from components.ui_kit import page_header, panel, state_panel, sim_badge, fmt_num
from service.auth import get_telemetry_node_history, get_telemetry_water_history, get_telemetry_flow_history
from datetime import datetime, timedelta
import pandas as pd
import tempfile
import os
import traceback

DATA_CSS = """
.sm-filter{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px}
.sm-filter-row{display:flex;flex-wrap:wrap;align-items:center;gap:10px}
.sm-section{margin:20px 0 10px;display:block}
.sm-grid2{display:grid;gap:12px;grid-template-columns:minmax(0,1fr)}
@media (min-width:1200px){.sm-grid2{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}}
.sm-tbl.q-table{box-shadow:none!important;border:1px solid var(--sm-net-soft);border-radius:var(--sm-r-m);background:var(--sm-surface);min-width:640px}
.sm-tbl.q-table thead th{background:var(--sm-sunken);color:var(--sm-ink-2);font-size:12px;font-weight:600}
.sm-tbl.q-table tbody td{font-size:13px;color:var(--sm-ink)}
"""

NODE_COLS = [
    {'name': 'advisory', 'label': 'Theo dõi', 'field': 'advisory', 'align': 'left'},
    {'name': 'air_temp', 'label': 'Nhiệt độ KK', 'field': 'air_temp', 'align': 'left'},
    {'name': 'air_hum', 'label': 'Độ ẩm KK', 'field': 'air_hum', 'align': 'left'},
    {'name': 'soil_temp', 'label': 'Nhiệt độ đất', 'field': 'soil_temp', 'align': 'left'},
    {'name': 'soil_hum', 'label': 'Độ ẩm đất', 'field': 'soil_hum', 'align': 'left'},
    {'name': 'ec', 'label': 'EC đất', 'field': 'ec', 'align': 'left'},
    {'name': 'timestamp', 'label': 'Thời gian', 'field': 'timestamp', 'align': 'left'},
]
EC_COLS = [
    {'name': 'ec_val', 'label': 'EC', 'field': 'ec_val', 'align': 'left'},
    {'name': 'timestamp', 'label': 'Thời gian', 'field': 'timestamp', 'align': 'left'},
]
PH_COLS = [
    {'name': 'ph_val', 'label': 'pH', 'field': 'ph_val', 'align': 'left'},
    {'name': 'timestamp', 'label': 'Thời gian', 'field': 'timestamp', 'align': 'left'},
]
FLOW_COLS = [
    {'name': 'flow_f1', 'label': 'Lưu lượng 1', 'field': 'flow_f1', 'align': 'left'},
    {'name': 'flow_t1', 'label': 'Tổng 1', 'field': 'flow_t1', 'align': 'left'},
    {'name': 'flow_f2', 'label': 'Lưu lượng 2', 'field': 'flow_f2', 'align': 'left'},
    {'name': 'flow_t2', 'label': 'Tổng 2', 'field': 'flow_t2', 'align': 'left'},
    {'name': 'total_water', 'label': 'Tổng nước', 'field': 'total_water', 'align': 'left'},
    {'name': 'timestamp', 'label': 'Thời gian', 'field': 'timestamp', 'align': 'left'},
]


@ui.page('/data')
def data_page():
    if not check_login(): return

    if not app.storage.user.get('history_start_date'):
        app.storage.user['history_start_date'] = datetime.now().strftime("%Y-%m-%d")
    if not app.storage.user.get('history_end_date'):
        app.storage.user['history_end_date'] = datetime.now().strftime("%Y-%m-%d")

    ui.add_head_html(f"<style>{CUSTOM_CSS}{DATA_CSS}</style>")
    sidebar(active="Data")

    with ui.element('div').classes('main-content'):
        global_topbar("Số đo", emoji="", show_farm_selector=True)

        with ui.element('div').classes('content-area'):
            with page_header("Số đo", "Số đo cảm biến của nhà màng đang chọn, lấy từ dữ liệu đã lưu.") as slot:
                sim_badge()

            # Thanh lọc
            with ui.element('div').classes('sm-panel sm-filter'):
                with ui.element('div').classes('sm-filter-row'):
                    ui.label("Khoảng thời gian").classes('sm-note')
                    ui.input('Từ ngày').props('type=date dense outlined').bind_value(app.storage.user, 'history_start_date')
                    ui.input('Đến ngày').props('type=date dense outlined').bind_value(app.storage.user, 'history_end_date')

                    def set_preset(days):
                        today = datetime.now()
                        app.storage.user['history_end_date'] = today.strftime("%Y-%m-%d")
                        app.storage.user['history_start_date'] = (today - timedelta(days=days)).strftime("%Y-%m-%d")
                        data_view.refresh()

                    ui.button('Hôm nay', on_click=lambda: set_preset(0)).props('flat dense no-caps').classes('sm-btn-quiet')
                    ui.button('7 ngày', on_click=lambda: set_preset(7)).props('flat dense no-caps').classes('sm-btn-quiet')
                    ui.button('30 ngày', on_click=lambda: set_preset(30)).props('flat dense no-caps').classes('sm-btn-quiet')
                    ui.button('Lọc dữ liệu', on_click=lambda: data_view.refresh()).props('unelevated no-caps').classes('sm-btn')

                ui.button('Xuất Excel', on_click=lambda: export_excel()).props('outline no-caps').classes('sm-btn-quiet')

            @ui.refreshable
            def data_view():
                from pages.home import state
                current_farm = state.get("selected_farm", "Greenhouse A")
                start = app.storage.user.get('history_start_date') or datetime.now().strftime("%Y-%m-%d")
                end = app.storage.user.get('history_end_date') or datetime.now().strftime("%Y-%m-%d")

                from service.farm_registry import FARM_KEYS_BY_LABEL
                f_key = FARM_KEYS_BY_LABEL.get(current_farm, "greenhouse_a")

                try:
                    node_rows = get_telemetry_node_history(f_key, start, end)
                    water_rows = get_telemetry_water_history(f_key, start, end)
                    flow_rows = get_telemetry_flow_history(f_key, start, end)

                    df_node = process_df(node_rows)
                    df_water = process_df(water_rows)
                    df_flow = process_df(flow_rows)

                    build_all_tables(df_node, df_water, df_flow)
                except Exception:
                    print("DATA VIEW ERROR:", traceback.format_exc())
                    state_panel('error', 'Chưa đọc được số đo',
                                'Thử lại sau ít phút hoặc chọn khoảng ngày khác.',
                                action_label='Thử lại', on_action=lambda: data_view.refresh())

            data_view()

            # Xuất Excel
            def export_excel():
                from pages.home import state
                current_farm = state.get("selected_farm", "Greenhouse A")
                start = app.storage.user.get('history_start_date')
                end = app.storage.user.get('history_end_date')
                from service.farm_registry import FARM_KEYS_BY_LABEL
                f_key = FARM_KEYS_BY_LABEL.get(current_farm, "greenhouse_a")

                df_n = process_df(get_telemetry_node_history(f_key, start, end))
                df_w = process_df(get_telemetry_water_history(f_key, start, end))
                df_f = process_df(get_telemetry_flow_history(f_key, start, end))

                if df_n.empty and df_w.empty and df_f.empty:
                    ui.notify("Không có số đo để xuất trong khoảng ngày này.", color="warning")
                    return

                path = os.path.join(tempfile.gettempdir(), f'DuLieu_{f_key}_{start}_{end}.xlsx')
                with pd.ExcelWriter(path) as writer:
                    if not df_n.empty: df_n.to_excel(writer, sheet_name='Cảm biến Node', index=False)
                    if not df_w.empty: df_w.to_excel(writer, sheet_name='Chất lượng nước', index=False)
                    if not df_f.empty: df_f.to_excel(writer, sheet_name='Lưu lượng', index=False)

                ui.download(path, f'DuLieu_{f_key}_{start}_{end}.xlsx')
                ui.notify("Đang tải file Excel...", color="positive")

            # Đăng ký callback refresh khi đổi farm từ topbar cho client hiện tại
            from pages.home import client_refreshes
            client_id = ui.context.client.id
            if client_id in client_refreshes:
                if data_view.refresh not in client_refreshes[client_id]:
                    client_refreshes[client_id].append(data_view.refresh)
            else:
                client_refreshes[client_id] = [data_view.refresh]

            ui.context.client.on_disconnect(lambda c_id=client_id: client_refreshes.pop(c_id, None))


def process_df(rows, time_col='timestamp'):
    """Dữ liệu lưu theo UTC; cộng 7 giờ để ra giờ Việt Nam."""
    try:
        df = pd.DataFrame(rows)
        if df.empty: return df
        df[time_col] = pd.to_datetime(df[time_col]) + pd.Timedelta(hours=7)
        df[time_col] = df[time_col].dt.strftime('%Y-%m-%d %H:%M:%S')
        return df
    except Exception as e:
        print(f"Error processing DataFrame: {e}")
        return pd.DataFrame()


def _advisory_label(air_temp, air_hum, classifier):
    notes = [
        result["message"] for result in (
            classifier("air_temp_c", air_temp),
            classifier("air_humidity_pct", air_hum),
        ) if result.get("message")
    ]
    return " · ".join(notes) if notes else "Không có cảnh báo nhiệt/ẩm không khí"


def _num(value):
    """Số thực, hoặc None khi không có số đo. Không thay bằng số mặc định."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(number) else number


def _measure(value, digits, unit):
    number = _num(value)
    return "—" if number is None else f"{fmt_num(number, digits)} {unit}"


def _when(value):
    if value is None or str(value).strip() in ("", "nan", "NaT"):
        return "—"
    try:
        return pd.to_datetime(value).strftime('%d/%m/%Y %H:%M:%S')
    except (TypeError, ValueError):
        return "—"


def _node_rows(df, node_id, classify):
    if 'node_id' not in df.columns:
        return []
    part = df[df['node_id'] == node_id].sort_values('timestamp', ascending=False).head(100)
    rows = []
    for _, row in part.iterrows():
        rows.append({
            'advisory': _advisory_label(row.get('air_temp'), row.get('air_hum'), classify),
            'air_temp': _measure(row.get('air_temp'), 1, '°C'),
            'air_hum': _measure(row.get('air_hum'), 1, '%'),
            'soil_temp': _measure(row.get('soil_temp'), 1, '°C'),
            'soil_hum': _measure(row.get('soil_hum'), 1, '%'),
            'ec': _measure(row.get('ec'), 2, 'mS/cm'),
            'timestamp': _when(row.get('timestamp')),
        })
    return rows


def _water_rows(df):
    part = df.sort_values('timestamp', ascending=False).head(100)
    ec_rows, ph_rows = [], []
    for _, row in part.iterrows():
        ts = _when(row.get('timestamp'))
        ec_rows.append({'ec_val': _measure(row.get('ec_val'), 2, 'mS/cm'), 'timestamp': ts})
        ph_rows.append({'ph_val': _measure(row.get('ph_val'), 2, 'pH'), 'timestamp': ts})
    return ec_rows, ph_rows


def _flow_rows(df):
    part = df.sort_values('timestamp', ascending=False).head(100)
    rows = []
    for _, row in part.iterrows():
        t1 = _num(row.get('flow_t1'))
        t2 = _num(row.get('flow_t2'))
        rows.append({
            'flow_f1': _measure(row.get('flow_f1'), 2, 'L/m'),
            'flow_t1': _measure(t1, 1, 'm³'),
            'flow_f2': _measure(row.get('flow_f2'), 2, 'L/m'),
            'flow_t2': _measure(t2, 1, 'm³'),
            'total_water': _measure(t1 + t2, 1, 'm³') if t1 is not None and t2 is not None else "—",
            'timestamp': _when(row.get('timestamp')),
        })
    return rows


def _section(title):
    ui.label(title).classes('sm-h2 sm-section')


def _table_card(title, rows, columns):
    with panel(title, f"{len(rows)} bản ghi"):
        with ui.element('div').classes('sm-scroll-x'):
            ui.table(columns=columns, rows=rows, pagination={'rowsPerPage': 20}).classes(
                'sm-tbl w-full').style('max-height:500px')


def build_all_tables(df_node, df_water, df_flow):
    from service.agronomic_thresholds import classify_advisory

    ui.label("Giờ Việt Nam (UTC+7). Mỗi bảng hiển thị tối đa 100 bản ghi mới nhất.").classes('sm-source')

    if df_node.empty and df_water.empty and df_flow.empty:
        state_panel('empty', 'Không có số đo nào trong khoảng ngày đã chọn',
                    'Chọn khoảng ngày khác hoặc bấm "Hôm nay" để xem dữ liệu mới nhất.')
        return

    if not df_node.empty:
        _section('Giám sát môi trường')
        with ui.element('div').classes('sm-grid2'):
            _table_card('Node 1, môi trường', _node_rows(df_node, 1, classify_advisory), NODE_COLS)
            _table_card('Node 2, môi trường', _node_rows(df_node, 2, classify_advisory), NODE_COLS)

    if not df_water.empty:
        _section('Chất lượng nước')
        ec_rows, ph_rows = _water_rows(df_water)
        with ui.element('div').classes('sm-grid2'):
            _table_card('Độ dẫn điện (EC)', ec_rows, EC_COLS)
            _table_card('pH', ph_rows, PH_COLS)

    if not df_flow.empty:
        _section('Lưu lượng nước')
        _table_card('Cảm biến lưu lượng', _flow_rows(df_flow), FLOW_COLS)
