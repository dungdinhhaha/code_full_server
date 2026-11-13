# Kiểm chứng khẳng định MongoDB, sự cố và số liệu (02, 01) với mã nguồn

Phạm vi: chỉ đọc mã trong service/, pages/, main.py, scripts/, tests/, requirements.txt, deploy/datadog/. Không gọi mạng, không gọi Datadog, không đọc máy chủ MongoDB. Không in giá trị biến môi trường, token, khóa hay chuỗi kết nối.

Quy ước: đường dẫn tương đối tính từ D:\IOT Trung\code_full_server. "Khớp" = mã xác nhận đúng. "Sai" = mã mâu thuẫn với khẳng định. "Không kiểm được" = cần máy chủ, Datadog hoặc phép đếm chưa đủ căn cứ.

| # | Khẳng định (file, mục) | Mã đối chiếu (file:dòng) | Kết quả | Gợi ý sửa |
|---|---|---|---|---|
| 1 | 02 §1: tên database lấy từ MONGODB_DATABASE, mặc định smiot | service/mongodb_store.py:30 | khớp | - |
| 2 | 02 §1: pymongo >=4.0 và <4.18 | requirements.txt:11 | khớp | - |
| 3 | 02 §2: 25 collection nghiệp vụ + _counters = 26 tên khai báo | Đếm các lệnh collection()/db[...] trong service/, pages/, main.py, scripts/: 26 tên, gồm _counters tại service/mongodb_store.py:38,45 | khớp | - |
| 4 | 02 Bảng 2: telemetry ghi từ service/mongodb_telemetry.py và service/mqtt.py | service/mongodb_telemetry.py:93 (insert_one); service/mqtt.py:591 | khớp | - |
| 5 | 02 Bảng 2: operational_incidents có nguồn ghi service/incident_blackbox.py | service/incident_blackbox.py không có lệnh ghi nào (chỉ create_index, collMod, aggregate, find_one) | sai | Bỏ incident_blackbox.py khỏi cột nguồn ghi. Nguồn ghi thật: service/incident_lifecycle.py (nhiều dòng từ 57), service/scenario_evidence.py (69, 127, 141...), service/mqtt.py:1244,1276, service/special_incident_correlation.py |
| 6 | 02 Bảng 2: incident_telemetry_evidence có nguồn ghi service/incident_blackbox.py | Không có lệnh ghi trong incident_blackbox.py. Ghi thật: service/incident_lifecycle.py:127, service/scenario_evidence.py:183, 498 | sai | Đổi nguồn ghi thành incident_lifecycle.py và scenario_evidence.py |
| 7 | 02 Bảng 2: crop_cycles, crop_stage_media, lot_sensor_assignments có nguồn ghi service/auth.py | service/auth.py chỉ có create_index cho các collection này (auth.py:82-89). Ghi thật: service/demo_mode.py:173 (crop_cycles), service/traceability.py và scripts/seed_harvest_story.py (crop_stage_media), service/scenario_evidence.py:205 (lot_sensor_assignments) | sai | Sửa cột nguồn ghi theo file ghi thực tế; auth.py chỉ là nơi tạo index |
| 8 | 02 Bảng 2: action_ledger có nguồn ghi service/mqtt.py | service/mqtt.py không có lệnh ghi action_ledger. Ghi thật: service/operational_evidence.py:41, service/incident_lifecycle.py:335, main.py:589 | sai | Thay service/mqtt.py bằng main.py và service/incident_lifecycle.py |
| 9 | 02 Bảng 2: users, permissions, schedules, schedule_logs, notifications, inverter_mode có nguồn service/auth.py | service/auth.py:109-491 (collection("users"), "schedules", "schedule_logs", "notifications", "inverter_mode", "permissions") | khớp | - |
| 10 | 02 Bảng 2: operational_decisions ghi từ service/incident_lifecycle.py | service/incident_lifecycle.py:188 | khớp | - |
| 11 | 02 Bảng 2: findings ghi từ service/telemetry_findings.py | service/telemetry_findings.py:381 | khớp | - |
| 12 | 02 Bảng 2: scenario_runs, scenario_run_events, scenario_observations | service/scenario_evidence.py:58,273,445; service/mqtt.py:1194; main.py:366,470 | khớp | - |
| 13 | 02 Bảng 2: device_profile_events ghi từ service/mqtt.py | service/mqtt.py:679 | khớp | - |
| 14 | 02 Bảng 2: agronomic_advisories (service/agronomic_thresholds.py), traceability_events (service/traceability.py), stage_envelopes (service/stage_envelopes.py) | service/agronomic_thresholds.py:67; service/traceability.py:133-167; service/stage_envelopes.py:118-182 | khớp | - |
| 15 | 02 §3: service/auth.py hàm init_db có 19 lệnh create_index | service/auth.py:72-90 (19 dòng create_index) | khớp | - |
| 16 | 02 §3: INCIDENT_INDEX_SPECS có 11 khai báo | service/incident_blackbox.py:55-79 (11 mục) | khớp | - |
| 17 | 02 §3: HARDENING_INDEX_SPECS có 6 khai báo | service/incident_blackbox.py:91-105 (6 mục) | khớp | - |
| 18 | 02 §3: stage_envelopes có thêm 2 khai báo | service/stage_envelopes.py:125, 127 | khớp | - |
| 19 | 02 §3: tổng 36 lệnh khai báo (19 + 11 + 6) | Phép cộng trên dòng 15-17 | khớp | Ghi rõ 36 không gồm 2 khai báo của stage_envelopes |
| 20 | 02 §3, §6.1: unique partial active_incident_by_scope_unique, kind false_offline và service_down, status open/holding/recovering | service/incident_blackbox.py:93-94 (UNIQUE_ACTIVE_KINDS: line 87; ACTIVE_STATUSES: line 30) | khớp | - |
| 21 | 02 Bảng 3: partial active_incident_by_scope trên operational_incidents | service/incident_blackbox.py:55-58 | khớp | - |
| 22 | 02 Bảng 3: partial telemetry_by_incident_ts khi source.incident_id tồn tại | service/incident_blackbox.py:75-79 | khớp | - |
| 23 | 02 Bảng 3, §6.3: TTL scenario_api_idempotency trên created_at, 7 ngày | service/incident_blackbox.py:88, 100-102; created_at được ghi tại main.py (insert_one với created_at) | khớp | - |
| 24 | 02 Bảng 3, §6.3: TTL scenario_api_rate_limits trên updated_at, 24 giờ | service/incident_blackbox.py:89, 103-105; updated_at được ghi trong pipeline main.py:~222 | khớp | - |
| 25 | 02 Bảng 3: unique khác: users.username; crop_cycles.public_share_token (sparse); crop_stage_media (farm_key, lot_id, stage_code); stage_envelopes (crop_key, stage_code, cultivar, version) | service/auth.py:72, 82, 84; service/stage_envelopes.py:19, 125-126 | khớp | - |
| 26 | 02 Bảng 3: compound telemetry, action_ledger, findings | service/auth.py:77-78, 85; service/incident_blackbox.py:72, 95 | khớp | - |
| 27 | 02 §3: không đặt TTL cho notifications, schedules, schedule_logs, telemetry, operational_incidents, action_ledger | service/incident_blackbox.py:98-99 (comment); chỉ có TTL tại :100-105 | khớp | - |
| 28 | 02 §5: pipeline hộp đen có 7 nhánh $unionWith | service/incident_blackbox.py:345, 359, 373, 391, 412, 427, 472 | khớp | - |
| 29 | 02 §5: $setWindowFields kèm $shift trên nhánh telemetry, GAP_FACTOR = 3, chu kỳ 30 giây, dòng 472-480 | service/incident_blackbox.py:44 (GAP_FACTOR), :43 (DEFAULT_SAMPLE_INTERVAL_SECONDS=30), :477-480 | khớp | - |
| 30 | 02 §5: service/mongodb_showcase.py dòng 62-105, 239-241 | service/mongodb_showcase.py:62, 82, 105, 239, 241 | khớp | - |
| 31 | 02 §5: pages/farm_overview_component.py dòng 358, 393 ($group) | pages/farm_overview_component.py:358, 393 | khớp | - |
| 32 | 02 §5: pages/project.py dòng 43 ($group, $max) | pages/project.py:43 | khớp | - |
| 33 | 02 §5: service/traceability.py dòng 150 ($group) | service/traceability.py:150 | khớp | - |
| 34 | 02 §5: service/auth.py dòng 386 ($match regex, $group, $sum, $ifNull) | service/auth.py:386 | khớp | - |
| 35 | 02 §5: main.py dòng 213-223 (update pipeline với $cond, $add) | main.py:213-223 | khớp | - |
| 36 | 02 §5: scripts gdd_forecast, telemetry_quality_report, mongo_timeseries_benchmark dùng $setWindowFields và $shift | scripts/telemetry_quality_report.py:45-89; scripts/mongo_timeseries_benchmark.py:77-80; scripts/gdd_forecast.py:89 | khớp | Với gdd_forecast chỉ xác nhận $setWindowFields; $group chưa kiểm |
| 37 | 02 §5: mã ứng dụng không dùng $lookup, $facet, $graphLookup | Tìm trong *.py: không có kết quả | khớp | - |
| 38 | 02 §8: không dùng change streams | Tìm watch(, change_stream trong *.py: không có kết quả | khớp | - |
| 39 | 02 §8: không dùng transactions | Tìm start_session, with_transaction trong *.py: không có kết quả | khớp | - |
| 40 | 02 §8: không dùng Atlas Search, Vector Search, Triggers | service/incident_blackbox.py:12 (docstring); không có pipeline $search | khớp | - |
| 41 | 02 §6.2: $jsonSchema cho 6 collection (operational_incidents, action_ledger, notifications, scenario_runs, scenario_observations, scenario_run_events), validationAction=warn, validationLevel=moderate | service/incident_blackbox.py:108-217 (6 validator); :267-295 (apply, dùng collMod/create_collection với warn/moderate tại :285-289). Dẫn "dòng 110-290" là gần đúng | khớp | Ghi dòng 108-295 cho chính xác |
| 42 | 02 §2, §6.2: enum action_ledger (LEDGER_ACTIONS) và state (requested, published, acknowledged, failed, verified) | service/operational_evidence.py:15 (LEDGER_ACTIONS = HOLD, CLEAR, SAFE_STOP, SET_OUTPUTS, SET_VALVE, SET_VENT, SET_INVERTER); service/incident_blackbox.py:136 (enum theo LEDGER_ACTIONS); :137 và service/operational_evidence.py:11 (state). Hồ sơ không liệt kê giá trị enum | khớp | Có thể thêm bảng 7 giá trị LEDGER_ACTIONS nếu cần |
| 43 | 02 §6.3, 01 §6: Idempotency-Key bắt buộc, tối đa 200 ký tự | main.py:276-278 | khớp | - |
| 44 | 02 §6.3: băm token và key được lưu; trả lại kết quả cũ khi trùng | main.py:290 (sha256 của token_scope:key), :296-310 (replay, idempotent_replay) | khớp | Hồ sơ có thể nêu thêm 409 khi khác fingerprint (main.py:306) |
| 45 | 02 §6.3, 01 §6: giới hạn 20 lượt ghi, 120 lượt đọc mỗi token trong 60 giây | main.py:284 (write 20), main.py:452 (read 120), main.py:213-223 (cửa sổ 60_000 ms) | khớp | - |
| 46 | 02 §6.3: late-ACK W9 giới hạn 1 lượt | main.py:517 (_take_demo_api_rate_limit ... "w9-late-ack", 1) | khớp | - |
| 47 | 02 §6.3: scenario_api_farm_locks, _id là farm_key, một kịch bản mỗi nhà màng | main.py:379-394 (find_one và insert với _id farm_key), :422-427 | khớp | - |
| 48 | 02 §4: telemetry là time-series với timeField timestamp, metaField meta, granularity seconds; script chỉ chấp nhận đúng hai trường (dòng 115-139) | scripts/migrate_sqlite_telemetry_to_mongodb.py:115-139 (TIME_FIELD, META_FIELD, granularity "seconds" tại :120, :134) | khớp | - |
| 49 | 02 §4: ứng dụng ghi mẫu bằng insert_one vào telemetry, dòng 64-93 | service/mongodb_telemetry.py:64-93 (insert_one tại :93) | khớp | - |
| 50 | 01 §4 (Bảo mật): PBKDF2-HMAC-SHA256, 310.000 vòng, salt 16 byte | service/auth.py:35 (_PASSWORD_HASH_ITERATIONS = 310_000), :40 (salt 16 byte), :41 | khớp | Mã còn chấp nhận hash SHA-256 cũ (auth.py:46-54) và tự nâng cấp khi đăng nhập; hồ sơ không nêu, có thể bổ sung |
| 51 | 01 §4: 14 quyền cố định | service/auth.py:17-28 (FIXED_PERMISSIONS: 14 mục) | khớp | - |
| 52 | 01 §4: khóa đăng nhập tạm sau 5 lần sai | service/auth.py:215 (_LOGIN_MAX_FAILS = 5) | khớp | - |
| 53 | 01 §4: so sánh bằng hmac.compare_digest | service/auth.py:51, 55 (dòng compare_digest) | khớp | Xác nhận module là hmac hay secrets trước khi giữ nguyên chữ "hmac" |
| 54 | 01 §4: NICEGUI_STORAGE_SECRET bắt buộc khi APP_ENV=production | service/session_security.py:13-28: không có kiểm tra bắt buộc; khi thiếu chỉ ghi cảnh báo (có thêm chữ "bắt buộc trong production" trong thông báo) và dùng secret ngẫu nhiên theo tiến trình | sai | Sửa thành: khi thiếu, ứng dụng dùng secret ngẫu nhiên và cảnh báo; phiên đăng nhập mất khi khởi động lại. Không ghi là "bắt buộc" |
| 55 | 01 §4: cookie https_only khi production | service/session_security.py:31-33 | khớp | - |
| 56 | 01 §4: API kịch bản dùng Bearer <REDACTED_TOKEN>, chỉ bật khi SMIOT_DEMO_MODE=true | main.py:262-265: thiếu SMIOT_DEMO_CONTROL_TOKEN trả 503, sai token trả 401. SMIOT_DEMO_MODE chỉ xuất hiện ở main.py:499 (route /api/demo/w9/late-ack), không gate route /api/demo/scenarios | sai | Sửa: API kịch bản bật khi đã cấu hình SMIOT_DEMO_CONTROL_TOKEN; SMIOT_DEMO_MODE là điều kiện của route W9 late-ack |
| 57 | 01 §4 và Bảng 2 (trang sự cố): /incident/{id} chỉ dành cho admin | pages/incident.py:147-150: _is_admin trả True khi role là admin hoặc có quyền manage_users | sai | Sửa: "chỉ admin hoặc người có quyền quản lý người dùng" |
| 58 | 01 §4: /lot/{token} là trang công khai chỉ đọc | pages/public_lot.py:73 (@ui.page("/lot/{token}")) | khớp | - |
| 59 | 01 §1, Bảng 5: 16 route @ui.page | main.py + pages/*.py: 16 | khớp | - |
| 60 | 01 Bảng 1, Bảng 5: 10 route API @app | main.py: 10 route HTTP (dòng 128, 253, 440, 489, 613, 625, 698, 801, 960, 1010) + 1 @app.exception_handler (120) | khớp | Ghi rõ không tính exception_handler |
| 61 | 01 Bảng 1, Bảng 5: 15 module pages/ và 37 module service/ | pages/: 15 .py không tính __init__.py (16 file kể cả __init__); service/: 37 | khớp | Ghi rõ có hay không tính __init__.py |
| 62 | 01 Bảng 5: 62 file .py trong scripts/ | Đệ quy: 62; chỉ cấp 1: 59 | khớp | Ghi rõ đếm đệ quy |
| 63 | 01 Bảng 5: 41 file tests/test_*.py | tests/ (đệ quy): 41 | khớp | - |
| 64 | 01 §1, Bảng 5: 10 nhà màng greenhouse_a đến greenhouse_j | service/farm_registry.py: 10 dòng greenhouse_ | khớp | - |
| 65 | 01 Bảng 1, Bảng 5: 3 project Velxio | velxio/: node1_environment, node2_virtual_pump, node3_flow_monitor | khớp | - |
| 66 | 01 Bảng 1: chủ đề MQTT farm/sensor, farm/status, farm/command/ack, farm/demo/* | service/mqtt.py:939, 954, 1026, 1092, 1096; farm/command/ack tại main.py và service/mqtt.py (3 tham chiếu) | khớp | - |
| 67 | 01 Bảng 5: 19 metric DogStatsD gọi trực tiếp, 78 chuỗi smiot.* trong mã | service/datadog_metrics.py chỉ có 16 hàm def và 23 chuỗi "smiot."; không đếm được 19 lần gọi và 78 chuỗi trên toàn mã trong phạm vi kiểm này | không kiểm được | Ghi phương pháp đếm (ví dụ: đếm lần gọi emit_* và chuỗi smiot.* trong toàn service/) |
| 68 | 01 §2.1: metric smiot.telemetry.sequence_* thuộc service/telemetry_health.py | Chuỗi nằm ở service/datadog_metrics.py:257-259; service/telemetry_health.py không có chuỗi này | sai | Sửa nguồn dẫn thành service/datadog_metrics.py:257-259 |
| 69 | 01 Bảng 5: 36 kịch bản trong service/scenario_catalog.py (A7, C10, D7, H6, S6) | Tổng nhóm 7+10+7+6+6 = 36 khớp phép cộng, nhưng chưa đếm được số định nghĩa trong file (file 98 dòng) | không kiểm được | Đếm lại định nghĩa scenario trong service/scenario_catalog.py |
| 70 | 01 Bảng 5: 23 định nghĩa monitor dạng mã (17 + 5 + 1) trong deploy/datadog/terraform_* | Chưa đếm đầy đủ. Thấy monitors.tf và 2 file monitor_*.json; không đủ để xác nhận 17 + 5 + 1 | không kiểm được | Đếm resource "datadog_monitor" và monitor JSON theo thư mục deploy/datadog/ |
| 71 | 01 §2.1, §5, Bảng 2-3, Bảng 5: monitor, dashboard, workflow, số lần diễn tập, ID Datadog, số đếm trên giao diện | Dữ liệu từ Datadog API và giao diện (13/11/2026), không đối chiếu được với mã; không gọi Datadog theo yêu cầu | không kiểm được | Giữ nguồn "Datadog API, 13/11/2026" và ghi người đọc đã kiểm |
| 72 | 01 Bảng 1: ddtrace>=4.16.1,<5.0 | requirements.txt:12 | khớp | - |
| 73 | 01 §3.3: SMIOT_RECOVERY_INSTANCE_ID kiểm tra đúng máy chủ (main.py) | main.py:836 (expected_instance từ SMIOT_RECOVERY_INSTANCE_ID) | khớp | Biến AWS_REGION chưa kiểm trong phạm vi này |
| 74 | 01 §2.3, Bảng 4: khôi phục chỉ chạy systemctl start smiot.service | Lệnh chỉ thấy trong docs/DATADOG_GUARDED_RECOVERY.md:13, 48 và docs/DATADOG_MULTI_CAUSE_SCENARIOS.md:41-42. Không thấy lệnh tương ứng trong *.py (service/, main.py, scripts/) | không kiểm được | Trỏ đúng file thực thi lệnh hoặc ghi "theo tài liệu vận hành" |
| 75 | 01 §5: 10 ca sự cố (Ca 1-3, W1, W5-W10) | Bảng 2 của 01 liệt kê đủ 10 mã ca; không có số đếm riêng trong mã | khớp | - |
| 76 | 01 §5 Bảng 3: số lần diễn tập và phục hồi theo ca | Số đếm do ứng dụng ghi nhận (13/11/2026); không tái hiện được từ mã | không kiểm được | Giữ ghi chú "số đếm của ứng dụng tại thời điểm chụp" |
| 77 | 02 Bảng 1: 24 collection, 1 time-series, 23 collection có index, 0 validator trên máy chủ | Thuộc máy chủ, nằm ngoài phạm vi kiểm này (theo fact sheet) | không kiểm được | Giữ nguồn "đọc trực tiếp EC2, 13/11/2026" |
| 78 | 02 Bảng 4: số index trên máy chủ (operational_incidents 6, action_ledger 4, telemetry 4, stage_envelopes 3) | Thuộc máy chủ | không kiểm được | Giữ nguồn đọc trực tiếp |
| 79 | 02 §6.1: "Server đã có index unique partial" | Thuộc máy chủ | không kiểm được | Giữ nguồn đọc trực tiếp |
| 80 | 02 §5 Bảng 5: pipeline hộp đen xuất phát từ operational_incidents | service/incident_blackbox.py:834 đọc header bằng find_one trên operational_incidents; collection gốc của aggregate chưa đối chiếu đủ dòng | không kiểm được | Đối chiếu dòng aggregate gốc trong service/incident_blackbox.py:834-900 |

## Tổng kết

- Khớp: 62
- Sai: 8 (dòng 5, 6, 7, 8, 54, 56, 57, 68)
- Không kiểm được: 10 (dòng 67, 69, 70, 71, 74, 76, 77, 78, 79, 80)
- Tổng: 80 khẳng định

## Ba lỗi quan trọng nhất

1. 01 §4: NICEGUI_STORAGE_SECRET "bắt buộc" khi APP_ENV=production. Mã chỉ cảnh báo và dùng secret ngẫu nhiên (service/session_security.py:13-28).
2. 01 §4: API kịch bản "chỉ bật khi SMIOT_DEMO_MODE=true". Mã gate bằng SMIOT_DEMO_CONTROL_TOKEN (main.py:262-265); SMIOT_DEMO_MODE chỉ gate route W9 late-ack (main.py:499).
3. 02 Bảng 2: service/incident_blackbox.py được ghi là nguồn ghi của operational_incidents và incident_telemetry_evidence, nhưng file này không có lệnh ghi. Nguồn ghi thực là incident_lifecycle.py và scenario_evidence.py.
