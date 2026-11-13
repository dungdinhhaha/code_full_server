# Dàn ý bộ hồ sơ nộp (7 file .docx) và phân việc

Nguồn duy nhất: `outputs/nop_bai_v2/00_fact_sheet.md` (viết tắt FS, kèm số mục). Module định dạng: `_build/style.py` (hàm `new_document`, `add_heading`, `add_paragraph`, `add_bullets`, `add_table`, `add_figure`, `save`). Hình sinh bằng matplotlib/PNG, lưu trong `_build/img/`.

## Quy tắc chung (mọi agent)

1. Tiếng Việt có dấu, giọng trung tính, rõ ràng, dễ hiểu. Không tự phê bình, không hạ thấp dự án.
2. Không ghi tên cuộc thi. Không ghi ngành, chuyên ngành. Nhóm: Simpson. Tên dự án: "Trung tâm giám sát, điều hành và phục hồi sau sự cố nhà màng SMIOT".
3. Không viết mục "chưa làm", "đang bổ sung". Chỉ khẳng định điều đã có bằng chứng trong FS. Điều chưa kiểm được thì không đưa vào văn bản như thể đã có (bỏ qua hoặc diễn đạt đúng phạm vi: "theo mã nguồn", "khai báo trong mã").
4. Mỗi con số có nguồn (đường dẫn file hoặc tên file JSON) ngay cạnh số hoặc trong cột "Nguồn" của bảng.
5. Số trong hai file `drill_suite_*.json` ghi là "dữ liệu diễn tập" (một lần chạy mỗi mã), không phải ngưỡng đã duyệt.
6. Cấm xuất hiện trong mọi file: token, khóa API, mật khẩu, chuỗi kết nối, địa chỉ IP, ID tài khoản AWS, email cá nhân. Bỏ qua giá trị đó nếu FS có. Tên biến môi trường (ví dụ `SMIOT_DEMO_CONTROL_TOKEN`) được phép, giá trị thì không.
7. Snapshot `docs/datadog_config_snapshot/` có header Authorization trong một file workflow: không trích giá trị, không dẫn file đó làm nguồn, không đưa vào hồ sơ.
8. Từ "chưa kiểm được" chỉ dùng trong ghi chú nội bộ của file này, không dùng trong file nộp.
9. Thiết bị và cảm biến là ảo (mô phỏng). Không khẳng định có phần cứng thật. Dữ liệu Velxio gắn `synthetic=true`.
10. Không nêu số test đạt (281 / 162) vì chưa chạy lại; có thể nêu "41 file test" với nguồn `tests/test_*.py`.
11. ID Datadog: dùng ID live 13/11 (mục 4.2a, 4.3a FS). Không dùng ID cũ. ID monitor/dashboard/workflow là định danh công khai trong org, không phải bí mật; vẫn không in header hay khóa.
12. Mỗi file: trang bìa + mục lục tự sinh (style.new_document), tiêu đề đánh số tối đa cấp 3, mỗi hình/bảng có chú thích. Tên file đúng như dưới đây, lưu trong `outputs/nop_bai_v2/`.

---

## Agent A

### 01_kien_truc_giai_phap.docx
Mục:
1. Bài toán và phạm vi (FS 1: 10 nhà màng, mô phỏng, ngoài phạm vi)
2. Mô hình Phát hiện – Điều tra – Phản ứng (FS 1 hàng "Ba pha")
 2.1 Phát hiện (watchdog, sequence, heartbeat, monitor)
 2.2 Điều tra (hồ sơ sự cố, hộp đen, Datadog điều tra)
 2.3 Phản ứng (lệnh có ACK, khôi phục có guard, xác minh)
3. Kiến trúc tổng thể (FS 2.1)
 3.1 Thành phần chính
 3.2 Phân vai MongoDB – Datadog – ứng dụng (Datadog điều tra, MongoDB tác động và giữ bằng chứng, ứng dụng điều hướng)
 3.3 Triển khai trên EC2 (`smiot.service`, vùng ap-southeast-2; không nêu IP, ID tài khoản)
