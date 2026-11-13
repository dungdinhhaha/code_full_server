# Quyết định định vị hồ sơ v2

Nguồn: `outputs/nop_bai_v2/00_fact_sheet.md` (số mục ghi trong ngoặc là mục của fact sheet).

## 1. Kết luận

SMIOT đáp ứng đề bài mở: có. Bài toán tự chọn là vận hành 10 nhà màng dưa lưới ảo (mục 1). MongoDB là nền dữ liệu vận hành và bằng chứng (mục 3). Datadog quan sát, phát hiện và điều phối xử lý (mục 2.2, 4).

Bằng chứng theo mục:
- Bài toán và ba pha: mục 1 (10 nhà màng; phát hiện, điều tra, phản ứng).
- MongoDB: mục 3.1 (26 tên collection trong mã, gồm operational_incidents, findings, action_ledger, telemetry), 3.2 (index partial, unique, TTL), 3.4 (hộp đen sự cố dùng `$unionWith` 7 nhánh và `$setWindowFields`).
- Datadog: mục 4.1 (5 dashboard SMIOT live), 4.2 (19 monitor SMIOT live), 4.3 (10 workflow SMIOT published), 4.4 (DogStatsD, `smiot.*`), 4.5 (APM, span tùy chỉnh, log, LLM Observability có điều kiện).
- Phản ứng có kiểm chứng: mục 2.2 (lệnh MQTT có ACK, khôi phục có guard, xác minh health + MongoDB + MQTT + telemetry mới).
- 10 ca sự cố được giám sát: Ca 1-3, W1, W5-W10 (mục 4.2, 4.3, 5.3).

Định vị chung: Datadog là trung tâm của ba pha; MongoDB giữ dữ liệu và bằng chứng; ứng dụng điều hướng, giữ khóa an toàn cục bộ và hiển thị hồ sơ.

## 2. Vai trò từng thành phần theo ba pha

### Phát hiện
- Datadog: monitor trên metric `smiot.*` do DogStatsD gửi (ví dụ flatline, telemetry not fresh, ingest lag, status mismatch, `smiot.service inactive`, W1, W6, W9) xác định điều bất thường trước người dùng (mục 4.2, 4.4). Dashboard "Incident & Recovery" và "IoT & MQTT Fleet" cho cái nhìn tổng quan (mục 4.1).
- MongoDB: lưu mẫu telemetry và `findings` từ watchdog; là nguồn dữ liệu mà các chỉ số tươi/trễ/thiếu mẫu được tính từ đó (mục 2.2, 3.1).
- Ứng dụng: watchdog, kiểm tra trình tự và heartbeat detector phát metric; mở hồ sơ sự cố khi có phát hiện (mục 2.2).

### Điều tra
- Datadog: nối metric, log (có `incident_id`, qua Agent đọc file), trace (span `mqtt.message.process`, `smiot.ai.tool`, `DD_LOGS_INJECTION`) và bối cảnh monitor/workflow quanh cùng một correlation ID (mục 4.5, 2.2). Workflow chạy bước kiểm tra bằng chứng (ví dụ W1, W5, W7, W8) (mục 4.3).
- MongoDB: hộp đen sự cố dựng dòng thời gian từ 7 nhánh (telemetry, findings, action_ledger, operational_decisions, bằng chứng, sự kiện/quan sát kịch bản) và đánh dấu khoảng thiếu mẫu (mục 3.4).
- Ứng dụng: trang `/incident/{id}` (admin) gom hồ sơ MongoDB với liên kết và đọc lại sự kiện/log Datadog qua `datadog_reader.py` (mục 2.1, 4.5; đường đọc trong app chưa được gọi thử, xem mục 5 dưới).

### Phản ứng
- Datadog: monitor kích hoạt workflow có guard (Ca 1 từ chối khởi động lại khi mẫu còn tươi; Ca 2 xác nhận interlock cục bộ; Guarded EC2 app recovery cho `smiot.service`); monitor trở về OK là tín hiệu phục hồi từ phía Datadog (mục 4.3, 5.3).
- MongoDB: `action_ledger` ghi lệnh (requested, published, acknowledged, verified); readback sau khôi phục đối chiếu mẫu mới (mục 3.1, 2.2).
- Ứng dụng: thực thi lệnh MQTT có ACK và khôi phục có guard (token, khóa, cooldown, allowlist); xác minh bằng health + MongoDB + MQTT + telemetry mới; thông báo vào chuông qua `POST /api/integrations/datadog/notification` (mục 2.2, 6.1).

## 3. Thứ tự nhấn mạnh theo file

Ghi chú: fact sheet chỉ nêu `docs/submission/01-06` và `EVIDENCE_INDEX`; tên file 01-07 của bộ v2 cần đối chiếu bằng tay trước khi áp dụng. Thứ tự dưới đây theo vai trò nội dung.

Nguyên tắc chung cho mọi file: câu mở đầu mỗi phần nêu việc Datadog làm, sau đó MongoDB (dữ liệu, bằng chứng), sau đó ứng dụng.

