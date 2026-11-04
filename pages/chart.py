from nicegui import ui, app
from pages.login import check_login
from pages.home import global_topbar, sidebar, CUSTOM_CSS
from service.auth import get_telemetry_node_history, get_telemetry_water_history
from datetime import datetime, timedelta
import pandas as pd

@ui.page('/history')
def history_redirect():
    ui.navigate.to('/chart')

@ui.page('/chart')
def chart_page():
    if not check_login(): return
    
    if 'history_start_date' not in app.storage.user:
        app.storage.user['history_start_date'] = datetime.now().strftime("%Y-%m-%d")
    if 'history_end_date' not in app.storage.user:
        app.storage.user['history_end_date'] = datetime.now().strftime("%Y-%m-%d")
        
    ui.add_head_html(f"<style>{CUSTOM_CSS}</style>")
    sidebar(active="Chart")
    
    with ui.element('div').classes('main-content'):
        global_topbar("Biểu Đồ Phân Tích", "📈")
        
        with ui.element('div').classes('content-area'):
            
            # Smart Filter Bar - Clean design
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

            @ui.refreshable
            def data_view():
                from pages.home import state
                current_farm = state.get("selected_farm", "Greenhouse A")
                start = app.storage.user.get('history_start_date')
                end = app.storage.user.get('history_end_date')
                
                farm_map = { "Greenhouse A": "greenhouse_a", "Greenhouse B": "greenhouse_b", "Greenhouse C": "greenhouse_c", "Greenhouse D": "greenhouse_d" }
                f_key = farm_map.get(current_farm, "greenhouse_a")
                
                # Fetch
                node_rows = get_telemetry_node_history(f_key, start, end)
                water_rows = get_telemetry_water_history(f_key, start, end)
                
                # Auto Grouping Logic using Pandas
                df_node, df_water = group_data(node_rows, water_rows, start, end)
                
                # Grid Layout 2 Columns for Charts
                with ui.element('div').classes('w-full grid grid-cols-1 xl:grid-cols-2 gap-6'):
                    # Biểu đồ Nhiệt độ không khí
                    build_air_temp_chart(df_node, current_farm)
                    
                    # Biểu đồ Độ ẩm không khí
                    build_air_hum_chart(df_node, current_farm)
                    
                    # Biểu đồ Nhiệt độ đất
                    build_soil_temp_chart(df_node, current_farm)
                    
                    # Biểu đồ Độ ẩm đất
                    build_soil_hum_chart(df_node, current_farm)
                    
                    # Biểu đồ EC Đất
                    build_soil_ec_chart(df_node, current_farm)
                    
                    # Biểu đồ Chất lượng nước (pH / EC)
                    build_water_chart(df_water, current_farm)
                        
            data_view()

            # Đăng ký callback refresh khi đổi farm từ topbar cho client hiện tại
            from pages.home import client_refreshes
            client_id = ui.context.client.id
            if client_id in client_refreshes:
                if data_view.refresh not in client_refreshes[client_id]:
                    client_refreshes[client_id].append(data_view.refresh)
            else:
                client_refreshes[client_id] = [data_view.refresh]
            
            ui.context.client.on_disconnect(lambda c_id=client_id: client_refreshes.pop(c_id, None))

# Helper Functions
def group_data(node_rows, water_rows, start, end):
    import pandas as pd
    from datetime import datetime
    
    d1 = datetime.strptime(start, "%Y-%m-%d")
    d2 = datetime.strptime(end, "%Y-%m-%d")
    days = (d2 - d1).days
    
    freq = None
    if days > 30: freq = '1D'
    elif days > 7: freq = '3h'
    elif days > 1: freq = '1h'
    
    def process_df(rows, time_col='timestamp'):
        df = pd.DataFrame(rows)
        if df.empty: return df
        df[time_col] = pd.to_datetime(df[time_col]) + pd.Timedelta(hours=7)
        
        # Đảm bảo các cột cảm biến được ép kiểu về dạng số để tính mean()
        for col in df.columns:
            if col not in [time_col, 'node_id', 'id', 'farm_id', 'status', 'project_id']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        if freq:
            if 'node_id' in df.columns:
                # Group by time and node_id
                df = df.set_index(time_col).groupby('node_id').resample(freq).mean(numeric_only=True).reset_index()
            else:
                df = df.set_index(time_col).resample(freq).mean(numeric_only=True).reset_index()
            # Drop rows where all numeric values are NaN
            numeric_cols = df.select_dtypes(include='number').columns.tolist()
            if 'node_id' in numeric_cols: numeric_cols.remove('node_id')
            if 'id' in numeric_cols: numeric_cols.remove('id')
            if numeric_cols:
                df.dropna(subset=numeric_cols, how='all', inplace=True)
            df[time_col] = df[time_col].dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            df[time_col] = df[time_col].dt.strftime('%Y-%m-%d %H:%M:%S')
        return df

    return process_df(node_rows), process_df(water_rows)


