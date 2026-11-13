"""Shared SMIOT interface pieces. Styling lives in ``components/theme.py``.

Everything here renders what it is given. Nothing invents a value: a missing
timestamp stays "chưa có", a missing proof stays "đang chờ".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape as html_escape
from typing import Any, Callable, Iterable

from nicegui import ui

# Mot mui gio co dinh cho moi nhan gio hien thi (Viet Nam khong co gio mua he), khong phu thuoc may chu hay trinh duyet.
VN_TZ = timezone(timedelta(hours=7))
VN_OFFSET_MS = 7 * 3600 * 1000

# level -> css modifier. Shapes are added by CSS so colour is never the only cue.
LEVELS = {"ok", "watch", "act", "stale", "info", "sim", "none"}


def status_chip(level: str, text: str) -> ui.element:
    """Small status label. level: ok | watch | act | stale | info | sim | none."""
    level = level if level in LEVELS else "none"
    return ui.label(text).classes(f"sm-chip {'' if level == 'none' else level}".strip())


def sim_badge(text: str = "Thiết bị ảo, dữ liệu mô phỏng") -> ui.element:
    """Always-visible marker that readings/ACKs come from the simulator."""
    return status_chip("sim", text)


def page_header(title: str, lede: str | None = None) -> ui.element:
    """Title plus one plain sentence. Returns the right-hand slot for actions/chips."""
    with ui.element("div").classes("sm-head"):
        with ui.element("div").style("min-width:0"):
            ui.label(title).classes("sm-h1")
            if lede:
                ui.label(lede).classes("sm-lede")
        slot = ui.element("div").style("display:flex;align-items:center;gap:8px;flex-wrap:wrap")
    return slot


def panel(title: str | None = None, note: str | None = None) -> ui.element:
    """Bordered surface. Use as ``with panel('Tiêu đề'):``."""
    box = ui.element("section").classes("sm-panel")
    if title or note:
        with box:
            with ui.element("div").classes("sm-panel-head"):
                if title:
                    ui.label(title).classes("sm-h2")
                if note:
                    ui.label(note).classes("sm-note")
    return box


_STATE_MARK = {"loading": "◌", "empty": "○", "stale": "◐", "error": "■"}


def state_panel(kind: str, title: str, detail: str | None = None, *,
                action_label: str | None = None,
                on_action: Callable[[], Any] | None = None) -> ui.element:
    """Loading, empty, stale-data and connection-error states.

    kind: loading | empty | stale | error. Say what happened and what to do next.
    """
    kind = kind if kind in _STATE_MARK else "empty"
    with ui.element("div").classes(f"sm-state {kind}").props('role="status"') as box:
        ui.label(_STATE_MARK[kind]).classes("sm-state-mark")
        with ui.element("div").style("min-width:0;flex:1"):
            ui.label(title).classes("sm-state-title")
            if detail:
                ui.label(detail).classes("sm-state-detail")
            if action_label and on_action:
                ui.button(action_label, on_click=on_action).props("flat dense no-caps").classes(
                    "sm-btn-quiet").style("margin-top:8px")
    return box


# ── time ──────────────────────────────────────────────────────────────

def as_utc(value: Any) -> datetime | None:
    """Datetime, epoch seconds or ISO string -> aware UTC datetime, else None."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def fmt_time(value: Any, with_date: bool = True) -> str:
    """Vietnam wall-clock (UTC+7, fixed), Vietnamese order. 'chưa có' when the value is missing."""
    stamp = as_utc(value)
    if stamp is None:
        return "chưa có"
    return stamp.astimezone(VN_TZ).strftime("%H:%M:%S %d/%m" if with_date else "%H:%M:%S")


def fmt_age(value: Any, now: datetime | None = None) -> str:
    """'12 giây trước', '4 phút trước'. 'chưa có mẫu' when missing."""
    stamp = as_utc(value)
    if stamp is None:
        return "chưa có mẫu"
    seconds = max(0, int(((now or datetime.now(timezone.utc)) - stamp).total_seconds()))
    if seconds < 60:
        return f"{seconds} giây trước"
    if seconds < 3600:
        return f"{seconds // 60} phút trước"
    if seconds < 86400:
        return f"{seconds // 3600} giờ trước"
    return f"{seconds // 86400} ngày trước"


