"""Mùa vụ và truy xuất: tiến độ dưa lưới, điều kiện tích lũy, chất lượng dữ liệu, ảnh theo giai đoạn.

Số liệu lấy từ aggregation MongoDB trong service.mongodb_showcase.load_harvest_story; trang chỉ vẽ lại.
Mọi mốc thu hoạch là dự kiến để nhắc kiểm tra quả. Trang không khẳng định sản lượng hay chất lượng.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from nicegui import run, ui

from components.theme import CHART
from components.ui_kit import (
    echart_base, ext_link, facts, page_header, panel, sim_badge, source_note, stat, state_panel,
    stats, status_chip,
)
from pages.home import CUSTOM_CSS, global_topbar, sidebar, state
from pages.login import check_login
from service.farm_registry import FARM_KEYS_BY_LABEL
from service.mongodb_showcase import EXPECTED_SAMPLES_PER_DAY, MIN_COVERAGE, list_harvest_lots, load_harvest_story
from service.traceability import STAGE_LABELS, STAGES, public_lot_url, qr_data_uri, stage_images_for_lot

FARM_KEYS = FARM_KEYS_BY_LABEL

LAB_CSS = """
.lab-wrap { max-width:1180px; }
.lab-pick { min-width:280px; }
.lab-stages { display:flex; gap:12px; overflow-x:auto; padding-bottom:4px; -webkit-overflow-scrolling:touch; }
.lab-stage { flex:1 0 150px; min-width:150px; display:flex; flex-direction:column; gap:4px; }
.lab-empty { width:100%; aspect-ratio:4/3; display:flex; align-items:center; justify-content:center;
  background:var(--sm-sunken); border:1px dashed var(--sm-net); border-radius:var(--sm-r-m);
  color:var(--sm-ink-3); font-size:12px; }