- 01 (bài toán/tổng quan): mở bằng đề bài mở và bài toán đã chọn; nêu ngay mô hình ba pha với Datadog ở vị trí trung tâm; MongoDB và ứng dụng ở dòng tiếp theo. Cần đổi vai trò mô tả: nếu hiện mở bằng ứng dụng NiceGUI hoặc MongoDB, chuyển sang Datadog trước.
- 02 (kiến trúc): sơ đồ luồng dữ liệu đặt Datadog (metric, log, trace, monitor, workflow) thành trục giữa; MongoDB là kho dữ liệu vận hành và bằng chứng; ứng dụng là lớp điều hướng và khóa an toàn cục bộ. Cần đổi vai trò mô tả: bỏ cách gọi MongoDB là "trung tâm" nếu có. Số nhánh `$unionWith` ghi 7.
- 03 (Datadog): trình bày theo ba pha thay vì theo loại tài nguyên; mỗi pha nêu monitor, log/trace/metric, workflow, dashboard liên quan bằng ID live (mục 4). Cần đổi vai trò mô tả: đây là file trọng tâm; ID dùng danh sách live 13/11.
- 04 (mô tả sự cố vận hành): mỗi ca viết theo trình tự Datadog phát hiện, Datadog cùng MongoDB điều tra, workflow và ứng dụng phản ứng, Datadog xác nhận về OK. Ca 1-3, W1, W5-W10 là 10 ca sự cố được giám sát. Kịch bản A1, A2, A3, A4, C10, S2, S3, C2 chỉ dùng cho demo trực tiếp, không viết như ca.
- 05 (kiểm chứng/kiểm thử): bằng chứng lấy từ trạng thái monitor, log, trace trước rồi mới đến dữ liệu MongoDB; số test đạt ghi theo nguồn và ngày.
- 06 (tổng quan/đối chiếu tiêu chí): khớp từng tiêu chí với ba pha; mỗi dòng nêu thành phần Datadog trước.
- 07: chưa có thông tin trong fact sheet; áp dụng nguyên tắc chung. Nếu là danh mục bằng chứng, sắp theo ba pha và đặt bằng chứng Datadog trước bằng chứng MongoDB.

## 4. Việc cần sửa

1. Đổi vai trò mô tả ở 01, 02, 03 như mục 3 (Datadog là trung tâm; MongoDB là nền dữ liệu và bằng chứng; ứng dụng điều hướng).
2. Dùng ID monitor và workflow live 13/11 (mục 4.2, 4.3); không dùng ID tài liệu 06/11 và snapshot 08/11 (mục 8.1).
3. Đồng bộ số liệu: `$unionWith` 7 nhánh; số widget theo file dashboard (5-7 mỗi dashboard); tên monitor Ca 1 là `telemetry status mismatch` (mục 8.2).
4. Với kịch bản dùng cho demo trực tiếp, gọi là "kịch bản diễn tập"; giữ chữ "ca" cho 10 ca sự cố được giám sát. Không nêu số liệu diễn tập như ngưỡng đã duyệt (mục 5.2).
5. Với SLO và dữ liệu chưa đủ kỳ, dùng cách nói "đang bổ sung", "chưa đủ 7 ngày", đúng giọng trung tính đã chốt.
6. Xử lý token trong file snapshot `docs/datadog_config_snapshot/20261108T150159Z/json/workflows/18d1b008-...json` trước khi nộp bất cứ thứ gì kèm snapshot (mục 6.2.1); quyết định thuộc người dùng.
7. Không nêu tên cuộc thi trong bất kỳ file nào; rà lại cả tên file đính kèm.

## 5. Điều không khẳng định

Không khẳng định các điểm sau vì fact sheet chưa đủ bằng chứng:
- Time Series, index thật, validator `$jsonSchema`, topology/replica set trên MongoDB sống (mục 3.2, 3.3, 3.5, 9).
- Số widget thật của dashboard live; nội dung query và ngưỡng từng monitor live (mục 4.1, 9).
- Phục hồi Ca 2 (kết quả một phần, E-56); đầu ra lệnh EC2 của Ca 3 (E-82); kết quả W3, W5, W6, W9, W10 trên live ngoài ghi chép PROGRESS (mục 8.3, 8.4, 9).
- Đường đọc Datadog trong app (events/logs API) đang chạy ổn định; quyền `logs_read_data`, `events_read` (mục 4.5, 9).
- Số test đạt (281, 162) còn pass: chưa chạy lại (mục 7, 9).
- Mọi số liệu diễn tập (độ trễ phát hiện, thời gian phục hồi) là một lần chạy, không phải ngưỡng; S2 và C2 không thấy Alert; A1 và A4 ngày 13/11 không có Alert (mục 5.2).
- Phần cứng vật lý: dữ liệu và thiết bị là ảo hoặc mô phỏng; không nói là đo thực tế.
- Bot Telegram, Gemini, Open-Meteo hoạt động trên EC2; cấu hình broker MQTT (mục 9).
- 78 tên `smiot.*` đều là metric: chưa phân loại; chỉ nêu 19 metric gọi trực tiếp trong `datadog_metrics.py` (mục 4.4).
- Tên và nội dung các file 01-07 của bộ v2: ngoài phạm vi fact sheet.
