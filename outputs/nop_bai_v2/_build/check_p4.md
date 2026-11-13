# Kiểm chứng P4 (chỉ đọc)

Phạm vi: 7 file .docx trong outputs\nop_bai_v2 (đã trích text), scripts\velxio_mqtt_bridge.py, scripts\drill_*.py, velxio\ và outputs\velxio_v2\, service\scenario_catalog.py, service\scenario_domain_*.py, service\demo_mode.py, service\mqtt.py, tests\.

Cột "Khẳng định (file, mục)": vị trí trong .docx (đoạn hoặc bảng) hoặc trong file README/HUONG_DAN.
Cột "Mã đối chiếu (file:dòng)": dòng trong mã nguồn.

| Khẳng định (file, mục) | Mã đối chiếu (file:dòng) | Kết quả | Gợi ý sửa |
|---|---|---|---|
| 06, đoạn mở đầu: 8 mã đã chạy A1, A2, A3, A4, C10, S2, S3, C2 | service\scenario_catalog.py:34-44 (alias); service\scenario_domain_actuator_infra.py:16,26,36,46 (A1-A4); service\scenario_domain_crops.py:38 (C2), :78 (C10); service\scenario_domain_sensor_device.py:26,32 (S2, S3) | khớp | không cần sửa |
| 06, Bảng 4 (mục 4.2) và 07: scenario_type A3 = a3_low_flow, C10 = pipe_leak | service\scenario_domain_actuator_infra.py:37 (a3_low_flow); service\scenario_catalog.py:40 (pipe_leak -> C10) | khớp | không cần sửa |
| 06, Bảng 4 và 05: nhóm S gồm S1-S6 | service\scenario_domain_sensor_device.py:19-52 | khớp | không cần sửa |
| 06, mục 4.1: A1 đo trên node2, profile=fault | scripts\velxio_mqtt_bridge.py:33 ("A1": ("node2", "flow")); outputs\velxio_v2\node2_virtual_pump\sketch.ino:116-122 (ACK node2, profile) | khớp | không cần sửa |
| Ánh xạ thiết bị A2, A4 -> node2 (06 mục 4.1; 07 bảng thiết bị) | scripts\velxio_mqtt_bridge.py:34 (A2), :37 (A4); sketch node2:57-61 (A4 withhold ACK), :165 (A2 giữ đầu ra = 0) | khớp | không cần sửa |
| A3, C10 -> node flow (chưa có câu nào trong hồ sơ nêu thiết bị cụ thể) | scripts\velxio_mqtt_bridge.py:35-36 | không kiểm được (hồ sơ không nêu; mã khớp với code) | Nếu muốn nêu, ghi "flow (node3)" |
| S2, S3 -> node1 (soil spike / out of range); C2 -> node1 | scripts\velxio_mqtt_bridge.py:38-41 | khớp | không cần sửa |
| Mã S1 (soil_flatline) có nhánh riêng trên node1 | outputs\velxio_v2\node1_environment\sketch.ino:178 (S1 -> sh=8); scripts\velxio_mqtt_bridge.py:30-44 (không có S1, S4-S6 trong bảng SET_PROFILE) | khớp catalog; lưu ý: cầu nối không gửi SET_PROFILE cho S1 | Nếu hồ sơ hoặc demo cần S1 trên node1, bổ sung S1 vào bảng ánh xạ trong cầu nối. Hiện hồ sơ không nêu S1 là kịch bản đã chạy, nên không sửa hồ sơ |
| Giá trị fault node1 (velxio_v2 README, mục bảng): S1 sh=8; S2 sh=95; S3 sh=0 | outputs\velxio_v2\node1_environment\sketch.ino:178-180; outputs\velxio_v2\node1_environment\README.md:32-34 | khớp | không cần sửa |
| Giá trị fault node1: C2 và C6 at=39, ah=88, sec=3.8 | outputs\velxio_v2\node1_environment\sketch.ino:181; README.md:35-36; outputs\velxio_v2\HUONG_DAN.md:24-25 | khớp | không cần sửa |
| Giá trị fault mặc định node1: at=38, ah=82, sh=12 | outputs\velxio_v2\node1_environment\sketch.ino:168, :182; README.md:38 | khớp | không cần sửa |
| "sec" trong profile fault mặc định không được gán giá trị riêng | outputs\velxio_v2\node1_environment\sketch.ino:174 (sec = 1,30 ± 0,05, không đổi khi fault) | khớp với code; hồ sơ không nêu sec mặc định | không cần sửa |
| Tự động trả về normal sau 120 s (node1, node2, node3) | outputs\velxio_v2\node1_environment\sketch.ino:32,148; node2_virtual_pump\sketch.ino:30,268; node3_flow_monitor\sketch.ino:37,168 (đều 120000 ms); README và HUONG_DAN ghi "120 s" | khớp (sketch và README velxio_v2); không có trong 7 file .docx | Nếu cần nêu trong hồ sơ, thêm dẫn chiếu tới sketch. Lưu ý không nhầm với VIRTUAL_PLC_MAX_RUN_SECONDS=120 ở service\demo_mode.py:60, :1356-1361 (giới hạn thời gian chạy PLC ảo, cơ chế khác) |
| ACK lệnh: "Lệnh MQTT có ACK, ghi vào sổ lệnh action_ledger (service/mqtt.py)" (01, mục 2) | service\mqtt.py:115-116 (khớp ACK theo command_id); service\mqtt.py:1165 (log smiot_action_ledger) | khớp | không cần sửa |
| ACK thiết bị ảo: log "velxio_profile_ack_forwarded" (06, Bảng 6, A1) | scripts\velxio_mqtt_bridge.py:397 | khớp | không cần sửa |
| A4 không gửi ACK (W9) | outputs\velxio_v2\node2_virtual_pump\sketch.ino:54-61, :79-80 (ACK_SUPPRESSED); scripts\drill_device_a_series.py:10,28 (A4 -> W9) | khớp | không cần sửa |
| A2 và C10 gắn W1; A4 gắn W9 (06, mục 4.4 "W1 gồm A1, A2, A3, C10; W9 gồm A4") | scripts\drill_device_a_series.py:8-10, :26-28 | khớp với A2, C10, A4. A1, A3 không có trong drill_device_a_series.py (không kiểm được tại đây) | không cần sửa |
| 06, mục 4.4: "W7 gồm S2 và S3 (ở S3, monitor báo là monitor flatline)" và cùng mục "S3: monitor báo là monitor flatline (342585819); không phải monitor W7" | Bảng 6 của 06 (S3 -> Sensor flatline 342585819); 01 (W7 = soil moisture advisory 343594187) | sai (mâu thuẫn nội bộ: một câu gán S3 vào W7, câu sau nói không phải monitor W7) | Viết lại: "W7 gồm kịch bản S2 và S3. Với S3, monitor phát hiện là sensor flatline (342585819), không phải monitor advisory của W7 (343594187)." |
| Số file test: 41 file tests\test_*.py (04, Bảng 1 mục tests; 05) | tests\ (đếm test_*.py: 41 file, gồm cả pycache không tính) | khớp | không cần sửa |
| Catalog có 36 kịch bản, 5 nhóm (01 Bảng; 05 mục 4.2; 06 Bảng 4; 07 bảng nhóm) | service\scenario_catalog.py:1,48 (docstring 36); scenario_domain_crops.py:33-78 (C1-C10 = 10); scenario_domain_sensor_device.py:19-92 (S1-S6, D1-D7 = 13); scenario_domain_actuator_infra.py:16-136 (A1-A7, H1-H6 = 13). Tổng 36 | khớp | không cần sửa |
| Bảng 4 (06) và bảng nhóm (07): A 7, C 10, D 7, H 6, S 6, Tổng 36 | khớp với số mã đếm ở trên. 07 bảng nhóm có đủ 5 dòng A, C, D, H, S | khớp | không cần sửa |
| 10 ca sự cố: Ca 1-3, W1, W5-W10 (04 đoạn cuối; 06 đoạn mở; 03 mục 5) | Không thuộc phạm vi mã (cấu hình Datadog/app). Số ca đếm trong hồ sơ: 3 + 1 + 6 = 10 | khớp nội bộ hồ sơ; mã không kiểm được | không cần sửa |
| 06, mục 4.3: A3 và C10 có lệnh CLEAR safe mode; chờ monitor OK 127 s trước A3 | Không có trong phạm vi mã đã đọc (cần drill_suite_*.json, không có trong phạm vi) | không kiểm được | Cần đối chiếu với file đo của suite 12/11 và 13/11 |
| 06, Bảng 5-6: các con số đo (109,8 s; 1,4 s; 317,6 s; SET_OUTPUTS T_stop 360,3 s, v.v.) và mã INC-SMIOT-SCENARIO-* | Dữ liệu từ drill_suite_20261112T225228Z.json và drill_suite_pump_20261113T023126Z.json, không nằm trong phạm vi | không kiểm được | Đối chiếu với hai file JSON trong bản ghi suite |
| 06, mục 4.4: W8 gồm C2 (monitor và workflow) | Không có ánh xạ W8 -> C2 trong scripts\drill_*.py đã đọc; cầu nối chỉ có W8/vpd_ec_risk -> node1 (velxio_mqtt_bridge.py:44) | không kiểm được (ánh xạ W8 nằm ở cấu hình Datadog/Terraform, ngoài phạm vi) | Giữ nguyên, ghi rõ nguồn là cấu hình monitor/workflow |

Tổng kết theo dòng: khớp 18 dòng (gồm dòng 10 ca sự cố, khớp nội bộ hồ sơ), sai 1 dòng (06 mục 4.4, S3 và W7), không kiểm được 4 dòng (ánh xạ A3/C10 tới thiết bị flow, CLEAR và 127 s, số đo trong hai file JSON suite, ánh xạ W8 -> C2). Dòng 120 s khớp với sketch và README velxio_v2 nhưng không có trong 7 file .docx.

Ghi chú về phạm vi: không gọi mạng, không gọi Datadog, không ghi DB, không gửi MQTT, không sửa hồ sơ hay mã nguồn. Không in giá trị token, khóa, mật khẩu, chuỗi kết nối hoặc tên broker.
