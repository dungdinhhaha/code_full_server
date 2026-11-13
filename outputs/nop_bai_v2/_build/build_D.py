# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import style

B = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(B, "img")
OUT = os.path.dirname(B)
os.makedirs(IMG, exist_ok=True)
plt.rcParams["font.family"] = "DejaVu Sans"


def box(ax, x, y, w, h, text, fc="#E8EEF7", fs=10, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02", fc=fc, ec="#333", lw=1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal")


def arrow(ax, x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", lw=1.5, color="#333"))


# ---------- Hinh: cay thu muc ----------
def fig_tree():
    lines = [
        ("code_full_server/", 0),
        ("main.py  (điểm vào ứng dụng NiceGUI, 11 route API)", 1),
        ("requirements.txt", 1),
        ("pages/  (15 module trang giao diện)", 1),
        ("service/  (37 module nghiệp vụ)", 1),
        ("components/  (4 module + __init__.py)", 1),
        ("scripts/  (62 file .py, cầu nối Velxio, hạ tầng, báo cáo)", 1),
        ("velxio/  (3 project: node1, node2, node3)", 1),
        ("deploy/  (datadog, systemd, mẫu biến môi trường)", 1),
        ("tests/  (41 file test_*.py)", 1),
        ("docs/  (tài liệu)", 1),
        ("outputs/velxio_v2/  (sketch Velxio v2 và hướng dẫn)", 1),
        ("static/  (tài nguyên tĩnh)", 1),
    ]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, len(lines) + 0.5)
    for i, (t, lv) in enumerate(lines):
        y = len(lines) - i
        ax.text(0.2 + lv * 0.6, y, ("├─ " if lv else "") + t, fontsize=10.5,
                family="DejaVu Sans Mono" if False else "DejaVu Sans",
                fontweight="bold" if lv == 0 else "normal")
    fig.savefig(os.path.join(IMG, "d_cay_thu_muc.png"), dpi=150, bbox_inches="tight"); plt.close(fig)


def fig_deploy():
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 5)
    ax.text(0.1, 4.7, "Máy phát triển", fontsize=11, fontweight="bold")
    box(ax, 0.1, 3.2, 2.2, 1.2, "Mã nguồn\n+ requirements.txt", "#EAF3E6")
    box(ax, 0.1, 1.5, 2.2, 1.2, "Kiểm thử\npytest tests/", "#EAF3E6")
    ax.text(3.6, 4.7, "Máy chủ (EC2, Linux)", fontsize=11, fontweight="bold")
    box(ax, 3.6, 3.2, 2.3, 1.2, "Thư mục ứng dụng\n/opt/smiot + venv", "#E8EEF7")
    box(ax, 3.6, 1.5, 2.3, 1.2, "File môi trường\n/etc/smiot/app.env", "#FFF3D6")
    box(ax, 6.3, 3.2, 1.8, 1.2, "smiot.service\n(systemd)", "#E8EEF7")
    box(ax, 6.3, 1.5, 1.8, 1.2, "MQTT broker\ncổng 1883", "#E8EEF7")
    box(ax, 8.4, 3.2, 1.5, 1.2, "MongoDB", "#E8EEF7")
    box(ax, 8.4, 1.5, 1.5, 1.2, "Datadog\nAgent", "#E8EEF7")
    arrow(ax, 2.3, 3.8, 3.6, 3.8)
    arrow(ax, 5.9, 3.8, 6.3, 3.8)
    arrow(ax, 4.75, 2.7, 4.75, 3.2)
    arrow(ax, 8.1, 3.8, 8.4, 3.8)
    arrow(ax, 7.2, 3.2, 7.2, 2.7)
    arrow(ax, 8.1, 2.1, 8.4, 2.1)
    ax.text(0.1, 0.5, "Các bước: sao chép mã -> cài gói -> đặt biến môi trường -> đăng ký dịch vụ systemd -> khởi động -> kiểm tra /healthz",
            fontsize=9.5)
    fig.savefig(os.path.join(IMG, "d_trien_khai.png"), dpi=150, bbox_inches="tight"); plt.close(fig)


