# Checklist hồ sơ nộp (12 mục)

Nguồn: trang điều khoản (§7.2) và trang chính của cuộc thi, đọc ngày 06/11/2026. Trạng thái:
**Đã có** = tệp/nội dung đã nằm trong repo hoặc hệ thống; **Cần làm** = AI/đội có thể làm tiếp; **Cần người dùng** = cần quyết định, thông tin hoặc hành động của người dùng.
Trạng thái dưới đây là đánh giá của người viết tại thời điểm tạo file, chưa được người dùng xác nhận.

| # | Mục hồ sơ | Trạng thái | Ghi chú / việc còn lại |
|---|---|---|---|
| 1 | Tên dự án, mô tả bài toán | Cần người dùng | Viết 1 đoạn: ai đau, đau gì, đo bằng gì |
| 2 | Thông tin đội, đầu mối liên hệ | Cần người dùng | Không đưa email/điện thoại vào repo công khai |
| 3 | Kiến trúc giải pháp và ứng dụng | Cần làm | Sơ đồ thiết bị -> ingest -> smiot.service -> MongoDB -> Datadog Agent; ghi rõ EC2 self-managed |
| 4 | Kiến trúc dữ liệu, data model MongoDB | Cần làm | Collection, schema, index, Time Series, pipeline, `explain()` (IXSCAN); `docs/MONGODB_BACKUP_RESTORE_DRILL_20261103.md` đã có phần backup. Thêm khi hoàn tất: trang `/incident` (hộp đen) và JSON `explain` từ `scripts/explain_before_after.py` |
| 5 | Kiến trúc observability Datadog | Cần làm | Metrics/logs/traces, tag, dashboard nkc-685-vw8, monitor, workflow; bản nháp monitor/workflow ở `deploy/datadog/drafts/` đã có, chưa tạo trên Datadog. Thêm: ảnh chụp 5 monitor đang OK trước triển khai |
| 6 | Link repo, hướng dẫn cài đặt | Cần người dùng | Nếu private: cấp quyền cho tài khoản giám khảo, giữ đến 22/11/2026 |
| 7 | README (môi trường, triển khai, cấu hình, kiểm thử) | Cần làm | `.env.example` không secret; lệnh tái hiện 3 ca (README thuộc agent khác) |
| 8 | MVP chạy được / demo truy cập được | Cần người dùng | URL còn sống trong vòng chấm hoặc hướng dẫn chạy local + seed tổng hợp |
| 9 | Video demo | Cần người dùng | Có cảnh monitor kích hoạt -> điều tra -> xử lý -> recovered; không lộ key/IP/email |
| 10 | Slide chung kết | Cần người dùng | Bám trọng số 30/30/30/10 |
| 11 | Mô tả sự cố, tình huống trình diễn | Cần làm | Playbook `docs/THREE_CASES_PLAYBOOK.md` và mẫu `docs/EVIDENCE_TEMPLATE.md` đã có; Ca 2 đã có hồ sơ `INC-SMIOT-20261103T114321-BD19A22C_EVIDENCE.md`; Ca 1 và Ca 3 chưa có hồ sơ chuẩn 6 câu. Ảnh `/incident/<id>` của từng ca đưa vào hồ sơ khi có |
| 12 | Khai báo tái sử dụng, dataset, công cụ AI | Cần người dùng | `docs/DECLARATIONS.md` đã dựng khung; người dùng điền giấy phép, ngày commit, mục có từ trước 17/10 |

Thêm: commit cuối trước hạn (không chỉnh repo sau hạn); quét secret toàn bộ lịch sử git, không chỉ HEAD (Cần người dùng).

## Cần xác nhận với BTC (bằng văn bản)
1. **Hạn nộp:** web ghi 23:59 31/10/2026; email BTC ghi 08/11/2026 (chưa xác minh được trên web). Người dùng phải hỏi lại BTC bằng văn bản để chốt hạn 08/11 hay 31/10. Hỏi: hạn mới chính xác; commit cuối chấm theo mốc nào; video/slide hạn nào. Lưu email gốc.
2. Chung kết 08/11 (dự kiến) trùng hạn mới: vòng sơ loại và việc công bố đội vào chung kết xử lý thế nào?
3. Trọng số 30/30/30/10 trên trang chính nhưng trang điều khoản còn câu "sẽ được công bố"; ánh xạ 8 tiêu chí vào 4 nhóm không được nêu chính thức; vòng sơ loại chấm theo gì?
4. "Dữ liệu thật của hệ thống" so với "dùng dữ liệu tổng hợp": dữ liệu IoT tổng hợp/thiết bị mô phỏng do đội tạo có hợp lệ không?
5. MongoDB Community self-managed trên EC2 (không Atlas) có được chấp nhận đầy đủ không?
6. Thành phần có từ trước 17/10: mức khai báo cần thiết; cửa sổ build có kéo dài khi hạn dời không?
7. Repo private: tài khoản giám khảo đã có chưa; thời hạn giữ quyền 22/11/2026 có đổi không?
8. Datadog trial (kích hoạt 17/10, thường 14 ngày): dashboard/monitor còn truy cập lúc chung kết không? Chuẩn bị JSON export và ảnh dự phòng.
9. Thời lượng thuyết trình chung kết.
10. Kênh liên hệ chính thức để xác nhận bằng văn bản.

## Điều không được tuyên bố trong hồ sơ
Atlas Search/Vector Search/Triggers/Charts/Stream Processing; Change Streams (mongod standalone); đạt SLO/SLA hay con số MTTD/MTTR/% giảm cảnh báo khi chưa có nguồn đo; thiết bị vật lý hỏng/đã sửa; dữ liệu tổng hợp là dữ liệu thật; "tự động khắc phục" nếu bước thực hiện là thủ công; Bits đã xác nhận phục hồi khi chưa; điểm số.