def build_air_temp_chart(df, current_farm):
    if df.empty:
        with ui.element('div').classes('w-full card h-96 flex items-center justify-center'):
            ui.label("Không có dữ liệu Nhiệt độ không khí").classes('text-slate-400 font-medium')
        return
        
    df_n1 = df[df['node_id'] == 1]
    df_n2 = df[df['node_id'] == 2]
    
    # Lấy unique timestamps chung và lọc giá trị không hợp lệ
    raw_times = sorted(list(set(df['timestamp'].dropna())))
    clean_times = []
    for t in raw_times:
        if pd.isna(t) or t == 'NaT' or t is None or str(t).strip() == '':
            continue
        try:
            dt = datetime.strptime(str(t), '%Y-%m-%d %H:%M:%S')
            clean_times.append(dt.strftime('%H:%M\n%d/%m'))
        except:
            clean_times.append(str(t))
            
    # Map data
    def get_data(d, col):
        m = dict(zip(d['timestamp'], d[col]))
        return [m.get(t, None) for t in raw_times]
        
    n1_at = get_data(df_n1, 'air_temp')
    n2_at = get_data(df_n2, 'air_temp')
    
    # Tính toán chỉ số thống kê trung bình
    t1_avg = df_n1['air_temp'].mean() if not df_n1.empty else None
    t2_avg = df_n2['air_temp'].mean() if not df_n2.empty else None
    stats_parts = []
    if t1_avg is not None and not pd.isna(t1_avg):
        stats_parts.append(f"N1: {t1_avg:.1f}°C")
    if t2_avg is not None and not pd.isna(t2_avg):
        stats_parts.append(f"N2: {t2_avg:.1f}°C")
    stats_text = ""
    if stats_parts:
        stats_text = f'<span class="text-xs text-slate-500 font-normal ml-3 bg-slate-100 px-2.5 py-1 rounded-full">TB | {" - ".join(stats_parts)}</span>'
    
    with ui.element('div').classes('w-full card hover-elevate flex flex-col justify-between p-5').style('height: 480px;'):
        # Custom Header
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('thermostat', size='sm').classes('text-orange-500 bg-orange-50 p-2 rounded-lg')
                ui.html(f'<div class="flex items-center"><span class="font-bold text-base text-slate-800">Môi trường không khí - Nhiệt độ</span>{stats_text}</div>')
                
        ui.echart({
            'tooltip': {
                'trigger': 'axis',
                'axisPointer': {'type': 'cross', 'crossStyle': {'color': '#94a3b8'}},
            },
            'legend': {
                'data': ['Nhiệt độ N1', 'Nhiệt độ N2'],
                'top': 4, 'right': 10,
                'textStyle': {'fontSize': 11, 'fontFamily': 'Inter, sans-serif', 'color': '#64748b'},
                'itemWidth': 16, 'itemHeight': 3,
            },
            'grid': {'left': '3%', 'right': '4%', 'bottom': '10%', 'top': '14%', 'containLabel': True},
            'xAxis': {
                'type': 'category',
                'boundaryGap': False,
                'data': clean_times,
                'axisLine': {'lineStyle': {'color': '#f1f5f9'}},
                'axisLabel': {'color': '#94a3b8', 'fontFamily': 'Inter, sans-serif', 'fontSize': 10}
            },
            'yAxis': {
                'type': 'value',
                'name': 'Nhiệt độ (°C)',
                'nameTextStyle': {'color': '#94a3b8', 'fontSize': 10, 'align': 'right'},
                'axisLine': {'show': False},
                'axisTick': {'show': False},
                'splitLine': {'lineStyle': {'type': 'dashed', 'color': '#f1f5f9'}},
                'axisLabel': {'color': '#94a3b8', 'fontFamily': 'Inter, sans-serif', 'fontSize': 10}
            },
            'dataZoom': [{'type': 'inside'}],
            'series': [
                {
                    'name': 'Nhiệt độ N1',
                    'type': 'line',
                    'smooth': True,
                    'connectNulls': True,
                    'showSymbol': False,
                    'itemStyle': {'color': '#f97316'},
                    'lineStyle': {'width': 3},
                    'areaStyle': {
                        'color': {
                            'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                            'colorStops': [
                                {'offset': 0, 'color': 'rgba(249, 115, 22, 0.12)'},
                                {'offset': 1, 'color': 'rgba(249, 115, 22, 0.01)'}
                            ]
                        }
                    },
                    'data': n1_at,
                    'markLine': {
                        'silent': True,
                        'symbol': 'none',
                        'label': {'position': 'end', 'formatter': 'Ngưỡng cao ({c}°C)', 'color': '#ef4444', 'fontSize': 9},
                        'lineStyle': {'color': '#ef4444', 'type': 'dashed', 'width': 1},
                        'data': [{'yAxis': 38}]
                    }
                },
                {
                    'name': 'Nhiệt độ N2',
                    'type': 'line',
                    'smooth': True,
                    'connectNulls': True,
                    'showSymbol': False,
                    'itemStyle': {'color': '#3b82f6'},
                    'lineStyle': {'width': 2.5},
                    'areaStyle': {
                        'color': {
                            'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                            'colorStops': [
                                {'offset': 0, 'color': 'rgba(59, 130, 246, 0.08)'},
                                {'offset': 1, 'color': 'rgba(59, 130, 246, 0.01)'}
                            ]
                        }
                    },
                    'data': n2_at,
                }
            ]
        }).classes('w-full flex-grow')


