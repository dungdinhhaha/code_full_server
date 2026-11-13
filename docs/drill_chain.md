# Chuỗi diễn tập thiết bị ảo Velxio (nhà màng greenhouse_j)

Tài liệu mô tả hành vi theo mã trong code tại thời điểm viết (2026-11-13). Chưa đối chiếu với lượt chạy thực tế và chưa truy vấn Datadog. Các mục đánh dấu "chưa xác minh" cần kiểm tra trước khi dùng làm bằng chứng.

## 1. Nguồn đã đọc

- `service\scenario_catalog.py`: mã, tiêu đề, ánh xạ tên cũ sang mã.
- `service\scenario_domain_actuator_infra.py`, `service\scenario_domain_sensor_device.py`, `service\scenario_domain_crops.py`: định nghĩa tiêu chí của từng mã (chỉ đọc để tra).
- `service\demo_mode.py`: START/STOP_SCENARIO, ACK, interlock, ngưỡng và điều kiện ngữ cảnh (chỉ đọc).
- `velxio\node1_environment\sketch.ino`, `velxio\node2_virtual_pump\sketch.ino`, `velxio\node3_flow_monitor\sketch.ino`: đèn, còi, dòng Serial, tín hiệu sai (chỉ đọc).
- `scripts\velxio_mqtt_bridge.py`: bảng `SCENARIO_DEVICES` quyết định thiết bị nào nhận SET_PROFILE (chỉ đọc).
- `pages\plc.py`: đường dẫn trang và nhãn nút.
- `deploy\datadog\terraform_monitors\monitors.tf`, `scripts\seed_six_step_demo_incidents.py`: tên và phạm vi monitor (chỉ đọc, không gọi Datadog).

Tên ID monitor lấy từ danh sách đã biết: W1 342734303, W7 343594187, W8 343594185, W9 342734743.

## 2. Quy trình chung

**Bắt đầu**
1. Đăng nhập tài khoản admin. Panel "Diễn tập thiết bị ảo" chỉ hiện với admin.
2. Chọn nhà màng greenhouse_j ở thanh trên (`current_farm_key`).
3. Mở trang `/plc` (tiêu đề trang "Bơm"), kéo tới panel "Diễn tập thiết bị ảo".
4. Chọn mã trong ô "Kịch bản" (mặc định A1; nhãn dạng "A1 · Tràn nước / quá lượng"). Ô "Seed lặp lại" mặc định 17.
5. Bấm nút "Chạy kịch bản", rồi bấm nút "Chạy kịch bản" trong hộp xác nhận "Chạy kịch bản?".
- Điều kiện: MQTT đã kết nối; không có diễn tập khác đang chờ hoặc đang chạy.
- Lệnh gửi đi là `START_SCENARIO` trên `farm/demo/control`. `demo_mode` trả `scenario_ack` (started hoặc rejected) trên `farm/demo/status`. Bridge chuyển ACK "started" thành SET_PROFILE fault tới các thiết bị được ánh xạ.

**Dừng**
- Bấm "Dừng kịch bản", xác nhận "Dừng kịch bản?". Hệ thống gửi `STOP_SCENARIO` với `scenario_run_id` hiện tại.
- Giao diện chờ ACK. Nếu quá 15 giây chưa có ACK, hiển thị "trạng thái thiết bị chưa xác định".

**Phục hồi**
- `demo_mode` trả `scenario_ack` "stopped". Bridge gửi SET_PROFILE normal tới các thiết bị đã ánh xạ cho mã đó.
- node1 và node2 tự chuyển về normal sau 120 giây nếu không nhận lệnh (`FAULT_AUTO_REVERT_MS` và `AUTO_REVERT_MS`). Tự phục hồi không tạo ACK.
- flow (node3) không có tự phục hồi; chỉ chuyển về normal khi nhận lệnh.
- Khi không còn lượt chạy nào trên farm, `demo_mode` xóa safe mode của farm.

**Từ chối khi bắt đầu** (`demo_mode`)
- A1, A2, A3, pipe_leak bị từ chối (`safe_mode_active`) nếu farm đang ở safe mode.
- Hai mã cùng tài nguyên không chạy đồng thời. Ví dụ A1 và C10 cùng dùng `pump_water_line` (`scenario_resource_already_active`).

## 3. Bảng tám kịch bản

Ký hiệu: "node1" là cảm biến đất và khí hậu (DHT22). "node2" là bơm ảo, có đèn HOLD chân 25 và còi chân 26. "flow" là đồng hồ lưu lượng, có đèn cảnh báo chân 22 và còi chân 21. Thời gian bíp lấy từ sketch.

