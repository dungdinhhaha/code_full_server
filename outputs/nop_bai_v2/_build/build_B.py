# -*- coding: utf-8 -*-
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import style

IMG = os.path.join(HERE, "img")
os.makedirs(IMG, exist_ok=True)
plt.rcParams["font.family"] = "DejaVu Sans"

def box(ax, x, y, w, h, text, fc="#E8EEF7", ec="#1F3A5F", fs=9, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.15",
                                fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", linespacing=1.3)

def arrow(ax, x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color="#333333", lw=1.4))

# ---------- Hinh 1: nhom collection ----------
def fig1():
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.set_xlim(0, 11); ax.set_ylim(0, 7); ax.axis("off")
    box(ax, 4.0, 2.9, 3.0, 1.2, "operational_incidents\n(khóa nối: incident_id)", "#FCE9C8", "#8A5A00", 10, True)
    groups = [
        (0.2, 5.0, 3.6, 1.7, "Nhóm telemetry", "telemetry\n(Time Series)", "#E1F0E1", "#2E6B2E"),
        (7.2, 5.0, 3.6, 1.7, "Nhóm sự cố và bằng chứng",
         "incident_telemetry_evidence\noperational_decisions\nfindings, action_ledger", "#E8EEF7", "#1F3A5F"),
        (0.2, 0.2, 3.6, 2.0, "Nhóm kịch bản demo",
         "scenario_runs, scenario_run_events\nscenario_observations\nscenario_api_idempotency\nscenario_api_rate_limits\nscenario_api_farm_locks\ndevice_profile_events", "#F1E6F5", "#5B2C6F"),
        (7.2, 0.2, 3.6, 2.0, "Nhóm người dùng và vận hành",
         "users, permissions\nnotifications\nschedules, schedule_logs\ninverter_mode", "#E0F3F5", "#1B5E66"),
        (3.7, 5.2, 3.6, 1.5, "Nhóm mùa vụ và truy xuất",
         "crop_cycles, crop_stage_media\ntraceability_events\nlot_sensor_assignments\nagronomic_advisories, stage_envelopes", "#FBE3E3", "#8B2E2E"),
    ]
    for (x, y, w, h, title, body, fc, ec) in groups:
        box(ax, x, y, w, h, title + "\n\n" + body, fc, ec, 8.5)
    arrow(ax, 3.8, 5.6, 4.6, 4.1)
    arrow(ax, 7.2, 5.6, 6.4, 4.1)
    arrow(ax, 3.8, 1.7, 4.6, 2.9)
    arrow(ax, 7.2, 1.7, 6.4, 2.9)
    ax.text(5.5, 4.55, "incident_id", ha="center", fontsize=9, color="#8A5A00")
    ax.text(5.5, 0.6, "Kỹ thuật: _counters (bộ đếm)", ha="center", fontsize=9, style="italic")
    p = os.path.join(IMG, "B_fig1_collections.png")
    fig.savefig(p, dpi=170, bbox_inches="tight"); plt.close(fig)
    return p

# ---------- Hinh 2: pipeline hop den ----------
def fig2():
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.set_xlim(0, 11); ax.set_ylim(0, 6.4); ax.axis("off")
    src = ["incident_telemetry_evidence", "operational_decisions", "findings", "action_ledger",
           "scenario_run_events", "scenario_observations", "telemetry"]
    ys = [5.6 - i * 0.8 for i in range(7)]
    box(ax, 4.6, 2.2, 2.0, 1.3, "operational_incidents\n(điểm xuất phát)\n$match theo incident_id", "#FCE9C8", "#8A5A00", 9, True)
    for i, (s, y) in enumerate(zip(src, ys)):
        box(ax, 0.1, y - 0.3, 3.3, 0.6, "Nhánh %d: %s" % (i + 1, s), "#E8EEF7", "#1F3A5F", 8.5)
        arrow(ax, 3.4, y, 4.6, 2.85)
    ax.text(4.0, 6.15, "7 nhánh $unionWith", fontsize=10, fontweight="bold")
    box(ax, 7.4, 3.4, 3.4, 1.1, "$setWindowFields + $shift\n(trên nhánh telemetry)\nGAP_FACTOR = 3, chu kỳ 30 giây", "#E1F0E1", "#2E6B2E", 8.5)
    box(ax, 7.4, 1.6, 3.4, 1.1, "Dòng thời gian hộp đen\n(sắp theo thời điểm,\nđánh dấu khoảng thiếu mẫu)", "#F1E6F5", "#5B2C6F", 8.5)
    arrow(ax, 6.6, 3.0, 7.4, 3.9)
    arrow(ax, 9.1, 3.4, 9.1, 2.7)
    p = os.path.join(IMG, "B_fig2_blackbox_pipeline.png")
    fig.savefig(p, dpi=170, bbox_inches="tight"); plt.close(fig)
    return p