4. Luồng dữ liệu (FS 2.2) và nguyên tắc an toàn cục bộ
5. Ba ca trình diễn (FS 5.3), nêu bằng chứng theo EVIDENCE_INDEX
6. Bảo mật và ranh giới (FS 6.1, chỉ cơ chế đã có)
7. Số liệu tổng hợp (FS 7)
Hình/bảng: ít nhất 3 hình, 3 bảng.
- Hình 1 (bắt buộc): sơ đồ luồng Phát hiện – Điều tra – Phản ứng (3 khối nối mũi tên, dưới mỗi khối liệt kê thành phần).
- Hình 2: sơ đồ kiến trúc thành phần (thiết bị ảo/Velxio -> MQTT -> app -> MongoDB / Datadog -> workflow -> app).
- Hình 3: sơ đồ phân vai MongoDB – Datadog – app.
- Bảng: thành phần và nguồn; ba ca trình diễn; số liệu đếm được.

### 07_khai_bao_thanh_phan_va_cong_cu.docx
Mục:
1. Mục đích và phạm vi khai báo
2. Thành phần phần mềm (FS 2.1, `requirements.txt`: NiceGUI, pymongo, ddtrace, ...)
3. Dịch vụ bên ngoài (MongoDB Community self-managed, Datadog, Open-Meteo, Gemini, Telegram, MQTT) – nêu vai trò, không nêu khóa
4. Công cụ và mô phỏng (Velxio 3 project, cầu nối, kịch bản 36 mã)
5. Hạ tầng triển khai (EC2, systemd, Datadog Agent)
6. Biến môi trường (chỉ tên biến và mục đích, FS 6.1)
7. Dữ liệu mô phỏng và nhãn nguồn (`synthetic=true`, `source`)
Hình/bảng: 1 hình (sơ đồ phân lớp thành phần/công cụ), 3 bảng (thành phần, dịch vụ ngoài, biến môi trường theo tên).

---

## Agent B

### 02_kien_truc_du_lieu_mongodb.docx
Mục:
1. Vai trò MongoDB trong hệ thống (tác động và giữ bằng chứng)
2. Mô hình dữ liệu (FS 3.1: 26 tên collection trong mã, nhóm theo chức năng: telemetry; sự cố/bằng chứng; kịch bản; người dùng/vận hành; mùa vụ/truy xuất)
3. Chỉ mục (FS 3.2: unique partial, partial, TTL, unique, compound; số liệu 36 khai báo, 3 partial, 2 TTL)
4. Time Series (FS 3.3: script migrate, timeField/metaField/granularity; nói "khi tạo bằng script")
5. Aggregation pipeline (FS 3.4: hộp đen 7 nhánh `$unionWith`, `$setWindowFields` + `$shift`, GAP_FACTOR=3, chu kỳ 30 giây)
6. Ràng buộc dữ liệu: `$jsonSchema` 6 collection ở chế độ warn/moderate (FS 3.5), idempotency, rate limit, farm lock
7. Tính năng không dùng (change streams, transactions, Atlas Search): nêu trung tính dưới dạng "thiết kế chọn" nếu cần
8. Script hỗ trợ (benchmark, quality report, GDD forecast)
Hình/bảng: ít nhất 3 hình, 4 bảng.
- Hình 1: sơ đồ nhóm collection và quan hệ (incident_id nối operational_incidents, findings, action_ledger, telemetry...).
- Hình 2: sơ đồ pipeline hộp đen 7 nhánh `$unionWith` -> `$setWindowFields`.
- Hình 3: biểu đồ cột số index theo loại hoặc số collection theo nhóm (từ FS 3.2 / 3.1).
- Bảng: danh sách collection; index; pipeline; tính năng và căn cứ.
Lưu ý: không nêu "đã áp dụng trên EC2" cho index, validator, Time Series; nêu "khai báo trong mã". Không nêu chuỗi kết nối. Dùng "7 nhánh" (xem mâu thuẫn M3).

---

## Agent C

