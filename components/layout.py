from nicegui import ui

def tao_menu_chung(active_page='Home'):
    """Hàm này sẽ được gọi ở mọi trang để tạo thanh sidebar"""
    ui.query('body').classes('bg-[#f4f6f9]')
    with ui.left_drawer(value=True).classes('bg-[#faf9f8] border-r border-gray-200 w-64 flex flex-col justify-between'):
        with ui.column().classes('w-full p-4'):
            # Logo
            with ui.row().classes('items-center gap-2 mb-8'):
                ui.icon('monitor_heart', size='md').classes('text-gray-800')
                ui.label('SMIOT').classes('text-2xl font-black tracking-wider text-gray-900')
            
            # Menu Items
            ui.label('Application').classes('text-xs text-gray-500 mb-2')
            
            menu_items = [
                ('home', 'Home', '/'), ('devices', 'Device', '/devices'), 
                ('bolt', 'Inverter', '/inverter'), ('memory', 'PLC', '/plc'), 
                ('bar_chart', 'Chart', '/chart'), ('database', 'Data', '/data')
            ]
            
            for icon, name, url in menu_items:
                is_active = (name == active_page)
                bg_class = 'bg-white shadow-sm font-bold text-gray-900' if is_active else 'text-gray-600 hover:bg-gray-100'
                
                with ui.row().classes(f'w-full items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors {bg_class}').on('click', lambda u=url: ui.navigate.to(u)):
                    ui.icon(icon, size='sm')
                    ui.label(name).classes('text-sm')

        # User Profile (Bottom)
        with ui.row().classes('w-full items-center justify-between p-4 border-t border-gray-200'):
            with ui.row().classes('items-center gap-2'):
                ui.avatar('person').classes('bg-blue-100 text-blue-500')
                ui.label('Trần Quốc Trung').classes('text-sm font-bold')
            ui.icon('unfold_more', size='sm').classes('text-gray-400')