# ---------- Hinh 3: so collection theo nhom ----------
def fig3():
    labels = ["Telemetry", "Sự cố và\nbằng chứng", "Kịch bản demo", "Người dùng\nvà vận hành", "Mùa vụ và\ntruy xuất"]
    vals = [1, 5, 7, 6, 6]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(labels, vals, color=["#2E6B2E", "#1F3A5F", "#5B2C6F", "#1B5E66", "#8B2E2E"])
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.1, str(v), ha="center", fontsize=11)
    ax.set_ylabel("Số collection nghiệp vụ")
    ax.set_ylim(0, 8.5)
    ax.set_title("Collection nghiệp vụ theo nhóm chức năng (tổng 25)", fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    p = os.path.join(IMG, "B_fig3_collections_by_group.png")
    fig.savefig(p, dpi=170, bbox_inches="tight"); plt.close(fig)
    return p

# ---------- Hinh 4: index tren server ----------
def fig4():
    labels = ["operational_incidents", "action_ledger", "telemetry\n(time-series)", "stage_envelopes"]
    vals = [6, 4, 4, 3]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(labels, vals, color="#1F3A5F")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.1, str(v), ha="center", fontsize=11)
    ax.set_ylabel("Số index (đọc trên máy chủ)")
    ax.set_ylim(0, 8)
    ax.set_title("Số index của bốn collection, đọc trên máy chủ ngày 13/11/2026", fontsize=10.5)
    ax.spines[["top", "right"]].set_visible(False)
    p = os.path.join(IMG, "B_fig4_server_indexes.png")
    fig.savefig(p, dpi=170, bbox_inches="tight"); plt.close(fig)
    return p

f1, f2, f3, f4 = fig1(), fig2(), fig3(), fig4()

doc = style.new_document("Kiến trúc dữ liệu MongoDB")
P = lambda t: style.add_paragraph(doc, t)
H = lambda t, l=1: style.add_heading(doc, t, l)

# 1
H("Vai trò MongoDB trong hệ thống")
P("MongoDB là nơi lưu trữ dữ liệu vận hành của hệ thống, bao gồm mẫu cảm biến, hồ sơ sự cố, sổ lệnh, kết quả kịch bản demo trực tiếp, người dùng và dữ liệu mùa vụ. MongoDB là nền dữ liệu và bằng chứng cho Datadog, trung tâm của ba pha Phát hiện, Điều tra, Phản ứng: MongoDB ghi lệnh, trạng thái sự cố, kết quả xác minh và giữ bằng chứng (mẫu telemetry, quyết định, phát hiện, sự kiện ACK) để dựng lại diễn biến từng sự cố, còn ứng dụng điều hướng và giữ khóa an toàn cục bộ.")
P("Cơ sở dữ liệu dùng MongoDB Community tự quản trị (pymongo, phiên bản >=4.0 và <4.18; nguồn: requirements.txt). Tên database lấy từ biến môi trường MONGODB_DATABASE, giá trị mặc định là smiot (nguồn: service/mongodb_store.py). Chuỗi kết nối nằm trong biến môi trường và không được ghi trong mã hay hồ sơ.")
P("Ngày 13/11/2026, nhóm đã đọc trực tiếp (chỉ đọc) máy chủ MongoDB trên EC2. Kết quả được dùng xuyên suốt tài liệu và tổng hợp ở Bảng 1.")
style.add_table(doc, ["Hạng mục", "Giá trị đọc trên máy chủ", "Nguồn"], [
    ["Phiên bản MongoDB", "8.0.34", "Đọc trực tiếp trên EC2, 13/11/2026"],
    ["Database", "smiot", "Đọc trực tiếp trên EC2, 13/11/2026"],
    ["Số collection không phải hệ thống", "24", "Đọc trực tiếp trên EC2, 13/11/2026"],
    ["Collection dạng time-series", "1 (telemetry, ước lượng 965.357 bản ghi)", "Đọc trực tiếp trên EC2, 13/11/2026"],
    ["Collection thường", "23", "Đọc trực tiếp trên EC2, 13/11/2026"],
    ["Collection có index", "23 (riêng _counters chỉ có index _id)", "Đọc trực tiếp trên EC2, 13/11/2026"],
    ["Collection có validator", "0 (không áp dụng $jsonSchema trên máy chủ)", "Đọc trực tiếp trên EC2, 13/11/2026"],
], caption="Kết quả đọc trực tiếp MongoDB trên máy chủ (chỉ đọc)")

