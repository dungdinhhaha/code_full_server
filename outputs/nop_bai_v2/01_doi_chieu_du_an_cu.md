# Đối chiếu dự án cũ (A) và dự án hiện tại (B)

**Ngày đọc:** 2026-11-13. **Phạm vi:** chỉ đọc file. Không chạy ứng dụng, không gọi Datadog, không gửi MQTT, không ghi DB.

- **A** = `D:\attt\code_full_server` (dự án cũ)
- **B** = `D:\IOT Trung\code_full_server` (dự án thi hiện tại)

Ký hiệu đường dẫn: file nằm trong A viết tắt là `A:\...`, file trong B là `B:\...` (đường dẫn đầy đủ ở mục 5).

---

## 1. Dự án A làm được gì

**Mục tiêu (theo tài liệu của A):** giám sát và điều khiển nhà nông nghiệp thông minh "SMIOT System v2.0", có cảm biến môi trường, biến tần (inverter) và PLC điều khiển 8 bơm/van (Q0-Q7). Nguồn: `A:\PROJECT_CONTEXT.md` mục 1 và mục 5.

**Chức năng thật, đọc được trong source:**

| Nhóm | Nội dung | Bằng chứng |
|---|---|---|
| Trang giao diện (11 route `@ui.page`) | `/` (home), `/login`, `/projects`, `/inverter`, `/plc`, `/devices`, `/permission`, `/schedule`, `/history` và `/chart`, `/data` | `A:\pages\home.py:1277`, `A:\pages\login.py:202`, `A:\pages\project.py:111`, `A:\pages\inverter.py:30`, `A:\pages\plc.py:7`, `A:\pages\devices.py:458`, `A:\pages\permission.py:73`, `A:\pages\schedule.py:147`, `A:\pages\chart.py:8,12`, `A:\pages\data_table.py:10` |
| Thiết bị | Điều khiển bơm qua PLC (8 điểm), đọc/ghi tần số, công suất, PID trên inverter; có khóa an toàn cooldown/lock | `A:\memory.md` mục 2; `A:\PROJECT_CONTEXT.md` mục 5 |
| Cảm biến | Nhiệt độ/độ ẩm không khí và đất, EC, pH, đồng hồ lưu lượng (flow) | `A:\PROJECT_CONTEXT.md` mục 5; `A:\pages\home.py` |
| Giao thức | MQTT, subscribe `farm/data`, `farm/sensor`, `farm/ai`, `farm/status`; publish `farm/inverter`, `farm/control`, `farm/pid`, `farm/notify` | `A:\service\mqtt.py:561-564`; grep publish trong `A:\service\`, `A:\pages\`, `A:\main.py` |
| Giám sát mất kết nối | "Trọng tài SCADA": PLC timeout 10 giây, inverter timeout 60 giây, rollback UI khi quá hạn | `A:\PROJECT_CONTEXT.md` mục 3; `A:\memory.md` mục 2 |
| Lịch tưới | Lịch tưới tự động, log lượng nước thực tế theo flow meter | `A:\memory.md` mục 2; bảng `schedules`, `schedule_logs` trong `A:\service\auth.py:143,156` |
| Phân quyền | 11 quyền cố định (RBAC), vai trò admin/operator/viewer, quyền theo farm | `A:\service\auth.py:17` (`FIXED_PERMISSIONS`), `A:\service\auth.py:104-125`; `A:\memory.md` mục 1 |
| Thông báo | Lưu thông báo vào bảng `notifications`, gửi qua MQTT `farm/notify` tới Telegram | `A:\service\auth.py:171`; `A:\service\telegram_bot.py:2-4` |
| Bot Telegram và AI | Bot đọc dữ liệu (read-only), gọi Gemini API `gemini-2.5-flash`, 9 hàm công cụ chỉ đọc | `A:\service\ai_service.py:189`; `A:\service\ai_tools.py:10-234`; `A:\manual_test_checklist.md` |
| Thời tiết | Dữ liệu thời tiết qua lớp `WeatherAPIClient` | `A:\service\weather_api.py`; `A:\pages\home.py:4` |
| Giám sát máy chủ | Cảnh báo CPU/RAM qua Telegram; bắt lỗi toàn cục gửi cảnh báo | `A:\service\scheduler.py:169-175`; `A:\main.py:45-82` |
| Thiết bị (danh mục) | Trang danh mục thiết bị, thông số kỹ thuật, thông tin hiệu chuẩn | `A:\pages\devices.py:398-443` |
| Truy cập công khai | Chạy ngrok tunnel qua `ngrok.service` | `A:\PROJECT_CONTEXT.md` mục 4; `A:\ngrok.service` |

**Dữ liệu và lưu trữ:**
- **SQLite: CÓ.** `sqlite3.connect` tại `A:\service\auth.py:66`. Các bảng: `users`, `permissions`, `user_permissions`, `user_farms`, `inverter_mode`, `schedules`, `schedule_logs`, `notifications`, `telemetry_sensor`, `telemetry_node`, `telemetry_water`, `telemetry_flow` (`A:\service\auth.py:89-226`). Thêm `import sqlite3` trong `A:\pages\project.py` và `A:\pages\permission.py` (docstring ghi "Kết nối trực tiếp SQLite").
- **MongoDB: KHÔNG.** Tìm chuỗi `mongo` trong toàn bộ `.py` của A: 0 kết quả.
- **Datadog: KHÔNG.** Tìm chuỗi `datadog`: 0 kết quả.
- **Trạng thái trong RAM:** biến `state` dictionary, mất khi khởi động lại. `A:\memory.md` mục 3 ghi nhận rủi ro này.
- **Phạm vi farm:** Greenhouse A-D (`A:\memory.md` mục 1). Trang inverter ghi "Hiện tại chỉ Greenhouse A đang hoạt động" (`A:\pages\inverter.py:301`).
- **API HTTP:** 2 route: `POST /api/js_error` (`A:\main.py:88`), `GET /api/inverter` (`A:\pages\inverter.py:12`).
- **Kiểm thử:** `A:\manual_test_checklist.md`, kiểm thử thủ công cho bot Telegram AI. Không có thư mục `tests\`.
- **Thư viện:** `A:\requirements.txt` gồm nicegui, paho-mqtt, pandas, openpyxl, psutil, python-dotenv và các gói thời tiết. Không có pymongo, ddtrace, boto3.

---

## 2. Dự án B làm được gì

**Mục tiêu (theo `B:\PRD.md`):** trung tâm vận hành cho 10 nhà màng dưa lưới ảo, mở một sự cố từ tín hiệu đến điều tra, hành động có kiểm soát hoặc từ chối, bằng chứng lưu trữ, và xác nhận phục hồi. Dữ liệu và thiết bị là ảo, "trừ khi có nguồn vật lý được tích hợp và xác minh" (`B:\PRD.md` dòng Product).

**Chức năng thật, đọc được trong source:**

| Nhóm | Nội dung | Bằng chứng |
|---|---|---|
| Trang giao diện (16 route `@ui.page`) | `/`, `/login`, `/incident`, `/incident/{id}` (chỉ admin), `/inverter`, `/plc`, `/devices`, `/permission`, `/schedule`, `/history`, `/chart`, `/data`, `/projects`, `/mongodb-lab`, `/lot/{token}` (công khai, đọc-only), `/traceability` (chuyển hướng cũ) | `B:\pages\home.py:938`, `B:\pages\incident.py:1355,1639`, `B:\pages\inverter.py:165`, `B:\pages\plc.py:390`, `B:\pages\devices.py:489`, `B:\pages\permission.py:96`, `B:\pages\schedule.py:95`, `B:\pages\chart.py:37,42`, `B:\pages\data_table.py:50`, `B:\pages\project.py:128`, `B:\pages\mongodb_lab.py:210`, `B:\pages\public_lot.py:73`, `B:\pages\traceability.py:6` |
| 10 nhà màng | `greenhouse_a` đến `greenhouse_j` | `B:\service\farm_registry.py:3-14` |
| Thiết bị ảo | 9 nhóm thiết bị ảo mỗi farm; actuator ảo: bơm, van, quạt, lưu lượng, áp suất, thông gió; PLC ảo có phản hồi và kiểm tra farm | `B:\PRD.md` dòng Scope; `B:\service\datadog_metrics.py` (`smiot.actuator.*`); `B:\pages\plc.py:229-274` |
| Kịch bản diễn tập | Danh mục 36 kịch bản (theo docstring); 3 module domain: crops, sensor_device, actuator_infra; API `POST /api/demo/scenarios`, `GET /api/demo/scenarios/{id}` | `B:\service\scenario_catalog.py:1`; `B:\main.py:253,440` |
| Lệnh điều khiển và ACK | Ghi nhận trạng thái lệnh, khớp ACK theo run; sổ `action_ledger` | `B:\service\mqtt.py:15,84,99`; `B:\service\mqtt.py` (2 lần gọi `action_ledger`) |
| Phát hiện | Watchdog telemetry; kiểm tra sequence gap/duplicate/regression; detector heartbeat; monitor Datadog | `B:\service\telemetry_health.py`, `B:\service\telemetry_findings.py`, `B:\service\detector_heartbeat.py`; `B:\deploy\datadog\terraform_monitors\monitors.tf:152,172` |
| Điều tra | Trang sự cố danh sách và hồ sơ 6 chặng; Datadog điều tra, MongoDB giữ hồ sơ, app điều hướng (docstring) | `B:\pages\incident.py:1-3`; `B:\service\incident_blackbox.py`, `B:\service\incident_lifecycle.py:390` |
| Phản ứng có kiểm soát | Endpoint khôi phục W2 (`recover`, `verify`), xác minh khôi phục W3, xóa safe-mode có kiểm tra bằng chứng | `B:\main.py:625,698,801,960`; `B:\service\w3_recovery_verification.py`; `B:\service\scenario_recovery.py` |
| Chứng minh phục hồi | Verifier kiểm tra health, MongoDB, MQTT và telemetry mới; "Unknown không bao giờ là recovered" (PRD) | `B:\main.py:801`; `B:\PRD.md` mục Product acceptance 5; `B:\PROGRESS.md` mục W3 |
| Thông báo | Endpoint nhận sự kiện Datadog, lưu vào chuông thông báo của app, có token xác thực | `B:\main.py:1010`; `B:\service\datadog_notifications.py` |
| Datadog | Khởi tạo ddtrace (`DD_SERVICE=smiot-smart-farm`); metric `smiot.*`; đọc trạng thái monitor; 2 resource `datadog_monitor` trong Terraform; 5 dashboard JSON; 3 workflow JSON trong snapshot | `B:\service\observability.py:24-37`; `B:\service\datadog_metrics.py`; `B:\service\datadog_reader.py`; `B:\deploy\datadog\terraform_monitors\monitors.tf`; `B:\deploy\datadog\terraform_farm_control_center\dashboards\`; `B:\docs\datadog_config_snapshot\20261108T150159Z\json\workflows\` |
| MongoDB | Kho chính: `telemetry`, `action_ledger`, `operational_incidents`, `incident_telemetry_evidence`, `notifications`, `users`, `schedules`, `schedule_logs`, `traceability_events`, `crop_cycles`, `agronomic_advisories`, và các collection khác | `B:\service\mongodb_store.py:17-50`; `B:\service\auth.py:1` ("MongoDB-backed application persistence") |
| Truy xuất lô và mùa vụ | Trang công khai theo mã QR; trang mùa vụ dùng aggregation MongoDB; ảnh theo giai đoạn | `B:\pages\public_lot.py`; `B:\pages\mongodb_lab.py:1-4`; `B:\service\mongodb_showcase.py` |
| Thời tiết | Open-Meteo, hiển thị nguồn rõ ràng, không hiện số mặc định khi lỗi | `B:\service\weather_api.py`; `B:\pages\farm_overview_component.py:1358-1380` |
| Bot Telegram và AI | Bot đọc tin MQTT, gửi qua Telegram HTTP API; AI Gemini và công cụ | `B:\service\telegram_bot.py:26-44`; `B:\service\ai_service.py:32`; `B:\service\ai_tools.py` |
| Tài liệu nộp | 6 bản viết (`docs\submission\01` đến `06`), kịch bản video, chỉ mục bằng chứng | `B:\docs\submission\`; `B:\docs\video\kich_ban_video_demo.md` |
| Kiểm thử | 41 file `test_*.py` trong `tests\` | `B:\tests\` |

**Dữ liệu và lưu trữ:**
- **MongoDB: CÓ, là kho chính.** `pymongo>=4.0,<4.18` (`B:\requirements.txt`).
- **Datadog: CÓ.** `ddtrace>=4.16.1,<5.0`, `boto3>=1.34,<2` (`B:\requirements.txt`).
- **SQLite: KHÔNG import trong code chạy.** Không có `import sqlite3` trong `B:\main.py`, `B:\service\`, `B:\pages\` (0 kết quả). Còn lại: comment và docstring nhắc SQLite (`B:\service\mongodb_telemetry.py:72,80,108`, `B:\service\mqtt.py:1017`, docstring `B:\pages\permission.py:3` vẫn ghi "Kết nối trực tiếp SQLite"), file `B:\farm_data.db` và `B:\farm_auth.db` còn ở thư mục gốc, và 2 script di chuyển `B:\scripts\migrate_sqlite_operational_to_mongodb.py`, `B:\scripts\migrate_sqlite_telemetry_to_mongodb.py`.
- **Trạng thái thiết bị:** B nêu rõ không điều khiển bơm/van/quạt phần cứng (`B:\PRD.md` mục Out of scope; `B:\PRD.md` mục Scope).

---

## 3. Bảng so sánh

Cột "B mạnh hơn ở đâu" chỉ ghi chỗ B có bằng chứng cụ thể. "Không áp dụng" nghĩa là hàng đó không phải điểm mạnh so sánh.

| Chức năng | A có? | B có? | B mạnh hơn ở đâu (có bằng chứng) |
|---|---|---|---|
| Dashboard tổng quan | Có, 1 trang chủ (`A:\pages\home.py:1277`) | Có, 10 farm trong một trang (`B:\pages\home.py:938`; `B:\PROGRESS.md` ghi nhận "Home renders 10 farms") | Số farm (10 so với 4), dữ liệu từ MongoDB |
| Lưu telemetry | Có, SQLite `telemetry_*` (`A:\service\auth.py:182-226`) | Có, MongoDB `telemetry` (`B:\service\mongodb_store.py`; `B:\service\mongodb_telemetry.py:64-93`) | Kho chuyên cho chuỗi thời gian, có ghi bản sao từ luồng SQLite cũ |
| Điều khiển bơm/biến tần | Có, điều khiển thiết bị thật qua MQTT (`A:\PROJECT_CONTEXT.md` mục 5) | Chỉ ảo (`B:\pages\plc.py:229-274`; `B:\PRD.md`) | Không áp dụng. B giới hạn chủ đích trong thiết bị ảo |
| Lịch tưới | Có (`A:\service\auth.py:143,156`) | Có (`B:\pages\schedule.py:95`; collection `schedules`, `schedule_logs`) | Nhãn "Thiết bị ảo" rõ ràng trong trang (`B:\pages\schedule.py:4-5`) |
| Phân quyền | Có, 11 quyền, SQLite (`A:\service\auth.py:17`) | Có, quyền gồm `pump_7_control`, `manage_users` (`B:\service\auth.py:25`) | Chưa so sánh chi tiết số quyền và phạm vi theo farm (chưa kiểm) |
| Thông báo | Có, bảng `notifications` và Telegram (`A:\service\auth.py:171`) | Có, collection `notifications` và chuông thông báo nhận sự kiện Datadog (`B:\main.py:1010`) | Nhận sự kiện từ Datadog có token xác thực và chống trùng lặp (`B:\main.py:1081-1083`) |
| Bot Telegram và AI | Có (`A:\service\telegram_bot.py`, `A:\service\ai_service.py`, `A:\service\ai_tools.py`) | Có (file tương ứng trong `B:\service\`) | Chưa so sánh chi tiết (chưa kiểm) |
| Thời tiết | Có (`A:\service\weather_api.py`) | Có (`B:\service\weather_api.py`) | Ghi nguồn và không hiện số mặc định khi lỗi (`B:\pages\farm_overview_component.py:1358-1380`) |
| MongoDB | Không (0 kết quả) | Có (`B:\requirements.txt`; `B:\service\mongodb_store.py`) | Kho vận hành chính, aggregation cho trang mùa vụ (`B:\pages\mongodb_lab.py:1-4`) |
| Datadog | Không (0 kết quả) | Có (`B:\service\observability.py`; `B:\service\datadog_metrics.py`; Terraform) | Metric `smiot.*`, monitor, dashboard, workflow, đọc trạng thái monitor |
| Phát hiện | Có, timeout SCADA: PLC 10 giây, inverter 60 giây (`A:\PROJECT_CONTEXT.md` mục 3) | Có, nhiều tín hiệu: watchdog, sequence gap/duplicate/regression, detector heartbeat, monitor (`B:\service\telemetry_health.py`; `B:\service\telemetry_findings.py`; `B:\deploy\datadog\terraform_monitors\monitors.tf:152,172`) | Phát hiện theo nhiều nguồn tín hiệu, lưu bằng chứng (`B:\service\telemetry_provenance.py`) |
| Điều tra | Không | Có, `/incident` và hồ sơ sự cố 6 chặng (`B:\pages\incident.py:1355,1639`; `B:\service\incident_blackbox.py`) | Mỗi sự cố có hồ sơ, Datadog điều tra và MongoDB giữ bằng chứng (`B:\pages\incident.py:1-3`) |
| Phản ứng | Có, điều khiển trực tiếp, cooldown/lock (`A:\memory.md` mục 2) | Có, lệnh có ACK, sổ hành động, endpoint khôi phục có kiểm soát (`B:\service\mqtt.py:84-99`; `B:\main.py:625,698`) | Hành động có kiểm soát và từ chối khi bằng chứng không đủ (`B:\PRD.md` mục Product acceptance 5) |
| Chứng minh phục hồi | Không. Chỉ rollback giao diện khi quá hạn (`A:\PROJECT_CONTEXT.md` mục 3) | Có, verifier kiểm tra health, MongoDB, MQTT, telemetry mới (`B:\main.py:801`; `B:\service\w3_recovery_verification.py`) | Có bước xác minh riêng; trạng thái "không rõ" không được tính là đã phục hồi (`B:\PRD.md`) |
| Mô phỏng thiết bị ảo | Không | Có, 9 nhóm thiết bị ảo mỗi farm, actuator ảo (`B:\PRD.md`; `B:\service\datadog_metrics.py`) | Có, mỗi thiết bị có định danh, nhịp gửi và số thứ tự riêng (`B:\PRD.md` acceptance 3) |
| Kịch bản diễn tập | Không | Có, 36 kịch bản, API bearer token (`B:\service\scenario_catalog.py:1`; `B:\main.py:253,440`) | Có API có xác thực bearer token, idempotency, khóa theo farm, giới hạn tốc độ qua Mongo (`B:\PROGRESS.md` mục Baseline observed; token trên EC2 chưa xác nhận) |
| Hồ sơ sự cố | Không | Có, `/incident/{id}`, tài liệu bằng chứng trong `B:\docs\` | Có hồ sơ và tài liệu bằng chứng cho từng sự cố |
| API | 2 route (`A:\main.py:88`; `A:\pages\inverter.py:12`) | Nhiều route: demo scenario, healthz, Datadog recover/verify/notification (`B:\main.py:128-1010`) | Có `/healthz` kiểm tra Mongo và MQTT (`B:\main.py:613`) |
| Truy xuất lô công khai | Không | Có, `/lot/{token}`, đọc-only (`B:\pages\public_lot.py:73`) | Có trang công khai không đăng nhập |
| Kiểm thử tự động | Không (chỉ checklist thủ công, `A:\manual_test_checklist.md`) | Có, 41 file test (`B:\tests\`) | Có kiểm thử tự động. Số lượt pass do `B:\PROGRESS.md` ghi (240/240); chưa chạy lại |

---

## 4. A có mà B chưa có hoặc B bỏ

1. **Điều khiển bơm và biến tần thật qua MQTT (PLC 8 điểm Q0-Q7, ghi PID inverter).** A có (`A:\PROJECT_CONTEXT.md` mục 5; `A:\pages\inverter.py`). B không có: B chủ đích chỉ dùng thiết bị ảo (`B:\PRD.md` Out of scope, "No pump/valve/fan hardware operation"). Đây là thay đổi phạm vi có chủ đích, không phải thiếu sót kỹ thuật.
2. **Triển khai đơn giản, không cần máy chủ DB ngoài.** A chỉ cần SQLite (`A:\service\auth.py:66`) và file `.db` nằm cạnh mã nguồn. B phụ thuộc MongoDB Community (`B:\requirements.txt`) và Datadog Agent theo `B:\ARCHITECTURE.md` "Deployment model". Đây là đánh đổi, không phải B thiếu tính năng.

Ghi chú thêm: A có bộ kiểm thử thủ công cho bot Telegram AI (`A:\manual_test_checklist.md`). B chưa có tài liệu tương đương cho bot trong mục kiểm thử đã đọc (chưa kiểm đầy đủ).

---

## 5. Bằng chứng và phạm vi kiểm

**Đã đọc hoặc đã kiểm bằng lệnh tìm chuỗi:**
- `A:\PROJECT_CONTEXT.md`, `A:\memory.md` (đọc đầu), `A:\manual_test_checklist.md` (đọc đầu), `A:\requirements.txt`, `A:\main.py` (route và cấu hình), danh sách `A:\pages\`, `A:\service\`, `A:\components\`.
- `B:\PRD.md`, `B:\ARCHITECTURE.md` (đầu), `B:\PROGRESS.md` (mục mới nhất), `B:\requirements.txt`, `B:\main.py` (đầu và route), danh sách `B:\pages\`, `B:\service\`, `B:\scripts\`, `B:\deploy\datadog\`, `B:\docs\`.
- Các số liệu "0 kết quả" (MongoDB và Datadog trong A; sqlite3 trong B) là kết quả tìm chuỗi trong các file `.py` của từng dự án.

**Chưa kiểm:**
- Chưa chạy ứng dụng, chưa chạy test (số 240/240 chỉ là lời ghi trong `B:\PROGRESS.md`).
- Chưa đếm lại 36 kịch bản trong `B:\service\scenario_catalog.py` (dựa trên docstring).
- Chưa mở các file bằng chứng vận hành như `outputs\evidence\w3_runtime_20261111T1255Z.json`. Trạng thái W1-W10 chỉ lấy từ `B:\PROGRESS.md`.
- Chưa đọc đầy đủ `A:\service\ai_service.py`, `B:\service\ai_service.py` để so sánh chi tiết.
- Chưa kiểm số quyền và phạm vi theo farm trong `B:\service\auth.py`.
- Chưa kiểm trạng thái Datadog thật. Mục này dựa trên file cấu hình và `B:\PROGRESS.md`, không gọi API Datadog.
- Chưa đối chiếu đầy đủ từng nhãn giao diện giữa A và B.
- `A:\memory.md` và `A:\PROJECT_CONTEXT.md` có chuỗi tiếng Việt bị lỗi mã hóa (UTF-8 đọc thành cp1252). Nội dung được hiểu theo ngữ cảnh.
