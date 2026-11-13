# Review H4: 04 và 05 (chỉ đọc)

Phạm vi: 04_repository_va_huong_dan_cai_dat.docx, 05_readme_yeu_cau_kiem_thu.docx; đối chiếu 00_fact_sheet.md và 01_kien_truc_giai_phap.docx (chỉ tìm chuỗi .env, app.env, Datadog Agent). Không đọc mã dự án.

| File | Vị trí | Vấn đề | Mức | Gợi ý sửa |
|---|---|---|---|---|
| 05 | Bảng 4 (mục 6.2), cột "Cách kích hoạt", các dòng W1, W7, W8, W9 | Ghi theo sketch và node cụ thể ("nạp sketch node2_virtual_pump", "node2_virtual_pump nhận lệnh nhưng không phản hồi"), không dẫn về cấu hình ca và service/scenario_catalog.py. Các dòng Ca 1, Ca 2, Ca 3, W5, W6, W10 dùng cách viết khác. Vi phạm quy định cột này. | cao | Viết lại cả cột theo một mẫu: "Chọn <mã> trong cấu hình ca của ứng dụng; điều kiện kích hoạt theo service/scenario_catalog.py". Bỏ tên sketch và mô tả hành vi thiết bị khỏi cột. |
| 05 | Mục 4, FR-2 và FR-5; mục 1 | Vai trò Datadog chưa là trung tâm của cả ba pha. Phát hiện (FR-2) và khôi phục (FR-5) đang ghi là module của app (telemetry_findings, detector_heartbeat, w3_recovery_verification). Datadog chỉ xuất hiện ở FR-6 như một mục tích hợp. Fact sheet ghi Datadog "quan sát và điều phối", khóa an toàn cục bộ do app giữ. | cao | Nêu rõ trong mục 1 và bảng FR: Phát hiện dựa trên monitor Datadog (kèm detector của app làm đầu vào); Điều tra dựa trên log, trace, dashboard Datadog theo incident_id, MongoDB giữ bằng chứng; Phản ứng do workflow Datadog gọi endpoint có guard của app; app giữ khóa an toàn. |
| 04 | Mục 4, bảng 3 và đoạn cuối mục 4 | Thiếu tên biến URI MongoDB. Bước 5 mục 3.1 yêu cầu tạo .env "từ danh sách biến ở mục 4", nhưng danh sách không có biến này. Fact sheet ghi URI đọc từ biến môi trường (service/mongodb_store.py). Tên biến chưa được kiểm trong phiên này. | cao | Thêm dòng tên biến URI MongoDB (lấy tên từ service/mongodb_store.py, không ghi giá trị) và tên biến MQTT nếu có. |
| 04 | Mục 4, đoạn cuối "mã nguồn chỉ đọc tên biến, không có giá trị mặc định" | Mâu thuẫn với bảng 3 trong cùng mục: MONGODB_DATABASE mặc định smiot, AWS_REGION mặc định ap-southeast-2. Fact sheet ghi không có khóa mặc định, nhưng vẫn có giá trị mặc định cho một số biến không nhạy cảm. | vừa | Sửa thành "không có khóa, token hay URI mặc định"; giữ cột "mặc định" cho các biến có giá trị mặc định. |
| 04 | Mục 3.1 bước 5; mục 5 bảng 4 bước 3; mục 4 đoạn cuối | Nơi đặt khóa không thống nhất: local dùng file .env, server dùng /etc/smiot/app.env. 01 không nêu nơi đặt khóa (không tìm thấy .env hoặc app.env trong 01). | vừa | Thêm một câu cố định trong mục 4: local đặt trong .env ở gốc repo và không commit; server đặt trong /etc/smiot/app.env. Đồng bộ câu này với 01. |
| 04 | Mục 3.1 bước 6 và 7; 05 mục 3 | Thiếu cách lấy tài khoản đăng nhập đầu tiên (admin cho /incident). Không nêu dữ liệu đầu vào cần có trước khi kiểm tra "trang tổng quan hiển thị 10 nhà màng" (cần mẫu telemetry hoặc cầu nối). | vừa | Ghi rõ cách tạo tài khoản admin đầu tiên (chưa kiểm trong phiên này). Thêm điều kiện dữ liệu cho bước kiểm tra. |
| 05 | Mục 7.2, dòng "Dashboard" | Liệt kê 7 tên dashboard không có nguồn. Fact sheet ghi có 5 file JSON cục bộ và 1 dashboard live (SMIOT, App EC2 MongoDB và AI). Fact sheet cũng ghi số widget mâu thuẫn giữa các tài liệu (8 so với 5-7). | vừa | Ghi nguồn và ngày đọc (Datadog, 13/11) và chỉ liệt kê tên đã đối chiếu. Kiểm lại trước khi nộp. |
| 05 | Mục 8, bảng 7, dòng Ca 2 | "workflow xác nhận interlock cục bộ" đang được viết như kết quả. Fact sheet (E-56) ghi kết quả một phần, chưa xác nhận recovered. Khẳng định vượt bằng chứng. | vừa | Viết dòng này thành tiêu chí (workflow ghi nhận interlock cục bộ), không khẳng định đã đạt. Kết quả đo để ở tài liệu 06. Không dùng cụm "đang bổ sung". |
| 04 | Bảng 1 (mục 1.2), dòng scripts/ | "62 file .py (đệ quy)" không có nguồn kiểm trong phiên này (cột Nguồn ghi "scripts/"). | thấp | Ghi cách đếm (ví dụ Get-ChildItem -Recurse -Filter *.py) hoặc kiểm lại. |
| 04 | Mục 6, đoạn danh sách Terraform | Liệt kê terraform_scenarios. Fact sheet chỉ ghi terraform_monitors, terraform_farm_control_center, terraform_w2_greenhouse_j. Chưa thấy terraform_scenarios trong dữ liệu đã đọc. | vừa | Kiểm lại bằng cách liệt kê deploy/datadog; xóa tên nếu không tồn tại. |
| 05 | Mục 7.2, dòng "Workflow" | "10 workflow SMIOT ở trạng thái published" không có nguồn kèm. Fact sheet ghi đúng số này (live, 13/11). | thấp | Thêm nguồn "Datadog API, đọc 13/11". |
| 05 | Mục 5, bảng 3, dòng "Khóa đăng nhập tạm" | Ghi "5 lần sai trong một cửa sổ thời gian" nhưng không nêu độ dài cửa sổ. | thấp | Ghi số phút cụ thể và nguồn service/auth.py. |
| 04 | Bảng 2, dòng Python | "Python 3 (khuyến nghị bản đang được hỗ trợ)" không nêu phiên bản đã kiểm. | thấp | Ghi phiên bản cụ thể đã chạy. |
| 04, 05 | 04 mục 9; 05 mục 6.2 và 6.3 | Cụm "Ca khác với kịch bản" lặp ba lần. Bảng kích hoạt ca được nhắc ở nhiều nơi. | thấp | Giữ một lần ở 05 mục 6.2 và các nơi khác trỏ tới. |

Đã đạt (không có dòng lỗi):
- Datadog Agent ghi "Bắt buộc cho metric và log" ở 04 bảng 2 và 05 bảng 1. Không còn "Tùy chọn".
- Không có tên cuộc thi, ngành, chuyên ngành, IP, host, email, ID tài khoản, token hay giá trị khóa. Chỉ ghi tên biến.
- Số test: không ghi 281 hay 162. Chỉ ghi 41 file test_*.py, khớp fact sheet.
- Số lượng khớp fact sheet: 16 route giao diện, 10 route API, 36 kịch bản, 15 module pages, 37 module service, 4 module components, 41 file test, 3 project Velxio.
- Bước triển khai dùng smiot.service và /etc/smiot/app.env, khớp fact sheet.
- Nơi đặt khóa Datadog (Terraform hoặc Agent) khớp giữa 04 mục 6 và 04 bảng 3.