# 2
H("Mô hình dữ liệu")
P("Trên máy chủ có 24 collection không phải hệ thống (đọc trực tiếp ngày 13/11/2026). Riêng trong mã nguồn, có 26 tên collection được khai báo, gồm 25 collection nghiệp vụ và collection kỹ thuật _counters (nguồn: đếm các lệnh collection(\"...\") và db[...] trong service/, pages/, main.py). Hai số này đến từ hai nguồn khác nhau và được nêu tách riêng.")
P("Các collection được nhóm theo chức năng như Hình 1. Khóa incident_id nối hồ sơ sự cố (operational_incidents) với phát hiện, quyết định, bằng chứng telemetry, sổ lệnh và mẫu telemetry gắn sự cố, nên một truy vấn theo incident_id đủ để dựng lại toàn bộ diễn biến.")
style.add_figure(doc, f1, "Sơ đồ nhóm collection và quan hệ qua incident_id")
H("Nhóm telemetry", 2)
P("Collection telemetry chứa mẫu cảm biến, node, nước và lưu lượng. Trên máy chủ, đây là collection time-series duy nhất. Mẫu thuộc sự cố có trường source.incident_id để truy vết.")
H("Nhóm sự cố và bằng chứng", 2)
P("Gồm operational_incidents (hồ sơ sự cố), incident_telemetry_evidence, operational_decisions, findings (phát hiện từ watchdog) và action_ledger (sổ lệnh với các trạng thái requested, published, acknowledged, failed, verified).")
H("Nhóm kịch bản demo", 2)
P("Gồm kết quả và sự kiện của các lần chạy kịch bản demo trực tiếp, cùng ba collection hỗ trợ API kịch bản demo: khóa idempotency, giới hạn tốc độ và khóa theo nhà màng. Dữ liệu kịch bản demo mang cờ execution_mode=SIMULATED_ONLY.")
H("Nhóm người dùng và vận hành", 2)
P("Gồm users (mật khẩu băm PBKDF2), permissions, notifications, schedules, schedule_logs và inverter_mode.")
H("Nhóm mùa vụ và truy xuất", 2)
P("Gồm crop_cycles, crop_stage_media, traceability_events, lot_sensor_assignments, agronomic_advisories và stage_envelopes (khung môi trường theo giai đoạn cây).")
style.add_figure(doc, f3, "Số collection nghiệp vụ theo nhóm chức năng (nguồn: Bảng 2)")
style.add_table(doc, ["Collection", "Nhóm", "Mục đích", "Nguồn ghi (trong mã)"], [
    ["telemetry", "Telemetry", "Mẫu cảm biến, node, nước, lưu lượng (time-series)", "service/mongodb_telemetry.py, service/mqtt.py"],
    ["operational_incidents", "Sự cố", "Hồ sơ sự cố: kind, status, farm_key, node_id, opened_at", "service/incident_lifecycle.py"],
    ["incident_telemetry_evidence", "Sự cố", "Bằng chứng telemetry gắn sự cố", "service/scenario_evidence.py"],
    ["operational_decisions", "Sự cố", "Quyết định vận hành theo sự cố", "service/incident_lifecycle.py"],
    ["findings", "Sự cố", "Phát hiện từ watchdog", "service/telemetry_findings.py"],
    ["action_ledger", "Sự cố", "Sổ lệnh và hành động, trạng thái từ requested đến verified", "service/operational_evidence.py"],
    ["scenario_runs", "Kịch bản demo", "Lần chạy kịch bản demo (scenario_run_id, status)", "service/scenario_evidence.py, service/mqtt.py"],
    ["scenario_run_events", "Kịch bản demo", "Sự kiện ACK của kịch bản demo", "main.py, service/scenario_evidence.py"],
    ["scenario_observations", "Kịch bản demo", "Quan sát kịch bản demo (SIMULATED_ONLY)", "service/scenario_evidence.py"],
    ["scenario_api_idempotency", "Kịch bản demo", "Khóa idempotency của API kịch bản demo (có TTL)", "main.py"],
    ["scenario_api_rate_limits", "Kịch bản demo", "Giới hạn tốc độ API kịch bản demo (có TTL)", "main.py"],
    ["scenario_api_farm_locks", "Kịch bản demo", "Khóa theo nhà màng cho API kịch bản demo", "main.py"],
    ["device_profile_events", "Kịch bản demo", "Sự kiện hồ sơ thiết bị (Velxio)", "service/mqtt.py"],
    ["notifications", "Người dùng, vận hành", "Thông báo trong ứng dụng, kể cả từ Datadog", "service/auth.py, main.py"],
    ["users", "Người dùng, vận hành", "Người dùng (mật khẩu PBKDF2)", "service/auth.py"],
    ["permissions", "Người dùng, vận hành", "Danh mục quyền", "service/auth.py"],
    ["schedules", "Người dùng, vận hành", "Lịch tưới", "service/auth.py"],
    ["schedule_logs", "Người dùng, vận hành", "Nhật ký lịch tưới", "service/auth.py"],
    ["inverter_mode", "Người dùng, vận hành", "Chế độ inverter ảo", "service/auth.py"],
    ["crop_cycles", "Mùa vụ, truy xuất", "Vòng đời mùa vụ, có public_share_token", "-"],
    ["crop_stage_media", "Mùa vụ, truy xuất", "Ảnh theo giai đoạn", "-"],
    ["traceability_events", "Mùa vụ, truy xuất", "Sự kiện truy xuất lô", "service/traceability.py"],
    ["lot_sensor_assignments", "Mùa vụ, truy xuất", "Gán cảm biến cho lô theo hiệu lực thời gian", "service/incident_lifecycle.py"],
    ["agronomic_advisories", "Mùa vụ, truy xuất", "Khuyến nghị nông học", "service/agronomic_thresholds.py"],
    ["stage_envelopes", "Mùa vụ, truy xuất", "Khung môi trường theo giai đoạn cây", "service/stage_envelopes.py"],
], caption="Danh sách 25 collection nghiệp vụ theo mã nguồn (cộng _counters là 26 tên)", font_size=10)