def build_air_hum_chart(df, current_farm):
    if df.empty:
        with ui.element('div').classes('w-full card h-96 flex items-center justify-center'):
            ui.label("Không có dữ liệu Độ ẩm không khí").classes('text-slate-400 font-medium')
        return
        
    df_n1 = df[df['node_id'] == 1]
    df_n2 = df[df['node_id'] == 2]
    
    # Lấy unique timestamps chung và lọc giá trị không hợp lệ
    raw_times = sorted(list(set(df['timestamp'].dropna())))
    clean_times = []
    for t in raw_times:
        if pd.isna(t) or t == 'NaT' or t is None or str(t).strip() == '':
            continue
        try:
            dt = datetime.strptime(str(t), '%Y-%m-%d %H:%M:%S')
            clean_times.append(dt.strftime('%H:%M\n%d/%m'))
        except:
            clean_times.append(str(t))
            
    # Map data
    def get_data(d, col):
        m = dict(zip(d['timestamp'], d[col]))
        return [m.get(t, None) for t in raw_times]
        
    n1_ah = get_data(df_n1, 'air_hum')
    n2_ah = get_data(df_n2, 'air_hum')
    
    # Tính toán chỉ số thống kê trung bình
    h1_avg = df_n1['air_hum'].mean() if not df_n1.empty else None
    h2_avg = df_n2['air_hum'].mean() if not df_n2.empty else None
    stats_parts = []
    if h1_avg is not None and not pd.isna(h1_avg):
        stats_parts.append(f"N1: {h1_avg:.1f}%")
    if h2_avg is not None and not pd.isna(h2_avg):
        stats_parts.append(f"N2: {h2_avg:.1f}%")
    stats_text = ""
    if stats_parts:
        stats_text = f'<span class="text-xs text-slate-500 font-normal ml-3 bg-slate-100 px-2.5 py-1 rounded-full">TB | {" - ".join(stats_parts)}</span>'
    
    with ui.element('div').classes('w-full card hover-elevate flex flex-col justify-between p-5').style('height: 480px;'):
        # Custom Header
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('water_drop', size='sm').classes('text-blue-500 bg-blue-50 p-2 rounded-lg')
                ui.html(f'<div class="flex items-center"><span class="font-bold text-base text-slate-800">Môi trường không khí - Độ ẩm</span>{stats_text}</div>')
                
        ui.echart({
            'tooltip': {
                'trigger': 'axis',
                'axisPointer': {'type': 'cross', 'crossStyle': {'color': '#94a3b8'}},
            },
            'legend': {
                'data': ['Độ ẩm N1', 'Độ ẩm N2'],
                'top': 4, 'right': 10,
                'textStyle': {'fontSize': 11, 'fontFamily': 'Inter, sans-serif', 'color': '#64748b'},
                'itemWidth': 16, 'itemHeight': 3,
            },
            'grid': {'left': '3%', 'right': '4%', 'bottom': '10%', 'top': '14%', 'containLabel': True},
            'xAxis': {
                'type': 'category',
                'boundaryGap': False,
                'data': clean_times,
                'axisLine': {'lineStyle': {'color': '#f1f5f9'}},
                'axisLabel': {'color': '#94a3b8', 'fontFamily': 'Inter, sans-serif', 'fontSize': 10}
            },
            'yAxis': {
                'type': 'value',
                'name': 'Độ ẩm (%)',
                'nameTextStyle': {'color': '#94a3b8', 'fontSize': 10, 'align': 'right'},
                'axisLine': {'show': False},
                'axisTick': {'show': False},
                'splitLine': {'lineStyle': {'type': 'dashed', 'color': '#f1f5f9'}},
                'axisLabel': {'color': '#94a3b8', 'fontFamily': 'Inter, sans-serif', 'fontSize': 10}
            },
            'dataZoom': [{'type': 'inside'}],
            'series': [
                {
                    'name': 'Độ ẩm N1',
                    'type': 'line',
                    'smooth': True,
                    'connectNulls': True,
                    'showSymbol': False,
                    'itemStyle': {'color': '#1d4ed8'},
                    'lineStyle': {'width': 3},
                    'areaStyle': {
                        'color': {
                            'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                            'colorStops': [
                                {'offset': 0, 'color': 'rgba(29, 78, 216, 0.12)'},
                                {'offset': 1, 'color': 'rgba(29, 78, 216, 0.01)'}
                            ]
                        }
                    },
                    'data': n1_ah,
                },
                {
                    'name': 'Độ ẩm N2',
                    'type': 'line',
                    'smooth': True,
                    'connectNulls': True,
                    'showSymbol': False,
                    'itemStyle': {'color': '#06b6d4'},
                    'lineStyle': {'width': 2.5},
                    'areaStyle': {
                        'color': {
                            'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                            'colorStops': [
                                {'offset': 0, 'color': 'rgba(6, 182, 212, 0.08)'},
                                {'offset': 1, 'color': 'rgba(6, 182, 212, 0.01)'}
                            ]
                        }
                    },
                    'data': n2_ah,
                }
            ]
        }).classes('w-full flex-grow')