def fig_modules():
    names = ["pages/", "service/", "components/", "scripts/", "tests/", "velxio/ (project)"]
    vals = [15, 37, 4, 62, 41, 3]
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(names, vals, color="#5B7DB1")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 1, str(v), ha="center", fontsize=10)
    ax.set_ylabel("Số file / project"); ax.set_title("Số file .py (hoặc project) theo thư mục", fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    plt.xticks(fontsize=9)
    fig.savefig(os.path.join(IMG, "d_so_module.png"), dpi=150, bbox_inches="tight"); plt.close(fig)


def fig_layers():
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 4)
    box(ax, 0.2, 1.2, 2.8, 1.8, "Lớp 1\nKiểm thử tự động\ntests/test_*.py (41 file)", "#EAF3E6")
    box(ax, 3.6, 1.2, 2.8, 1.8, "Lớp 2\nDiễn tập bằng thiết bị ảo\nVelxio + cầu nối MQTT\nhoặc API kịch bản", "#E8EEF7")
    box(ax, 7.0, 1.2, 2.8, 1.8, "Lớp 3\nKiểm tra dữ liệu\nMongoDB (hồ sơ, mẫu)\nDatadog (monitor, log)", "#FFF3D6")
    arrow(ax, 3.0, 2.1, 3.6, 2.1); arrow(ax, 6.4, 2.1, 7.0, 2.1)
    ax.text(5, 0.5, "Ba lớp kiểm thử của dự án", ha="center", fontsize=10.5)
    fig.savefig(os.path.join(IMG, "d_lop_kiem_thu.png"), dpi=150, bbox_inches="tight"); plt.close(fig)


def fig_groups():
    names = ["A", "C", "D", "H", "S"]
    vals = [7, 10, 7, 6, 6]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    bars = ax.bar(names, vals, color="#5B7DB1")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.2, str(v), ha="center")
    ax.set_ylabel("Số kịch bản"); ax.set_xlabel("Nhóm"); ax.set_title("36 kịch bản theo nhóm (service/scenario_catalog.py)", fontsize=10.5)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(os.path.join(IMG, "d_nhom_kich_ban.png"), dpi=150, bbox_inches="tight"); plt.close(fig)


def fig_drill():
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 4)
    steps = ["Broker MQTT\nchạy", "Cầu nối\nvelxio_mqtt_bridge", "Sketch Velxio\nnode1/2/3", "Ứng dụng\nnhận farm/sensor", "MongoDB\n+ Datadog"]
    for i, s in enumerate(steps):
        x = 0.1 + i * 2.0
        box(ax, x, 1.4, 1.7, 1.3, s, "#E8EEF7", fs=9)
        if i < len(steps) - 1:
            arrow(ax, x + 1.7, 2.05, x + 2.0, 2.05)
    ax.text(5, 0.6, "Dữ liệu từ Velxio gắn synthetic=true, source=velxio_synthetic", ha="center", fontsize=10)
    fig.savefig(os.path.join(IMG, "d_dien_tap_velxio.png"), dpi=150, bbox_inches="tight"); plt.close(fig)


fig_tree(); fig_deploy(); fig_modules(); fig_layers(); fig_groups(); fig_drill()

PN = style.PROJECT_NAME

# ======================= FILE 04 =======================
d = style.new_document("Repository và hướng dẫn cài đặt")
H, P, BL, T, F = style.add_heading, style.add_paragraph, style.add_bullets, style.add_table, style.add_figure

H(d, "Cấu trúc repository", 1)
P(d, "Repository của %s gồm ứng dụng NiceGUI, các module nghiệp vụ, kịch bản diễn tập, dự án thiết bị ảo Velxio, cấu hình triển khai và bộ kiểm thử. Dữ liệu và cảm biến trong hệ thống là mô phỏng." % PN)
H(d, "Cây thư mục chính", 2)
F(d, os.path.join(IMG, "d_cay_thu_muc.png"), "Cây thư mục repository (cấp cao)")
H(d, "Vai trò từng thư mục", 2)
T(d, ["Thư mục / file", "Vai trò", "Số lượng", "Nguồn"], [
    ["main.py", "Điểm vào ứng dụng NiceGUI; khai báo route API", "11 route API", "main.py"],
    ["pages/", "Trang giao diện (tổng quan, sự cố, thiết bị, lịch tưới, lịch sử, biểu đồ...)", "15 module", "pages/*.py"],
    ["service/", "Nghiệp vụ: MQTT, MongoDB, sự cố, hộp đen, kịch bản, Datadog, xác thực", "37 module", "service/*.py"],
    ["components/", "Thành phần giao diện dùng chung", "4 module + __init__.py", "components/"],
    ["scripts/", "Cầu nối Velxio, migrate, benchmark, báo cáo, hạ tầng", "62 file .py (đệ quy)", "scripts/"],
    ["velxio/", "Ba project thiết bị ảo ESP32: node1_environment, node2_virtual_pump, node3_flow_monitor", "3 project", "velxio/"],
    ["outputs/velxio_v2/", "Sketch Velxio v2 và hướng dẫn (HUONG_DAN.md)", "3 sketch", "outputs/velxio_v2/"],
    ["deploy/", "Cấu hình Datadog (Terraform, smiot-logs.yaml), systemd, mẫu biến môi trường", "-", "deploy/"],
    ["tests/", "Kiểm thử tự động", "41 file test_*.py", "tests/"],
    ["docs/", "Tài liệu dự án", "-", "docs/"],
    ["requirements.txt", "Danh sách gói Python", "15 dòng", "requirements.txt"],
], caption="Thư mục chính và vai trò")
F(d, os.path.join(IMG, "d_so_module.png"), "Số file theo thư mục")

