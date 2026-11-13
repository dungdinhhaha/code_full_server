# Brief Writer B — Tài liệu 02: Kiến trúc dữ liệu và data model trên MongoDB

Bạn là writer kỹ thuật cho dự án SMIOT Smart Farm dự thi Mini Hackathon MongoDB x Datadog. Repo: `D:\IOT Trung\code_full_server` (Windows, PowerShell; Python `py -3.12 -X utf8`). Viết tiếng Việt, văn phong báo cáo khoa học.

## 1. Phạm vi quyền
- **Được tạo/sửa đúng một tệp:** `docs/submission/02_kien_truc_du_lieu_mongodb.md`.
- **Không** sửa tệp khác, không commit git, không kết nối MongoDB/EC2/Datadog (kể cả MCP MongoDB), không đọc `.env`/`/etc/smiot/*`, không in URI/secret.
- Không ghi IP, account AWS, instance ID, tên bucket, org ID, email.
- Số liệu sống (đếm, kích thước, index thật, explain) **chưa có**: dùng placeholder «CẦN NGƯỜI DÙNG: kết quả lệnh H.2-x» và ghi lệnh tương ứng trong Phụ lục. Không ước lượng.

## 2. Đọc trước
1. `docs/submission/00_PLAN.md` §0 (F1–F22, M1–M12), §C.2, §D, §E, §H.2.
2. `docs/submission/EVIDENCE_INDEX.md`.
3. `docs/MONGODB_BACKUP_RESTORE_DRILL_20261103.md`; `docs/DECLARATIONS.md` §1, §5.
4. `docs/INC-SMIOT-20261103T102822-D3B0F8A7_EVIDENCE.md` (danh sách collection liên quan sự cố).
5. `README.md` dòng 6–37 (DBM, `collect_schemas` tắt). **Không** trích các đoạn lịch sử nhắc Atlas (dòng ~53, ~111).
- Không chép mẫu document trong `outputs/20261104_smiot_story_pack/Kien_truc_giai_phap_MongoDB_Datadog.md` (sai tên trường, M1).

## 3. Kiểm trong mã trước khi viết
| Cần kiểm | Ở đâu |
|---|---|
| Tạo Time Series (`timeField`, `metaField`, `granularity`) | `scripts/migrate_sqlite_telemetry_to_mongodb.py:115-135` |
| Hình dạng document telemetry | `service/auth.py:291-304` (`_telemetry_doc`), `service/mongodb_telemetry.py:93-105`, `service/telemetry_provenance.py:91-104`, `service/mqtt.py:380-460` (khóa trong `readings`, ví dụ `soil_hum`) |
| Lọc seed lịch sử `source.demo_seed_version` | `service/auth.py:305-308`, `service/incident_blackbox.py:32, 249` |
| Index nghiệp vụ | `service/auth.py:71-98` |
| Index/validator hộp đen | `service/incident_blackbox.py:39-148` |
| Pipeline hộp đen | `service/incident_blackbox.py:170-300` và hàm `build_timeline_pipeline`, `build_incident_timeline` (đọc tiếp sau dòng 292) |
| Vòng đời sự cố, `lot_sensor_assignments` | `service/incident_lifecycle.py:24-95, 117-175, 311-370` |
| Sổ hành động, idempotency `command_id` | `service/operational_evidence.py` |
| Aggregation GDD/độ phủ | `service/mongodb_showcase.py:20-180`; `scripts/gdd_forecast.py:80-100`; `scripts/telemetry_quality_report.py:40-90` |
| Explain và benchmark (chỉ đọc) | `scripts/explain_before_after.py`; `scripts/mongo_timeseries_benchmark.py` |
| Backup Time Series | `scripts/aws/mongodb_backup.sh`; `scripts/aws/mongodb_restore_drill.sh` |
| Ảnh: S3 + metadata | `crop_stage_media` trong `service/auth.py:82-83`; tìm nơi ghi bằng Grep `crop_stage_media` |
| Xác nhận không có transaction/change stream | Grep `\.watch\(|start_session|with_transaction` trong `service/`, `pages/`, `scripts/` |
Nếu mã khác `00_PLAN.md`, theo mã và báo cáo.

