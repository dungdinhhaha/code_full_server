"""Public read-only crop-lot page opened from the customer QR code.

No login, no sidebar. Dates shown here are planned (dự kiến) or as recorded in the
seasonal file; the page makes no claim about quality or yield.
"""

import logging
from datetime import date, datetime, timedelta

from nicegui import ui

from components.theme import THEME_CSS, THEME_FONTS
from components.ui_kit import page_header, panel, sim_badge, stat, stats, state_panel
from service.farm_registry import FARM_LABELS
from service.traceability import STAGE_LABELS, customer_lot_by_token

LOGGER = logging.getLogger(__name__)

LOT_CSS = """
html,body{overflow:auto!important}
.lot-wrap{width:100%;max-width:560px;margin:0 auto;padding:16px;box-sizing:border-box;display:flex;flex-direction:column;gap:12px}
.lot-wrap .sm-panel{min-width:0}
.lot-strip{display:grid;grid-template-columns:minmax(0,1fr);gap:12px}
@media (min-width:480px){.lot-strip{grid-template-columns:repeat(2,minmax(0,1fr))}}
.lot-stage{display:flex;flex-direction:column;gap:6px;min-width:0}
.lot-img{width:100%;height:180px;object-fit:cover;border-radius:var(--sm-r-s);border:1px solid var(--sm-net-soft);display:block}
.lot-img-empty{width:100%;height:180px;box-sizing:border-box;border-radius:var(--sm-r-s);border:1px dashed var(--sm-net);display:flex;align-items:center;justify-content:center;font-size:13px;color:var(--sm-ink-3)}
.lot-stage-name{font-size:14px;font-weight:600;color:var(--sm-ink)}
.lot-stage-date{font-size:12px;color:var(--sm-ink-3)}
.lot-foot{font-size:12px;color:var(--sm-ink-3);margin:4px 0 0}
"""


def _fmt_date(value):
    """dd/mm/yyyy for a real date, None otherwise."""
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    return None


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _harvest_window(fruit, days_min, days_max):
    """Planned inspection window from the fruit-set date. (None, None) when any input is missing."""
    lo, hi = _int(days_min), _int(days_max)
    if not isinstance(fruit, (date, datetime)) or lo is None or hi is None:
        return None, None
    return _fmt_date(fruit + timedelta(days=lo)), _fmt_date(fruit + timedelta(days=hi))


def _stage_card(item):
    code = str(item.get("stage_code") or item.get("stage") or "")
    label = item.get("stage_label") or STAGE_LABELS.get(code) or code or "Giai đoạn"
    at = _fmt_date(item.get("stage_at"))
    if item.get("date_kind") == "forecast":
        date_text = f"Dự kiến: {at}" if at else "Chưa có ngày dự kiến"
    else:
        date_text = f"Ngày ghi nhận: {at}" if at else "Chưa có ngày ghi nhận"
    with ui.element("div").classes("lot-stage"):
        if item.get("image_url"):
            ui.image(item["image_url"]).classes("lot-img")
        else:
            ui.label("Chưa có ảnh").classes("lot-img-empty")
        ui.label(label).classes("lot-stage-name")
        ui.label(date_text).classes("lot-stage-date")


@ui.page("/lot/{token}")
def public_lot_page(token: str):
    try:
        lot = customer_lot_by_token(token)
    except Exception:
        LOGGER.warning("public lot lookup failed", exc_info=True)
        lot = None

    ui.add_head_html(
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<style>{THEME_FONTS}{THEME_CSS}{LOT_CSS}</style>"
    )

    with ui.element("main").classes("lot-wrap"):
        if not lot:
            state_panel("error", "Không tìm thấy lô này", "Kiểm tra lại mã QR.")
            return

        farm = FARM_LABELS.get(str(lot.get("farm_key", "")), "")
        crop = str(lot.get("crop_name") or "Dưa lưới")
        page_header(f"Lô {lot.get('lot_id', '')}", " · ".join(x for x in (crop, farm) if x))

        fruit = lot.get("fruit_set_at")
        fruit_text = _fmt_date(fruit)
        start_text, end_text = _harvest_window(fruit, lot.get("harvest_days_min"), lot.get("harvest_days_max"))
        with stats():
            stat("Ngày đậu quả", fruit_text, meta="Theo hồ sơ mùa vụ")
            stat("Dự kiến kiểm tra từ", start_text,
                 meta="Ngày dự kiến" if start_text else "Chưa có ngày dự kiến")
            stat("Dự kiến kiểm tra đến", end_text,
                 meta="Ngày dự kiến" if end_text else "Chưa có ngày dự kiến")

        with panel("Các giai đoạn phát triển"):
            images = lot.get("stage_images") or []
            if not images:
                ui.label("Chưa có ảnh").classes("lot-img-empty")
            else:
                with ui.element("div").classes("lot-strip"):
                    for item in images:
                        _stage_card(item)

        if lot.get("simulated") is True:
            sim_badge("Dữ liệu mô phỏng")

        ui.label("Thông tin lô được cập nhật theo hồ sơ mùa vụ. Các ngày kiểm tra là dự kiến.").classes("lot-foot")