# 3
H("Chỉ mục")
P("Trong mã, chỉ mục được khai báo ở ba nơi, có chủ đích trùng lặp để khởi tạo an toàn: service/auth.py (hàm init_db, 19 lệnh create_index), service/incident_blackbox.py (INCIDENT_INDEX_SPECS, 11 khai báo; HARDENING_INDEX_SPECS, 6 khai báo). Tổng là 36 lệnh khai báo trong mã, và con số này không phải số index khác biệt trên cơ sở dữ liệu. Collection stage_envelopes có thêm 2 khai báo riêng (nguồn: service/stage_envelopes.py).")
style.add_table(doc, ["Loại", "Index", "Nguồn"], [
    ["Unique partial", "operational_incidents (kind, farm_key, node_id), unique, áp dụng cho status thuộc open, holding, recovering và kind thuộc false_offline, service_down (active_incident_by_scope_unique)", "service/incident_blackbox.py (HARDENING)"],
    ["Partial", "operational_incidents active_incident_by_scope; telemetry telemetry_by_incident_ts (khi source.incident_id tồn tại)", "service/incident_blackbox.py"],
    ["TTL", "scenario_api_idempotency trên created_at, 7 ngày (604.800 giây); scenario_api_rate_limits trên updated_at, 24 giờ", "service/incident_blackbox.py"],
    ["Unique khác", "users.username; crop_cycles.public_share_token (sparse); crop_stage_media (farm_key, lot_id, stage_code); stage_envelopes (crop_key, stage_code, cultivar, version)", "service/auth.py; service/stage_envelopes.py"],
    ["Compound", "telemetry (meta.farm_key, meta.measurement_type, meta.node_id, timestamp); action_ledger (incident_id, created_at); findings (incident_id, detected_at)", "service/auth.py; service/incident_blackbox.py"],
], caption="Các loại index theo khai báo trong mã (3 partial, 2 TTL)", font_size=10)
P("Thông tin đọc trên máy chủ ngày 13/11/2026: 23 collection có index; riêng _counters chỉ có index _id. Số index đọc được của một số collection được nêu ở Hình 3 và Bảng 4.")
style.add_figure(doc, f4, "Số index của bốn collection đọc trên máy chủ (13/11/2026)")
style.add_table(doc, ["Collection", "Số index trên máy chủ", "Ghi chú"], [
    ["operational_incidents", "6", "Gồm active_incident_by_scope_unique"],
    ["action_ledger", "4", ""],
    ["telemetry", "4", "Index của collection time-series"],
    ["stage_envelopes", "3", ""],
    ["notifications, schedules, schedule_logs, incident_telemetry_evidence, traceability_events", "Có index", "Đã đọc tên index; số lượng không nêu trong bảng này"],
    ["scenario_api_idempotency, scenario_api_rate_limits", "Có index", "Có index TTL"],
], caption="Index đọc trên máy chủ ngày 13/11/2026", font_size=10)
P("Không đặt TTL cho notifications, schedules, schedule_logs, telemetry, operational_incidents và action_ledger, vì đây là dữ liệu bằng chứng và lịch sử cần giữ lâu (theo chú thích trong mã). Chỉ hai collection phục vụ API kịch bản demo có TTL.")