### 03_kien_truc_observability_datadog.docx
Mục:
1. Vai trò Datadog (quan sát, điều tra; correlation ID trong log, span, document)
2. Thu thập tín hiệu
 2.1 Metric DogStatsD (19 tên trong `service/datadog_metrics.py`; chuỗi `smiot.*` 78 literal, không gọi là 78 metric)
 2.2 APM / ddtrace và span tùy chỉnh (FS 4.5)
 2.3 Log qua Agent (`deploy/datadog/smiot-logs.yaml`)
 2.4 LLM Observability (có điều kiện bật)
3. Dashboard (live: 5 dashboard, tên theo FS 4.1; mô tả theo file JSON local, widget 5-7 mỗi dashboard)
4. Monitor (live 19 SMIOT; IaC 23 định nghĩa; bảng theo ID live)
5. Workflow (live 10, published)
6. Hạ tầng dạng mã (`deploy/datadog/terraform_*`)
7. Đọc ngược từ ứng dụng (`service/datadog_reader.py`, thông báo `POST /api/integrations/datadog/notification` có token – chỉ nêu tên biến)
Hình/bảng: ít nhất 3 hình, 4 bảng.
- Hình 1: sơ đồ luồng tín hiệu app -> DogStatsD/ddtrace/log -> Datadog -> monitor -> workflow -> app.
- Hình 2: biểu đồ cột số monitor theo nguồn (live SMIOT 19, IaC 23, ...) hoặc số widget theo dashboard.
- Hình 3: sơ đồ ánh xạ monitor -> workflow -> hành động cho 3 ca.
- Bảng: dashboard; monitor (ID live, tên, loại); workflow; nhóm metric.
Không in giá trị trạng thái Alert/No Data như kết quả diễn tập; nếu nêu thì ghi "ảnh chụp trạng thái 13/11" (FS 4.2a). Bỏ qua mọi nội dung từ `docs/datadog_config_snapshot`.

### 06_mo_ta_su_co_tinh_huong_trinh_dien.docx
Mục:
1. Mục đích và cách đọc số liệu (dữ liệu diễn tập, mỗi mã một lần chạy, không phải ngưỡng đã duyệt)
2. Danh mục 36 kịch bản (A7, C10, D7, H6, S6; FS 5.1)
3. Ba ca trình diễn: mô tả sự cố – phát hiện – điều tra – phản ứng (FS 5.3)
 3.1 Ca 1 báo offline sai
 3.2 Ca 2 độ ẩm đất Node 2 đứng yên
 3.3 Ca 3 `smiot.service` dừng
4. Kết quả diễn tập đo được (FS 5.2 bảng A và B, chỉ các mã đã chạy, ghi nguồn JSON)
5. Ranh giới mô phỏng (Velxio, `synthetic=true`, không phần cứng)
Hình/bảng: ít nhất 3 hình, 3 bảng.
- Hình 1: dòng thời gian (timeline) một ca (ví dụ A3 hoặc C10 từ bảng A/B).
- Hình 2: biểu đồ cột thời gian phát hiện Datadog và phục hồi app theo mã (A3, C10, A2, S3...).
- Hình 3: sơ đồ ba ca theo Phát hiện – Điều tra – Phản ứng.
- Bảng: danh mục kịch bản theo nhóm; kết quả suite 12/11; kết quả suite 13/11.
Lưu ý: không đưa các mã bị bỏ qua (A1, A2, A4 ở suite 12/11) thành kết quả; không đưa số "độ trễ phát hiện" cho mã không Alert. S3: ghi rõ monitor báo là flatline. A4 13/11: W9 không Alert.

---

## Agent D