def build_soil_temp_chart(df, current_farm):
    if df.empty:
        with ui.element('div').classes('w-full card h-96 flex items-center justify-center'):
            ui.label("Không có dữ liệu Nhiệt độ đất").classes('text-slate-400 font-medium')
        return
        
    df_n1 = df[df['node_id'] == 1]
    df_n2 = df[df['node_id'] == 2]
    
    raw_times = sorted(list(set(df['timestamp'].dropna())))
    clean_times = []
    for t in raw_times:
        if pd.isna(t) or t == 'NaT' or t is None or str(t).strip() == '':
            continue
        try:
            dt = datetime.strptime(str(t), '%Y-%m-%d %H:%M:%S')
            clean_times.append(dt.strftime('%H:%M\n%d/%m'))
        except:
            clean_times.append(str(t))
            
    def get_data(d, col):
        m = dict(zip(d['timestamp'], d[col]))
        return [m.get(t, None) for t in raw_times]
        
    n1_st = get_data(df_n1, 'soil_temp')
    n2_st = get_data(df_n2, 'soil_temp')
    
    # Tính toán chỉ số thống kê trung bình
    st1_avg = df_n1['soil_temp'].mean() if not df_n1.empty else None
    st2_avg = df_n2['soil_temp'].mean() if not df_n2.empty else None
    stats_parts = []
    if st1_avg is not None and not pd.isna(st1_avg):
        stats_parts.append(f"N1: {st1_avg:.1f}°C")
    if st2_avg is not None and not pd.isna(st2_avg):
        stats_parts.append(f"N2: {st2_avg:.1f}°C")
    stats_text = ""
    if stats_parts:
        stats_text = f'<span class="text-xs text-slate-500 font-normal ml-3 bg-slate-100 px-2.5 py-1 rounded-full">TB | {" - ".join(stats_parts)}</span>'
        
    with ui.element('div').classes('w-full card hover-elevate flex flex-col justify-between p-5').style('height: 480px;'):
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('grass', size='sm').classes('text-emerald-500 bg-emerald-50 p-2 rounded-lg')
                ui.html(f'<div class="flex items-center"><span class="font-bold text-base text-slate-800">Điều kiện đất - Nhiệt độ đất</span>{stats_text}</div>')
                
        ui.echart({
            'tooltip': {
                'trigger': 'axis',
                'axisPointer': {'type': 'cross', 'crossStyle': {'color': '#94a3b8'}},
            },
            'legend': {
                'data': ['Nhiệt độ đất N1', 'Nhiệt độ đất N2'],
                'top': 4, 'right': 10,
                'textStyle': {'fontSize': 11, 'fontFamily': 'Inter, sans-serif', 'color': '#64748b'},
                'itemWidth': 16, 'itemHeight': 3,
            },
            'grid': {'left': '3%', 'right': '4%', 'bottom': '10%', 'top': '14%', 'containLabel': True},
            'xAxis': {
                'type': 'category',
                'boundaryGap': False,
                'data': clean_times,
                'axisLine': {'lineStyle': {'color': '#f1f5f9'}},
                'axisLabel': {'color': '#94a3b8', 'fontFamily': 'Inter, sans-serif', 'fontSize': 10}
            },
            'yAxis': {
                'type': 'value',
                'name': 'Nhiệt độ đất (°C)',
                'nameTextStyle': {'color': '#94a3b8', 'fontSize': 10, 'align': 'right'},
                'axisLine': {'show': False},
                'axisTick': {'show': False},
                'splitLine': {'lineStyle': {'type': 'dashed', 'color': '#f1f5f9'}},
                'axisLabel': {'color': '#94a3b8', 'fontFamily': 'Inter, sans-serif', 'fontSize': 10}
            },
            'dataZoom': [{'type': 'inside'}],
            'series': [
                {
                    'name': 'Nhiệt độ đất N1',
                    'type': 'line',
                    'smooth': True,
                    'connectNulls': True,
                    'showSymbol': False,
                    'itemStyle': {'color': '#059669'},
                    'lineStyle': {'width': 3},
                    'areaStyle': {
                        'color': {
                            'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                            'colorStops': [
                                {'offset': 0, 'color': 'rgba(5, 150, 105, 0.12)'},
                                {'offset': 1, 'color': 'rgba(5, 150, 105, 0.01)'}
                            ]
                        }
                    },
                    'data': n1_st,
                    'markLine': {
                        'silent': True,
                        'symbol': 'none',
                        'label': {'position': 'end', 'formatter': 'Ngưỡng cao ({c}°C)', 'color': '#ef4444', 'fontSize': 9},
                        'lineStyle': {'color': '#ef4444', 'type': 'dashed', 'width': 1},
                        'data': [{'yAxis': 35}]
                    }
                },
                {
                    'name': 'Nhiệt độ đất N2',
                    'type': 'line',
                    'smooth': True,
                    'connectNulls': True,
                    'showSymbol': False,
                    'itemStyle': {'color': '#f59e0b'},
                    'lineStyle': {'width': 2.5},
                    'areaStyle': {
                        'color': {
                            'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                            'colorStops': [
                                {'offset': 0, 'color': 'rgba(245, 158, 11, 0.08)'},
                                {'offset': 1, 'color': 'rgba(245, 158, 11, 0.01)'}
                            ]
                        }
                    },
                    'data': n2_st,
                }
            ]
        }).classes('w-full flex-grow')