| Mã và tên | Workflow | Mạch nhận | Tín hiệu sai (trường, giá trị) | Đèn và còi | Log Serial mong đợi | Bắt đầu / dừng / phục hồi | Monitor và điều kiện |
|---|---|---|---|---|---|---|---|
| A1 · Tràn nước / quá lượng (`a1_water_overrun`) | W1 | node2 (HOLD) và flow (ALARM). node1 không nhận | flow `id3`: `f1` = 12.0 L/phút, `pressure_bar` = 0.2, `fault` = "high_flow_leak", `valve_open` = false. node2: không có số đo sai, `virtual_output` toàn 0 | flow: đèn 22 sáng, đèn 23 tắt, còi 21 một bíp 700 Hz 180 ms. node2: đèn HOLD 25 sáng, còi 26 hai bíp 700 Hz 130 ms cách 90 ms | node2: `virtual_plc_safety_trip ... state=HOLD cause=profile_fault ... scenario_code=A1 ... hold_led=1 pumps_on=0`; `PROFILE ACK ... -> fault applied=1 ...; pumps remain OFF`. flow: `virtual_plc_safety_trip device=velxio-flow-monitor-01 state=ALARM cause=profile_fault ... scenario_code=A1`; mỗi 5 giây `sample #N profile=fault flow=12.00 pressure=0.20 fault=high_flow_leak` | Bắt đầu: chọn "A1 · Tràn nước / quá lượng", theo mục 2. Dừng: "Dừng kịch bản". Phục hồi: node2 và flow nhận normal; node2 tự về sau 120 giây (`state=CLEAR cause=auto_revert`); flow chờ lệnh normal | W1 · 342734303 (tên không có trong file cục bộ đã đọc). Điều kiện: có sự kiện safety trip hoặc ACK mang đúng `scenario_run_id`, flow chuyển sang fault. Seed gắn W1 với greenhouse_a; cần xác minh phạm vi khi chạy trên greenhouse_j (chưa xác minh) |
| A2 · Bơm chạy nhưng áp suất bằng 0 (`a2_pump_pressure_zero`) | W1 | node2 (HOLD). Bridge không gửi profile cho flow với A2, nên nhánh A2 trong sketch flow không chạy | Chưa có trường sai trên chuỗi Velxio. node2 chỉ báo `safe_mode_active` = true và `virtual_output` toàn 0. `pressure_bar` = 0 khi bơm bật chỉ có trong bản tạo cloud của `demo_mode`, không đi qua Velxio | node2: đèn HOLD 25 sáng; các đèn bơm tắt; còi 26 hai bíp 700 Hz | node2: `virtual_plc_safety_trip ... state=HOLD cause=profile_fault ... scenario_code=A2 ...`; `PROFILE ACK ... -> fault applied=1 ...; pumps remain OFF` | Bắt đầu: chọn "A2 · Bơm chạy nhưng áp suất bằng 0". Dừng: "Dừng kịch bản". Phục hồi: node2 nhận normal, đèn 25 tắt, còi 1650 Hz 110 ms (`state=CLEAR cause=profile_normal`), hoặc tự về sau 120 giây | W1 · 342734303. Điều kiện: chưa có tín hiệu áp suất bằng 0 trên thiết bị Velxio, nên monitor có thể không bắt được qua chuỗi này (chưa xác minh) |
| A3 · Lưu lượng thấp khi bơm được lệnh chạy (`a3_low_flow`) | W1 | flow (ALARM). node1 và node2 không nhận | flow `id3`: `f1` = 0.1, `pressure_bar` = 0.3, `fault` = "low_flow", `valve_open` = false | flow: đèn 22 sáng, đèn 23 tắt, còi 21 một bíp 700 Hz 180 ms | flow: `virtual_plc_safety_trip device=velxio-flow-monitor-01 state=ALARM cause=profile_fault ... scenario_code=A3`; mỗi 5 giây `sample #N profile=fault flow=0.10 pressure=0.30 fault=low_flow` | Bắt đầu: chọn "A3 · Lưu lượng thấp khi bơm được lệnh chạy". Dừng: "Dừng kịch bản". Phục hồi: flow nhận normal (`state=CLEAR cause=profile_normal`), không tự về | W1 · 342734303. Điều kiện: có mẫu flow với `f1` = 0.1 và `fault` = "low_flow", mang `scenario_run_id` (chưa xác minh truy vấn monitor) |
| C10 · Áp suất và lưu lượng nước không khớp (`pipe_leak`) | W1 | flow (ALARM). Bridge ánh xạ C10 sang flow | Không khớp ý định. Sketch flow so khớp "A1", "water_overrun", "pipe_leak" nhưng không so khớp "C10", nên vào nhánh else: `f1` = 0.0, `pressure_bar` = 0.0, `fault` = "scenario_fault". Ý định theo catalog: áp suất thấp và lưu lượng cao | flow: đèn 22 sáng, còi 21 một bíp 700 Hz | flow: `virtual_plc_safety_trip ... state=ALARM cause=profile_fault ... scenario_code=C10`; mỗi 5 giây `sample #N profile=fault flow=0.00 pressure=0.00 fault=scenario_fault` | Bắt đầu: chọn "C10 · Áp suất và lưu lượng nước không khớp". Dừng và phục hồi như A3 | W1 · 342734303. Điều kiện: tín hiệu thực tế không có áp suất thấp kết hợp lưu lượng cao. Monitor có bắt được hay không phụ thuộc truy vấn (chưa xác minh). Nên đồng bộ mã trong sketch trước khi dùng |
| S2 · Cảm biến đất tăng đột biến (`soil_spike`) | W7 | node1 (cảm biến đất). Bridge ánh xạ S2 sang node1 | node1 `sh` = 95.0. `at` và `ah` giữ giá trị DHT22 thật. Bridge nhận được mẫu vì `sh` ≤ 100 | node1: đèn 23 sáng khi nhận lệnh, còi 22 một bíp 700 Hz 260 ms. Mẫu kế tiếp (trong 10 giây) đèn tắt lại nếu `at` < 32, `ah` < 75 và `sh` > 15 | node1: `DRILL ALERT profile=fault scenario_code=S2 scenario_run_id=<id>`; `DRILL OUTPUT LED23=HIGH BUZZER22=beep700Hz command_id=<cmd>`; `PROFILE ACK command_id=<cmd> scenario_run_id=<id> -> fault applied=1 sent=1 ...`; dòng JSON mẫu có `"sh":95.0` và `"profile":"fault"` | Bắt đầu: chọn "S2 · Cảm biến đất tăng đột biến". Dừng: "Dừng kịch bản". Phục hồi: node1 nhận normal (`DRILL RESTORED`, đèn 23 tắt, còi 1650 Hz 110 ms), hoặc `DRILL AUTO_REVERT` sau 120 giây (không có ACK) | W7 · 343594187 ("SMIOT \| W7 \| soil moisture advisory review required" theo monitors.tf). Điều kiện: bước tăng `sh` lớn hơn 20 so với mẫu trước (`spike_threshold` = 20.0 trong `demo_mode`), tức mẫu trước thấp hơn khoảng 75. PROGRESS.md ghi W7 cần envelope đã duyệt; seed gắn W7 với greenhouse_f node 2 (chưa xác minh) |
| S3 · Cảm biến đất ngoài miền vật lý (`soil_out_of_range`) | W7 | node1. Bridge ánh xạ S3 sang node1 | node1 `sh` = 150.0 (ngoài 0–100). Bridge loại mẫu này (`build_node_envelope`: "humidity is outside 0..100"), nên mẫu không tới `farm/sensor` | node1: như S2 (đèn 23 sáng khi nhận lệnh, còi 22 một bíp 700 Hz 260 ms; đèn tắt ở mẫu kế tiếp vì `sh` > 15) | node1: `DRILL ALERT ... scenario_code=S3`; `DRILL OUTPUT LED23=HIGH ...`; `PROFILE ACK ...`; dòng JSON mẫu có `"sh":150.0`. Bridge không ghi log khi loại mẫu | Bắt đầu: chọn "S3 · Cảm biến đất ngoài miền vật lý". Dừng và phục hồi như S2 | W7 · 343594187. Điều kiện: mẫu `sh` = 150 không đi qua bridge, nên monitor không nhận tín hiệu này từ Velxio (chưa xác minh cách monitor lấy dữ liệu) |
| Khí hậu quá ngưỡng, W8: C2 · Không khí khô hoặc ẩm bất thường (VPD ngoài dải) hoặc C6 · EC nước thoát tăng so với nước tưới | W8 | node1 theo nhánh C2/C6 của sketch. Bridge hiện không ánh xạ C2 và C6, nên không gửi SET_PROFILE và node1 không đổi | Khi nhận fault (theo sketch): `at` = 39.0 °C, `ah` = 88.0 %, `sec` = 3.8 | node1: đèn 23 sáng, còi 22 một bíp 700 Hz 260 ms. Mẫu kế tiếp `alert` = true (`at` ≥ 32), đèn giữ sáng; không có bíp 1800 Hz vì cờ `previousAlert` đã đặt | node1: `DRILL ALERT profile=fault scenario_code=C2` (hoặc C6); dòng JSON mẫu có `"at":39.0,"ah":88.0,"sec":3.80,"alert":true,"profile":"fault"` | Bắt đầu: chọn "C2 · ..." hoặc "C6 · ..." trong danh mục (không có mã "W8" trong danh mục). Dừng và phục hồi như S2 | W8 · 343594185 ("SMIOT \| W8 \| VPD and EC advisory review required" theo monitors.tf). Seed và PROGRESS.md gắn 343594185 với S3 greenhouse_g, mâu thuẫn với tên trong terraform (chưa xác minh). Điều kiện: có envelope giai đoạn đã duyệt trong MongoDB (`crop_cycles` đang active và `stage_envelopes` đã duyệt). Nếu không có, C2 trả "No approved, field-calibrated VPD band", không tạo finding |
| A4 · Lệnh chấp hành không có ACK (`a4_command_no_ack`) | W9 | node2 (bơm). Bridge ánh xạ A4 sang node2 | node2 không gửi `virtual_plc_command_ack` cho các lệnh SET_OUTPUTS, HOLD, CLEAR trong lúc A4. Catalog ghi `ack_received` = false, `target_value` = 1, `observed_value` = 0. ACK profile vẫn gửi với `applied` = true | node2: đèn HOLD 25 không sáng (A4 không đặt safe hold); còi 26 hai bíp 700 Hz (ACK profile). Không có bíp xác nhận 1650 Hz cho lệnh bị giữ ACK | node2: `virtual_plc_safety_trip ... state=CLEAR cause=profile_fault ... scenario_code=A4`; `PROFILE ACK ... -> fault applied=1 ...`. Khi có lệnh bị giữ: `ACK_SUPPRESSED command_id=<id> action=<SET_OUTPUTS/HOLD/CLEAR> scenario_code=A4 ... pumps_on=0 safe_hold=0` | Bắt đầu: chọn "A4 · Lệnh chấp hành không có ACK". Giao diện chặn lệnh bơm khi đang diễn tập, nên dòng ACK_SUPPRESSED chỉ xuất hiện nếu có lệnh khác tới node2 (nguồn chưa xác định). Dừng và phục hồi như A1 | W9 · 342734743 (tên không có trong file cục bộ; seed ghi "actuator_command_unacknowledged", greenhouse_j node 1). Điều kiện: cần lệnh có `command_id` đang chờ ACK và hết hạn 10 giây (`ack_deadline` trong plc.py). Luồng A4 từ trang web không tự tạo lệnh chờ. Đường `w9_drill` trong `demo_mode` cần cờ `w9_late_ack_drill` = true (chưa xác minh) |

