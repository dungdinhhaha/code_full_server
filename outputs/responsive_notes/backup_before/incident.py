"""pages/incident.py - Hop den su co: danh sach /incident, chi tiet /incident/{id} (chi admin).

Chia vai: Datadog = dieu tra (phat hien, nguyen nhan, workflow, log, trace);
MongoDB = tac dong len trang trai; app = bang dieu huong (tom tat ngan, dan sang Datadog).
Chi doc qua 2 ham cua service.incident_blackbox (list_incidents, build_incident_timeline).
Khong truy van Mongo truc tiep, khong bia link: moi link chi hien khi du lieu co gia tri.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from nicegui import app, run, ui

from pages.home import CUSTOM_CSS, global_topbar, sidebar
from pages.login import check_login
from service.incident_blackbox import CASES, UNKNOWN, build_incident_timeline, case_for_kind, latest_by_case, list_incidents

DD_BASE = "https://app.datadoghq.com"
DD_DASHBOARD = f"{DD_BASE}/dashboard/nkc-685-vw8"
MAX_EVENT_ROWS = 500
MAX_GAP_MINUTES = 1440  # chan so phut cua mot khoang thieu mau khi ve bieu do
REFRESH_LIST_SECONDS = 10
REFRESH_DETAIL_SECONDS = 20

SRC_MONGO = "MongoDB"
SRC_DATADOG = "Datadog →"

# Su kien trong nhat ky MongoDB ma nguon thuc su la Datadog (mốc phat hien theo monitor): an khoi nhat ky, xem cau 2.
DATADOG_SOURCED_KINDS = frozenset({"detected"})

QUALITY_KEYS = ("valid", "abnormal", "missing")
QUALITY_LABELS = {"valid": "Mẫu hợp lệ", "abnormal": "Mẫu bất thường", "missing": "Phút thiếu mẫu"}
QUALITY_COLORS = {"valid": "#0f766e", "abnormal": "#dc2626", "missing": "#94a3b8"}

SAFETY_RULE_BY_KIND = {
    "soil_humidity_flatline": "Đề xuất tưới bị chặn, giữ HOLD cho đến khi dữ liệu đáng tin trở lại.",
    "false_offline": "Từ chối restart vì dữ liệu vẫn vào MongoDB, không có lý do restart.",
    "service_down": "Chỉ khởi động app sau khi kiểm tra MongoDB và MQTT đã khỏe.",
}

INC_CSS = """
.inc-wrap { max-width:1280px; }
.inc-head { display:flex; flex-wrap:wrap; align-items:center; gap:10px 14px; margin-bottom:14px; }
.inc-id { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:17px; font-weight:700;
  color:#0f172a; word-break:break-all; }
.inc-pill { font-size:12px; font-weight:600; padding:3px 10px; border-radius:999px; background:#e2e8f0; color:#334155; }
.inc-pill-ok { background:#dcfce7; color:#166534; }
.inc-pill-warn { background:#fef3c7; color:#92400e; }
.inc-pill-alert { background:#fee2e2; color:#991b1b; }
.inc-main { min-width:0; width:100%; }
.inc-panel { background:#fff; border:1px solid #e2e8f0; border-radius:10px; padding:14px 16px; margin-bottom:14px; }
.inc-panel-title { font-weight:700; font-size:14px; color:#0f172a; margin-bottom:10px; }
.inc-facts { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:10px 18px; }
.inc-fact-k { font-size:11px; color:#64748b; }
.inc-fact-v { font-size:13px; color:#0f172a; word-break:break-word; }
.inc-group { border:1px solid #e2e8f0; border-radius:8px; padding:10px 12px; margin-bottom:10px; }
.inc-group-title { font-size:12px; font-weight:700; color:#475569; margin-bottom:6px; }
.inc-link { display:block; font-size:12.5px; color:#1d4ed8; padding:4px 0; word-break:break-all; }
.inc-link:hover { text-decoration:underline; }
.inc-banner { background:#fffbeb; color:#92400e; border:1px solid #fcd34d; border-radius:8px;
  padding:8px 12px; font-weight:600; font-size:12.5px; margin-bottom:14px; }
.inc-muted { font-size:12px; color:#64748b; }
.inc-line { font-size:12.5px; color:#334155; margin-bottom:3px; word-break:break-word; }
.inc-event { font-size:12.5px; color:#0f172a; border-left:3px solid #94a3b8; padding:4px 0 4px 10px; }
.inc-table { width:100%; }
.inc-src { display:inline-block; font-size:10.5px; font-weight:700; padding:2px 8px; border-radius:4px;
  color:#fff; margin:0 6px 6px 0; vertical-align:middle; }
.inc-src-mongo { background:#16a34a; }
.inc-src-dd { background:#7c3aed; }
.inc-top { background:#fff; border:1px solid #e2e8f0; border-radius:10px; padding:14px 16px; margin-bottom:14px; }
.inc-summary { font-size:14px; color:#1e293b; line-height:1.6; margin:4px 0 12px; }
.inc-dd-row { display:flex; flex-wrap:wrap; align-items:center; gap:8px; }
.inc-dd-btn { font-size:12.5px; font-weight:600; color:#5b21b6; background:#f5f3ff; border:1px solid #c4b5fd;
  border-radius:6px; padding:5px 10px; text-decoration:none; }
.inc-dd-btn:hover { background:#ede9fe; }
.inc-qtable { display:grid; grid-template-columns:minmax(150px,1fr) minmax(0,2.4fr) 130px 170px; margin-bottom:14px;
  border:1px solid #e2e8f0; border-radius:8px; overflow:hidden; }
.inc-qhead { font-size:11px; font-weight:700; color:#64748b; padding:6px 10px; background:#f8fafc; }
.inc-qcell { font-size:12.5px; color:#0f172a; padding:8px 10px; border-top:1px solid #e2e8f0; word-break:break-word; }
.inc-qq { font-weight:600; }
.inc-cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; margin-bottom:12px; }
.inc-card { border:1px solid #e2e8f0; border-radius:8px; padding:10px 12px; }
.inc-card-v { font-size:20px; font-weight:700; color:#0f172a; }
@media (max-width:760px) { .inc-qtable { grid-template-columns:1fr; } .inc-qhead { display:none; } }
.inc-case-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px; margin-bottom:20px; }
.inc-case { position:relative; background:#fff; border:1px solid #e2e8f0; border-radius:10px;
  padding:14px 16px 12px 20px; cursor:pointer; transition:border-color .15s, box-shadow .15s; }
.inc-case::before { content:""; position:absolute; left:0; top:12px; bottom:12px; width:4px;
  border-radius:0 4px 4px 0; background:var(--accent); }
.inc-case:hover { border-color:#94a3b8; }
.inc-case-on { border-color:var(--accent); box-shadow:0 0 0 1px var(--accent); }
.inc-case-title { font-weight:700; font-size:15px; color:#0f172a; }
.inc-case-sum { font-size:13px; color:#475569; line-height:1.5; margin:4px 0 12px; }
.inc-strip { display:flex; flex-wrap:wrap; gap:4px; margin-bottom:6px; min-height:14px; }
.inc-run { width:14px; height:14px; border-radius:3px; box-sizing:border-box; }
.inc-run-ok { background:var(--accent); }
.inc-run-open { background:#fff; border:2px solid #f59e0b; }
.inc-case-meta { font-size:12.5px; color:#334155; }
.inc-case-links { display:flex; flex-wrap:wrap; gap:14px; margin-top:10px; }
.inc-case-link { font-size:12.5px; font-weight:600; color:#5b21b6; text-decoration:none; }
.inc-case-link:hover { text-decoration:underline; }
.inc-list-head { display:flex; flex-wrap:wrap; align-items:center; gap:10px 14px; margin:2px 0 10px; }
.inc-chip { font-size:12.5px; font-weight:600; color:#0f172a; background:#f1f5f9; border-radius:999px; padding:3px 12px; }
.inc-id-mono { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:12.5px; color:#0f172a; }
.inc-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:7px; }
.inc-dot-ok { background:#16a34a; }
.inc-dot-open { background:#f59e0b; }
.inc-ca { font-weight:700; }
.inc-ca-1 { color:#b45309; }
.inc-ca-2 { color:#0f766e; }
.inc-ca-3 { color:#475569; }
"""


def _fmt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S UTC")
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


def incident_headline(kind: str | None, node_id: Any = None) -> str:
    """Mot cau tom tat cho nguoi khong chuyen."""
    if kind == "soil_humidity_flatline":
        return f"Cảm biến độ ẩm{_node_phrase(node_id)} báo một giá trị đứng yên."
    if kind == "false_offline":
        return "Giao diện báo thiết bị offline sai trong khi dữ liệu vẫn vào MongoDB."
    if kind == "service_down":
        return "Dịch vụ smiot.service đã dừng."
    return UNKNOWN


def incident_summary(kind: str | None, node_id: Any = None) -> str:
    """Tom tat 1-2 cau theo kind cho dau trang trang chi tiet."""
    head = incident_headline(kind, node_id)
    if kind == "soil_humidity_flatline":
        return f"{head} Hệ thống đã giữ chế độ an toàn, không tưới, cho đến khi dữ liệu trở lại bình thường."
    if kind == "false_offline":
        return f"{head} Hệ thống từ chối restart không cần thiết vì dữ liệu vẫn đang được ghi nhận."
    if kind == "service_down":
        return f"{head} Hệ thống chỉ khởi động lại sau khi kiểm tra an toàn."
    return "Loại sự cố này chưa có mô tả trên trang; xem chi tiết trong Datadog."


def _monitor_id(inc: dict[str, Any]) -> str | None:
    case = CASES.get(case_for_kind(inc.get("kind")), {})
    monitor = inc.get("monitor_id") or case.get("monitor_id")
    return str(monitor) if monitor else None


def _workflow_id(inc: dict[str, Any]) -> str | None:
    case = CASES.get(case_for_kind(inc.get("kind")), {})
    workflow = inc.get("workflow_id") or case.get("workflow_id")
    return str(workflow) if workflow else None


def _monitor_links(inc: dict[str, Any]) -> list[tuple[str, str, str]]:
    monitor = _monitor_id(inc)
    return [(f"Monitor {monitor}", f"{DD_BASE}/monitors/{quote(monitor)}", monitor)] if monitor else []


def _execution_links(inc: dict[str, Any]) -> list[tuple[str, str, str]]:
    workflow, execution = _workflow_id(inc), inc.get("last_workflow_execution_id")
    if not (workflow and execution):
        return []
    return [(f"Execution {_short(str(execution), 8)}",
             f"{DD_BASE}/workflow/{quote(workflow)}?instance={quote(str(execution))}", str(execution))]


def _workflow_links(inc: dict[str, Any]) -> list[tuple[str, str, str]]:
    workflow = _workflow_id(inc)
    if not workflow:
        return []
    return [(f"Workflow {_short(workflow, 8)}", f"{DD_BASE}/workflow/{quote(workflow)}", workflow),
            *_execution_links(inc)]


def _logs_link(inc: dict[str, Any]) -> list[tuple[str, str, str]]:
    inc_id = str(inc.get("incident_id") or inc.get("_id") or "")
    if not inc_id:
        return []
    q = f"@incident.id:{inc_id}"
    return [("Logs của sự cố", f"{DD_BASE}/logs?query={quote(q)}", q)]


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
# Chi la lien ket dieu huong sang Datadog; app khong ve lai metric.
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
    return utc.strftime("%H:%M:%S UTC") if utc else None


def format_recovery_evidence(verification: Any, kind: str | None = None) -> str:
    """Bang chung phuc hoi -> cau tieng Viet doc duoc. Ham thuan, khong in dict tho, khong bia so.

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
        parts.append(f"Monitor {monitor.strip()}")

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
        {"question": "Chuyện gì xảy ra?", "answer": incident_headline(kind, inc.get("node_id")),
         "sources": [SRC_DATADOG], "links": _monitor_links(inc)},
        {"question": "Phát hiện lúc nào?", "answer": detected_text,
         "sources": [SRC_MONGO, SRC_DATADOG], "links": _monitor_links(inc)},
        {"question": "Bằng chứng gốc là gì?", "answer": evidence_text,
         "sources": [SRC_DATADOG], "links": [*_logs_link(inc), *_first_trace_link(inc)]},
        {"question": "Lô nào bị ảnh hưởng?", "answer": lot_text,
         "sources": [SRC_MONGO], "links": []},
        {"question": "Vì sao chọn hành động đó?", "answer": SAFETY_RULE_BY_KIND.get(kind, UNKNOWN),
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
# Trang danh sach
# ---------------------------------------------------------------------------
CASE_ACCENT = {1: "#b45309", 2: "#0f766e", 3: "#475569"}
STATE_DONE = "Đã phục hồi"
STATE_OPEN = "Đang xử lý"


def case_runs(rows: list[dict[str, Any]] | None) -> dict[int, list[dict[str, Any]]]:
    """Gom cac lan dien tap theo ca (rows da sap xep moi nhat truoc). Kind la -> bo qua."""
    out: dict[int, list[dict[str, Any]]] = {number: [] for number in CASES}
    for row in rows or []:
        number = case_for_kind(row.get("kind"))
        if number in out:
            out[number].append(row)
    return out


def run_state(row: dict[str, Any]) -> str:
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


def case_summary_text(runs: list[dict[str, Any]]) -> str:
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
        out.append({
            "id": incident_id, "id_short": f"…{incident_id[-8:]}" if len(incident_id) > 8 else incident_id,
            "case_no": number or 0, "case": f"Ca {number}" if number else "—",
            "scope": scope_label(row), "state": run_state(row),
            "state_ok": row.get("status") == "recovered",
            "opened_at": _fmt(row.get("opened_at")),
            "duration": format_duration(row.get("opened_at"), row.get("recovered_at")),
        })
    return out


LIST_COLUMNS = [
    {"name": "case", "label": "Ca", "field": "case", "align": "left"},
    {"name": "id_short", "label": "Mã sự cố", "field": "id_short", "align": "left"},
    {"name": "scope", "label": "Phạm vi", "field": "scope", "align": "left"},
    {"name": "state", "label": "Trạng thái", "field": "state", "align": "left"},
    {"name": "opened_at", "label": "Mở lúc", "field": "opened_at", "align": "left"},
    {"name": "duration", "label": "Xử lý trong", "field": "duration", "align": "left"},
]


def _case_card(number: int, case: dict[str, Any], runs: list[dict[str, Any]], selected: bool, on_click) -> None:
    latest = runs[0] if runs else {"kind": case["kind"]}
    card = ui.element("div").classes("inc-case" + (" inc-case-on" if selected else ""))
    card.style(f"--accent:{CASE_ACCENT.get(number, '#475569')}")
    card.on("click", on_click)
    with card:
        ui.label(case["title"]).classes("inc-case-title")
        ui.label(case["summary"]).classes("inc-case-sum")
        with ui.element("div").classes("inc-strip"):
            for row in reversed(runs[:12]):  # cu -> moi, ben phai la lan gan nhat
                done = row.get("status") == "recovered"
                ui.element("span").classes("inc-run " + ("inc-run-ok" if done else "inc-run-open")) \
                    .tooltip(f"{_fmt(row.get('opened_at'))}: {run_state(row).lower()}")
        ui.label(case_summary_text(runs)).classes("inc-case-meta")
        with ui.element("div").classes("inc-case-links"):
            for label, url, tip in [*_monitor_links(latest)[:1], *_workflow_links(latest)[:1]]:
                link = ui.link(label, url, new_tab=True).classes("inc-case-link").props(f'title="{tip}"')
                link.on("click.stop", lambda e: None)  # bam link khong kich hoat bo loc


@ui.page("/incident")
def incident_list_page():
    if not _guard():
        return
    ui.add_head_html(f"<style>{CUSTOM_CSS}{INC_CSS}</style>")
    sidebar(active="Incident")
    with ui.element("div").classes("main-content"):
        global_topbar("Hộp đen sự cố", "🛰️")
        with ui.element("div").classes("content-area inc-wrap"):
            selected_case = {"value": 0}
            holder = ui.element("div").classes("inc-table")

            def make_toggle(number: int):
                async def toggle(_=None):
                    selected_case["value"] = 0 if selected_case["value"] == number else number
                    await load()
                return toggle

            async def clear_filter(_=None):
                selected_case["value"] = 0
                await load()

            async def load():
                holder.clear()
                with holder:
                    try:
                        rows = await run.io_bound(list_incidents, 50)
                    except Exception as exc:  # Mongo chua san sang
                        ui.label(f"Không đọc được danh sách sự cố: {str(exc)[:200]}").style("color:#b91c1c")
                        return
                    runs_by_case = case_runs(rows)
                    ui.label("Ba ca diễn tập").classes("inc-panel-title")
                    ui.label("Bấm một ca để lọc danh sách bên dưới. Hồ sơ điều tra nằm trong từng sự cố.").classes("inc-muted")
                    with ui.element("div").classes("inc-case-grid"):
                        for number, case in CASES.items():
                            _case_card(number, case, runs_by_case.get(number, []),
                                       selected_case["value"] == number, make_toggle(number))
                    with ui.element("div").classes("inc-list-head"):
                        ui.label("Các lần diễn tập").classes("inc-panel-title").style("margin:0")
                        if selected_case["value"]:
                            ui.label(f"Đang lọc: Ca {selected_case['value']}").classes("inc-chip")
                            ui.button("Xem tất cả", on_click=clear_filter).props("flat dense no-caps color=primary")
                    if not rows:
                        ui.label("Chưa có sự cố nào. Chạy một ca diễn tập để sinh hồ sơ.").classes("inc-muted")
                        return
                    table_rows = build_list_rows(rows, selected_case["value"])
                    if not table_rows:
                        ui.label(f"Chưa có lần diễn tập nào cho Ca {selected_case['value']}.").classes("inc-muted")
                        return
                    table = ui.table(columns=LIST_COLUMNS, rows=table_rows, row_key="id").props("flat dense").style("width:100%")
                    table.add_slot("body-cell-case", r'''<q-td :props="props"><span :class="'inc-ca inc-ca-' + props.row.case_no">{{ props.value }}</span></q-td>''')
                    table.add_slot("body-cell-id_short", r'''<q-td :props="props"><span class="inc-id-mono" :title="props.row.id">{{ props.value }}</span></q-td>''')
                    table.add_slot("body-cell-state", r'''<q-td :props="props"><span :class="'inc-dot ' + (props.row.state_ok ? 'inc-dot-ok' : 'inc-dot-open')"></span>{{ props.value }}</q-td>''')
                    table.on("rowClick", lambda e: ui.navigate.to(f"/incident/{e.args[1]['id']}"))

            ui.timer(0.1, load, once=True)
            ui.timer(REFRESH_LIST_SECONDS, load)  # tu cap nhat khi co su co moi


# ---------------------------------------------------------------------------
# Trang chi tiet
# ---------------------------------------------------------------------------
@ui.page("/incident/{incident_id}")
def incident_detail_page(incident_id: str):
    if not _guard():
        return
    ui.add_head_html(f"<style>{CUSTOM_CSS}{INC_CSS}</style>")
    sidebar(active="Incident")
    with ui.element("div").classes("main-content"):
        global_topbar("Hộp đen sự cố", "🛰️")
        with ui.element("div").classes("content-area inc-wrap"):
            ui.link("← Tất cả sự cố", "/incident").classes("inc-muted")
            holder = ui.element("div").style("width:100%")
            last_sig: dict[str, Any] = {"value": None}

            async def load(force: bool = False):
                if force or last_sig["value"] is None:
                    holder.clear()
                    with holder:
                        ui.label("Đang tải hồ sơ...").classes("inc-muted")
                try:
                    tl = await run.io_bound(build_incident_timeline, incident_id)
                except Exception as exc:
                    holder.clear()
                    with holder:
                        ui.label(f"Không đọc được sự cố: {str(exc)[:200]}").style("color:#b91c1c")
                    return
                # Chi ve lai khi co thay doi, de khong lam mat vi tri thanh tua.
                inc = tl.get("incident") or {}
                sig = (inc.get("status"), len(tl.get("events") or []), str(inc.get("recovered_at")))
                if not force and sig == last_sig["value"]:
                    return
                last_sig["value"] = sig
                holder.clear()
                with holder:
                    _render(tl)

            ui.timer(0.1, load, once=True)
            ui.timer(REFRESH_DETAIL_SECONDS, load)


# ---------------------------------------------------------------------------
# Thanh phan giao dien
# ---------------------------------------------------------------------------
def _source_tag(source: str) -> None:
    """The nguon nho: MongoDB (xanh la) hoac Datadog → (tim)."""
    ui.label(source).classes(f"inc-src {'inc-src-mongo' if source == SRC_MONGO else 'inc-src-dd'}")


def _fact(key: str, value: str) -> None:
    with ui.element("div"):
        ui.label(key).classes("inc-fact-k")
        ui.label(value).classes("inc-fact-v")


def _dd_button_row(inc: dict[str, Any], full: bool = True) -> None:
    """Hang nut 'Mo trong Datadog'. full=False (trang danh sach): chi monitor, workflow.

    Trace: chi MOT nut 'Trace' (trace dau tien); con lai ghi nhan '(+N trace khac)', xem expansion o cau 6 cau hoi.
    """
    items = [*_monitor_links(inc), *_workflow_links(inc)]
    if full:
        items += [*_logs_link(inc), *_first_trace_link(inc), ("Dashboard SMIOT", DD_DASHBOARD, "Dashboard vận hành")]
    traces = _trace_links(inc) if full else []
    with ui.element("div").classes("inc-dd-row"):
        for label, url, tip in items:
            ui.link(label, url, new_tab=True).classes("inc-dd-btn").props(f'title="{tip}"')
        if full and len(traces) > 1:
            ui.label(f"(+{len(traces) - 1} trace khác)").classes("inc-muted")
        if full and not traces:
            ui.label("Trace: đang bổ sung trace_id trong dữ liệu").classes("inc-muted")


def _top_box(inc: dict[str, Any]) -> None:
    with ui.element("div").classes("inc-top"):
        _source_tag(SRC_DATADOG)
        ui.label(incident_summary(inc.get("kind"), inc.get("node_id"))).classes("inc-summary")
        _dd_button_row(inc)


def _metrics_panel(inc: dict[str, Any]) -> None:
    """Khoi 'Metric cua su co': chi ten metric va lien ket sau sang Datadog, khong ve lai metric."""
    links = metric_links(inc)
    if not links:
        return
    window = metric_window(inc)
    with ui.element("div").classes("inc-panel"):
        ui.label("Metric của sự cố").classes("inc-panel-title")
        _source_tag(SRC_DATADOG)
        if window:
            ui.label(f"Khung giờ mở sẵn trong Datadog: {_fmt(window[0])} đến {_fmt(window[1])}").classes("inc-muted")
        for label, url, note in links:
            with ui.element("div").classes("inc-line"):
                ui.label(label if label.startswith(("smiot.", "systemd.")) else "Dashboard").classes("inc-id-mono")
                ui.label(note).classes("inc-muted")
                ui.link("Mở trong Datadog →", url, new_tab=True).classes("inc-dd-btn").props(f'title="{label}"')


def _six_questions(inc: dict[str, Any], tl: dict[str, Any]) -> None:
    """Ho so 6 cau hoi dang bang 4 cot: Cau hoi | Tra loi ngan | Nguon | Mo; ben duoi la tat ca trace."""
    rows = build_six_questions(inc, tl)
    with ui.element("div").classes("inc-panel"):
        ui.label("Hồ sơ 6 câu hỏi").classes("inc-panel-title")
        with ui.element("div").classes("inc-qtable"):
            for header in ("Câu hỏi", "Trả lời ngắn", "Nguồn", "Mở"):
                ui.label(header).classes("inc-qhead")
            for index, row in enumerate(rows, start=1):
                ui.label(f"{index}. {row['question']}").classes("inc-qcell inc-qq")
                ui.label(str(row["answer"])).classes("inc-qcell")
                with ui.element("div").classes("inc-qcell"):
                    for src in row["sources"]:
                        _source_tag(src)
                with ui.element("div").classes("inc-qcell"):
                    if row["links"]:
                        for label, url, tip in row["links"]:
                            ui.link(label, url, new_tab=True).classes("inc-link").props(f'title="{tip}"')
                    else:
                        ui.label("—").classes("inc-muted")
        traces = _trace_links(inc)
        if traces:
            with ui.expansion(f"Tất cả trace ({len(traces)})", icon="route").classes("w-full"):
                for label, url, tip in traces:
                    ui.link(label, url, new_tab=True).classes("inc-link").props(f'title="{tip}"')


def _timeline_scrubber(events: list[dict[str, Any]]) -> None:
    """Thanh tua: keo de xem tung su kien theo thu tu thoi gian."""
    shown = events[:MAX_EVENT_ROWS]
    with ui.element("div").classes("inc-panel"):
        ui.label("Dòng thời gian").classes("inc-panel-title")
        if not shown:
            ui.label(UNKNOWN).classes("inc-muted")
            return
        detail = ui.element("div")

        def show(index: int) -> None:
            e = shown[int(index)]
            detail.clear()
            with detail:
                ui.label(f"{_fmt(e.get('ts'))} · {e.get('source_collection', '')} · {e.get('kind', '')}").classes("inc-muted")
                ui.label(str(e.get("summary", "")) or UNKNOWN).classes("inc-event")

        slider = ui.slider(min=0, max=max(len(shown) - 1, 0), value=0, step=1).props("label-always").classes("w-full")
        slider.on_value_change(lambda ev: show(ev.value))
        show(0)
        ui.label(f"Kéo thanh để tua · {len(shown)} sự kiện" + (
            f" (chỉ hiện {MAX_EVENT_ROWS}/{len(events)})" if len(events) > MAX_EVENT_ROWS else "")).classes("inc-muted")


def _quality_chart(q: dict[str, Any]) -> None:
    """Bieu do cot chong: chat luong du lieu theo phut (ECharts)."""
    ui.label("Chất lượng dữ liệu theo phút").classes("inc-group-title")
    if not q.get("known"):
        ui.label(f"Chưa truy vấn được telemetry: {UNKNOWN}").classes("inc-muted")
        if q.get("note"):
            ui.label(q["note"]).classes("inc-muted")
        return
    if not q["labels"]:
        ui.label("Không có mẫu telemetry hay khoảng thiếu trong cửa sổ truy vấn.").classes("inc-muted")
        return
    totals = q["totals"]
    ui.label("Tổng: " + " · ".join(
        f"{QUALITY_LABELS[k]} {totals[k] if totals[k] is not None else UNKNOWN}" for k in QUALITY_KEYS)).classes("inc-muted")
    ui.echart({
        "tooltip": {"trigger": "axis"},
        "legend": {"bottom": 0, "textStyle": {"fontSize": 11, "color": "#475569"}},
        "grid": {"left": "3%", "right": "4%", "bottom": "16%", "top": "8%", "containLabel": True},
        "xAxis": {"type": "category", "data": q["labels"],
                  "axisLabel": {"color": "#64748b", "fontSize": 10}},
        "yAxis": {"type": "value", "minInterval": 1, "axisLabel": {"color": "#64748b", "fontSize": 10},
                  "splitLine": {"lineStyle": {"type": "dashed", "color": "#e2e8f0"}}},
        "series": [{"type": "bar", "name": QUALITY_LABELS[k], "stack": "quality", "barMaxWidth": 18,
                    "itemStyle": {"color": QUALITY_COLORS[k]}, "data": q["series"][k]} for k in QUALITY_KEYS],
    }).classes("w-full").style("height:240px")
    if q.get("note"):
        ui.label(q["note"]).classes("inc-muted")


def _impact_panel(chart_data: dict[str, Any]) -> None:
    with ui.element("div").classes("inc-panel"):
        ui.label("Tác động (từ MongoDB)").classes("inc-panel-title")
        _source_tag(SRC_MONGO)
        with ui.element("div").classes("inc-cards"):
            for card in chart_data["cards"]:
                with ui.element("div").classes("inc-card"):
                    ui.label(card["label"]).classes("inc-fact-k")
                    value = card["value"]
                    ui.label(UNKNOWN if value is None else f"{value}{card.get('unit', '')}").classes("inc-card-v")
                    if card.get("note"):
                        ui.label(card["note"]).classes("inc-muted")
        _quality_chart(chart_data["quality"])


def _recovery_panel(rec: dict[str, Any], kind: str | None) -> None:
    with ui.element("div").classes("inc-panel"):
        ui.label("Bằng chứng phục hồi").classes("inc-panel-title")
        _source_tag(SRC_MONGO)
        ui.label(f"Mốc xóa/phục hồi: {_fmt(rec.get('clear_ts'))}").classes("inc-line")
        after = rec.get("samples_after_clear") or []
        if after:
            for e in after:
                ui.label(f"{_fmt(e.get('ts'))} · {e.get('summary', '')} · khác giá trị lỗi: {_fmt(e.get('differs_from_fault'))}").classes("inc-line")
        else:
            ui.label("Chưa có mẫu mới sau phục hồi trong dữ liệu.").classes("inc-muted")
        if rec.get("verification"):
            ui.label(f"Xác minh: {format_recovery_evidence(rec.get('verification'), kind)}").classes("inc-line")


def _timeline_expansion(events: list[dict[str, Any]], stage_count: Any) -> None:
    shown = mongo_only_events(events)
    hidden = len(events) - len(shown)
    with ui.expansion("Nhật ký ghi nhận trong MongoDB (aggregation $unionWith)", icon="storage").classes("w-full"):
        _source_tag(SRC_MONGO)
        if hidden:
            ui.label(f"Đã ẩn {hidden} mốc phát hiện theo monitor (nguồn Datadog, xem câu 2).").classes("inc-muted")
        _timeline_scrubber(shown)
        ui.label(f"1 aggregation, {stage_count} stage ($unionWith)").classes("inc-muted")


def _render(tl: dict[str, Any]) -> None:
    if not tl.get("found"):
        ui.label(f"Không tìm thấy sự cố {tl.get('incident_id')}.").style("font-weight:600;color:#64748b")
        return
    inc = tl.get("incident") or {}
    events = tl.get("events") or []
    impact = tl.get("impact") or {}
    rec = tl.get("recovery_evidence") or {}
    lots = tl.get("affected_lots") or []
    chart_data = build_impact_chart_data(inc, events, impact)
    status = str(inc.get("status") or "")
    pill = "inc-pill-ok" if status in ("recovered", "closed") else ("inc-pill-alert" if status == "open" else "inc-pill-warn")

    with ui.element("div").classes("inc-head"):
        ui.label(str(tl.get("incident_id"))).classes("inc-id")
        case_number = case_for_kind(inc.get("kind"))
        if case_number:
            ui.label(f"Ca {case_number}").classes("inc-pill")
        ui.label(_fmt(inc.get("kind"))).classes("inc-pill")
        ui.label(f"Trạng thái: {status or UNKNOWN}").classes(f"inc-pill {pill}")
    if tl.get("synthetic"):
        ui.label("SYNTHETIC: dữ liệu diễn tập, không phải số đo từ thiết bị thật.").classes("inc-banner")
    if case_number == 1:
        with ui.element("div").classes("inc-banner"):
            ui.label("Đối chứng: monitor 339977703 đo tuổi mẫu MongoDB; mẫu vẫn mới thì không restart app.")
            ui.link("Mở monitor đối chứng", f"{DD_BASE}/monitors/339977703", new_tab=True)

    _top_box(inc)

    with ui.element("div").classes("inc-main"):
        _metrics_panel(inc)
        _six_questions(inc, tl)
        with ui.element("div").classes("inc-panel"):
            ui.label("Thông tin sự cố").classes("inc-panel-title")
            _source_tag(SRC_MONGO)
            with ui.element("div").classes("inc-facts"):
                _fact("Farm / node", f"{_fmt(inc.get('farm_key'))} / {_fmt(inc.get('node_id'))}")
                _fact("Phát hiện lúc", _fmt(inc.get("detected_at")))
                _fact("Vào an toàn lúc", _fmt(impact.get("safe_at")))
                _fact("Phục hồi lúc", _fmt(impact.get("recovered_at")))
                _fact("Lô ảnh hưởng",
                      ", ".join(_fmt(lot.get("lot_id")) for lot in lots) if lots
                      else str(tl.get("affected_lots_status") or UNKNOWN))
                _fact("Mẫu telemetry trong cửa sổ",
                      str(sum(1 for e in events if e.get("kind") == "telemetry_sample")))
            if inc.get("scenario"):
                ui.label(str(inc.get("scenario"))).classes("inc-muted").style("margin-top:10px")

        _impact_panel(chart_data)
        _recovery_panel(rec, inc.get("kind"))
        _timeline_expansion(events, tl.get("pipeline_stage_count", "?"))