# 4
H("Time Series")
P("Collection telemetry là collection time-series trên máy chủ (ước lượng 965.357 bản ghi ngày 13/11/2026). Khi tạo bằng script scripts/migrate_sqlite_telemetry_to_mongodb.py, collection dùng timeField là timestamp, metaField là meta và granularity là seconds; script chỉ chấp nhận collection đúng hai trường này (nguồn: scripts/migrate_sqlite_telemetry_to_mongodb.py, dòng 115-139).")
P("Ứng dụng ghi mẫu bằng insert_one vào telemetry (service/mongodb_telemetry.py, dòng 64-93). Trường meta chứa farm_key, node_id và measurement_type, giúp các truy vấn theo nhà màng và loại số đo dùng index compound. Script scripts/mongo_timeseries_benchmark.py so sánh việc đọc raw cursor với aggregation $setWindowFields bằng executionStats.")

# 5
H("Aggregation pipeline")
P("Pipeline quan trọng nhất là dòng thời gian hộp đen sự cố (service/incident_blackbox.py, dòng 345-472). Pipeline xuất phát từ operational_incidents, dùng 7 nhánh $unionWith để gộp bằng chứng từ bảy collection, sau đó dùng $setWindowFields kèm $shift trên nhánh telemetry để đánh dấu khoảng thiếu mẫu (GAP_FACTOR = 3, chu kỳ mẫu 30 giây; dòng 472-480).")
style.add_figure(doc, f2, "Pipeline hộp đen: 7 nhánh $unionWith và $setWindowFields")
style.add_table(doc, ["File", "Toán tử chính", "Mục đích"], [
    ["service/incident_blackbox.py (dòng 345-480)", "$unionWith (7 nhánh), $setWindowFields, $shift", "Dòng thời gian hộp đen; đánh dấu khoảng thiếu mẫu"],
    ["service/mongodb_showcase.py (dòng 62-105, 239-241)", "$setWindowFields, $shift, $group", "Độ phủ dữ liệu theo ngày; GDD lũy kế; nhiệt độ trung bình trượt 7 ngày"],
    ["pages/farm_overview_component.py (dòng 358, 393)", "$group", "Tổng quan 10 nhà màng theo nhóm thời gian"],
    ["pages/project.py (dòng 43)", "$group, $max", "Lần mẫu gần nhất theo nhà màng"],
    ["service/traceability.py (dòng 150)", "$group", "Truy xuất lô"],
    ["service/auth.py (dòng 386)", "$match (regex), $group, $sum, $ifNull", "Tổng nước tưới theo ngày"],
    ["main.py (dòng 213-223)", "update pipeline với $cond, $add", "Giới hạn tốc độ API kịch bản demo, cửa sổ 60 giây"],
    ["scripts/gdd_forecast.py, telemetry_quality_report.py, mongo_timeseries_benchmark.py", "$group, $setWindowFields, $shift", "Báo cáo và dự báo (script ngoài ứng dụng)"],
], caption="Aggregation pipeline trong mã nguồn", font_size=10)
P("Mã ứng dụng không dùng $lookup, $facet hay $graphLookup; việc nối dữ liệu được thực hiện bằng $unionWith và khóa incident_id.")

