---
doc_id: SMIOT-SUB-06
title: "Tổng quan dự án và bằng chứng theo tiêu chí chấm điểm"
submission_section: 6
project: "SMIOT Smart Farm"
competition: "Mini Hackathon MongoDB x Datadog 2026"
version: "0.1-draft"
date: "2026-11-07"
language: vi
data_label: synthetic
mongodb: {edition: "Community", version: "8.0.34 (đối chiếu chỉ đọc 07/11)", deployment: "self-managed, standalone, EC2"}
datadog: {site: "US1", service: "smiot-smart-farm", env: "demo"}
cases:
  - {id: CA1, kind: false_offline, monitor: "341409441", control_monitor: "339977703", workflow: "e2835af0-63fc-48e0-9562-2a1ee4a351d3"}
  - {id: CA2, kind: soil_humidity_flatline, monitor: "339977691", workflow: "18d1b008-fb24-4713-aa0b-a1432d84ea80"}
  - {id: CA3, kind: service_down, monitor: "340356283", workflow: "b83453ff-e122-4148-9519-e698f2effa7f"}
evidence_index: "EVIDENCE_INDEX.md"
related_docs: [SMIOT-SUB-01, SMIOT-SUB-02, SMIOT-SUB-03, SMIOT-SUB-04, SMIOT-SUB-05]
reading_order: [SMIOT-SUB-06, SMIOT-SUB-01, SMIOT-SUB-05, SMIOT-SUB-04, SMIOT-SUB-02, SMIOT-SUB-03]
status: draft
---

# Tổng quan dự án và bằng chứng theo tiêu chí chấm điểm

## Tóm tắt

Tài liệu này dành cho người chấm đọc đầu tiên. Nó tóm tắt dự án SMIOT Smart Farm, chỉ ra MongoDB và Datadog được dùng ở đâu, và dẫn tới tài liệu 01 đến 05 cùng mã bằng chứng `[E-xx]` cho từng khẳng định. Tài liệu không thêm số liệu mới: mọi con số đều lấy từ tài liệu 01 đến 05 hoặc `EVIDENCE_INDEX.md`.

Bài toán: một ứng dụng có thể "xanh" ở mọi chỉ báo hạ tầng nhưng vẫn đưa ra quyết định sai. SMIOT phân biệt ba lớp lỗi (hiển thị sai, số đo đứng yên, tiến trình dừng) và gắn mỗi lớp với một phản ứng riêng: từ chối restart, giữ trạng thái an toàn HOLD, hoặc start đúng một unit sau guard. Datadog phát hiện và điều tra; MongoDB đo tác động và là nguồn xác minh phục hồi; ứng dụng điều hướng giữa hai bên.

Dữ liệu cảm biến là dữ liệu tổng hợp (luồng Wokwi hoặc bộ phát mô phỏng) và bơm là PLC ảo. Hệ thống không điều khiển thiết bị vật lý [E-02, E-13].

## SMIOT trong 30 giây

Bảy điểm khiến SMIOT đáng được xem kỹ. Mỗi điểm có mã bằng chứng và vị trí trong hồ sơ.

1. **Hai nền tảng, mỗi bên đúng vai.** Datadog phát hiện và điều tra; MongoDB đo tác động lên dữ liệu và xác nhận phục hồi; ứng dụng dẫn người xem sang đúng monitor, workflow và logs [E-17].
2. **Ba lớp lỗi, ba phản ứng riêng.** Ca 1 từ chối restart vì mẫu vẫn vào MongoDB; Ca 2 giữ HOLD và chỉ CLEAR sau verifier; Ca 3 start đúng một unit sau guard [E-16, E-22, E-24].
3. **Phục hồi được chứng minh bằng dữ liệu đọc lại**, không bằng việc lệnh chạy xong: mẫu biến thiên mới và ACK của PLC ảo (Ca 2), HTTP 200 và mẫu MongoDB mới (Ca 3) [E-22, E-24, E-59].
4. **Một mã sự cố nối hai hệ thống.** `incident_id` có mặt ở log, trace và MongoDB, nên từ một cảnh báo có thể đi tới nhật ký, dấu vết, sổ lệnh và mẫu telemetry của đúng sự cố đó [E-15, E-40].
5. **MongoDB dùng đúng chỗ mạnh.** Time Series cho chuỗi mẫu đo; một aggregation `$unionWith` bốn nhánh cùng `$setWindowFields` và `$shift` dựng dòng thời gian sự cố và khoảng thiếu mẫu ngay trong cơ sở dữ liệu; chỉ mục một phần cho sự cố đang mở [E-08, E-16].
6. **Datadog được dùng ở nhiều lớp vận hành.** Sáu monitor, ba workflow qua Private Action Runner, dashboard 12 widget, Logs, APM và LLM Observability [E-50, E-71, E-72].
7. **Ba ca đều có lượt chạy ghi nhận trên EC2 và Datadog** với mốc thời gian, mã monitor và mã execution [E-40, E-41, E-81, E-82].

## Bảng 0. Tóm tắt máy đọc được