def freshness_level(value: Any, fresh_s: float, stale_s: float | None = None) -> str:
    """ok when newer than fresh_s, stale up to stale_s, act beyond, none if missing."""
    stamp = as_utc(value)
    if stamp is None:
        return "none"
    age = (datetime.now(timezone.utc) - stamp).total_seconds()
    if age <= fresh_s:
        return "ok"
    return "stale" if age <= (stale_s or fresh_s * 3) else "act"


# ── evidence chain ────────────────────────────────────────────────────

def evidence_chain(steps: Iterable[dict]) -> ui.element:
    """Horizontal chain of proof steps.

    Each step: {"label": str, "state": "done"|"waiting"|"failed"|"none", "detail": str|None}.
    A step is "done" only when its own evidence exists.
    """
    with ui.element("div").classes("sm-chain") as chain:
        for step in steps:
            state = step.get("state") if step.get("state") in {"done", "waiting", "failed", "none"} else "none"
            with ui.element("div").classes(f"sm-step {state}"):
                with ui.element("div").classes("sm-step-mark"):
                    ui.element("span").classes("sm-step-dot")
                    ui.element("span").classes("sm-step-line")
                ui.label(step.get("label", "")).classes("sm-step-label")
                if step.get("detail"):
                    ui.label(step["detail"]).classes("sm-step-detail")
    return chain


# Names used in code today. In-memory pending record (service/mqtt.py):
# pending, superseded, publish_failed, acknowledged, unacknowledged.
# action_ledger (service/incident_blackbox.py): requested, published,
# acknowledged, failed, verified.
_SENT = {"pending", "requested", "published", "pending_ack", "stop_pending_ack"}
_ACKED = {"acknowledged", "started", "running", "stopped"}
_VERIFIED = {"verified"}
_NO_ACK = {"unacknowledged", "ack_timeout"}
_NOT_SENT = {"publish_failed", "send_failed"}
_REFUSED = {"rejected", "failed"}


def command_steps(status: str | None, *, sent_at: Any = None, acked_at: Any = None,
                  verified_at: Any = None, verify_hint: str | None = None,
                  reason: str | None = None) -> list[dict]:
    """Map a command status to the three proof steps.

    Sent, ACK and verified are different facts. ACK never implies verified;
    ``verified`` needs its own readback/ledger state.
    """
    status = str(status or "").strip().lower()
    sent = {"label": "Đã gửi lệnh", "state": "none", "detail": None}
    ack = {"label": "Thiết bị đã ACK", "state": "none", "detail": None}
    ver = {"label": "Kết quả đã xác minh", "state": "none", "detail": None}
    if not status:
        sent["detail"] = "Chưa có lệnh nào"
        return [sent, ack, ver]
    if status in _NOT_SENT:
        sent.update(state="failed", detail=reason or "Không gửi được lệnh tới broker")
        return [sent, ack, ver]
    sent.update(state="done", detail=fmt_time(sent_at) if sent_at else None)
    if status in _SENT:
        ack.update(state="waiting", detail="Đang chờ thiết bị phản hồi")
    elif status in _NO_ACK:
        ack.update(state="failed", detail=reason or "Hết thời gian chờ, thiết bị không phản hồi")
    elif status in _REFUSED:
        ack.update(state="failed", detail=reason or "Thiết bị từ chối hoặc lệnh thất bại")
    elif status == "superseded":
        ack.update(state="none", detail="Bị thay bằng lệnh mới hơn")
    elif status in _ACKED or status in _VERIFIED:
        ack.update(state="done", detail=fmt_time(acked_at) if acked_at else None)
        if status in _VERIFIED:
            ver.update(state="done", detail=fmt_time(verified_at) if verified_at else None)
        else:
            ver.update(state="waiting", detail=verify_hint or "Chưa có số đo xác nhận sau lệnh")
    else:
        ack.update(state="none", detail=f"Trạng thái: {status}")
    return [sent, ack, ver]