# 6
H("Ràng buộc dữ liệu")
H("Chỉ mục unique và partial", 2)
P("Chỉ mục unique partial active_incident_by_scope_unique bảo đảm tại một thời điểm chỉ có một sự cố đang mở cho cùng bộ (kind, farm_key, node_id) với hai loại false_offline và service_down. Server đã có index này trên operational_incidents (đọc ngày 13/11/2026).")
H("Mô hình $jsonSchema", 2)
P("Trong mã, $jsonSchema được định nghĩa cho 6 collection: operational_incidents, action_ledger, notifications, scenario_runs, scenario_observations và scenario_run_events, với validationAction=warn và validationLevel=moderate, tức là cảnh báo chứ không chặn ghi (nguồn: service/incident_blackbox.py, dòng 110-290; scripts/apply_mongo_hardening.py). Trạng thái validator trên máy chủ được nêu ở Bảng 1.")
H("Idempotency, giới hạn tốc độ, khóa theo nhà màng", 2)
style.add_table(doc, ["Cơ chế", "Collection", "Chi tiết", "Nguồn"], [
    ["Idempotency", "scenario_api_idempotency", "Header Idempotency-Key bắt buộc (tối đa 200 ký tự); băm token và key được lưu, trả lại kết quả cũ khi trùng; TTL 7 ngày", "main.py; service/incident_blackbox.py"],
    ["Giới hạn tốc độ", "scenario_api_rate_limits", "20 lượt ghi và 120 lượt đọc mỗi token trong 60 giây; late-ACK W9 giới hạn 1 lượt; TTL 24 giờ", "main.py"],
    ["Khóa theo nhà màng", "scenario_api_farm_locks", "_id là farm_key; mỗi nhà màng chạy một kịch bản demo tại một thời điểm", "main.py"],
], caption="Cơ chế ràng buộc cho API kịch bản demo", font_size=10)

