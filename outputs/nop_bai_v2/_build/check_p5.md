# Kiểm chứng hồ sơ nộp bài (check_p5)

Phạm vi: hồ sơ 01, 04, 05, 07 (đoạn và bảng) đối chiếu với mã nguồn, README, requirements.txt, deploy/velxio.env.example, ARCHITECTURE.md, PRD.md, PROGRESS.md (phần mới nhất). Chỉ đọc; không gọi mạng, không gọi Datadog, không ghi DB. Không ghi giá trị biến môi trường, token, khóa, mật khẩu hay chuỗi kết nối; chỉ nêu tên biến.

Ký hiệu: "khớp" = hồ sơ đúng với mã/tài liệu; "sai" = hồ sơ nói khác hoặc thiếu so với repo; "không kiểm được" = cần dữ liệu live (Datadog, EC2, MongoDB runtime) hoặc chưa đếm được từ mã tĩnh.

| Khẳng định (file, mục) | Mã đối chiếu (file:dòng) | Kết quả | Gợi ý sửa |
|---|---|---|---|
| 04 §1.2: main.py có 10 route API | main.py:128, 253, 440, 489, 613, 625, 698, 801, 960, 1010 | khớp | Không cần sửa |
| 04 §1.2: pages/ có 15 module | pages/*.py: 15 module và __init__.py | khớp | Không cần sửa |
| 04 §1.2: service/ có 37 module | service/*.py: 37 file | khớp | Không cần sửa |
| 04 §1.2: components/ có 4 module và __init__.py | components/: cards, layout, theme, ui_kit, __init__ | khớp | Không cần sửa |
| 04 §1.2: scripts/ có 62 file .py (đệ quy) | scripts/ đệ quy: 62 file | khớp | Không cần sửa |
| 04 §1.2: tests/ có 41 file test_*.py | tests/test_*.py: 41 file | khớp | Không cần sửa |
| 04 §1.2: velxio/ có 3 project; outputs/velxio_v2 có 3 sketch và HUONG_DAN.md | velxio/node1..3; outputs/velxio_v2/ | khớp | Không cần sửa |
| 04 §1.1-1.2: bảng thư mục chính | Repo còn có infra/, wokwi/, static/, logs/, reports/, scratch/ không có trong bảng | sai (thiếu mục, không mâu thuẫn) | Thêm dòng cho infra/ và wokwi/ hoặc ghi "các thư mục khác không liệt kê" |
| 04 §2.1: requirements.txt có 15 dòng; pymongo, ddtrace, boto3 đúng ràng buộc | requirements.txt:1-15 | khớp | Có thể thêm python-docx vào bảng gói (có trong requirements.txt) |
| 04 §2.1: "Python 3 (khuyến nghị bản đang được hỗ trợ)" | Không có file pin phiên bản; README.md:165 ghi py -3.12 | sai (thiếu) | Ghi rõ phiên bản đã kiểm thử: Python 3.12 (theo README) |
| 04 §3.1 bước 1-3: tạo venv, pip install -r requirements.txt | requirements.txt | khớp | Không cần sửa |
| 04 §3.1 bước 6: python main.py rồi mở trình duyệt | main.py:1210-1221 (ui.run, port=8080) | khớp | Ghi thêm cổng 8080 |
| 04 §3.1 bước 7: GET /healthz | main.py:613 | khớp | Không cần sửa |
| 04 §3.1 bước 5: tạo .env từ danh sách biến mục 4 | Repo không có file .env.example (.gitignore có !.env.example nhưng không có file) | sai (thiếu) | Thêm .env.example chỉ có tên biến, không giá trị, rồi nêu trong hồ sơ |
| 04 §4 bảng 3 và 07 §6: các tên đã nêu (MONGODB_DATABASE, APP_ENV, NICEGUI_STORAGE_SECRET, SMIOT_DEMO_MODE, SMIOT_DEMO_CONTROL_TOKEN, DATADOG_APP_NOTIFICATION_TOKEN, SAFE_MODE_RECOVERY_TOKEN, SMIOT_RECOVERY_INSTANCE_ID, AWS_REGION, DATADOG_APM_ENABLED, DATADOG_LLMOBS_ENABLED, DD_*, VELXIO_PUBLIC_HOST, VELXIO_MQTT_USERNAME/PASSWORD) | main.py (getenv); service/observability.py; service/datadog_metrics.py; service/session_security.py; service/mongodb_store.py; scripts/velxio_mqtt_bridge.py:59-60 | khớp (tên tồn tại và đúng nguồn) | Không cần sửa |
| 04 §4 và 07 §6: danh sách đủ tên biến của ứng dụng | MONGODB_URI: service/mongodb_store.py:22 và service/mongodb_telemetry.py:34; DD_API_KEY, DD_APP_KEY, DATADOG_API_KEY, DATADOG_APP_KEY: service/datadog_reader.py:42-43; GEMINI_API_KEY, GOOGLE_API_KEY, AI_ENABLED: service/ai_service.py:32-33; TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, MQTT_BROKER, MQTT_PORT: service/telegram_bot.py:26-29; SMIOT_BOOTSTRAP_ADMIN_PASSWORD, SMIOT_APPLY_VALIDATORS: service/auth.py:103, 118; DD_AGENT_HOST, DATADOG_METRICS_ENABLED: service/datadog_metrics.py:24, 39; MONGODB_LIVE_INGEST_ENABLED, MONGODB_TELEMETRY_COLLECTION: service/mongodb_telemetry.py:27, 50; DD_SITE, DD_LLMOBS_ML_APP: service/observability.py:53, 56; SMIOT_PUBLIC_BASE_URL, TRACEABILITY_IMAGE_BUCKET: service/traceability.py:29, 74; SMIOT_DETECTOR_*: service/detector_heartbeat.py:100, 108; SMIOT_SIM_*, SMIOT_VIRTUAL_PLC_*, SMIOT_W2_DEMO_MODE: service/demo_mode.py:48-82, 66 | sai (thiếu) | Bổ sung các tên trên, chỉ nêu tên và mục đích; nhóm SMIOT_SIM_* và SMIOT_VIRTUAL_PLC_* có thể gom thành một dòng |
| 04 §4 và 07 §4.1, §6: deploy/velxio.env.example và biến của cầu nối | deploy/velxio.env.example: VELXIO_FARM_KEY, VELXIO_CHANNEL, VELXIO_PUBLIC_HOST, VELXIO_PUBLIC_PORT, VELXIO_LOCAL_HOST, VELXIO_LOCAL_PORT; scripts/velxio_mqtt_bridge.py:53-60 | sai (thiếu) | Bổ sung VELXIO_FARM_KEY, VELXIO_CHANNEL, VELXIO_PUBLIC_PORT, VELXIO_LOCAL_HOST, VELXIO_LOCAL_PORT (04 §4 chỉ có VELXIO_PUBLIC_HOST) |
| 04 §4: khóa Datadog, URI MongoDB, khóa AI/Telegram đặt trong /etc/smiot/app.env | infra/telemetry/apply_telemetry.py:25 dùng /etc/smiot/app.env | khớp (đường dẫn) | Không cần sửa |
| 04 §5 bước 4: unit systemd smiot.service nằm trong deploy/systemd/ | deploy/systemd/ chỉ có smiot-external-probe.service, smiot-external-probe.timer, velxio-bridge.service; smiot-telegram.service nằm ở gốc repo; không có smiot.service | sai | Thêm unit smiot.service vào deploy/systemd/ hoặc ghi rõ unit chỉ có trên EC2, ngoài repo |
| 04 §5: deploy/systemd có velxio-bridge.service và smiot-external-probe.service/.timer | deploy/systemd/ | khớp | Không cần sửa |
| 04 §6: thư mục Terraform và smiot-logs.yaml (service smiot-smart-farm) | deploy/datadog/terraform_monitors, terraform_farm_control_center, terraform_scenarios, terraform_w2_greenhouse_j; deploy/datadog/smiot-logs.yaml:3-10 | khớp | Không cần sửa |
| 04 §7, 07 §4.1, §7: cầu nối chỉ chuyển lệnh trong allowlist, gắn synthetic=true và source=velxio_synthetic | scripts/velxio_mqtt_bridge.py:27, 29, 108 | khớp | Không cần sửa |
| 04 §8.1: 16 route giao diện và đường dẫn | pages/*.py: 16 @ui.page (chart 2, incident 2, còn lại 1 mỗi file) | khớp | Không cần sửa |
| 04 §8.1 và 01 §6, 05 §5, 07: /incident và /incident/{id} chỉ Admin | pages/incident.py:147-150: cho phép role admin HOẶC quyền manage_users | sai (nhỏ) | Ghi "admin hoặc người có quyền Quản lý User" |
| 04 §8.1: /login và /lot/{token} công khai | pages/login.py:63; pages/public_lot.py:73 | không kiểm được | Đối chiếu thêm nội dung public_lot.py |
| 04 §8.2: 10 route API và phương thức, đường dẫn | main.py:128-1010 (liệt kê đủ 10 route) | khớp | Không cần sửa |
| 04 §9: bảng kích hoạt từng ca nằm trong 05 | 05 mục 6.2 (bảng 4) | khớp | Không cần sửa |
| 01 §2.2: hộp đen gộp 7 nhánh $unionWith | service/incident_blackbox.py:345, 359, 373, 391, 412, 427, 472 | khớp | Không cần sửa |
| 01 §2.3: lệnh MQTT có ACK, ghi action_ledger trong service/mqtt.py | service/mqtt.py (2 vị trí có action_ledger) | khớp | Không cần sửa |
| 01 §2.3, 05, 07 §5: khôi phục có guard chỉ systemctl start smiot.service, có khóa và thời gian chờ | scripts/aws/smiot-recover-guarded.sh:8, 99-100 (flock), 115 (systemctl start), 54, 126, 144 (sleep); docs/DATADOG_GUARDED_RECOVERY.md có tồn tại | khớp | Không cần sửa |
| 01 §3.1: kênh MQTT farm/sensor, farm/status, farm/command/ack, farm/demo/* | service/mqtt.py | khớp | Không cần sửa |
| 01 §3.1, 07 §2: 9 nhóm thiết bị ảo mỗi nhà màng | Không đếm được từ mã tĩnh (PRD.md, ARCHITECTURE.md chỉ nêu) | không kiểm được | Ghi nguồn đếm (file định nghĩa nhóm) |
| 01 §3.3: ARCHITECTURE.md (Deployment model) nêu systemd smiot.service và /opt/smiot | ARCHITECTURE.md:27-28 chỉ nêu EC2 ap-southeast-2; không có systemd hay /opt/smiot | sai (nguồn không có nội dung) | Bổ sung vào ARCHITECTURE.md hoặc đổi nguồn trích dẫn sang tài liệu khác |
| 01 §3.3: khôi phục kiểm đúng máy chủ qua SMIOT_RECOVERY_INSTANCE_ID và AWS_REGION | main.py:836, 847 (AWS_REGION mặc định ap-southeast-2) | khớp | Không cần sửa |
| 01 §5, 05 §7.2: monitor SMIOT (19), ID monitor và workflow trong Bảng 2 | deploy/datadog/terraform_monitors/terraform.tfstate chứa 8/10 ID monitor trong danh sách; 2 ID không thấy trong repo; trạng thái live không đọc được | không kiểm được | Ghi nguồn và ngày đọc Datadog; không suy từ repo |
| 01 §5 Bảng 3: số lần diễn tập và phục hồi | Dữ liệu runtime, không có trong mã | không kiểm được | Giữ ghi chú "số đếm do ứng dụng ghi nhận" và nguồn ảnh chụp |
| 01 §7: 19 metric DogStatsD gọi trực tiếp | service/datadog_metrics.py: 19 tên smiot.* (không tính tiền tố smiot.telemetry.) | khớp | Không cần sửa |
| 01 §7: 5 dashboard SMIOT | deploy/datadog/terraform_farm_control_center/dashboards/*.json: 5 file | khớp | Không cần sửa |
| 01 §7: 23 định nghĩa monitor dạng mã (17+5+1) | deploy/datadog/terraform_*/*.tf: 8 khối resource "datadog_monitor"; còn for_each (monitors.tf:153) và count (terraform.tf:81-209) | không kiểm được | Ghi cách đếm (locals hoặc terraform plan), không chạy plan trong kiểm chứng này |
| 01 §7: 10 workflow SMIOT ở trạng thái published | Không đếm được trong repo (1 khối datadog_workflow_automation) | không kiểm được | Ghi nguồn đọc Datadog API và ngày |
| 01 §7, 04 §1: 25 collection nghiệp vụ (26 tên kể cả _counters) | Grep collection("...") ra 18 tên; chưa đếm đủ db.x và db["..."] | không kiểm được | Ghi cách đếm; đối chiếu lại bằng script |
| 01 §6: băm mật khẩu PBKDF2-HMAC-SHA256, 310.000 vòng, salt 16 byte, so sánh hmac.compare_digest | service/auth.py:35, 40-41, 51, 55 | khớp | Không cần sửa |
| 01 §6, 05 §5: khóa đăng nhập tạm sau 5 lần sai | service/auth.py:214-215 (5 lần, cửa sổ 900 giây), 224-242 (lưu trong bộ nhớ tiến trình) | khớp | Ghi cửa sổ 15 phút và việc khóa lưu trong bộ nhớ, mất khi khởi động lại |
| 01 §6, 05 §5: phân quyền 14 quyền cố định, vai trò admin/operator/viewer, phạm vi theo nhà màng | service/auth.py:17-32 (14 mục trong FIXED_PERMISSIONS; FARM_PRESETS) | khớp | Không cần sửa |
| 01 §6, 05 §5: chỉ admin thao tác tài khoản admin | service/auth.py:191-199 (check_user_change) | khớp | Không cần sửa |
| 01 §6 (không nêu), 05 §5: đường lùi hash SHA-256 cũ không muối | service/auth.py:54-55 (chấp nhận), 167-171 (tự nâng cấp khi đăng nhập đúng), 126-129 (đếm hash cũ) | sai (thiếu) | Nêu rõ: hash cũ còn được chấp nhận và tự nâng cấp; báo cáo số hash cũ |
| 01 §6, 04 §4, 05 §5, 07 §6: NICEGUI_STORAGE_SECRET bắt buộc khi APP_ENV=production | service/session_security.py:13-28: thiếu secret thì sinh secret ngẫu nhiên cho tiến trình, chỉ ghi cảnh báo, không dừng; main.py:1211-1212 | sai | Sửa thành: khuyến nghị đặt; khi thiếu, app dùng secret ngẫu nhiên và phiên đăng nhập mất khi khởi động lại |
| 01 §6, 05 §5: cookie https_only ở production | service/session_security.py:31-33; main.py:1214 | khớp | Không cần sửa |
| 01 §6, 05 §5: API kịch bản chỉ bật khi SMIOT_DEMO_MODE=true, bearer token riêng | main.py:499 (mặc định false), 193-196 (secrets.compare_digest) | khớp | Không cần sửa |
| 01 §6, 05 §5: Idempotency-Key bắt buộc, tối đa 200 ký tự; băm token và key trong MongoDB | main.py:277, 281, 290 | khớp | Không cần sửa |
| 01 §6, 05 §5: giới hạn 20 ghi và 120 đọc mỗi token trong 60 giây | main.py:204-222 (cửa sổ 60.000 ms, Mongo), 284 (20), 452 (120) | khớp | Không cần sửa |
| 01 §6, 05 §5: mỗi nhà màng chạy một kịch bản tại một thời điểm | main.py:379-427 (scenario_api_farm_locks) | khớp | Không cần sửa |
| 01 §6: token tích hợp DATADOG_APP_NOTIFICATION_TOKEN, SAFE_MODE_RECOVERY_TOKEN | main.py:628, 701, 811, 963, 1017 | khớp | Không cần sửa |
| 01 §6, 07 §6: bí mật không có giá trị mặc định trong mã | service/mongodb_store.py:22-24 (raise nếu thiếu URI); main.py: token đọc với mặc định rỗng; service/auth.py:118-120 (bắt buộc SMIOT_BOOTSTRAP_ADMIN_PASSWORD khi chưa có user) | khớp | Không cần sửa |
| 01 §6: nhãn nguồn synthetic=true và source cho mẫu Velxio và kịch bản | service/telemetry_provenance.py:9-11, 83-90 | khớp | Không cần sửa |
| 01 §6 / 07 §3: Open-Meteo, khi lỗi không hiện số mặc định | service/weather_api.py:89-93 (trả status error, không có số) | khớp (mức hàm; hiển thị chưa kiểm) | Không cần sửa |
| 07 §3: Gemini là công cụ chỉ đọc; khóa đọc từ biến môi trường | service/ai_service.py:32 (GEMINI_API_KEY hoặc GOOGLE_API_KEY); service/ai_tools.py: không thấy mẫu ghi (insert, update, delete, publish, send) | khớp (tìm mẫu, chưa đọc hết ai_tools.py) | Đọc toàn bộ ai_tools.py trước khi nộp |
| 07 §3: Telegram là bot thông báo và hỏi đáp; chạy như dịch vụ riêng | service/telegram_bot.py:4, 26-29 (nhận farm/notify, gửi Telegram); smiot-telegram.service ở gốc repo | không kiểm được (tính năng hỏi đáp chưa thấy rõ) | Ghi rõ tính năng hỏi đáp nếu có; ghi vị trí unit |
| 07 §3: Datadog API đọc monitor, workflow, dashboard; khóa đọc từ biến môi trường | service/datadog_reader.py:41-43 | khớp (tên biến chưa có trong 07 §6, xem dòng trên) | Bổ sung tên biến vào 07 §6 |
| 07 §3: AWS EC2 vùng ap-southeast-2 | main.py:847; ARCHITECTURE.md:28 | khớp | Không cần sửa |
| 07 §3: MQTT cổng mặc định 1883 | service/mqtt.py (MQTT_PORT = 1883) | khớp | Không cần sửa |
| 07 §4.2: 36 kịch bản, nhóm A7, C10, D7, H6, S6 | service/scenario_catalog.py: grep chưa đếm đủ | không kiểm được | Đếm lại bằng script trên scenario_catalog.py |
| 07 §5: systemd smiot.service và /opt/smiot (nguồn ARCHITECTURE.md) | ARCHITECTURE.md không có nội dung này; unit smiot.service không có trong repo | sai | Xem dòng 04 §5 và 01 §3.3 |
| 07 §5: khôi phục có guard: scripts/aws/smiot-recover-guarded.sh và docs/DATADOG_GUARDED_RECOVERY.md | scripts/aws/smiot-recover-guarded.sh; docs/DATADOG_GUARDED_RECOVERY.md | khớp | Không cần sửa |
| 07 §7: synthetic=true, source=velxio_synthetic, execution_mode=SIMULATED_ONLY | service/demo_mode.py:206, 1263; service/incident_blackbox.py:195; scripts/velxio_mqtt_bridge.py:27 | khớp | Không cần sửa |
| 05 §2-3: Python 3, requirements, chạy python main.py, GET /healthz | requirements.txt; main.py:613 | khớp | Thêm phiên bản Python 3.12 (theo README.md:165) |
| 05 §6.1: python -m pytest tests -q; hồ sơ ghi pip install pytest khi cần | tests/ 41 file; pytest không có trong requirements.txt | khớp (lệnh); kết quả chạy test không kiểm được | Ghi kết quả chạy thực tế nếu có |
| 05 §6.3: kịch bản đã dùng A1, A2, A3, A4, C10, S2, S3, C2 | service/scenario_catalog.py: thấy A1, C2, C10, S2, S3; A2-A4 chưa xác nhận | không kiểm được | Đối chiếu từng mã bằng grep |
| 05 §7.2: "SMIOT" gồm 7 dashboard: 10-Farm Portfolio, Farm Data Quality, IoT & MQTT Fleet, Incident & Recovery, App, EC2, MongoDB & AI | Repo có 5 file dashboard JSON (terraform_farm_control_center/dashboards) | sai (cần làm rõ) | Làm rõ "App, EC2, MongoDB & AI" là một dashboard hay ba; sửa số lượng cho khớp với 01 §7 (5 dashboard) |
| 05 §7.2: log và trace lọc theo incident_id hoặc service smiot-smart-farm | deploy/datadog/smiot-logs.yaml:4, 9 | khớp | Không cần sửa |
| 04 §5 và 05 §6.4 / PROGRESS.md:419-423: luồng ba thiết bị Velxio trên EC2 | PROGRESS.md:423 ghi EC2 chưa đồng bộ mã mới, /devices chưa có tab Node 3, chưa xác minh luồng ba thiết bị trên EC2 và UI | không kiểm được (trạng thái EC2 hiện tại) | Nếu hồ sơ nói đã vận hành trên EC2 thì phải sửa; ghi rõ là đã kiểm trên mô phỏng cục bộ |
| 04 §4 và 07 §6: DD_TRACE_AGENT_URL có mặc định nội bộ | service/observability.py:37 (setdefault 127.0.0.1:8126) | khớp | Không cần sửa |

