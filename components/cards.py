from nicegui import ui

def tao_the_node(ten_node, nhiet_do_kk, do_am_kk, nhiet_do_dat, do_am_dat, ec, thoi_gian):
    """Tạo Card giám sát Node (Cảm biến không khí và đất)"""
    with ui.card().classes('w-full h-full rounded-2xl shadow-sm border border-gray-100 p-4 bg-white flex flex-col hover-elevate glass-card'):
        # Header Node
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('memory', size='sm').classes('text-blue-600 bg-blue-50 p-2 rounded-lg')
                ui.label(ten_node).classes('font-black text-lg')
            ui.label('ONLINE').classes('bg-teal-500 text-white px-3 py-1 rounded-full text-[10px] font-bold')
        
        # Không khí
        ui.label('KHÔNG KHÍ').classes('text-[10px] text-gray-400 font-bold tracking-wider mb-2')
        with ui.row().classes('w-full gap-2 mb-4'):
            with ui.column().classes('flex-1 bg-gray-50 rounded-xl p-2 border border-gray-100'):
                with ui.row().classes('items-center gap-1 text-orange-500'):
                    ui.icon('device_thermostat', size='xs')
                    ui.label('NHIỆT ĐỘ').classes('text-[9px] font-bold text-gray-400')
                ui.label(nhiet_do_kk).classes('text-xl font-bold mt-1')
            with ui.column().classes('flex-1 bg-gray-50 rounded-xl p-2 border border-gray-100'):
                with ui.row().classes('items-center gap-1 text-blue-400'):
                    ui.icon('water_drop', size='xs')
                    ui.label('ĐỘ ẨM').classes('text-[9px] font-bold text-gray-400')
                ui.label(do_am_kk).classes('text-xl font-bold mt-1')

        # Đất trồng
        ui.label('ĐẤT TRỒNG').classes('text-[10px] text-gray-400 font-bold tracking-wider mb-2')
        with ui.row().classes('w-full gap-2 mb-4'):
            with ui.column().classes('flex-1 bg-gray-50 rounded-xl p-2 border border-gray-100'):
                with ui.row().classes('items-center gap-1 text-teal-500'):
                    ui.icon('air', size='xs')
                    ui.label('NHIỆT ĐỘ').classes('text-[9px] font-bold text-gray-400')
                ui.label(nhiet_do_dat).classes('text-xl font-bold mt-1')
            with ui.column().classes('flex-1 bg-gray-50 rounded-xl p-2 border border-gray-100'):
                with ui.row().classes('items-center gap-1 text-blue-600'):
                    ui.icon('waves', size='xs')
                    ui.label('ĐỘ ẨM').classes('text-[9px] font-bold text-gray-400')
                ui.label(do_am_dat).classes('text-xl font-bold mt-1')
        
        ui.element('div').classes('flex-grow') # Empty fill space
        ui.separator().classes('mb-3 mt-4')
        
        # Footer Node (EC & Time)
        with ui.row().classes('w-full justify-between items-center mt-auto'):
            with ui.row().classes('items-center gap-1 text-purple-600'):
                ui.icon('show_chart', size='xs')
                ui.label(f'EC: {ec}').classes('text-xs font-bold')
            with ui.row().classes('items-center gap-1 text-gray-400'):
                ui.icon('schedule', size='xs')
                ui.label(f'Update: {thoi_gian}').classes('text-[10px]')

def tao_the_luu_luong():
    """Tạo Card biểu đồ lưu lượng nước"""
    with ui.card().classes('w-full h-full rounded-2xl shadow-sm border border-gray-100 p-4 bg-white flex flex-col justify-between hover-elevate glass-card relative overflow-hidden group'):
        ui.element('div').classes('shimmer-overlay')
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('bolt', size='sm').classes('text-blue-500 bg-blue-50 p-2 rounded-full')
                ui.label('Flow_Meter').classes('font-black text-lg')
            ui.label('LIVE').classes('text-teal-500 border border-teal-500 px-2 py-0.5 rounded-full text-[10px] font-bold')
        
        with ui.row().classes('w-full gap-2 mb-4'):
            with ui.column().classes('flex-1 bg-gray-50 rounded-xl p-3 items-center'):
                ui.label('LINE01').classes('text-[10px] font-bold text-blue-500')
                ui.label('0 L/m').classes('text-xl font-bold')
            with ui.column().classes('flex-1 bg-gray-50 rounded-xl p-3 items-center'):
                ui.label('LINE02').classes('text-[10px] font-bold text-teal-500')
                ui.label('0 L/m').classes('text-xl font-bold')
        
        ui.element('div').classes('flex-grow')
        
        # Dark Box Tổng lưu lượng
        with ui.row().classes('w-full bg-[#1e2330] rounded-xl p-4 items-center justify-between text-white mt-auto'):
            with ui.row().classes('items-center gap-3'):
                ui.icon('analytics', size='sm').classes('text-blue-400')
                with ui.column().classes('gap-0'):
                    ui.label('TỔNG LƯU LƯỢNG HIỆN TẠI').classes('text-[9px] text-gray-400')
                    ui.label('18.35 L').classes('text-lg font-bold')
            ui.icon('swap_horiz', size='sm').classes('text-gray-500')