| Khóa | Giá trị |
|---|---|
| Tên dự án | SMIOT Smart Farm |
| Lĩnh vực | Nông nghiệp thông minh: giám sát nhà màng trồng dưa lưới (farm `greenhouse_a`, hai node cảm biến) |
| Bài toán một câu | Xác định dữ liệu cảm biến còn đủ tin cậy để quyết định tưới và lịch thu hoạch hay không, và phản ứng đúng theo từng lớp lỗi |
| Loại dữ liệu | Tổng hợp (synthetic); nhãn nằm trong từng document (`source.synthetic`, `meta.source`) [E-13] |
| Thiết bị | PLC ảo; không có thiết bị vật lý [E-02] |
| Nền tảng | MongoDB Community 8.0.34, standalone, tự quản trên một EC2 (đối chiếu chỉ đọc 07/11, Tài liệu 02); Datadog US1, service `smiot-smart-farm`, env `demo` |
| Ứng dụng | NiceGUI, MQTT (Mosquitto), Nginx, Datadog Agent trên cùng EC2 [E-03] |
| Tính năng MongoDB | Time Series `telemetry`; chỉ mục ghép; chỉ mục một phần `active_incident_by_scope`; `$jsonSchema` (warn/moderate); aggregation `$unionWith` bốn nhánh; `$setWindowFields` với `$shift`; sao lưu và khôi phục logic [E-08, E-16, E-28, E-42] |
| Sản phẩm Datadog | Infrastructure Agent, DogStatsD, Log Management, APM (`ddtrace`), Database Monitoring cho MongoDB, tích hợp systemd, Monitors, Workflow Automation, Private Action Runner, Dashboards, LLM Observability (Tài liệu 03, Bảng 0) |
| Mã monitor | 339977691 (Ca 2), 339977703 (đối chứng Ca 1), 339990226 (phụ thuộc MongoDB), 339990232 (phụ thuộc MQTT), 340356283 (Ca 3), 341409441 (Ca 1) [E-50, E-70] |
| Mã workflow | e2835af0-63fc-48e0-9562-2a1ee4a351d3 (Ca 1); 18d1b008-fb24-4713-aa0b-a1432d84ea80 (Ca 2); b83453ff-e122-4148-9519-e698f2effa7f (Ca 3) [E-71] |
| Mã dashboard | `nkc-685-vw8`, 12 widget theo bản đọc ngày 06/11 [E-72] |
| Ba ca sự cố | Ca 1 báo offline sai (`false_offline`); Ca 2 độ ẩm đất Node 2 đứng yên (`soil_humidity_flatline`); Ca 3 `smiot.service` dừng (`service_down`) |
| Khóa truy vết | `incident_id` dạng `INC-SMIOT-<UTC>-<8HEX>` xuyên Datadog (log, trace) và MongoDB [E-15, E-40] |
| Kiểm thử | 162 test đạt, 17 tệp test, chạy local 06/11/2026 [E-30] |
| Công cụ AI và thành phần có từ trước 17/10 | Xem Phụ lục khai báo trong Tài liệu 01 (Phụ lục A, B) và `docs/DECLARATIONS.md` (đang bổ sung) |

## Mục lục

Tóm tắt; SMIOT trong 30 giây; Bảng 0; 1 Dự án làm gì và bài toán vận hành; 2 Đối chiếu tiêu chí chấm điểm; 3 Kiểm tra yêu cầu bắt buộc; 4 MongoDB được dùng như thế nào; 5 Datadog được dùng như thế nào; 6 Ba ca sự cố từ đầu đến cuối; 7 Điểm khác biệt và sáng tạo; 8 Tác động vận hành; 9 Chất lượng MVP và tài liệu; 10 Phạm vi và giới hạn; 11 Bản đồ tìm nhanh và câu hỏi thường gặp; 12 Thuật ngữ.

## 1. Dự án làm gì và bài toán vận hành

### 1.1 Dự án làm gì

1. SMIOT giám sát một nhà màng dưa lưới mô phỏng: hai node cảm biến, một PLC ảo, lịch tưới, trợ lý AI đề xuất lượng nước [E-03].
2. Số đo đến định kỳ 30 s qua MQTT, được ghi vào MongoDB Time Series cùng nhãn nguồn và nhãn tổng hợp [E-11, E-13].
3. Một watchdog trong ứng dụng và một probe ngoài ứng dụng đo tuổi mẫu, độ biến thiên và lệch trạng thái hiển thị [E-14, E-23].
4. Datadog nhận metric, log, trace; sáu monitor và ba workflow gắn với ba ca sự cố [E-50, E-71].
5. Mỗi phản ứng chỉ được coi là hiệu quả khi dữ liệu đọc lại từ MongoDB xác nhận (Tài liệu 01, §2, nguyên tắc R4).

### 1.2 Vì sao bài toán khó

Một ứng dụng có thể "xanh" ở mọi chỉ báo hạ tầng nhưng vẫn đưa ra quyết định sai (Tài liệu 03, §1). Câu hỏi đúng là "dữ liệu hiện tại còn đủ tin cậy để quyết định không", không chỉ "ứng dụng có chạy không" (Tài liệu 01, §1.2). Ví dụ trong hồ sơ: số đo độ ẩm đất đứng ở 2,4% làm quy tắc tưới danh nghĩa yêu cầu tưới vì thấp hơn 30%; hệ thống ghi quyết định `BLOCKED_HOLD` và không gửi lệnh bơm [E-40].

### 1.3 Ba lớp lỗi, ba phản ứng

Bảng 1.1. Ba lớp lỗi khác bản chất (Tài liệu 01, §1.3 [E-16]).

| Lớp lỗi | Triệu chứng | Dữ liệu trong MongoDB | Phản ứng đúng | Vì sao không dùng một phản ứng chung |
|---|---|---|---|---|
| Hiển thị sai, Ca 1 | Giao diện báo node OFFLINE | Mẫu mới vẫn đến | Từ chối restart | Restart xóa phiên và bằng chứng mà không đổi dữ liệu |
| Số đo đứng yên, Ca 2 | Độ ẩm đất Node 2 kẹt ở 2,4% | Mẫu đến nhưng không biến thiên | HOLD; CLEAR chỉ sau verifier | Restart không làm số đo biến thiên trở lại |
| Tiến trình dừng, Ca 3 | Không có HTTP, không metric từ app | MongoDB và MQTT hoạt động; mẫu mới ngừng vào | Start đúng một unit sau guard | Restart EC2, `mongod` hoặc `mosquitto` gây gián đoạn thêm |

## 2. Đối chiếu tiêu chí chấm điểm

### 2.1 Sáng tạo (30%)

| Tiêu chí | Trọng số | Dự án đáp ứng thế nào | Bằng chứng | Vị trí trong hồ sơ |
|---|---|---|---|---|
| Độc đáo của ý tưởng | 30% | (1) Chọn phản ứng theo lớp lỗi thay vì restart chung. (2) Ca 1 có phản ứng đúng là không tác động hạ tầng, được chứng minh bằng hai monitor đối chứng. (3) HOLD trước, CLEAR chỉ sau verifier đọc lại MongoDB. (4) Phục hồi định nghĩa bằng dữ liệu đọc lại, không bằng việc lệnh chạy xong | [E-16, E-22, E-50, E-55] | Tài liệu 01 §1.3, §2; Tài liệu 03 §4.2; Tài liệu 04 §5 |
| Cách dùng MongoDB | 30% | (1) Một aggregation `$unionWith` bốn nhánh gom mốc sự cố, mẫu lỗi, quyết định, lệnh và telemetry thành dòng thời gian. (2) Khoảng thiếu mẫu tính trong cơ sở dữ liệu bằng `$setWindowFields` và `$shift`. (3) Chỉ mục một phần cho sự cố đang mở; Time Series cho mẫu đo | [E-08, E-16] | Tài liệu 02 §4, §5.2, §6.1, §6.2 |
| Cách dùng Datadog | 30% | (1) Monitor đối chứng cho Ca 1. (2) Probe ngoài app vì metric của app ngừng khi app dừng. (3) Workflow gọi hành động định nghĩa sẵn qua Private Action Runner. (4) `incident_id` ở log, trace và MongoDB, không ở tag metric | [E-23, E-43, E-50, E-71] | Tài liệu 03 §2.3, §3.2, §4.2, §5 |