## 4. Front matter
```yaml
---
doc_id: SMIOT-SUB-02
title: "Kiến trúc dữ liệu và mô hình dữ liệu trên MongoDB"
submission_section: 4
project: "SMIOT Smart Farm"
competition: "Mini Hackathon MongoDB x Datadog 2026"
version: "0.9-draft"
date: "2026-11-0X"
language: vi
data_label: synthetic
mongodb: {edition: "Community", version: "8.0.x (CẦN NGƯỜI DÙNG xác nhận)", deployment: "self-managed, standalone, EC2", transactions: false, change_streams: false}
features_used: [time_series_collection, compound_index, partial_index, jsonschema_validator_warn, aggregation_unionWith, aggregation_setWindowFields, logical_backup_restore]
collections: [telemetry, operational_incidents, incident_telemetry_evidence, operational_decisions, action_ledger, lot_sensor_assignments, crop_cycles, traceability_events, crop_stage_media, schedules, schedule_logs, notifications, users]
evidence_index: "EVIDENCE_INDEX.md"
related_docs: [SMIOT-SUB-01, SMIOT-SUB-03, SMIOT-SUB-04]
reading_order: [SMIOT-SUB-01, SMIOT-SUB-04, SMIOT-SUB-02, SMIOT-SUB-03]
status: draft
---
```
Chỉ giữ trong `collections` những collection có trong mã; bổ sung nếu Grep thấy thêm.

## 5. Dàn ý (5.000–6.500 từ), giữ nguyên số chương
- **Tóm tắt** (≤ 200 từ). **Đóng góp chính** (5 gạch, theo `00_PLAN.md` §C.2, mỗi gạch `[E-xx]`).
- **Bảng 0. Đọc nhanh:** phiên bản/chế độ; collection chính; tính năng dùng; lý do chọn; thứ tự đọc.
- **1 Đặt vấn đề dữ liệu.** 1.1 Hai loại dữ liệu và đặc tính ghi/đọc; 1.2 Bảng 1.1 câu hỏi truy vấn Q1–Q5 (Q1 mẫu mới nhất theo farm/node; Q2 mẫu trong cửa sổ quanh sự cố; Q3 sự cố đang mở theo phạm vi; Q4 timeline hợp nhất một sự cố; Q5 độ phủ/GDD theo ngày) → mỗi câu ánh xạ index/pipeline ở §5–§6.
- **2 Triển khai và hệ quả thiết kế.** Community self-managed standalone trên EC2 cùng app. Hệ quả: (a) không transaction đa document → ghi theo máy trạng thái (`requested → published → acknowledged → verified/failed`) và khóa `command_id` để lặp lại an toàn; (b) không change stream → watchdog định kỳ và probe ngoài app; (c) chung failure domain → backup logic ra S3.
- **3 Data model.** 3.1 Hình 3.1 `erDiagram` (telemetry ↔ operational_incidents qua farm_key/node_id + cửa sổ thời gian; incident 1–n evidence, decisions, action_ledger; lot_sensor_assignments nối lô–node theo `valid_from/valid_to`; crop_cycles, traceability_events, crop_stage_media theo lô). Đoạn mô tả bằng chữ. 3.2 Bảng 3.1 collection: mục đích; trường khóa; trường chính; nơi ghi (`file:dòng`); truy vấn chính. 3.3 Document mẫu `telemetry` và `operational_incidents`: dựng **theo mã** (ghi chú "minh họa theo mã, giá trị tổng hợp"), sau thay bằng kết quả H.2 khi có. 3.4 Nhúng vs tham chiếu (ví dụ: mẫu lỗi lưu ở `incident_telemetry_evidence` thay vì nhúng mảng lớn trong incident). 3.5 Gắn lô theo hiệu lực thời gian; không gán lô khi phạm vi không khớp.
- **4 Time Series `telemetry`.** Tùy chọn (F8); chiều `meta` (farm_key, node_id, measurement_type, source_table, source); index phụ trên `meta` + `timestamp`; index `source.incident_id` có nhánh dự phòng; hệ quả backup (bucket nội bộ → dùng `mongoexport` logic) [E-42]; nhãn tổng hợp `source.synthetic`.
- **5 Chỉ mục và ràng buộc.** 5.1 Bảng 5.1 index (collection, khóa, loại, phục vụ Q nào, nguồn `file:dòng`); 5.2 Partial index `active_incident_by_scope`; 5.3 `$jsonSchema` cho `operational_incidents`, `action_ledger` với `validationAction=warn`, `validationLevel=moderate` — lý do và đánh đổi; 5.4 Explain trước/sau: bảng trống với «CẦN NGƯỜI DÙNG: E-85» + mô tả phương pháp (dry-run mặc định, `executionStats`, so `COLLSCAN`/`IXSCAN`, `totalDocsExamined`).
- **6 Aggregation.** 6.1 Hộp đen (Hình 6.1 flowchart: `operational_incidents` [$match → $project mốc → $unwind] → `$unionWith` evidence → decisions → action_ledger (unwind chuyển trạng thái) → telemetry (window); Bảng 6.1 từng stage và mục đích); 6.2 Khoảng thiếu mẫu: `prev_ts = $shift(by −1)` theo `meta.node_id`, `gap_seconds = (timestamp − prev_ts)/1000`, `is_gap = gap_seconds > 3 × 30`; 6.3 Độ phủ và GDD (`service/mongodb_showcase.py`): quy tắc ngày đủ dữ liệu, `GDD_ngày = max(0, T_tb − 10)`, trượt 7 ngày; nêu rõ chưa hiệu chuẩn nông học; 6.4 Truy vấn tác động: lô bị ảnh hưởng, số giờ dữ liệu không đáng tin, đề xuất tưới bị chặn (`operational_decisions`, `BLOCKED_HOLD` [E-40]).
- **7 MongoDB trong luồng sự cố.** MongoDB trả lời câu 4 (phạm vi ảnh hưởng) và câu 6 (bằng chứng phục hồi: mẫu mới sau mốc X; verifier đọc ≥ 10 mẫu tươi theo mã hiện tại [E-22]; probe/guard đọc tuổi mẫu mới nhất [E-23, E-24]). Trỏ Tài liệu 04 cho từng ca.
- **8 Vận hành dữ liệu.** Backup logic + restore drill 154.618/154.618 và 1/1 [E-42]; quyền tối thiểu (user đọc cho giám sát; không cấp quyền bucket nội bộ; tắt thu schema DBM) [E-03, E-42]; Database Monitoring (chi tiết ở Tài liệu 03).
- **9 Đánh giá.** Bảng 9.1 số đo (phiên bản, standalone, số bản ghi từng collection, kích thước, số index, explain) — ô trống = «CẦN NGƯỜI DÙNG: H.2-x»; Bảng 9.2 Tuyên bố – Bằng chứng – Trạng thái (≥ 12 dòng).
- **10 Hạn chế và phạm vi.** Standalone, một EC2; validator chỉ cảnh báo; benchmark chưa có kết quả gốc; chưa PITR/EBS restore; dữ liệu tổng hợp; GDD chưa hiệu chuẩn; một câu duy nhất: không dùng dịch vụ Atlas (Search, Vector Search, Triggers, Charts, Stream Processing), không dùng change stream và transaction.
- **11 Kết luận.**
- **Phụ lục A.** Lệnh chỉ-đọc (sao từ `00_PLAN.md` §H.2, đánh số H.2-1…H.2-n) và cột "Kết quả" để trống. **Phụ lục B.** Tham chiếu tài liệu MongoDB chính thức (Time Series, `$setWindowFields`, `$unionWith`, partial index, schema validation).