def tao_the_he_thong_nuoc():
    """Tạo Card EC và pH"""
    with ui.column().classes('w-full h-full gap-4'):
        # Thẻ EC
        with ui.card().classes('w-full flex-1 rounded-2xl shadow-sm border border-gray-100 p-4 bg-white flex flex-col justify-between hover-elevate glass-card relative overflow-hidden group'):
            ui.element('div').classes('shimmer-overlay')
            with ui.row().classes('w-full justify-between mb-2'):
                ui.label('ec').classes('font-bold uppercase text-gray-700')
                ui.label('Online').classes('bg-green-100 text-green-600 px-2 rounded-full text-[10px]')
            with ui.column().classes('w-full gap-0 mb-4'):
                ui.label('EC').classes('text-[10px] text-gray-400')
                ui.label('0').classes('text-3xl font-bold text-blue-600')
            with ui.row().classes('w-full justify-between text-[10px] text-gray-500 mt-auto'):
                ui.label('Voltage: 0')
                ui.label('Raw: 0')
        
        # Thẻ pH
        with ui.card().classes('w-full flex-1 rounded-2xl shadow-sm border border-gray-100 p-4 bg-white flex flex-col justify-between hover-elevate glass-card relative overflow-hidden group'):
            ui.element('div').classes('shimmer-overlay')
            with ui.row().classes('w-full justify-between mb-2'):
                ui.label('ph').classes('font-bold uppercase text-gray-700')
                ui.label('Online').classes('bg-green-100 text-green-600 px-2 rounded-full text-[10px]')
            with ui.column().classes('w-full gap-0 mb-4'):
                ui.label('pH').classes('text-[10px] text-gray-400')
                ui.label('14').classes('text-3xl font-bold text-teal-500')
            with ui.row().classes('w-full justify-between text-[10px] text-gray-500 mt-auto'):
                ui.label('mV: 74.28')
                ui.label('Raw: 60')

def tao_the_thoi_tiet():
    """Tạo Card Thời tiết màu xanh dương"""
    with ui.card().classes('w-full h-full rounded-2xl shadow-md p-6 bg-blue-500 text-white flex flex-col justify-between hover-elevate relative overflow-hidden group'):
        ui.element('div').classes('shimmer-overlay')
        with ui.row().classes('w-full justify-between items-start mb-6'):
            with ui.column().classes('gap-0'):
                ui.label('Thành phố Hồ Chí Minh').classes('text-xl font-bold')
                ui.label('Vị trí: 10.86, 106.81').classes('text-xs text-blue-200 mt-1')
            ui.label('Live').classes('bg-white/20 px-2 py-0.5 rounded-full text-[10px]')
        
        with ui.row().classes('w-full gap-2 mb-6'):
            for time, temp, hum in [('11:00', '33.7°', '49%'), ('12:00', '33.7°', '50%'), ('13:00', '34.2°', '48%')]:
                with ui.column().classes('flex-1 bg-white rounded-xl p-3 items-center text-gray-800'):
                    ui.label(time).classes('text-[10px] text-gray-500 font-bold')
                    ui.label(temp).classes('text-lg font-bold')
                    with ui.row().classes('items-center text-blue-400 gap-1 text-[10px]'):
                        ui.icon('water_drop', size='xs')
                        ui.label(hum).classes('font-bold')
        
        ui.element('div').classes('flex-grow')
        
        with ui.column().classes('w-full gap-2 mt-auto'):
            ui.label('CHỈ SỐ TỔNG HỢP NGÀY').classes('text-[10px] text-blue-200 font-bold tracking-wider')
            with ui.row().classes('w-full justify-between bg-white rounded-xl p-4 text-gray-800'):
                with ui.column().classes('gap-0'):
                    ui.label('Bức xạ mặt trời').classes('text-[10px] text-gray-400 font-bold')
                    ui.label('6401 W/m²').classes('font-bold text-orange-500')
                with ui.column().classes('items-end gap-0'):
                    ui.label('Thoát hơi nước (ETO)').classes('text-[10px] text-gray-400 font-bold')
                    ui.label('5.74 mm').classes('font-bold text-green-500')

def tao_the_ai():
    """Tạo Card Dự đoán AI màu đen"""
    with ui.card().classes('w-full h-full rounded-2xl shadow-lg bg-[#141723] text-white p-6 flex flex-col justify-between hover-elevate neon-glow relative overflow-hidden group'):
        ui.element('div').classes('shimmer-overlay')
        with ui.row().classes('items-center gap-2 mb-4'):
            ui.icon('psychology', size='sm').classes('text-blue-400')
            ui.label('Dự đoán từ AI').classes('text-lg font-bold')
        
        with ui.row().classes('w-full justify-between items-center mb-4'):
            ui.label('Lượng nước đề xuất').classes('text-sm text-gray-400')
            ui.label('688,9 ml').classes('text-2xl font-bold text-teal-400')
            
        with ui.row().classes('w-full justify-between items-center mb-4'):
            ui.label('Gợi ý từ AI:').classes('text-sm text-gray-400')
            ui.label('tưới').classes('bg-teal-500/20 text-teal-400 px-4 py-1 rounded-full text-sm font-bold')
        
        ui.element('div').classes('flex-grow')
        
        with ui.column().classes('w-full mt-auto'):
            ui.separator().classes('bg-gray-700/50 mb-2')
            ui.label('10:58:16').classes('text-[10px] text-gray-500')
