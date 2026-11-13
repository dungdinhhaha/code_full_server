# Kiểm chứng P1: giao diện, route, luồng /incident (chỉ đọc)

Phạm vi: main.py, pages/*.py, components/*.py. Đối chiếu 7 file .docx trong outputs/nop_bai_v2 (text lấy từ đoạn và bảng).
Không gọi Datadog, không gọi mạng, không ghi DB, không sửa file dự án.

| Khẳng định (file, mục) | Mã đối chiếu (file:dòng) | Kết quả | Gợi ý sửa |
|---|---|---|---|
| 04 §8.1 và Bảng 5: 16 route giao diện (@ui.page) | pages/traceability.py:6, chart.py:37,42, public_lot.py:73, project.py:128, incident.py:1355,1639, plc.py:390, home.py:938, permission.py:96, devices.py:489, data_table.py:50, mongodb_lab.py:210, inverter.py:165, schedule.py:95, login.py:63 | khớp (đếm 16) | Không cần sửa |
| 04 §8.2 và Bảng 6: 10 route API (@app) "nguồn: main.py" | main.py:128, 253, 440, 489, 613, 625, 698, 801, 960, 1010 (10 route, method và path khớp Bảng 6) | sai (tổng toàn app là 11) | Thêm GET /api/inverter (pages/inverter.py:37) vào Bảng 6, ghi "11 route API (10 trong main.py, 1 trong pages/inverter.py)". Hoặc ghi rõ "10 route trong main.py" |
| 04 dòng 740: "main.py, 16 route giao diện, 10 route API" | main.py (10 @app), pages/inverter.py:37 (@app.get) | sai (11 route API) | Sửa "10 route API" thành "11 route API" hoặc "10 route API trong main.py" |
| 04 dòng 393: main.py "khai báo route API, 10 route API" | main.py:128-1010 | khớp với main.py, thiếu pages/inverter.py | Ghi thêm pages/inverter.py có 1 route API |
| 04 Bảng 5: /history "Lịch sử, Đăng nhập" | pages/chart.py:37-39 (@ui.page('/history') gọi ui.navigate.to('/chart')) | sai | Ghi "/history: chuyển hướng sang /chart (Biểu đồ)" |
| 04 Bảng 5: /traceability "Chuyển hướng sang trang lô" | pages/traceability.py:6-8 (chuyển sang "/mongodb-lab") | sai | Ghi đích là /mongodb-lab |
| 04 Bảng 5: /permission "Đăng nhập" | pages/permission.py:98-105 (check_login, sau đó chặn nếu không phải admin và không có manage_users) | sai (quyền thực tế hẹp hơn) | Ghi "Admin hoặc quyền manage_users" |
| 04 Bảng 5: /incident và /incident/{id} "Admin"; 03 "/incident/{id} chỉ dành cho admin" | pages/incident.py:147-160 (_guard: admin hoặc quyền manage_users), 1355-1357, 1639-1641 | khớp một phần (thiếu nhánh manage_users) | Ghi "Admin hoặc quyền manage_users" |
| 04 Bảng 5: /lot/{token} "Công khai, chỉ đọc" | pages/public_lot.py:73-79 (không có check_login) | khớp | Không cần sửa |
| 04 Bảng 5: /login "Công khai"; /, /inverter, /plc, /devices, /schedule, /history, /chart, /data, /projects, /mongodb-lab "Đăng nhập" | check_login có ở: home.py:940, inverter.py:167, plc.py:392, devices.py:491, schedule.py:97, chart.py:44, data_table.py:52, project.py:130, mongodb_lab.py:212 | khớp (trừ /history và /traceability đã nêu) | Không cần sửa |
| 04 §9 và 05 §6.2: 10 ca gồm Ca 1, Ca 2, Ca 3, W1, W5, W6, W7, W8, W9, W10 | service/incident_blackbox.py:780-812 (CASES có 10 mục: 1, 2, 3, 4=W7, 5=W8, 6=W5, 7=W6, 8=W1, 9=W9, 10=W10) | khớp (tập hợp) | Không cần sửa |
| 05 §6.2 mô tả Ca 1: "trạng thái UI báo offline, mẫu vẫn vào MongoDB" | service/incident_blackbox.py:781-782 ("Mẫu vẫn vào MongoDB nhưng giao diện báo offline") | khớp (nội dung ca) | Không cần sửa |
| 05 §6.2 mô tả Ca 2: "độ ẩm đất Node 2 đứng yên" | service/incident_blackbox.py:785-786 ("độ ẩm kẹt ở 2,4%") | khớp | Không cần sửa |
| 05 §6.2 mô tả Ca 3: "smiot.service dừng" | service/incident_blackbox.py:788-789 | khớp | Không cần sửa |
| "Datadog đang thấy gì" (tên khối trên /incident) | pages/incident.py:1382 (panel("Datadog đang thấy gì", ...)) | khớp với code. Cụm này KHÔNG có trong 7 file .docx | Nếu muốn nêu tên khối trong hồ sơ, thêm vào mục mô tả /incident. Chú thích: khối A là pha Phát hiện |
| Khối A subtitle "Phát hiện: trạng thái monitor của mười ca vận hành" | pages/incident.py:1382 | khớp với code; không có trong .docx | Không cần sửa nếu không trích |
| Thẻ theo ca (10 thẻ): tên ca, trạng thái monitor, "Đổi trạng thái lần cuối", "(MongoDB)", link Monitor và Workflow | pages/incident.py:1409-1431 (vòng lặp CASES, nút tên ca, ext_link Monitor/Workflow) | khớp với code | Không cần sửa |
| Chú thích "Bấm tên ca để lọc hồ sơ" | pages/incident.py:1432, bộ lọc "Đang lọc: Ca N" và "Bỏ lọc ca" ở 1478-1481 | khớp | Không cần sửa |
| Bốn ô thống kê Monitor Alert, Warn, No Data, OK | pages/incident.py:1397-1402 | khớp với code (chưa đối chiếu số liệu) | Không cần sửa |
| Ba pha: "1 · Phát hiện", "2 · Điều tra", "3 · Phản ứng" (docx: Phát hiện, Điều tra, Phản ứng) | pages/incident.py:1102, 1118, 1126, 1258 | khớp | Không cần sửa |
| 03 §: thông báo Datadog hiển thị ở chuông thông báo và /incident/{id} | main.py:1010 (POST notification); pages/home.py:737-801 (chuông, link "/incident/{id}" ở 801) | khớp | Không cần sửa |
| 04 Bảng 6: POST /api/demo/scenarios yêu cầu bearer và Idempotency-Key | main.py:253-278 (token, Idempotency-Key tối đa 200 ký tự) | khớp | Không cần sửa |
| 04: API kịch bản chỉ bật khi SMIOT_DEMO_MODE=true | main.py:499 (cho W9), main.py:262 và 443 (SMIOT_DEMO_CONTROL_TOKEN) | khớp một phần: /api/demo/scenarios và GET status không đọc SMIOT_DEMO_MODE; chỉ /api/demo/w9/late-ack kiểm tra biến này | Sửa: "chỉ W9 late-ack bật khi SMIOT_DEMO_MODE=true; các route scenarios cần SMIOT_DEMO_CONTROL_TOKEN" |
| 04 §8: /healthz không cần đăng nhập | main.py:613-622 | khớp | Không cần sửa |
| 04 §10 Bước 6-7: chạy python main.py, kiểm tra GET /healthz | main.py tồn tại; main.py:613 | khớp | Không cần sửa |
| 04: trang tổng quan hiển thị 10 nhà màng | service/farm_registry.py:4-13 (10 nhà màng a..j); pages/home.py:938 (route "/") | khớp | Không cần sửa |
| 04 / 03: pages/ có 15 module; components/ có 4 module và __init__.py | pages/: 15 file .py (không tính __init__); components/: cards, layout, theme, ui_kit | khớp | Không cần sửa |
| 04: 16 route giao diện, route /incident là danh sách, /incident/{id} là hộp đen | pages/incident.py:1355, 1639 | khớp | Không cần sửa |
| 03 §: /incident/{id} hiển thị dòng thời gian hộp đen | pages/incident.py:1639-1665 (build_incident_timeline) | khớp | Không cần sửa |
| Nội dung luồng 05 §6.2 bước (3) "chọn và bắt đầu ca trong cấu hình ca của ứng dụng" | Không tìm thấy nút hoặc màn hình chọn ca để bắt đầu ca trong pages/*.py (chỉ có lọc ca trên /incident) | không kiểm được (có thể nằm ngoài phạm vi: cấu hình ca ở tài liệu 05) | Nếu nói người dùng bấm để bắt đầu ca trên giao diện, cần chỉ rõ màn hình; nếu không, ghi rõ là cấu hình bên ngoài giao diện |
| 05 §6.2 bước (5) "Quan sát /devices và /incident" | pages/devices.py:489 (route tồn tại); incident.py:1355 | khớp route; thao tác thực tế không kiểm được | Không cần sửa |
| 04 Bảng 3 số đếm: Ca 1-3 "OFFLINE" và số lần chạy trên giao diện lúc 11:02:50 ngày 13/11 | Không kiểm được (cần dữ liệu runtime và MongoDB) | không kiểm được | Không sửa; ghi là số đo tại thời điểm chụp |
| 04 §3 và 03 Bảng: Monitor (19), Dashboard (5), Workflow (10), ID monitor và dashboard | Không gọi Datadog theo phạm vi; ID ca trong code nằm ở service/incident_blackbox.py:780-812 | không kiểm được (số đếm và trạng thái Datadog) | Không sửa trong P1 |
| 03 §: "Phân quyền 14 quyền; khóa đăng nhập 5 lần" | Ngoài phạm vi (service/auth.py) | không kiểm được | Kiểm ở P2 |

## Tổng kết
- Khớp: 26 khẳng định (không tính dòng gộp).
- Sai: 6 khẳng định (tổng route API là 11; /history, /traceability, /permission sai đích hoặc quyền; ghi sai phạm vi SMIOT_DEMO_MODE).
- Không kiểm được: 6 khẳng định (số đếm Datadog, số đo runtime, thao tác chọn ca, quyền auth ngoài phạm vi).

## Ba lỗi quan trọng nhất
1. Tổng route API là 11, không phải 10. Route GET /api/inverter nằm ở pages/inverter.py:37, nhưng 04 §8.2, dòng 393 và dòng 740 ghi 10 và nói nguồn là main.py.
2. Quyền truy cập sai trong 04 Bảng 5: /permission ghi "Đăng nhập" nhưng code chặn người không phải admin và không có manage_users (permission.py:103). /incident và /incident/{id} ghi "Admin" nhưng code cũng cho phép quyền manage_users (incident.py:147-150).
3. Đích chuyển hướng sai: /history chuyển sang /chart (chart.py:39) và /traceability chuyển sang /mongodb-lab (traceability.py:8), không phải "trang lô" hay trang lịch sử riêng.

Ghi chú: cụm "Datadog đang thấy gì" có trong code (incident.py:1382) nhưng không có trong 7 file .docx. Thẻ 10 ca khớp với CASES.
