# -*- coding: utf-8 -*-
"""Dung 01_kien_truc_giai_phap.docx va 07_khai_bao_thanh_phan_va_cong_cu.docx"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.dirname(HERE)
IMG = os.path.join(HERE, "img")
os.makedirs(IMG, exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

import style as S

plt.rcParams["font.family"] = "DejaVu Sans"
C_BLUE, C_GREEN, C_ORANGE, C_GREY, C_PURPLE = "#DCE9F7", "#DFF0D8", "#FCE8CF", "#EEEEEE", "#E8DDF3"
EDGE = "#333333"


def box(ax, x, y, w, h, text, fc=C_BLUE, fs=9, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=fc, ec=EDGE, lw=1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", wrap=True)


def arrow(ax, x1, y1, x2, y2, text=None, fs=8):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14,
                                 lw=1.3, color=EDGE))
    if text:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.12, text, ha="center", fontsize=fs)


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def save(fig, name):
    p = os.path.join(IMG, name)
    fig.savefig(p, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return p


# ---------------------------------------------------------------- hinh 01
def fig_three_phases():
    fig, ax = canvas(11, 5.6)
    cols = [(0.3, "PHÁT HIỆN", C_BLUE,
             ["Watchdog telemetry", "Kiểm tra số thứ tự mẫu", "Heartbeat của detector", "Monitor Datadog"]),
            (3.95, "ĐIỀU TRA", C_GREEN,
             ["Hồ sơ sự cố (MongoDB)", "Hộp đen sự cố: dòng thời gian", "Datadog: metric, log, span", "Trang /incident/{id}"]),
            (7.6, "PHẢN ỨNG", C_ORANGE,
             ["Lệnh MQTT có ACK", "Khôi phục dịch vụ có guard", "Xác minh phục hồi", "Thông báo trong ứng dụng"])]
    for x, title, fc, items in cols:
        box(ax, x, 4.2, 3.1, 0.9, title, fc=fc, fs=13, bold=True)
        for i, it in enumerate(items):
            box(ax, x, 3.1 - i * 0.95, 3.1, 0.75, it, fc="white", fs=9)
    arrow(ax, 3.45, 4.65, 3.85, 4.65)
    arrow(ax, 7.1, 4.65, 7.5, 4.65)
    return save(fig, "A_hinh1_ba_pha.png")


# ---------------------------------------------------------------- hinh 02
def fig_architecture():
    fig, ax = canvas(11, 6.4)
    box(ax, 0.2, 4.9, 2.6, 1.0, "Thiết bị ảo trong ứng dụng\n(9 nhóm mỗi nhà màng)", C_GREY, 9)
    box(ax, 0.2, 3.4, 2.6, 1.0, "Velxio ESP32 (3 project)\nnode1, node2, node3", C_GREY, 9)
    box(ax, 0.2, 1.9, 2.6, 1.0, "Cầu nối Velxio\nsynthetic=true", C_GREY, 9)
    box(ax, 3.5, 3.4, 1.9, 1.4, "MQTT\nfarm/sensor\nfarm/status\nfarm/command/ack", C_PURPLE, 9)
    box(ax, 6.2, 3.0, 2.2, 2.4, "Ứng dụng NiceGUI\n(smiot.service)\ningest, watchdog,\nsự cố, điều hướng", C_BLUE, 9, True)
    box(ax, 9.0, 4.6, 1.9, 1.2, "MongoDB\nbằng chứng,\nhồ sơ sự cố", C_GREEN, 9)
    box(ax, 9.0, 2.9, 1.9, 1.2, "Datadog\nmetric, log, span,\nmonitor", C_ORANGE, 9)
    box(ax, 9.0, 1.2, 1.9, 1.2, "Workflow có guard\n(Datadog)", C_ORANGE, 9)
    box(ax, 6.2, 1.2, 2.2, 1.1, "Người vận hành\n/incident/{id}, chuông", C_GREY, 9)
    arrow(ax, 2.8, 5.3, 3.5, 4.5)
    arrow(ax, 2.8, 3.9, 3.5, 4.1)
    arrow(ax, 1.5, 3.4, 1.5, 2.95)
    arrow(ax, 2.8, 2.4, 3.7, 3.4)
    arrow(ax, 5.4, 4.1, 6.2, 4.1)
    arrow(ax, 8.4, 4.6, 9.0, 5.1, "ghi")
    arrow(ax, 8.4, 3.9, 9.0, 3.5, "DogStatsD, ddtrace, log")
    arrow(ax, 9.95, 2.9, 9.95, 2.4, "monitor")
    arrow(ax, 9.0, 1.8, 8.4, 1.8)
    arrow(ax, 7.3, 2.3, 7.3, 3.0, "")
    ax.text(5.5, 0.55, "Workflow gọi lại ứng dụng: lệnh MQTT có ACK hoặc khôi phục dịch vụ có guard; "
            "ứng dụng giữ khóa an toàn cục bộ.", ha="center", fontsize=9, style="italic")
    return save(fig, "A_hinh2_kien_truc.png")


# ---------------------------------------------------------------- hinh 03
def fig_roles():
    fig, ax = canvas(11, 4.8)
    box(ax, 0.3, 1.0, 3.1, 3.0, "DATADOG\nTrung tâm ba pha\n\nMonitor, metric: phát hiện\nLog, trace: điều tra\nWorkflow có guard: phản ứng", C_ORANGE, 10, True)
    box(ax, 3.95, 1.0, 3.1, 3.0, "MONGODB\nNền dữ liệu và bằng chứng\n\nHồ sơ sự cố, sổ lệnh,\nmẫu telemetry,\nhộp đen sự cố", C_GREEN, 10, True)
    box(ax, 7.6, 1.0, 3.1, 3.0, "ỨNG DỤNG\nĐiều hướng\n\n/incident/{id}, thông báo,\nkhóa an toàn cục bộ,\nxác minh phục hồi", C_BLUE, 10, True)
    ax.text(5.5, 0.4, "Correlation ID (incident_id) đi trong log, span và document MongoDB; không dùng làm tag metric.",
            ha="center", fontsize=9, style="italic")
    arrow(ax, 3.4, 2.5, 3.95, 2.5)
    arrow(ax, 7.05, 2.5, 7.6, 2.5)
    return save(fig, "A_hinh3_phan_vai.png")


# ---------------------------------------------------------------- hinh 04 (bieu do cot)
def fig_counts():
    fig, ax = plt.subplots(figsize=(9, 4.6))
    labels = ["Nhà màng", "Route UI", "Route API", "Module pages/", "Module service/", "File test", "Project Velxio"]
    vals = [10, 16, 10, 15, 37, 41, 3]
    bars = ax.bar(labels, vals, color="#4C78A8")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.8, str(v), ha="center", fontsize=10)
    ax.set_ylabel("Số lượng")
    ax.set_ylim(0, 48)
    plt.xticks(rotation=20, ha="right", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    return save(fig, "A_hinh4_so_lieu.png")


# ---------------------------------------------------------------- hinh 07
def fig_layers():
    fig, ax = canvas(11, 6.6)
    layers = [
        ("Lớp hạ tầng", C_GREY, "EC2 (ap-southeast-2) | systemd smiot.service | Datadog Agent | MQTT broker nội bộ | MongoDB Community"),
        ("Lớp dữ liệu và quan sát", C_GREEN, "MongoDB (pymongo) | Datadog (ddtrace, DogStatsD, log, API) | Terraform"),
        ("Lớp ứng dụng", C_BLUE, "NiceGUI | main.py + pages/ (15) + service/ (37) + components/ | API HTTP (11 route)"),
        ("Lớp dịch vụ ngoài", C_ORANGE, "Open-Meteo (thời tiết) | Gemini (AI, công cụ chỉ đọc) | Telegram (bot)"),
        ("Lớp mô phỏng và công cụ", C_PURPLE, "Velxio ESP32 (3 project) | Cầu nối MQTT | Danh mục 36 kịch bản | scripts/ (62 file .py)"),
    ]
    y = 5.4
    for name, fc, txt in layers:
        box(ax, 0.2, y, 2.4, 0.95, name, fc, 10, True)
        box(ax, 2.8, y, 7.9, 0.95, txt, "white", 9)
        y -= 1.15
    return save(fig, "A_hinh7_phan_lop.png")


# ======================================================================
def build_01():
    d = S.new_document("Kiến trúc giải pháp")
    P, B, T, F, H = S.add_paragraph, S.add_bullets, S.add_table, S.add_figure, S.add_heading

    H(d, "Bài toán và phạm vi", 1)
    P(d, "Dự án xây dựng một trung tâm giám sát, điều hành và phục hồi sau sự cố cho 10 nhà màng trồng dưa lưới "
         "ảo, mã từ greenhouse_a đến greenhouse_j (nguồn: service/farm_registry.py). Hệ thống là mô phỏng vận hành: "
         "thiết bị và cảm biến là thiết bị ảo; dữ liệu từ Velxio được gắn nhãn synthetic=true (nguồn: PRD.md, "
         "scripts/velxio_mqtt_bridge.py).")
    P(d, "Phạm vi của giải pháp:")
    B(d, ["Phát hiện sự cố trên dữ liệu cảm biến và trạng thái dịch vụ của 10 nhà màng.",
          "Điều tra bằng hồ sơ sự cố, hộp đen sự cố trong MongoDB và tín hiệu quan sát trong Datadog.",
          "Phản ứng bằng lệnh có xác nhận (ACK) hoặc khôi phục dịch vụ có guard, sau đó xác minh phục hồi."])
    P(d, "Ngoài phạm vi: điều khiển bơm, van, quạt phần cứng thật; tự khởi động lại máy chủ EC2; cam kết năng suất "
         "cây trồng (nguồn: PRD.md, mục Out of scope).")

    H(d, "Mô hình Phát hiện – Điều tra – Phản ứng", 1)
    P(d, "Giải pháp tổ chức theo ba pha liên tiếp (nguồn: ARCHITECTURE.md, mục Main data path).")
    F(d, fig_three_phases(), "Mô hình ba pha Phát hiện – Điều tra – Phản ứng")
    H(d, "Phát hiện", 2)
    B(d, ["Watchdog telemetry và các phát hiện (findings) ghi vào MongoDB (service/telemetry_findings.py).",
          "Kiểm tra số thứ tự mẫu: trùng, lùi, thiếu (service/telemetry_health.py; metric smiot.telemetry.sequence_*).",
          "Heartbeat của detector (service/detector_heartbeat.py; monitor W6 mã 343029221).",
          "Monitor Datadog trên metric smiot.* (19 monitor SMIOT, nguồn đọc trực tiếp 13/11)."])
    H(d, "Điều tra", 2)
    B(d, ["Hồ sơ sự cố trong collection operational_incidents (service/incident_lifecycle.py).",
          "Hộp đen sự cố: dòng thời gian gộp 7 nhánh $unionWith và đánh dấu khoảng thiếu mẫu (service/incident_blackbox.py).",
          "Datadog giữ metric, log có incident_id và span; ứng dụng đọc lại sự kiện, log qua service/datadog_reader.py."])
    H(d, "Phản ứng", 2)
    B(d, ["Lệnh MQTT có ACK, ghi vào sổ lệnh action_ledger (service/mqtt.py).",
          "Khôi phục dịch vụ có guard: chỉ khởi động smiot.service, có khóa, thời gian chờ giữa hai lần và kiểm tra lại "
          "(docs/DATADOG_GUARDED_RECOVERY.md).",
          "Xác minh phục hồi bằng health, MongoDB, MQTT và telemetry mới (service/w3_recovery_verification.py)."])

    H(d, "Kiến trúc tổng thể", 1)
    H(d, "Thành phần chính", 2)
    F(d, fig_architecture(), "Sơ đồ kiến trúc thành phần")
    T(d, ["Thành phần", "Thực tế trong mã", "Nguồn"], [
        ["Ứng dụng", "NiceGUI: main.py, 15 module pages/, 37 module service/, components/", "main.py; thống kê thư mục"],
        ["Giao diện", "16 route @ui.page, trong đó /lot/{token} là trang công khai chỉ đọc", "main.py; pages/*.py"],
        ["API HTTP", "11 route @app (kịch bản, health, tích hợp Datadog, safe mode)", "main.py"],
        ["Thiết bị ảo", "9 nhóm thiết bị ảo mỗi nhà màng; actuator ảo: bơm, van, quạt, lưu lượng, áp suất, thông gió", "PRD.md; ARCHITECTURE.md"],
        ["Velxio ESP32", "3 project: node1_environment, node2_virtual_pump, node3_flow_monitor", "velxio/"],
        ["Cầu nối Velxio", "Chuyển thông điệp Velxio thành envelope farm/sensor, chỉ chuyển lệnh trong danh sách cho phép", "scripts/velxio_mqtt_bridge.py"],
        ["MQTT", "Chủ đề: farm/sensor, farm/status, farm/command/ack, farm/demo/*", "service/mqtt.py; ARCHITECTURE.md"],
        ["MongoDB", "Community, self-managed; pymongo>=4.0,<4.18", "service/mongodb_store.py; requirements.txt"],
        ["Datadog", "ddtrace>=4.16.1,<5.0, DogStatsD, log qua Agent, API đọc monitor/workflow/dashboard", "requirements.txt; service/observability.py"],
        ["AI", "Gemini, công cụ chỉ đọc, bot Telegram", "service/ai_service.py; service/ai_tools.py"],
        ["Thời tiết", "Open-Meteo, hiển thị nguồn dữ liệu", "service/weather_api.py"],
    ], caption="Thành phần chính và nguồn đối chiếu")
    H(d, "Phân vai MongoDB – Datadog – ứng dụng", 2)
    P(d, "Datadog là trung tâm của cả ba pha. Ở pha Phát hiện, monitor và metric smiot.* nhận biết điều bất thường. "
         "Ở pha Điều tra, log, trace và bối cảnh monitor, workflow quanh cùng một correlation ID cho biết nguyên nhân. "
         "Ở pha Phản ứng, workflow có guard thực hiện phản ứng và nhận xác minh khi monitor trở về OK. "
         "MongoDB giữ hồ sơ sự cố, sổ lệnh action_ledger, hộp đen sự cố và bằng chứng telemetry. "
         "Ứng dụng điều hướng người vận hành và giữ các khóa an toàn cục bộ (nguồn: ARCHITECTURE.md).")
    F(d, fig_roles(), "Phân vai giữa Datadog, MongoDB và ứng dụng")
    H(d, "Triển khai trên EC2", 2)
    B(d, ["Vùng AWS ap-southeast-2.",
          "Biến môi trường nằm trong tệp riêng của dịch vụ; hồ sơ này chỉ nêu tên biến, không nêu giá trị.",
          "Khôi phục dịch vụ kiểm tra đúng máy chủ qua biến SMIOT_RECOVERY_INSTANCE_ID và AWS_REGION (main.py)."])

    H(d, "Luồng dữ liệu và nguyên tắc an toàn cục bộ", 1)
    P(d, "Luồng dữ liệu (nguồn: ARCHITECTURE.md; service/mqtt.py; service/mongodb_telemetry.py):")
    B(d, ["Thiết bị ảo trong ứng dụng và Velxio ESP32 phát thông điệp lên MQTT (farm/sensor, farm/status, farm/command/ack).",
          "Ứng dụng nhận, kiểm tra nguồn và sức khỏe mẫu (telemetry_provenance.py, telemetry_health.py), ghi mẫu vào MongoDB.",
          "Watchdog và detector tạo phát hiện, mở hồ sơ sự cố và hộp đen.",
          "Ứng dụng gửi metric DogStatsD, span và log có incident_id tới Datadog; monitor đánh giá tín hiệu.",
          "Workflow có guard của Datadog gọi lại ứng dụng để gửi lệnh có ACK hoặc khôi phục dịch vụ.",
          "Ứng dụng xác minh phục hồi và hiển thị trên /incident/{id} cùng chuông thông báo."])
    P(d, "Nguyên tắc an toàn cục bộ: Datadog quan sát và điều phối; khóa an toàn (PLC ảo, interlock) do ứng dụng giữ. "
         "Correlation ID đi trong log, span và document MongoDB, không đưa vào tag metric để giữ số tổ hợp tag ở mức thấp "
         "(nguồn: ARCHITECTURE.md).")

    H(d, "Mười ca sự cố", 1)
    P(d, "Giao diện ứng dụng (ảnh chụp ngày 13/11/2026) trình bày 10 ca sự cố. Mỗi ca được ghép với monitor và workflow "
         "đọc trực tiếp từ Datadog ngày 13/11/2026 (ID công khai trong tổ chức).")
    T(d, ["Ca", "Tên ca", "Monitor (ID)", "Workflow (ID)"], [
        ["Ca 1", "Báo offline sai", "SMIOT | telemetry status mismatch (342585836)", "Ca 1 | Refuse restart when samples are fresh (ffd62026-6b63-40e4-9b46-6ac18d2d584f)"],
        ["Ca 2", "Node 2 đứng số đo", "SMIOT | sensor flatline (342585819)", "Ca 2 | Confirm local interlock (2f9a3c1d-5292-4bc3-b4b9-cc03d4172724)"],
        ["Ca 3", "smiot.service dừng", "SMIOT | smiot.service inactive (342585838)", "Guarded EC2 app recovery (373ed0c0-4509-4fcd-a067-f54f0becc00e)"],
        ["W1", "PLC safety trip", "virtual PLC safety trip (342734303)", "W1 | Verify PLC safety trip evidence (b9e72b04-1580-45f8-ae1e-628124a19065)"],
        ["W5", "MongoDB/MQTT suy giảm", "MongoDB dependency unhealthy (342585827)", "W5 | Root cause dependency triage (d3f0705e-2cbd-430a-9a3a-b1fd02a42cc9)"],
        ["W6", "Detector mất heartbeat", "W6 | Detector evaluation stalled (343029221)", "W6 | Detector heartbeat review (d8e1b3db-1a54-4b4f-9be3-bf7e270a86f3)"],
        ["W7", "Rủi ro độ ẩm đất", "W7 | soil moisture advisory review required (343594187)", "W7 | Irrigation schedule evidence review (bb86206c-6df8-4b1d-8016-175a2fc62e49)"],
        ["W8", "Rủi ro VPD/EC", "W8 | VPD and EC advisory review required (343594185)", "W8 | Crop climate and EC evidence review (593a670c-d59c-4104-8658-df260245a21e)"],
        ["W9", "Actuator không ACK", "actuator command unacknowledged (342734743)", "W9 | Actuator acknowledgement verification (47e95b24-db40-4cd5-b667-5b90e170b667)"],
        ["W10", "AI provider lỗi", "Monitor 342585824", "W10 | AI failure safety verification (50b3dc85-dd20-4220-bda1-ec78d2a3d00f)"],
    ], caption="Mười ca sự cố, monitor và workflow (nguồn: Datadog API, 13/11/2026)", font_size=10)
    T(d, ["Ca", "Tên ca", "Trạng thái trên app", "Số lần diễn tập", "Số lần phục hồi"], [
        ["Ca 1", "Báo offline sai", "OK", "23", "9"],
        ["Ca 2", "Node 2 đứng số đo", "OK", "21", "4"],
        ["Ca 3", "smiot.service dừng", "OK", "3", "3"],
        ["W1", "PLC safety trip", "OK", "16", "2"],
        ["W5", "MongoDB/MQTT suy giảm", "OK", "12", "3"],
        ["W6", "Detector mất heartbeat", "OK", "207", "3"],
        ["W7", "Rủi ro độ ẩm đất", "Alert", "11", "3"],
        ["W8", "Rủi ro VPD/EC", "OK", "26", "3"],
        ["W9", "Actuator không ACK", "OK", "15", "2"],
        ["W10", "AI provider lỗi", "No Data", "17", "6"],
    ], caption="Số đếm do ứng dụng ghi nhận (nguồn: giao diện ứng dụng, 13/11/2026 11:02:50, Datadog API chỉ đọc)", font_size=10)
    P(d, "Các số trên là số đếm do ứng dụng ghi nhận, không phải kết quả đo.")
    P(d, "Mười ca trên là phạm vi sự cố được giám sát. Để trình diễn trực tiếp, hệ thống có danh mục 36 kịch bản (nguồn: service/scenario_catalog.py); kịch bản chỉ dùng cho phần demo, không phải là ca sự cố.")

    H(d, "Bảo mật và ranh giới", 1)
    T(d, ["Cơ chế", "Chi tiết", "Nguồn"], [
        ["Băm mật khẩu", "PBKDF2-HMAC-SHA256, 310.000 vòng, salt 16 byte; so sánh bằng hmac.compare_digest", "service/auth.py"],
        ["Khóa đăng nhập tạm", "5 lần sai trong cửa sổ thời gian thì khóa tạm", "service/auth.py"],
        ["Phân quyền", "14 quyền cố định, vai trò admin/operator/viewer, phạm vi theo nhà màng; chỉ admin thao tác tài khoản admin", "service/auth.py"],
        ["Trang sự cố", "/incident/{id} yêu cầu đăng nhập và quyền quản trị (manage_users)", "pages/incident.py; PRD.md"],
        ["Khóa session", "Nếu thiếu NICEGUI_STORAGE_SECRET, ứng dụng cảnh báo và tự sinh secret ngẫu nhiên; cookie https_only", "service/session_security.py; main.py"],
        ["API kịch bản", "Bearer token riêng (SMIOT_DEMO_CONTROL_TOKEN); SMIOT_DEMO_MODE chỉ điều khiển route xác nhận muộn W9", "main.py"],
        ["Idempotency", "Idempotency-Key bắt buộc (tối đa 200 ký tự); băm token và key lưu trong MongoDB", "main.py"],
        ["Giới hạn tốc độ", "20 ghi và 120 đọc mỗi token trong 60 giây", "main.py"],
        ["Khóa theo nhà màng", "Mỗi nhà màng chạy một kịch bản tại một thời điểm (scenario_api_farm_locks)", "main.py"],
        ["Token tích hợp", "DATADOG_APP_NOTIFICATION_TOKEN và SAFE_MODE_RECOVERY_TOKEN cho endpoint nhận sự kiện và khôi phục", "main.py"],
        ["Khôi phục có guard", "Chỉ systemctl start smiot.service, có khóa và thời gian chờ", "docs/DATADOG_GUARDED_RECOVERY.md"],
        ["Nhãn nguồn dữ liệu", "Mẫu Velxio và kịch bản gắn synthetic=true và source", "service/telemetry_provenance.py"],
        ["Bí mật", "Giá trị token, khóa, chuỗi kết nối đọc từ biến môi trường, không có giá trị mặc định trong mã", "service/mongodb_store.py; main.py"],
    ], caption="Cơ chế bảo mật đã có trong mã", font_size=10)

    H(d, "Số liệu tổng hợp", 1)
    F(d, fig_counts(), "Số liệu đếm được của hệ thống")
    T(d, ["Số liệu", "Giá trị", "Nguồn"], [
        ["Nhà màng", "10", "service/farm_registry.py"],
        ["Kịch bản trong danh mục", "36 (A7, C10, D7, H6, S6)", "service/scenario_catalog.py"],
        ["Ca sự cố trên giao diện", "10 (Ca 1-3, W1, W5-W10)", "Giao diện ứng dụng, 13/11/2026"],
        ["Route giao diện (@ui.page)", "16", "pages/*.py, main.py"],
        ["Route API (@app)", "10", "main.py"],
        ["Module pages/ và service/", "15 và 37", "thống kê thư mục"],
        ["Script trong scripts/", "62 file .py", "thống kê thư mục"],
        ["File kiểm thử", "41 file tests/test_*.py", "tests/"],
        ["Project Velxio", "3", "velxio/"],
        ["Collection MongoDB (tên trong mã)", "25 nghiệp vụ, 26 tên kể cả _counters", "service/, main.py, pages/"],
        ["Nhánh $unionWith của hộp đen", "7", "service/incident_blackbox.py"],
        ["Metric DogStatsD gọi trực tiếp", "19", "service/datadog_metrics.py"],
        ["Monitor Datadog SMIOT", "19 (đọc trực tiếp 13/11)", "Datadog API, 13/11/2026"],
        ["Dashboard SMIOT", "5 (đọc trực tiếp 13/11)", "Datadog API, 13/11/2026"],
        ["Workflow SMIOT", "10, đều ở trạng thái published (đọc trực tiếp 13/11)", "Datadog API, 13/11/2026"],
        ["Định nghĩa monitor dạng mã", "23 (17 + 5 + 1)", "deploy/datadog/terraform_*"],
    ], caption="Số liệu đếm được và nguồn", font_size=10)
    return S.save(d, os.path.join(OUT, "01_kien_truc_giai_phap.docx"))


def build_07():
    d = S.new_document("Khai báo thành phần và công cụ")
    P, B, T, F, H = S.add_paragraph, S.add_bullets, S.add_table, S.add_figure, S.add_heading

    H(d, "Mục đích và phạm vi khai báo", 1)
    P(d, "Tài liệu liệt kê các thành phần phần mềm, dịch vụ bên ngoài, công cụ mô phỏng, hạ tầng và biến môi trường "
         "mà giải pháp sử dụng. Với dịch vụ bên ngoài và biến môi trường, tài liệu chỉ nêu vai trò và tên; không nêu "
         "khóa, token, mật khẩu hay chuỗi kết nối.")
    F(d, fig_layers(), "Sơ đồ phân lớp thành phần và công cụ")

    H(d, "Thành phần phần mềm", 1)
    T(d, ["Thành phần", "Vai trò", "Nguồn"], [
        ["NiceGUI", "Khung giao diện web và máy chủ ứng dụng (main.py, 16 route giao diện, 11 route API)", "main.py; requirements.txt"],
        ["pymongo (>=4.0,<4.18)", "Kết nối MongoDB", "requirements.txt; service/mongodb_store.py"],
        ["ddtrace (>=4.16.1,<5.0)", "APM, span tùy chỉnh, chèn correlation vào log, LLM Observability có điều kiện", "requirements.txt; service/observability.py"],
        ["DogStatsD", "Gửi metric smiot.* (19 tên gọi trực tiếp)", "service/datadog_metrics.py"],
        ["Module pages/", "15 module trang giao diện", "pages/"],
        ["Module service/", "37 module nghiệp vụ: MQTT, telemetry, sự cố, hộp đen, Datadog, AI, xác thực", "service/"],
        ["Module components/", "4 module dùng chung cho giao diện, cùng __init__.py", "components/"],
        ["Mô phỏng thiết bị ảo", "9 nhóm thiết bị ảo mỗi nhà màng, nhúng trong ứng dụng", "PRD.md; ARCHITECTURE.md"],
        ["Kiểm thử", "41 file tests/test_*.py", "tests/"],
        ["Script hỗ trợ", "62 file .py (cầu nối, benchmark, báo cáo, tiện ích triển khai)", "scripts/"],
    ], caption="Thành phần phần mềm", font_size=10)

    H(d, "Dịch vụ bên ngoài", 1)
    T(d, ["Dịch vụ", "Vai trò", "Cách dùng", "Nguồn"], [
        ["MongoDB Community (self-managed)", "Lưu telemetry, hồ sơ sự cố, sổ lệnh, bằng chứng, người dùng", "Truy cập qua pymongo; chuỗi kết nối đọc từ biến môi trường", "service/mongodb_store.py"],
        ["Datadog", "Metric, log, span, monitor, dashboard, workflow, LLM Observability", "Agent trên EC2; API đọc trạng thái; khóa đọc từ biến môi trường", "service/observability.py; service/datadog_reader.py"],
        ["Open-Meteo", "Dữ liệu thời tiết", "Hiển thị kèm nguồn; khi lỗi không hiện số mặc định", "service/weather_api.py"],
        ["Gemini", "Trợ lý AI với công cụ chỉ đọc", "Gọi từ service/ai_service.py; khóa đọc từ biến môi trường", "service/ai_service.py; service/ai_tools.py"],
        ["Telegram", "Bot thông báo và hỏi đáp", "Chạy như dịch vụ riêng", "service/telegram_bot.py"],
        ["MQTT", "Kênh truyền telemetry, trạng thái, ACK lệnh", "Ứng dụng kết nối broker nội bộ, cổng mặc định 1883", "service/mqtt.py"],
        ["AWS EC2", "Máy chủ chạy ứng dụng", "Vùng ap-southeast-2", "ARCHITECTURE.md"],
    ], caption="Dịch vụ bên ngoài", font_size=10)

    H(d, "Công cụ và mô phỏng", 1)
    H(d, "Velxio ESP32", 2)
    T(d, ["Project", "Vai trò", "Nguồn"], [
        ["node1_environment", "Cảm biến môi trường (DHT22)", "velxio/node1_environment"],
        ["node2_virtual_pump", "Bơm ảo, ACK lệnh", "velxio/node2_virtual_pump"],
        ["node3_flow_monitor", "Giám sát lưu lượng", "velxio/node3_flow_monitor"],
    ], caption="Ba project Velxio", font_size=10)
    P(d, "Cầu nối scripts/velxio_mqtt_bridge.py chuyển thông điệp Velxio thành envelope farm/sensor, chỉ chuyển các "
         "lệnh trong danh sách cho phép, gắn synthetic=true và source=velxio_synthetic.")
    H(d, "Danh mục kịch bản cho demo trực tiếp", 2)
    T(d, ["Nhóm", "Mã", "Số kịch bản", "Module"], [
        ["A", "A1-A7", "7", "service/scenario_domain_actuator_infra.py"],
        ["C (cây trồng)", "C1-C10", "10", "service/scenario_domain_crops.py"],
        ["D (thiết bị)", "D1-D7", "7", "service/scenario_domain_sensor_device.py"],
        ["H", "H1-H6", "6", "service/scenario_domain_actuator_infra.py"],
        ["S", "S1-S6", "6", "service/scenario_domain_sensor_device.py"],
    ], caption="Danh mục 36 kịch bản demo (nguồn: service/scenario_catalog.py)", font_size=10)
    P(d, "Danh mục kịch bản chỉ phục vụ demo trực tiếp; phạm vi sự cố được giám sát gồm 10 ca (Ca 1-3, W1, W5-W10).")

    H(d, "Hạ tầng triển khai", 1)
    T(d, ["Hạng mục", "Mô tả", "Nguồn"], [
        ["EC2", "Vùng ap-southeast-2, chạy ứng dụng, broker MQTT nội bộ, MongoDB", "ARCHITECTURE.md"],
        ["Datadog Agent", "Đọc log theo cấu hình deploy/datadog/smiot-logs.yaml (service smiot-smart-farm); nhận DogStatsD và trace", "deploy/datadog/smiot-logs.yaml"],
        ["Terraform", "Định nghĩa monitor, workflow, dashboard dạng mã (terraform_monitors, terraform_scenarios, terraform_w2_greenhouse_j, terraform_farm_control_center)", "deploy/datadog/"],
        ["Khôi phục có guard", "scripts/aws/smiot-recover-guarded.sh và docs/DATADOG_GUARDED_RECOVERY.md", "scripts/aws/"],
    ], caption="Hạ tầng triển khai", font_size=10)

    H(d, "Biến môi trường", 1)
    P(d, "Bảng chỉ nêu tên biến và mục đích. Giá trị được cấu hình tại môi trường chạy và không nằm trong mã hay hồ sơ.")
    T(d, ["Tên biến", "Mục đích", "Nguồn"], [
        ["APP_ENV", "Chế độ chạy; production bật các ràng buộc session", "service/session_security.py"],
        ["NICEGUI_STORAGE_SECRET", "Khóa session của NiceGUI; nếu thiếu, ứng dụng cảnh báo và tự sinh secret ngẫu nhiên", "service/session_security.py"],
        ["MONGODB_DATABASE", "Tên database MongoDB (mặc định smiot)", "service/mongodb_store.py"],
        ["SMIOT_DEMO_MODE", "Điều khiển route xác nhận muộn W9 (không bật/tắt API kịch bản)", "main.py"],
        ["SMIOT_DEMO_CONTROL_TOKEN", "Bearer token riêng của API kịch bản", "main.py"],
        ["DATADOG_APP_NOTIFICATION_TOKEN", "Xác thực endpoint nhận thông báo từ Datadog", "main.py"],
        ["SAFE_MODE_RECOVERY_TOKEN", "Xác thực endpoint xóa safe mode sau khôi phục", "main.py"],
        ["SMIOT_RECOVERY_INSTANCE_ID", "Chỉ định đúng máy chủ cho khôi phục", "main.py"],
        ["AWS_REGION", "Vùng AWS (mặc định ap-southeast-2)", "main.py"],
        ["DATADOG_APM_ENABLED", "Bật APM", "service/observability.py"],
        ["DATADOG_LLMOBS_ENABLED", "Bật LLM Observability", "service/observability.py"],
        ["DD_SERVICE, DD_ENV, DD_VERSION", "Nhãn dịch vụ, môi trường, phiên bản cho Datadog", "service/observability.py"],
        ["DD_TRACE_AGENT_URL", "Địa chỉ Agent nhận trace", "service/observability.py"],
        ["DD_LOGS_INJECTION", "Chèn trace vào log", "service/observability.py"],
        ["DD_DOGSTATSD_PORT", "Cổng DogStatsD (mặc định 8125)", "service/datadog_metrics.py"],
        ["VELXIO_PUBLIC_HOST", "Máy chủ MQTT mà cầu nối Velxio kết nối", "scripts/velxio_mqtt_bridge.py"],
        ["VELXIO_MQTT_USERNAME, VELXIO_MQTT_PASSWORD", "Thông tin xác thực MQTT cho cầu nối (đặt khi cần)", "scripts/velxio_mqtt_bridge.py"],
    ], caption="Biến môi trường theo tên", font_size=10)

    H(d, "Dữ liệu mô phỏng và nhãn nguồn", 1)
    P(d, "Toàn bộ thiết bị và cảm biến trong hồ sơ là mô phỏng. Để phân biệt với dữ liệu thật, mỗi mẫu từ Velxio và từ "
         "kịch bản mang nhãn nguồn (nguồn: service/telemetry_provenance.py; scripts/velxio_mqtt_bridge.py):")
    T(d, ["Trường", "Giá trị", "Ý nghĩa"], [
        ["synthetic", "true", "Mẫu do mô phỏng sinh ra"],
        ["source", "velxio_synthetic", "Mẫu đến từ cầu nối Velxio"],
        ["execution_mode", "SIMULATED_ONLY", "Quan sát kịch bản chạy ở chế độ mô phỏng (collection scenario_observations)"],
    ], caption="Nhãn nguồn của dữ liệu mô phỏng", font_size=10)
    return S.save(d, os.path.join(OUT, "07_khai_bao_thanh_phan_va_cong_cu.docx"))


if __name__ == "__main__":
    print(build_01())
    print(build_07())