H("Collection liên quan đến mười ca sự cố")
P("Giao diện ứng dụng hiển thị mười ca sự cố (ảnh chụp ngày 13/11/2026). Bảng 7 nêu các collection tham gia lưu hồ sơ, bằng chứng và lệnh của từng ca, theo vai trò đã mô tả ở Bảng 2. Các collection chung cho mọi ca: operational_incidents (hồ sơ), telemetry (mẫu), notifications (thông báo), action_ledger (sổ lệnh) và operational_decisions (quyết định). Khi một ca được trình diễn bằng kịch bản demo trực tiếp, dữ liệu còn ghi vào scenario_runs và scenario_run_events; incident_telemetry_evidence lưu bằng chứng telemetry khi sự cố có gắn mẫu.")
style.add_table(doc, ["Ca", "Nội dung", "Collection liên quan theo vai trò trong mã"], [
    ["Ca 1", "Báo offline sai", "operational_incidents (kind false_offline), telemetry, incident_telemetry_evidence, operational_decisions, notifications"],
    ["Ca 2", "Node 2 đứng số đo", "operational_incidents, telemetry, findings, incident_telemetry_evidence, operational_decisions, notifications"],
    ["Ca 3", "smiot.service dừng", "operational_incidents (kind service_down), operational_decisions, action_ledger, notifications"],
    ["W1", "PLC safety trip", "operational_incidents, action_ledger, scenario_runs, scenario_run_events, notifications"],
    ["W5", "MongoDB/MQTT suy giảm", "operational_incidents, findings, operational_decisions, notifications"],
    ["W6", "Detector mất heartbeat", "operational_incidents, findings, notifications"],
    ["W7", "Rủi ro độ ẩm đất", "operational_incidents, agronomic_advisories, telemetry, notifications"],
    ["W8", "Rủi ro VPD/EC", "operational_incidents, agronomic_advisories, telemetry, notifications"],
    ["W9", "Actuator không ACK", "operational_incidents, action_ledger, scenario_run_events, scenario_observations, notifications"],
    ["W10", "AI provider lỗi", "operational_incidents, operational_decisions, notifications"],
], caption="Collection liên quan đến từng ca sự cố (theo vai trò collection trong mã)", font_size=10)

# 7
H("Lựa chọn thiết kế về tính năng MongoDB")
P("Thiết kế chọn một tập tính năng gọn, đủ cho bài toán, như Bảng 8.")
style.add_table(doc, ["Tính năng", "Trạng thái", "Căn cứ"], [
    ["Time Series", "Dùng cho telemetry", "Đọc trên máy chủ 13/11/2026; scripts/migrate_sqlite_telemetry_to_mongodb.py"],
    ["Aggregation ($unionWith, $setWindowFields, $shift)", "Dùng", "service/incident_blackbox.py"],
    ["Index unique partial, partial, TTL", "Dùng", "Mục 3; đọc tên index trên máy chủ"],
    ["$jsonSchema", "Định nghĩa trong mã cho 6 collection (warn, moderate)", "service/incident_blackbox.py; scripts/apply_mongo_hardening.py"],
    ["Change streams", "Không dùng", "Không có watch( hoặc change_stream trong mã"],
    ["Transactions", "Không dùng", "Không có start_session hoặc with_transaction trong mã"],
    ["Atlas Search, Vector Search, Triggers", "Không dùng", "Ghi rõ trong docstring service/incident_blackbox.py"],
], caption="Tính năng MongoDB và căn cứ", font_size=10)
P("Các thao tác ghi quan trọng đều là thao tác trên một document, kết hợp với index unique partial để chống trùng sự cố, nên thiết kế không cần transaction nhiều document. Việc phát hiện thay đổi dựa trên watchdog chu kỳ, không dựa trên change stream.")

# 8
H("Script hỗ trợ")
style.add_table(doc, ["Script", "Chức năng"], [
    ["scripts/migrate_sqlite_telemetry_to_mongodb.py", "Chuyển dữ liệu telemetry từ SQLite cũ sang collection time-series telemetry"],
    ["scripts/apply_mongo_hardening.py", "Áp dụng chỉ mục và $jsonSchema theo định nghĩa trong mã"],
    ["scripts/mongo_timeseries_benchmark.py", "So sánh đọc raw cursor và aggregation $setWindowFields bằng executionStats"],
    ["scripts/telemetry_quality_report.py", "Báo cáo chất lượng telemetry (độ phủ, khoảng thiếu mẫu)"],
    ["scripts/gdd_forecast.py", "Dự báo tích lũy độ ngày sinh trưởng (GDD) từ telemetry"],
], caption="Script hỗ trợ liên quan đến MongoDB", font_size=10)

out = os.path.join(os.path.dirname(HERE), "02_kien_truc_du_lieu_mongodb.docx")
style.save(doc, out)
print("OK", out, doc._smiot_fig, doc._smiot_tab)