### 04_repository_va_huong_dan_cai_dat.docx
Mục:
1. Cấu trúc repository (thư mục chính: `main.py`, `pages/` 15 module, `service/` 37 module, `components/`, `scripts/` 62 file .py, `velxio/` 3 project, `deploy/`, `docs/`, `tests/`)
2. Yêu cầu hệ thống (Python, `requirements.txt`, MongoDB, MQTT broker, Datadog Agent tùy chọn)
3. Cài đặt môi trường local (tạo venv, cài gói, đặt biến môi trường theo tên, chạy `main.py`)
4. Triển khai trên EC2 (systemd `smiot.service`, thư mục ứng dụng `/opt/smiot`, file môi trường `/etc/smiot/app.env` không ghi nội dung)
5. Cấu hình Datadog (Agent, `smiot-logs.yaml`, Terraform)
6. Chạy Velxio và cầu nối (`scripts/velxio_mqtt_bridge.py`)
7. Route giao diện (16) và API (10) – bảng
Hình/bảng: ít nhất 2 hình, 4 bảng.
- Hình 1: cây thư mục repository.
- Hình 2: sơ đồ các bước cài đặt/triển khai hoặc biểu đồ cột số module theo thư mục.
- Bảng: thư mục và vai trò; biến môi trường (tên + mục đích); route UI; route API.
Không in IP, domain riêng, giá trị biến, token. Lệnh mẫu chỉ dùng chỗ giữ chỗ như `<GIÁ_TRỊ>`. Không đưa `.env`, `farm_auth.db` vào hướng dẫn như tệp cần nộp.

### 05_readme_yeu_cau_kiem_thu.docx
Mục:
1. Giới thiệu dự án (README ngắn: bài toán, tính năng, phạm vi)
2. Yêu cầu chức năng (từ `PRD.md`, FS 1)
3. Yêu cầu phi chức năng và bảo mật (FS 6.1)
4. Kế hoạch và danh mục kiểm thử
 4.1 Kiểm thử tự động (`tests/`, 41 file `test_*.py`)
 4.2 Kiểm thử bằng kịch bản diễn tập (36 mã; API kịch bản có token, idempotency, giới hạn tốc độ)
 4.3 Tiêu chí chấp nhận cho từng ca trình diễn
5. Kết quả diễn tập (tham chiếu tài liệu 06, nhắc "dữ liệu diễn tập")
6. Hướng dẫn tái lập kiểm thử (lệnh chạy test, chạy kịch bản qua API; token là biến môi trường)
Hình/bảng: ít nhất 2 hình, 3 bảng.
- Hình 1: sơ đồ các lớp kiểm thử (test tự động, kịch bản diễn tập, kiểm tra trên Datadog/MongoDB).
- Hình 2: biểu đồ cột số kịch bản theo nhóm (A7, C10, D7, H6, S6).
- Bảng: yêu cầu chức năng; cơ chế bảo mật; tiêu chí chấp nhận ba ca.
Không nêu số test đạt. Không dùng từ "chưa chạy".

---

## Danh sách mâu thuẫn trong fact sheet (ghi chú nội bộ; agent viết chọn số có nguồn live mới nhất)