H(d, "Yêu cầu môi trường", 1)
H(d, "Phần mềm", 2)
T(d, ["Thành phần", "Yêu cầu", "Ghi chú"], [
    ["Python", "Python 3 (khuyến nghị bản đang được hỗ trợ), cài gói theo requirements.txt", "Dùng môi trường ảo (venv)"],
    ["Gói chính", "nicegui, paho-mqtt, pymongo>=4.0,<4.18, ddtrace>=4.16.1,<5.0, boto3>=1.34,<2, pandas, openpyxl, psutil, python-dotenv, requests-cache, retry-requests, openmeteo-requests, qrcode[pil], lzstring", "Nguồn: requirements.txt"],
    ["MongoDB", "MongoDB Community (tự quản lý); ứng dụng kết nối qua biến URI và tên database", "Database mặc định smiot"],
    ["MQTT broker", "Broker MQTT cục bộ, cổng mặc định 1883, kết nối nội bộ", "Ứng dụng kết nối nội bộ"],
    ["Datadog Agent", "Bắt buộc cho metric và log: nhận DogStatsD, ddtrace, đọc log từ file", "Cấu hình log: deploy/datadog/smiot-logs.yaml"],
], caption="Yêu cầu môi trường")

H(d, "Cài đặt môi trường local", 1)
H(d, "Các bước", 2)
BL(d, [
    "Bước 1: Sao chép repository về máy.",
    "Bước 2: Tạo môi trường ảo: python -m venv .venv, sau đó kích hoạt (Windows: .venv\\Scripts\\activate).",
    "Bước 3: Cài gói: pip install -r requirements.txt.",
    "Bước 4: Khởi động MongoDB và MQTT broker cục bộ.",
    "Bước 5: Tạo file .env từ danh sách biến ở mục 4 (đặt giá trị riêng, không chia sẻ file này).",
    "Bước 6: Chạy ứng dụng: python main.py, sau đó mở giao diện qua trình duyệt.",
    "Bước 7: Kiểm tra sức khỏe qua route GET /healthz.",
])
P(d, "Lệnh mẫu với giá trị giữ chỗ:")
BL(d, [
    "MONGODB_DATABASE=<TÊN_DATABASE>",
    "NICEGUI_STORAGE_SECRET=<GIÁ_TRỊ>",
    "APP_ENV=<development|production>",
])

H(d, "Biến môi trường", 1)
P(d, "Chỉ liệt kê tên biến và mục đích. Giá trị được đặt riêng cho từng môi trường và không đưa vào repository.")
T(d, ["Tên biến", "Mục đích", "Nguồn"], [
    ["MONGODB_DATABASE", "Tên database MongoDB (mặc định smiot)", "service/mongodb_store.py"],
    ["APP_ENV", "Chế độ chạy; production yêu cầu khóa session và bật cookie https_only", "service/session_security.py"],
    ["NICEGUI_STORAGE_SECRET", "Khóa session NiceGUI; nếu thiếu, ứng dụng cảnh báo và tự sinh secret ngẫu nhiên", "service/session_security.py"],
    ["SMIOT_DEMO_MODE", "Điều khiển route xác nhận muộn W9", "main.py"],
    ["SMIOT_DEMO_CONTROL_TOKEN", "Bearer token riêng cho API kịch bản", "main.py"],
    ["DATADOG_APP_NOTIFICATION_TOKEN", "Token cho endpoint nhận thông báo từ Datadog", "main.py"],
    ["SAFE_MODE_RECOVERY_TOKEN", "Token cho endpoint xóa safe mode", "main.py"],
    ["SMIOT_RECOVERY_INSTANCE_ID", "Định danh instance cho khôi phục có guard", "main.py"],
    ["AWS_REGION", "Vùng AWS cho khôi phục (mặc định ap-southeast-2)", "main.py"],
    ["DATADOG_APM_ENABLED", "Bật ddtrace / APM", "service/observability.py"],
    ["DATADOG_LLMOBS_ENABLED", "Bật LLM Observability", "service/observability.py"],
    ["DD_SERVICE, DD_ENV, DD_VERSION", "Nhãn dịch vụ cho Datadog", "service/observability.py"],
    ["DD_LOGS_INJECTION", "Gắn trace_id vào log", "service/observability.py"],
    ["DD_TRACE_AGENT_URL", "Địa chỉ Agent nhận trace (mặc định nội bộ)", "service/observability.py"],
    ["DD_DOGSTATSD_PORT", "Cổng DogStatsD (mặc định 8125)", "service/datadog_metrics.py"],
    ["VELXIO_PUBLIC_HOST", "Máy chủ MQTT mà cầu nối Velxio sử dụng", "scripts/velxio_mqtt_bridge.py"],
    ["VELXIO_MQTT_USERNAME, VELXIO_MQTT_PASSWORD", "Thông tin xác thực MQTT cho cầu nối (tùy chọn)", "scripts/velxio_mqtt_bridge.py"],
], caption="Biến môi trường theo tên")
P(d, "Mẫu cấu hình cho cầu nối nằm tại deploy/velxio.env.example. Khóa Datadog, URI MongoDB và khóa dịch vụ AI/Telegram được đặt trong biến môi trường của máy chủ (file môi trường của dịch vụ, ví dụ /etc/smiot/app.env); mã nguồn chỉ đọc tên biến, không có giá trị mặc định và hồ sơ này không nêu giá trị.")

