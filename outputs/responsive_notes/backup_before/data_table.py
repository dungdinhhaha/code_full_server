from nicegui import ui, app
from pages.login import check_login
from pages.home import global_topbar, sidebar, CUSTOM_CSS
from service.auth import get_telemetry_node_history, get_telemetry_water_history, get_telemetry_flow_history
from datetime import datetime, timedelta
import pandas as pd
import tempfile
import os

@ui.page('/data')
def data_page():
    if not check_login(): return
    
    if not app.storage.user.get('history_start_date'):
        app.storage.user['history_start_date'] = datetime.now().strftime("%Y-%m-%d")
    if not app.storage.user.get('history_end_date'):
        app.storage.user['history_end_date'] = datetime.now().strftime("%Y-%m-%d")
        
    custom_table_css = """
    <style>
    .ec-table th { background-color: #fef9c3 !important; color: #854d0e !important; font-weight: bold !important; font-size: 11px !important; }
    .ph-table th { background-color: #fce7f3 !important; color: #9d174d !important; font-weight: bold !important; font-size: 11px !important; }
    .flow-table th { background-color: #ecfeff !important; color: #0891b2 !important; font-weight: bold !important; font-size: 11px !important; }
    .node-table th { background-color: #dcfce7 !important; color: #15803d !important; font-weight: bold !important; font-size: 11px !important; }
    .node2-table th { background-color: #dbeafe !important; color: #1d4ed8 !important; font-weight: bold !important; font-size: 11px !important; }
    .q-table__card { box-shadow: none !important; border-radius: 0px !important; }
    .q-table tbody td { font-size: 12px !important; }
    .data-section-title {
        display: flex; align-items: center; gap: 8px;
        font-size: 10px; font-weight: 700; letter-spacing: 0.08em;
        text-transform: uppercase; color: #94a3b8;
        margin-bottom: 12px; margin-top: 20px;
    }
    .data-section-title:first-child { margin-top: 0; }
    .row-count-badge {
        display: inline-flex; align-items: center;
        padding: 2px 8px; border-radius: 12px;
        font-size: 10px; font-weight: 700;
        background: #f1f5f9; color: #64748b;
    }
    </style>
    """
    ui.add_head_html(f"<style>{CUSTOM_CSS}</style>{custom_table_css}")
    sidebar(active="Data")
    
    with ui.element('div').classes('main-content'):
        global_topbar("Dữ Liệu Thô", "📋")
        
        with ui.element('div').classes('content-area'):
            # Smart Filter Bar
            with ui.row().classes('w-full items-center justify-between mb-6 bg-white rounded-[16px] border border-[#e8ecf0] p-4 shadow-[0_1px_4px_rgba(30,41,59,0.05)]'):
                with ui.row().classes('items-center gap-4'):
                    ui.label("Khoảng thời gian:").classes('font-bold text-slate-700')
                    with ui.input('Từ ngày').props('type=date dense outlined').bind_value(app.storage.user, 'history_start_date'): pass
                    with ui.input('Đến ngày').props('type=date dense outlined').bind_value(app.storage.user, 'history_end_date'): pass
                    
                    def set_preset(days):
                        today = datetime.now()
                        app.storage.user['history_end_date'] = today.strftime("%Y-%m-%d")
                        app.storage.user['history_start_date'] = (today - timedelta(days=days)).strftime("%Y-%m-%d")
                        data_view.refresh()
                        
                    with ui.row().classes('gap-2 ml-4'):
                        ui.button('Hôm nay', on_click=lambda: set_preset(0)).props('outline size=sm color=primary rounded')
                        ui.button('7 ngày', on_click=lambda: set_preset(7)).props('outline size=sm color=primary rounded')
                        ui.button('30 ngày', on_click=lambda: set_preset(30)).props('outline size=sm color=primary rounded')
                        
                    ui.button('Lọc Dữ Liệu', icon='filter_alt', on_click=lambda: data_view.refresh()).props('color=primary unelevated rounded')
                
                with ui.element('div').classes('flex items-center gap-2'):
                    ui.button('Xuất Excel', icon='file_download', on_click=lambda: export_excel()).props('color=positive outline rounded')

            @ui.refreshable
            def data_view():
                from pages.home import state
                current_farm = state.get("selected_farm", "Greenhouse A")
                start = app.storage.user.get('history_start_date') or datetime.now().strftime("%Y-%m-%d")
                end = app.storage.user.get('history_end_date') or datetime.now().strftime("%Y-%m-%d")
                
                farm_map = { "Greenhouse A": "greenhouse_a", "Greenhouse B": "greenhouse_b", "Greenhouse C": "greenhouse_c", "Greenhouse D": "greenhouse_d" }
                f_key = farm_map.get(current_farm, "greenhouse_a")
                
                try:
                    # Fetch data
                    node_rows = get_telemetry_node_history(f_key, start, end)
                    water_rows = get_telemetry_water_history(f_key, start, end)
                    flow_rows = get_telemetry_flow_history(f_key, start, end)
                    
                    df_node = process_df(node_rows)
                    df_water = process_df(water_rows)
                    df_flow = process_df(flow_rows)
                    
                    # Hiển thị tất cả bảng cùng lúc (không tabs)
                    build_all_tables(df_node, df_water, df_flow)
                except Exception as e:
                    import traceback
                    error_text = traceback.format_exc()
                    with ui.element('div').classes('w-full bg-red-50 rounded-2xl border border-red-200 p-8 text-center'):
                        ui.icon('error_outline', size='48px', color='#ef4444').classes('mb-4')
                        ui.label(f"Lỗi hệ thống: {e}").classes('text-red-600 font-bold text-lg mb-2')
                        ui.label(error_text).classes('text-red-400 text-xs whitespace-pre-wrap text-left max-h-40 overflow-auto')
                    print("DATA VIEW ERROR:", error_text)
            
            data_view()

            # Xuất Excel
            def export_excel():
                from pages.home import state
                current_farm = state.get("selected_farm", "Greenhouse A")
                start = app.storage.user.get('history_start_date')
                end = app.storage.user.get('history_end_date')
                farm_map = { "Greenhouse A": "greenhouse_a", "Greenhouse B": "greenhouse_b", "Greenhouse C": "greenhouse_c", "Greenhouse D": "greenhouse_d" }
                f_key = farm_map.get(current_farm, "greenhouse_a")
                
                node_rows = get_telemetry_node_history(f_key, start, end)
                water_rows = get_telemetry_water_history(f_key, start, end)
                flow_rows = get_telemetry_flow_history(f_key, start, end)
                
                df_n = process_df(node_rows)
                df_w = process_df(water_rows)
                df_f = process_df(flow_rows)
                
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
    try:
        df = pd.DataFrame(rows)
        if df.empty: return df
        df[time_col] = pd.to_datetime(df[time_col]) + pd.Timedelta(hours=7)
        df[time_col] = df[time_col].dt.strftime('%Y-%m-%d %H:%M:%S')
        return df
    except Exception as e:
        print(f"Error processing DataFrame: {e}")
        return pd.DataFrame()