def build_soil_hum_chart(df, current_farm):
    if df.empty:
        with ui.element('div').classes('w-full card h-96 flex items-center justify-center'):
            ui.label("Không có dữ liệu Độ ẩm đất").classes('text-slate-400 font-medium')
        return
        
    df_n1 = df[df['node_id'] == 1]
    df_n2 = df[df['node_id'] == 2]
    
    raw_times = sorted(list(set(df['timestamp'].dropna())))
    clean_times = []
    for t in raw_times:
        if pd.isna(t) or t == 'NaT' or t is None or str(t).strip() == '':
            continue
        try:
            dt = datetime.strptime(str(t), '%Y-%m-%d %H:%M:%S')
            clean_times.append(dt.strftime('%H:%M\n%d/%m'))
        except:
            clean_times.append(str(t))
            
    def get_data(d, col):
        m = dict(zip(d['timestamp'], d[col]))
        return [m.get(t, None) for t in raw_times]
        
    n1_sh = get_data(df_n1, 'soil_hum')
    n2_sh = get_data(df_n2, 'soil_hum')
    
    # Tính toán chỉ số thống kê trung bình
    sh1_avg = df_n1['soil_hum'].mean() if not df_n1.empty else None
    sh2_avg = df_n2['soil_hum'].mean() if not df_n2.empty else None
    stats_parts = []
    if sh1_avg is not None and not pd.isna(sh1_avg):
        stats_parts.append(f"N1: {sh1_avg:.1f}%")
    if sh2_avg is not None and not pd.isna(sh2_avg):
        stats_parts.append(f"N2: {sh2_avg:.1f}%")
    stats_text = ""
    if stats_parts:
        stats_text = f'<span class="text-xs text-slate-500 font-normal ml-3 bg-slate-100 px-2.5 py-1 rounded-full">TB | {" - ".join(stats_parts)}</span>'
        
    with ui.element('div').classes('w-full card hover-elevate flex flex-col justify-between p-5').style('height: 480px;'):
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('opacity', size='sm').classes('text-teal-500 bg-teal-50 p-2 rounded-lg')
                ui.html(f'<div class="flex items-center"><span class="font-bold text-base text-slate-800">Điều kiện đất - Độ ẩm đất</span>{stats_text}</div>')
                
        ui.echart({
            'tooltip': {
                'trigger': 'axis',
                'axisPointer': {'type': 'cross', 'crossStyle': {'color': '#94a3b8'}},
            },
            'legend': {
                'data': ['Độ ẩm đất N1', 'Độ ẩm đất N2'],
                'top': 4, 'right': 10,
                'textStyle': {'fontSize': 11, 'fontFamily': 'Inter, sans-serif', 'color': '#64748b'},
                'itemWidth': 16, 'itemHeight': 3,
            },
            'grid': {'left': '3%', 'right': '4%', 'bottom': '10%', 'top': '14%', 'containLabel': True},
            'xAxis': {
                'type': 'category',
                'boundaryGap': False,
                'data': clean_times,
                'axisLine': {'lineStyle': {'color': '#f1f5f9'}},
                'axisLabel': {'color': '#94a3b8', 'fontFamily': 'Inter, sans-serif', 'fontSize': 10}
            },
            'yAxis': {
                'type': 'value',
                'name': 'Độ ẩm đất (%)',
                'nameTextStyle': {'color': '#94a3b8', 'fontSize': 10, 'align': 'right'},
                'axisLine': {'show': False},
                'axisTick': {'show': False},
                'splitLine': {'lineStyle': {'type': 'dashed', 'color': '#f1f5f9'}},
                'axisLabel': {'color': '#94a3b8', 'fontFamily': 'Inter, sans-serif', 'fontSize': 10}
            },
            'dataZoom': [{'type': 'inside'}],
            'series': [
                {
                    'name': 'Độ ẩm đất N1',
                    'type': 'line',
                    'smooth': True,
                    'connectNulls': True,
                    'showSymbol': False,
                    'itemStyle': {'color': '#0f766e'},
                    'lineStyle': {'width': 3},
                    'areaStyle': {
                        'color': {
                            'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                            'colorStops': [
                                {'offset': 0, 'color': 'rgba(15, 118, 110, 0.15)'},
                                {'offset': 1, 'color': 'rgba(15, 118, 110, 0.01)'}
                            ]
                        }
                    },
                    'data': n1_sh,
                },
                {
                    'name': 'Độ ẩm đất N2',
                    'type': 'line',
                    'smooth': True,
                    'connectNulls': True,
                    'showSymbol': False,
                    'itemStyle': {'color': '#818cf8'},
                    'lineStyle': {'width': 2.5},
                    'areaStyle': {
                        'color': {
                            'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                            'colorStops': [
                                {'offset': 0, 'color': 'rgba(129, 140, 248, 0.08)'},
                                {'offset': 1, 'color': 'rgba(129, 140, 248, 0.01)'}
                            ]
                        }
                    },
                    'data': n2_sh,
                }
            ]
        }).classes('w-full flex-grow')