## Tổng kết

- Tổng số dòng kiểm: 69
- Khớp: 46
- Sai: 12 (gồm 1 sai nhỏ về thiếu mục bảng, 1 sai nhỏ về quyền admin/manage_users, 1 sai về tên dashboard, còn lại là thiếu biến môi trường, thiếu unit systemd, nguồn trích dẫn không có nội dung, và NICEGUI_STORAGE_SECRET được mô tả là bắt buộc)
- Không kiểm được: 11 (dữ liệu live Datadog, dữ liệu runtime, số đếm chưa đếm đủ từ mã tĩnh, EC2 hiện tại)

## Ba lỗi quan trọng nhất

1. Danh sách biến môi trường (04 §4, 07 §6) thiếu nhiều tên đang được mã đọc, gồm MONGODB_URI, DD_API_KEY/DD_APP_KEY, GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, và 5 tên VELXIO trong deploy/velxio.env.example.
2. NICEGUI_STORAGE_SECRET không bắt buộc ở production trong mã (service/session_security.py:13-28 chỉ ghi cảnh báo và sinh secret ngẫu nhiên). Các mục 01 §6, 04 §4, 05 §5, 07 §6 đang ghi là bắt buộc.
3. Không có unit smiot.service trong deploy/systemd/ (04 §5 bước 4). 01 §3.3 và 07 §5 trích ARCHITECTURE.md cho systemd và /opt/smiot, nhưng ARCHITECTURE.md không có nội dung này.

## Ghi chú thêm

- README.md dòng 19 có định danh tài khoản và instance AWS. Không đưa nội dung này vào hồ sơ nộp; kiểm chứng này không sao chép giá trị đó.
- Repo có file .env ở gốc (đã nằm trong .gitignore). Kiểm chứng này chỉ đọc tên biến, không đọc giá trị.