### 2.2 Kỹ thuật (30%)

| Tiêu chí | Trọng số | Dự án đáp ứng thế nào | Bằng chứng | Vị trí trong hồ sơ |
|---|---|---|---|---|
| Kiến trúc | 30% | (1) Luồng ingest MQTT đến MongoDB, watchdog trong app, probe ngoài app, guard trên host. (2) Hành động duy nhất trên host là `systemctl start smiot.service`, có allowlist sudoers, khóa chống chạy chồng, cooldown 300 s, kiểm đĩa dưới 85%. (3) Tách vai: Datadog điều tra, MongoDB đo tác động | [E-14, E-23, E-24, E-43] | Tài liệu 01 §3, §4, §6 |
| Triển khai MongoDB | 30% | (1) Time Series `timeField=timestamp`, `metaField=meta`, `granularity=seconds`. (2) Định danh thay đổi theo mẫu nằm trong `source`, không trong `meta`. (3) Ghi lặp lại an toàn bằng `command_id` và máy trạng thái vì không dùng giao dịch. (4) Sao lưu logic khớp 154.618/154.618 mẫu và 1/1 sự cố | [E-08, E-12, E-21, E-42] | Tài liệu 02 §2, §3, §4, §8 |
| Triển khai Datadog | 30% | (1) Sáu monitor, ba workflow, dashboard 12 widget. (2) Metric tag hữu hạn `farm`, `node`, `source`. (3) Log JSON có `incident.id`; trace; LLM Observability che nội dung. (4) 162 test đơn vị đạt | [E-20, E-30, E-50, E-72] | Tài liệu 03 §3, §4, §6, §8; Tài liệu 05 §5.1 |

### 2.3 Tác động (30%)

| Tiêu chí | Trọng số | Dự án đáp ứng thế nào | Bằng chứng | Vị trí trong hồ sơ |
|---|---|---|---|---|
| Giá trị kinh doanh và vận hành | 30% | (1) Tránh restart oan khi mẫu vẫn đến (Ca 1). (2) Chặn quyết định tưới trên số đo không đáng tin (Ca 2: `BLOCKED_HOLD`). (3) Chỉ start đúng một unit khi mọi dependency khỏe (Ca 3: `mongod` và `mosquitto` active ở cả 26 lần quan sát) | [E-40, E-55, E-59] | Tài liệu 04 §2.4, §3.4, §4.3, §5; mục 8 của tài liệu này |
| Luồng phát hiện, điều tra, xử lý trọn vẹn | 30% | (1) Mỗi ca đi trọn vòng: tín hiệu, monitor, điều tra, quyết định qua guard, hành động hoặc từ chối, xác minh bằng MongoDB, đóng sự cố. (2) Trang `/incident` có hồ sơ 6 câu hỏi, liên kết Datadog và dòng thời gian từ aggregation. (3) Ca 2 có hai hồ sơ đầy đủ ngày 03/11 | [E-17, E-40, E-41] | Tài liệu 01 §5; Tài liệu 04 §1.2, §6 |

### 2.4 Trình bày (10%)

| Tiêu chí | Trọng số | Dự án đáp ứng thế nào | Bằng chứng | Vị trí trong hồ sơ |
|---|---|---|---|---|
| Chất lượng MVP | 10% | (1) Ứng dụng NiceGUI chạy trên EC2, trang `/incident` chỉ cho admin. (2) Bộ kiểm thử tự động đạt toàn bộ (số test ở Bảng 0). | [E-17, E-30] | Tài liệu 01 §4.6; Tài liệu 05 §5.1 |
| Tài liệu | 10% | (1) Năm tài liệu kỹ thuật cùng tài liệu này và danh mục bằng chứng. (2) Mỗi khẳng định có mã E và nhãn trạng thái. (3) Hạn chế được nêu ở mục riêng của từng tài liệu | `EVIDENCE_INDEX.md` | Mục 9 và mục 10 của tài liệu này |

## 3. Kiểm tra yêu cầu bắt buộc

### 3.1 MongoDB

| Yêu cầu | Đáp ứng | Cách dùng cụ thể | Bằng chứng | Trạng thái |
|---|---|---|---|---|
| MongoDB là nền tảng dữ liệu vận hành chính | Có | 16 collection: telemetry, hồ sơ sự cố, quyết định, sổ lệnh, lô, lịch, người dùng; dữ liệu người dùng và lịch tưới đã chuyển từ SQLite sang MongoDB (README [E-03]) | Tài liệu 02 front matter, §3.2 [E-12] | Đã kiểm chứng (mã); đối chiếu chỉ đọc 07/11 |
| Mô hình dữ liệu hợp lý | Có | Time Series cho mẫu đo; collection nhỏ cho vòng đời sự cố; nhúng mã tham chiếu ngắn, tham chiếu phần tăng theo thời gian | Tài liệu 02 §3.1 đến §3.5 [E-08, E-12] | Đã kiểm chứng (mã) |
| Truy cập hiệu quả | Có (thiết kế) | Chỉ mục ghép cho Q1, Q2; chỉ mục một phần cho Q3; một lần explain chọn chỉ mục, 101 khóa và 101 tài liệu duyệt; so sánh trước/sau đang bổ sung | Tài liệu 02 §5, Bảng 9.1 hàng 14 [E-25, E-85] | Một phần; đang bổ sung |
| Có Aggregation Pipeline | Có | `build_incident_timeline`: `$unionWith` bốn nhánh, `$setWindowFields`, `$shift`; `harvest_pipeline`: độ phủ và GDD | Tài liệu 02 §6 [E-16, E-18] | Đã kiểm chứng (mã) |
| Cách dùng gắn chặt với bài toán | Có | Aggregation trả lời "dữ liệu quanh sự cố còn đáng tin đến đâu"; chỉ mục một phần phục vụ truy vấn sự cố đang mở | Tài liệu 02 §7 [E-16] | Đã kiểm chứng (mã) |