M1. Số monitor Datadog: live 13/11 có 30 trong org, 19 "SMIOT" (FS 4.2a, 7); IaC 23 định nghĩa (17 + 5 + 1); snapshot 08/11 có 17 (7 hạ tầng + 10 SMIOT/APM). Bảng live liệt kê 18 dòng ID nhưng FS ghi 19 (đếm lại bảng 4.2a: 342585819-342585838 cho 14 dòng, + 342734303, 342734743, 343029221, 343594185, 343594187 = 19; khớp nếu tính đủ 14+5). Chọn: dùng 19 (live 13/11) làm số monitor SMIOT; IaC 23 chỉ là "định nghĩa trong mã", không cộng với live.
M2. ID cũ so với ID live: monitor Ca 1 (341409441), Ca 3 (340356283) và 4 ID khác trong E-50/E-70 không có trên live; workflow Ca 1/2/3 có hai bộ ID (e2835af0/18d1b008/b83453ff cũ so với ffd62026/2f9a3c1d/373ed0c0 live). Chọn: ID live. Không dùng ID snapshot 08/11.
M3. `$unionWith`: tài liệu `docs/submission/01`, `02`, E-16 ghi 4 nhánh; mã `service/incident_blackbox.py` 345-472 có 7 nhánh (FS 3.4, 7). Chọn: 7 (mã hiện tại).
M4. Số widget dashboard: tài liệu cũ "8 widget (04/11)" so với file JSON 5-7 mỗi dashboard (7, 5, 6, 6, 7 = 31, cộng 1 dashboard "smiot_additional"); live chỉ có danh sách, không có số widget. Chọn: số theo file JSON local, ghi rõ nguồn là file.
M5. Dashboard: live 5 dashboard (tên Portfolio, Data Quality, IoT & MQTT Fleet, Incident & Recovery, App/EC2/MongoDB/AI); snapshot 08/11 và E-52 còn dùng "Farm Operations & Recovery (US)" ID `nkc-685-vw8` không thấy trên live. Chọn: 5 dashboard live.
M6. Số test: 162 (tài liệu 06/11) so với 281 (PROGRESS 12/11) so với 41 file. Chưa chạy lại. Chọn: chỉ nêu 41 file `tests/test_*.py`; không nêu số đạt.
M7. Index: 36 khai báo (19 + 11 + 6) nhưng FS ghi có trùng lặp chủ đích giữa ba nơi, nên 36 không phải số index khác biệt. Chọn: ghi "36 lệnh khai báo trong mã (có trùng lặp chủ đích)" hoặc không nêu tổng; không nói "36 index trên cơ sở dữ liệu".
M8. Collection: "26 tên" (18 + 8) gồm `_counters`; mục 7 ghi "25 nghiệp vụ + `_counters`", bảng 3.1 liệt kê 25 dòng. Chọn: 25 collection nghiệp vụ (bảng) và 26 tên kể cả kỹ thuật; ghi nhất quán một cách.
M9. Ca 3 mã kịch bản so với suite: bảng A ghi S3 phát hiện bởi monitor 342585819 (flatline) chứ không phải W7; S2/C2 không phát hiện trên DD. Chọn: chỉ trình bày đúng như bảng, không gán S3 cho W7.
M10. Suite 12/11 vs 13/11: A1, A2, A4 bỏ qua ngày 12/11, đo lại 13/11; A4 13/11 không Alert. Chọn: dùng bảng B (13/11) cho A1, A2, A4; bảng A cho A3, C10, S2, S3, C2.
M11. Trạng thái monitor: W7 (343594187) và W8 (343594185) đang Alert lúc đọc 13/11; AI ask latency (342585824) và PLC command latency (342585825) No Data. Đây là ảnh chụp trạng thái, không phải kết quả diễn tập; không dùng làm bằng chứng phát hiện.
M12. Số kịch bản: docstring 36 và đếm 36 khớp; nhóm H dùng chung module với A (`scenario_domain_actuator_infra.py`), D và S chung module (`scenario_domain_sensor_device.py`). Không mâu thuẫn, chỉ lưu ý khi nêu "module theo nhóm".
M13. Tên metric: 78 chuỗi `smiot.*` gồm cả span và sự kiện log; chỉ 19 xác nhận là lệnh DogStatsD trong `datadog_metrics.py`. Chọn: nói "19 metric gọi trực tiếp" và "78 chuỗi tên".
M14. Ngày/Mongo: chỉ mục, validator, Time Series, topology trên DB sống không đọc được; mã và tài liệu chỉ cho thấy khai báo. Chọn: viết "theo khai báo trong mã".
M15. Route: FS 2.1 liệt kê 15 route @ui.page được kể tên (đếm danh sách: `/`, `/login`, `/incident`, `/incident/{incident_id}`, `/inverter`, `/plc`, `/devices`, `/permission`, `/schedule`, `/history`, `/chart`, `/data`, `/projects`, `/mongodb-lab`, `/lot/{token}`, `/traceability` = 16). Khớp 16. API: liệt kê 10 khớp 10.
M16. Cổng/biến: `DD_TRACE_AGENT_URL` mặc định có địa chỉ loopback và MQTT `localhost:1883` – địa chỉ loopback không phải IP công khai, nhưng để tuân thủ quy tắc, viết "cổng MQTT mặc định 1883, kết nối nội bộ" không in địa chỉ.
M17. Ghi chú nội bộ: FS 6.2 nêu token trong snapshot và broker công cộng của cầu nối; không đưa vào hồ sơ. Cầu nối Velxio: không nêu tên broker công cộng mặc định.