.lab-shot { border-radius:var(--sm-r-m); border:1px solid var(--sm-net-soft); }
.lab-stage-k { font-size:13px; font-weight:600; color:var(--sm-ink); }
.lab-stage-d { font-size:12px; color:var(--sm-ink-3); }
.lab-qr { display:flex; flex-wrap:wrap; align-items:center; gap:16px; }
.lab-chart-title { font-size:13px; font-weight:600; color:var(--sm-ink); margin-bottom:4px; }
@media (max-width:768px) {
  .lab-pick { min-width:100%; }
  .lab-stage { flex-basis:140px; min-width:140px; }
  .sm-link { display:inline-flex; align-items:center; min-height:40px; }
}
"""


def _date(value: Any) -> str:
    return value.strftime("%d/%m/%Y") if value else "chưa có"


def _short_date(value: date) -> str:
    return value.strftime("%d/%m")


def _ms(day: date) -> int:
    return int(datetime.combine(day, time.min, timezone.utc).timestamp() * 1000)


def _as_day(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else None


def _rgba(color: str, alpha: float) -> str:
    color = color.lstrip("#")
    r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def stage_spans(images: list[dict[str, Any]] | None, pollination_day: date, harvest_late: date) -> list[dict[str, Any]]:
    """Các giai đoạn có mốc ngày thật hoặc dự kiến. Giai đoạn không có mốc thì bỏ qua, không đoán."""
    known: dict[str, tuple[date, bool]] = {}
    for item in images or []:
        code = item.get("stage_code") or item.get("stage")
        day = _as_day(item.get("stage_at"))
        if code in STAGES and day is not None:
            known[code] = (day, item.get("date_kind") == "forecast")
    known.setdefault("flowering_fruiting", (pollination_day, False))  # ngày đậu quả của chu kỳ là mốc thật
    ordered = sorted(((code, *known[code]) for code in STAGES if code in known), key=lambda row: row[1])
    spans = []
    for index, (code, start, forecast) in enumerate(ordered):
        end = ordered[index + 1][1] if index + 1 < len(ordered) else max(harvest_late, start)
        if end <= start:
            end = start + timedelta(days=1)
        spans.append({"code": code, "label": STAGE_LABELS.get(code, code), "start": start, "end": end,
                      "forecast": forecast})
    return spans


def timeline_option(result: dict[str, Any], spans: list[dict[str, Any]], today: date) -> dict[str, Any]:
    """Dòng thời gian 5 giai đoạn, ngày đậu quả, hôm nay và dải dự kiến kiểm tra quả."""
    pollination, early, late, reference = (result["pollination_day"], result["harvest_early"],
                                           result["harvest_late"], result["reference_day"])
    first = min([pollination, today] + [s["start"] for s in spans])
    last = max([late, today] + [s["end"] for s in spans])
    info = CHART["level"]["info"]
    tints = (CHART["tint"]["none"], CHART["grid"])
    stage_areas = []
    for index, span in enumerate(spans):
        style = {"color": tints[index % 2], "borderColor": CHART["muted"], "borderWidth": 1,
                 "borderType": "dashed" if span["forecast"] else "solid"}
        text = span["label"] + (" (dự kiến)" if span["forecast"] else "")
        stage_areas.append([{"name": text, "xAxis": _ms(span["start"]), "yAxis": 1, "itemStyle": style,
                             "label": {"show": True, "position": "inside", "color": CHART["ink"], "fontSize": 11}},
                            {"xAxis": _ms(span["end"]), "yAxis": 2}])
    window = [{"name": "Dự kiến kiểm tra quả", "xAxis": _ms(early), "yAxis": 0,
               "itemStyle": {"color": _rgba(info, 0.16), "borderColor": info, "borderType": "dashed", "borderWidth": 1},
               "label": {"show": True, "position": "inside", "color": info, "fontSize": 11}},
              {"xAxis": _ms(late), "yAxis": 1}]

    def line(day: date, name: str, color: str, kind: str) -> dict[str, Any]:
        return {"xAxis": _ms(day), "name": name, "lineStyle": {"color": color, "type": kind, "width": 1.5},
                "label": {"formatter": "{b}", "color": color, "fontSize": 11, "position": "end"}}

    marks = [line(pollination, "Đậu quả", CHART["ink"], "dashed"), line(reference, "Mốc tham chiếu", info, "dotted"),
             line(today, "Hôm nay", CHART["level"]["watch"], "solid")]
    option = echart_base()
    option["useUTC"] = True
    option["tooltip"] = {"show": False}
    option["legend"] = {"show": False}
    option["grid"] = {"left": 12, "right": 28, "top": 30, "bottom": 28}
    option["xAxis"] = {**option["xAxis"], "type": "time", "min": _ms(first - timedelta(days=2)),
                       "max": _ms(last + timedelta(days=3)), "splitLine": {"show": False}}
    option["yAxis"] = {"type": "value", "min": 0, "max": 2, "show": False}
    option["series"] = [{"type": "line", "data": [], "silent": True,
                         "markArea": {"silent": True, "data": [*stage_areas, window]},
                         "markLine": {"silent": True, "symbol": "none", "data": marks}}]
    return option


def _window_marks(result: dict[str, Any]) -> dict[str, Any]:
    info = CHART["level"]["info"]
    return {
        "markArea": {"silent": True, "itemStyle": {"color": _rgba(info, 0.12)},
                     "data": [[{"xAxis": _ms(result["harvest_early"])}, {"xAxis": _ms(result["harvest_late"])}]]},
        "markLine": {"silent": True, "symbol": "none", "data": [
            {"xAxis": _ms(result["reference_day"]), "lineStyle": {"color": info, "type": "dotted", "width": 1}, "label": {"show": False}}]},
    }


def daily_option(result: dict[str, Any], field: str, unit: str, digits: int | None = None) -> dict[str, Any]:
    """Đường theo ngày cho từng node; ngày thiếu mẫu để trống (không nội suy). Vẽ dải dự kiến lên trục thời gian."""
    series = []
    for index, node in enumerate(result["nodes"]):
        data = [[_ms(row["date"]), row[field] if row["complete"] and row.get(field) is not None else None]
                for row in node["daily"]]
        item: dict[str, Any] = {"name": f"Node {node['node_id']}", "type": "line", "showSymbol": False,
                                "connectNulls": False, "lineStyle": {"width": 1.8}, "data": data,
                                "color": CHART["series"][index % len(CHART["series"])]}
        if index == 0:
            item.update(_window_marks(result))
        series.append(item)
    option = echart_base()
    option["useUTC"] = True
    option["xAxis"] = {**option["xAxis"], "type": "time", "splitLine": {"show": False}}
    option["yAxis"] = {**option["yAxis"], "type": "value", "scale": True, "name": unit,
                       "nameTextStyle": {"color": CHART["muted"]}}
    option["series"] = series
    return option


def gdd_total_option(result: dict[str, Any]) -> dict[str, Any]:
    heat = result.get("heat_by_node") or []
    option = echart_base()
    option["legend"] = {"show": False}
    option["xAxis"] = {**option["xAxis"], "type": "category", "data": [f"Node {row['node_id']}" for row in heat]}
    option["yAxis"] = {**option["yAxis"], "type": "value", "name": "°C·ngày", "nameTextStyle": {"color": CHART["muted"]}}
    option["series"] = [{"type": "bar", "barMaxWidth": 44, "label": {"show": True, "position": "top", "color": CHART["ink"]},
                         "data": [{"value": row["gdd"], "itemStyle": {"color": CHART["series"][i % len(CHART["series"])]}}
                                  for i, row in enumerate(heat)]}]
    return option


def coverage_option(result: dict[str, Any]) -> dict[str, Any] | None:
    """Lưới lịch: tỉ lệ mẫu có so với kỳ vọng theo ngày và node. Ngày không có mẫu được tô riêng."""
    nodes = result.get("nodes") or []
    if not nodes or not nodes[0]["daily"]:
        return None
    labels = [_short_date(row["date"]) for row in nodes[0]["daily"]]
    cells = []
    for y, node in enumerate(nodes):
        for x, row in enumerate(node["daily"]):
            cells.append([x, y, min(100.0, float(row["coverage_pct"] or 0)), row["samples"]])
    full = int(MIN_COVERAGE * 100)
    option = echart_base()
    option["legend"] = {"show": False}
    option["grid"] = {"left": 64, "right": 12, "top": 8, "bottom": 52}
    option["xAxis"] = {**option["xAxis"], "type": "category", "data": labels, "splitArea": {"show": False},
                       "splitLine": {"show": False}, "axisLabel": {"color": CHART["muted"], "fontSize": 10, "interval": "auto"}}
    option["yAxis"] = {**option["yAxis"], "type": "category", "data": [f"Node {n['node_id']}" for n in nodes],
                       "splitLine": {"show": False}, "inverse": True}
    option["visualMap"] = {
        "type": "piecewise", "orient": "horizontal", "left": "center", "bottom": 0, "dimension": 2,
        "itemWidth": 14, "itemHeight": 14, "textStyle": {"color": CHART["muted"], "fontSize": 11},
        "pieces": [
            {"min": full, "max": 100, "label": f"Đủ mẫu (từ {full}%)", "color": CHART["tint"]["ok"]},
            {"gt": 0, "lt": full, "label": "Thiếu mẫu", "color": CHART["level"]["watch"]},
            {"value": 0, "label": "Không có mẫu", "color": CHART["level"]["act"]},
        ],
    }
    option["series"] = [{"type": "heatmap", "data": cells, "itemStyle": {"borderColor": CHART["surface"], "borderWidth": 2}}]
    option["tooltip"] = {"trigger": "item", "backgroundColor": "#fff", "borderColor": CHART["grid"],
                         "textStyle": {"color": CHART["ink"], "fontSize": 12}}
    return option


@ui.page("/mongodb-lab")
def mongodb_lab_page():
    if not check_login():
        return
    ui.add_head_html(f"<style>{CUSTOM_CSS}{LAB_CSS}</style>")
    sidebar(active="Mùa vụ & truy xuất")
    with ui.element("div").classes("main-content"):
        global_topbar("Mùa vụ và truy xuất", emoji="")
        with ui.element("div").classes("content-area lab-wrap"):
            with ui.element("div").classes("sm-stack"):
                with page_header("Mùa vụ và truy xuất",
                                 "Tiến độ lô dưa lưới, điều kiện tích lũy và ảnh theo giai đoạn. Mốc thu hoạch chỉ là dự kiến để nhắc kiểm tra quả."):
                    sim_badge()
                top = ui.element("div").classes("lab-pick")
                body = ui.element("div").classes("sm-stack")

                def farm_key() -> str:
                    return FARM_KEYS.get(state.get("selected_farm", "Greenhouse A"), "greenhouse_a")

                async def load_lots():
                    key = farm_key()
                    top.clear()
                    body.clear()
                    with body:
                        state_panel("loading", "Đang tải danh sách lô", "Đọc chu kỳ cây trồng từ MongoDB.")
                    try:
                        lots = await run.io_bound(list_harvest_lots, key)
                    except Exception as exc:
                        body.clear()
                        with body:
                            state_panel("error", "Không tải được danh sách lô", f"Lỗi {type(exc).__name__}. Kiểm tra MongoDB rồi thử lại.",
                                        action_label="Thử lại", on_action=load_lots)
                        return
                    if not lots:
                        body.clear()
                        with body:
                            state_panel("empty", "Chưa có lô dưa trong nhà màng này", "Chọn nhà màng khác ở thanh trên.")
                        return
                    options = {row["lot_id"]: f"{row.get('crop_name', 'Dưa lưới')} · {row['lot_id']}" for row in lots}
                    if state.get("selected_harvest_farm") != key or state.get("selected_harvest_lot") not in options:
                        state["selected_harvest_lot"] = lots[0]["lot_id"]
                    state["selected_harvest_farm"] = key
                    with top:
                        async def pick(e):
                            state["selected_harvest_lot"] = e.value
                            await show_lot(key, e.value)
                        ui.select(options, value=state["selected_harvest_lot"], label="Chọn lô", on_change=pick
                                  ).props("outlined dense options-dense").classes("w-full")
                    await show_lot(key, state["selected_harvest_lot"])

                async def show_lot(key: str, lot_id: str):
                    body.clear()
                    with body:
                        state_panel("loading", "Đang tải mùa vụ", "MongoDB đang tổng hợp số đo theo ngày.")
                    result, images = await asyncio.gather(
                        run.io_bound(load_harvest_story, key, lot_id),
                        run.io_bound(stage_images_for_lot, key, lot_id),
                        return_exceptions=True)
                    body.clear()
                    with body:
                        if isinstance(result, Exception):
                            state_panel("error", "Không tải được dữ liệu mùa vụ", f"Lỗi {type(result).__name__}.",
                                        action_label="Thử lại", on_action=lambda: show_lot(key, lot_id))
                            return
                        if not result.get("crop_cycle"):
                            state_panel("empty", "Lô này chưa có ngày đậu quả", "Chưa thể tính lịch dự kiến kiểm tra quả.")
                            return
                        _render_lot(result, images)

                ui.timer(0.1, load_lots, once=True)


def _render_lot(result: dict[str, Any], images: Any) -> None:
    today = datetime.now(timezone.utc).date()
    cycle = result["crop_cycle"]
    image_error = isinstance(images, Exception)
    image_rows: list[dict[str, Any]] = [] if image_error else list(images or [])
    nodes = result.get("nodes") or []

    # 1. Tien do
    with panel("Tiến độ dưa lưới", "Các mốc đều là dự kiến"):
        stage = result.get("current_stage")
        envelope = result.get("stage_envelope")
        with ui.element("div").classes("sm-inline").style("margin-bottom:10px"):
            ui.label(f"Giai đoạn ghi nhận: {STAGE_LABELS.get(stage, stage) if stage else 'chưa ghi nhận'}").classes("sm-fact-v")
            if envelope:
                status_chip("ok", f"Dải chăm sóc {envelope.get('version', '')} đã duyệt")
            else:
                status_chip("none", "Chưa có dải chăm sóc đã hiệu chuẩn")
        to_early, to_late = result["days_to_early"], result["days_to_late"]
        with stats():
            stat("Ngày đậu quả", _date(result["pollination_day"]), None, "Mốc ghi trong chu kỳ")
            stat("Đã qua", result["days_since_pollination"], "ngày", "Kể từ ngày đậu quả")
            if to_early > 0:
                stat("Tới đầu cửa sổ dự kiến", to_early, "ngày", f"Dự kiến từ {_date(result['harvest_early'])}")
            elif to_late >= 0:
                stat("Cửa sổ dự kiến", "Đang trong", None, f"Còn {to_late} ngày tới cuối cửa sổ ({_date(result['harvest_late'])})")
            else:
                stat("Cửa sổ dự kiến", "Đã qua", None, f"Qua cuối cửa sổ {-to_late} ngày")
            coverage = result["coverage_pct"]
            stat("Dữ liệu đủ", coverage, "%", f"{result['complete_node_days']}/{result['possible_node_days']} ngày-node đủ mẫu",
                 level="watch" if coverage < MIN_COVERAGE * 100 else None)
        spans = stage_spans(image_rows, result["pollination_day"], result["harvest_late"])
        ui.echart(timeline_option(result, spans, today)).classes("sm-chart").style("height:190px;margin-top:10px")
        source_note(f"Dự kiến kiểm tra quả {_date(result['harvest_early'])} đến {_date(result['harvest_late'])} "
                    f"(đậu quả cộng {cycle.get('harvest_days_min')} đến {cycle.get('harvest_days_max')} ngày), "
                    f"mốc tham chiếu ngày {cycle.get('reference_day', 39)} là {_date(result['reference_day'])}. "
                    "Giai đoạn viền nét đứt là dự kiến. Người trồng xác nhận trước khi thu hoạch.")

    # 2. Dieu kien tich luy
    with panel("Điều kiện tích lũy", "Chỉ ngày đủ mẫu mới được vẽ"):
        if not result.get("chart_days"):
            state_panel("empty", "Chưa có ngày nào đủ số đo", "Biểu đồ hiện khi MongoDB có mẫu theo ngày của lô này.")
        else:
            span_text = f"Dải xanh: dự kiến kiểm tra quả. Ngày thiếu mẫu để trống."
            with ui.element("div").classes("sm-cols-2"):
                with ui.element("div"):
                    ui.label("Nhiệt tích lũy (GDD) theo ngày").classes("lab-chart-title")
                    ui.echart(daily_option(result, "cumulative_gdd_context", "°C·ngày")).classes("sm-chart").style("height:240px")
                    source_note(f"MongoDB, telemetry lịch sử theo giờ. GDD là chỉ báo ngữ cảnh, nền 10 °C. {span_text}")
                with ui.element("div"):
                    ui.label("Tổng nhiệt tích lũy theo node").classes("lab-chart-title")
                    ui.echart(gdd_total_option(result)).classes("sm-chart").style("height:240px")
                    source_note("MongoDB, cộng GDD của các ngày đủ mẫu trong khoảng từ ngày đậu quả đến hôm qua.")
                with ui.element("div"):
                    ui.label("Nhiệt độ không khí trung bình ngày").classes("lab-chart-title")
                    ui.echart(daily_option(result, "mean_air_temp_c", "°C")).classes("sm-chart").style("height:240px")
                    source_note(f"MongoDB, trung bình theo ngày UTC. {span_text}")
                with ui.element("div"):
                    ui.label("Độ khô không khí (VPD) trung bình ngày").classes("lab-chart-title")
                    ui.echart(daily_option(result, "mean_vpd_kpa", "kPa")).classes("sm-chart").style("height:240px")
                    source_note(f"MongoDB, tính từ nhiệt độ và độ ẩm theo công thức Tetens. {span_text}")

    # 3. Chat luong du lieu
    with panel("Chất lượng dữ liệu", "Mẫu có so với kỳ vọng theo ngày"):
        option = coverage_option(result)
        if option is None:
            state_panel("empty", "Chưa có ngày đóng nào để đánh giá", "Lô mới đậu quả hôm nay chưa có ngày đủ để tính.")
        else:
            with ui.element("div").classes("sm-scroll-x"):
                ui.echart(option).classes("sm-chart").style(f"height:{70 + 34 * len(nodes)}px;min-width:{max(420, 12 * len(nodes[0]['daily']) + 120)}px")
            facts([(f"Node {n['node_id']}", f"{n['complete_days']}/{n['expected_days']} ngày đủ mẫu") for n in nodes])
            first_day, last_day = nodes[0]["daily"][0]["date"], nodes[0]["daily"][-1]["date"]
            source_note(f"Phạm vi: {_date(first_day)} đến {_date(last_day)} (các ngày UTC đã đóng, không gồm hôm nay). "
                        f"Kỳ vọng {EXPECTED_SAMPLES_PER_DAY} mẫu mỗi ngày; ngày đủ khi từ {int(MIN_COVERAGE * 100)}% và không có khoảng trống dài. "
                        f"Tính từ {result['raw_count']:,} mẫu MongoDB.")

    # 4. Anh theo giai doan
    with panel("Ảnh theo giai đoạn", "Theo thứ tự giai đoạn"):
        if image_error:
            state_panel("error", "Không tải được ảnh", f"Lỗi {type(images).__name__} khi ký đường dẫn ảnh.")
        by_code = {(row.get("stage_code") or row.get("stage")): row for row in image_rows}
        with ui.element("div").classes("lab-stages"):
            for code in STAGES:
                item = by_code.get(code)
                with ui.element("div").classes("lab-stage"):
                    if item and item.get("image_url"):
                        label = STAGE_LABELS.get(code, code)
                        ui.image(item["image_url"]).props(f'ratio=1.3333 fit=cover alt="{label}"').classes("lab-shot w-full")
                    else:
                        ui.label("Chưa có ảnh").classes("lab-empty")
                    ui.label(STAGE_LABELS.get(code, code)).classes("lab-stage-k")
                    at = _as_day(item.get("stage_at")) if item else None
                    if at is None:
                        ui.label("Chưa có ngày").classes("lab-stage-d")
                    elif item.get("date_kind") == "forecast":
                        ui.label(f"Dự kiến {_date(at)}").classes("lab-stage-d")
                    else:
                        ui.label(f"Ghi nhận {_date(at)}").classes("lab-stage-d")
                    if item and item.get("image_url") and (item.get("image_captured") is False or item.get("is_synthetic") is True):
                        status_chip("sim", "ảnh minh họa")
        source_note("MongoDB crop_stage_media, ảnh lưu trên S3 và ký đường dẫn tạm. Ảnh minh họa không phải ảnh chụp tại nhà màng.")

    # 5. Trang cong khai
    with panel("Trang công khai của lô"):
        token = cycle.get("public_share_token")
        if not token:
            state_panel("empty", "Lô này chưa có mã chia sẻ", "Chưa tạo được mã QR cho khách hàng.")
        elif cycle.get("public_share_enabled") is not True:
            state_panel("empty", "Chia sẻ công khai đang tắt", "Bật chia sẻ cho lô này để dùng mã QR.")
        else:
            url = public_lot_url(token)
            try:
                qr = qr_data_uri(url)
            except Exception:
                qr = None
            with ui.element("div").classes("lab-qr"):
                if qr:
                    ui.image(qr).props('alt="Mã QR trang công khai của lô"').style("width:132px;height:132px")
                with ui.element("div").style("min-width:0;flex:1"):
                    ui.label("Khách quét mã để xem hồ sơ lô và ảnh theo giai đoạn.").classes("sm-note")
                    ext_link("Mở trang công khai", url)
                    ui.label(url).classes("sm-id")

    # 6. Cach tinh
    with ui.expansion("Cách tính và giới hạn").classes("w-full"):
        ui.label(result.get("note") or "").classes("sm-note")
        ui.label(f"MongoDB tổng hợp {result['raw_count']:,} mẫu thành {result['daily_count']:,} điểm ngày trong {result['aggregation_ms']} ms.").classes("sm-note")
        for step in result.get("pipeline") or []:
            ui.label(f"{step['stage']}: {step['purpose']}").classes("sm-note")