def build_all_tables(df_node, df_water, df_flow):
    """Hiển thị tất cả bảng cùng lúc, không dùng tabs."""
    
    # Định dạng thời gian phụ trợ
    def format_time(val):
        if pd.isna(val) or val is None or str(val).strip() == '': return "-"
        try:
            dt = pd.to_datetime(val)
            return dt.strftime('%m/%d/%Y %I:%M:%S %p')
        except:
            return str(val)

    # Check nếu toàn bộ rỗng
    if df_node.empty and df_water.empty and df_flow.empty:
        with ui.element('div').classes('w-full bg-white rounded-2xl border border-[#e8ecf0] p-16 text-center shadow-sm'):
            ui.icon('inbox', size='64px', color='#cbd5e1').classes('mb-4')
            ui.label("Không có dữ liệu").classes('text-xl font-bold text-slate-400 mb-2')
            ui.label("Hãy chọn khoảng thời gian khác hoặc nhấn 'Hôm nay' để xem dữ liệu mới nhất.").classes('text-sm text-slate-400')
        return

    # Hàm vẽ badge Online chung cho các table
    def add_online_slot(table_obj):
        table_obj.add_slot('body-cell-status', '''
            <q-td :props="props">
                <span class="inline-flex items-center gap-1.5 px-3 py-1 bg-[#e6f4ea] text-[#137333] text-[10px] font-bold rounded-full">
                    <span class="w-1.5 h-1.5 rounded-full bg-[#137333] inline-block"></span>
                    Online
                </span>
            </q-td>
        ''')

    # ═══════════════════════════════════════════
    # SECTION 1: Giám sát môi trường (Node 1 & Node 2)
    # ═══════════════════════════════════════════
    if not df_node.empty:
        ui.html('<div class="data-section-title"><span style="font-size:14px">🌿</span> GIÁM SÁT MÔI TRƯỜNG</div>')
        
        df_n1 = df_node[df_node['node_id'] == 1].sort_values('timestamp', ascending=False).head(100)
        df_n2 = df_node[df_node['node_id'] == 2].sort_values('timestamp', ascending=False).head(100)
        
        n1_rows = []
        for _, row in df_n1.iterrows():
            at = row.get('air_temp', 0.0)
            ah = row.get('air_hum', 0.0)
            st = row.get('soil_temp', 0.0)
            sh = row.get('soil_hum', 0.0)
            ec = row.get('ec', 0.0)
            if pd.isna(at): at = 0.0
            if pd.isna(ah): ah = 0.0
            if pd.isna(st): st = 0.0
            if pd.isna(sh): sh = 0.0
            if pd.isna(ec): ec = 0.0
            n1_rows.append({
                'status': 'Online',
                'air_temp': f"{at:.1f} °C",
                'air_hum': f"{ah:.1f} %",
                'soil_temp': f"{st:.1f} °C",
                'soil_hum': f"{sh:.1f} %",
                'ec': f"{ec:.2f} mS/cm",
                'timestamp': format_time(row.get('timestamp'))
            })
            
        n2_rows = []
        for _, row in df_n2.iterrows():
            at = row.get('air_temp', 0.0)
            ah = row.get('air_hum', 0.0)
            st = row.get('soil_temp', 0.0)
            sh = row.get('soil_hum', 0.0)
            ec = row.get('ec', 0.0)
            if pd.isna(at): at = 0.0
            if pd.isna(ah): ah = 0.0
            if pd.isna(st): st = 0.0
            if pd.isna(sh): sh = 0.0
            if pd.isna(ec): ec = 0.0
            n2_rows.append({
                'status': 'Online',
                'air_temp': f"{at:.1f} °C",
                'air_hum': f"{ah:.1f} %",
                'soil_temp': f"{st:.1f} °C",
                'soil_hum': f"{sh:.1f} %",
                'ec': f"{ec:.2f} mS/cm",
                'timestamp': format_time(row.get('timestamp'))
            })

        node_cols = [
            {'name': 'status', 'label': 'STATUS', 'field': 'status', 'align': 'left'},
            {'name': 'air_temp', 'label': 'NHIỆT ĐỘ KK', 'field': 'air_temp', 'align': 'left'},
            {'name': 'air_hum', 'label': 'ĐỘ ẨM KK', 'field': 'air_hum', 'align': 'left'},
            {'name': 'soil_temp', 'label': 'NHIỆT ĐỘ ĐẤT', 'field': 'soil_temp', 'align': 'left'},
            {'name': 'soil_hum', 'label': 'ĐỘ ẨM ĐẤT', 'field': 'soil_hum', 'align': 'left'},
            {'name': 'ec', 'label': 'EC ĐẤT', 'field': 'ec', 'align': 'left'},
            {'name': 'timestamp', 'label': 'THỜI GIAN', 'field': 'timestamp', 'align': 'left'}
        ]

        with ui.element('div').classes('w-full grid grid-cols-1 xl:grid-cols-2 gap-6 mb-6'):
            # Table Node 1
            with ui.element('div').classes('w-full card flex flex-col p-0 overflow-hidden'):
                with ui.row().classes('px-4 py-3 bg-emerald-50 border-b border-[#e8ecf0] items-center justify-between'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('memory', size='18px', color='#059669')
                        ui.label('NODE 1 — ENVIRONMENTAL').classes('text-xs font-bold text-emerald-800')
                    ui.html(f'<span class="row-count-badge">{len(n1_rows)} bản ghi</span>')
                t_n1 = ui.table(
                    columns=node_cols, rows=n1_rows,
                    pagination={'rowsPerPage': 20}
                ).classes('w-full node-table').style('max-height: 500px;')
                add_online_slot(t_n1)

            # Table Node 2
            with ui.element('div').classes('w-full card flex flex-col p-0 overflow-hidden'):
                with ui.row().classes('px-4 py-3 bg-blue-50 border-b border-[#e8ecf0] items-center justify-between'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('memory', size='18px', color='#1d4ed8')
                        ui.label('NODE 2 — ENVIRONMENTAL').classes('text-xs font-bold text-blue-800')
                    ui.html(f'<span class="row-count-badge">{len(n2_rows)} bản ghi</span>')
                t_n2 = ui.table(
                    columns=node_cols, rows=n2_rows,
                    pagination={'rowsPerPage': 20}
                ).classes('w-full node2-table').style('max-height: 500px;')
                add_online_slot(t_n2)

    # ═══════════════════════════════════════════
    # SECTION 2: Chất lượng nước (EC & pH)
    # ═══════════════════════════════════════════
    if not df_water.empty:
        ui.html('<div class="data-section-title"><span style="font-size:14px">💧</span> CHẤT LƯỢNG NƯỚC</div>')
        
        df_w = df_water.sort_values('timestamp', ascending=False).head(100)
        
        ec_rows = []
        ph_rows = []
        for _, row in df_w.iterrows():
            ec_val = row.get('ec_val', 0.0)
            ph_val = row.get('ph_val', 7.0)
            if pd.isna(ec_val): ec_val = 0.0
            if pd.isna(ph_val): ph_val = 7.0
            ts = format_time(row.get('timestamp'))
            
            ec_rows.append({
                'status': 'Online',
                'ec_val': f"{ec_val:.2f} mS/cm",
                'voltage': f"{ec_val * 0.1:.2f} V",
                'raw': str(int(ec_val * 100)),
                'timestamp': ts
            })
            ph_rows.append({
                'status': 'Online',
                'ph_val': f"{ph_val:.2f} pH",
                'mv': f"{(7.0 - ph_val) * 59.2:.1f} mV",
                'raw': str(int(ph_val * 10)),
                'timestamp': ts
            })

        with ui.element('div').classes('w-full grid grid-cols-1 xl:grid-cols-2 gap-6 mb-6'):
            # Table EC
            with ui.element('div').classes('w-full card flex flex-col p-0 overflow-hidden'):
                with ui.row().classes('px-4 py-3 bg-amber-50 border-b border-[#e8ecf0] items-center justify-between'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('flash_on', size='18px', color='#d97706')
                        ui.label('ELECTRICAL CONDUCTIVITY (EC)').classes('text-xs font-bold text-amber-800')
                    ui.html(f'<span class="row-count-badge">{len(ec_rows)} bản ghi</span>')
                ec_cols = [
                    {'name': 'status', 'label': 'STATUS', 'field': 'status', 'align': 'left'},
                    {'name': 'ec_val', 'label': 'EC', 'field': 'ec_val', 'align': 'left'},
                    {'name': 'voltage', 'label': 'VOLTAGE', 'field': 'voltage', 'align': 'left'},
                    {'name': 'raw', 'label': 'RAW', 'field': 'raw', 'align': 'left'},
                    {'name': 'timestamp', 'label': 'THỜI GIAN', 'field': 'timestamp', 'align': 'left'}
                ]
                t_ec = ui.table(
                    columns=ec_cols, rows=ec_rows,
                    pagination={'rowsPerPage': 20}
                ).classes('w-full ec-table').style('max-height: 500px;')
                add_online_slot(t_ec)

            # Table pH
            with ui.element('div').classes('w-full card flex flex-col p-0 overflow-hidden'):
                with ui.row().classes('px-4 py-3 bg-pink-50 border-b border-[#e8ecf0] items-center justify-between'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('science', size='18px', color='#db2777')
                        ui.label('PH LEVEL MONITORING').classes('text-xs font-bold text-pink-800')
                    ui.html(f'<span class="row-count-badge">{len(ph_rows)} bản ghi</span>')
                ph_cols = [
                    {'name': 'status', 'label': 'STATUS', 'field': 'status', 'align': 'left'},
                    {'name': 'ph_val', 'label': 'PH LEVEL', 'field': 'ph_val', 'align': 'left'},
                    {'name': 'mv', 'label': 'MV', 'field': 'mv', 'align': 'left'},
                    {'name': 'raw', 'label': 'RAW', 'field': 'raw', 'align': 'left'},
                    {'name': 'timestamp', 'label': 'THỜI GIAN', 'field': 'timestamp', 'align': 'left'}
                ]
                t_ph = ui.table(
                    columns=ph_cols, rows=ph_rows,
                    pagination={'rowsPerPage': 20}
                ).classes('w-full ph-table').style('max-height: 500px;')
                add_online_slot(t_ph)

    # ═══════════════════════════════════════════
    # SECTION 3: Lưu lượng nước (Flow Rate)
    # ═══════════════════════════════════════════
    if not df_flow.empty:
        ui.html('<div class="data-section-title"><span style="font-size:14px">🌊</span> LƯU LƯỢNG NƯỚC</div>')
        
        df_f = df_flow.sort_values('timestamp', ascending=False).head(100)
        
        flow_data_rows = []
        for _, row in df_f.iterrows():
            f1 = row.get('flow_f1', 0.0)
            f2 = row.get('flow_f2', 0.0)
            t1 = row.get('flow_t1', 0.0)
            t2 = row.get('flow_t2', 0.0)
            if pd.isna(f1): f1 = 0.0
            if pd.isna(f2): f2 = 0.0
            if pd.isna(t1): t1 = 0.0
            if pd.isna(t2): t2 = 0.0
            flow_data_rows.append({
                'status': 'Online',
                'flow_f1': f"{f1:.2f} L/m",
                'flow_t1': f"{t1:.1f} M³",
                'flow_f2': f"{f2:.2f} L/m",
                'flow_t2': f"{t2:.1f} M³",
                'total_water': f"{t1 + t2:.1f} M³",
                'timestamp': format_time(row.get('timestamp'))
            })

        with ui.element('div').classes('w-full mb-6'):
            with ui.element('div').classes('w-full card flex flex-col p-0 overflow-hidden'):
                with ui.row().classes('px-4 py-3 bg-cyan-50 border-b border-[#e8ecf0] items-center justify-between'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('waves', size='18px', color='#0891b2')
                        ui.label('FLOW RATE SENSORS').classes('text-xs font-bold text-cyan-800')
                    ui.html(f'<span class="row-count-badge">{len(flow_data_rows)} bản ghi</span>')
                flow_cols = [
                    {'name': 'status', 'label': 'STATUS', 'field': 'status', 'align': 'left'},
                    {'name': 'flow_f1', 'label': 'FLOW 1', 'field': 'flow_f1', 'align': 'left'},
                    {'name': 'flow_t1', 'label': 'TOTAL 1', 'field': 'flow_t1', 'align': 'left'},
                    {'name': 'flow_f2', 'label': 'FLOW 2', 'field': 'flow_f2', 'align': 'left'},
                    {'name': 'flow_t2', 'label': 'TOTAL 2', 'field': 'flow_t2', 'align': 'left'},
                    {'name': 'total_water', 'label': 'TỔNG NƯỚC', 'field': 'total_water', 'align': 'left'},
                    {'name': 'timestamp', 'label': 'THỜI GIAN', 'field': 'timestamp', 'align': 'left'}
                ]
                t_flow = ui.table(
                    columns=flow_cols, rows=flow_data_rows,
                    pagination={'rowsPerPage': 20}
                ).classes('w-full flow-table').style('max-height: 500px; min-width: 800px;')
                add_online_slot(t_flow)