## 4. Chỗ còn chưa rõ hoặc mâu thuẫn

1. Bridge chỉ ánh xạ A1–A4, C10, S2, S3, W8 và vpd_ec_risk. Không có S1 (soil_flatline), C2, C6 trong `SCENARIO_DEVICES`, nên các nhánh tương ứng trong sketch node1 không được kích hoạt qua bridge. W8 và vpd_ec_risk không phải mã trong catalog.
2. Sketch flow không so khớp mã "C10", nên C10 ra `scenario_fault` (f1 = 0, pressure = 0).
3. Bridge không gửi profile cho flow với A2, nên không có tín hiệu áp suất bằng 0 trên Velxio.
4. Bridge loại mẫu sh = 150 của S3 và không ghi log.
5. Khi không truyền `node_id`, `demo_mode` gán S và D sang node 2. Bridge lại gửi S2 và S3 sang node1. Hai đường này chưa thống nhất.
6. Tên monitor W8 (343594185) trong terraform là VPD/EC, nhưng seed và PROGRESS.md gắn ID này với S3 ở greenhouse_g. Phạm vi farm của các monitor (W1 greenhouse_a, W7 greenhouse_f, W8 greenhouse_g) khác greenhouse_j. Chưa đối chiếu truy vấn monitor do không gọi Datadog.
7. Tên của monitor W1 (342734303) và W9 (342734743) không có trong `monitors.tf` đã đọc.
8. Flow không có tự phục hồi 120 giây.
9. PROGRESS.md yêu cầu envelope đã duyệt cho W7 và W8. Chưa xác nhận điều này có áp dụng cho nhánh S2 và S3 hay không.
10. Ba sketch và bridge đã thay đổi trong lúc viết tài liệu (có bản cũ hơn). Tài liệu dựa trên bản đọc sau cùng.
11. Khi lease Velxio còn hạn (`SMIOT_EXTERNAL_SOURCE_LEASE_SECONDS`, mặc định 35 giây), bộ phát cloud không gửi dữ liệu node1, node2, flow của greenhouse_j. Dữ liệu Velxio là nguồn duy nhất trong thời gian đó.