### 3.2 Datadog

| Yêu cầu | Đáp ứng | Cách dùng cụ thể | Bằng chứng | Trạng thái |
|---|---|---|---|---|
| Ít nhất một dashboard | Có | `nkc-685-vw8` "SMIOT \| Farm Operations & Recovery", bộ lọc `farm`, 12 widget (8 ban đầu, 4 hạ tầng thêm ngày 06/11) | Tài liệu 03 §6 [E-52, E-72] | Đã kiểm chứng; ảnh sau cập nhật đang bổ sung |
| Ít nhất một monitor gắn rủi ro vận hành | Có | Sáu monitor SMIOT: flatline, dữ liệu cũ, phụ thuộc MongoDB, phụ thuộc MQTT, service inactive, status mismatch | Tài liệu 03 §4.1 [E-50, E-70] | Đã kiểm chứng (xuất cấu hình 06/11) |
| Ít nhất một năng lực bổ sung | Có (nhiều) | Logs, APM, LLM Observability, Workflow Automation, Private Action Runner, DBM, Agent systemd | Tài liệu 03 Bảng 0 [E-19, E-29, E-71] | Đã kiểm chứng (mã và cấu hình); ảnh LLM Observability: [E-84] |
| Kết nối metrics, logs, traces và bối cảnh vận hành | Có | `incident.id`, `farm.key`, `node.id` trong log và span; cùng `incident_id` với bản ghi MongoDB; truy vấn `@incident.id` trả 76 span và 10 log ở sự cố D3B0F8A7 | Tài liệu 03 §3.3, §7.1 [E-40] | Đã kiểm chứng (tài liệu hồ sơ) |
| Trình diễn trọn vẹn một tình huống | Có | Ca 2: từ T0 đến `recovered` ở hai hồ sơ ngày 03/11; Ca 3: dừng đến xác minh trong 418 s ngày 06/11 | Tài liệu 04 §3, §4 [E-40, E-41, E-59] | Đã kiểm chứng; Ca 3 đầu ra EC2 đang bổ sung |

## 4. MongoDB được dùng như thế nào

Vai trò: MongoDB lưu bằng chứng, đo tác động của sự cố lên dữ liệu và lô, và là nguồn xác minh phục hồi bằng dữ liệu đọc lại (Tài liệu 02, §7). MongoDB phụ trách hai trong sáu câu hỏi của hồ sơ sự cố: câu 4 (dữ liệu bị ảnh hưởng) và câu 6 (bằng chứng phục hồi).

Bảng 4.1. Tính năng MongoDB, mục đích và nơi đọc.

| Tính năng | Dùng để làm gì | Chi tiết cụ thể | Bằng chứng | Nơi đọc |
|---|---|---|---|---|
| Time Series `telemetry` | Lưu mẫu đo định kỳ 30 s | `timeField=timestamp`, `metaField=meta`, `granularity=seconds`; đối chiếu chỉ đọc 07/11 xác nhận là Time Series, khoảng 342.546 bản ghi ước tính | [E-08, E-80] | Tài liệu 02 §4 |
| Chiều `meta` | Lọc và phân hoạch | `farm_key`, `source_table`, `measurement_type`, `node_id`, `source`; `message_id` và `incident_id` nằm trong `source` để không tăng tổ hợp `meta` | [E-12, E-13] | Tài liệu 02 §4 |
| Chỉ mục ghép | Mẫu mới nhất theo node; mẫu quanh sự cố | `meta.farm_key, meta.measurement_type, meta.node_id, timestamp(-1)` | [E-12] | Tài liệu 02 §5.1 |
| Chỉ mục một phần `active_incident_by_scope` | Tìm sự cố đang mở theo kind, farm, node | Chỉ phủ `status` thuộc `open`, `holding`, `recovering`; sự cố `recovered` rời chỉ mục | [E-16] | Tài liệu 02 §5.2 |
| `$jsonSchema` | Kiểm tra cấu trúc hồ sơ | `operational_incidents`, `action_ledger`; `validationAction=warn`, `validationLevel=moderate`; hiệu lực trên máy chủ đang bổ sung | [E-16] | Tài liệu 02 §5.3 |
| Aggregation `$unionWith` | Hợp nhất dòng thời gian sự cố | Bốn nhánh: mẫu lỗi, quyết định, sổ lệnh, telemetry; một lần `aggregate` với `allowDiskUse`; cửa sổ từ lúc bắt đầu lỗi trừ 15 phút đến lúc phục hồi cộng 15 phút | [E-16] | Tài liệu 02 §6.1 |
| `$setWindowFields` và `$shift` | Đánh dấu khoảng thiếu mẫu | Phân hoạch theo `meta.node_id`; `gap_seconds` lớn hơn 3 × 30 thì thêm sự kiện `telemetry_gap`; khoảng thiếu cuối cửa sổ tính ở ứng dụng | [E-16] | Tài liệu 02 §6.2 |
| Aggregation độ phủ và GDD | Trang kế hoạch thu hoạch | `$setWindowFields`, `$group`; ngày đủ dữ liệu khi độ phủ từ 80%; GDD là chỉ số ngữ cảnh | [E-18] | Tài liệu 02 §6.3 |
| Hộp đen sự cố | Đo tác động | Giờ dữ liệu không đáng tin theo `kind`, lô bị ảnh hưởng theo hiệu lực gắn lô, số khoảng thiếu mẫu, quyết định tưới bị chặn | [E-16, E-17] | Tài liệu 02 §6.4 |
| `action_ledger` | Sổ lệnh HOLD và CLEAR | `command_id` làm `_id`; trạng thái `requested`, `published`, `acknowledged`, `verified` hoặc `failed`; bỏ bản tin phát lại | [E-21] | Tài liệu 02 §2 |
| Ghi lặp lại an toàn | Thay cho giao dịch | Upsert `$setOnInsert` theo `message_id`; quyết định có `_id` cố định `<incident_id>:irrigation-interlock` | [E-15, E-21] | Tài liệu 02 §2 |
| Sao lưu và khôi phục logic | Bảo vệ dữ liệu | `mongodump` cho collection thường, `mongoexport` cho Time Series; diễn tập 03/11: 154.618/154.618 mẫu và 1/1 sự cố | [E-28, E-42] | Tài liệu 02 §8 |
| Đối chiếu chỉ đọc 07/11 | Xác nhận cấu hình | Phiên bản 8.0.34, standalone; `operational_incidents` 7, `action_ledger` 25, `incident_telemetry_evidence` 241; một lần explain chọn chỉ mục (101 khóa, 101 tài liệu duyệt) | [E-80, E-85] | Tài liệu 02, Tóm tắt, Bảng 9.1 |