H(d, "Triển khai lên máy chủ", 1)
F(d, os.path.join(IMG, "d_trien_khai.png"), "Sơ đồ triển khai lên máy chủ Linux")
T(d, ["Bước", "Nội dung", "Chi tiết"], [
    ["1", "Chuẩn bị máy chủ", "Máy Linux (EC2, vùng ap-southeast-2); cài Python, MongoDB, MQTT broker, Datadog Agent"],
    ["2", "Đưa mã lên", "Sao chép mã vào /opt/smiot, tạo venv, pip install -r requirements.txt"],
    ["3", "Đặt biến môi trường", "Ghi vào /etc/smiot/app.env (quyền đọc hạn chế); nội dung không đưa vào repository"],
    ["4", "Đăng ký dịch vụ", "Đăng ký ứng dụng thành dịch vụ systemd tên smiot.service trên máy chủ (unit của ứng dụng không nằm trong deploy/systemd/)"],
    ["5", "Khởi động", "systemctl enable --now smiot.service"],
    ["6", "Kiểm tra", "systemctl status smiot.service; GET /healthz; xem trang /incident và /devices"],
], caption="Các bước triển khai")
P(d, "Thư mục deploy/systemd/ có thêm unit cho cầu nối Velxio (velxio-bridge.service) và tác vụ kiểm tra bên ngoài (smiot-external-probe.service, smiot-external-probe.timer).")

H(d, "Cấu hình Datadog", 1)
BL(d, [
    "Datadog Agent nhận metric DogStatsD qua cổng DD_DOGSTATSD_PORT và trace qua DD_TRACE_AGENT_URL.",
    "Log đọc từ file theo deploy/datadog/smiot-logs.yaml (incident_events.jsonl, recovery/*.jsonl, service smiot-smart-farm).",
    "Monitor, dashboard và workflow khai báo bằng Terraform trong deploy/datadog/: terraform_monitors, terraform_farm_control_center, terraform_scenarios, terraform_w2_greenhouse_j.",
    "Khóa API và khóa ứng dụng Datadog đặt qua biến môi trường của Terraform hoặc Agent, không ghi vào file cấu hình.",
])

H(d, "Chạy Velxio và cầu nối", 1)
BL(d, [
    "Mở ba project Velxio: node1_environment (cảm biến môi trường), node2_virtual_pump (bơm ảo, ACK lệnh), node3_flow_monitor (lưu lượng). Phiên bản v2 nằm ở outputs/velxio_v2/ cùng HUONG_DAN.md.",
    "Chạy cầu nối: python scripts/velxio_mqtt_bridge.py. Cầu nối chuyển thông điệp Velxio sang envelope farm/sensor, chỉ chuyển lệnh trong danh sách cho phép, gắn synthetic=true và source=velxio_synthetic.",
    "Triển khai dạng dịch vụ: deploy/systemd/velxio-bridge.service với biến từ deploy/velxio.env.example.",
])