def build_soil_ec_chart(df, current_farm):
    if df.empty:
        with ui.element('div').classes('w-full card h-96 flex items-center justify-center'):
            ui.label("Không có dữ liệu EC đất").classes('text-slate-400 font-medium')
        return
        
    df_n1 = df[df['node_id'] == 1]
    df_n2 = df[df['node_id'] == 2]
    
    raw_times = sorted(list(set(df['timestamp'].dropna())))
    clean_times = []
    for t in raw_times:
        if pd.isna(t) or t == 'NaT' or t is None or str(t).strip() == '':
            continue
        try:
            dt = datetime.strptime(str(t), '%Y-%m-%d %H:%M:%S')
            clean_times.append(dt.strftime('%H:%M\n%d/%m'))
        except:
            clean_times.append(str(t))
            
    def get_data(d, col):
        m = dict(zip(d['timestamp'], d[col]))
        return [m.get(t, None) for t in raw_times]
        
    n1_sec = get_data(df_n1, 'ec')
    n2_sec = get_data(df_n2, 'ec')
    
    # Tính toán chỉ số thống kê trung bình
    ec1_avg = df_n1['ec'].mean() if not df_n1.empty else None
    ec2_avg = df_n2['ec'].mean() if not df_n2.empty else None
    stats_parts = []
    if ec1_avg is not None and not pd.isna(ec1_avg):
        stats_parts.append(f"N1: {ec1_avg:.2f} mS/cm")
    if ec2_avg is not None and not pd.isna(ec2_avg):
        stats_parts.append(f"N2: {ec2_avg:.2f} mS/cm")
    stats_text = ""
    if stats_parts:
        stats_text = f'<span class="text-xs text-slate-500 font-normal ml-3 bg-slate-100 px-2.5 py-1 rounded-full">TB | {" - ".join(stats_parts)}</span>'
        
    with ui.element('div').classes('w-full card hover-elevate flex flex-col justify-between p-5').style('height: 480px;'):
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('flash_on', size='sm').classes('text-purple-500 bg-purple-50 p-2 rounded-lg')
                ui.html(f'<div class="flex items-center"><span class="font-bold text-base text-slate-800">Độ dẫn điện đất (EC đất)</span>{stats_text}</div>')
                
        ui.echart({
            'tooltip': {
                'trigger': 'axis',
                'axisPointer': {'type': 'cross', 'crossStyle': {'color': '#94a3b8'}},
            },
            'legend': {
                'data': ['EC đất N1', 'EC đất N2'],
                'top': 4, 'right': 10,
                'textStyle': {'fontSize': 11, 'fontFamily': 'Inter, sans-serif', 'color': '#64748b'},
                'itemWidth': 16, 'itemHeight': 3,
            },
            'grid': {'left': '3%', 'right': '4%', 'bottom': '10%', 'top': '14%', 'containLabel': True},
            'xAxis': {
                'type': 'category',
                'boundaryGap': False,
                'data': clean_times,
                'axisLine': {'lineStyle': {'color': '#f1f5f9'}},
                'axisLabel': {'color': '#94a3b8', 'fontFamily': 'Inter, sans-serif', 'fontSize': 10}
            },
            'yAxis': {
                'type': 'value',
                'name': 'Độ dẫn điện (mS/cm)',
                'nameTextStyle': {'color': '#94a3b8', 'fontSize': 10, 'align': 'right'},
                'axisLine': {'show': False},
                'axisTick': {'show': False},
                'splitLine': {'lineStyle': {'type': 'dashed', 'color': '#f1f5f9'}},
                'axisLabel': {'color': '#94a3b8', 'fontFamily': 'Inter, sans-serif', 'fontSize': 10}
            },
            'dataZoom': [{'type': 'inside'}],
            'series': [
                {
                    'name': 'EC đất N1', 'type': 'line', 'smooth': True, 'connectNulls': True, 'showSymbol': False,
                    'itemStyle': {'color': '#6d28d9'}, 'lineStyle': {'width': 3},
                    'areaStyle': {
                        'color': {
                            'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                            'colorStops': [
                                {'offset': 0, 'color': 'rgba(109, 40, 217, 0.12)'},
                                {'offset': 1, 'color': 'rgba(109, 40, 217, 0.01)'}
                            ]
                        }
                    },
                    'data': n1_sec,
                },
                {
                    'name': 'EC đất N2', 'type': 'line', 'smooth': True, 'connectNulls': True, 'showSymbol': False,
                    'itemStyle': {'color': '#a78bfa'}, 'lineStyle': {'width': 2.5},
                    'areaStyle': {
                        'color': {
                            'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                            'colorStops': [
                                {'offset': 0, 'color': 'rgba(167, 139, 250, 0.08)'},
                                {'offset': 1, 'color': 'rgba(167, 139, 250, 0.01)'}
                            ]
                        }
                    },
                    'data': n2_sec,
                }
            ]
        }).classes('w-full flex-grow')


