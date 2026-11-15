"""pages/incident.py - Hop so su co: danh sach /incident, ho so /incident/{id} (chi admin).

Chia vai: Datadog = dieu tra (monitor, workflow, log, trace); MongoDB = ho so, so do, tac dong;
app = dieu huong. Chi doc qua service.incident_blackbox (list_incidents, build_incident_timeline).
Ho so chi dung du lieu cua DUNG incident do. Gia tri lay tu cau hinh ca (CASES) phai ghi ro
"theo cau hinh ca"; moi link Datadog chi hien khi co ID that.
"""

from __future__ import annotations

import html
import json
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from nicegui import app, run, ui

from components.theme import CHART
from components.ui_kit import (
    VN_OFFSET_MS, VN_TZ, command_chain, dd_reason, dd_state, dd_state_panel, echart_base, evidence_chain,
    ext_link, facts, fmt_age, fmt_num, fmt_time, page_header, panel, phase_block, sim_badge, source_note,
    stat, state_panel, stats, status_chip,
)
from pages.home import CUSTOM_CSS, global_topbar, sidebar
from pages.login import check_login
from service.farm_registry import FARM_KEYS, FARM_LABELS
from service.incident_blackbox import (
    ACTIVE_STATUSES, ALL_STATUSES, CASES, UNKNOWN, build_incident_timeline, case_for_kind,
    latest_by_case, list_incidents,
)
from service.datadog_reader import read_incident_snapshot, read_monitor_overview

DD_BASE = "https://app.datadoghq.com"
# Current US1 dashboard in the active Datadog organization. nkc-685-vw8 is a
# historical ID from the previous organization (404): never link to it.
DD_DASHBOARD = f"{DD_BASE}/dashboard/rzf-su8-zgf/smiot--10-farm-portfolio"
MAX_EVENT_ROWS = 500
MAX_LIST_ROWS = 200
MAX_GAP_MINUTES = 1440  # chan so phut cua mot khoang thieu mau khi ve bieu do
REFRESH_LIST_SECONDS = 15
REFRESH_DETAIL_SECONDS = 20

SRC_MONGO = "MongoDB"
SRC_DATADOG = "Datadog →"

# Su kien trong nhat ky MongoDB ma nguon thuc su la Datadog (mốc phat hien theo monitor).
DATADOG_SOURCED_KINDS = frozenset({"detected"})

QUALITY_KEYS = ("valid", "abnormal", "missing")
QUALITY_LABELS = {"valid": "Mẫu hợp lệ", "abnormal": "Mẫu bất thường", "missing": "Phút thiếu mẫu"}
QUALITY_COLORS = {"valid": CHART["series"][0], "abnormal": CHART["level"]["act"], "missing": CHART["level"]["none"]}

KIND_NAMES = {
    "soil_humidity_flatline": "Cảm biến độ ẩm đứng số",
    "false_offline": "Báo offline sai",
    "service_down": "Dịch vụ ứng dụng dừng",
    "soil_humidity_spike": "Độ ẩm đất tăng đột biến",
    "soil_humidity_out_of_range": "Độ ẩm đất ngoài khoảng đo",
    "water_overrun": "Lưu lượng nước vượt giới hạn",
    "ventilation_stuck": "Quạt thông gió không khớp lệnh",
    "pipe_leak": "Nghi rò ống nước",
    "scenario_event": "Tình huống diễn tập",
    "dependency_degraded": "MongoDB/MQTT suy giảm",
    "detector_heartbeat_missing": "Bộ phát hiện mất heartbeat",
    "plc_safety_trip": "PLC ảo ngắt an toàn",
    "actuator_command_unacknowledged": "Lệnh thiết bị chưa có ACK",
    "ai_provider_failure": "Nhà cung cấp AI lỗi",
}


def kind_name(kind: str | None) -> str:
    return KIND_NAMES.get(str(kind or ""), str(kind) if kind else UNKNOWN)


SAFETY_RULE_BY_KIND = {
    "dependency_degraded": "Chỉ xử lý dependency đã xác định lỗi; nếu chưa rõ thì không làm gì thêm.",
    "detector_heartbeat_missing": "Báo và chuyển cấp; không nhận detector đã cô lập khi cùng tiến trình ứng dụng.",
    "plc_safety_trip": "PLC ảo giữ đầu ra an toàn; cloud chỉ điều tra, không thay interlock cục bộ.",
    "actuator_command_unacknowledged": "Không gửi lại mù; giữ đầu ra OFF và chờ ACK đúng command và farm.",
    "ai_provider_failure": "Chuyển HOLD hoặc phương án xác định; không dùng quyết định AI chưa xác minh.",
    "soil_humidity_flatline": "Đề xuất tưới bị chặn, giữ HOLD cho đến khi dữ liệu đáng tin trở lại.",
    "false_offline": "Từ chối restart vì dữ liệu vẫn vào MongoDB, không có lý do restart.",
    "service_down": "Chỉ khởi động app sau khi kiểm tra MongoDB và MQTT đã khỏe.",
    "soil_humidity_spike": "Không tự tưới theo một mẫu tăng vọt; giữ mẫu để kiểm tra với lịch sử và cảm biến lân cận.",
    "soil_humidity_out_of_range": "Không dùng số đo ngoài khoảng vật lý để điều khiển tưới.",
    "water_overrun": "PLC ảo dừng bơm và đóng van khi chạm giới hạn bảo vệ.",
    "ventilation_stuck": "Ghi nhận lệnh và phản hồi quạt lệch nhau; chưa tự khởi động lại thiết bị.",
    "pipe_leak": "PLC ảo ngắt bơm và đóng van khi áp suất thấp đi kèm lưu lượng cao.",
}

INC_CSS = """
.inc-wrap { max-width:1180px; }
.inc-filters { display:flex; flex-wrap:wrap; gap:10px 14px; align-items:flex-end; }
.inc-filters .q-field { min-width:200px; }
.inc-cases { display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:1px;
  background:var(--sm-net-soft); border:1px solid var(--sm-net-soft); border-radius:var(--sm-r-l); overflow:hidden; }
.inc-case { background:var(--sm-surface); padding:10px 12px; min-width:0; display:flex; flex-direction:column; gap:4px; }
.inc-case.on { background:var(--sm-vine-tint); box-shadow:inset 3px 0 0 var(--sm-vine); }
.inc-case-btn { appearance:none; border:0; background:transparent; padding:0; text-align:left; font:inherit;
  cursor:pointer; color:var(--sm-ink); font-weight:600; font-size:13px; line-height:1.35; }
.inc-case-sum { font-size:12px; color:var(--sm-ink-2); line-height:1.4; }
.inc-case-meta { font-size:12px; color:var(--sm-ink-3); }
.inc-case-links { display:flex; flex-wrap:wrap; gap:4px 12px; margin-top:2px; }
.inc-links { display:flex; flex-wrap:wrap; gap:6px 16px; }
.inc-block-title { font-size:12px; font-weight:600; color:var(--sm-ink-3); margin:14px 0 6px; }
.inc-cmd { padding:10px 0; border-top:1px solid var(--sm-net-soft); }
.inc-cmd:first-of-type { border-top:0; padding-top:0; }
.inc-cmd-head { display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 10px; margin-bottom:6px; }
.inc-qtable { width:100%; }
.inc-active { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:8px; }
.inc-active-card { background:var(--sm-surface); border:1px solid var(--sm-net-soft); border-left:3px solid var(--sm-act);
  border-radius:var(--sm-r-s); padding:10px 12px; display:flex; flex-direction:column; gap:6px; min-width:0; }
.inc-two { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; width:100%; }
.inc-card { background:var(--sm-sunken); border-radius:var(--sm-r-m); padding:10px 12px; min-width:0; }
.inc-mongo { border-left:3px solid var(--sm-vine); padding-left:12px; display:flex; flex-direction:column; gap:10px; }
.sm-stat-m { overflow-wrap:anywhere; }
@media (max-width:900px) { .inc-two { grid-template-columns:minmax(0,1fr); } }
@media (max-width:900px) { .inc-qtable { font-size:12px; display:block; overflow-x:auto; } }
@media (max-width:768px) {
  .inc-wrap { max-width:100%; }
  .inc-active { grid-template-columns:1fr; }
  .dd-card, .dd-case-btn { min-height:44px; }
  .inc-filters .q-field { min-width:100%; }
  .inc-case-btn, .sm-link { display:inline-flex; align-items:center; min-height:40px; }
  .inc-cases { grid-template-columns:1fr; }
}
@media (max-width:900px) { .inc-qtable { font-size:12px; } }
"""


def _fmt(value: Any) -> str:
    """Moc gio theo gio Viet Nam (co dinh UTC+7), cung kieu voi fmt_time."""
    if isinstance(value, datetime):
        return _as_utc(value).astimezone(VN_TZ).strftime("%Y-%m-%d %H:%M:%S")
    if value is None or value == "":
        return "—"
    return str(value)


def _short(value: str, keep: int = 10) -> str:
    return value if len(value) <= keep * 2 else f"{value[:keep]}…{value[-4:]}"


def _is_admin() -> bool:
    role = app.storage.user.get("role", "")
    permissions = app.storage.user.get("permissions", [])
    return role == "admin" or "manage_users" in permissions


def _guard() -> bool:
    if not check_login():
        return False
    if not _is_admin():
        ui.notify("Bạn không có quyền truy cập trang này", color="negative")
        ui.navigate.to("/")
        return False
    return True


def _as_utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


# ---------------------------------------------------------------------------
# Ham thuan: tom tat, link Datadog
# ---------------------------------------------------------------------------
def _node_phrase(node_id: Any) -> str:
    return f" Node {node_id}" if node_id is not None else ""


def incident_headline(kind: str | None, node_id: Any = None,
                      scenario_title: str | None = None) -> str:
    """Mot cau tom tat cho nguoi khong chuyen."""
    if kind == "soil_humidity_flatline":
        return f"Cảm biến độ ẩm{_node_phrase(node_id)} báo một giá trị đứng yên."
    if kind == "false_offline":
        return "Giao diện báo thiết bị offline sai trong khi dữ liệu vẫn vào MongoDB."
    if kind == "service_down":
        return "Dịch vụ smiot.service đã dừng."
    if kind == "soil_humidity_spike":
        return f"Cảm biến độ ẩm{_node_phrase(node_id)} có mẫu tăng đột biến."
    if kind == "soil_humidity_out_of_range":
        return f"Cảm biến độ ẩm{_node_phrase(node_id)} gửi giá trị ngoài khoảng đo."
    if kind == "water_overrun":
        return "Lưu lượng tưới vượt giới hạn an toàn của PLC ảo."
    if kind == "ventilation_stuck":
        return "Phản hồi quạt thông gió không khớp với lệnh điều khiển."
    if kind == "pipe_leak":
        return "Áp suất thấp cùng lưu lượng cao kích hoạt ngắt an toàn của PLC ảo."
    if kind == "dependency_degraded":
        return "MongoDB hoặc MQTT phản hồi kém; phải phân loại dependency lỗi trước khi xử lý."
    if kind == "detector_heartbeat_missing":
        return "Bộ phát hiện không còn gửi heartbeat; cần tách lỗi detector với thiếu dữ liệu đầu vào."
    if kind == "plc_safety_trip":
        return "PLC ảo kích hoạt ngắt an toàn; cần ACK, đầu ra an toàn và sổ lệnh khớp nhau."
    if kind == "actuator_command_unacknowledged":
        return "Lệnh điều khiển chưa nhận ACK trước hạn; không gửi lại mù."
    if kind == "ai_provider_failure":
        return "Nhà cung cấp AI lỗi hoặc chậm; dùng HOLD hoặc phương án an toàn xác định."
    if kind == "scenario_event":
        title = str(scenario_title or "tình huống vận hành").strip()
        return f"Diễn tập mô phỏng: {title}."
    return UNKNOWN


def incident_summary(kind: str | None, node_id: Any = None,
                     scenario_title: str | None = None) -> str:
    """Tom tat 1-2 cau theo kind cho dau trang trang chi tiet."""
    head = incident_headline(kind, node_id, scenario_title)
    if kind == "soil_humidity_flatline":
        return f"{head} Hệ thống đã giữ chế độ an toàn, không tưới, cho đến khi dữ liệu trở lại bình thường."
    if kind == "false_offline":
        return f"{head} Hệ thống từ chối restart không cần thiết vì dữ liệu vẫn đang được ghi nhận."
    if kind == "service_down":
        return f"{head} Hệ thống chỉ khởi động lại sau khi kiểm tra an toàn."
    if kind in {"water_overrun", "pipe_leak"}:
        return f"{head} ACK của PLC ảo chứng minh bơm đã dừng và van đã đóng; sự cố vẫn cần xác minh trước khi đóng."
    if kind in {"soil_humidity_spike", "soil_humidity_out_of_range", "ventilation_stuck"}:
        return f"{head} Đây là sự cố mô phỏng; chưa có bằng chứng phục hồi cho đến khi nhận được số đo và phản hồi thiết bị bình thường."
    if kind in {"dependency_degraded", "detector_heartbeat_missing", "plc_safety_trip",
                "actuator_command_unacknowledged", "ai_provider_failure"}:
        return f"{head} Chỉ coi là phục hồi khi hồ sơ này có bằng chứng kiểm tra sau xử lý."
    if kind == "scenario_event":
        return f"{head} Tín hiệu này được tạo trong bộ mô phỏng; phần nguyên nhân vật lý hoặc hạ tầng thật chưa được khẳng định."
    return "Loại sự cố này chưa có mô tả trên trang; xem chi tiết trong Datadog."


def _case_config(inc: dict[str, Any]) -> dict[str, Any]:
    return CASES.get(case_for_kind(inc.get("kind")), {})


def _monitor_id(inc: dict[str, Any], config_fallback: bool = True) -> str | None:
    """Monitor cua chinh document; config_fallback=True them monitor theo cau hinh ca (chi cho link chung)."""
    monitor = inc.get("monitor_id") or (_case_config(inc).get("monitor_id") if config_fallback else None)
    return str(monitor) if monitor else None


def _workflow_id(inc: dict[str, Any], config_fallback: bool = True) -> str | None:
    workflow = inc.get("workflow_id") or (_case_config(inc).get("workflow_id") if config_fallback else None)
    return str(workflow) if workflow else None