H(d, "Route giao diện và API", 1)
H(d, "Route giao diện (16)", 2)
T(d, ["Route", "Mô tả", "Quyền truy cập"], [
    ["/", "Tổng quan 10 nhà màng", "Đăng nhập"],
    ["/login", "Đăng nhập", "Công khai"],
    ["/incident", "Danh sách sự cố", "Đăng nhập và quyền quản trị (manage_users)"],
    ["/incident/{incident_id}", "Chi tiết sự cố (hộp đen)", "Đăng nhập và quyền quản trị (manage_users)"],
    ["/inverter", "Inverter ảo", "Đăng nhập"],
    ["/plc", "PLC ảo", "Đăng nhập"],
    ["/devices", "Thiết bị", "Đăng nhập"],
    ["/permission", "Phân quyền người dùng", "Đăng nhập và quyền quản trị (manage_users)"],
    ["/schedule", "Lịch tưới", "Đăng nhập"],
    ["/history", "Chuyển hướng sang /chart", "Chuyển hướng cũ"],
    ["/chart", "Biểu đồ", "Đăng nhập"],
    ["/data", "Dữ liệu", "Đăng nhập"],
    ["/projects", "Dự án", "Đăng nhập"],
    ["/mongodb-lab", "Trang minh họa MongoDB", "Đăng nhập"],
    ["/lot/{token}", "Truy xuất lô, chỉ đọc", "Công khai"],
    ["/traceability", "Chuyển hướng sang /mongodb-lab", "Chuyển hướng cũ"],
], caption="Route giao diện (nguồn: main.py, pages/*.py)")
H(d, "Route API (11)", 2)
T(d, ["Phương thức", "Đường dẫn", "Mục đích"], [
    ["POST", "/api/js_error", "Ghi lỗi JavaScript phía trình duyệt"],
    ["GET", "/api/inverter", "Đọc trạng thái inverter ảo (pages/inverter.py)"],
    ["POST", "/api/demo/scenarios", "Tạo lần chạy kịch bản (bearer token, Idempotency-Key)"],
    ["GET", "/api/demo/scenarios/{scenario_run_id}", "Đọc trạng thái lần chạy kịch bản"],
    ["POST", "/api/demo/w9/late-ack", "Gửi ACK muộn cho kịch bản W9"],
    ["GET", "/healthz", "Kiểm tra sức khỏe"],
    ["POST", "/api/integrations/datadog/w2-greenhouse-j/recover", "Khôi phục có guard (workflow Datadog)"],
    ["POST", "/api/integrations/datadog/w2-greenhouse-j/verify", "Xác minh sau khôi phục"],
    ["POST", "/api/integrations/datadog/recovery-verification", "Xác minh phục hồi"],
    ["POST", "/api/internal/safe-mode/recovery-clear", "Xóa safe mode (token riêng)"],
    ["POST", "/api/integrations/datadog/notification", "Nhận thông báo từ Datadog (token riêng)"],
], caption="Route API (nguồn: main.py)")
H(d, "Chạy mười ca sự cố", 1)
P(d, "Sau khi ứng dụng, MQTT broker và cầu nối chạy, mười ca sự cố (Ca 1, Ca 2, Ca 3, W1, W5, W6, W7, W8, W9, W10) được chọn trong cấu hình ca của ứng dụng. Kịch bản (A1-A4, C10, S2, S3, C2) khác với ca và chỉ dùng cho demo trực tiếp. Sketch Velxio v2 trong outputs/velxio_v2 cung cấp dữ liệu cho node 1, node 2 và node 3. Bảng kích hoạt từng ca nằm trong tài liệu 05.")
style.save(d, os.path.join(OUT, "04_repository_va_huong_dan_cai_dat.docx"))

# ======================= FILE 05 =======================
d = style.new_document("README và yêu cầu kiểm thử")
H(d, "Giới thiệu", 1)
P(d, "%s theo dõi 10 nhà màng dưa lưới ảo (greenhouse_a đến greenhouse_j) theo ba pha Phát hiện, Điều tra và Phản ứng. Ứng dụng NiceGUI nhận dữ liệu qua MQTT, lưu bằng chứng vào MongoDB, gửi tín hiệu tới Datadog và thực hiện khôi phục có guard. Thiết bị và cảm biến là mô phỏng; dữ liệu từ Velxio gắn synthetic=true." % PN)
H(d, "Yêu cầu môi trường", 1)
T(d, ["Thành phần", "Yêu cầu"], [
    ["Python", "Python 3, cài gói theo requirements.txt trong môi trường ảo"],
    ["MongoDB", "Community tự quản lý; database mặc định smiot"],
    ["MQTT broker", "Broker cục bộ, cổng mặc định 1883"],
    ["Datadog Agent", "Bắt buộc cho metric và log; cần để kiểm tra monitor, log, dashboard"],
    ["Velxio", "Ba project trong velxio/ hoặc bản v2 trong outputs/velxio_v2/"],
], caption="Yêu cầu môi trường để chạy và kiểm thử")
P(d, "Chi tiết cài đặt và danh sách biến môi trường theo tên nằm trong tài liệu 04.")

