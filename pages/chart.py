from nicegui import ui
from pages.login import check_login
from pages.home import global_topbar, sidebar, CUSTOM_CSS
from pages.incident import DD_BASE, DD_DASHBOARD
from components.ui_kit import page_header, panel, ext_link

# Trang này chỉ dẫn đường sang Datadog: biểu đồ, monitor và log được xem ở đó.
DD_LLM_URL = f"{DD_BASE}/llm/applications"
DD_MONITORS_URL = f"{DD_BASE}/monitors/manage"
DD_LOGS_URL = f"{DD_BASE}/logs"

CHART_CSS = """
.dd-grid{display:grid;gap:12px;grid-template-columns:minmax(0,1fr);margin-top:4px}
@media (min-width:640px){.dd-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:768px){.dd-grid{grid-template-columns:1fr}}
.dd-grid .sm-panel{display:flex;flex-direction:column;gap:10px}
.dd-about{font-size:13px;color:var(--sm-ink-2);line-height:1.5;margin:0}
"""

# (tiêu đề, một câu nói mở cái gì, đường dẫn, chữ của liên kết)
TILES = [
    ("Dashboard vận hành",
     "Telemetry cảm biến, tài nguyên EC2 và MongoDB theo thời gian.",
     DD_DASHBOARD, "Mở dashboard trên Datadog"),
    ("Monitor",
     "Danh sách đầy đủ monitor và trạng thái hiện tại.",
     DD_MONITORS_URL, "Mở danh sách monitor"),
    ("Log",
     "Tìm kiếm và lọc log của các dịch vụ trong hệ thống.",
     DD_LOGS_URL, "Mở log trên Datadog"),
    ("Quan sát AI",
     "LLM Observability: số lần gọi AI, độ trễ và token.",
     DD_LLM_URL, "Mở quan sát AI trên Datadog"),
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
        global_topbar("Datadog", emoji="", show_farm_selector=False)

        with ui.element('div').classes('content-area'):
            page_header("Datadog", "Mở dashboard, monitor và log trong tab mới.")
            ui.label(
                "Ứng dụng không vẽ biểu đồ. Số liệu vận hành được theo dõi và điều tra trên Datadog."
            ).classes('dd-about').style('margin-bottom:14px')
            with ui.element('div').classes('dd-grid'):
                for title, desc, url, link_text in TILES:
                    with panel(title):
                        ui.label(desc).classes('dd-about')
                        ext_link(link_text, url)