Số liệu ngày 07/11 do người dùng báo lại và chưa được tác giả tài liệu tái lập (Tài liệu 02, Tóm tắt). Kích thước lưu trữ, validator trên máy chủ và so sánh explain trước/sau đang bổ sung.

## 5. Datadog được dùng như thế nào

Vai trò: Datadog phát hiện và điều tra (phát hiện, nguyên nhân, workflow, log, trace). Ứng dụng không tự kết luận nguyên nhân mà điều hướng bằng liên kết sâu sang monitor, lượt chạy workflow, Logs và APM (Tài liệu 03, §6; Tài liệu 04, §1.3).

Bảng 5.1. Thành phần Datadog.

| Thành phần | Nội dung | Bằng chứng | Nơi đọc |
|---|---|---|---|
| Dashboard | `nkc-685-vw8`, 12 widget: telemetry (3), DBM MongoDB (2), phụ thuộc (2), SLO (1), EC2 (2), MongoDB (2). SLO được tạo ngày 03/11 và chưa đủ 7 ngày dữ liệu | [E-52, E-72] | Tài liệu 03 §6 |
| Monitor Ca 1 | `341409441` đo `status_mismatch`; đối chứng `339977703` đo tuổi mẫu lớn hơn 120 s | [E-50] | Tài liệu 03 §4.1, §4.2 |
| Monitor Ca 2 | `339977691` đo `sensor_flatline` trong 2 phút | [E-50] | Tài liệu 03 §4.1 |
| Monitor Ca 3 | `340356283` đo `systemd.unit.active` của `smiot.service`, trung bình 5 phút, ngưỡng nhỏ hơn hoặc bằng 0 | [E-50] | Tài liệu 03 §4.1 |
| Monitor phụ thuộc | `339990226` (MongoDB), `339990232` (MQTT) | [E-50] | Tài liệu 03 §4.1 |
| Workflow Automation | Ca 1: đọc hai metric tuổi mẫu rồi ghi `REFUSED_RESTART` hoặc `ESCALATE_HUMAN`, không gọi EC2. Ca 2: gọi có xác thực điểm cuối recovery của ứng dụng. Ca 3: chạy script guard qua Private Action Runner | [E-55, E-71] | Tài liệu 03 §5.1 |
| Private Action Runner | Chạy `recover-smiot-web` gọi guard; người dùng runner chỉ có hai lệnh sudo (`systemctl start smiot.service` và helper đọc lại MongoDB) | [E-24, E-43] | Tài liệu 03 §5.2 |
| Metric DogStatsD | `smiot.telemetry.*`, `smiot.dependency.*`; tag chỉ `farm`, `node`, `source` | [E-14, E-20] | Tài liệu 03 §3 |
| Probe ngoài app | `smiot.external.*`, timer 30 s; phục vụ điều tra | [E-23, E-57] | Tài liệu 03 §2.3 |
| Logs | Log JSON có `incident.id`, `farm.key`, `node.id`; log của guard `smiot.guarded_recovery` | [E-29, E-40] | Tài liệu 03 §2.2, §3.3 |
| APM | Span `smiot.*` mang `incident.id`; 76 span ở sự cố D3B0F8A7 | [E-40] | Tài liệu 03 §7.1 |
| LLM Observability | `ml_app=smiot-smart-farm`, nội dung vào và ra bị che, lỗi Datadog không làm gián đoạn lời gọi; span Gemini xuất hiện ngày 06/11 | [E-19, E-30] | Tài liệu 03 §8 |
| Agent systemd | Theo dõi sáu unit: `smiot`, `mongod`, `mosquitto`, `nginx`, `wokwi-bridge`, `datadog-agent` | [E-03] | Tài liệu 03 §2.1 |
| Database Monitoring | Bật cho MongoDB Community; người dùng giám sát chỉ đọc cộng `clusterMonitor` | [E-03] | Tài liệu 03 §2.1 |

## 6. Ba ca sự cố từ đầu đến cuối

Mốc thời gian lấy từ Tài liệu 04. Các khoảng thời gian là một lần quan sát, không phải số trung bình.

### 6.1 Ca 1 — Báo offline sai

| Giai đoạn | Nội dung | Bằng chứng |
|---|---|---|
| Phát sinh | Publisher đặt cache hiển thị cũ cho Node 1; dữ liệu cảm biến không đổi, mẫu vẫn vào MongoDB | [E-27, E-44] |
| Phát hiện | Watchdog so hiển thị với trạng thái tính từ MongoDB; `status_mismatch` bằng 1; monitor `341409441` Alert lúc 04:49:21Z (06/11) | [E-14, E-81] |
| Điều tra | Monitor đối chứng `339977703` cho biết dữ liệu còn tươi; log `smiot_status_mismatch` | [E-14, E-50] |
| Phản ứng | Workflow `e2835af0…` lượt `a782b12c…` lúc 04:50:21Z, Success, nhánh `REFUSED_RESTART`; không có lệnh restart | [E-81] |
| Chứng minh phục hồi | Hiển thị khớp trạng thái tính từ MongoDB; sự cố C581C638 ghi `recovered` lúc 04:54:56Z; monitor OK lúc 05:00:21Z. Số lần restart và đầu ra từng bước đang bổ sung | [E-81]; Tài liệu 04 §2.7 |

### 6.2 Ca 2 — Độ ẩm đất Node 2 đứng yên

