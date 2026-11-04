"""Harvest planning view: MongoDB time-series analysis, lot QR and stage gallery."""

from nicegui import ui

from pages.home import CUSTOM_CSS, global_topbar, sidebar, state
from pages.login import check_login
from service.mongodb_showcase import list_harvest_lots, load_harvest_story
from service.traceability import public_lot_url, qr_data_uri, stage_images_for_lot

FARM_KEYS = {"Greenhouse A": "greenhouse_a", "Greenhouse B": "greenhouse_b", "Greenhouse C": "greenhouse_c", "Greenhouse D": "greenhouse_d"}


def _date(value):
    return value.strftime("%d/%m/%Y")


@ui.page("/mongodb-lab")
def mongodb_lab_page():
    if not check_login():
        return
    ui.add_head_html(f"<style>{CUSTOM_CSS}</style>")
    sidebar(active="Mùa vụ & truy xuất")
    with ui.element("div").classes("main-content"):
        global_topbar("Mùa vụ & truy xuất", "🍈")
        with ui.element("div").classes("content-area"):
            with ui.column().classes("w-full max-w-7xl mx-auto gap-4"):
                @ui.refreshable
                def story():
                    farm_name = state.get("selected_farm", "Greenhouse A")
                    farm_key = FARM_KEYS.get(farm_name, "greenhouse_a")
                    lots = list_harvest_lots(farm_key)
                    if not lots:
                        ui.label("Chưa có lô dưa trong nhà kính này.").classes("rounded-xl bg-amber-50 p-5")
                        return
                    lot_options = {row["lot_id"]: f"{row.get('crop_name', 'Dưa lưới')} · {row['lot_id']}" for row in lots}
                    if state.get("selected_harvest_farm") != farm_key or state.get("selected_harvest_lot") not in lot_options:
                        state["selected_harvest_lot"] = lots[0]["lot_id"]
                    state["selected_harvest_farm"] = farm_key
                    selected_lot = state["selected_harvest_lot"]
                    with ui.row().classes("w-full items-center justify-between gap-3 flex-wrap"):
                        ui.label("Khi nào nên bắt đầu kiểm tra quả?").classes("text-xl font-bold text-slate-900")
                        ui.select(lot_options, value=selected_lot, label="Chọn lô",
                                  on_change=lambda e: (state.update(selected_harvest_lot=e.value), story.refresh())
                                  ).props("outlined dense options-dense").classes("w-80")
                    try:
                        result = load_harvest_story(farm_key, selected_lot)
                    except Exception as exc:
                        ui.label(f"Không tải được dữ liệu mùa vụ: {exc}").classes("text-red-700")
                        return
                    if not result.get("crop_cycle"):
                        ui.label("Lô này chưa có ngày đậu quả để tính lịch kiểm tra.").classes("rounded-xl bg-amber-50 p-4")
                        return
                    harvest_estimate = result["reference_day"]
                    with ui.row().classes("w-full gap-3 flex-wrap"):
                        for title, value, color in [
                            ("ĐẬU QUẢ", _date(result["pollination_day"]), "emerald"),
                            ("NGÀY SAU ĐẬU QUẢ", str(result["days_since_pollination"]), "sky"),
                            ("BẮT ĐẦU KIỂM TRA", _date(harvest_estimate), "amber"),
                            ("ĐỘ ĐỦ DỮ LIỆU", f"{result['coverage_pct']}%", "violet"),
                        ]:
                            with ui.column().classes(f"flex-1 min-w-44 rounded-xl border border-{color}-200 bg-{color}-50 p-4 gap-1"):
                                ui.label(title).classes(f"text-xs font-bold text-{color}-800")
                                ui.label(value).classes("text-xl font-bold text-slate-900")

                    heat = result.get("heat_by_node", [])
                    with ui.row().classes("w-full gap-4 flex-wrap"):
                        if heat:
                            values = {f"Khu {row['node_id']}": row["gdd"] for row in heat}
                            ui.echart({"tooltip": {"trigger": "axis"}, "xAxis": {"type": "category", "data": list(values)},
                                       "yAxis": {"type": "value", "name": "°C·ngày"},
                                       "series": [{"type": "bar", "data": [
                                           {"value": value, "itemStyle": {"color": ["#f59e0b", "#fb7185"][i % 2]}}
                                           for i, value in enumerate(values.values())], "barWidth": "45%",
                                           "label": {"show": True, "position": "top"}}]
                                       }).classes("flex-1 min-w-80 h-72 rounded-xl bg-white p-3")
                        if result.get("chart_days"):
                            series = [{"name": f"Khu {node['node_id']}", "type": "line", "smooth": True,
                                       "connectNulls": False,
                                       "data": [[row["date"].strftime("%d/%m"), row["cumulative_gdd_context"] if row["complete"] else None]
                                                 for row in node["daily"]]} for node in result["nodes"]]
                            dates = [row["date"].strftime("%d/%m") for row in result["nodes"][0]["daily"]]
                            ui.echart({"tooltip": {"trigger": "axis"}, "legend": {"bottom": 0},
                                       "xAxis": {"type": "category", "data": dates},
                                       "yAxis": {"type": "value", "name": "°C·ngày"}, "series": series
                                       }).classes("flex-1 min-w-80 h-72 rounded-xl bg-white p-3")
                    ui.label("Nhiệt tích lũy theo từng ngày").classes("text-sm font-semibold text-slate-700")
                    ui.label(f"Cửa sổ tham khảo: {_date(result['harvest_early'])} – {_date(result['harvest_late'])} · kiểm tra quả trước khi chốt ngày hái.").classes("text-sm text-amber-800")
                    if result.get("chart_days"):
                        series = [{"name": f"Khu {node['node_id']}", "type": "line", "smooth": True,
                                   "connectNulls": False,
                                   "data": [[row["date"].strftime("%d/%m"), row["mean_air_temp_c"] if row["complete"] else None]
                                             for row in node["daily"]]} for node in result["nodes"]]
                        dates = [row["date"].strftime("%d/%m") for row in result["nodes"][0]["daily"]]
                        ui.echart({"tooltip": {"trigger": "axis"}, "legend": {"bottom": 0},
                                   "xAxis": {"type": "category", "data": dates},
                                   "yAxis": {"type": "value", "name": "°C"}, "series": series
                                   }).classes("w-full h-64 rounded-xl bg-white p-3")
                    with ui.expansion("Cách tính").classes("w-full"):
                        ui.label("Ngày đủ mẫu mới được cộng nhiệt. Biểu đồ giúp lên lịch kiểm tra quả, không tự kết luận quả đã chín.").classes("text-sm text-slate-600")
                        ui.label(f"MongoDB gom {result['raw_count']:,} mẫu thành {result['daily_count']:,} điểm ngày · {result['aggregation_ms']} ms.").classes("text-xs text-slate-500")

                    token = result["crop_cycle"].get("public_share_token")
                    if token:
                        customer_url = public_lot_url(token)
                        with ui.expansion("Mã QR hồ sơ khách hàng").classes("w-full bg-white rounded-xl"):
                            with ui.row().classes("items-center gap-4 flex-wrap"):
                                ui.image(qr_data_uri(customer_url)).classes("w-36 h-36")
                                with ui.column().classes("gap-2"):
                                    ui.label("Khách quét mã để xem hồ sơ và ảnh theo giai đoạn.").classes("text-sm text-slate-700")
                                    ui.link("Mở trang khách hàng", customer_url, new_tab=True).classes("text-blue-700 font-semibold")

                    try:
                        stage_images = stage_images_for_lot(farm_key, selected_lot)
                    except Exception as exc:
                        stage_images = []
                        ui.label(f"Không tải được ảnh từ S3: {exc}").classes("text-sm text-amber-800")
                    ui.label("Ảnh theo giai đoạn").classes("text-lg font-bold text-slate-800 mt-2")
                    if not stage_images:
                        ui.label("Lô này chưa có ảnh theo giai đoạn.").classes("rounded-xl bg-white border border-slate-200 p-5 text-slate-500")
                    else:
                        with ui.element("div").style("display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;width:100%"):
                            for item in stage_images:
                                with ui.column().classes("rounded-2xl bg-white border border-slate-200 p-3 gap-2"):
                                    ui.image(item["image_url"]).classes("w-full h-64 object-cover rounded-xl")
                                    ui.label(item["stage_label"]).classes("font-bold text-slate-800")
                                    at = item.get("stage_at")
                                    date_text = _date(at) if at else "Chưa có ngày"
                                    date_kind = "Dự kiến" if item.get("date_kind") == "forecast" else "Ngày ghi nhận"
                                    ui.label(f"{date_kind}: {date_text}").classes("text-sm text-slate-500")
                story()
