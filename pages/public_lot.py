"""Public read-only crop-lot page opened from the customer QR code."""

from nicegui import ui

from service.traceability import STAGE_LABELS, customer_lot_by_token


@ui.page("/lot/{token}")
def public_lot_page(token: str):
    try:
        lot = customer_lot_by_token(token)
    except Exception:
        lot = None
    if not lot:
        with ui.column().classes("w-full min-h-screen items-center justify-center bg-slate-50 p-8"):
            ui.label("Không tìm thấy hồ sơ lô.").classes("text-2xl font-bold text-slate-800")
            ui.label("Mã QR có thể đã hết hiệu lực.").classes("text-slate-500")
        return

    ui.add_head_html("""<meta name="viewport" content="width=device-width, initial-scale=1">
    <style>body{background:#f7faf9}.lot-image{width:100%;height:280px;object-fit:cover;border-radius:14px}
    @media(max-width:640px){.lot-image{height:230px}}</style>""")
    with ui.column().classes("w-full max-w-6xl mx-auto gap-5 p-4 md:p-8"):
        with ui.row().classes("w-full items-center gap-3"):
            ui.label("🍈").classes("text-3xl")
            with ui.column().classes("gap-0"):
                ui.label("Hồ sơ dưa lưới").classes("text-2xl font-bold text-slate-900")
                ui.label(f"{lot.get('crop_name', 'Dưa lưới')} · {lot['lot_id']}").classes("text-slate-500")
        fruit_set_at = lot.get("fruit_set_at")
        if fruit_set_at:
            with ui.row().classes("w-full rounded-2xl bg-white border border-slate-200 p-4 gap-8 flex-wrap"):
                ui.label(f"Đậu quả: {fruit_set_at.strftime('%d/%m/%Y')}").classes("font-semibold text-slate-800")
                ui.label(f"Khoảng theo dõi: ngày {lot.get('harvest_days_min', 33)}–{lot.get('harvest_days_max', 45)} sau đậu quả").classes("text-slate-600")
        ui.label("Các giai đoạn phát triển").classes("text-lg font-bold text-slate-800 mt-2")
        images = lot.get("stage_images", [])
        if not images:
            ui.label("Lô chưa có ảnh theo giai đoạn.").classes("rounded-xl bg-white p-5 text-slate-500")
        else:
            with ui.element("div").style("display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;width:100%"):
                for item in images:
                    stage = item.get("stage_code", item.get("stage", ""))
                    label = item.get("stage_label") or STAGE_LABELS.get(stage, stage)
                    at = item.get("stage_at")
                    date_text = at.strftime("%d/%m/%Y") if at else "Chưa có ngày"
                    date_kind = item.get("date_kind", "recorded")
                    with ui.column().classes("rounded-2xl bg-white border border-slate-200 p-3 gap-2"):
                        ui.image(item["image_url"]).classes("lot-image")
                        ui.label(label).classes("font-bold text-slate-800")
                        ui.label(f"{'Dự kiến' if date_kind == 'forecast' else 'Ngày ghi nhận'}: {date_text}").classes("text-sm text-slate-500")
        ui.label("Thông tin lô được cập nhật theo hồ sơ mùa vụ.").classes("text-xs text-slate-400 mt-3")