def build_water_chart(df, current_farm):
    if df.empty:
        with ui.element('div').classes('w-full card h-96 flex items-center justify-center'):
            ui.label("Không có dữ liệu Chất lượng nước").classes('text-slate-400 font-medium')
        return
        
    raw_times = df['timestamp'].tolist()
    clean_times = []
    for t in raw_times:
        if pd.isna(t) or t == 'NaT' or t is None or str(t).strip() == '':
            continue
        try:
            dt = datetime.strptime(str(t), '%Y-%m-%d %H:%M:%S')
            clean_times.append(dt.strftime('%H:%M\n%d/%m'))
        except:
            clean_times.append(str(t))
            
    # Tính toán chỉ số thống kê trung bình
    ph_avg = df['ph_val'].mean() if not df.empty else None
    ec_avg = df['ec_val'].mean() if not df.empty else None
    stats_parts = []
    if ph_avg is not None and not pd.isna(ph_avg):
        stats_parts.append(f"pH {ph_avg:.2f}")
    if ec_avg is not None and not pd.isna(ec_avg):
        stats_parts.append(f"EC {ec_avg:.2f} mS/cm")
    stats_text = ""
    if stats_parts:
        stats_text = f'<span class="text-xs text-slate-500 font-normal ml-3 bg-slate-100 px-2.5 py-1 rounded-full">TB | {" - ".join(stats_parts)}</span>'
        
    with ui.element('div').classes('w-full card hover-elevate flex flex-col justify-between p-5').style('height: 480px;'):
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('analytics', size='sm').classes('text-pink-500 bg-pink-50 p-2 rounded-lg')
                ui.html(f'<div class="flex items-center"><span class="font-bold text-base text-slate-800">Chất lượng nước (pH / EC)</span>{stats_text}</div>')
                
        ui.echart({
            'tooltip': {
                'trigger': 'axis',
                'axisPointer': {'type': 'cross', 'crossStyle': {'color': '#94a3b8'}},
            },
            'legend': {
                'data': ['pH', 'EC nước'],
                'top': 4, 'right': 10,
                'textStyle': {'fontSize': 11, 'fontFamily': 'Inter, sans-serif', 'color': '#64748b'},
                'itemWidth': 16, 'itemHeight': 3,
            },
            'grid': {'left': '3%', 'right': '4%', 'bottom': '10%', 'top': '14%', 'containLabel': True},
            'xAxis': {
                'type': 'category',
                'boundaryGap': False,
                'data': clean_times,
                'axisLine': {'lineStyle': {'color': '#f1f5f9'}},
                'axisLabel': {'color': '#94a3b8', 'fontFamily': 'Inter, sans-serif', 'fontSize': 10}
            },
            'yAxis': [
                {
                    'type': 'value',
                    'name': 'pH',
                    'nameTextStyle': {'color': '#94a3b8', 'fontSize': 10, 'align': 'right'},
                    'min': 0, 'max': 14,
                    'axisLine': {'show': False},
                    'axisTick': {'show': False},
                    'splitLine': {'lineStyle': {'type': 'dashed', 'color': '#f1f5f9'}},
                    'axisLabel': {'color': '#94a3b8', 'fontFamily': 'Inter, sans-serif', 'fontSize': 10}
                },
                {
                    'type': 'value',
                    'name': 'EC nước (mS/cm)',
                    'nameTextStyle': {'color': '#94a3b8', 'fontSize': 10, 'align': 'left'},
                    'axisLine': {'show': False},
                    'axisTick': {'show': False},
                    'splitLine': {'show': False},
                    'axisLabel': {'color': '#94a3b8', 'fontFamily': 'Inter, sans-serif', 'fontSize': 10}
                }
            ],
            'dataZoom': [{'type': 'inside'}],
            'series': [
                {
                    'name': 'pH',
                    'type': 'line',
                    'smooth': True,
                    'connectNulls': True,
                    'showSymbol': False,
                    'itemStyle': {'color': '#ec4899'},
                    'lineStyle': {'width': 3},
                    'areaStyle': {
                        'color': {
                            'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                            'colorStops': [
                                {'offset': 0, 'color': 'rgba(236, 72, 153, 0.08)'},
                                {'offset': 1, 'color': 'rgba(236, 72, 153, 0.01)'}
                            ]
                        }
                    },
                    'data': df['ph_val'].tolist(),
                    'markLine': {
                        'silent': True,
                        'symbol': 'none',
                        'lineStyle': {'color': '#f59e0b', 'type': 'dashed', 'width': 1},
                        'data': [
                            {'yAxis': 6.0, 'label': {'position': 'end', 'formatter': 'pH tối thiểu (6.0)', 'fontSize': 9, 'color': '#f59e0b'}},
                            {'yAxis': 8.0, 'label': {'position': 'end', 'formatter': 'pH tối đa (8.0)', 'fontSize': 9, 'color': '#f59e0b'}}
                        ]
                    }
                },
                {
                    'name': 'EC nước',
                    'type': 'line',
                    'smooth': True,
                    'connectNulls': True,
                    'showSymbol': False,
                    'yAxisIndex': 1,
                    'itemStyle': {'color': '#8b5cf6'},
                    'lineStyle': {'width': 2.5, 'type': 'dashed'},
                    'areaStyle': {
                        'color': {
                            'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                            'colorStops': [
                                {'offset': 0, 'color': 'rgba(139, 92, 246, 0.08)'},
                                {'offset': 1, 'color': 'rgba(139, 92, 246, 0.01)'}
                            ]
                        }
                    },
                    'data': df['ec_val'].tolist(),
                }
            ]
        }).classes('w-full flex-grow')