| Giai đoạn | Nội dung | Bằng chứng |
|---|---|---|
| Phát sinh | Publisher gửi cố định 2,4%; hồ sơ BD19A22C mở sự cố lúc 11:43:21Z ngày 03/11 | [E-41] |
| Phát hiện | Monitor `339977691` Alert lúc 11:48:51Z, cách 330 s; mã hiện tại coi là flatline khi 10 mẫu liên tiếp chênh lệch nhỏ hơn hoặc bằng 0,01 trong cửa sổ 600 s | [E-14, E-41] |
| Điều tra | Logs và APM theo `@incident.id`; số thứ tự mẫu vẫn tăng; quyết định `BLOCKED_HOLD` chặn tưới | [E-40, E-41] |
| Phản ứng | HOLD được xác nhận lúc 11:49:59Z, bơm ảo OFF; CLEAR chỉ sau verifier | [E-41] |
| Chứng minh phục hồi | 7 mẫu mới 39,3–41,0%, monitor OK, ACK của PLC ảo, mọi bơm ảo OFF; CLEAR và `recovered` lúc 13:39:56Z | [E-41] |

Hồ sơ D3B0F8A7 (03/11) có 6 mẫu 39,5–40,6% và HOLD do cầu nối gửi; execution của workflow bị khử trùng lặp [E-40]. Lần diễn tập 06/11: Alert sau 311 s, monitor OK sau 206 s; bản ghi `recovered` đang bổ sung [E-56, E-86].

### 6.3 Ca 3 — `smiot.service` dừng

| Giai đoạn | Nội dung | Bằng chứng |
|---|---|---|
| Phát sinh | Operator dừng đúng một unit lúc 03:06:32Z (06/11); `mongod` và `mosquitto` active ở cả 26 lần quan sát | [E-59] |
| Phát hiện | Probe ngoài app mở sự cố `INC-SMIOT-20261106T030719-D1E0243D`; monitor `340356283` Alert lúc 03:11:43Z | [E-23, E-82] |
| Điều tra | HTTP 000, tuổi mẫu tăng từ 19 s đến 406,7 s; loại trừ dependency lỗi | [E-59] |
| Phản ứng | Workflow `b83453ff…` lượt `06cb1b46…` lúc 03:12:43Z chạy `recover-smiot-web` thành công; guard chỉ start `smiot.service` | [E-82, E-24] |
| Chứng minh phục hồi | Lúc 03:13:30Z unit active, HTTP 200, mẫu mới tuổi 6,6 s; 418 s từ dừng đến xác minh; sự cố D1E0243D `recovered` lúc 03:13:26Z | [E-59]; Tài liệu 04 §4.6 |

Đầu ra lệnh trên EC2 và log `smiot.guarded_recovery` ngày 06/11 đang bổ sung [E-82].

## 7. Điểm khác biệt và sáng tạo

### 7.1 So với cách giám sát thông thường

Bảng 7.1. Cách thông thường và cách SMIOT làm.

| Cách thông thường | Cách SMIOT làm | Bằng chứng |
|---|---|---|
| Có cảnh báo thì restart | Chọn phản ứng theo lớp lỗi; Ca 1 từ chối restart vì dữ liệu vẫn vào | [E-16, E-55] |
| Chỉ báo hạ tầng xanh là ổn | Đo cả độ tin cậy của dữ liệu: tuổi mẫu, độ biến thiên, lệch hiển thị | [E-14, E-23] |
| Lệnh chạy xong là đã khắc phục | Phục hồi chỉ được công nhận khi dữ liệu đọc lại từ MongoDB xác nhận | [E-22, E-24] |
| Mỗi công cụ một màn hình riêng | Một `incident_id` nối log, trace và MongoDB; trang `/incident` dẫn tới đúng monitor, workflow, logs | [E-15, E-17] |
| Tự động hóa có quyền rộng | Hành động duy nhất trên host là `systemctl start smiot.service`, allowlist hai lệnh, khóa chống chạy chồng, cooldown 300 s | [E-24, E-43] |

### 7.2 Các ý sáng tạo chính

| Ý | Nội dung | Bằng chứng | Nơi đọc |
|---|---|---|---|
| Chọn phản ứng theo lớp lỗi | Ba lớp, ba phản ứng; không dùng restart chung | [E-16] | Tài liệu 01 §1.3 |
| Từ chối restart khi dữ liệu vẫn vào | Ca 1: workflow chỉ ghi `REFUSED_RESTART`, không có đường tới EC2 | [E-55, E-81] | Tài liệu 04 §2.4 |
| HOLD trước, CLEAR chỉ sau verifier | Verifier đòi monitor OK, HOLD đã ACK, từ 10 mẫu bình thường, mẫu mới nhất không quá 90 s, biên độ từ 0,5, PLC ảo ACK và mọi bơm ảo OFF; không có đường từ HOLD sang NORMAL ngoài verifier | [E-22] | Tài liệu 04 §3.6; Tài liệu 01 §4.4 |
| Một mã `incident_id` xuyên hai hệ thống | Nối log và trace trên Datadog với bản ghi sự cố, sổ lệnh và mẫu trên MongoDB | [E-15, E-40] | Tài liệu 03 §3.3 |
| Phục hồi bằng dữ liệu đọc lại | Ca 2: mẫu biến thiên và ACK; Ca 3: HTTP 200 và mẫu MongoDB mới tuổi không quá 180 s | [E-22, E-24] | Tài liệu 01 §2 R4 |
| Chia vai | Datadog điều tra, MongoDB đo tác động, ứng dụng điều hướng | [E-17] | Tài liệu 04 §1.3 |
| Hành động nhỏ nhất | `start` thay cho `restart`; allowlist hai lệnh | [E-43] | Tài liệu 03 §5.2 |
| Cardinality thấp | `incident_id` ở log, trace, MongoDB; tag metric chỉ `farm`, `node`, `source` | [E-20] | Tài liệu 03 §3.2 |

## 8. Tác động vận hành

Giá trị rõ nhất của SMIOT là những quyết định sai mà hệ thống ngăn được và đường ngắn từ cảnh báo đến bằng chứng. Các giá trị dưới đây chỉ nêu những gì hồ sơ đã ghi; mỗi thời lượng là một lần quan sát trên dữ liệu tổng hợp.