H(d, "Cách chạy ứng dụng", 1)
BL(d, [
    "Kích hoạt môi trường ảo và cài gói: pip install -r requirements.txt.",
    "Khởi động MongoDB và MQTT broker, đặt biến môi trường (tên trong tài liệu 04).",
    "Chạy: python main.py, mở giao diện bằng trình duyệt, đăng nhập.",
    "Kiểm tra GET /healthz và trang tổng quan hiển thị 10 nhà màng.",
])

H(d, "Yêu cầu chức năng", 1)
T(d, ["Mã", "Yêu cầu", "Nơi thể hiện"], [
    ["FR-1", "Giám sát 10 nhà màng ảo: nhiệt độ, độ ẩm, đất, lưu lượng, áp suất", "/, service/mqtt.py"],
    ["FR-2", "Phát hiện bất thường do monitor Datadog đánh giá trên metric smiot.*; ứng dụng phát metric và giữ finding cục bộ (watchdog, sequence, heartbeat) làm bằng chứng", "service/datadog_metrics.py, telemetry_findings.py, detector_heartbeat.py"],
    ["FR-3", "Hồ sơ sự cố và hộp đen có dòng thời gian", "/incident/{id}, service/incident_blackbox.py"],
    ["FR-4", "Lệnh thiết bị có ACK và sổ hành động; lệnh do workflow có guard của Datadog gọi endpoint của ứng dụng, ứng dụng vẫn giữ khóa an toàn cục bộ và kiểm tra guard", "service/mqtt.py, collection action_ledger"],
    ["FR-5", "Phản ứng là workflow có guard của Datadog gọi endpoint của ứng dụng để thực hiện lệnh hoặc khôi phục; xác minh phục hồi khi monitor trở về OK, ghi lại ở MongoDB; ứng dụng vẫn giữ khóa an toàn cục bộ và kiểm tra guard", "service/w3_recovery_verification.py, route /api/integrations/datadog/*"],
    ["FR-6", "Tích hợp Datadog: metric, trace, log, monitor, workflow", "service/observability.py, datadog_metrics.py"],
    ["FR-7", "Kịch bản demo trực tiếp (36 mã) qua API", "service/scenario_catalog.py, /api/demo/scenarios"],
    ["FR-8", "Phân quyền, lịch tưới, truy xuất lô", "service/auth.py, /lot/{token}"],
], caption="Yêu cầu chức năng")
H(d, "Phạm vi", 2)
BL(d, [
    "Không điều khiển bơm, van, quạt phần cứng thật.",
    "Không tự khởi động lại máy chủ.",
    "Không cam kết kết quả năng suất cây trồng.",
])

H(d, "Yêu cầu phi chức năng và bảo mật", 1)
T(d, ["Cơ chế", "Chi tiết", "Nguồn"], [
    ["Băm mật khẩu", "PBKDF2-HMAC-SHA256, 310.000 vòng, salt 16 byte", "service/auth.py"],
    ["Khóa đăng nhập tạm", "5 lần sai trong một cửa sổ thời gian", "service/auth.py"],
    ["Phân quyền", "14 quyền cố định, vai trò admin/operator/viewer, phạm vi theo nhà màng", "service/auth.py"],
    ["Trang sự cố", "Đăng nhập và quyền quản trị (manage_users)", "pages/incident.py"],
    ["Khóa session", "Bắt buộc ở production; cookie https_only", "service/session_security.py"],
    ["Token API kịch bản", "Bearer token riêng (SMIOT_DEMO_CONTROL_TOKEN); SMIOT_DEMO_MODE chỉ điều khiển route xác nhận muộn W9", "main.py"],
    ["Idempotency", "Idempotency-Key bắt buộc, lưu băm trong MongoDB", "main.py"],
    ["Giới hạn tốc độ", "20 ghi, 120 đọc mỗi token trong 60 giây", "main.py"],
    ["Khóa theo nhà màng", "Một kịch bản đồng thời mỗi nhà màng", "main.py"],
    ["Nhãn nguồn", "Mẫu Velxio và kịch bản gắn synthetic=true", "service/telemetry_provenance.py"],
], caption="Cơ chế bảo mật và an toàn")

