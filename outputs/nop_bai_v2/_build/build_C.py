# -*- coding: utf-8 -*-
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import style
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = os.path.dirname(HERE)
IMG = os.path.join(HERE, "img")
os.makedirs(IMG, exist_ok=True)
plt.rcParams["font.family"] = "DejaVu Sans"

C_APP, C_DD, C_MG, C_OK, C_GR = "#DCE9F7", "#E6DDF3", "#DFF0D8", "#FCE9C8", "#EEEEEE"


def box(ax, x, y, w, h, text, fc=C_GR, fs=9, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fc, ec="#333333", lw=1.1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal")


def arrow(ax, x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color="#333333", lw=1.4))


def canvas(w, h, xl, yl):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, xl); ax.set_ylim(0, yl); ax.axis("off")
    return fig, ax


def save(fig, name):
    p = os.path.join(IMG, name)
    fig.savefig(p, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return p


def vn(x):
    return ("%.1f" % x).replace(".", ",")


# ---------------- Hinh cho tai lieu 03 ----------------
def fig03_flow():
    fig, ax = canvas(11, 4.6, 11, 4.6)
    box(ax, 0.1, 1.6, 1.9, 1.4, "Ứng dụng\nNiceGUI\n(main.py, service/)", C_APP, 9, True)
    box(ax, 2.7, 3.2, 2.2, 0.9, "Metric DogStatsD\n(smiot.*)", C_GR)
    box(ax, 2.7, 1.9, 2.2, 0.9, "Span ddtrace\n(APM, LLM Obs)", C_GR)
    box(ax, 2.7, 0.6, 2.2, 0.9, "Log JSON qua\nDatadog Agent", C_GR)
    box(ax, 5.6, 1.6, 1.8, 1.4, "Datadog\nDashboard\nMonitor", C_DD, 9, True)
    box(ax, 8.0, 1.6, 1.4, 1.4, "Workflow\ncó guard", C_DD, 9, True)
    box(ax, 9.8, 1.6, 1.1, 1.4, "Ứng dụng\n(endpoint,\n/incident)", C_APP, 8, True)
    for y in (3.65, 2.35, 1.05):
        arrow(ax, 2.0, 2.3, 2.7, y)
        arrow(ax, 4.9, y, 5.6, 2.3)
    arrow(ax, 7.4, 2.3, 8.0, 2.3)
    arrow(ax, 9.4, 2.3, 9.8, 2.3)
    ax.text(5.5, 4.45, "Correlation ID đi trong log, span và document MongoDB; không dùng làm tag metric",
            ha="center", fontsize=8.5, style="italic")
    return save(fig, "C03_h1_luong_tin_hieu.png")


def fig03_monitors():
    fig, ax = plt.subplots(figsize=(7.2, 4))
    labels = ["Live SMIOT\n(13/11)", "IaC\nmonitors.tf", "IaC\nterraform_scenarios", "IaC\nterraform_w2"]
    vals = [19, 17, 5, 1]
    cols = ["#6A4FA3", "#8FB8DE", "#8FB8DE", "#8FB8DE"]
    b = ax.bar(labels, vals, color=cols, edgecolor="#333333")
    for r, v in zip(b, vals):
        ax.text(r.get_x() + r.get_width() / 2, v + 0.4, str(v), ha="center", fontsize=10, fontweight="bold")
    ax.set_ylabel("Số monitor")
    ax.set_ylim(0, 23)
    ax.set_title("Số monitor theo nguồn (IaC: 17 + 5 + 1 = 23 định nghĩa)", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    return save(fig, "C03_h2_monitor_theo_nguon.png")


def fig03_widgets():
    fig, ax = plt.subplots(figsize=(7.2, 4))
    labels = ["Portfolio", "Data\nQuality", "IoT & MQTT\nFleet", "Incident &\nRecovery", "App, EC2,\nMongoDB & AI"]
    vals = [6, 5, 7, 6, 7]
    b = ax.bar(labels, vals, color="#8FB8DE", edgecolor="#333333")
    for r, v in zip(b, vals):
        ax.text(r.get_x() + r.get_width() / 2, v + 0.15, str(v), ha="center", fontsize=10, fontweight="bold")
    ax.set_ylabel("Số widget (theo file JSON)")
    ax.set_ylim(0, 8.5)
    ax.set_title("Số widget của 5 dashboard (deploy/datadog/terraform_farm_control_center/dashboards)", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    return save(fig, "C03_h3_widget_theo_dashboard.png")


def fig03_cases():
    fig, ax = canvas(11, 4.2, 11, 4.2)
    rows = [
        ("Ca 1", "telemetry status mismatch\n(342585836)", "Ca 1 | Refuse restart when\nsamples are fresh",
         "Từ chối khởi động lại\nkhi mẫu còn mới"),
        ("Ca 2", "sensor flatline\n(342585819)", "Ca 2 | Confirm local\ninterlock",
         "Xác nhận khóa liên động\ncục bộ"),
        ("Ca 3", "smiot.service inactive\n(342585838)", "Guarded EC2 app\nrecovery",
         "Khôi phục có guard,\nxác minh health + MongoDB"),
    ]
    ax.text(2.6, 4.0, "Monitor", ha="center", fontsize=10, fontweight="bold")
    ax.text(5.9, 4.0, "Workflow", ha="center", fontsize=10, fontweight="bold")
    ax.text(9.2, 4.0, "Hành động", ha="center", fontsize=10, fontweight="bold")
    for i, (c, m, w, a) in enumerate(rows):
        y = 2.65 - i * 1.3
        box(ax, 0.05, y, 0.8, 1.0, c, C_OK, 10, True)
        box(ax, 1.2, y, 2.9, 1.0, m, C_DD, 9)
        box(ax, 4.5, y, 2.8, 1.0, w, C_DD, 9)
        box(ax, 7.7, y, 3.1, 1.0, a, C_APP, 9)
        arrow(ax, 0.85, y + 0.5, 1.2, y + 0.5)
        arrow(ax, 4.1, y + 0.5, 4.5, y + 0.5)
        arrow(ax, 7.3, y + 0.5, 7.7, y + 0.5)
    return save(fig, "C03_h4_monitor_workflow_hanh_dong.png")


# ---------------- Hinh cho tai lieu 06 ----------------
def fig06_timeline():
    fig, ax = plt.subplots(figsize=(9, 3.6))
    data = [("C10 pipe_leak (suite 12/11)", 1.5, 79.1, 286.5), ("A3 a3_low_flow (suite 12/11)", 1.4, 109.8, 317.6)]
    for i, (n, rec, det, ok) in enumerate(data):
        y = i
        ax.plot([0, ok], [y, y], color="#999999", lw=2, zorder=1)
        for x, c, lab in ((0, "#333333", "Bắt đầu"), (rec, "#2E8B57", "App khôi phục"),
                          (det, "#C0392B", "Datadog phát hiện"), (ok, "#2F6DB5", "Datadog về OK")):
            ax.scatter([x], [y], s=70, color=c, zorder=3)
            dy = 0.16 if lab in ("App khôi phục", "Datadog về OK") else -0.26
            ax.text(x, y + dy, "%s\n%s s" % (lab, vn(x)) if x else lab, ha="center", fontsize=7.5,
                    va="bottom" if dy > 0 else "top")
        ax.text(-8, y, n, ha="right", va="center", fontsize=9, fontweight="bold")
    ax.set_xlim(-10, 345); ax.set_ylim(-0.7, 1.7)
    ax.set_yticks([])
    ax.set_xlabel("Thời gian từ mốc bắt đầu kịch bản (giây)")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.set_title("Dòng thời gian hai kịch bản (dữ liệu diễn tập, một lần chạy mỗi mã)", fontsize=10)
    fig.subplots_adjust(left=0.30)
    return save(fig, "C06_h1_timeline.png")


def fig06_bars():
    codes = ["A3\n(12/11)", "C10\n(12/11)", "A2\n(13/11)", "S3\n(12/11)", "A1\n(13/11)", "S2\n(12/11)", "C2\n(12/11)"]
    det = [109.8, 79.1, 79.1, 0.6, None, None, None]
    rec = [1.4, 1.5, None, 13.2, 4.2, 13.0, 12.1]
    import numpy as np
    x = np.arange(len(codes)); w = 0.38
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for i in range(len(codes)):
        if det[i] is not None:
            ax.bar(x[i] - w / 2, det[i], w, color="#C0392B", edgecolor="#333333")
            ax.text(x[i] - w / 2, det[i] + 2, vn(det[i]), ha="center", fontsize=8)
        else:
            ax.text(x[i] - w / 2, 3, "không\nalert", ha="center", fontsize=7, color="#555555")
        if rec[i] is not None:
            ax.bar(x[i] + w / 2, rec[i], w, color="#2E8B57", edgecolor="#333333")
            ax.text(x[i] + w / 2, rec[i] + 2, vn(rec[i]), ha="center", fontsize=8)
        else:
            ax.text(x[i] + w / 2, 3, "không áp\ndụng", ha="center", fontsize=7, color="#555555")
    ax.set_xticks(x); ax.set_xticklabels(codes)
    ax.set_ylabel("Giây")
    ax.set_ylim(0, 130)
    ax.bar([0], [0], color="#C0392B", label="Datadog phát hiện")
    ax.bar([0], [0], color="#2E8B57", label="App khôi phục")
    ax.legend(frameon=False, loc="upper right")
    ax.set_title("Thời gian phát hiện Datadog và khôi phục app theo mã (dữ liệu diễn tập)", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    return save(fig, "C06_h2_thoi_gian.png")


def fig06_cases():
    fig, ax = canvas(11, 5, 11, 5)
    heads = ["Phát hiện", "Điều tra", "Phản ứng"]
    cases = [
        ("Ca 1\nBáo offline sai",
         ["Monitor telemetry\nstatus mismatch", "Giao diện báo OFFLINE\nnhưng mẫu vẫn vào MongoDB",
          "Workflow từ chối khởi động\nlại khi mẫu còn mới"]),
        ("Ca 2\nĐộ ẩm đất Node 2\nđứng yên",
         ["Monitor sensor\nflatline", "Flatline: 10 mẫu, 0,01,\n600 s (tham số kịch bản)",
          "Workflow xác nhận\nkhóa liên động cục bộ"]),
        ("Ca 3\nsmiot.service dừng",
         ["Monitor smiot.service\ninactive", "Kiểm tra health\nvà MongoDB",
          "Khôi phục có guard,\nxác minh sau khôi phục"]),
    ]
    xs = [2.9, 5.7, 8.5]
    for x, h in zip(xs, heads):
        ax.text(x + 1.0, 4.75, h, ha="center", fontsize=11, fontweight="bold")
    for i, (name, cells) in enumerate(cases):
        y = 3.2 - i * 1.5
        box(ax, 0.05, y, 2.3, 1.15, name, C_OK, 9, True)
        for j, (x, t) in enumerate(zip(xs, cells)):
            box(ax, x, y, 2.0, 1.15, t, [C_DD, C_MG, C_APP][j], 8)
            arrow(ax, x - 0.5 if j else 2.35, y + 0.57, x, y + 0.57)
    return save(fig, "C06_h3_ba_ca.png")


# ---------------- Tai lieu 03 ----------------
def build_03():
    d = style.new_document("Kiến trúc observability trên Datadog")
    H, P, B, T, F = style.add_heading, style.add_paragraph, style.add_bullets, style.add_table, style.add_figure

    H(d, "Vai trò của Datadog", 1)
    P(d, "Datadog là trung tâm quan sát của cả ba pha Phát hiện, Điều tra và Phản ứng. Ứng dụng NiceGUI gửi metric, span và log lên Datadog; "
         "monitor đánh giá tín hiệu, workflow có guard thực hiện bước phản ứng và gọi ngược về ứng dụng, monitor trở về OK là tín hiệu phục hồi. "
         "MongoDB là nền dữ liệu và bằng chứng; ứng dụng điều hướng và giữ khóa an toàn cục bộ (PLC ảo, interlock) (nguồn: ARCHITECTURE.md).")
    B(d, [
        "Phát hiện: monitor trên metric smiot.* do DogStatsD gửi, ví dụ telemetry status mismatch (342585836), sensor flatline (342585819), "
        "smiot.service inactive (342585838), virtual PLC safety trip (342734303), W6 | Detector evaluation stalled (343029221), "
        "actuator command unacknowledged (342734743). Dashboard SMIOT | Incident & Recovery (isq-rzw-a6s) và SMIOT | IoT & MQTT Fleet (kzx-fwc-sai) cho cái nhìn tổng quan.",
        "Điều tra: log có incident_id qua Agent, trace (mqtt.message.process, smiot.ai.tool) và bối cảnh monitor, workflow quanh cùng một correlation ID; "
        "workflow kiểm tra bằng chứng như W1 (b9e72b04-1580-45f8-ae1e-628124a19065), W5 (d3f0705e-2cbd-430a-9a3a-b1fd02a42cc9), "
        "W7 (bb86206c-6df8-4b1d-8016-175a2fc62e49), W8 (593a670c-d59c-4104-8658-df260245a21e).",
        "Phản ứng: workflow có guard Ca 1 (ffd62026-6b63-40e4-9b46-6ac18d2d584f), Ca 2 (2f9a3c1d-5292-4bc3-b4b9-cc03d4172724) và Guarded EC2 app recovery "
        "(373ed0c0-4509-4fcd-a067-f54f0becc00e); monitor trở về OK xác nhận phục hồi từ phía Datadog.",
    ])
    P(d, "Mã tương quan (correlation ID, ví dụ incident_id) đi trong log, span và document MongoDB; không đưa vào tag "
         "của metric để giữ số lượng tổ hợp tag ở mức giới hạn. Nhãn của metric gồm farm, node và source "
         "(nguồn: service/datadog_metrics.py).")

    H(d, "Thu thập tín hiệu", 1)
    F(d, fig03_flow(), "Luồng tín hiệu từ ứng dụng tới Datadog, monitor, workflow và quay lại ứng dụng", 16)

    H(d, "Metric DogStatsD", 2)
    P(d, "Ứng dụng gửi metric qua DogStatsD (cổng cấu hình bằng biến DD_DOGSTATSD_PORT, mặc định 8125). "
         "File service/datadog_metrics.py gọi trực tiếp 19 tên metric, chia thành bốn nhóm ở Bảng 1.")
    T(d, ["Nhóm", "Số tên", "Tên metric (tiền tố smiot.)"], [
        ["Bộ truyền động (actuator)", "9",
         "actuator.fan_rpm, actuator.flow_lpm, actuator.pressure_bar, actuator.pump_on, actuator.safe_mode_active, "
         "actuator.total_volume_l, actuator.valve_open, actuator.vent_command, actuator.vent_state"],
        ["Cây trồng (crop)", "5",
         "crop.envelope.approved, crop.soil_moisture.review_required, crop.stage_context.valid, "
         "crop.vpd_ec.review_required, crop.vpd_kpa"],
        ["Thiết bị (device)", "2", "device.reboot_detected, device.uptime_seconds"],
        ["Trình tự telemetry (sequence)", "3",
         "telemetry.sequence_duplicate, telemetry.sequence_gap, telemetry.sequence_regression"],
        ["Tổng", "19", "Nguồn: service/datadog_metrics.py"],
    ], caption="Nhóm metric DogStatsD gọi trực tiếp trong service/datadog_metrics.py", font_size=10)
    P(d, "Trong mã còn có các chuỗi tên dạng smiot.* gồm tên metric, tên span và tên sự kiện log. Một số tên khác "
         "ngoài Bảng 1: smiot.telemetry.samples_persisted, smiot.telemetry.ingest_lag_ms, "
         "smiot.telemetry.sample_age_seconds, smiot.telemetry.status_mismatch, smiot.telemetry.sensor_flatline, "
         "smiot.dependency.mongo.up, smiot.dependency.mqtt.up, smiot.actuator.command_acknowledged, "
         "smiot.virtual_plc.safety_trip, smiot.safe_mode.transition.")

    H(d, "APM và ddtrace", 2)
    B(d, [
        "Bật bằng biến DATADOG_APM_ENABLED. Thiết lập: DD_SERVICE=smiot-smart-farm, DD_ENV=demo, DD_VERSION=1.0.0, "
        "DD_LOGS_INJECTION=true và ddtrace.patch_all() (service/observability.py).",
        "Span tùy chỉnh qua trace_span (service/observability.py): mqtt.message.process trong service/mqtt.py; "
        "gemini.generate_content và smiot.ai.tool trong service/ai_service.py; lấy trace_id trong "
        "service/incident_lifecycle.py; service/special_incident_correlation.py.",
        "Nhờ DD_LOGS_INJECTION, log của ứng dụng mang trace_id để nối log với span.",
    ])

    H(d, "Log qua Datadog Agent", 2)
    P(d, "Agent đọc file log theo cấu hình deploy/datadog/smiot-logs.yaml: incident_events.jsonl và recovery/*.jsonl, "
         "service smiot-smart-farm. Theo PROGRESS.md (12/11), cấu hình Agent trên EC2 có thêm system.log và error.log.")

    H(d, "LLM Observability", 2)
    P(d, "LLM Observability được bật có điều kiện bằng biến DATADOG_LLMOBS_ENABLED, ml_app=smiot-smart-farm "
         "(service/observability.py, service/ai_service.py). Nội dung gửi đi được che theo thiết kế.")

    H(d, "Dashboard", 1)
    P(d, "Tổ chức Datadog có 5 dashboard SMIOT (đọc bằng GET ngày 13/11). Số widget lấy từ 5 file JSON trong "
         "deploy/datadog/terraform_farm_control_center/dashboards; các file này không chứa trường id.")
    T(d, ["Dashboard (live 13/11)", "ID", "Số widget (file JSON)", "File JSON"], [
        ["SMIOT | 10-Farm Portfolio", "rzf-su8-zgf", "6", "farm-portfolio"],
        ["SMIOT | Farm Data Quality", "g8w-hj8-px7", "5", "farm-data-quality"],
        ["SMIOT | IoT & MQTT Fleet", "kzx-fwc-sai", "7", "iot-mqtt-fleet"],
        ["SMIOT | Incident & Recovery", "isq-rzw-a6s", "6", "incident-recovery"],
        ["SMIOT | App, EC2, MongoDB & AI", "mzj-a5m-yh9", "7", "app-mongodb-ai"],
    ], caption="Dashboard SMIOT và số widget theo file JSON")
    F(d, fig03_widgets(), "Số widget của từng dashboard theo file JSON", 12.5)

    H(d, "Monitor", 1)
    P(d, "Tổ chức Datadog có 30 monitor, trong đó 19 monitor có SMIOT trong tên (GET /api/v1/monitor, 13/11). "
         "Bảng 3 liệt kê 19 monitor theo ID live. Trạng thái tức thời của monitor thay đổi theo thời điểm đọc nên không "
         "đưa vào bảng; kết quả phát hiện được trình bày trong tài liệu mô tả sự cố và tình huống trình diễn.")
    mon = [
        ["342585819", "SMIOT | sensor flatline", "query alert", "Flatline Node 2 (Ca 2)"],
        ["342585820", "telemetry not fresh", "query alert", "Độ mới của telemetry"],
        ["342585822", "telemetry ingest lag", "query alert", "Độ trễ nạp dữ liệu"],
        ["342585823", "persisted sample rate missing", "query alert", "Tốc độ ghi mẫu"],
        ["342585824", "AI ask latency high", "query alert", "Độ trễ truy vấn AI"],
        ["342585825", "PLC command latency high", "query alert", "Độ trễ lệnh PLC ảo"],
        ["342585827", "MongoDB dependency unhealthy", "query alert", "Phụ thuộc MongoDB"],
        ["342585828", "MQTT dependency unhealthy", "query alert", "Phụ thuộc MQTT"],
        ["342585830", "air temperature telemetry absent", "query alert", "Thiếu telemetry nhiệt độ không khí"],
        ["342585831", "telemetry sample stale", "query alert", "Mẫu telemetry cũ"],
        ["342585835", "soil humidity telemetry absent", "query alert", "Thiếu telemetry độ ẩm đất"],
        ["342585836", "telemetry status mismatch", "query alert", "Trạng thái không khớp mẫu (Ca 1)"],
        ["342585837", "soil temperature telemetry absent", "query alert", "Thiếu telemetry nhiệt độ đất"],
        ["342585838", "smiot.service inactive", "query alert", "Dịch vụ ứng dụng dừng (Ca 3)"],
        ["342734303", "virtual PLC safety trip (W1)", "query alert", "Ưu tiên 2. Dừng an toàn PLC ảo"],
        ["342734743", "actuator command unacknowledged (W9)", "query alert", "Ưu tiên 2. Lệnh chưa có ACK"],
        ["343029221", "W6 | Detector evaluation stalled", "query alert", "Ưu tiên 2. Heartbeat của detector"],
        ["343594185", "W8 | VPD and EC advisory review required", "query alert", "Khuyến nghị VPD và EC"],
        ["343594187", "W7 | soil moisture advisory review required", "query alert", "Khuyến nghị độ ẩm đất"],
    ]
    T(d, ["ID monitor", "Tên", "Loại", "Vai trò"], mon,
      caption="19 monitor SMIOT trên tổ chức Datadog (GET ngày 13/11)", font_size=10)
    F(d, fig03_monitors(), "Số monitor theo nguồn: live và định nghĩa trong Terraform", 12.5)

    H(d, "Workflow", 1)
    P(d, "Tổ chức Datadog có 10 workflow SMIOT, tất cả ở trạng thái published (GET /api/v2/workflows, 13/11).")
    T(d, ["ID workflow", "Tên", "Gắn với"], [
        ["ffd62026-6b63-40e4-9b46-6ac18d2d584f", "SMIOT | Ca 1 | Refuse restart when samples are fresh", "Ca 1"],
        ["2f9a3c1d-5292-4bc3-b4b9-cc03d4172724", "SMIOT | Ca 2 | Confirm local interlock", "Ca 2"],
        ["373ed0c0-4509-4fcd-a067-f54f0becc00e", "SMIOT | Guarded EC2 app recovery", "Ca 3"],
        ["50b3dc85-dd20-4220-bda1-ec78d2a3d00f", "SMIOT | W10 | AI failure safety verification", "W10"],
        ["b9e72b04-1580-45f8-ae1e-628124a19065", "SMIOT | W1 | Verify PLC safety trip evidence", "W1"],
        ["d3f0705e-2cbd-430a-9a3a-b1fd02a42cc9", "SMIOT | W5 | Root cause dependency triage", "W5"],
        ["d8e1b3db-1a54-4b4f-9be3-bf7e270a86f3", "SMIOT | W6 | Detector heartbeat review", "W6"],
        ["bb86206c-6df8-4b1d-8016-175a2fc62e49", "SMIOT | W7 | Irrigation schedule evidence review", "W7"],
        ["593a670c-d59c-4104-8658-df260245a21e", "SMIOT | W8 | Crop climate and EC evidence review", "W8"],
        ["47e95b24-db40-4cd5-b667-5b90e170b667", "SMIOT | W9 | Actuator acknowledgement verification", "W9"],
    ], caption="10 workflow SMIOT trên tổ chức Datadog (GET ngày 13/11)", font_size=10)
    T(d, ["Ca", "Trạng thái trên app", "Số lần diễn tập / phục hồi"], [
        ["Ca 1", "OK", "23 / 9"], ["Ca 2", "OK", "21 / 4"], ["Ca 3", "OK", "3 / 3"], ["W1", "OK", "16 / 2"],
        ["W5", "OK", "12 / 3"], ["W6", "OK", "207 / 3"], ["W7", "Alert", "11 / 3"], ["W8", "OK", "26 / 3"],
        ["W9", "OK", "15 / 2"], ["W10", "No Data", "17 / 6"],
    ], caption="Mười ca sự cố: trạng thái và số đếm trên app (13/11/2026, 11:02:50; số đếm do app ghi nhận, "
               "không phải kết quả đo)", font_size=10)
    P(d, "Monitor và workflow được tổ chức theo 10 ca sự cố: Ca 1 đến Ca 3, W1 và W5 đến W10 (cột Gắn với ở Bảng 4). "
         "Ánh xạ monitor, workflow và hành động của Ca 1 đến Ca 3 được minh họa ở Hình 4. Kịch bản diễn tập (A1 đến S6) "
         "chỉ dùng để demo trực tiếp và được trình bày trong tài liệu mô tả sự cố và tình huống trình diễn.")
    F(d, fig03_cases(), "Ánh xạ monitor, workflow và hành động cho ba ca trình diễn", 16)

    H(d, "Hạ tầng dạng mã", 1)
    P(d, "Cấu hình Datadog được khai báo bằng Terraform trong thư mục deploy/datadog. Tổng cộng có 23 định nghĩa monitor.")
    T(d, ["Thư mục / file", "Nội dung", "Số định nghĩa"], [
        ["deploy/datadog/terraform_monitors/monitors.tf", "Monitor, nối workflow bằng @workflow-smiot-... trong message; "
         "gồm 16 monitor trong for_each và 1 monitor detector_heartbeat (W6)", "17 monitor"],
        ["deploy/datadog/terraform_scenarios/terraform.tf",
         "Virtual PLC protective stop; safety trip/ACK imbalance; device reboot; telemetry sequence gap; "
         "duplicate/regressing sequence", "5 monitor"],
        ["deploy/datadog/terraform_w2_greenhouse_j/main.tf",
         "W2 greenhouse_j sensor flatline và một datadog_workflow_automation (w2-greenhouse-j.json, 12 bước)",
         "1 monitor, 1 workflow"],
        ["deploy/datadog/terraform_farm_control_center/", "5 dashboard JSON và một datadog_dashboard_json "
         "bổ sung trong main.tf", "5 dashboard"],
    ], caption="Định nghĩa Datadog trong Terraform", font_size=10)

    H(d, "Đọc ngược từ ứng dụng", 1)
    B(d, [
        "service/datadog_reader.py gọi Datadog API: /api/v2/events (lọc theo monitor_id) và /api/v2/logs/events "
        "(lọc theo chuỗi incident_id). Cần quyền events_read và logs_read_data.",
        "Ứng dụng nhận sự kiện từ Datadog qua POST /api/integrations/datadog/notification; xác thực bằng biến "
        "DATADOG_APP_NOTIFICATION_TOKEN. Sự kiện được ghi thành thông báo trong ứng dụng (chuông thông báo) và hiển thị ở /incident/{id}.",
        "Các endpoint khôi phục và xác minh do workflow gọi: POST /api/integrations/datadog/w2-greenhouse-j/recover, "
        ".../verify, POST /api/integrations/datadog/recovery-verification và "
        "POST /api/internal/safe-mode/recovery-clear (token SAFE_MODE_RECOVERY_TOKEN).",
        "Khôi phục dịch vụ có khóa đúng instance qua biến SMIOT_RECOVERY_INSTANCE_ID và AWS_REGION (main.py).",
    ])
    return style.save(d, os.path.join(OUT, "03_kien_truc_observability_datadog.docx")), d


# ---------------- Tai lieu 06 ----------------
def build_06():
    d = style.new_document("Mô tả sự cố và tình huống trình diễn")
    H, P, B, T, F = style.add_heading, style.add_paragraph, style.add_bullets, style.add_table, style.add_figure

    H(d, "Mục đích và cách đọc số liệu", 1)
    P(d, "Tài liệu mô tả danh mục ca sự cố, danh mục kịch bản diễn tập, ba ca trình diễn và kết quả diễn tập đo được trên nhà màng greenhouse_j. "
         "Kết quả lấy từ hai file JSON: drill_suite_20261112T225228Z.json (suite ngày 12/11) và "
         "drill_suite_pump_20261113T023126Z.json (suite bơm ngày 13/11). Tham số chung: giữ sự cố 90 s, chờ Datadog 360 s.")
    B(d, [
        "Mọi số ở mục 4 là dữ liệu diễn tập của kịch bản demo, mỗi kịch bản một lần chạy; không phải ngưỡng đã duyệt.",
        "Thời gian do script diễn tập đo; thời điểm phát hiện của Datadog được đọc từ trạng thái monitor theo chu kỳ.",
        "Thiết bị và cảm biến là mô phỏng; dữ liệu Velxio gắn synthetic=true.",
        "Tám kịch bản demo khác nhau đã chạy: A1, A2, A3, A4, C10, S2, S3, C2. Ở suite 12/11, A1, A2 và A4 không chạy được vì thiếu "
        "telemetry node2 trong 60 s; suite 13/11 chạy lại được cả ba mã.",
    ])

    H(d, "Mười ca sự cố", 1)
    P(d, "Hồ sơ gồm 10 ca sự cố (Ca 1 đến Ca 3, W1, W5 đến W10), hiển thị trên giao diện ứng dụng. Ca sự cố khác với "
         "kịch bản: kịch bản (A1, A2, A3, A4, C10, S2, S3, C2) chỉ dùng để demo trực tiếp và được trình bày ở mục 4. "
         "Bảng 1 nêu tên ca, monitor và workflow tương ứng (ID theo tổ chức Datadog, đọc ngày 13/11).")
    T(d, ["Ca", "Tên ca", "Monitor (ID live)", "Workflow (ID live)", "Trạng thái trên app", "Số lần diễn tập / phục hồi"], [
        ["Ca 1", "Báo offline sai", "telemetry status mismatch (342585836)", "ffd62026-6b63-40e4-9b46-6ac18d2d584f", "OK", "23 / 9"],
        ["Ca 2", "Node 2 đứng số đo", "sensor flatline (342585819)", "2f9a3c1d-5292-4bc3-b4b9-cc03d4172724", "OK", "21 / 4"],
        ["Ca 3", "smiot.service dừng", "smiot.service inactive (342585838)", "373ed0c0-4509-4fcd-a067-f54f0becc00e", "OK", "3 / 3"],
        ["W1", "PLC safety trip", "virtual PLC safety trip (342734303)", "b9e72b04-1580-45f8-ae1e-628124a19065", "OK", "16 / 2"],
        ["W5", "MongoDB/MQTT suy giảm",
         "MongoDB dependency unhealthy (342585827); MQTT dependency unhealthy (342585828) (ánh xạ suy theo tên)",
         "d3f0705e-2cbd-430a-9a3a-b1fd02a42cc9", "OK", "12 / 3"],
        ["W6", "Detector mất heartbeat", "W6 | Detector evaluation stalled (343029221)",
         "d8e1b3db-1a54-4b4f-9be3-bf7e270a86f3", "OK", "207 / 3"],
        ["W7", "Rủi ro độ ẩm đất", "W7 | soil moisture advisory review required (343594187)",
         "bb86206c-6df8-4b1d-8016-175a2fc62e49", "Alert", "11 / 3"],
        ["W8", "Rủi ro VPD/EC", "W8 | VPD and EC advisory review required (343594185)",
         "593a670c-d59c-4104-8658-df260245a21e", "OK", "26 / 3"],
        ["W9", "Actuator không ACK", "actuator command unacknowledged (342734743)",
         "47e95b24-db40-4cd5-b667-5b90e170b667", "OK", "15 / 2"],
        ["W10", "AI provider lỗi", "Không có monitor trong bộ đã đọc", "50b3dc85-dd20-4220-bda1-ec78d2a3d00f", "No Data", "17 / 6"],
    ], caption="Mười ca sự cố, monitor, workflow và số đếm trên app", font_size=8)
    P(d, "Cột Trạng thái trên app và Số lần diễn tập / phục hồi là số đếm do giao diện ứng dụng ghi nhận lúc 11:02:50 "
         "ngày 13/11/2026 (Datadog API chỉ đọc), không phải kết quả đo của diễn tập.")

    H(d, "Luồng Phát hiện, Điều tra, Phản ứng của các ca", 1)
    F(d, fig06_cases(), "Ba ca trình diễn theo ba pha Phát hiện, Điều tra, Phản ứng", 16)
    H(d, "Ca 1: báo offline sai", 2)
    B(d, [
        "Sự cố: giao diện hiển thị trạng thái OFFLINE trong khi mẫu vẫn được ghi vào MongoDB.",
        "Phát hiện: monitor telemetry status mismatch (342585836).",
        "Điều tra trên Datadog: trạng thái monitor telemetry status mismatch (Alert lúc 04:49:21Z, OK lúc 05:00:21Z), metric smiot.*, "
        "log và trace có incident_id của sự cố dùng để khoanh vùng.",
        "Điều tra trên MongoDB: hồ sơ sự cố và mẫu telemetry mới nhất, đối chiếu với trạng thái OFFLINE hiển thị.",
        "Phản ứng: workflow Ca 1 | Refuse restart when samples are fresh (ffd62026-6b63-40e4-9b46-6ac18d2d584f) từ chối "
        "khởi động lại khi mẫu còn mới.",
        "Mốc monitor: Alert lúc 04:49:21Z, OK lúc 05:00:21Z.",
    ])
    H(d, "Ca 2: độ ẩm đất Node 2 đứng yên", 2)
    B(d, [
        "Sự cố: cảm biến độ ẩm đất Node 2 đứng yên (flatline); tham số kịch bản 10 mẫu, 0,01, 600 s.",
        "Phát hiện: monitor SMIOT | sensor flatline (342585819).",
        "Điều tra trên Datadog: theo trạng thái monitor trên Datadog (sensor flatline), cùng metric smiot.* và log, trace có incident_id của sự cố.",
        "Điều tra trên MongoDB: hồ sơ sự cố và bằng chứng telemetry của Node 2.",
        "Phản ứng: workflow Ca 2 | Confirm local interlock (2f9a3c1d-5292-4bc3-b4b9-cc03d4172724) xác nhận khóa liên động cục bộ.",
    ])
    H(d, "Ca 3: smiot.service dừng", 2)
    B(d, [
        "Sự cố: dịch vụ ứng dụng smiot.service dừng.",
        "Phát hiện: monitor smiot.service inactive (342585838).",
        "Điều tra trên Datadog: trạng thái monitor smiot.service inactive (Alert lúc 03:11:43Z, OK lúc 03:13:43Z), metric smiot.* và log có incident_id để khoanh vùng.",
        "Điều tra trên MongoDB: hồ sơ sự cố và dữ liệu telemetry quanh thời điểm dịch vụ dừng, cùng health của ứng dụng.",
        "Phản ứng: workflow SMIOT | Guarded EC2 app recovery (373ed0c0-4509-4fcd-a067-f54f0becc00e) khôi phục có guard "
        "(khóa, thời gian chờ giữa hai lần, danh sách lệnh cho phép) và xác minh bằng health cùng MongoDB.",
        "Mốc monitor: Alert lúc 03:11:43Z, OK lúc 03:13:43Z.",
    ])
    T(d, ["Ca", "Monitor (ID live)", "Workflow (ID live)", "Mốc monitor"], [
        ["Ca 1", "telemetry status mismatch (342585836)", "ffd62026-6b63-40e4-9b46-6ac18d2d584f", "Alert 04:49:21Z, OK 05:00:21Z"],
        ["Ca 2", "sensor flatline (342585819)", "2f9a3c1d-5292-4bc3-b4b9-cc03d4172724", "Theo trạng thái monitor trên Datadog"],
        ["Ca 3", "smiot.service inactive (342585838)", "373ed0c0-4509-4fcd-a067-f54f0becc00e", "Alert 03:11:43Z, OK 03:13:43Z"],
    ], caption="Tóm tắt Ca 1 đến Ca 3", font_size=10)
    H(d, "Các ca W1, W5 đến W10", 2)
    T(d, ["Ca", "Phát hiện", "Điều tra", "Phản ứng (workflow)"], [
        ["W1", "virtual PLC safety trip (342734303)", "Log, trace Datadog theo incident_id; hồ sơ và bằng chứng trong MongoDB",
         "Verify PLC safety trip evidence"],
        ["W5", "MongoDB/MQTT dependency unhealthy (342585827, 342585828)", "Log, trace Datadog theo incident_id; hồ sơ và bằng chứng trong MongoDB",
         "Root cause dependency triage"],
        ["W6", "W6 | Detector evaluation stalled (343029221)", "Log, trace Datadog theo incident_id; hồ sơ và bằng chứng trong MongoDB",
         "Detector heartbeat review"],
        ["W7", "W7 | soil moisture advisory review required (343594187)", "Log, trace Datadog theo incident_id; hồ sơ và bằng chứng trong MongoDB",
         "Irrigation schedule evidence review"],
        ["W8", "W8 | VPD and EC advisory review required (343594185)", "Log, trace Datadog theo incident_id; hồ sơ và bằng chứng trong MongoDB",
         "Crop climate and EC evidence review"],
        ["W9", "actuator command unacknowledged (342734743)", "Log, trace Datadog theo incident_id; hồ sơ và bằng chứng trong MongoDB",
         "Actuator acknowledgement verification"],
        ["W10", "Không có monitor trong bộ đã đọc", "Log, trace Datadog theo incident_id; hồ sơ và bằng chứng trong MongoDB", "AI failure safety verification"],
    ], caption="Phát hiện, điều tra và phản ứng của W1 và W5 đến W10", font_size=9)

    H(d, "Kịch bản demo trực tiếp", 1)
    P(d, "Mục này trình bày các kịch bản demo, không phải ca sự cố. Kịch bản gắn với monitor của các ca như sau: "
         "W1 gồm A1, A2, A3, C10; W7 gồm S2 (S3 do monitor flatline phát hiện); W8 gồm C2; W9 gồm A4.")
    H(d, "Danh mục 36 kịch bản", 2)
    P(d, "Danh mục khai báo trong service/scenario_catalog.py gồm 36 mã, chia thành năm nhóm.")
    T(d, ["Nhóm", "Mã", "Số mã", "Module nguồn"], [
        ["A", "A1-A7", "7", "service/scenario_domain_actuator_infra.py"],
        ["C (cây trồng)", "C1-C10", "10", "service/scenario_domain_crops.py"],
        ["D (thiết bị)", "D1-D7", "7", "service/scenario_domain_sensor_device.py"],
        ["H", "H1-H6", "6", "service/scenario_domain_actuator_infra.py"],
        ["S", "S1-S6", "6", "service/scenario_domain_sensor_device.py"],
        ["Tổng", "", "36", "service/scenario_catalog.py"],
    ], caption="Danh mục kịch bản demo theo nhóm")
    H(d, "Suite ngày 12/11/2026", 2)
    P(d, "Nguồn: drill_suite_20261112T225228Z.json. Các mã A3, C10, S2, S3, C2 đã chạy; A1, A2, A4 không chạy được "
         "do thiếu telemetry node2 trong 60 s và được đo lại ở suite 13/11 (mục 4.3).")
    T(d, ["Mã", "Kịch bản", "Monitor", "ACK", "Datadog phát hiện (s)", "App khôi phục (s)", "Datadog về OK sau (s)",
          "Hồ sơ sự cố"], [
        ["A3", "a3_low_flow", "W1 (342734303)", "Started, applied", "109,8", "1,4", "317,6",
         "INC-SMIOT-SCENARIO-9F3A2859A819F323 (open)"],
        ["C10", "pipe_leak", "W1 (342734303)", "Started, applied", "79,1", "1,5", "286,5",
         "INC-SMIOT-SCENARIO-B840598BD9CF6644 (holding)"],
        ["S2", "soil_spike", "W7 (343594187)", "Started, applied", "Monitor không phát hiện", "13,0", "Không áp dụng",
         "INC-SMIOT-SCENARIO-676B9F7C0FCE4434 (open)"],
        ["S3", "soil_out_of_range", "Sensor flatline (342585819)", "Started, applied", "0,6", "13,2",
         "Không về OK trong dữ liệu ghi nhận", "INC-SMIOT-SCENARIO-5E92235C67178079 (open)"],
        ["C2", "scenario_type C2", "W8 (343594185)", "Started, applied", "Monitor không phát hiện", "12,1",
         "Không áp dụng", "INC-SMIOT-SCENARIO-E6C842D9B25E0F29 (open)"],
    ], caption="Kết quả suite ngày 12/11/2026 (dữ liệu diễn tập)", font_size=9)
    B(d, [
        "A3 và C10 có lệnh CLEAR safe mode. Trước khi bắt đầu A3, script chờ monitor về OK (127 s).",
        "S3: monitor báo là monitor flatline (342585819); không phải monitor W7.",
        "Ở các mã đã chạy, số mẫu MongoDB có scenario_run_id là 0; mỗi mã có 1 đến 2 bản ghi scenario_observations.",
        "MQTT ghi nhận trong suite: farm/sensor 3407, farm/status 4693, farm/command/ack 6.",
    ])

    H(d, "Suite bơm ngày 13/11/2026", 2)
    P(d, "Nguồn: drill_suite_pump_20261113T023126Z.json. Mạch nhận là node2 (ACK của bơm ảo qua cầu nối Velxio).")
    T(d, ["Mã", "ACK bơm (s sau T0)", "Datadog phát hiện (s)", "Datadog về OK sau (s)", "App khôi phục (s)",
          "Hồ sơ sự cố", "Ghi chú"], [
        ["A1", "1,0", "Monitor không Alert", "Không áp dụng", "4,2", "INC-SMIOT-SCENARIO-9D18A090182D7BC4 (open)",
         "Log velxio_profile_ack_forwarded, device=node2, profile=fault, verified=True"],
        ["A2", "0,55", "79,1", "286,3", "Không áp dụng", "INC-SMIOT-SCENARIO-B4D3B09D9FB6BCA0 (holding)",
         "Có CLEAR safe mode"],
        ["A4", "0,65", "Monitor không Alert", "Không áp dụng", "Không áp dụng",
         "INC-SMIOT-SCENARIO-3A00032EB64EEF03 (open); 6 observations",
         "SET_OUTPUTS bit0=1 sau START 5 s, bit0=0 sau khi W9 hết hạn; T_stop 360,3 s sau T0"],
    ], caption="Kết quả suite bơm ngày 13/11/2026 (dữ liệu diễn tập)", font_size=9)
    B(d, [
        "Bước dọn cuối (final_cleanup) gửi SET_OUTPUTS bit0=0 và CLEAR.",
        "MQTT ghi nhận trong suite: farm/sensor 1823, farm/status 2458, farm/command/ack 13, "
        "farm/demo/device_profile/ack 8.",
    ])

    P(d, "Tổng hợp phát hiện: monitor Datadog phát hiện 4 trên 8 mã diễn tập (A2, A3, C10 và S3 ở mục kết quả). "
         "A2 (suite bơm 13/11): Datadog phát hiện 79,1 s, về OK 286,3 s. C10 (suite 12/11): phát hiện 79,1 s, về OK 286,5 s. "
         "A3 (suite 12/11) có mốc về OK 317,6 s; S3 ghi nhận phát hiện 0,6 s nhưng chưa có bằng chứng phục hồi về OK. "
         "Bốn mã còn lại (A1, A4, S2, C2) không có mốc phát hiện của monitor trong lần chạy nên chưa có bằng chứng phục hồi về OK để đối chiếu. "
         "Đây là ghi nhận của một lần chạy mỗi mã, không phải nhận định cuối cùng về monitor.")
    H(d, "Biểu đồ thời gian", 2)
    F(d, fig06_timeline(), "Dòng thời gian của C10 và A3 (suite 12/11)", 15.5)
    F(d, fig06_bars(), "Thời gian Datadog phát hiện và app khôi phục theo mã", 15.5)
    P(d, "Ghi chú Hình 3: các mã không có cột đỏ là mã mà monitor không chuyển sang Alert trong lần chạy; "
         "các mã không có cột xanh là mã không áp dụng đo thời gian khôi phục của app. "
         "S3 ghi nhận phát hiện 0,6 s bởi monitor flatline.")

    H(d, "Ranh giới mô phỏng", 1)
    B(d, [
        "Thiết bị và cảm biến là mô phỏng: thiết bị ảo nhúng trong ứng dụng và ba project Velxio "
        "(velxio/node1_environment, node2_virtual_pump, node3_flow_monitor).",
        "Cầu nối scripts/velxio_mqtt_bridge.py chuyển thông điệp Velxio sang envelope farm/sensor, chỉ chuyển lệnh trong "
        "danh sách cho phép, gắn synthetic=true và source=velxio_synthetic.",
        "Kết quả ngày 13/11 là ACK của bơm ảo node2 qua cầu nối; không có thiết bị vật lý.",
        "Quan sát kịch bản được ghi với execution_mode=SIMULATED_ONLY (collection scenario_observations).",
        "Hệ thống không điều khiển bơm, van, quạt phần cứng thật (PRD.md, phần ngoài phạm vi).",
    ])
    return style.save(d, os.path.join(OUT, "06_mo_ta_su_co_tinh_huong_trinh_dien.docx")), d


if __name__ == "__main__":
    p3, d3 = build_03()
    p6, d6 = build_06()
    print(p3, d3._smiot_fig, d3._smiot_tab)
    print(p6, d6._smiot_fig, d6._smiot_tab)
