# Kết quả kiểm H3 (chỉ đọc)

Nguồn: 03_kien_truc_observability_datadog.docx, 06_mo_ta_su_co_tinh_huong_trinh_dien.docx. Đối chiếu: 00_fact_sheet.md.

| Mục | Vị trí | Kết quả (đạt / còn lỗi / không kiểm được) | Đoạn trích |
|---|---|---|---|
| 1 | 03, Mục 3 (P38) | đạt | "Tổ chức Datadog có 5 dashboard SMIOT (đọc bằng GET ngày 13/11)." Không có chuỗi "5 + 1 dashboard". |
| 2 | 03, Mục 2.1 (P28) | đạt | "Trong mã còn có các chuỗi tên dạng smiot.* gồm tên metric, tên span và tên sự kiện log." Không có chuỗi "78 chuỗi smiot.*". |
| 3 | 06, Mục 4.4 (P57) | đạt | "W7 gồm S2 (S3 do monitor flatline phát hiện); W8 gồm C2; W9 gồm A4." S3 không nằm trong W7. |
| 4 | 06, Mục 4.4 (P69, Bảng 5) | đạt | "S3: monitor báo là monitor flatline (342585819); không phải monitor W7." |
| 5 | 06, Mục 3.1 (P32-P33) | đạt | "Điều tra trên Datadog: trạng thái monitor telemetry status mismatch (...). Điều tra trên MongoDB: hồ sơ sự cố và mẫu telemetry mới nhất" |
| 6 | 06, Mục 3.2 (P39-P40) | đạt | "Điều tra trên Datadog: theo trạng thái monitor (sensor flatline). Điều tra trên MongoDB: hồ sơ sự cố và bằng chứng telemetry của Node 2." |
| 7 | 06, Mục 3.3 (P45-P46) | đạt | "Điều tra trên Datadog: trạng thái monitor smiot.service inactive (...). Điều tra trên MongoDB: hồ sơ sự cố và dữ liệu telemetry quanh thời điểm dừng." |
| 8 | 06, Mục 3.2 (P39) | đạt | "Điều tra trên Datadog: theo trạng thái monitor trên Datadog (sensor flatline), cùng metric smiot.* và log, trace có incident_id của sự cố." |
| 9 | 06, toàn văn | đạt | Không có "EVIDENCE_INDEX" (không tìm thấy). |
| 10 | 06, toàn văn | đạt | Không có "kịch bản sự cố" (không tìm thấy). |
| 11 | 06, Mục 4.4 (P79; Bảng 6, dòng A2) | đạt | "A2 (suite bơm 13/11): Datadog phát hiện 79,1 s, về OK 286,3 s." Khớp 00_fact_sheet.md dòng 287. |
| 12 | 06, Mục 4.4 (P79; Bảng 5, dòng C10) | đạt | "C10 (suite 12/11): phát hiện 79,1 s, về OK 286,5 s." Khớp 00_fact_sheet.md dòng 274. |
| 13 | 03 và 06, toàn văn | đạt | Không có "cuộc thi" (không tìm thấy). |
| 14 | 03 và 06, toàn văn | đạt | Không có "chuyên ngành" (không tìm thấy). |
| 15 | 03 và 06, toàn văn | đạt | Không có "chưa làm" (không tìm thấy). |
| 16 | 03 và 06, toàn văn | đạt | Không có "đang bổ sung" (không tìm thấy). |
| 17 | 03 và 06, toàn văn | đạt | Không có địa chỉ email. Ký tự "@" chỉ xuất hiện trong "@workflow-smiot-..." (Bảng 6, 03). |
| 18 | 03 và 06, toàn văn | đạt | Không có địa chỉ IP (không tìm thấy). |
| 19 | 03 và 06, toàn văn | đạt | Không có "mongodb://" (không tìm thấy). |
| 20 | 03 và 06, toàn văn | đạt | Không có giá trị bí mật. Chỉ có tên biến, ví dụ "DATADOG_APP_NOTIFICATION_TOKEN" (03, P69). |

Ghi chú: Bảng 6 của 03 ghi "5 dashboard JSON và một datadog_dashboard_json bổ sung trong main.tf". Chuỗi cấm "5 + 1 dashboard" không xuất hiện, nên mục 1 đạt theo đúng nghĩa kiểm.