H(d, "Kế hoạch và các bước kiểm thử", 1)
F(d, os.path.join(IMG, "d_lop_kiem_thu.png"), "Ba lớp kiểm thử")
H(d, "Kiểm thử tự động", 2)
P(d, "Thư mục tests/ có 41 file test_*.py (nguồn: tests/test_*.py). Chạy toàn bộ từ thư mục gốc repository:")
BL(d, [
    "pip install pytest (nếu môi trường chưa có).",
    "python -m pytest tests -q",
    "Chạy một file: python -m pytest tests/<tên_file>.py -q",
])
H(d, "Kiểm thử theo 10 ca sự cố", 2)
P(d, "Đối tượng kiểm thử sự cố là 10 ca hiển thị trên giao diện ứng dụng, trình bày ở bảng dưới. Ca khác với kịch bản: kịch bản chỉ dùng cho demo trực tiếp (mục sau).")
T(d, ["Ca", "Tình huống", "Cách kích hoạt", "Quan sát khi kiểm thử"], [
    ["Ca 1", "Báo offline sai", "Chọn Ca 1 trong cấu hình ca của ứng dụng; điều kiện kích hoạt theo cấu hình kịch bản và ca trong mã nguồn (service/scenario_catalog.py)", "Trạng thái UI khác với mẫu đang vào MongoDB; monitor telemetry status mismatch; hồ sơ sự cố"],
    ["Ca 2", "Node 2 đứng số đo", "Chọn Ca 2 trong cấu hình ca của ứng dụng; điều kiện kích hoạt theo cấu hình kịch bản và ca trong mã nguồn (service/scenario_catalog.py)", "Monitor sensor flatline; hồ sơ sự cố và bằng chứng telemetry"],
    ["Ca 3", "smiot.service dừng", "Chọn Ca 3 trong cấu hình ca của ứng dụng; điều kiện kích hoạt theo cấu hình kịch bản và ca trong mã nguồn (service/scenario_catalog.py)", "Monitor smiot.service inactive; khôi phục có guard; xác minh health, MongoDB, MQTT"],
    ["W1", "PLC safety trip", "Cấu hình ca trong ứng dụng; sketch node2_virtual_pump và node3_flow_monitor qua cầu nối", "Monitor W1; hồ sơ sự cố; ACK từ node 2"],
    ["W5", "MongoDB/MQTT suy giảm", "Chọn W5 trong cấu hình ca của ứng dụng; điều kiện kích hoạt theo cấu hình kịch bản và ca trong mã nguồn (service/scenario_catalog.py)", "Workflow W5 phân loại phụ thuộc; metric dependency"],
    ["W6", "Detector mất heartbeat", "Chọn W6 trong cấu hình ca của ứng dụng; điều kiện kích hoạt theo cấu hình kịch bản và ca trong mã nguồn (service/scenario_catalog.py)", "Monitor W6; workflow W6"],
    ["W7", "Rủi ro độ ẩm đất", "Cấu hình ca trong ứng dụng; sketch node1_environment qua cầu nối", "Monitor W7; workflow W7; advisory"],
    ["W8", "Rủi ro VPD/EC", "Cấu hình ca trong ứng dụng; sketch node1_environment qua cầu nối", "Monitor W8; workflow W8; advisory"],
    ["W9", "Actuator không ACK", "Cấu hình ca trong ứng dụng; node2_virtual_pump nhận lệnh nhưng không phản hồi", "Monitor W9; sổ hành động action_ledger"],
    ["W10", "AI provider lỗi", "Chọn W10 trong cấu hình ca của ứng dụng; điều kiện kích hoạt theo cấu hình kịch bản và ca trong mã nguồn (service/scenario_catalog.py)", "Workflow W10 xác minh an toàn khi AI lỗi"],
], caption="Mười ca sự cố và cách kích hoạt")
P(d, "Thứ tự thực hiện mỗi ca: (1) khởi động broker, ứng dụng và cầu nối; (2) nạp sketch Velxio v2; (3) chọn và bắt đầu ca trong cấu hình ca của ứng dụng; (4) quan sát /incident, MongoDB và Datadog theo cột quan sát; (5) kết thúc ca và dọn dẹp. Số đo được trình bày trong tài liệu 06.")
H(d, "Kịch bản demo trực tiếp", 2)
P(d, "Catalog có 36 kịch bản chia thành năm nhóm (service/scenario_catalog.py). Kịch bản dùng để demo trực tiếp qua API; các mã đã dùng: A1, A2, A3, A4, C10, S2, S3, C2.")
F(d, os.path.join(IMG, "d_nhom_kich_ban.png"), "Số kịch bản theo nhóm")
BL(d, [
    "Đặt SMIOT_DEMO_CONTROL_TOKEN (giá trị riêng) trong môi trường ứng dụng.",
    "Gửi POST /api/demo/scenarios kèm header Authorization (bearer) và Idempotency-Key; nhận scenario_run_id.",
    "Theo dõi GET /api/demo/scenarios/{scenario_run_id} đến khi hoàn tất.",
    "Mỗi nhà màng chỉ chạy một kịch bản tại một thời điểm; vượt giới hạn tốc độ trả lỗi.",
])
H(d, "Diễn tập bằng thiết bị ảo (Velxio và cầu nối MQTT)", 2)
F(d, os.path.join(IMG, "d_dien_tap_velxio.png"), "Luồng diễn tập bằng thiết bị ảo")
T(d, ["Bước", "Hành động", "Kết quả mong đợi"], [
    ["1", "Khởi động MQTT broker và ứng dụng", "GET /healthz trả về bình thường"],
    ["2", "Nạp sketch từ outputs/velxio_v2 (node1_environment, node2_virtual_pump, node3_flow_monitor) vào Velxio; xem HUONG_DAN.md", "Ba thiết bị ảo chạy"],
    ["3", "Chạy python scripts/velxio_mqtt_bridge.py", "Thông điệp chuyển thành envelope farm/sensor, gắn synthetic=true"],
    ["4", "Kích hoạt kịch bản (API hoặc lệnh demo)", "Node 2 gửi ACK; lệnh đi qua danh sách cho phép"],
    ["5", "Quan sát /devices và /incident", "Mẫu và hồ sơ sự cố xuất hiện"],
    ["6", "Dọn dẹp: gửi CLEAR safe mode, tắt đầu ra bơm ảo", "Hệ thống trở về trạng thái bình thường"],
], caption="Các bước diễn tập bằng thiết bị ảo")