def _monitor_links(inc: dict[str, Any], config_fallback: bool = True) -> list[tuple[str, str, str]]:
    monitor = _monitor_id(inc, config_fallback)
    return [(f"Monitor {monitor}", f"{DD_BASE}/monitors/{quote(monitor)}", monitor)] if monitor else []


def _execution_links(inc: dict[str, Any], config_fallback: bool = True) -> list[tuple[str, str, str]]:
    workflow, execution = _workflow_id(inc, config_fallback), inc.get("last_workflow_execution_id")
    if not (workflow and execution):
        return []
    return [(f"Execution {_short(str(execution), 8)}",
             f"{DD_BASE}/workflow/{quote(workflow)}?instance={quote(str(execution))}", str(execution))]


def _workflow_links(inc: dict[str, Any], config_fallback: bool = True) -> list[tuple[str, str, str]]:
    workflow = _workflow_id(inc, config_fallback)
    if not workflow:
        return []
    return [(f"Workflow {_short(workflow, 8)}", f"{DD_BASE}/workflow/{quote(workflow)}", workflow),
            *_execution_links(inc, config_fallback)]


def _logs_link(inc: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Tim log theo ma su co, kem khung gio cua su co khi co.

    service.logger.log_incident_event ghi ma su co o dang JSON long
    ({"incident": {"id": ...}}); Agent facet thanh thuoc tinh @incident.id
    thay vi giu nguyen van ban day du de tim kiem toan van khop (ma co dau
    gach ngang khong khop tim kiem toan van co ngoac kep). Dung dung thuoc tinh.
    """
    inc_id = str(inc.get("incident_id") or inc.get("_id") or "")
    if not inc_id:
        return []
    q = f'@incident.id:"{inc_id}"'
    url = f"{DD_BASE}/logs?query={quote(q)}"
    window = metric_window(inc)
    if window:
        url += f"&from_ts={_epoch_ms(window[0])}&to_ts={_epoch_ms(window[1])}&live=false"
    return [("Logs của sự cố", url, q)]


def _trace_links(inc: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Tat ca trace cua su co (theo thu tu trong du lieu). Chi dung trong expansion 'Tat ca trace'."""
    ev = inc.get("evidence") or {}
    traces = [t for t in (ev.get("trace_ids") or []) if t]
    return [(f"Trace {_short(str(t), 6)}", f"{DD_BASE}/apm/trace/{quote(str(t))}", str(t)) for t in traces]


def _first_trace_link(inc: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Chi trace DAU TIEN, nhan ngan 'Trace'. Dung o hang nut dau trang va cau 3."""
    traces = _trace_links(inc)
    if not traces:
        return []
    _, url, tip = traces[0]
    return [("Trace", url, tip)]


def _link_groups(incident: dict[str, Any] | None) -> dict[str, list[tuple[str, str, str]]]:
    """Nhom link theo muc dich dieu tra. Moi muc: (nhan hien thi, url day du, tooltip).

    Khong con duoc render (cac link da nam o hang nut dau trang); giu lai de tests/test_incident_cases.py
    van import duoc. Chi them link khi du lieu co gia tri; khong dung link du doan.
    """
    inc = incident or {}
    groups: dict[str, list[tuple[str, str, str]]] = {
        "Phát hiện": _monitor_links(inc),
        "Hành động": _workflow_links(inc),
        "Nhật ký & điều tra": _logs_link(inc),
        "Dấu vết (trace)": _trace_links(inc),
        "Hạ tầng": [("Dashboard SMIOT", DD_DASHBOARD, "Dashboard vận hành")],
    }
    return {k: v for k, v in groups.items() if v}


METRIC_WINDOW_PAD = timedelta(minutes=15)

# Metric Datadog theo loai su co: (ten metric, kieu gop, mo ta ngan).
# Các liên kết vẫn mở trực tiếp Datadog; snapshot bên dưới đọc read-only từ API.
METRICS_BY_KIND: dict[str, list[tuple[str, str, str]]] = {
    "false_offline": [
        ("smiot.telemetry.status_mismatch", "max:smiot.telemetry.status_mismatch{*} by {farm,node}",
         "Giao diện lệch với trạng thái tính từ MongoDB"),
        ("smiot.telemetry.sample_age_seconds", "max:smiot.telemetry.sample_age_seconds{*}",
         "Tuổi mẫu mới nhất (đối chứng: mẫu vẫn mới)"),
    ],
    "soil_humidity_flatline": [
        ("smiot.telemetry.sensor_flatline", "max:smiot.telemetry.sensor_flatline{*} by {farm,node}",
         "Số đo độ ẩm đứng yên"),
        ("smiot.telemetry.sample_age_seconds", "max:smiot.telemetry.sample_age_seconds{*}", "Tuổi mẫu mới nhất"),
    ],
    "service_down": [
        ("systemd.unit.active", "min:systemd.unit.active{unit:smiot.service}", "Trạng thái unit smiot.service"),
        ("smiot.external.sample_age_seconds", "max:smiot.external.sample_age_seconds{*}",
         "Tuổi mẫu đo từ probe ngoài ứng dụng"),
    ],
}

try:  # Metrics Explorer nhan trang thai bieu do qua phan # cua URL, nen bang lz-string (cung dinh dang Datadog dung).
    from lzstring import LZString as _LZString

    _LZ = _LZString()
except ImportError:  # thieu thu vien: chuyen sang trang Metrics Summary, khong dung khung gio
    _LZ = None


def metric_window(inc: dict[str, Any] | None, now: datetime | None = None) -> tuple[datetime, datetime] | None:
    """Cua so thoi gian cua su co cho lien ket Datadog: mo su co -15 phut den phuc hoi +15 phut (hoac hien tai).

    Khong co moc mo su co thi tra None de khong tao link doan.
    """
    inc = inc or {}
    start = _as_utc(inc.get("opened_at")) or _as_utc(inc.get("detected_at"))
    if start is None:
        return None
    now = now or datetime.now(timezone.utc)
    end = _as_utc(inc.get("recovered_at")) or now
    if end < start:
        end = start
    return start - METRIC_WINDOW_PAD, end + METRIC_WINDOW_PAD


def _epoch_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _explorer_state(query: str) -> str:
    """Trang thai Metrics Explorer (1 bieu do duong), dung dung cau truc Datadog tao ra khi mo mot truy van."""
    return json.dumps({
        "widget": {
            "definition": {
                "requests": [{
                    "display_type": "line",
                    "formulas": [{"formula": "query0"}],
                    "queries": [{"data_source": "metrics", "name": "query0", "query": query}],
                    "response_format": "timeseries",
                    "style": {"line_type": "solid", "line_width": "normal", "palette": "dog_classic"},
                }],
                "type": "timeseries",
            },
            "layout": {"height": 1, "width": 1, "x": 1, "y": 1},
        },
        "splitConfig": None,
    }, separators=(",", ":"), ensure_ascii=False)


def _explorer_url(name: str, query: str, start_ms: int, end_ms: int) -> str:
    """URL Metrics Explorer co san truy van va khung gio co dinh; thieu lzstring thi mo Metrics Summary cua metric."""
    if _LZ is None:
        return f"{DD_BASE}/metric/summary?metric={quote(name)}"
    state = _LZ.compressToEncodedURIComponent(_explorer_state(query))
    return f"{DD_BASE}/metric/explorer?start={start_ms}&end={end_ms}&paused=true#{state}"


def metric_links(incident: dict[str, Any] | None, now: datetime | None = None) -> list[tuple[str, str, str]]:
    """Lien ket sau toi metric Datadog cua su co: (nhan, url, mo ta). Rong neu khong ro kind hoac moc thoi gian."""
    inc = incident or {}
    specs = METRICS_BY_KIND.get(str(inc.get("kind") or ""))
    window = metric_window(inc, now)
    if not specs or window is None:
        return []
    start_ms, end_ms = _epoch_ms(window[0]), _epoch_ms(window[1])
    links: list[tuple[str, str, str]] = []
    for name, query, note in specs:
        links.append((name, _explorer_url(name, query, start_ms, end_ms), note))
    links.append(("Dashboard SMIOT theo thời gian sự cố",
                  f"{DD_DASHBOARD}?from_ts={start_ms}&to_ts={end_ms}&live=false",
                  "Dashboard vận hành, khung giờ của sự cố"))
    return links


def mongo_only_events(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Bo cac muc co nguon Datadog (mốc phát hiện theo monitor); giu telemetry, quyet dinh, so lenh, moc su co."""
    return [e for e in (events or []) if e.get("kind") not in DATADOG_SOURCED_KINDS]


RECOVERY_GENERIC = "Đã xác minh (xem chi tiết trong MongoDB)"


def _vi_decimal(value: float) -> str:
    """So kieu Viet: 38.9 -> '38,9'; 40.0 -> '40'."""
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}".replace(".", ",")


def _vi_range(value: Any) -> str | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    lo, hi = _as_float(value[0]), _as_float(value[1])
    if lo is None or hi is None or not (math.isfinite(lo) and math.isfinite(hi)):
        return None
    lo, hi = min(lo, hi), max(lo, hi)
    return f"độ ẩm {_vi_decimal(lo)}–{_vi_decimal(hi)}%"


def _vi_age(*values: Any) -> int | None:
    """Tuoi mau moi nhat (giay): lay gia tri dau tien hop le trong cac khoa dang co."""
    for value in values:
        seconds = _as_float(value)
        if seconds is not None and math.isfinite(seconds) and seconds >= 0:
            return int(round(seconds))
    return None


def _vi_time(value: Any) -> str | None:
    dt = value if isinstance(value, datetime) else None
    if dt is None and isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
    utc = _as_utc(dt)
    return utc.astimezone(VN_TZ).strftime("%H:%M:%S") if utc else None


_NO_AT: Any = object()  # khong truyen `at`: giu cau cu ("Monitor OK"); truyen None/datetime: ghi moc xac minh


def _hhmm(value: Any) -> str | None:
    stamp = _as_utc(value) if isinstance(value, datetime) else None
    if stamp is None and isinstance(value, str):
        try:
            stamp = _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            stamp = None
    return stamp.astimezone(VN_TZ).strftime("%H:%M") if stamp else None


def verified_at_of(incident: dict[str, Any] | None, ver: dict[str, Any] | None = None) -> Any:
    """Moc xac minh phuc hoi: verified_at trong ban ghi, khong co thi recovered_at cua ho so."""
    inc, ver = incident or {}, ver or {}
    return ver.get("verified_at") or (inc.get("recovery_verification") or {}).get("verified_at") \
        or inc.get("recovered_at")


def format_recovery_evidence(verification: Any, kind: str | None = None, at: Any = _NO_AT) -> str:
    """Bang chung phuc hoi -> cau tieng Viet doc duoc. Ham thuan, khong in dict tho, khong bia so.

    Co truyen `at` (moc xac minh, co the None) thi trang thai monitor luon di kem moc gio:
    "Monitor OK lúc xác minh 04:26" hoac "Monitor OK lúc xác minh (chưa ghi giờ)" - ban ghi MongoDB,
    khong phai trang thai hien tai tren Datadog.

    Nhan cac dang: verifier long (verification["verifier"]), method=auto_flatline_recovery_verified,
    false_offline (mongo_newest_received_at/age_s/display_now/computed_now), service_down (http_status,
    newest_sample_age_s), va verifier truc tiep. Khoa nao khong co thi bo qua; khong nhan ra gi thi tra
    RECOVERY_GENERIC.
    """
    if verification is None or verification == "":
        return UNKNOWN
    if not isinstance(verification, dict):
        return RECOVERY_GENERIC
    nested = verification.get("verifier")
    src = {**verification, **nested} if isinstance(nested, dict) else verification

    parts: list[str] = []
    monitor = src.get("monitor_state")
    if isinstance(monitor, str) and monitor.strip():
        if at is _NO_AT:
            parts.append(f"Monitor {monitor.strip()}")
        else:
            parts.append(f"Monitor {monitor.strip()} lúc xác minh {_hhmm(at) or '(chưa ghi giờ)'}")

    sample_bits: list[str] = []
    count = _as_count(src.get("sample_count"))
    if count is not None and count >= 0:
        sample_bits.append(f"{count} mẫu mới")
    rng = _vi_range(src.get("soil_humidity_range_pct"))
    if rng:
        sample_bits.append(rng)
    if sample_bits:
        parts.append(", ".join(sample_bits))

    age = _vi_age(src.get("sample_freshness_seconds"), src.get("newest_sample_age_seconds"),
                  src.get("newest_sample_age_s"), src.get("age_s"))
    time_text = _vi_time(src.get("mongo_newest_received_at"))
    age_text = f"mẫu mới nhất cách {age} giây" if age is not None else None
    if time_text:
        age_text = f"{age_text} ({time_text})" if age_text else f"mẫu mới nhất lúc {time_text}"
    if age_text:
        parts.append(age_text)

    pump = src.get("virtual_pump_outputs_off")
    if isinstance(pump, bool):
        parts.append("pump ảo đều OFF" if pump else "pump ảo chưa đều OFF")

    http_status = _as_count(src.get("http_status"))
    if http_status is not None:
        parts.append(f"healthz HTTP {http_status}")

    if kind == "false_offline":
        display, computed = src.get("display_now"), src.get("computed_now")
        if isinstance(display, str) and isinstance(computed, str) and display and computed:
            parts.append(f"UI hiện {display}, tính lại {computed}")

    if not parts:
        return RECOVERY_GENERIC
    return "; ".join(parts) + "."


# ---------------------------------------------------------------------------
# Ham thuan: 6 cau hoi
# ---------------------------------------------------------------------------
def build_six_questions(incident: dict[str, Any] | None, timeline: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Bang 6 cau hoi: moi dong gom cau hoi, tra loi ngan, nguon, va link mo. Thieu du lieu thi ghi UNKNOWN."""
    inc = incident or {}
    tl = timeline or {}
    rec = tl.get("recovery_evidence") or {}
    lots = tl.get("affected_lots") or []
    kind = inc.get("kind")
    monitor = _monitor_id(inc)
    trace_links = _trace_links(inc)  # chi de kiem tra co trace hay khong; cau 3 chi lay trace dau tien

    detected = inc.get("detected_at")
    detected_text = _fmt(detected) if detected else UNKNOWN
    if monitor:
        detected_text += f" · monitor {monitor} (Datadog)"

    lot_ids = [str(lot.get("lot_id")) for lot in lots if lot.get("lot_id") is not None]
    lot_text = ", ".join(lot_ids) if lot_ids else str(tl.get("affected_lots_status") or UNKNOWN)

    after = rec.get("samples_after_clear") or []
    clear_ts = rec.get("clear_ts")
    if after or clear_ts:
        recovery_text = f"Mốc phục hồi {_fmt(clear_ts)}; {len(after)} mẫu sau phục hồi"
        if rec.get("verification"):
            recovery_text += f"; {format_recovery_evidence(rec.get('verification'), kind)}"
    else:
        recovery_text = UNKNOWN

    evidence_text = "Nằm trong log và trace của Datadog. Log ghi chuỗi sự kiện đầy đủ, trace cho thấy đường đi của yêu cầu."
    if not trace_links:
        evidence_text += " Chưa có trace_id trong dữ liệu."

    return [
        {"question": "Chuyện gì xảy ra?", "answer": incident_headline(
            kind, inc.get("node_id"), inc.get("scenario_title")),
         "sources": [SRC_DATADOG], "links": _monitor_links(inc)},
        {"question": "Phát hiện lúc nào?", "answer": detected_text,
         "sources": [SRC_MONGO, SRC_DATADOG], "links": _monitor_links(inc)},
        {"question": "Bằng chứng gốc là gì?", "answer": evidence_text,
         "sources": [SRC_DATADOG], "links": [*_logs_link(inc), *_first_trace_link(inc)]},
        {"question": "Lô nào bị ảnh hưởng?", "answer": lot_text,
         "sources": [SRC_MONGO], "links": []},
        {"question": "Vì sao chọn hành động đó?",
         "answer": (inc.get("scenario_response") if kind == "scenario_event" else SAFETY_RULE_BY_KIND.get(kind, UNKNOWN)) or UNKNOWN,
         "sources": [SRC_DATADOG], "links": _execution_links(inc)},
        {"question": "Dữ liệu nào chứng minh phục hồi?", "answer": recovery_text,
         "sources": [SRC_MONGO], "links": []},
    ]


# ---------------------------------------------------------------------------
# Ham thuan: du lieu bieu do va the so tac dong
# ---------------------------------------------------------------------------
def count_blocked(events: list[dict[str, Any]] | None) -> int:
    """So quyet dinh BLOCKED. Quyet dinh duoc truy van theo incident_id nen 0 la gia tri thuc."""
    return sum(1 for e in events or []
               if e.get("source_collection") == "operational_decisions" and "BLOCKED" in str(e.get("summary", "")))


def _minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def _quality_series(inc: dict[str, Any], evs: list[dict[str, Any]]) -> dict[str, Any]:
    """Chuoi theo phut: mau hop le / mau bat thuong (= gia tri loi) / phut thieu mau.

    Gia tri None nghia la "chua xac dinh" (khong ve so 0 gia). Mau bat thuong chi tach duoc khi
    biet gia tri loi (observed_fault.value) hoac la false_offline (moi mau deu hop le theo dinh nghia).
    """
    kind = inc.get("kind")
    fault_value = _as_float((inc.get("observed_fault") or {}).get("value"))
    known = bool(inc.get("farm_key")) and (_as_utc(inc.get("fault_started_at")) or _as_utc(inc.get("opened_at"))) is not None
    if not known:
        return {"known": False, "split_known": False, "labels": [],
                "series": {k: [] for k in QUALITY_KEYS}, "totals": {k: None for k in QUALITY_KEYS},
                "note": "Thiếu farm_key hoặc mốc bắt đầu lỗi nên chưa truy vấn telemetry."}

    split_known = kind == "false_offline" or fault_value is not None
    buckets: dict[datetime, dict[str, int]] = {}

    def bump(minute: datetime, key: str) -> None:
        buckets.setdefault(minute, {k: 0 for k in QUALITY_KEYS})[key] += 1

    for e in evs:
        if e.get("kind") != "telemetry_sample":
            continue
        ts, value = _as_utc(e.get("ts")), _as_float(e.get("value"))
        if ts is None or value is None:
            continue  # mau khong co gia tri: khong dem vao bat ky nhom nao
        is_abnormal = (kind != "false_offline" and fault_value is not None
                       and abs(value - fault_value) < 1e-9)
        bump(_minute(ts), "abnormal" if is_abnormal else "valid")

    recovered = _as_utc(inc.get("recovered_at"))
    for e in evs:
        if e.get("kind") != "telemetry_gap":
            continue
        start = _as_utc(e.get("gap_start")) or _as_utc(e.get("ts"))
        end = _as_utc(e.get("gap_end"))
        if start is None or end is None or end <= start:
            continue
        if recovered is not None and start > recovered:
            continue  # khoang thieu mau sau phuc hoi khong thuoc su co nay
        minute, count = _minute(start), 0
        while minute < end and count < MAX_GAP_MINUTES:
            bump(minute, "missing")
            minute += timedelta(minutes=1)
            count += 1

    minutes = sorted(buckets)
    series: dict[str, list[int | None]] = {}
    for key in QUALITY_KEYS:
        if key != "missing" and not split_known:
            series[key] = [None] * len(minutes)
        else:
            series[key] = [buckets[m][key] for m in minutes]
    totals: dict[str, int | None] = {
        key: (sum(buckets[m][key] for m in minutes) if (key == "missing" or split_known) else None)
        for key in QUALITY_KEYS}

    if kind == "false_offline":
        note = "Dữ liệu vẫn vào MongoDB trong lúc UI báo offline: các mẫu được tính là hợp lệ."
    elif not split_known:
        note = "Chưa xác định giá trị lỗi (observed_fault) nên chưa tách mẫu bất thường; không vẽ số 0 giả."
    else:
        note = None
    return {"known": True, "split_known": split_known, "labels": [m.strftime("%H:%M") for m in minutes],
            "series": series, "totals": totals, "note": note}


def build_impact_chart_data(incident: dict[str, Any] | None, events: list[dict[str, Any]] | None,
                            impact: dict[str, Any] | None) -> dict[str, Any]:
    """Du lieu cho khoi Tac dong (tu MongoDB). Ham thuan: khong goi mang, khong ghi Mongo.

    - quality: chuoi theo phut cho bieu do cot chong (xem _quality_series).
    - cards: cac the so: lo anh huong, de xuat bi chan, gio du lieu khong dang tin, so khoang thieu mau.
    """
    inc = incident or {}
    evs = events or []
    imp = impact or {}

    hours = _as_float(imp.get("unreliable_hours"))
    basis_parts = [str(imp["unreliable_basis"])] if imp.get("unreliable_basis") else []
    if imp.get("unreliable_ongoing"):
        basis_parts.append("đang tiếp diễn")
    cards = [
        {"label": "Lô ảnh hưởng", "value": _as_count(imp.get("lots_to_review")), "unit": "",
         "note": "Lô khớp farm/node trong khoảng sự cố"},
        {"label": "Đề xuất tưới bị chặn", "value": count_blocked(evs), "unit": "",
         "note": "Quyết định BLOCKED ghi trong MongoDB"},
        {"label": "Giờ dữ liệu không đáng tin", "value": round(hours, 2) if hours is not None else None,
         "unit": " giờ", "note": " · ".join(basis_parts)},
        {"label": "Số khoảng thiếu mẫu", "value": _as_count(imp.get("missing_sample_gaps")), "unit": "",
         "note": "Khoảng telemetry_gap ghi trong MongoDB"},
    ]
    return {"quality": _quality_series(inc, evs), "cards": cards}


# ---------------------------------------------------------------------------
# Ket luan phuc hoi (dung o danh sach va ho so)
# ---------------------------------------------------------------------------
V_RECOVERED = "Đã phục hồi"
V_NO_PROOF = "Đã đóng, chưa có bằng chứng phục hồi"
V_UNVERIFIED = "Chưa xác minh"
V_OBSERVED = "Đã quan sát, chưa kết luận"
V_OPEN = {"open": "Đang mở", "holding": "Đang giữ an toàn", "recovering": "Đang phục hồi, chờ xác minh"}
V_OPEN_LEVEL = {"open": "act", "holding": "watch", "recovering": "watch"}

# Gia tri verifier tra ve khi chua/khong xac minh duoc: khong bao gio la bang chung.
_NOT_PROOF_STATES = frozenset({
    "unknown", "unverified", "not_verified", "pending", "failed", "error", "verifier_error",
    "timeout", "verification_not_passed", "not_cleared", "recovering", "recovered_pending_review",
})


def _unwrap_verification(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or not value:
        return None
    nested = value.get("verifier")
    return {**value, **nested} if isinstance(nested, dict) else value


def _finite(value: Any) -> float | None:
    number = _as_float(value)
    return number if number is not None and math.isfinite(number) else None


def _verification_problem(incident: dict[str, Any], ver: dict[str, Any]) -> str | None:
    """None neu bang chung du dieu kien theo tung loai; nguoc lai tra ly do ngan.

    Dieu kien bam theo code ghi bang chung: flatline = record_incident_action (CLEAR da verified:
    monitor OK, >= 10 mau, pump ao OFF, mau moi <= 90 giay); false_offline = telemetry_health
    (tinh lai ONLINE, co tuoi mau); service_down = smiot_external_probe (healthz 2xx va mau moi).
    Cac loai con lai chua co verifier ghi vao ho so nen can verified=true tuong minh.
    """
    kind = incident.get("kind")
    inc_id = str(incident.get("incident_id") or incident.get("_id") or "")
    owner = str(ver.get("incident_id") or "")
    if owner and inc_id and owner != inc_id:
        return "bằng chứng thuộc sự cố khác"
    if ver.get("verified") is False:
        return "bản ghi ghi rõ chưa xác minh"
    for key in ("status", "result", "verification_status"):
        word = str(ver.get(key) or "").strip().lower()
        if word in _NOT_PROOF_STATES:
            return f"verifier báo {word}"
    if kind == "soil_humidity_flatline":
        if str(ver.get("monitor_state") or "").upper() != "OK":
            return "monitor chưa ở trạng thái OK"
        count = _finite(ver.get("sample_count"))
        if count is None or count < 10:
            return "chưa đủ 10 mẫu mới"
        if ver.get("virtual_pump_outputs_off") is not True:
            return "chưa xác nhận pump ảo OFF"
        fresh = _finite(ver.get("sample_freshness_seconds"))
        if fresh is None or not 0 <= fresh <= 90:
            return "mẫu mới nhất không đủ tươi"
        return None
    if kind == "false_offline":
        if str(ver.get("computed_now") or "").upper() != "ONLINE":
            return "chưa tính lại được trạng thái ONLINE"
        if _vi_age(ver.get("age_s"), ver.get("newest_sample_age_s")) is None and not ver.get("mongo_newest_received_at"):
            return "thiếu tuổi mẫu MongoDB"
        return None
    if kind == "service_down":
        code = _as_count(ver.get("http_status"))
        if code is None or not 200 <= code < 300:
            return "healthz chưa trả HTTP 2xx"
        if _vi_age(ver.get("newest_sample_age_s"), ver.get("sample_freshness_seconds")) is None:
            return "thiếu tuổi mẫu mới nhất (HTTP 200 chưa đủ)"
        return None
    if ver.get("verified") is True:
        return None
    return "loại này chưa có bộ kiểm tra phục hồi ghi vào hồ sơ"


def recovery_verdict(incident: dict[str, Any] | None) -> tuple[str, str, str]:
    """(level, nhan, ly do) cho DUNG document incident. level: ok | watch | act | stale | info | none.

    "Đã phục hồi" chi khi status la recovered/closed VA recovery_verification (hoac recovery_evidence)
    cua chinh document do qua _verification_problem. Danh sach va ho so cung dung ham nay.
    """
    inc = incident or {}
    status = str(inc.get("status") or "").strip().lower()
    if status in V_OPEN:
        reason = {"open": "Chưa có lệnh an toàn được ACK.",
                  "holding": "Đã giữ an toàn; chưa có bằng chứng phục hồi.",
                  "recovering": "Đang chờ số đo mới và kiểm tra phục hồi."}[status]
        return V_OPEN_LEVEL[status], V_OPEN[status], reason
    if status == "observed":
        return "info", V_OBSERVED, "Mới quan sát được tín hiệu; chưa có kết luận hay bằng chứng phục hồi."
    if status not in {"recovered", "closed"}:
        return "none", status or UNKNOWN, "Trạng thái không nằm trong vòng đời đã biết."
    ver = _unwrap_verification(inc.get("recovery_verification")) or _unwrap_verification(inc.get("recovery_evidence"))
    if ver is None:
        return "watch", V_NO_PROOF, "Hồ sơ này không có bản ghi xác minh phục hồi."
    problem = _verification_problem(inc, ver)
    if problem:
        return "stale", V_UNVERIFIED, f"Có bản ghi xác minh nhưng chưa đủ điều kiện: {problem}."
    return "ok", V_RECOVERED, format_recovery_evidence(ver, inc.get("kind"), verified_at_of(inc, ver))


VERDICT_GROUPS = {
    "all": "Tất cả trạng thái", "active": "Đang xử lý", "recovered": V_RECOVERED,
    "no_proof": V_NO_PROOF, "unverified": V_UNVERIFIED, "observed": V_OBSERVED,
}


def verdict_group(incident: dict[str, Any] | None) -> str:
    label = recovery_verdict(incident)[1]
    if label in V_OPEN.values():
        return "active"
    return {V_RECOVERED: "recovered", V_NO_PROOF: "no_proof", V_UNVERIFIED: "unverified",
            V_OBSERVED: "observed"}.get(label, "other")


def _attach_verification(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """list_incidents tra ve recovery_verification va recovery_evidence cua chinh document, nen chi can chuan hoa."""
    return [{**row, "recovery_verification": row.get("recovery_verification"),
             "recovery_evidence": row.get("recovery_evidence")} for row in rows]


# ---------------------------------------------------------------------------
# Ham thuan: du lieu cho ho so sau chang
# ---------------------------------------------------------------------------
ACTION_LABELS = {"HOLD": "Giữ an toàn (HOLD)", "CLEAR": "Xóa HOLD (CLEAR)", "SAFE_STOP": "Dừng an toàn (SAFE_STOP)"}
_LEDGER_ORDER = {"requested": 0, "published": 1, "acknowledged": 2, "failed": 3, "verified": 4}


def ledger_commands(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Gom action_ledger (va ACK cua scenario_run_events) theo command_id cua DUNG incident.

    Moi lenh: {command_id, label, status, sent_at, acked_at, verified_at}; status la trang thai moi nhat
    de dua vao ui_kit.command_chain. Khong suy ra buoc nao khong co moc thoi gian that.
    """
    groups: dict[str, dict[str, Any]] = {}
    for e in events or []:
        src = e.get("source_collection")
        refs = e.get("refs") or {}
        cid = refs.get("message_id") or refs.get("log")
        ts = _as_utc(e.get("ts"))
        if not cid or ts is None:
            continue
        if src == "action_ledger":
            state = str(e.get("state") or "")
            if state not in _LEDGER_ORDER:
                continue
            action = str(e.get("action") or "")
            group = groups.setdefault(str(cid), {"command_id": str(cid), "origin": "action_ledger",
                                                 "label": ACTION_LABELS.get(action, action or "Lệnh"), "steps": []})
            group["steps"].append((ts, state))
        elif src == "scenario_run_events":
            status = str(e.get("kind") or "").removeprefix("scenario_")
            group = groups.setdefault(str(cid), {"command_id": str(cid), "origin": "scenario",
                                                 "label": str(e.get("summary") or "Lệnh kịch bản"), "steps": []})
            group["steps"].append((ts, status))
    out = []
    for group in groups.values():
        steps = sorted(group["steps"], key=lambda s: (s[0], _LEDGER_ORDER.get(s[1], 9)))
        at = lambda *names: next((t for t, s in steps if s in names), None)  # noqa: E731
        if group["origin"] == "action_ledger":
            sent = at("requested", "published")
            acked, verified = at("acknowledged"), at("verified")
        else:
            sent, acked, verified = None, at("started", "stopped"), None
        out.append({"command_id": group["command_id"], "label": group["label"], "origin": group["origin"],
                    "status": steps[-1][1], "sent_at": sent, "acked_at": acked, "verified_at": verified})
    out.sort(key=lambda c: c["sent_at"] or c["acked_at"] or datetime.min.replace(tzinfo=timezone.utc))
    return out


def measurement_points(events: list[dict[str, Any]] | None) -> list[tuple[datetime, float]]:
    pts = []
    for e in events or []:
        if e.get("kind") != "telemetry_sample":
            continue
        ts, value = _as_utc(e.get("ts")), _finite(e.get("value"))
        if ts is not None and value is not None:
            pts.append((ts, value))
    pts.sort(key=lambda p: p[0])
    return pts


def _vn_ms(value: datetime) -> int:
    """Moc cho truc thoi gian bieu do: cong 7 gio va dat useUTC, de nhan gio khong phu thuoc trinh duyet."""
    return _epoch_ms(value) + VN_OFFSET_MS


def _incident_marks(inc: dict[str, Any]) -> list[dict[str, Any]]:
    marks = []
    for key, label, color in (("fault_started_at", "Bắt đầu lỗi", CHART["level"]["act"]),
                              ("opened_at", "Mở hồ sơ", CHART["level"]["none"]),
                              ("detected_at", "Phát hiện", CHART["level"]["info"]),
                              ("safe_at", "An toàn", CHART["level"]["ok"]),
                              ("recovered_at", "Phục hồi", CHART["level"]["ok"])):
        stamp = _as_utc(inc.get(key))
        if stamp is not None:
            marks.append({"xAxis": _vn_ms(stamp), "name": label,
                          "lineStyle": {"color": color, "type": "dashed", "width": 1},
                          "label": {"formatter": "{b}", "color": color, "fontSize": 11,
                                    "position": "insideEndTop", "rotate": 90}})
    return marks


def _time_axis_option(y_name: str) -> dict[str, Any]:
    option = echart_base()
    option["useUTC"] = True  # moc thoi gian da cong 7 gio (xem _vn_ms)
    option["legend"] = {"show": False}
    option["grid"] = {**option["grid"], "top": 36, "left": 48}
    option["xAxis"] = {**option["xAxis"], "type": "time", "splitLine": {"show": False}}
    option["yAxis"] = {**option["yAxis"], "type": "value", "scale": True, "name": y_name,
                       "nameTextStyle": {"color": CHART["muted"]}}
    return option


def _downsample(pts: list[Any], limit: int = 700) -> list[Any]:
    return pts[::math.ceil(len(pts) / limit)] if len(pts) > limit else pts


def measure_chart_options(inc: dict[str, Any], events: list[dict[str, Any]] | None,
                          now: datetime | None = None, dd: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Duong do am dat quanh su co: MongoDB (xanh) va, neu Datadog co diem, Datadog (tim) tren cung truc.

    Danh dau cac moc that cua ho so. None neu ca hai nguon deu khong co diem.
    """
    pts = _downsample(measurement_points(events))
    soil = [(float(p[0]), float(p[1])) for p in ((dd or {}).get("soil_series") or [])
            if isinstance(p, (list, tuple)) and len(p) == 2 and _finite(p[1]) is not None]
    if not pts and not soil:
        return None
    areas: list[Any] = []
    start = _as_utc(inc.get("fault_started_at")) or _as_utc(inc.get("opened_at"))
    if start is not None:
        end = _as_utc(inc.get("recovered_at")) or (now or datetime.now(timezone.utc))
        areas.append([{"xAxis": _vn_ms(start)}, {"xAxis": _vn_ms(max(end, start))}])
    for e in events or []:
        if e.get("kind") == "telemetry_gap":
            g0, g1 = _as_utc(e.get("gap_start")), _as_utc(e.get("gap_end"))
            if g0 is not None and g1 is not None and g1 > g0:
                areas.append([{"xAxis": _vn_ms(g0), "itemStyle": {"color": CHART["tint"]["none"]}},
                              {"xAxis": _vn_ms(g1)}])
    option = _time_axis_option("%")
    series: list[dict[str, Any]] = []
    if pts:
        series.append({"type": "line", "name": "MongoDB", "showSymbol": len(pts) <= 120, "symbolSize": 4,
                       "lineStyle": {"width": 1.5, "color": CHART["series"][0]},
                       "itemStyle": {"color": CHART["series"][0]},
                       "data": [[_vn_ms(t), v] for t, v in pts]})
    if soil:
        series.append({"type": "line", "name": "Datadog", "showSymbol": False,
                       "lineStyle": {"width": 1.5, "color": CHART["dd"]}, "itemStyle": {"color": CHART["dd"]},
                       "data": [[int(t * 1000) + VN_OFFSET_MS, v] for t, v in soil]})
    series[0]["markLine"] = {"silent": True, "symbol": "none", "data": _incident_marks(inc)}
    series[0]["markArea"] = {"silent": True, "itemStyle": {"color": CHART["band"]}, "data": areas}
    if len(series) > 1:
        option["legend"] = {**echart_base()["legend"], "show": True}
    option["series"] = series
    return option


def dd_metric_options(inc: dict[str, Any], dd: dict[str, Any] | None) -> dict[str, Any] | None:
    """Metric phat hien cua Datadog tren truc thoi gian, co vach moc su co va nguong critical neu API tra ve."""
    series = [(float(p[0]), float(p[1])) for p in ((dd or {}).get("series") or [])
              if isinstance(p, (list, tuple)) and len(p) == 2 and _finite(p[1]) is not None]
    if not series:
        return None
    marks: list[dict[str, Any]] = _incident_marks(inc)
    critical = _finite(((dd or {}).get("thresholds") or {}).get("critical"))
    if critical is not None:
        marks.append({"yAxis": critical, "name": "Ngưỡng critical",
                      "lineStyle": {"color": CHART["level"]["act"], "type": "solid", "width": 1},
                      "label": {"formatter": "{b}", "color": CHART["level"]["act"], "fontSize": 11,
                                "position": "insideEndTop"}})
    option = _time_axis_option("")
    option["series"] = [{
        "type": "line", "name": "Metric Datadog", "showSymbol": False,
        "lineStyle": {"width": 2, "color": CHART["dd"]}, "itemStyle": {"color": CHART["dd"]},
        "data": [[int(t * 1000) + VN_OFFSET_MS, v] for t, v in series],
        "markLine": {"silent": True, "symbol": "none", "data": marks},
    }]
    return option


def dashboard_window_link(inc: dict[str, Any], now: datetime | None = None) -> tuple[str, str, str] | None:
    window = metric_window(inc, now)
    if window is None:
        return None
    return ("Dashboard SMIOT theo thời gian sự cố",
            f"{DD_DASHBOARD}?from_ts={_epoch_ms(window[0])}&to_ts={_epoch_ms(window[1])}&live=false",
            "Dashboard vận hành, khung giờ của sự cố")


def case_file_state(tl: dict[str, Any], dd: dict[str, Any] | None = None) -> dict[str, Any]:
    """Tom tat sau chang: co bang chung hay khong (tu du lieu cua dung incident) va chuoi tom tat."""
    inc = tl.get("incident") or {}
    events = tl.get("events") or []
    ev = inc.get("evidence") or {}
    verdict = cross_check_verdict(recovery_verdict(inc), tl.get("recovery_evidence"))
    commands = ledger_commands(events)
    decisions = [e for e in events if e.get("source_collection") == "operational_decisions"]
    points = measurement_points(events)
    traces = [t for t in (ev.get("trace_ids") or []) if t]
    observations = [o for o in (ev.get("workflow_observations") or []) if isinstance(o, dict)]
    monitor, workflow = _monitor_id(inc, False), _workflow_id(inc, False)
    has_dd = bool(monitor or inc.get("last_workflow_execution_id") or traces or observations)
    has_decision = bool(decisions or inc.get("last_action") or inc.get("safe_at")
                        or inc.get("last_workflow_disposition"))
    has = [bool(inc.get("detected_at") or inc.get("opened_at")), bool(points), has_dd, has_decision,
           bool(commands), verdict[0] == "ok"]

    def step(label: str, ok: bool, detail: str | None, failed: bool = False, waiting: bool = False) -> dict:
        state = "failed" if failed else ("done" if ok else ("waiting" if waiting else "none"))
        return {"label": label, "state": state, "detail": detail}

    if not commands:
        ack_step = step("ACK", False, "Chưa ghi nhận lệnh")
    elif any(c["status"] in {"failed", "rejected", "publish_failed", "unacknowledged"} for c in commands):
        ack_step = step("ACK", False, "Có lệnh lỗi hoặc bị từ chối", failed=True)
    elif all(c["acked_at"] for c in commands):
        ack_step = step("ACK", True, f"{len(commands)} lệnh đã ACK")
    else:
        ack_step = step("ACK", False, "Có lệnh chưa ACK", waiting=True)
    if verdict[0] == "ok":
        rec_step = step("Phục hồi", True, fmt_time(inc.get("recovered_at")))
    elif verdict[1] in (V_NO_PROOF, V_UNVERIFIED):
        rec_step = step("Phục hồi", False, verdict[1], failed=True)
    elif verdict[1] in V_OPEN.values():
        rec_step = step("Phục hồi", False, verdict[1], waiting=True)
    else:
        rec_step = step("Phục hồi", False, verdict[1])
    chain = [
        step("Phát hiện", has[0], fmt_time(inc.get("detected_at") or inc.get("opened_at"))),
        step("Datadog", has[2], "Có monitor, workflow hoặc trace" if has_dd else "Chưa gắn"),
        step("Bối cảnh", has[1], f"{len(points)} mẫu" if points else "Chưa có mẫu"),
        step("Quyết định", has[3], f"{len(decisions)} bản ghi" if decisions else ("Có ghi nhận" if has[3] else "Chưa ghi nhận")),
        ack_step, rec_step,
    ]
    return {"verdict": verdict, "commands": commands, "decisions": decisions, "points": points,
            "traces": traces, "observations": observations, "has": has, "chain": chain,
            "phases": build_phases(inc, verdict, commands, traces, observations, dd)}


SAMPLES_CONTRADICT_REASON = "mẫu MongoDB sau mốc CLEAR vẫn bằng giá trị lỗi"


def samples_contradict(rec: dict[str, Any] | None) -> bool:
    """True khi co mau sau mốc CLEAR va MOI mau deu bang gia tri loi (differs_from_fault is False)."""
    after = [s for s in ((rec or {}).get("samples_after_clear") or []) if isinstance(s, dict)]
    return bool(after) and all(s.get("differs_from_fault") is False for s in after)


def cross_check_verdict(verdict: tuple[str, str, str], rec: dict[str, Any] | None) -> tuple[str, str, str]:
    """Ha ket luan 'Da phuc hoi' xuong 'Chua xac minh' neu chinh cac mau sau CLEAR phu nhan no."""
    if verdict[0] == "ok" and samples_contradict(rec):
        return "stale", V_UNVERIFIED, SAMPLES_CONTRADICT_REASON
    return verdict


# Nhan tieng Viet cho ma cach xu ly cua workflow; ma chua co nhan thi in nguyen ma.
DISPOSITION_LABELS = {
    "hold_already_latched_duplicate_suppressed": "Đã giữ HOLD từ trước, bỏ qua lần lặp",
}


def disposition_label(code: Any) -> tuple[str | None, str | None]:
    """(nhan tieng Viet hoac ma goc, ma goc neu da dich). (None, None) khi khong co."""
    word = str(code or "").strip()
    if not word:
        return None, None
    label = DISPOSITION_LABELS.get(word)
    return (label, word) if label else (word, None)


def format_gap(start: Any, end: Any) -> str | None:
    """Khoang tu start den end, chi khi du hai moc that va end >= start. Khong doan."""
    begin, finish = _as_utc(start), _as_utc(end)
    if begin is None or finish is None or finish < begin:
        return None
    return format_duration(begin, finish)


def build_phases(inc: dict[str, Any], verdict: tuple[str, str, str], commands: list[dict[str, Any]],
                 traces: list[Any], observations: list[Any], dd: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Ba pha Phat hien / Dieu tra / Phan ung, moi pha 2 dong. Dong 2 chi co khi du hai moc that."""
    monitor = _monitor_id(inc, False)
    detected = inc.get("detected_at")
    line1 = (f"Monitor {monitor} báo lúc {fmt_time(detected)}" if monitor and detected
             else (f"Phát hiện lúc {fmt_time(detected)}" if detected else "Hồ sơ chưa ghi mốc phát hiện"))
    gap = format_gap(inc.get("fault_started_at"), detected)
    detect = {"key": "detect", "title": "1 · Phát hiện", "owner": "datadog", "line1": line1,
              "line2": f"Sau khi lỗi bắt đầu {gap}" if gap and gap != "0 giây" else None}

    runs = len(observations) or (1 if inc.get("last_workflow_execution_id") else 0)
    logs = (dd or {}).get("logs")
    # Only count evidence explicitly linked to this incident.  Datadog traces
    # that merely fall in the same time window are context, not proof for this
    # case.  Likewise, a stored synthetic observation is a reference to a
    # reviewed run, not a newly executed live run.
    parts = [f"{len(traces)} trace gắn mã sự cố" if traces else "chưa có trace gắn mã sự cố",
             f"{runs} workflow đã ghi trong hồ sơ" if runs else "chưa có workflow gắn hồ sơ"]
    if isinstance(logs, list):
        parts.append(f"{len(logs)}{'+' if (dd or {}).get('logs_more') else ''} dòng log khớp mã sự cố")
    result_label, _code = disposition_label(inc.get("last_workflow_disposition"))
    status = inc.get("last_workflow_status")
    result = " / ".join(str(x) for x in (status, result_label) if x)
    investigate = {"key": "investigate", "title": "2 · Điều tra", "owner": "datadog",
                   "line1": ", ".join(parts), "line2": f"Kết quả workflow: {result}" if result else None}

    sent = [c for c in commands if c.get("sent_at") or c.get("acked_at")]
    names = [f"{c['label'].split(' (')[-1].rstrip(')') if '(' in c['label'] else c['label']} "
             f"{fmt_time(c.get('sent_at') or c.get('acked_at'), with_date=False)}" for c in sent[:3]]
    line1 = ", ".join(names) if names else "Chưa ghi nhận lệnh nào"
    took = format_gap(inc.get("opened_at"), inc.get("recovered_at")) if verdict[0] == "ok" else None
    respond = {"key": "respond", "title": "3 · Phản ứng", "owner": "mongo", "line1": line1,
               "line2": f"Phục hồi sau {took}" if took else None}
    return [detect, investigate, respond]


# ---------------------------------------------------------------------------
# Danh sach: ham thuan giu cho cac ca van hanh
# ---------------------------------------------------------------------------
STATE_DONE = "Đã phục hồi"
STATE_OPEN = "Đang xử lý"


def case_runs(rows: list[dict[str, Any]] | None) -> dict[int, list[dict[str, Any]]]:
    """Gom cac lan su co theo ca (rows da sap xep moi nhat truoc). Kind la -> bo qua."""
    out: dict[int, list[dict[str, Any]]] = {number: [] for number in CASES}
    for row in rows or []:
        number = case_for_kind(row.get("kind"))
        if number in out:
            out[number].append(row)
    return out


def run_state(row: dict[str, Any]) -> str:
    """Chi theo status; giu cho tuong thich. Giao dien dung recovery_verdict (can bang chung)."""
    return STATE_DONE if row.get("status") == "recovered" else STATE_OPEN


def format_duration(start: Any, end: Any) -> str:
    """Thoi gian tu luc mo den luc phuc hoi, dang doc duoc. Thieu moc -> '—' (khong doan)."""
    begin, finish = _as_utc(start), _as_utc(end)
    if begin is None or finish is None or finish < begin:
        return "—"
    seconds = int((finish - begin).total_seconds())
    if seconds < 60:
        return f"{seconds} giây"
    minutes, rest = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} phút {rest} giây" if rest else f"{minutes} phút"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} giờ {minutes} phút" if minutes else f"{hours} giờ"


def scope_label(row: dict[str, Any]) -> str:
    farm, node = row.get("farm_key"), row.get("node_id")
    if not farm or farm == "_system":
        return "Toàn hệ thống"
    return f"{farm}, node {node}" if node is not None else str(farm)


def case_summary_text(runs: list[dict[str, Any]], case: dict[str, Any] | None = None) -> str:
    if not runs:
        return "Chưa diễn tập"
    done = sum(1 for row in runs if row.get("status") == "recovered")
    return f"{len(runs)} lần diễn tập, {done} đã phục hồi"


def build_list_rows(rows: list[dict[str, Any]] | None, selected_case: int = 0) -> list[dict[str, Any]]:
    """Dong cho bang; selected_case=0 la tat ca."""
    out = []
    for row in rows or []:
        number = case_for_kind(row.get("kind"))
        if selected_case and number != selected_case:
            continue
        incident_id = str(row.get("incident_id") or "")
        level, label, reason = recovery_verdict(row)
        out.append({
            "id": incident_id, "id_short": f"…{incident_id[-8:]}" if len(incident_id) > 8 else incident_id,
            "case_no": number or 0, "case": f"Ca {number}" if number else "—",
            "scope": scope_label(row), "state": label, "state_level": level, "state_reason": reason,
            "state_ok": row.get("status") == "recovered",
            "opened_at": _fmt(row.get("opened_at")),
            "duration": format_duration(row.get("opened_at"), row.get("recovered_at")),
        })
    return out


# ---------------------------------------------------------------------------
# Giao dien dung chung
# ---------------------------------------------------------------------------
def _missing(what: str) -> None:
    ui.label(f"Hồ sơ này chưa ghi nhận {what}.").classes("sm-note")


def _block_title(text: str) -> None:
    ui.label(text).classes("inc-block-title")


def _table(headers: list[str], rows: list[list[Any]], min_width: int = 520, stack: bool = True) -> None:
    """Bang phang. Moi o: chuoi hoac ham ve widget ben trong o.

    stack=True: duoi 768 px moi hang thanh mot the (nhan cot lay tu data-label), khong con cuon ngang.
    """
    with ui.element("div").classes("sm-scroll-x" + (" sm-stack-table" if stack else "")):
        with ui.element("table").classes("sm-table").style(f"min-width:{min_width}px"):
            with ui.element("thead"):
                with ui.element("tr"):
                    for header in headers:
                        with ui.element("th"):
                            ui.label(header)
            with ui.element("tbody"):
                for row in rows:
                    with ui.element("tr"):
                        for index, cell in enumerate(row):
                            label = headers[index] if index < len(headers) else ""
                            with ui.element("td").props(f'data-label="{html.escape(label, quote=True)}"'):
                                if callable(cell):
                                    cell()
                                else:
                                    ui.label(str(cell))


def _monitor_level(state: Any) -> str:
    word = str(state or "").strip().lower()
    return {"ok": "ok", "warn": "watch", "alert": "act", "no data": "stale", "skipped": "none",
            "ignored": "none"}.get(word, "none")


# ---------------------------------------------------------------------------
# Trang danh sach
# ---------------------------------------------------------------------------
def _scope_text(row: dict[str, Any]) -> str:
    farm_key = row.get("farm_key")
    text = ("Toàn hệ thống" if not farm_key or farm_key == "_system" else FARM_LABELS.get(str(farm_key), str(farm_key)))
    node = row.get("node_id")
    return text + (f", node {node}" if node is not None else "")



PAGE_SIZE = 25
_FLAGS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_FLAGS_TTL_SECONDS = 120
TAB_LABELS = {"complete": "Đủ bằng chứng", "incomplete": "Thiếu bước", "all": "Tất cả đã đóng"}
PHASE_NAMES = ("Phát hiện", "Điều tra", "Phản ứng")
_DOT_TEXT = {"done": "đủ", "wait": "đang chờ", "none": "thiếu"}


def phase_dots(st: dict[str, Any]) -> list[str]:
    """Trang thai 3 pha (done | wait | none) tu case_file_state, chi theo du lieu cua dung ho so."""
    has = st["has"]
    respond = "none"
    if st["verdict"][0] == "ok" and st["commands"]:
        respond = "done"
    elif st["commands"] or st["decisions"] or has[3]:
        respond = "wait"
    return ["done" if has[0] else "none", "done" if has[2] else "none", respond]


def _dots_html(dots: list[str] | None) -> str:
    if not dots:
        return '<span class="sm-note">…</span>'
    cells = []
    for name, state in zip(PHASE_NAMES, dots):
        mark = {"done": "✓", "wait": "…"}.get(state, "–")
        cells.append(f'<span class="sm-dot {state if state != "none" else ""}" '
                     f'title="{name}: {_DOT_TEXT.get(state, "thiếu")}">{mark}</span>')
    return f'<span class="sm-dots" aria-label="Ba pha: phát hiện, điều tra, phản ứng">{"".join(cells)}</span>'


def _detail_flags(incident_id: str) -> dict[str, Any]:
    """Doc ho so MOT lan (cache ngan): du 6 buoc, co bi ha ket luan, 3 cham pha. Khong ghi gi vao Mongo."""
    now = time.time()
    cached = _FLAGS_CACHE.get(incident_id)
    if cached and now - cached[0] < _FLAGS_TTL_SECONDS:
        return cached[1]
    try:
        st = case_file_state(build_incident_timeline(incident_id))
        flags = {"known": True, "complete": all(st["has"]),
                 "downgrade": st["verdict"][2] == SAMPLES_CONTRADICT_REASON, "dots": phase_dots(st)}
    except Exception:
        flags = {"known": False, "complete": False, "downgrade": False, "dots": None}
    _FLAGS_CACHE[incident_id] = (now, flags)
    return flags


def _cached_flags(incident_id: str) -> dict[str, Any] | None:
    cached = _FLAGS_CACHE.get(incident_id)
    return cached[1] if cached and time.time() - cached[0] < _FLAGS_TTL_SECONDS else None


def row_verdict(row: dict[str, Any], flags: dict[str, Any] | None = None) -> tuple[str, str, str]:
    """Ket luan cua dong; ha xuong 'Chua xac minh' neu cac mau sau CLEAR phu nhan (flags.downgrade)."""
    level, label, reason = recovery_verdict(row)
    if level == "ok" and (flags or {}).get("downgrade"):
        return "stale", V_UNVERIFIED, SAMPLES_CONTRADICT_REASON
    return level, label, reason


def group_of_label(label: str) -> str:
    if label in V_OPEN.values():
        return "active"
    return {V_RECOVERED: "recovered", V_NO_PROOF: "no_proof", V_UNVERIFIED: "unverified",
            V_OBSERVED: "observed"}.get(label, "other")


def is_active_row(row: dict[str, Any]) -> bool:
    return str(row.get("status") or "").strip().lower() in ACTIVE_STATUSES


def split_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(dang mo, da dong) - khong an ho so nao."""
    active = [r for r in rows if is_active_row(r)]
    return active, [r for r in rows if not is_active_row(r)]


def tab_rows(closed: list[dict[str, Any]], tab: str) -> list[dict[str, Any]]:
    """Loc theo tab dua tren co da kiem tra: chua kiem tra xong thi khong xep vao tab Du / Thieu."""
    if tab == "all":
        return list(closed)
    out = []
    for row in closed:
        flags = _cached_flags(str(row.get("incident_id") or ""))
        if flags is None or not flags.get("known"):
            continue
        if (tab == "complete") == bool(flags["complete"]):
            out.append(row)
    return out


def _chip_for_monitor(info: dict[str, Any] | None, overview: dict[str, Any] | None) -> tuple[str, str]:
    if overview is None:
        return "none", "Đang đọc…"
    if not overview.get("available"):
        return "none", "Chưa đọc được"
    if info is None:
        return "stale", "Không có trong tổ chức Datadog"
    state = str(info.get("overall_state") or "Unknown")
    return _monitor_level(state), state


@ui.page("/incident")
def incident_list_page(farm: str = ""):
    if not _guard():
        return
    ui.add_head_html(f"<style>{CUSTOM_CSS}{INC_CSS}</style>")
    sidebar(active="Incident")
    with ui.element("div").classes("main-content"):
        global_topbar("Sự cố", emoji="", show_farm_selector=False)
        with ui.element("div").classes("content-area inc-wrap"):
            with ui.element("div").classes("sm-stack"):
                with page_header("Sự cố", "Datadog phát hiện và điều tra; MongoDB giữ hồ sơ và tác động; ứng dụng dẫn bạn tới đúng chỗ."):
                    sim_badge()
                view = {"farm": farm if farm in FARM_KEYS else "", "group": "all", "case": 0,
                        "tab": "complete", "page": 0}
                data: dict[str, Any] = {"rows": None, "error": None, "dd": None, "computing": False}

                def redraw() -> None:
                    dd_block.refresh()
                    results.refresh()

                # ---- Khoi A: Datadog dang thay gi (pha Phat hien) --------------------
                @ui.refreshable
                def dd_block():
                    overview = data["dd"]
                    case_ids = [c["monitor_id"] for c in CASES.values() if c.get("monitor_id")]
                    note = (f"Datadog API, chỉ đọc, đọc lúc {fmt_time(overview.get('fetched_at'), with_date=False)}"
                            if overview and overview.get("available") else "Datadog API, chỉ đọc")
                    box = panel("Datadog đang thấy gì", "Phát hiện: trạng thái monitor của mười ca vận hành").classes("dd-panel")
                    with box:
                        with ui.element("div").classes("sm-inline"):
                            ui.label(note).classes("dd-src").style("margin-left:0")
                            ext_link("Mở danh sách monitor trên Datadog ↗", f"{DD_BASE}/monitors/manage?q=SMIOT")
                        if overview is None:
                            state_panel("loading", "Đang đọc Datadog", "Chỉ đọc, tối đa vài giây.")
                        elif not overview.get("available"):
                            reason = overview.get("reason")
                            retry = dd_reason(reason) in {"timeout", "network"}
                            dd_state_panel(reason, on_action=(load_dd if retry else
                                                              (lambda: ui.navigate.to(f"{DD_BASE}/monitors/manage?q=SMIOT", new_tab=True))))
                        else:
                            counts = overview.get("counts") or {}
                            with stats():
                                stat("Monitor Alert", counts.get("Alert", 0), None, "Datadog, trạng thái hiện tại",
                                     level="act" if counts.get("Alert") else None)
                                stat("Monitor Warn", counts.get("Warn", 0), None, "Datadog, trạng thái hiện tại",
                                     level="watch" if counts.get("Warn") else None)
                                stat("Monitor No Data", counts.get("No Data", 0), None, "Datadog, trạng thái hiện tại")
                                stat("Monitor OK", counts.get("OK", 0), None, f"trong {overview.get('total', 0)} monitor SMIOT")
                            missing = overview.get("missing_ids") or []
                            if missing:
                                source_note(f"{len(missing)} monitor theo cấu hình ca không có trong tổ chức Datadog đang dùng.")
                        runs_by_case = case_runs([r for r in (data["rows"] or [])
                                                  if not view["farm"] or r.get("farm_key") == view["farm"]])
                        with ui.element("div").classes("dd-cases").style("margin-top:12px"):
                            for number, case in CASES.items():
                                runs = runs_by_case.get(number, [])
                                info = ((overview or {}).get("monitors") or {}).get(str(case.get("monitor_id")))
                                level, text = _chip_for_monitor(info, overview)
                                with ui.element("div").classes("dd-case" + (" on" if view["case"] == number else "")):
                                    def toggle(n=number):
                                        view["case"] = 0 if view["case"] == n else n
                                        view["page"] = 0
                                        redraw()
                                    button = ui.element("button").classes("dd-case-btn").props('type="button"')
                                    with button:
                                        ui.label(case["title"])
                                    button.on("click", lambda _e, t=toggle: t())
                                    status_chip(level, text)
                                    changed = info.get("overall_state_modified") if info else None
                                    if changed:
                                        ui.label(f"Đổi trạng thái lần cuối {fmt_time(changed)}").classes("inc-case-meta")
                                    ui.label(case_summary_text(runs, case) + " (MongoDB)").classes("inc-case-meta")
                                    with ui.element("div").classes("inc-case-links"):
                                        if case.get("monitor_id"):
                                            ext_link("Monitor ↗", f"{DD_BASE}/monitors/{quote(str(case['monitor_id']))}")
                                        if case.get("workflow_id"):
                                            ext_link("Workflow ↗", f"{DD_BASE}/workflow/{quote(str(case['workflow_id']))}")
                        source_note("Monitor và workflow ở đây là theo cấu hình ca, không phải của từng hồ sơ. Bấm tên ca để lọc hồ sơ.")
                        if overview and overview.get("available"):
                            extra = [m for mid, m in (overview.get("monitors") or {}).items() if mid not in case_ids]
                            if extra:
                                _block_title("Monitor SMIOT khác đang có trong tổ chức Datadog (không gắn với ca nào theo cấu hình)")
                                rows_extra = []
                                for m in extra:
                                    def state_cell(m=m):
                                        status_chip(_monitor_level(m["overall_state"]), m["overall_state"])

                                    def open_cell(m=m):
                                        ext_link("Mở ↗", f"{DD_BASE}/monitors/{quote(str(m['id']))}")
                                    rows_extra.append([m.get("name") or m["id"], state_cell,
                                                       fmt_time(m.get("overall_state_modified")), open_cell])
                                _table(["Monitor", "Trạng thái", "Đổi trạng thái lần cuối", ""], rows_extra, 520)

                dd_block()

                # ---- Khoi B + C: MongoDB ---------------------------------------------
                with panel():
                    with ui.element("div").classes("inc-filters"):
                        farm_options = {"all": "Tất cả nhà màng", **{key: FARM_LABELS.get(key, key) for key in FARM_KEYS}}
                        ui.select(farm_options, value=view["farm"] or "all", label="Nhà màng",
                                  on_change=lambda e: (view.update(farm="" if e.value == "all" else e.value, page=0),
                                                       redraw())
                                  ).props("outlined dense options-dense")
                        ui.select(VERDICT_GROUPS, value="all", label="Kết luận",
                                  on_change=lambda e: (view.update(group=e.value, page=0), results.refresh())
                                  ).props("outlined dense options-dense")

                @ui.refreshable
                def results():
                    if data["error"]:
                        state_panel("error", "Không đọc được danh sách sự cố",
                                    f"{data['error']}. Kiểm tra MongoDB rồi thử lại.",
                                    action_label="Thử lại", on_action=load)
                        return
                    if data["rows"] is None:
                        state_panel("loading", "Đang tải danh sách sự cố", "Đọc từ MongoDB.")
                        return
                    all_rows = [r for r in data["rows"]
                                if (not view["farm"] or r.get("farm_key") == view["farm"])
                                and (not view["case"] or case_for_kind(r.get("kind")) == view["case"])]
                    active, closed = split_rows(all_rows)

                    if view["case"]:
                        with ui.element("div").classes("sm-inline"):
                            status_chip("info", f"Đang lọc: Ca {view['case']}")
                            ui.button("Bỏ lọc ca", on_click=lambda: (view.update(case=0, page=0), redraw())
                                      ).props("flat dense no-caps").classes("sm-btn-quiet")

                    # Khoi B: dang mo
                    with panel("Đang mở, cần phản ứng", f"{len(active)} hồ sơ · MongoDB").classes("mongo-panel"):
                        if not active:
                            status_chip("ok", "Không có sự cố đang mở.")
                        else:
                            with ui.element("div").classes("inc-active"):
                                for r in active:
                                    incident_id = str(r.get("incident_id") or "")
                                    flags = _cached_flags(incident_id)
                                    level, label, reason = row_verdict(r, flags)
                                    with ui.element("div").classes("inc-active-card"):
                                        with ui.element("div").classes("sm-inline"):
                                            ui.label(kind_name(r.get("kind"))).classes("sm-h2")
                                            status_chip(level, label).tooltip(reason)
                                        ui.label(_scope_text(r) + f" · mở {fmt_age(r.get('opened_at'))}").classes("inc-case-meta")
                                        ui.html(_dots_html(flags["dots"] if flags else None))
                                        with ui.element("div").classes("inc-case-links"):
                                            ui.link("Mở hồ sơ", f"/incident/{quote(incident_id, safe='')}").classes("sm-link")
                                            if r.get("monitor_id"):
                                                ext_link("Monitor ↗", f"{DD_BASE}/monitors/{quote(str(r['monitor_id']))}")
                        source_note("Cùng nguồn với mục \"Cần chú ý\" trên Tổng quan (bộ sưu tập operational_incidents).")

                    # Khoi C: da dong
                    group = view["group"]
                    pending = sum(1 for r in closed if _cached_flags(str(r.get("incident_id") or "")) is None)
                    counts = {name: len(tab_rows(closed, name)) for name in ("complete", "incomplete")}
                    counts["all"] = len(closed)
                    with panel("Hồ sơ đã đóng", f"{len(closed)} hồ sơ" + (
                            f" · {FARM_LABELS.get(view['farm'], view['farm'])}" if view["farm"] else "") + " · MongoDB"
                            ).classes("mongo-panel"):
                        with ui.element("div").classes("sm-tabs"):
                            for name, text in TAB_LABELS.items():
                                suffix = "…" if pending and name != "all" else ""
                                button = ui.element("button").classes("sm-tab" + (" active" if view["tab"] == name else "")
                                                                      ).props('type="button"')
                                with button:
                                    ui.label(f"{text} ({counts[name]}{suffix})")
                                button.on("click", lambda _e, n=name: (view.update(tab=n, page=0), results.refresh()))
                        if pending:
                            source_note(f"Đang kiểm tra đủ bằng chứng cho {pending} hồ sơ; số trong tab sẽ cập nhật.")
                        shown = []
                        for r in tab_rows(closed, view["tab"]):
                            flags = _cached_flags(str(r.get("incident_id") or ""))
                            if group == "all" or group_of_label(row_verdict(r, flags)[1]) == group:
                                shown.append(r)
                        if not data["rows"]:
                            state_panel("empty", "Chưa có sự cố nào", "Chạy một ca diễn tập để sinh hồ sơ.")
                        elif not shown:
                            state_panel("empty", "Không có hồ sơ khớp bộ lọc",
                                        "Đổi tab, nhà màng, kết luận hoặc bỏ lọc ca." if not pending
                                        else "Đang kiểm tra bằng chứng, vui lòng đợi vài giây.")
                        else:
                            pages = max(1, math.ceil(len(shown) / PAGE_SIZE))
                            view["page"] = min(view["page"], pages - 1)
                            page_rows = shown[view["page"] * PAGE_SIZE:(view["page"] + 1) * PAGE_SIZE]
                            rows_out = []
                            for r in page_rows:
                                incident_id = str(r.get("incident_id") or "")
                                flags = _cached_flags(incident_id)
                                level, label, reason = row_verdict(r, flags)
                                href = f"/incident/{quote(incident_id, safe='')}"

                                def when(h=href, r=r):
                                    ui.link(fmt_time(r.get("opened_at")), h).classes("sm-link")

                                def phases(flags=flags):
                                    ui.html(_dots_html(flags["dots"] if flags else None))

                                def verdict(level=level, label=label, reason=reason, r=r):
                                    with ui.element("div").classes("sm-inline"):
                                        status_chip(level, label).tooltip(reason)
                                        if r.get("synthetic") is True:
                                            status_chip("sim", "diễn tập")

                                def open_link(h=href):
                                    ui.link("Mở hồ sơ", h).classes("sm-link")

                                monitor = r.get("monitor_id")
                                rows_out.append([when, _scope_text(r), kind_name(r.get("kind")),
                                                 f"Monitor {monitor}" if monitor else "chưa ghi", phases, verdict,
                                                 format_duration(r.get("opened_at"), r.get("recovered_at"))
                                                 if level == "ok" else "—", open_link])
                            _table(["Thời điểm", "Nhà màng", "Loại", "Phát hiện bởi", "3 pha", "Kết luận", "Kéo dài", ""],
                                   rows_out, 860)
                            if pages > 1:
                                with ui.element("div").classes("sm-inline").style("margin-top:10px"):
                                    ui.button("Trang trước", on_click=lambda: (view.update(page=view["page"] - 1), results.refresh())
                                              ).props("flat dense no-caps" + ("" if view["page"] > 0 else " disable")
                                                      ).classes("sm-btn-quiet")
                                    ui.label(f"Trang {view['page'] + 1}/{pages} · {len(shown)} hồ sơ").classes("sm-note")
                                    ui.button("Trang sau", on_click=lambda: (view.update(page=view["page"] + 1), results.refresh())
                                              ).props("flat dense no-caps" + ("" if view["page"] < pages - 1 else " disable")
                                                      ).classes("sm-btn-quiet")
                        source_note("3 pha: Phát hiện, Điều tra (Datadog), Phản ứng (workflow và MongoDB). "
                                    "Kết luận tính theo bằng chứng phục hồi trong từng hồ sơ.")

                async def compute_flags():
                    """Kiem tra du buoc cho tung ho so nen, khong chan lan hien thi dau tien."""
                    if data["computing"]:
                        return
                    data["computing"] = True
                    try:
                        active, closed = split_rows(data["rows"] or [])
                        done = 0
                        for r in [*active, *closed]:
                            incident_id = str(r.get("incident_id") or "")
                            if not incident_id or _cached_flags(incident_id) is not None:
                                continue
                            await run.io_bound(_detail_flags, incident_id)
                            done += 1
                            if done % PAGE_SIZE == 0:
                                results.refresh()
                        if done:
                            results.refresh()
                    except Exception:
                        pass
                    finally:
                        data["computing"] = False

                async def load_dd():
                    data["dd"] = None
                    dd_block.refresh()
                    ids = [c["monitor_id"] for c in CASES.values() if c.get("monitor_id")]
                    try:
                        data["dd"] = await run.io_bound(read_monitor_overview, ids)
                    except Exception as exc:
                        data["dd"] = {"available": False, "reason": type(exc).__name__}
                    dd_block.refresh()

                async def load():
                    data["error"] = None
                    try:
                        rows = await run.io_bound(list_incidents, 500)
                        data["rows"] = await run.io_bound(_attach_verification, rows)
                    except Exception as exc:
                        data["error"] = f"Lỗi {type(exc).__name__}"
                    redraw()
                    if data["dd"] is None or not data["dd"].get("available"):
                        await load_dd()
                    else:
                        try:  # lam moi am tham (doc lai qua cache 30 giay), khong nhap nhay o "dang doc"
                            data["dd"] = await run.io_bound(read_monitor_overview, [
                                c["monitor_id"] for c in CASES.values() if c.get("monitor_id")])
                            dd_block.refresh()
                        except Exception:
                            pass
                    await compute_flags()

                results()
                ui.timer(0.1, load, once=True)
                ui.timer(REFRESH_LIST_SECONDS, load)


# ---------------------------------------------------------------------------
# Trang ho so
# ---------------------------------------------------------------------------
@ui.page("/incident/{incident_id}")
def incident_detail_page(incident_id: str):
    if not _guard():
        return
    ui.add_head_html(f"<style>{CUSTOM_CSS}{INC_CSS}</style>")
    sidebar(active="Incident")
    with ui.element("div").classes("main-content"):
        global_topbar("Sự cố", emoji="", show_farm_selector=False)
        with ui.element("div").classes("content-area inc-wrap"):
            ui.link("← Tất cả sự cố", "/incident").classes("sm-link").style("margin-bottom:10px;display:inline-block")
            holder = ui.element("div").classes("sm-stack")
            last_sig: dict[str, Any] = {"value": None}

            async def load(force: bool = False):
                if force or last_sig["value"] is None:
                    holder.clear()
                    with holder:
                        state_panel("loading", "Đang tải hồ sơ", "Đọc MongoDB và Datadog.")
                try:
                    tl = await run.io_bound(build_incident_timeline, incident_id)
                except Exception as exc:
                    holder.clear()
                    with holder:
                        state_panel("error", "Không đọc được hồ sơ",
                                    f"Lỗi {type(exc).__name__}. Kiểm tra MongoDB rồi thử lại.",
                                    action_label="Thử lại", on_action=lambda: load(True))
                    return
                inc = tl.get("incident") or {}
                try:
                    dd = await run.io_bound(read_incident_snapshot, inc) if inc else {"available": False}
                except Exception:
                    dd = {"available": False, "reason": "snapshot_failed"}
                sig = (inc.get("status"), len(tl.get("events") or []), str(inc.get("recovered_at")),
                       dd.get("monitor_state"), dd.get("latest_at"), dd.get("reason"),
                       len(dd.get("logs") or []), len(dd.get("events") or []))
                if not force and sig == last_sig["value"]:
                    return
                last_sig["value"] = sig
                holder.clear()
                with holder:
                    _render(tl, dd)

            ui.timer(0.1, load, once=True)
            ui.timer(REFRESH_DETAIL_SECONDS, load)


def _datadog_links(inc: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Link Datadog cua chinh ho so; moi link chi co khi co ID that."""
    links = [*_monitor_links(inc, False), *_workflow_links(inc, False), *_logs_link(inc)]
    traces = _trace_links(inc)
    links += traces[:5]
    links += [link for link in metric_links(inc) if not link[0].startswith("Dashboard")]
    dash = dashboard_window_link(inc)
    if dash:
        links.append(dash)
    return links


def _window_query(inc: dict[str, Any]) -> str:
    """from_ts/to_ts cua khung gio su co cho link Datadog; rong neu chua ro moc mo ho so."""
    window = metric_window(inc)
    return f"from_ts={_epoch_ms(window[0])}&to_ts={_epoch_ms(window[1])}&live=false" if window else ""


def _monitor_missing(dd: dict[str, Any] | None) -> bool:
    return (dd or {}).get("reason") == "monitor_not_found"


def _datadog_nav(inc: dict[str, Any], st: dict[str, Any], dd: dict[str, Any] | None = None
                 ) -> list[tuple[str, str, str | None]]:
    """Thẻ điều hướng tới đúng tài nguyên Datadog của hồ sơ. url None = chưa có ID thật hoặc không còn trên Datadog."""
    cards: list[tuple[str, str, str | None]] = []
    monitor = _monitor_id(inc, False)
    window = _window_query(inc)
    if monitor and _monitor_missing(dd):
        cards.append(("Xem monitor", f"ID {monitor} không có trong tổ chức Datadog đang dùng", None))
        cfg_monitor = _case_config(inc).get("monitor_id")
        if cfg_monitor and str(cfg_monitor) != monitor:
            cards.append(("Monitor hiện hành của ca (cấu hình ca)",
                          "Không phải monitor của hồ sơ này; chỉ để xem ca đang được giám sát thế nào",
                          f"{DD_BASE}/monitors/{quote(str(cfg_monitor))}"))
    else:
        cards.append(("Xem monitor",
                      f"Trạng thái và lịch sử cảnh báo của monitor {monitor}, đúng khung giờ sự cố" if monitor
                      else "Hồ sơ chưa ghi monitor",
                      f"{DD_BASE}/monitors/{quote(monitor)}" + (f"?{window}" if window else "") if monitor else None))
    workflow = _workflow_id(inc, False)
    execution = inc.get("last_workflow_execution_id")
    if workflow and execution:
        cards.append(("Xem lần chạy workflow", "Từng bước workflow đã chạy cho hồ sơ này",
                      f"{DD_BASE}/workflow/{quote(workflow)}?instance={quote(str(execution))}"))
    elif workflow:
        cards.append(("Xem lịch sử workflow",
                      f"Các lần chạy của workflow {_short(workflow, 8)}. Hồ sơ này chưa ghi lần chạy nào.",
                      f"{DD_BASE}/workflow/{quote(workflow)}"))
    else:
        cards.append(("Workflow", "Hồ sơ chưa ghi workflow", None))
    logs = _logs_link(inc)
    cards.append(("Tìm log của sự cố",
                  "Log có mã sự cố trong đúng khung giờ của sự cố" if logs else "Hồ sơ chưa có mã sự cố",
                  logs[0][1] if logs else None))
    for name, url, note in metric_links(inc):
        if name.startswith("Dashboard"):
            continue
        cards.append((f"Xem metric {name}", note, url))
    traces = _trace_links(inc)
    if traces:
        cards.append(("Mở trace APM", f"Đường đi của yêu cầu, trace {_short(traces[0][2], 6)}", traces[0][1]))
    else:
        cards.append(("Trace APM", "Hồ sơ chưa ghi trace_id, nên không có trace để mở", None))
    dash = dashboard_window_link(inc)
    cards.append(("Dashboard vận hành", "Dashboard SMIOT đúng khung giờ của sự cố" if dash else "Chưa xác định khung giờ",
                  dash[1] if dash else None))
    return cards


def _nav_grid(inc: dict[str, Any], st: dict[str, Any], dd: dict[str, Any] | None = None) -> None:
    with ui.element("div").classes("dd-grid"):
        for title, desc, url in _datadog_nav(inc, st, dd):
            if url:
                card = ui.element("a").classes("dd-card").props(
                    f'href="{html.escape(url, quote=True)}" target="_blank" rel="noopener"')
            else:
                card = ui.element("div").classes("dd-card off")
            with card:
                ui.label(title).classes("dd-card-t")
                ui.label(desc).classes("dd-card-d")
                if url:
                    ui.label("Mở trong Datadog ↗").classes("dd-card-go")


def _clip(text: Any, limit: int = 160) -> str:
    word = " ".join(str(text or "").split())
    return word if len(word) <= limit else word[:limit - 1] + "…"


def _dd_note(reason: Any) -> None:
    """Mot dong thong diep trung thuc cho mot phan Datadog khong doc duoc (theo bang dd_state)."""
    title, detail, _action = dd_state(reason)
    ui.label(f"{title}. {detail}").classes("sm-note")


def _verification_of(inc: dict[str, Any]) -> dict[str, Any] | None:
    return _unwrap_verification(inc.get("recovery_verification")) or _unwrap_verification(inc.get("recovery_evidence"))


def _phase_detect(inc: dict[str, Any], dd: dict[str, Any] | None, st: dict[str, Any], events: list[dict[str, Any]],
                  impact: dict[str, Any]) -> None:
    monitor = _monitor_id(inc, False)
    top = (dd or {}).get("reason")
    fetched = (dd or {}).get("fetched_at")
    keys_missing = dd_reason(top) == "keys_missing" if top else False
    note = (f"Datadog API, chỉ đọc, đọc lúc {fmt_time(fetched, with_date=False)}" if fetched and not keys_missing
            else "Datadog (chưa đọc được)")
    with phase_block(1, "Phát hiện", "datadog", note=note, has_evidence=st["has"][0]):
        if dd is None:
            state_panel("stale", "Chưa đọc được Datadog", "Các link bên dưới vẫn mở đúng tài nguyên.")
        elif keys_missing:
            dd_state_panel("keys_missing")
        with ui.element("div").classes("inc-two"):
            # Trai: the monitor, tach hai mốc thoi gian khac nhau
            with ui.element("div").classes("inc-card"):
                _block_title("Monitor của hồ sơ")
                ver = _verification_of(inc)
                recorded = None
                if ver and str(ver.get("monitor_state") or "").strip():
                    at = _hhmm(verified_at_of(inc, ver))
                    recorded = f"{str(ver['monitor_state']).strip()} (lúc {at or 'chưa ghi giờ'})"
                facts([("Tên monitor", (dd or {}).get("monitor_name") or None),
                       ("Mã monitor", monitor or "Hồ sơ chưa ghi monitor"),
                       ("Lúc xác minh phục hồi (bản ghi MongoDB)", recorded)])
                query = (dd or {}).get("monitor_query")
                if query:
                    ui.label("Điều kiện cảnh báo (Datadog)").classes("sm-fact-k")
                    ui.label(_clip(query)).classes("sm-code").tooltip(str(query))
                ui.label("Hiện tại (Datadog)").classes("sm-fact-k").style("margin-top:8px")
                if dd and dd.get("available"):
                    with ui.element("div").classes("sm-inline"):
                        status_chip(_monitor_level(dd.get("monitor_state")), str(dd.get("monitor_state") or "UNKNOWN"))
                        if dd.get("overall_state_modified"):
                            ui.label(f"đổi lần cuối {fmt_time(dd['overall_state_modified'])}").classes("sm-note")
                elif _monitor_missing(dd):
                    status_chip("stale", f"ID {monitor} không có trong tổ chức Datadog đang dùng")
                elif not monitor:
                    status_chip("none", "Hồ sơ chưa ghi monitor")
                else:
                    status_chip("none", dd_state(top)[0] if top else "Chưa đọc được")
                thresholds = (dd or {}).get("thresholds") or {}
                if thresholds:
                    ui.label("Ngưỡng: " + ", ".join(f"{k} {v}" for k, v in thresholds.items())).classes("sm-note")
            # Phai: metric phat hien
            with ui.element("div").classes("inc-card"):
                _block_title("Metric phát hiện (Datadog)")
                opts = dd_metric_options(inc, dd)
                if opts is not None:
                    ui.echart(opts).classes("sm-chart").style("height:210px")
                    source_note(f"Datadog metric {dd.get('metric')}, {len(dd.get('series') or [])} điểm, giờ Việt Nam. "
                                "Vạch đứt: các mốc của hồ sơ.")
                elif dd and dd.get("metric_error"):
                    if not keys_missing:
                        _dd_note(dd["metric_error"])
                elif dd and dd.get("metric"):
                    window = metric_window(inc)
                    span = (f"{fmt_time(window[0], with_date=False)}–{fmt_time(window[1], with_date=False)} "
                            f"ngày {window[0].astimezone(VN_TZ).strftime('%d/%m')}") if window else "khung giờ của sự cố"
                    ui.label(f"Datadog không có điểm metric trong khung {span}.").classes("sm-note")
                elif dd is not None and not keys_missing:
                    ui.label("Loại sự cố này chưa có metric phát hiện được cấu hình.").classes("sm-note")
                else:
                    ui.label("Chưa có số liệu metric từ Datadog (xem thông báo ở đầu pha).").classes("sm-note")
        # Su kien monitor
        if not keys_missing:
            _block_title("Datadog đã báo")
        if dd and dd.get("events"):
            _table(["Lúc", "Sự kiện monitor"], [[fmt_time(e["ts"]), e["title"]] for e in dd["events"]], 420)
        elif dd and dd.get("events_error"):
            if not keys_missing:
                _dd_note(dd["events_error"])
        elif dd and monitor and "events" in dd:
            ui.label("Datadog không có sự kiện monitor trong khung giờ này.").classes("sm-note")
        elif not monitor:
            _missing("monitor")
        facts([
            ("Bắt đầu lỗi", fmt_time(impact.get("fault_started_at") or inc.get("fault_started_at"))),
            ("Mở hồ sơ lúc", fmt_time(inc.get("opened_at"))),
            ("Phát hiện lúc", fmt_time(inc.get("detected_at"))),
            ("Mở bởi", inc.get("opened_by")),
        ])
        findings = [e for e in events if e.get("kind") == "telemetry_finding"]
        if findings:
            _block_title("Phát hiện của bộ phân tích")
            _table(["Lúc", "Nội dung"], [[fmt_time(e.get("ts")), str(e.get("summary") or "")] for e in findings[:10]], 420)
        with ui.element("div").classes("inc-links"):
            window = _window_query(inc)
            if monitor and not _monitor_missing(dd):
                ext_link("Mở monitor đúng khung giờ ↗", f"{DD_BASE}/monitors/{quote(monitor)}" + (f"?{window}" if window else ""))
            elif _monitor_missing(dd) and _case_config(inc).get("monitor_id"):
                ext_link("Monitor hiện hành của ca (cấu hình ca) ↗",
                         f"{DD_BASE}/monitors/{quote(str(_case_config(inc)['monitor_id']))}")
            explorer = [link for link in metric_links(inc) if not link[0].startswith("Dashboard")]
            if explorer:
                ext_link("Mở metric trong Explorer ↗", explorer[0][1])


def _phase_investigate(inc: dict[str, Any], tl: dict[str, Any], dd: dict[str, Any] | None, st: dict[str, Any],
                       events: list[dict[str, Any]], impact: dict[str, Any], lots: list[dict[str, Any]]) -> None:
    farm_key = inc.get("farm_key")
    has_farm = bool(farm_key) and farm_key != "_system"
    top = (dd or {}).get("reason")
    keys_missing = dd_reason(top) == "keys_missing" if top else False
    with phase_block(2, "Điều tra", "mixed", note="Datadog (log, trace, workflow) · bối cảnh MongoDB",
                     has_evidence=st["has"][2] or st["has"][1]):
        runs = len(st["observations"]) or (1 if inc.get("last_workflow_execution_id") else 0)
        result_label, result_code = disposition_label(inc.get("last_workflow_disposition"))
        logs = (dd or {}).get("logs")
        if isinstance(logs, list):
            log_meta = "Datadog, khớp mã sự cố" + (", còn nữa" if dd.get("logs_more") else "")
        elif dd and dd.get("logs_error"):
            log_meta = dd_state(dd["logs_error"])[0]
        else:
            log_meta = "Chưa đọc được Datadog"
        with stats():
            stat("Log khớp đúng mã sự cố", len(logs) if isinstance(logs, list) else None, None, log_meta)
            stat("Trace gắn đúng mã sự cố", len(st["traces"]) if st["traces"] else 0, None,
                 "trace_id ghi trong hồ sơ" if st["traces"] else "Chưa có trace_id liên kết; trace cùng giờ chỉ là bối cảnh")
            stat("Workflow ghi trong hồ sơ", runs if runs else 0, None,
                 f"workflow {_short(_workflow_id(inc, False) or '', 8)}" if _workflow_id(inc, False)
                 else "Hồ sơ chưa ghi workflow")
            stat("Kết quả gần nhất", " / ".join(str(x) for x in (inc.get("last_workflow_status"), result_label) if x) or None,
                 None, result_code or ("Chưa có lần chạy" if not runs else None))
        # Log
        if not keys_missing:
            _block_title("Log gần nhất có mã sự cố (Datadog)")
        if isinstance(logs, list) and logs:
            _table(["Lúc", "Service", "Nội dung"], [[fmt_time(row["ts"]), row["service"] or "—", row["message"]]
                                                   for row in logs], 460)
            logs_url = (_logs_link(inc) or [(None, None, None)])[0][1]
            if logs_url:
                ext_link("Xem tất cả log ↗", logs_url)
        elif isinstance(logs, list):
            ui.label("Datadog chưa có log chứa đúng mã sự cố trong khung giờ này; không dùng log cùng giờ để thay thế.").classes("sm-note")
        elif dd and dd.get("logs_error") and not keys_missing:
            _dd_note(dd["logs_error"])
        # Trace
        if st["traces"]:
            _block_title("Trace APM")
            _table(["Trace", "Mở"], [[_short(str(t), 8), (lambda t=t: ext_link("Mở trace ↗", f"{DD_BASE}/apm/trace/{quote(str(t))}"))]
                                     for t in st["traces"][:5]], 320)
            if len(st["traces"]) > 5:
                ui.label(f"Hiện 5 trong {len(st['traces'])} trace.").classes("sm-note")
        else:
            ui.label("Chưa có trace_id gắn đúng mã sự cố; các trace cùng khung giờ chỉ là bối cảnh điều tra.").classes("sm-note")
        # Workflow
        if st["observations"]:
            _block_title("Các lần chạy workflow đã ghi")
            rows_out = []
            for o in st["observations"][-10:]:
                def run_link(o=o):
                    wf, ex = o.get("workflow_id"), o.get("execution_id")
                    if wf and ex:
                        ext_link(_short(str(ex), 8), f"{DD_BASE}/workflow/{quote(str(wf))}?instance={quote(str(ex))}")
                    else:
                        ui.label("—")
                code = o.get("disposition")
                shown = disposition_label(code)[0] or "—"
                rows_out.append([fmt_time(o.get("observed_at")), run_link, str(o.get("status") or "—"), shown])
            _table(["Ghi lúc", "Lần chạy", "Trạng thái", "Cách xử lý"], rows_out, 460)
        # Boi canh MongoDB
        with ui.element("div").classes("inc-mongo"):
            _block_title("Bối cảnh vận hành (MongoDB)")
            farm_text = FARM_LABELS.get(str(farm_key), str(farm_key)) if has_farm else "Toàn hệ thống"
            facts([("Nhà màng", farm_text), ("Node", inc.get("node_id")),
                   ("Lô ảnh hưởng", ", ".join(str(lot.get("lot_id")) for lot in lots if lot.get("lot_id") is not None)
                    or None),
                   ("Mẫu trong cửa sổ", len(st["points"]))])
            if not lots:
                ui.label(f"Chưa xác định lô bị ảnh hưởng ({tl.get('affected_lots_status') or UNKNOWN}); không ghép lô khi chưa có quan hệ thật.").classes("sm-note")
            if has_farm:
                ui.link("Mở farm", f"/?farm={quote(str(farm_key), safe='')}").classes("sm-link").style("margin-top:6px;display:inline-block")
            chart = measure_chart_options(inc, events, dd=dd)
            _block_title("Độ ẩm đất quanh thời điểm sự cố: MongoDB (xanh) và Datadog (tím)")
            if chart is None:
                _missing("mẫu số đo trong cửa sổ sự cố")
            else:
                ui.echart(chart).classes("sm-chart").style("height:240px")
                soil = (dd or {}).get("soil_series")
                source_note(f"MongoDB, telemetry (độ ẩm đất), {len(st['points'])} mẫu, từ {fmt_time(tl.get('window_start'))} "
                            f"đến {fmt_time(tl.get('window_end'))}, giờ Việt Nam. Dải cam: từ lúc lỗi đến lúc phục hồi hoặc hiện tại; "
                            f"dải xám: thiếu mẫu. Thiết bị ảo." + (f" Datadog: {len(soil)} điểm." if soil else ""))
            soil_query = (dd or {}).get("soil_query")
            if soil_query and not (dd or {}).get("soil_series"):
                ui.label("Datadog không có điểm độ ẩm đất trong khung giờ của sự cố này; chỉ vẽ dữ liệu MongoDB.").classes("sm-note")
            elif dd and dd.get("soil_error") and not keys_missing:
                _dd_note(dd["soil_error"])
            chart_data = build_impact_chart_data(inc, events, impact)
            with stats():
                for card in chart_data["cards"]:
                    stat(card["label"], card["value"], (card.get("unit") or "").strip() or None, card.get("note") or None)
            with ui.expansion("Chất lượng dữ liệu theo phút").classes("w-full"):
                _quality_chart(chart_data["quality"])
        _block_title("Mở trong Datadog")
        _nav_grid(inc, st, dd)


def _phase_respond(inc: dict[str, Any], st: dict[str, Any], events: list[dict[str, Any]], impact: dict[str, Any],
                   rec: dict[str, Any]) -> None:
    level, label, reason = st["verdict"]
    kind = inc.get("kind")
    with phase_block(3, "Phản ứng", "mongo", note="workflow Datadog quyết định · MongoDB ghi nhận",
                     has_evidence=st["has"][3] or st["has"][4]):
        # Quyet dinh
        _block_title("Quyết định")
        result_label, result_code = disposition_label(inc.get("last_workflow_disposition"))
        safe_at = inc.get("safe_at") or impact.get("safe_at")
        facts([("Vào trạng thái an toàn", fmt_time(safe_at) if safe_at else None),
               ("Hành động gần nhất", inc.get("last_action")),
               ("Cách xử lý của workflow", result_label)])
        if result_code:
            ui.label(result_code).classes("sm-code")
        if st["decisions"]:
            _table(["Lúc", "Quyết định"], [[fmt_time(e.get("ts")), str(e.get("summary") or "")] for e in st["decisions"][:20]], 420)
            blocked = count_blocked(events)
            ui.label(f"{blocked} đề xuất tưới bị chặn." if blocked else "Không có đề xuất bị chặn trong hồ sơ.").classes("sm-note")
        else:
            _missing("quyết định xử lý")
        rule = (inc.get("scenario_response") if kind == "scenario_event" else SAFETY_RULE_BY_KIND.get(kind))
        if rule:
            ui.label(f"Quy tắc của loại sự cố này (cấu hình, không phải bản ghi của hồ sơ): {rule}").classes("sm-note")

        # Lenh va ACK
        _block_title("Lệnh và ACK")
        if not st["commands"]:
            _missing("lệnh điều khiển nào")
        for cmd in st["commands"]:
            is_hold = cmd["origin"] == "action_ledger" and cmd["label"] == ACTION_LABELS["HOLD"]
            with ui.element("div").classes("inc-cmd"):
                with ui.element("div").classes("inc-cmd-head"):
                    ui.label(cmd["label"]).classes("sm-h2")
                    ui.label(_short(cmd["command_id"], 10)).classes("sm-id").tooltip(cmd["command_id"])
                command_chain(cmd["status"], sent_at=cmd["sent_at"], acked_at=cmd["acked_at"],
                              verified_at=cmd["verified_at"],
                              verify_hint="Không có bước đọc lại riêng cho lệnh này" if is_hold else None)
        for text in command_explanations(st["commands"], events, st["verdict"]):
            ui.label(text).classes("sm-note")
        if st["commands"]:
            source_note("MongoDB, action_ledger và scenario_run_events của riêng hồ sơ này. ACK không đồng nghĩa đã xác minh kết quả. Thiết bị ảo.")

        # Bang chung phuc hoi
        _block_title("Bằng chứng phục hồi")
        with ui.element("div").classes("sm-inline"):
            status_chip(level, label)
            ui.label(reason).classes("sm-note")
        if samples_contradict(rec):
            with ui.element("div").classes("sm-banner act"):
                ui.label("Số đo quay lại giá trị lỗi sau CLEAR: kết luận được hạ xuống \"Chưa xác minh\".")
        ver = inc.get("recovery_verification") or inc.get("recovery_evidence")
        at = verified_at_of(inc, _unwrap_verification(ver))
        facts([("Mốc phục hồi ghi", fmt_time(inc.get("recovered_at")) if inc.get("recovered_at") else None),
               ("Mốc xóa HOLD", fmt_time(rec.get("clear_ts")) if rec.get("clear_ts") else None)])
        after = rec.get("samples_after_clear") or []
        with ui.element("div").classes("inc-two"):
            with ui.element("div").classes("inc-card"):
                _block_title("Verifier đã kiểm (bản ghi MongoDB" + (
                    f" lúc {fmt_time(at) if at else 'chưa ghi giờ'})" if ver else ")")
                    + ("" if level == "ok" else " · chưa đủ điều kiện"))
                if ver:
                    ui.label(format_recovery_evidence(ver, kind, at)).classes("sm-note")
                else:
                    _missing("bản ghi xác minh")
            with ui.element("div").classes("inc-card"):
                _block_title("5 mẫu đầu tiên sau mốc CLEAR (MongoDB)")
                if after:
                    _table(["Lúc", "Giá trị", "Khác giá trị lỗi"],
                           [[fmt_time(e.get("ts")), _fmt(e.get("value")),
                             {True: "có", False: "không", None: "chưa xác định"}.get(e.get("differs_from_fault"), "chưa xác định")]
                            for e in after], 320)
                else:
                    _missing("mẫu sau mốc CLEAR")
        if not ver and not after:
            _missing("bằng chứng phục hồi")


def command_explanations(commands: list[dict[str, Any]], events: list[dict[str, Any]] | None,
                         verdict: tuple[str, str, str]) -> list[str]:
    """Cau giai thich de nguoi doc khong phai suy luan (HOLD chi can ACK; thieu lenh HOLD). Ham thuan."""
    out: list[str] = []
    ledger = [c for c in commands if c.get("origin") == "action_ledger"]
    clear = next((c for c in ledger if c["label"] == ACTION_LABELS["CLEAR"] and c.get("verified_at")), None)
    hold = [c for c in ledger if c["label"] == ACTION_LABELS["HOLD"]]
    if clear and verdict[0] == "ok":
        out.append(f"Kết luận phục hồi dựa trên lệnh CLEAR đã xác minh lúc {fmt_time(clear['verified_at'], with_date=False)}. "
                   "Lệnh HOLD chỉ cần ACK.")
    if count_blocked(events) and not hold:
        out.append("Hồ sơ này không có lệnh HOLD trong action_ledger; chỉ có quyết định chặn tưới.")
    return out


def _render(tl: dict[str, Any], dd: dict[str, Any] | None = None) -> None:
    if not tl.get("found"):
        state_panel("empty", "Không tìm thấy sự cố", str(tl.get("incident_id") or ""))
        return
    inc = tl.get("incident") or {}
    events = tl.get("events") or []
    impact = tl.get("impact") or {}
    rec = tl.get("recovery_evidence") or {}
    lots = tl.get("affected_lots") or []
    st = case_file_state(tl, dd)
    level, label, reason = st["verdict"]
    kind = inc.get("kind")

    slot = page_header(kind_name(kind), incident_headline(kind, inc.get("node_id"), inc.get("scenario_title")))
    with slot:
        status_chip(level, label).tooltip(reason)
        if _monitor_missing(dd):
            status_chip("stale", "Monitor của hồ sơ không còn trên Datadog")
        elif _monitor_id(inc, False):
            status_chip("info", "Giám sát bởi Datadog")
        if tl.get("synthetic"):
            status_chip("sim", "diễn tập")
        case_number = case_for_kind(kind)
        if case_number:
            status_chip("none", f"Ca {case_number}")
    ui.label(str(tl.get("incident_id"))).classes("sm-id")
    if tl.get("synthetic"):
        sim_badge("Diễn tập: dữ liệu mô phỏng, không phải số đo từ thiết bị thật")

    with panel("Ba pha của hồ sơ", reason):
        with ui.element("div").classes("sm-phases"):
            for phase in st["phases"]:
                with ui.element("div"):
                    ui.label(phase["title"]).classes("ph-t" + (" mongo" if phase["owner"] == "mongo" else ""))
                    ui.label(phase["line1"]).classes("ph-1")
                    if phase["line2"]:
                        ui.label(phase["line2"]).classes("ph-2")
        with ui.expansion("Chi tiết sáu bước bằng chứng").classes("w-full"):
            evidence_chain(st["chain"])

    _phase_detect(inc, dd, st, events, impact)
    _phase_investigate(inc, tl, dd, st, events, impact, lots)
    _phase_respond(inc, st, events, impact, rec)

    _timeline_expansion(events, tl.get("pipeline_stage_count", "?"))


def _quality_chart(q: dict[str, Any]) -> None:
    """Cot chong chat luong du lieu theo phut."""
    if not q.get("known"):
        ui.label(q.get("note") or f"Chưa truy vấn được telemetry: {UNKNOWN}").classes("sm-note")
        return
    if not q["labels"]:
        ui.label("Không có mẫu telemetry hay khoảng thiếu trong cửa sổ truy vấn.").classes("sm-note")
        return
    totals = q["totals"]
    ui.label("Tổng: " + " · ".join(
        f"{QUALITY_LABELS[k]} {totals[k] if totals[k] is not None else UNKNOWN}" for k in QUALITY_KEYS)).classes("sm-note")
    option = echart_base()
    option["legend"] = {**option["legend"], "bottom": 0, "top": None}
    option["grid"] = {**option["grid"], "bottom": 48}
    option["xAxis"] = {**option["xAxis"], "type": "category", "data": q["labels"]}
    option["yAxis"] = {**option["yAxis"], "type": "value", "minInterval": 1}
    option["series"] = [{"type": "bar", "name": QUALITY_LABELS[k], "stack": "quality", "barMaxWidth": 18,
                         "itemStyle": {"color": QUALITY_COLORS[k]}, "data": q["series"][k]} for k in QUALITY_KEYS]
    ui.echart(option).classes("sm-chart").style("height:240px")
    if q.get("note"):
        ui.label(q["note"]).classes("sm-note")
    source_note("MongoDB, telemetry theo phút trong cửa sổ sự cố.")


def _timeline_expansion(events: list[dict[str, Any]], stage_count: Any) -> None:
    rows = [e for e in events if e.get("kind") not in {"telemetry_sample"}][:MAX_EVENT_ROWS]
    with panel("Dòng thời gian sự kiện", f"{len(rows)} mốc, không gồm từng mẫu số đo"):
        if not rows:
            _missing("sự kiện nào")
            return
        with ui.expansion("Xem toàn bộ dòng thời gian").classes("w-full"):
            _table(["Lúc", "Nguồn", "Sự kiện"],
                   [[fmt_time(e.get("ts")), str(e.get("source_collection") or ""), str(e.get("summary") or "")]
                    for e in rows], 520)
        source_note(f"MongoDB, một aggregation {stage_count} stage ($unionWith) trên các bộ sưu tập của hồ sơ.")
