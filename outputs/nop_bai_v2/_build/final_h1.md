| Mục | Vị trí | Kết quả (đạt / còn lỗi / không kiểm được) | Đoạn trích (tối đa 150 ký tự) |
|---|---|---|---|
| NICEGUI_STORAGE_SECRET không ghi là bắt buộc | 01 bảng 4 (Khóa session); 07 bảng 6 | đạt | "Nếu thiếu NICEGUI_STORAGE_SECRET, ứng dụng cảnh báo và tự sinh secret ngẫu nhiên". Mã service/session_security.py:13-28 khớp. |
| API kịch bản: token riêng, SMIOT_DEMO_MODE không điều khiển API | 01 bảng 4 (API kịch bản); 07 bảng 6 (SMIOT_DEMO_MODE) | đạt | "Bearer token riêng (SMIOT_DEMO_CONTROL_TOKEN); SMIOT_DEMO_MODE chỉ điều khiển route xác nhận muộn W9". Mã main.py:262-265 và main.py:499 khớp. |
| Không có khẳng định trích ARCHITECTURE.md về unit systemd hoặc /opt/smiot | 01, 07 (quét toàn văn) | đạt | Quét toàn văn: không có cụm "systemd" hay "/opt/smiot". |
| $unionWith: 7 nhánh | 01 đoạn 32 và bảng 5 | đạt | "gộp 7 nhánh $unionWith". Mã service/incident_blackbox.py có 7 nhánh (dòng 345, 359, 373, 391, 412, 427, 472). |
| 10 ca khớp CASES | 01 bảng 2 (cột Ca, Tên ca) | đạt | Ca 1, Ca 2, Ca 3, W1, W5, W6, W7, W8, W9, W10 khớp khóa 1-10 của CASES tại service/incident_blackbox.py:780-811. |
| W10 không có monitor trong bộ đã đọc | 01 bảng 2 (hàng W10) | còn lỗi | "Không có monitor trong bộ đã đọc". Mã CASES gán monitor_id 342585824 cho W10 (incident_blackbox.py:809-811). Cần chủ hồ sơ đối chiếu với Datadog. |
| W5 liệt kê hai monitor (342585827, 342585828) | 01 bảng 2 (hàng W5) | còn lỗi | "MQTT dependency unhealthy (342585828)". Mã CASES chỉ gán monitor 342585827 cho W5 (incident_blackbox.py:797-799). |
| Không có cuộc thi, chuyên ngành, "chưa làm", "đang bổ sung" | 01, 07 (quét toàn văn) | đạt | Quét toàn văn đoạn và bảng: không có cụm nào trong bốn cụm này. |
| Không có email, IP | 01, 07 (quét toàn văn) | đạt | Chỉ có "@ui.page" và "@app", là tên decorator trong mã, không phải thông tin liên hệ hay địa chỉ IP. |
| Không có chuỗi kết nối hoặc giá trị token | 01 bảng 4 (Bí mật); 07 bảng 6 | đạt | "Giá trị token, khóa, chuỗi kết nối đọc từ biến môi trường, không có giá trị mặc định trong mã". Chỉ có tên biến, không có giá trị. |
