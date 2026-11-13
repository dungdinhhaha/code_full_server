from nicegui import ui
from pages.login import check_login
from pages.home import global_topbar, sidebar, CUSTOM_CSS
from pages.incident import DD_BASE, DD_DASHBOARD

# Trang này chỉ dẫn đường sang Datadog: biểu đồ, monitor và quan sát AI được xem ở đó.
DD_LLM_URL = f"{DD_BASE}/llm/applications"
DD_MONITORS_URL = f"{DD_BASE}/monitors/manage"

CHART_CSS = """
.dd-hub{max-width:980px;margin:24px auto 0;border:1px solid #e8ecf0;border-left:4px solid #632ca6;border-radius:16px;background:#fff;padding:26px 28px;box-shadow:0 1px 4px rgba(30,41,59,.05)}
.dd-hub-title{font-size:22px;font-weight:700;color:#1e293b;line-height:1.3;margin-bottom:8px}
.dd-hub-note{font-size:14px;color:#64748b;line-height:1.6;max-width:620px;margin-bottom:22px}
.dd-grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(250px,1fr))}
.dd-tile{display:flex;flex-direction:column;gap:10px;padding:18px;border-radius:12px;border:1px solid #e8ecf0;background:#fafbfc;color:#1e293b;text-decoration:none;transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease}
.dd-tile:hover{transform:translateY(-2px);box-shadow:0 8px 18px rgba(99,44,166,.10);border-color:#c4b5e0}
.dd-tile:focus-visible{outline:2px solid #632ca6;outline-offset:2px}
.dd-tile-top{display:flex;align-items:center;justify-content:space-between}
.dd-ico{width:38px;height:38px;border-radius:10px;display:grid;place-items:center;background:#f3eefb;color:#632ca6}
.dd-open{color:#94a3b8}
.dd-tile:hover .dd-open{color:#632ca6}
.dd-tile-title{font-size:15px;font-weight:700}
.dd-tile-desc{font-size:13px;color:#64748b;line-height:1.5}
.dd-hint{font-size:12px;color:#94a3b8;margin-top:14px}
@media (prefers-reduced-motion: reduce){.dd-tile,.dd-tile:hover{transition:none;transform:none}}
"""

TILES = [
    ("dashboard", "Dashboard vận hành",
     "Telemetry cảm biến, tài nguyên EC2 và MongoDB theo thời gian.", DD_DASHBOARD),
    ("psychology", "Quan sát AI",
     "LLM Observability của smiot-smart-farm: số lần gọi AI, độ trễ và token.", DD_LLM_URL),
    ("notifications_active", "Tất cả monitor",
     "Danh sách đầy đủ monitor và trạng thái hiện tại.", DD_MONITORS_URL),
]


@ui.page('/history')
def history_redirect():
    ui.navigate.to('/chart')


@ui.page('/chart')
def chart_page():
    if not check_login(): return

    ui.add_head_html(f"<style>{CUSTOM_CSS}{CHART_CSS}</style>")
    sidebar(active="Chart")

    with ui.element('div').classes('main-content'):
        global_topbar("Biểu Đồ Phân Tích", "📈")

        with ui.element('div').classes('content-area'):
            with ui.element('section').classes('dd-hub'):
                ui.label("Biểu đồ, monitor và quan sát AI nằm trên Datadog").classes('dd-hub-title')
                ui.label(
                    "Ứng dụng chỉ dẫn đường. Dữ liệu vận hành được theo dõi và điều tra trên Datadog, "
                    "mỗi liên kết dưới đây mở ở tab mới."
                ).classes('dd-hub-note')
                with ui.element('div').classes('dd-grid'):
                    for icon, title, desc, url in TILES:
                        with ui.link(target=url, new_tab=True).classes('dd-tile'):
                            with ui.element('div').classes('dd-tile-top'):
                                ui.icon(icon, size='sm').classes('dd-ico')
                                ui.icon('open_in_new', size='xs').classes('dd-open')
                            ui.label(title).classes('dd-tile-title')
                            ui.label(desc).classes('dd-tile-desc')