## 6. Điểm hay phải làm nổi bật (chỉ khi đã kiểm trong mã)
1. Một aggregation hợp nhất 5 nguồn thành timeline [E-16].
2. Khoảng thiếu mẫu tính trong DB bằng window function [E-16].
3. Partial index cho sự cố đang mở [E-16].
4. Validator chế độ cảnh báo không chặn ghi [E-16].
5. Backup Time Series qua đường logic + restore đếm khớp [E-42].

## 7. Danh sách cấm (nguyên văn từ người dùng)
Không tuyên bố Atlas Search/Vector Search/Triggers/Charts/Stream Processing; không tuyên bố Change Streams; không đưa MTTD/MTTR/% giảm cảnh báo/SLO đạt khi chưa có nguồn đo; không nói thiết bị vật lý hỏng/đã sửa; không coi dữ liệu tổng hợp là dữ liệu thật; không nói "tự động khắc phục" nếu bước thực hiện là thủ công; không nói Bits AI xác nhận phục hồi khi chưa; không ghi điểm tự chấm; không lộ key/IP/email. Chỗ thiếu thông tin: placeholder «CẦN NGƯỜI DÙNG: …», không bịa.
Thêm: không dùng số benchmark 98,9%/23,701 ms trừ khi có E-85; không nói "hiệu năng tăng X lần"; không nêu chuyện hạn nộp; không trình bày ánh xạ tiêu chí như của BTC.

## 8. Văn phong
Theo `00_PLAN.md` §E. Công thức dạng code inline. Trích mã ≤ 15 dòng/khối, chỉ cho pipeline cốt lõi (ví dụ nhánh `$setWindowFields`). Thuật ngữ §D.1. Tham chiếu chéo `(xem Tài liệu 04, §3.5)`.

## 9. Checklist tự kiểm
- [ ] Mọi tên collection/trường/index khớp mã (Grep lại từng tên).
- [ ] Không còn `readings.soil_humidity`/`source.sequence` nếu mã không có.
- [ ] Không số liệu sống bịa; mọi ô sống là placeholder có số lệnh H.2.
- [ ] Grep từ cấm: Atlas (chỉ được xuất hiện một lần ở §10), Change Stream (chỉ §10), MTTR, SLO, 100%, dữ liệu thật.
- [ ] Không IP/account/bucket/URI.
- [ ] Mọi `[E-xx]` tồn tại; số chương khớp; độ dài 5.000–6.500 từ.

## 10. Báo cáo
Tin nhắn ≤ 300 từ: đường dẫn tệp; số từ; chỗ mã khác `00_PLAN.md`; danh sách `[E-NEW]`; placeholder còn lại; danh sách lệnh H.2 cần người dùng chạy theo thứ tự ưu tiên.
