# Kiểm tra hồ sơ 04 và 05 (chỉ đọc)

| Mục | Vị trí | Kết quả (đạt / còn lỗi / không kiểm được) | Đoạn trích (tối đa 150 ký tự) |
|---|---|---|---|
| NICEGUI_STORAGE_SECRET không ghi là bắt buộc | 04, mục 4, Bảng 3 (dòng NICEGUI_STORAGE_SECRET); đối chiếu service/session_security.py:13-28 | đạt | "Khóa session NiceGUI; nếu thiếu, ứng dụng cảnh báo và tự sinh secret ngẫu nhiên" |
| API kịch bản: không ghi là chỉ bật khi SMIOT_DEMO_MODE=true; token SMIOT_DEMO_CONTROL_TOKEN | 04, mục 4, Bảng 3; 05, mục 5, Bảng 3; đối chiếu main.py:262-265 | đạt | "SMIOT_DEMO_CONTROL_TOKEN \| Bearer token riêng cho API kịch bản" |
| Tổng route API là 11 (có GET /api/inverter) | 04, mục 8.2, Bảng 6; đối chiếu main.py (10 decorator) và pages/inverter.py:37 | đạt | "8.2 Route API (11)" |
| /permission và /incident yêu cầu manage_users, không chỉ "Đăng nhập" | 04, mục 8.1, Bảng 5; 05, mục 5, Bảng 3; đối chiếu pages/permission.py:103, pages/incident.py:147-150 | đạt | "/permission \| Phân quyền người dùng \| Đăng nhập và quyền quản trị (manage_users)" |
| /history chuyển sang /chart | 04, mục 8.1, Bảng 5; đối chiếu pages/chart.py:39 | đạt | "/history \| Chuyển hướng sang /chart \| Chuyển hướng cũ" |
| /traceability chuyển sang /mongodb-lab | 04, mục 8.1, Bảng 5; đối chiếu pages/traceability.py:8 | đạt | "/traceability \| Chuyển hướng sang /mongodb-lab \| Chuyển hướng cũ" |
| Không khẳng định có unit smiot.service trong deploy\systemd\ | 04, mục 5, Bảng 4 bước 4; đối chiếu thư mục deploy\systemd\ (chỉ có velxio-bridge.service, smiot-external-probe.service, smiot-external-probe.timer) | đạt | "unit của ứng dụng không nằm trong deploy/systemd/" |
| Datadog Agent: "Bắt buộc cho metric và log" | 04, mục 2.1, Bảng 2 | đạt | "Datadog Agent \| Bắt buộc cho metric và log: nhận DogStatsD, ddtrace, đọc log từ file" |
| FR-2: Datadog đứng trung tâm (monitor phát hiện) | 05, mục 4, Bảng 2 (FR-2) | đạt | "Phát hiện bất thường do monitor Datadog đánh giá trên metric smiot.*" |
| FR-4: Datadog đứng trung tâm (workflow gọi lệnh) | 05, mục 4, Bảng 2 (FR-4) | đạt | "lệnh do workflow có guard của Datadog gọi endpoint của ứng dụng" |
| FR-5: Datadog đứng trung tâm (workflow phản ứng, MongoDB ghi xác minh) | 05, mục 4, Bảng 2 (FR-5) | đạt | "Phản ứng là workflow có guard của Datadog ... xác minh phục hồi ... ghi lại ở MongoDB" |
| Không có từ cấm (cuộc thi, chuyên ngành, chưa làm, đang bổ sung, email, IP, chuỗi kết nối, giá trị bí mật) | Toàn văn 04 và 05 (đoạn và bảng) | đạt | Không có từ nào trong danh sách; biến môi trường chỉ nêu tên hoặc placeholder <GIÁ_TRỊ> |