| Giá trị | Dữ kiện trong hồ sơ | Bằng chứng |
|---|---|---|
| Tránh restart oan | Ca 1: mẫu vẫn đến MongoDB khi giao diện báo offline; lượt workflow ghi nhánh `REFUSED_RESTART`, không có lệnh restart | [E-55, E-81] |
| Tránh tưới theo số đo không đáng tin | Ca 2: số đo 2,4% thấp hơn 30%; ghi `BLOCKED_HOLD`, không gửi lệnh bơm; mọi bơm ảo OFF suốt ca | [E-40, E-41] |
| Giới hạn phạm vi gián đoạn ở một unit | Ca 3: chỉ `smiot.service` được start; `mongod` và `mosquitto` không bị restart | [E-59, E-43] |
| Đo phạm vi ảnh hưởng | Ca 3: ingest ngừng xấp xỉ 415 s (suy ra từ hai giá trị epoch mẫu); hộp đen đánh dấu khoảng thiếu khi vượt 3 lần chu kỳ 30 s | [E-16, E-59] |
| Rút ngắn đường từ cảnh báo đến bằng chứng | `/incident` gom hồ sơ 6 câu hỏi, liên kết monitor, workflow, execution, logs, APM và dòng thời gian trên một trang | [E-17] |
| Khôi phục dữ liệu sao lưu | Diễn tập 03/11: 154.618/154.618 mẫu và 1/1 sự cố | [E-42] |

Thời lượng một lần quan sát (Tài liệu 04, Bảng 5.2): số đo đứng yên 6804 s (BD19A22C), 393 s (D3B0F8A7), 421 s (Ca 2, 06/11); Ca 3 ingest ngừng xấp xỉ 415 s. Các số này không phải chỉ số hiệu năng tổng quát; SLO được tạo ngày 03/11 và chưa đủ 7 ngày dữ liệu.

## 9. Chất lượng MVP và tài liệu

| Hạng mục | Nội dung | Bằng chứng | Trạng thái |
|---|---|---|---|
| Hồ sơ nộp | Tài liệu 01 kiến trúc giải pháp; 02 dữ liệu MongoDB; 03 observability Datadog; 04 mô tả sự cố; 05 use case; 06 tài liệu này; `EVIDENCE_INDEX.md` | `docs/submission/` | Bản nháp |
| Trang `/incident` | Danh sách ba thẻ Ca 1/2/3, chi tiết sự cố, hồ sơ 6 câu hỏi, liên kết Datadog; chỉ admin hoặc quyền `manage_users`; ảnh đang bổ sung | [E-17, E-83] | Mã đã kiểm chứng |
| Dashboard | `nkc-685-vw8`, 12 widget; trang `/chart` điều hướng sang Datadog | [E-52, E-72] | Ảnh sau cập nhật đang bổ sung |
| Kiểm thử | 162 test đạt, 17 tệp, chạy local 06/11/2026 | [E-30] | Đã kiểm chứng |
| Use case | 24 use case đã đặc tả: 19 có nguồn mã đã đối chiếu, 3 đang bổ sung, 2 đang bổ sung xác nhận | Tài liệu 05, Tóm tắt | Bản nháp |
| README | Phần "Trạng thái hiện tại" ghi phiên bản MongoDB và DBM | [E-03] | Đã kiểm chứng (nội dung tài liệu) |
| Tài khoản giám khảo cho `/incident` | đang bổ sung | Tài liệu 04 A-1 | Đang bổ sung |
| Khai báo | Công cụ AI và thành phần có từ trước 17/10: xem Phụ lục khai báo trong Tài liệu 01 và `docs/DECLARATIONS.md` | [E-02] | Đang bổ sung |

## 10. Phạm vi và giới hạn

1. **Dữ liệu tổng hợp và PLC ảo.** Số đo đến từ publisher demo hoặc cầu nối Wokwi; bơm là PLC ảo; hệ thống không điều khiển thiết bị vật lý. Kết quả không suy ra cho thiết bị hay cây trồng vật lý [E-02, E-13].
2. **Một EC2.** Ứng dụng, MongoDB, Mosquitto và Agent chung một miền lỗi; thiết kế xử lý lỗi ở mức tiến trình, không ở mức máy [E-03].
3. **MongoDB standalone.** Không dùng giao dịch đa tài liệu và cơ chế theo dõi thay đổi của MongoDB; phát hiện dựa trên watchdog và probe định kỳ 30 s; không dùng dịch vụ quản lý trên đám mây của nhà cung cấp [E-80].
4. **Validator.** Chế độ cảnh báo, hiệu lực trên máy chủ đang bổ sung (Tài liệu 02 §5.3).
5. **SLO.** SLO được tạo ngày 03/11 và chưa đủ 7 ngày dữ liệu [E-03].
6. **Quan sát đơn lẻ.** Các thời lượng 311 s, 206 s, 418 s, 415 s là một lần quan sát.
7. **Mức bằng chứng theo ca.** Ca 2 có hai hồ sơ đầy đủ; Ca 3 có tác nhân khởi động là workflow, đầu ra lệnh trên EC2 đang bổ sung [E-82]; Ca 1 có một lượt chạy, đầu ra từng bước đang bổ sung [E-81].
8. **Phạm vi farm.** Dữ liệu hiện có cho Greenhouse A; Greenhouse B đến D nằm ngoài phạm vi hiện tại (Tài liệu 05, N6).
9. **Số liệu quan sát phiên làm việc 06/11.** Mã sự cố và mốc mở, đóng chờ người dùng xác nhận trên `/incident` và Datadog (Tài liệu 04 §8).
10. **Trợ lý AI.** Nguồn publish topic `farm/ai` nằm ngoài repo hiện tại (Tài liệu 01 §8).

## 11. Bản đồ tìm nhanh và câu hỏi thường gặp

### 11.1 Muốn biết X thì đọc ở đâu