def command_chain(status: str | None, **kwargs: Any) -> ui.element:
    """Render the sent → ACK → verified chain for one command."""
    return evidence_chain(command_steps(status, **kwargs))


def facts(items: Iterable[tuple[str, Any]]) -> ui.element:
    """Grid of label/value pairs. Missing values render as an em dash."""
    with ui.element("div").classes("sm-facts") as grid:
        for key, value in items:
            with ui.element("div"):
                ui.label(key).classes("sm-fact-k")
                ui.label("—" if value in (None, "") else str(value)).classes("sm-fact-v")
    return grid


def ext_link(text: str, url: str) -> ui.element:
    """Link that opens an outside tool (Datadog) in a new tab."""
    return ui.link(text, url, new_tab=True).classes("sm-link sm-ext")


async def confirm(title: str, detail: str, confirm_label: str, *, danger: bool = False) -> bool:
    """Confirmation step for risky actions. Returns True only on explicit confirm."""
    with ui.dialog() as dialog, ui.card().style("max-width:440px;padding:20px;border-radius:14px;gap:10px"):
        ui.label(title).classes("sm-h2")
        ui.label(detail).classes("sm-state-detail")
        with ui.row().classes("w-full justify-end").style("gap:8px;margin-top:8px"):
            ui.button("Hủy", on_click=lambda: dialog.submit(False)).props("flat no-caps").classes("sm-btn-quiet")
            ui.button(confirm_label, on_click=lambda: dialog.submit(True)).props("unelevated no-caps").classes(
                "sm-btn-danger" if danger else "sm-btn")
    return bool(await dialog)


# ── numbers ───────────────────────────────────────────────────────────

def stat(label: str, value: Any, unit: str | None = None, meta: str | None = None,
         level: str | None = None) -> ui.element:
    """One measured number. ``value=None`` renders an em dash, never a default.

    meta: when and where it came from, e.g. "12 giây trước, node 1 (thiết bị ảo)".
    Wrap several in ``with stats():``.
    """
    missing = value is None or value == ""
    cls = "none" if missing else (level if level in {"watch", "act"} else "")
    with ui.element("div").classes(f"sm-stat {cls}".strip()) as tile:
        ui.label(label).classes("sm-stat-k")
        shown = "—" if missing else html_escape(str(value))
        suffix = f"<small>{unit}</small>" if unit and not missing else ""
        # Gia tri chu (khong phai so) cho xuong dong, khong tran the o man hinh hep.
        text_cls = " text" if (not missing and len(str(value)) > 14) else ""
        ui.html(f'<div class="sm-stat-v{text_cls}">{shown}{suffix}</div>')
        ui.label(meta if meta else ("Chưa có dữ liệu" if missing else "")).classes("sm-stat-m")
    return tile


def stats() -> ui.element:
    """Joined strip of ``stat`` tiles."""
    return ui.element("div").classes("sm-stats")