H(d, "Kiểm tra MongoDB và Datadog", 1)
H(d, "Kiểm tra MongoDB", 2)
T(d, ["Nội dung", "Cách kiểm tra", "Collection"], [
    ["Mẫu cảm biến", "Đếm/lọc theo meta.farm_key và timestamp", "telemetry"],
    ["Hồ sơ sự cố", "Lọc theo incident_id, status", "operational_incidents"],
    ["Bằng chứng", "Lọc theo incident_id", "incident_telemetry_evidence, findings"],
    ["Hành động và ACK", "Lọc theo incident_id, trạng thái", "action_ledger"],
    ["Lần chạy kịch bản", "Lọc theo scenario_run_id", "scenario_runs, scenario_run_events, scenario_observations"],
    ["Chỉ mục", "Liệt kê index của collection", "operational_incidents, telemetry"],
], caption="Kiểm tra dữ liệu MongoDB")
H(d, "Kiểm tra Datadog", 2)
BL(d, [
    "Dashboard: SMIOT | 10-Farm Portfolio, Farm Data Quality, IoT & MQTT Fleet, Incident & Recovery, App, EC2, MongoDB & AI.",
    "Monitor: danh sách theo tên SMIOT (ví dụ sensor flatline, telemetry status mismatch, smiot.service inactive, W1, W9); xem trạng thái và lịch sử.",
    "Workflow: 10 workflow SMIOT ở trạng thái published; xem lượt chạy sau mỗi diễn tập.",
    "Log và trace: lọc theo incident_id hoặc service smiot-smart-farm.",
])

H(d, "Tiêu chí chấp nhận ba ca trình diễn", 1)
T(d, ["Ca", "Tình huống", "Tiêu chí chấp nhận"], [
    ["Ca 1", "Trạng thái UI báo offline trong khi mẫu vẫn vào MongoDB", "Monitor telemetry status mismatch phát hiện; workflow từ chối khởi động lại khi mẫu còn mới; hồ sơ sự cố ghi nhận"],
    ["Ca 2", "Độ ẩm đất Node 2 đứng yên", "Monitor sensor flatline phát hiện; workflow xác nhận interlock cục bộ; hồ sơ sự cố và bằng chứng telemetry"],
    ["Ca 3", "smiot.service dừng", "Monitor smiot.service inactive phát hiện; khôi phục có guard; xác minh bằng health, MongoDB, MQTT và mẫu mới"],
], caption="Tiêu chí chấp nhận")

H(d, "Kết quả diễn tập", 1)
P(d, "Số liệu diễn tập (một lần chạy mỗi mã, không phải ngưỡng đã duyệt) được trình bày trong tài liệu 06. Tài liệu này chỉ mô tả cách tái lập.")
style.save(d, os.path.join(OUT, "05_readme_yeu_cau_kiem_thu.docx"))
print("done")