| Muốn biết | Đọc |
|---|---|
| Bài toán, ba lớp lỗi | Tài liệu 01 §1.3; Tài liệu 05 Mục đích hệ thống |
| Kiến trúc tổng thể, luồng ingest | Tài liệu 01 §3, §4.2 |
| Nguyên tắc thiết kế R1 đến R6 | Tài liệu 01 §2 |
| Mô hình dữ liệu, ER, collection | Tài liệu 02 §3 |
| Time Series và chỉ mục | Tài liệu 02 §4, §5 |
| Aggregation hộp đen | Tài liệu 02 §6.1, §6.2 |
| Tác động và lô bị ảnh hưởng | Tài liệu 02 §6.4 |
| Sao lưu và khôi phục | Tài liệu 02 §8 |
| Danh sách metric, tag | Tài liệu 03 §3 |
| Sáu monitor và query | Tài liệu 03 §4.1 |
| Workflow, guard, allowlist | Tài liệu 03 §5 |
| Cây quyết định từng ca | Tài liệu 03 §5A |
| Dashboard | Tài liệu 03 §6 |
| Điều tra theo `incident_id` | Tài liệu 03 §3.3, §7 |
| LLM Observability | Tài liệu 03 §8 |
| Dòng thời gian từng ca | Tài liệu 04 §2.7, §3.7, §4.7 |
| Sáu câu hỏi từng ca | Tài liệu 04 §2.8, §3.8, §4.8 |
| So sánh ba ca | Tài liệu 04 §5 |
| Trang `/incident` | Tài liệu 04 §6; Tài liệu 01 §4.6 |
| Use case, tác nhân, truy vết test | Tài liệu 05 §1, §3, §5 |
| Mã bằng chứng | `EVIDENCE_INDEX.md` |
| Mục còn đang bổ sung | Tài liệu 01 Phụ lục C; 02 Phụ lục C; 03 Phụ lục B; 04 Phụ lục A; 05 Phụ lục A |

### 11.2 Câu hỏi giám khảo thường hỏi

| Câu hỏi | Trả lời ngắn | Bằng chứng và nơi đọc |
|---|---|---|
| Dữ liệu là thật hay mô phỏng? | Tổng hợp (Wokwi hoặc bộ phát mô phỏng); bơm là PLC ảo; nhãn trong từng document | [E-02, E-13]; Tài liệu 02 §4 |
| MongoDB giữ vai trò gì? | Nền tảng dữ liệu vận hành chính: Time Series, hồ sơ sự cố, sổ lệnh; đo tác động và xác minh phục hồi | Tài liệu 02 §7 |
| Aggregation Pipeline ở đâu? | `build_incident_timeline` với `$unionWith` bốn nhánh và `$setWindowFields`/`$shift`; `harvest_pipeline` | [E-16, E-18]; Tài liệu 02 §6 |
| Vì sao dùng Time Series? | Mẫu đo chỉ thêm vào cuối, đọc theo khoảng thời gian và theo node | Tài liệu 02 §1.1, §4 |
| Có chỉ mục nào đặc thù? | Chỉ mục một phần `active_incident_by_scope` cho sự cố `open`, `holding`, `recovering`; lợi ích chưa đo | [E-16]; Tài liệu 02 §5.2 |
| Có dùng giao dịch hoặc theo dõi thay đổi không? | Không; MongoDB standalone; ghi lặp lại an toàn bằng `command_id` | [E-21]; Tài liệu 02 §2 |
| Datadog phát hiện thế nào? | Sáu monitor trên metric DogStatsD, `systemd.unit.active` và probe | [E-50]; Tài liệu 03 §4.1 |
| Dashboard và monitor có ID nào? | Dashboard `nkc-685-vw8`; monitor 339977691, 339977703, 339990226, 339990232, 340356283, 341409441 | [E-70, E-72] |
| Metrics, logs, traces nối với nhau ra sao? | Khóa `@incident.id`, `@farm.key`, `@node.id` và trace ID; cùng `incident_id` với MongoDB | Tài liệu 03 §3.3, §7.1 |
| Vì sao Ca 1 không restart? | Mẫu vẫn đến MongoDB; restart xóa phiên và bằng chứng mà không đổi dữ liệu | [E-55]; Tài liệu 04 §2.4 |
| Làm sao biết đã phục hồi? | Ca 2: mẫu biến thiên mới và ACK PLC ảo; Ca 3: unit active, HTTP 200, mẫu mới tuổi không quá 180 s | [E-22, E-24]; Tài liệu 04 §3.6, §4.6 |
| Hành động tự động nào chạy trên host? | Chỉ `systemctl start smiot.service` sau guard; không restart | [E-43]; Tài liệu 03 §5.2 |
| Ca nào có bằng chứng đầy đủ nhất? | Ca 2, hai hồ sơ ngày 03/11 | [E-40, E-41] |
| Phần nào đang bổ sung? | ảnh `/incident`, đầu ra EC2 Ca 3, `recovered` Ca 2 ngày 06/11, kích thước lưu trữ MongoDB | Mục 9; các Phụ lục |
| Công cụ AI và thành phần có từ trước 17/10? | Xem Phụ lục khai báo trong Tài liệu 01 và `docs/DECLARATIONS.md` (đang bổ sung) | Tài liệu 01 Phụ lục A, B |

## 12. Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| Ca 1, Ca 2, Ca 3 | Ba tình huống diễn tập: báo offline sai; độ ẩm đất Node 2 đứng yên; `smiot.service` dừng |
| `kind` | Loại sự cố trong mã: `false_offline`, `soil_humidity_flatline`, `service_down` |
| HOLD | Lệnh giữ trạng thái an toàn trên PLC ảo: mọi đầu ra bơm ảo ở OFF |
| CLEAR | Lệnh gỡ trạng thái an toàn; chỉ gửi sau khi verifier đạt |
| Verifier | Bộ xác minh phục hồi `verify_and_clear_demo_safe_mode.py`, kiểm điều kiện rồi mới CLEAR |
| Guard | Script `smiot-recover-guarded.sh` trên host: kiểm trước, start đúng một unit, xác minh sau |
| Hộp đen sự cố | Aggregation MongoDB hợp nhất mốc, mẫu lỗi, quyết định, lệnh và telemetry thành dòng thời gian |
| Flatline | Số đo đứng yên: 10 mẫu liên tiếp, chênh lệch nhỏ hơn hoặc bằng 0,01, cửa sổ tối thiểu 600 s (mã hiện tại) |
| Probe ngoài app | Tiến trình độc lập, timer 30 s, phát `smiot.external.*` khi app dừng |
| PLC ảo | Bộ điều khiển mô phỏng trong ứng dụng; không điều khiển thiết bị vật lý |
| `incident_id` | Mã sự cố `INC-SMIOT-<UTC>-<8HEX>` |
| `action_ledger` | Sổ lệnh HOLD và CLEAR theo `command_id` |
| Private Action Runner | Thành phần Datadog chạy script định nghĩa trước trên host |
| Dữ liệu tổng hợp | Dữ liệu do bộ phát mô phỏng hoặc luồng Wokwi tạo, có nhãn `source.synthetic` |
| «ĐANG BỔ SUNG» | Mục đang bổ sung bằng chứng hoặc thông tin |