def fmt_num(value: Any, digits: int = 1) -> str | None:
    """Vietnamese decimal comma. None for anything that is not a real number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return f"{value:.{digits}f}".replace(".", ",")


# ── greenhouse bay ────────────────────────────────────────────────────

LEVEL_WORD = {"ok": "● Bình thường", "watch": "▲ Cần theo dõi", "act": "■ Cần xử lý", "none": "○ Chưa đủ dữ liệu"}

def greenhouse_bay(name: str, level: str, cause: str | None = None,
                   on_click: Callable[[], Any] | None = None, age: str | None = None) -> ui.element:
    """One greenhouse as a cell on the fleet board.

    level: ok | watch | act | none. cause: the single main reason, from real data.
    age: when its newest sample arrived, e.g. fmt_age(ts). Use inside ``with bays():``.
    Keyboard-reachable (it is a <button>).
    """
    level = level if level in LEVEL_WORD else "none"
    label = f"{name}: {LEVEL_WORD[level][2:]}" + (f". {cause}" if cause else "")
    with ui.element("button").classes(f"sm-bay {level}").props(f'type="button" aria-label="{label}"') as bay:
        ui.label(name).classes("sm-bay-name")
        ui.label(LEVEL_WORD[level]).classes("sm-bay-state")
        if cause:
            ui.label(cause).classes("sm-bay-cause")
        if age:
            ui.label(age).classes("sm-bay-age")
    if on_click:
        bay.on("click", lambda _e: on_click())
    return bay

def bays() -> ui.element:
    """Fleet board: 10 cells across on desktop, 5 x 2 below 1180px, 2 columns on phones."""
    return ui.element("div").classes("sm-bays")


# ── case file ─────────────────────────────────────────────────────────

def file_step(number: int, title: str, *, has_evidence: bool, note: str | None = None) -> ui.element:
    """Numbered section of an incident file. Returns the body to fill with ``with``.

    has_evidence=False greys the number: the step exists, its proof does not.
    """
    with ui.element("div").classes(f"sm-file-step {'done' if has_evidence else 'missing'}"):
        ui.label(str(number)).classes("sm-file-no")
        with ui.element("div").classes("sm-file-body") as body:
            with ui.element("div").classes("sm-inline").style("margin-bottom:8px;min-height:34px"):
                ui.label(title).classes("sm-h2")
                if note:
                    ui.label(note).classes("sm-note")
    return body


def phase_block(number: int, title: str, owner: str = "datadog", *, note: str | None = None,
                has_evidence: bool = True) -> ui.element:
    """Mot pha cua ho so (Phat hien / Dieu tra / Phan ung). owner: datadog | mongo | mixed.

    Vien trai theo vai: tim = Datadog, xanh = MongoDB. Tra ve phan than de dien bang ``with``.
    """
    owner = owner if owner in {"datadog", "mongo", "mixed"} else "mongo"
    with ui.element("section").classes(f"sm-phase {owner}"):
        with ui.element("div").classes("sm-phase-head"):
            ui.label(str(number)).classes("sm-phase-no" + ("" if has_evidence else " missing"))
            ui.label(title).classes("sm-h2")
            if note:
                ui.label(note).classes("sm-phase-src")
        body = ui.element("div").classes("sm-phase-body")
    return body


# Thong diep trung thuc cho moi loi doc Datadog: reason -> (tieu de, chi tiet, nhan nut, kieu state_panel).
DD_STATES: dict[str, tuple[str, str, str | None, str]] = {
    "keys_missing": ("Máy chủ này chưa cấu hình khóa đọc Datadog",
                     "Số liệu Datadog không hiển thị trong ứng dụng. Bạn vẫn mở được trên Datadog.",
                     "Mở trên Datadog", "stale"),
    "monitor_not_found": ("Monitor không có trong tổ chức Datadog đang dùng",
                          "ID monitor của hồ sơ này thuộc tổ chức Datadog cũ. Hồ sơ giữ nguyên, chỉ không đọc lại được.",
                          "Monitor hiện hành của ca", "stale"),
    "http_403": ("Khóa đọc Datadog không đủ quyền cho mục này",
                 "Các mục khác vẫn đọc bình thường.", "Mở trên Datadog", "stale"),
    "timeout": ("Chưa đọc được Datadog (hết thời gian chờ)",
                "Thử lại sau 15 giây.", "Thử lại", "error"),
    "network": ("Chưa đọc được Datadog (lỗi mạng)", "Thử lại sau 15 giây.", "Thử lại", "error"),
    "no_points": ("Datadog không có điểm metric trong khung giờ này",
                  "Mở Metrics Explorer đúng khung giờ để kiểm tra.", "Mở Metrics Explorer", "empty"),
    "not_recorded": ("Hồ sơ này chưa ghi monitor, workflow hoặc trace_id",
                     "Không có gì để đọc từ Datadog cho hồ sơ này.", None, "empty"),
}


def dd_reason(reason: Any) -> str:
    """Chuan hoa reason cua datadog_reader ve khoa trong DD_STATES."""
    word = str(reason or "").strip()
    if word in DD_STATES:
        return word
    if word in {"monitor_id_missing", "id_missing"}:
        return "not_recorded"
    if word.startswith("http_"):
        return "http_403" if word in {"http_401", "http_403"} else "network"
    if word in {"TimeoutError", "timeout"} or "Timeout" in word or "timed out" in word:
        return "timeout"
    return "network"


def dd_state(reason: Any) -> tuple[str, str, str | None]:
    """(tieu de, chi tiet, nhan nut) cho mot reason loi/rong cua Datadog."""
    title, detail, action, _kind = DD_STATES[dd_reason(reason)]
    return title, detail, action


def dd_state_panel(reason: Any, *, on_action: Callable[[], Any] | None = None,
                   action_label: str | None = None) -> ui.element:
    """state_panel theo bang thong diep Datadog. Nut chi hien khi co ham xu ly."""
    title, detail, label, kind = DD_STATES[dd_reason(reason)]
    return state_panel(kind, title, detail, action_label=(action_label or label) if on_action else None,
                       on_action=on_action)


# ── charts ────────────────────────────────────────────────────────────

def echart_base(**overrides: Any) -> dict:
    """Shared echarts look: fonts, quiet grid, series palette. Merge your series in."""
    from components.theme import CHART
    axis = {
        "axisLine": {"lineStyle": {"color": CHART["grid"]}},
        "axisTick": {"show": False},
        "axisLabel": {"color": CHART["muted"], "fontSize": 11},
        "splitLine": {"lineStyle": {"color": CHART["grid"]}},
    }
    base = {
        "animation": False,
        "color": list(CHART["series"]),
        "textStyle": {"fontFamily": CHART["font"], "color": CHART["ink"]},
        "grid": {"left": 44, "right": 16, "top": 28, "bottom": 30, "containLabel": False},
        "tooltip": {"trigger": "axis", "backgroundColor": "#fff", "borderColor": CHART["grid"],
                    "textStyle": {"color": CHART["ink"], "fontSize": 12}},
        "legend": {"top": 0, "right": 0, "icon": "roundRect", "itemWidth": 10, "itemHeight": 10,
                   "textStyle": {"color": CHART["muted"], "fontSize": 12}},
        "xAxis": dict(axis), "yAxis": dict(axis),
    }
    base.update(overrides)
    return base


# ── farm switcher and time range ──────────────────────────────────────

def farm_tabs(farms: Iterable[tuple[str, str, str]], active: str | None,
              on_select: Callable[[str | None], Any], all_label: str | None = "Tất cả") -> ui.element:
    """One tab per greenhouse with its status mark; first tab is the fleet view.

    farms: (farm_key, label, level) with level ok | watch | act | none.
    active: farm_key, or None for the fleet view. on_select gets farm_key or None.
    """
    with ui.element("div").classes("sm-farmtabs").props('role="tablist" aria-label="Nhà màng"') as bar:
        if all_label:
            tab = ui.element("button").classes(f"sm-farmtab all {'active' if active is None else ''}").props(
                f'type="button" role="tab" aria-selected="{"true" if active is None else "false"}"')
            with tab:
                ui.label(all_label)
            tab.on("click", lambda _e: on_select(None))
        for key, label, level in farms:
            level = level if level in {"ok", "watch", "act", "none"} else "none"
            tab = ui.element("button").classes(
                f"sm-farmtab {level} {'active' if key == active else ''}").props(
                f'type="button" role="tab" aria-selected="{"true" if key == active else "false"}"')
            with tab:
                ui.label(label)
            tab.on("click", lambda _e, k=key: on_select(k))
    return bar


def range_pills(options: Iterable[tuple[str, Any]], active: Any, on_select: Callable[[Any], Any]) -> ui.element:
    """Time-range switch for charts, e.g. [("1 giờ", 1), ("6 giờ", 6), ("24 giờ", 24)]."""
    with ui.element("div").classes("sm-pills") as box:
        for label, value in options:
            pill = ui.element("button").classes(f"sm-pill {'active' if value == active else ''}").props('type="button"')
            with pill:
                ui.label(label)
            pill.on("click", lambda _e, v=value: on_select(v))
    return box


def source_note(text: str) -> ui.element:
    """One line under a chart: where the data came from and when it was read."""
    return ui.label(text).classes("sm-source")
