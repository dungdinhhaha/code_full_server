# FACT SHEET - SMIOT Greenhouse Operations Center (nguồn cho bộ hồ sơ nộp)

**Ngày đọc:** 2026-11-13. **Dự án:** `D:\IOT Trung\code_full_server`. **Phạm vi:** chỉ đọc. Không sửa mã, không ghi trên EC2, không gọi POST/PUT/DELETE tới Datadog.

**Quy ước nguồn:** `[mã]` = đường dẫn tương đối trong dự án. `[EC2-GET]` = đọc Datadog bằng GET từ EC2 (13/11). `[EC2-FILE]` = file đọc qua SSM từ EC2 (chỉ `cat`). `[LỆNH]` = lệnh chạy trên máy local (chỉ đọc).

**Ký hiệu trạng thái:** ĐÃ KIỂM = đọc được trong mã hoặc dữ liệu hiện tại. CHƯA KIỂM = không đọc được hoặc không kiểm trong phiên này.

---

## 1. Bài toán và phạm vi

| Mục | Nội dung | Nguồn |
|---|---|---|
| Đối tượng | 10 nhà màng dưa lưới ảo, mã `greenhouse_a` đến `greenhouse_j` (10 mã) | `[service/farm_registry.py]` (đếm: 10); `[PRD.md]` mục Product |
| Bản chất | Mô phỏng vận hành. Thiết bị và cảm biến là ảo, trừ khi có nguồn vật lý được tích hợp và xác minh | `[PRD.md]` mục Product |
| Ba pha | Phát hiện (watchdog, sequence, heartbeat, monitor Datadog); Điều tra (hồ sơ sự cố, Datadog điều tra, MongoDB giữ bằng chứng); Phản ứng (lệnh có ACK, khôi phục có guard, xác minh phục hồi) | `[ARCHITECTURE.md]` Main data path; `[docs/submission/06_tong_quan_cham_diem.md]` |
| Ca trình diễn | Ca 1: báo offline sai (`false_offline`). Ca 2: độ ẩm đất Node 2 đứng yên (flatline). Ca 3: `smiot.service` dừng (khôi phục app có guard) | `[docs/submission/04_mo_ta_su_co_van_hanh.md]`; `[docs/submission/EVIDENCE_INDEX.md]` E-40 đến E-82 |
| Ngoài phạm vi | Không điều khiển bơm, van, quạt phần cứng thật. Không tự reboot EC2. Không hứa năng suất cây trồng | `[PRD.md]` mục Out of scope |
| Kịch bản diễn tập | 36 mã (xem mục 5) | `[service/scenario_catalog.py]` |

---

## 2. Kiến trúc thật

### 2.1 Thành phần (đã đối chiếu với mã)

| Thành phần | Thực tế trong mã | Nguồn |
|---|---|---|
| Ứng dụng | NiceGUI, `main.py` + 15 module trang trong `pages/` + 37 module trong `service/` + `components/` (4 module và `__init__.py`) | `[LỆNH]` đếm file |
| Trang giao diện | 16 route `@ui.page`: `/`, `/login`, `/incident`, `/incident/{incident_id}` (admin), `/inverter`, `/plc`, `/devices`, `/permission`, `/schedule`, `/history`, `/chart`, `/data`, `/projects`, `/mongodb-lab`, `/lot/{token}` (công khai, chỉ đọc), `/traceability` (chuyển hướng cũ) | `[main.py]`, `[pages/*.py]` |
| API HTTP | 10 route `@app`: `POST /api/js_error`, `POST /api/demo/scenarios`, `GET /api/demo/scenarios/{scenario_run_id}`, `POST /api/demo/w9/late-ack`, `GET /healthz`, `POST /api/integrations/datadog/w2-greenhouse-j/recover`, `POST .../verify`, `POST /api/integrations/datadog/recovery-verification`, `POST /api/internal/safe-mode/recovery-clear`, `POST /api/integrations/datadog/notification` | `[main.py]` |
| Thiết bị ảo | Mô phỏng nhúng trong ứng dụng: 9 nhóm thiết bị ảo mỗi nhà màng. Actuator ảo: bơm, van, quạt, lưu lượng, áp suất, thông gió | `[PRD.md]`; `[ARCHITECTURE.md]` |
| Cảm biến ESP32 (Velxio) | 3 project mô phỏng: `velxio/node1_environment` (cảm biến môi trường, DHT22), `velxio/node2_virtual_pump` (bơm ảo, ACK lệnh), `velxio/node3_flow_monitor` (lưu lượng). Bản sao output: `outputs/velxio_v2/` | `[LỆNH]` liệt kê thư mục; `[PROGRESS.md]` 12/11 và 13/11 |
| Cầu nối Velxio | `scripts/velxio_mqtt_bridge.py`: chuyển thông điệp Velxio sang envelope `farm/sensor`, chỉ chuyển lệnh trong danh sách cho phép, gắn `synthetic=true`, `source=velxio_synthetic` | `[scripts/velxio_mqtt_bridge.py]`; `[PROGRESS.md]` |
| MQTT | Ứng dụng kết nối `localhost:1883`. Chủ đề dùng trong mã: `farm/sensor`, `farm/status`, `farm/command/ack`, `farm/demo/control`, `farm/demo/evidence`, `farm/demo/status`, `farm/demo/device_profile/ack` | `[service/mqtt.py:249-250]`; `[ARCHITECTURE.md]`; `[EC2-FILE]` mqtt_topics_seen (13/11) |
| MongoDB | Community self-managed, `pymongo>=4.0,<4.18`. Database `MONGODB_DATABASE` (mặc định `smiot`) | `[service/mongodb_store.py]`; `[requirements.txt]` |
| Datadog | `ddtrace>=4.16.1,<5.0`, DogStatsD, log qua Agent đọc file, Datadog API đọc trạng thái monitor/workflow/dashboard | `[requirements.txt]`; `[service/observability.py]`; `[service/datadog_metrics.py]`; `[service/datadog_reader.py]` |
| AI | Gemini (`service/ai_service.py`), công cụ chỉ đọc (`service/ai_tools.py`), bot Telegram (`service/telegram_bot.py`) | `[service/ai_service.py]` |
| Thời tiết | Open-Meteo (`service/weather_api.py`), hiển thị nguồn, không hiện số mặc định khi lỗi | `[service/weather_api.py]`; `[pages/farm_overview_component.py:1358-1380]` |
| Triển khai | EC2 `ap-southeast-2`, dịch vụ `smiot.service`, file môi trường `/etc/smiot/app.env` (không ghi nội dung). Thư mục ứng dụng `/opt/smiot` | `[ARCHITECTURE.md]` Deployment model; `[EC2-FILE]` systemctl show (13/11) |

### 2.2 Luồng dữ liệu (theo mã và ARCHITECTURE.md)

```
Thiết bị ảo trong app / Velxio ESP32 (node1, node2, node3)
  -> MQTT (farm/sensor, farm/status, farm/command/ack)
  -> ingest + kiểm tra (service/mqtt.py, telemetry_provenance.py, telemetry_health.py)
  -> MongoDB: telemetry (mongodb_telemetry.py)   [ghi mẫu, gắn incident_id nếu có]
  -> watchdog + findings (telemetry_findings.py, detector_heartbeat.py)
  -> sự cố: operational_incidents (incident_lifecycle.py), hộp đen (incident_blackbox.py)
  -> Datadog: DogStatsD (smiot.*), ddtrace (span, log có incident_id), monitor
  -> workflow có guard (Datadog) -> lệnh MQTT có ACK, hoặc khôi phục dịch vụ qua endpoint có token
  -> xác minh: health + MongoDB + MQTT + telemetry mới (w3_recovery_verification.py)
  -> app: /incident/{id}, chuông thông báo (datadog_notifications.py, POST /api/integrations/datadog/notification)
```

Ghi chú: ARCHITECTURE.md nói Datadog "quan sát và điều phối"; khóa an toàn cục bộ (PLC ảo, interlock) do app giữ. Correlation ID đi trong log, span và document MongoDB, không đưa vào tag metric (cardinality).

---

## 3. MongoDB

### 3.1 Collection (26 tên xuất hiện trong mã; ĐÃ KIỂM bằng grep, CHƯA KIỂM trên DB sống)

Đếm: 18 tên qua `collection("...")` + 8 tên qua `db[...]`/`db.<tên>`. Bao gồm `_counters` (kỹ thuật).

| Collection | Mục đích | Ghi bởi (tham khảo) |
|---|---|---|
| telemetry | Mẫu cảm biến/node/nước/lưu lượng (Time Series khi tạo bằng script) | `service/mongodb_telemetry.py`, `service/mqtt.py` |
| operational_incidents | Hồ sơ sự cố (kind, status, farm_key, node_id, opened_at) | `service/incident_lifecycle.py`, `service/incident_blackbox.py` |
| incident_telemetry_evidence | Bằng chứng telemetry gắn sự cố | `service/incident_blackbox.py` |
| operational_decisions | Quyết định vận hành theo sự cố | `service/incident_lifecycle.py` |
| findings | Phát hiện từ watchdog | `service/telemetry_findings.py:381` |
| action_ledger | Sổ lệnh/hành động (requested, published, acknowledged, failed, verified) | `service/mqtt.py`, `service/operational_evidence.py` |
| scenario_runs | Lần chạy kịch bản (scenario_run_id, status) | `service/scenario_evidence.py:58`, `service/mqtt.py:1194` |
| scenario_run_events | Sự kiện ACK của kịch bản | `main.py`, `service/scenario_evidence.py` |
| scenario_observations | Quan sát kịch bản (execution_mode=SIMULATED_ONLY) | `service/scenario_evidence.py` |
| scenario_api_idempotency | Khóa idempotency cho API kịch bản (có TTL) | `main.py` |
| scenario_api_rate_limits | Giới hạn tốc độ API (có TTL) | `main.py` |
| scenario_api_farm_locks | Khóa theo nhà màng cho API kịch bản | `main.py` |
| device_profile_events | Sự kiện hồ sơ thiết bị (Velxio) | `service/mqtt.py` |
| notifications | Thông báo trong app (kể cả từ Datadog) | `service/auth.py`, `main.py` |
| users | Người dùng (mật khẩu PBKDF2) | `service/auth.py` |
| permissions | Danh mục quyền | `service/auth.py:109` |
| schedules | Lịch tưới | `service/auth.py` |
| schedule_logs | Nhật ký lịch tưới (actual_water, start_at) | `service/auth.py` |
| inverter_mode | Chế độ inverter ảo | `service/auth.py:300-301` |
| crop_cycles | Vòng đời mùa vụ, có public_share_token | `service/auth.py` |
| crop_stage_media | Ảnh theo giai đoạn | `service/auth.py` |
| traceability_events | Sự kiện truy xuất lô | `service/traceability.py` |
| lot_sensor_assignments | Gán cảm biến cho lô theo hiệu lực thời gian | `service/auth.py` |
| agronomic_advisories | Khuyến nghị nông học (advisory) | `service/agronomic_thresholds.py:67` |
| stage_envelopes | Khung môi trường theo giai đoạn cây (ghi có kiểm soát) | `service/stage_envelopes.py` |

### 3.2 Index (khai báo trong mã; CHƯA KIỂM index thật trên EC2)

Khai báo trong ba nơi, có chủ đích trùng lặp (comment trong mã): `service/auth.py` `init_db` (19 lệnh `create_index`, dòng 72-90); `service/incident_blackbox.py` `INCIDENT_INDEX_SPECS` (11); `HARDENING_INDEX_SPECS` (6). `stage_envelopes` có thêm 2 index, chỉ gọi khi thiết lập thủ công.

| Loại | Index | Nguồn |
|---|---|---|
| Unique partial | `operational_incidents`: `(kind, farm_key, node_id)`, unique, partial `status in [open, holding, recovering]` và `kind in [false_offline, service_down]` (`active_incident_by_scope_unique`) | `service/incident_blackbox.py` HARDENING |
| Partial (không unique) | `operational_incidents` `active_incident_by_scope` (partial status active); `telemetry` `telemetry_by_incident_ts` (partial `source.incident_id` exists) | `service/incident_blackbox.py` |
| TTL | `scenario_api_idempotency` `created_at`: 7 ngày (604800 s). `scenario_api_rate_limits` `updated_at`: 24 giờ | `service/incident_blackbox.py` |
| Unique khác | `users.username`; `crop_cycles.public_share_token` (sparse); `crop_stage_media (farm_key, lot_id, stage_code)`; `stage_envelopes (crop_key, stage_code, cultivar, version)` | `service/auth.py:72,82,84`; `service/stage_envelopes.py:125` |
| Compound | Ví dụ: `telemetry (meta.farm_key, meta.measurement_type, meta.node_id, timestamp)`; `action_ledger (incident_id, created_at)`; `findings (incident_id, detected_at)` | `service/auth.py`; `service/incident_blackbox.py` |

Không có TTL trên notifications, schedules, schedule_logs, telemetry, operational_incidents, action_ledger (chủ đích, theo comment trong mã).

### 3.3 Time Series

- **Có trong mã:** `scripts/migrate_sqlite_telemetry_to_mongodb.py:115-139` tạo collection `telemetry` dạng Time Series với `timeField=timestamp`, `metaField=meta`, `granularity=seconds`, và chỉ chấp nhận khi đúng hai trường này.
- **App ghi trực tiếp:** `service/mongodb_telemetry.py:64-93` dùng `insert_one` vào `telemetry`. Mã app không tự tạo Time Series.
- **Trạng thái trên EC2:** CHƯA KIỂM (không đọc được `listCollections` trên DB sống; xem mục 9).
- Benchmark: `scripts/mongo_timeseries_benchmark.py` (raw cursor so với aggregation `$setWindowFields`, dùng `executionStats`). Kết quả benchmark chưa có trong phiên này.

### 3.4 Aggregation pipeline

| File | Hàm/nơi | Toán tử chính | Mục đích |
|---|---|---|---|
| `service/incident_blackbox.py` | `build_incident_timeline` và các hàm builder `$unionWith` (dòng 345-472) | `$unionWith` x7 nhánh: incident_telemetry_evidence, operational_decisions, findings, action_ledger, scenario_run_events, scenario_observations, telemetry. `$setWindowFields` + `$shift` (dòng 472-480) trên telemetry | Hộp đen sự cố; đánh dấu khoảng thiếu mẫu (GAP_FACTOR=3, chu kỳ 30 giây) |
| `service/mongodb_showcase.py` | dòng 62-105, 239-241 | `$setWindowFields`, `$shift`, `$group` | Độ phủ dữ liệu theo ngày; GDD lũy kế; nhiệt độ trung bình trượt 7 ngày |
| `pages/farm_overview_component.py` | dòng 358, 393 | `$group` theo nhóm thời gian và farm | Tổng quan 10 nhà màng |
| `pages/project.py` | dòng 43 | `$group`, `$max` | Lần mẫu gần nhất theo farm |
| `service/traceability.py` | dòng 150 | `$group` | Truy xuất lô |
| `service/auth.py` | dòng 386 | `$match` (regex), `$group`, `$sum`, `$ifNull` | Tổng nước tưới theo ngày |
| `main.py` | dòng 213-223 | update pipeline với `$cond`, `$add` | Giới hạn tốc độ API kịch bản (cửa sổ 60 giây) |
| `scripts/gdd_forecast.py`, `scripts/telemetry_quality_report.py`, `scripts/mongo_timeseries_benchmark.py` | các pipeline | `$group`, `$setWindowFields`, `$shift` | Báo cáo và dự báo (script ngoài app) |

Không thấy `$lookup`, `$facet`, `$graphLookup` trong mã app.

Ghi chú sửa tài liệu: `docs/submission/01` và `02` (và E-16 trong EVIDENCE_INDEX) ghi "$unionWith 4 nhánh". Mã hiện có 7 nhánh (dòng 345-472). Docstring đầu file vẫn nêu danh sách ngắn hơn. Cần đối chiếu trước khi nộp.

### 3.5 Các tính năng khác

| Tính năng | Trạng thái | Căn cứ |
|---|---|---|
| Change streams | Không dùng | Không có `watch(` hoặc `change_stream` trong mã |
| Transactions | Không dùng | Không có `start_session` hoặc `with_transaction` trong mã |
| Replica set | CHƯA KIỂM. Tài liệu ghi "self-managed", chưa đọc topology | `service/incident_blackbox.py:3-12`; EVIDENCE_INDEX E-80 |
| `$jsonSchema` | Có định nghĩa cho 6 collection (`operational_incidents`, `action_ledger`, `notifications`, `scenario_runs`, `scenario_observations`, `scenario_run_events`). Áp dụng ở chế độ `validationAction=warn`, `validationLevel=moderate` (không chặn ghi). Đã áp dụng trên EC2: CHƯA KIỂM | `service/incident_blackbox.py:110-290`; `scripts/apply_mongo_hardening.py` |
| Atlas Search, Vector Search, Triggers | Không dùng (ghi rõ trong docstring) | `service/incident_blackbox.py:11-12` |

---

## 4. Datadog

### 4.1 Dashboard

| Nguồn | Tên | ID | Ghi chú |
|---|---|---|---|
| Live, GET 13/11 | SMIOT \| 10-Farm Portfolio | `rzf-su8-zgf` | [EC2-GET] |
| Live, GET 13/11 | SMIOT \| Farm Data Quality | `g8w-hj8-px7` | [EC2-GET] |
| Live, GET 13/11 | SMIOT \| IoT & MQTT Fleet | `kzx-fwc-sai` | [EC2-GET] |
| Live, GET 13/11 | SMIOT \| Incident & Recovery | `isq-rzw-a6s` | [EC2-GET] |
| Live, GET 13/11 | SMIOT \| App, EC2, MongoDB & AI | `mzj-a5m-yh9` | [EC2-GET] |
| Snapshot 08/11 | SMIOT \| Farm Operations & Recovery (US) | `nkc-685-vw8` | Không thấy trong danh sách 13/11 (chỉ đối chiếu theo tên). Tài liệu 06/11 (E-52) vẫn dùng ID này |
| Local | 5 file JSON trong `deploy/datadog/terraform_farm_control_center/dashboards/` (app-mongodb-ai 7 widget, farm-data-quality 5, farm-portfolio 6, incident-recovery 6, iot-mqtt-fleet 7). Thêm 1 `datadog_dashboard_json` "smiot_additional" trong `main.tf:30` | File không có trường `id` |

Ghi chú: `docs/submission/` ghi "dashboard 8 widget (04/11)" (E-03). Số widget hiện tại theo file JSON là 5-7 mỗi dashboard. Cần đối chiếu trước khi nộp.

### 4.2 Monitor

**a) Live (GET 13/11, org đọc bằng khóa trên EC2):** 30 monitor trong org, 19 monitor có "SMIOT" trong tên.

| ID | Tên (rút gọn) | Loại | Ưu tiên | Trạng thái lúc đọc | Ghi chú rủi ro |
|---|---|---|---|---|---|
| 342585819 | SMIOT \| sensor flatline | query alert | - | OK | Flatline Node 2 (Ca 2). Được S3 (12/11) ghi là monitor cảnh báo |
| 342585820 | telemetry not fresh | query alert | - | OK | |
| 342585822 | telemetry ingest lag | query alert | - | OK | |
| 342585823 | persisted sample rate missing | query alert | - | OK | |
| 342585824 | AI ask latency high | query alert | - | **No Data** | Chưa có dữ liệu đo |
| 342585825 | PLC command latency high | query alert | - | **No Data** | Chưa có dữ liệu đo |
| 342585827 | MongoDB dependency unhealthy | query alert | - | OK | |
| 342585828 | MQTT dependency unhealthy | query alert | - | OK | |
| 342585830 | air temperature telemetry absent | query alert | - | OK | |
| 342585831 | telemetry sample stale | query alert | - | OK | |
| 342585835 | soil humidity telemetry absent | query alert | - | OK | |
| 342585836 | telemetry status mismatch | query alert | - | OK | Thay thế monitor Ca 1 (341409441) trong tài liệu 06/11 |
| 342585837 | soil temperature telemetry absent | query alert | - | OK | |
| 342585838 | smiot.service inactive | query alert | - | OK | Gắn cho Ca 3 |
| 342734303 | virtual PLC safety trip (W1) | query alert | 2 | OK | Dùng trong diễn tập A1-A3, C10, A2 |
| 342734743 | actuator command unacknowledged (W9) | query alert | 2 | OK | Dùng trong diễn tập A4 |
| 343029221 | W6 \| Detector evaluation stalled | query alert | 2 | OK | Heartbeat detector (W6) |
| 343594185 | W8 \| VPD and EC advisory review required | query alert | - | **Alert** | Lúc đọc đang Alert. Đây là monitor "W8 chưa đọc" trước đây |
| 343594187 | W7 \| soil moisture advisory review required | query alert | - | **Alert** | Lúc đọc đang Alert. Monitor của S2/S3 (W7) |

Trạng thái trên là ảnh chụp lúc 13/11, không phải kết quả diễn tập.

**b) Monitor ID trong tài liệu cũ không có trong danh sách live 13/11:** 339977691, 339977703, 339990226, 339990232, 340356283, 341409441 (E-50, E-70) và 6 monitor snapshot 08/11 (339687539-341409441). ID live nằm trong dải 342585819-343594187. Cần đối chiếu trước khi nộp (mục 8).

**c) Infrastructure as Code (không có ID; ID chỉ có sau apply):**

| File | Số monitor định nghĩa | Ghi chú |
|---|---|---|
| `deploy/datadog/terraform_monitors/monitors.tf` | 17 (16 trong `for_each` + 1 `detector_heartbeat` W6, dòng 172) | Message có `@workflow-smiot-...` nối workflow. Một số monitor có "No Data" hoặc dễ báo sai nếu thiếu dữ liệu |
| `deploy/datadog/terraform_scenarios/terraform.tf` | 5 (Virtual PLC protective stop; safety trip/ACK imbalance; device reboot; telemetry sequence gap; duplicate/regressing sequence) | Chưa đối chiếu với live |
| `deploy/datadog/terraform_w2_greenhouse_j/main.tf` | 1 (W2 greenhouse_j sensor flatline) | Có 1 `datadog_workflow_automation` |

Tổng định nghĩa IaC: 23. Số monitor trên live: 19 SMIOT (30 trong org). Khác biệt chưa đối chiếu từng cái.

**d) Snapshot 08/11** (`docs/datadog_config_snapshot/20261108T150159Z/`): 17 monitor, 1 dashboard, 3 workflow, 1 SLO. Gồm 7 monitor hạ tầng (CPU, đĩa, tải, mạng, bộ nhớ) và 10 monitor SMIOT/APM.

### 4.3 Workflow

**a) Live (GET 13/11):** 10 workflow tên "SMIOT", tất cả published.

| ID | Tên | Ghi chú |
|---|---|---|
| ffd62026-6b63-40e4-9b46-6ac18d2d584f | SMIOT \| Ca 1 \| Refuse restart when samples are fresh | Ca 1. Tài liệu 06/11 ghi ID khác (e2835af0-...) |
| 2f9a3c1d-5292-4bc3-b4b9-cc03d4172724 | SMIOT \| Ca 2 \| Confirm local interlock | Ca 2. Tài liệu ghi ID khác (18d1b008-...) |
| 373ed0c0-4509-4fcd-a067-f54f0becc00e | SMIOT \| Guarded EC2 app recovery | Ca 3 (`b83453ff-...` trong tài liệu). PROGRESS 12/11 nhắc ID này |
| 50b3dc85-dd20-4220-bda1-ec78d2a3d00f | SMIOT \| W10 \| AI failure safety verification | |
| b9e72b04-1580-45f8-ae1e-628124a19065 | SMIOT \| W1 \| Verify PLC safety trip evidence | |
| d3f0705e-2cbd-430a-9a3a-b1fd02a42cc9 | SMIOT \| W5 \| Root cause dependency triage | |
| d8e1b3db-1a54-4b4f-9be3-bf7e270a86f3 | SMIOT \| W6 \| Detector heartbeat review | |
| bb86206c-6df8-4b1d-8016-175a2fc62e49 | SMIOT \| W7 \| Irrigation schedule evidence review | |
| 593a670c-d59c-4104-8658-df260245a21e | SMIOT \| W8 \| Crop climate and EC evidence review | |
| 47e95b24-db40-4cd5-b667-5b90e170b667 | SMIOT \| W9 \| Actuator acknowledgement verification | |

**b) Local:** `deploy/datadog/terraform_w2_greenhouse_j/w2-greenhouse-j.json` (1 workflow, 12 bước theo key `steps`); `deploy/datadog/drafts/workflow_guard_branches.md` (bản nháp).

**c) Snapshot 08/11:** 3 workflow (`18d1b008-...` Node 2 Safe Mode - Hold and Verify; `b83453ff-...`; `e2835af0-...` Ca 1 Refuse restart). Mỗi file có 1 bước HTTP (`com.datadoghq.http.request`) trỏ tới endpoint của app. Xem mục 6 về token trong file này.

### 4.4 Metric DogStatsD (`service/datadog_metrics.py`)

Gửi qua DogStatsD, cổng `DD_DOGSTATSD_PORT` (mặc định 8125). 19 tên được gọi trực tiếp trong file này:

`smiot.actuator.fan_rpm`, `smiot.actuator.flow_lpm`, `smiot.actuator.pressure_bar`, `smiot.actuator.pump_on`, `smiot.actuator.safe_mode_active`, `smiot.actuator.total_volume_l`, `smiot.actuator.valve_open`, `smiot.actuator.vent_command`, `smiot.actuator.vent_state`, `smiot.crop.envelope.approved`, `smiot.crop.soil_moisture.review_required`, `smiot.crop.stage_context.valid`, `smiot.crop.vpd_ec.review_required`, `smiot.crop.vpd_kpa`, `smiot.device.reboot_detected`, `smiot.device.uptime_seconds`, `smiot.telemetry.sequence_duplicate`, `smiot.telemetry.sequence_gap`, `smiot.telemetry.sequence_regression`.

Toàn bộ chuỗi `smiot.*` xuất hiện dưới dạng literal trong `service/`, `scripts/`, `main.py`, `pages/`: **78 tên duy nhất** (đếm bằng grep). Gồm các metric trên và thêm tên như `smiot.telemetry.samples_persisted`, `smiot.telemetry.ingest_lag_ms`, `smiot.telemetry.sample_age_seconds`, `smiot.telemetry.status_mismatch`, `smiot.telemetry.sensor_flatline`, `smiot.detector.*`, `smiot.dependency.mongo.up`, `smiot.dependency.mqtt.up`, `smiot.external.sample_age_seconds`, `smiot.actuator.command_acknowledged`, `smiot.actuator.command_late_acknowledged`, `smiot.actuator.command_unacknowledged`, `smiot.ai.*`, `smiot.virtual_plc.safety_trip`, `smiot.virtual_plc.safety_ack`, `smiot.safe_mode.transition`, `smiot.velxio.bridge`. Một số là tên span hoặc sự kiện log, không phải metric. CHƯA PHÂN LOẠI từng tên.

Nhãn (tag) theo docstring: farm, node, source (bounded). Correlation ID đi trong log và span, không dùng làm tag metric.

### 4.5 APM, ddtrace, LLM Observability

- **APM: CÓ.** `service/observability.py:24-47`: bật bằng `DATADOG_APM_ENABLED`; `DD_SERVICE=smiot-smart-farm`, `DD_ENV=demo`, `DD_VERSION=1.0.0`, `DD_TRACE_AGENT_URL=http://127.0.0.1:8126`, `DD_LOGS_INJECTION=true`, `ddtrace.patch_all()`.
- **Span tùy chỉnh:** `trace_span` (`service/observability.py:86-131`) dùng trong `service/mqtt.py` (`mqtt.message.process`, dòng 1122-1126), `service/ai_service.py` (`gemini.generate_content`, `smiot.ai.tool`), `service/incident_lifecycle.py` (lấy trace_id, dòng 388-390), `service/special_incident_correlation.py`.
- **LLM Observability: CÓ, có điều kiện.** `DATADOG_LLMOBS_ENABLED`; `ml_app=smiot-smart-farm` (`service/observability.py:50-82`, `service/ai_service.py:218-267`). Nội dung được che (theo E-19).
- **Log:** CÓ. Qua Agent đọc file: `deploy/datadog/smiot-logs.yaml` (`incident_events.jsonl`, `recovery/*.jsonl`, `service smiot-smart-farm`). PROGRESS 12/11 ghi đã thêm `system.log`, `error.log` vào cấu hình Agent trên EC2.
- **Đọc từ Datadog trong app:** `service/datadog_reader.py` gọi `/api/v2/events` (`filter[query]=monitor_id:...`) và `/api/v2/logs/events` (lọc theo chuỗi incident_id). PROGRESS 12/11: quyền `events_read` và `logs_read_data` cần có; thiếu thì hiện 403.

---

## 5. Kịch bản và diễn tập

### 5.1 Danh mục kịch bản

**36 mã** trong `service/scenario_catalog.py`, đếm bằng lệnh đọc (`len(scenario_catalog())` = 36; `len(scenario_codes())` = 36).

| Nhóm | Mã | Số | Nguồn module |
|---|---|---|---|
| Nhóm A | A1-A7 | 7 | `service/scenario_domain_actuator_infra.py` |
| Nhóm C (cây trồng) | C1-C10 | 10 | `service/scenario_domain_crops.py` |
| Nhóm D (thiết bị) | D1-D7 | 7 | `service/scenario_domain_sensor_device.py` |
| Nhóm H | H1-H6 | 6 | `service/scenario_domain_actuator_infra.py` (cùng module với A1-A7) |
| Nhóm S | S1-S6 | 6 | `service/scenario_domain_sensor_device.py` |

Ghi chú: docstring nêu 36, phù hợp với đếm. Tổng 7+10+7+6+6 = 36.

### 5.2 Kết quả diễn tập đo được (hai file trên EC2)

Nguồn: `[EC2-FILE]` `/opt/smiot/outputs/drill_suite_20261112T225228Z.json` (8 dòng, ghi 12/11) và `/opt/smiot/outputs/drill_suite_pump_20261113T023126Z.json` (3 dòng, ghi 13/11). Nhà màng: greenhouse_j. Tham số chung: `hold=90 s`, `dd_wait=360 s`.

**QUAN TRỌNG:** mọi con số dưới đây là DỮ LIỆU DIỄN TẬP (một lần chạy cho mỗi mã). Không phải ngưỡng đã duyệt. Thời gian đo bởi script diễn tập. Các mã "bỏ qua" không được tính là kết quả.

**Bảng A. Suite 12/11/2026 (`drill_suite_20261112T225228Z.json`)**

| Mã | Kịch bản | Monitor DD | Mạch nhận | ACK | Phát hiện DD (s) | Phục hồi app (s) | DD về OK sau (s) | Hồ sơ (trạng thái) | Ghi chú nguồn |
|---|---|---|---|---|---|---|---|---|---|
| A1 | a1_water_overrun | W1 342734303 | Thiếu node2 | Bỏ qua | - | - | - | - | Không chạy: không có telemetry velxio_synthetic 60 s cho node2 |
| A2 | a2_pump_pressure_zero | W1 | Thiếu node2 | Bỏ qua | - | - | - | - | Không chạy (như A1) |
| A3 | a3_low_flow | W1 | flow | Started, applied | 109.8 | 1.4 | 317.6 | INC-SMIOT-SCENARIO-9F3A2859A819F323 (open) | Chờ 127 s monitor về OK trước START. Có CLEAR safe mode. 0 mẫu Mongo có scenario_run_id |
| C10 | pipe_leak | W1 | flow | Started, applied | 79.1 | 1.5 | 286.5 | INC-SMIOT-SCENARIO-B840598BD9CF6644 (holding) | Có CLEAR safe mode. 0 mẫu Mongo có scenario_run_id |
| S2 | soil_spike | W7 343594187 | node1 | Started, applied | Không phát hiện trên DD | 13.0 | Không áp dụng | INC-SMIOT-SCENARIO-676B9F7C0FCE4434 (open) | DD ở OK, không Alert |
| S3 | soil_out_of_range | W7 343594187 | Chưa thấy mẫu fault | Started, applied | 0.6 (monitor 342585819 "sensor flatline" Alert) | 13.2 | Không về OK | INC-SMIOT-SCENARIO-5E92235C67178079 (open) | Monitor báo là flatline, không phải W7. Cần ghi rõ khi trình bày |
| C2 | scenario_type C2 | W8 343594185 | node1 | Started, applied | Không phát hiện trên DD | 12.1 | Không áp dụng | INC-SMIOT-SCENARIO-E6C842D9B25E0F29 (open) | DD ở OK |
| A4 | a4_command_no_ack | W9 342734743 | Thiếu node2 | Bỏ qua | - | - | - | - | Không chạy (như A1) |

Chung: 0 mẫu Mongo có scenario_run_id ở các mã đã chạy (trường `mẫu_mongo_có_scenario_run_id`). Số quan sát scenario_observations: 1 đến 2 mỗi mã. MQTT thấy: farm/sensor 3407, farm/status 4693, farm/command/ack 6.

**Bảng B. Suite bơm 13/11/2026 (`drill_suite_pump_20261113T023126Z.json`)**

| Mã | Mạch nhận | ACK bơm (s sau T0) | Phát hiện DD (s) | DD về OK sau (s) | Phục hồi app (s) | Hồ sơ (trạng thái) | Ghi chú nguồn |
|---|---|---|---|---|---|---|---|
| A1 | node2 (ACK) + flow | 1.0 | Không Alert | Không áp dụng | 4.2 | INC-SMIOT-SCENARIO-9D18A090182D7BC4 (open) | Log: velxio_profile_ack_forwarded, device=node2, profile=fault, verified=True |
| A2 | node2 (ACK) | 0.55 | 79.1 | 286.3 | Không áp dụng (không có health_60s) | INC-SMIOT-SCENARIO-B4D3B09D9FB6BCA0 (holding) | Có CLEAR safe mode |
| A4 | node2 (ACK) | 0.65 | Không Alert | Không áp dụng | Không áp dụng | INC-SMIOT-SCENARIO-3A00032EB64EEF03 (open); 6 observations | SET_OUTPUTS bit0=1 sau START 5 s, bit0=0 sau khi W9 hết hạn. T_stop 360.3 s sau T0 |

Chung: `final_cleanup` đã gửi SET_OUTPUTS bit0=0 và CLEAR. MQTT thấy: farm/sensor 1823, farm/status 2458, farm/command/ack 13, farm/demo/device_profile/ack 8.

**Điểm cần ghi khi trình bày:**
- Kết quả 13/11 là cầu nối Velxio và ACK từ mô phỏng node2. Không có thiết bị vật lý.
- Ở suite 12/11, A1, A2, A4 bị bỏ qua vì mạch node2 thiếu. Suite 13/11 đo lại A1, A2, A4 sau khi node2 có ACK.
- A4 đã đo ngày 13/11 nhưng W9 không Alert nên không có "độ trễ phát hiện".
- Số liệu DD chỉ đo qua trạng thái monitor đọc theo chu kỳ, không phải thời điểm chính xác của sự kiện.

### 5.3 Ba ca trình diễn (theo tài liệu hồ sơ, chưa đối chiếu lại từng ID)

| Ca | Kịch bản | Monitor | Workflow | Bằng chứng (theo EVIDENCE_INDEX, 06/11) |
|---|---|---|---|---|
| Ca 1 - báo offline sai | Trạng thái UI OFFLINE nhưng mẫu vẫn vào MongoDB | 341409441 (cũ). Live: `telemetry status mismatch` 342585836 | Ca 1 workflow (ID cũ e2835af0; live ffd62026) | E-55, E-81 (Alert 04:49:21Z, OK 05:00:21Z, các lượt workflow) |
| Ca 2 - độ ẩm đất Node 2 đứng yên | Flatline 10 mẫu, 0,01, 600 s | 6 monitor cũ; live `sensor flatline` 342585819 | Ca 2 workflow (ID cũ 18d1b008; live 2f9a3c1d) | E-40, E-41, E-56 (kết quả một phần, chưa xác nhận recovered) |
| Ca 3 - smiot.service dừng | App dừng, khôi phục có guard, xác minh bằng health và Mongo | 340356283 (cũ). Live `smiot.service inactive` 342585838 | Guarded EC2 app recovery (live 373ed0c0; cũ b83453ff) | E-59, E-82 (Alert 03:11:43Z, OK 03:13:43Z; lệnh EC2 thành công nhưng đầu ra chưa đọc được trong 06/11) |

---

## 6. Bảo mật

### 6.1 Cơ chế đã có

| Cơ chế | Chi tiết | Nguồn |
|---|---|---|
| Băm mật khẩu | PBKDF2-HMAC-SHA256, 310.000 vòng, salt 16 byte. Hash SHA-256 không muối cũ được nâng cấp khi đăng nhập đúng | `service/auth.py:35-55, 129-139` |
| So sánh an toàn | `hmac.compare_digest` (mật khẩu); `secrets.compare_digest` (bearer token) | `service/auth.py`; `main.py:195-196` |
| Khóa đăng nhập tạm | 5 lần sai trong cửa sổ thời gian thì khóa tạm. Theo tiến trình (không dùng chung giữa nhiều instance) | `service/auth.py:213-238` |
| Phân quyền | 14 quyền cố định (view_dashboard, inverter x3, pump_1..pump_7_control, manage_users, manage_schedule, export_schedule_logs). Vai trò preset admin/operator/viewer. Phạm vi nhà màng theo người dùng | `service/auth.py:17-35` (FIXED_PERMISSIONS, ROLE_PRESETS, FARM_PRESETS) |
| Chặn leo quyền | `check_user_change`: chỉ admin mới thao tác tài khoản admin hoặc gán vai trò admin | `service/auth.py:191-205` |
| Trang sự cố | `/incident/{id}` chỉ admin | `pages/incident.py` (E-17); `[PRD.md]` |
| Khóa session | `NICEGUI_STORAGE_SECRET` bắt buộc khi `APP_ENV=production`; không có khóa mặc định; cookie `https_only` ở production | `service/session_security.py:9-33`; `main.py:1212-1214` |
| Bearer token API kịch bản | Biến `SMIOT_DEMO_CONTROL_TOKEN` (riêng, không phải mật khẩu người dùng). Chỉ bật khi `SMIOT_DEMO_MODE=true` | `main.py:193-196, 499-501` |
| Idempotency | `Idempotency-Key` bắt buộc (tối đa 200 ký tự); băm token + key lưu trong Mongo; trả replay khi trùng | `main.py:259-281`; `scenario_api_idempotency` |
| Giới hạn tốc độ | API kịch bản: 20 ghi và 120 đọc mỗi token trong 60 giây; late-ACK W9: 1 lượt. Lưu trong `scenario_api_rate_limits` (Mongo) | `main.py:284, 452, 517, 204-230` |
| Khóa theo nhà màng | `scenario_api_farm_locks` (`_id` = farm_key). Một kịch bản mỗi nhà màng | `main.py:379-427` |
| Token thông báo Datadog | `DATADOG_APP_NOTIFICATION_TOKEN` cho endpoint nhận sự kiện Datadog | `main.py:628, 701, 811, 1017` |
| Token khôi phục safe mode | `SAFE_MODE_RECOVERY_TOKEN` | `main.py:963` |
| Khóa đúng instance | `SMIOT_RECOVERY_INSTANCE_ID` và `AWS_REGION` (mặc định ap-southeast-2) cho khôi phục EC2 | `main.py:836-847` |
| Khôi phục dịch vụ có guard | Chỉ `systemctl start smiot.service`, có lock và cooldown, allowlist sudoers, readback MongoDB. Thiết kế trong tài liệu; chi tiết script chưa đọc đầy đủ | `docs/DATADOG_GUARDED_RECOVERY.md` (E-43); `scripts/aws/smiot-recover-guarded.sh` (E-24) |
| Nhãn nguồn | Mọi mẫu Velxio và kịch bản gắn `synthetic=true`, `source` (ví dụ `velxio_synthetic`) | `service/telemetry_provenance.py:91-104`; `scripts/velxio_mqtt_bridge.py` |
| Log truy cập | Middleware ghi access log | `service/middleware.py` |
| Bí mật không ghi vào mã | Giá trị token, khóa, URI đọc từ biến môi trường. Không có khóa mặc định trong mã | `service/mongodb_store.py:22`; `main.py` |

### 6.2 Rủi ro còn lại (ghi trung tính, cần xử lý trước khi nộp)

1. **Token trong snapshot Datadog (cần xử lý trước khi nộp).** File `docs/datadog_config_snapshot/20261108T150159Z/json/workflows/18d1b008-fb24-4713-aa0b-a1432d84ea80.json` chứa một header `Authorization` với giá trị bearer dạng chuỗi. Manifest ghi `secret_like_values_replaced: 0`. Giá trị không được ghi lại ở đây. Cần che hoặc xóa file (hoặc thay bằng biến). Nếu token đã dùng ở môi trường thật, nên xoay vòng. Quyết định thuộc người dùng.
2. **MQTT trên EC2 chưa kiểm cấu hình listener.** Mã ứng dụng kết nối `localhost:1883` không có `username_pw_set` trong `service/mqtt.py`. Không đọc được cấu hình broker, nên CHƯA KIỂM có mở ra ngoài hay không. Cầu nối Velxio dùng broker công cộng `broker.hivemq.com` làm mặc định (có thể đổi bằng `VELXIO_PUBLIC_HOST`), chỉ xác thực khi đặt `VELXIO_MQTT_USERNAME/PASSWORD` (`scripts/velxio_mqtt_bridge.py:55-60, 290`). Đây là broker công khai, rủi ro không xác thực nếu không đặt biến.
3. **Token đã cấu hình trên EC2 chưa xác nhận.** `ARCHITECTURE.md` ghi "Token presence was not confirmed". Không đọc giá trị biến môi trường (chủ đích).
4. **Tệp và cấu hình ở gốc repo.** `.env`, `.env.pre-us-20261103`, `farm_auth.db`, `farm_data.db` (SQLite cũ, không import trong code chạy), `ngrok.service`, `smiot-telegram.service`. Chưa đọc nội dung `.env`. Chưa kiểm `ngrok.service` có mở đường truy cập công khai hay không.
5. **Khóa đăng nhập theo tiến trình.** Không chia sẻ giữa nhiều instance. Hiện chỉ có một EC2.
6. **Quyền Datadog cho Logs và Events API** cần `logs_read_data`, `events_read`. Thiếu quyền thì trang chỉ hiện 403 (PROGRESS 12/11). Chưa kiểm trên org có dữ liệu.

---

## 7. Số liệu đếm được (mỗi số kèm nguồn)

| Số liệu | Giá trị | Nguồn / lệnh |
|---|---|---|
| Nhà màng | 10 | `service/farm_registry.py` (10 mã `greenhouse_a` đến `greenhouse_j`) |
| Kịch bản | 36 (A7, C10, D7, H6, S6) | `python -I` đọc `service.scenario_catalog.scenario_catalog()` (13/11) |
| Collection MongoDB (tên trong mã) | 26 (25 nghiệp vụ + `_counters`) | Đếm `collection("...")` (18) và `db[...]`/`db.<tên>` (8) trong `service/`, `main.py`, `pages/` |
| Index khai báo trong mã | 36 (+2 stage_envelopes) | `service/auth.py` init_db (19) + `INCIDENT_INDEX_SPECS` (11) + `HARDENING_INDEX_SPECS` (6). Có trùng lặp chủ đích |
| Index partial | 3 | `active_incident_by_scope`, `telemetry_by_incident_ts`, `active_incident_by_scope_unique` |
| Index TTL | 2 | `scenario_api_idempotency`, `scenario_api_rate_limits` |
| Collection có $jsonSchema (định nghĩa) | 6 | `service/incident_blackbox.py` INCIDENT_VALIDATORS |
| Time Series | 1 (`telemetry`, tạo bởi script migrate) | `scripts/migrate_sqlite_telemetry_to_mongodb.py:23, 115-139` |
| Nhánh $unionWith trong hộp đen | 7 | `service/incident_blackbox.py` dòng 345-472 |
| Tên `smiot.*` duy nhất trong mã | 78 (19 trong `datadog_metrics.py`) | Grep literal |
| Monitor Datadog trong org (live) | 30 tổng; 19 có "SMIOT" | GET `/api/v1/monitor` (13/11) [EC2-GET] |
| Monitor trong IaC | 23 (17 + 5 + 1) | `deploy/datadog/terraform_*` |
| Monitor trong snapshot | 17 | `docs/datadog_config_snapshot/20261108T150159Z/json/manifest.json` |
| Dashboard SMIOT (live) | 5 | GET `/api/v1/dashboard` (13/11) [EC2-GET] |
| Workflow SMIOT (live) | 10 (tất cả published) | GET `/api/v2/workflows` (13/11) [EC2-GET] |
| Workflow trong snapshot | 3 | `docs/datadog_config_snapshot/.../json/workflows/` |
| Route UI (`@ui.page`) | 16 | `pages/*.py`, `main.py` |
| Route API (`@app`) | 10 | `main.py` |
| File test (`tests/test_*.py`) | 41 | `Get-ChildItem tests -Filter test_*.py` (13/11) |
| Số test đạt (đã ghi) | 281/281 (PROGRESS 12/11); 162 (tài liệu 06/11). CHƯA CHẠY LẠI | `PROGRESS.md`; `docs/submission/01`, `05`, `06` |
| Module `service/` | 37 | `Get-ChildItem service -Filter *.py` |
| Module `pages/` (không tính __init__) | 15 | `Get-ChildItem pages -Filter *.py` |
| Script `scripts/` (đệ quy) | 62 | `Get-ChildItem scripts -Recurse -Filter *.py` |
| Project Velxio | 3 | `velxio/node1_environment`, `node2_virtual_pump`, `node3_flow_monitor` |
| Dòng diễn tập trong JSON 12/11 | 8 (ghi nhận; 4 mã bỏ qua) | `[EC2-FILE]` |
| Dòng diễn tập trong JSON 13/11 | 3 | `[EC2-FILE]` |

Lưu ý: số test 41 là số file, không phải số hàm test. Số test đạt 281 và 162 là số ghi trong tài liệu, chưa chạy lại trong phiên này.

---

## 8. Chưa làm hoặc đang bổ sung (ghi trung tính)

1. **Đối chiếu ID Datadog.** Tài liệu 06/11 và snapshot 08/11 dùng ID monitor và workflow khác ID live 13/11 (mục 4). Cần cập nhật bảng ID trong `docs/submission/03`, `04`, `06` và `EVIDENCE_INDEX` theo org hiện tại trước khi nộp.
2. **Đồng bộ con số trong tài liệu nộp.** Số test (162 so với 281 so với 41 file), số widget dashboard (8 so với 5-7 mỗi file), số nhánh `$unionWith` (4 so với 7), và tên monitor (Ca 1 cũ so với `telemetry status mismatch`).
3. **Ca 1, Ca 2, Ca 3 trên live.** Cần đọc lại từng lượt workflow và monitor theo ID mới. Ca 2 ghi `recovered` chưa xác nhận (E-56). Ca 3: đầu ra lệnh EC2 chưa đọc được trong 06/11 (E-82).
4. **W3, W5, W6, W9, W10.** PROGRESS 12/11 ghi các incident đã `recovered` trong MongoDB với ID chính xác. Đọc lại Datadog theo ID chính xác: PROGRESS ghi đã có log và span cho một ca scenario (`INC-SMIOT-SCENARIO-92C5A925F941F621`), và ghi W3/W5 chưa đủ điều kiện Level 5 cho đến khi readback Datadog đạt. Phiên này (13/11) chưa kiểm lại các mục này.
5. **W6 detector heartbeat.** ARCHITECTURE: hành vi triển khai và monitor live chưa kiểm. Monitor 343029221 đang OK lúc đọc 13/11, nhưng chưa có diễn tập W6 trên live trong phiên này.
6. **Velxio ba thiết bị trên EC2.** PROGRESS 13/11: EC2 chưa có tab Node 3 và `/devices` chưa đọc MongoDB cho Velxio. Cần triển khai bản local rồi chạy một chu kỳ lỗi, khôi phục, ACK cho cả ba thiết bị. Node 2 chưa có tiếng buzzer được xác nhận.
7. **Âm thanh và phần cứng.** Không có thiết bị vật lý. Âm báo ACK của Velxio chưa xác nhận (PROGRESS 13/11).
8. **Chứng cứ cần người dùng cung cấp** (EVIDENCE_INDEX E-80 đến E-86): kết quả lệnh chỉ đọc MongoDB (phiên bản, topology, Time Series, index thật, validator, collStats); ảnh `/incident`; ảnh LLM Observability (đã có); explain trước và sau (dry-run); ID Bits 164FBE41.
9. **Tài liệu trong `docs/submission/`.** Đã đọc tiêu đề và đối chiếu con số. Chưa đọc từng dòng toàn bộ ~400 KB. Các câu khẳng định trong tài liệu chưa được đối chiếu từng câu với mã.

---

## 9. Những điều chưa kiểm được

| Mục | Lý do | Ảnh hưởng |
|---|---|---|
| Danh sách collection, index, validator, Time Series, topology trên DB sống (EC2) | Lệnh đọc trực tiếp MongoDB trên EC2 bị từ chối bởi chính sách phiên làm việc (production reads). Không thử đường khác. Cần người dùng cấp quyền rõ ràng cho một lần đọc chỉ-đọc, hoặc tự chạy `listCollections` và `indexes` | Mục 3.1-3.3 và đếm index thật chưa xác nhận |
| Nội dung monitor (query, message) trên live | Chỉ đọc danh sách và trạng thái, không đọc chi tiết từng monitor | So sánh với IaC chỉ ở mức tên |
| Chi tiết widget của dashboard live | Chỉ đọc danh sách | Số widget trên live chưa xác nhận |
| Nội dung đầy đủ hai file JSON diễn tập | Đã đọc đủ 10.432 và 6.432 byte | Không còn thiếu |
| Log và Events API readback trong app | Không gọi | Chưa xác nhận đường đọc Datadog trong app |
| Chạy lại test | Không chạy. Số 281 và 162 là số ghi trong tài liệu | Chưa xác nhận test còn pass |
| Ngưỡng từng kịch bản | Không có trong JSON diễn tập. Ngưỡng monitor nằm trong Terraform, chưa đối chiếu giá trị từng monitor | Không trình bày ngưỡng đã duyệt |
| Trạng thái W7 và W8 monitor | Đang Alert lúc đọc (13/11). Không rõ từ khi nào | Cần đọc lịch sử nếu cần trình bày |
| Đầu ra W3, W5, W6, W9, W10 trên EC2 | Không đọc (ngoài phạm vi phiên này). Dựa trên PROGRESS | Ghi theo PROGRESS, chưa xác nhận lại |
| Bot Telegram, Gemini, Open-Meteo trên EC2 | Không kiểm | Không khẳng định hoạt động |
| Cấu hình broker MQTT trên EC2 và cổng mở | Không đọc | Rủi ro mục 6.2(2) chưa xác nhận |
| Giá trị biến môi trường và token trên EC2 | Chủ đích không đọc giá trị | Chỉ có tên biến trong mã |
| `ngrok.service`, `smiot-telegram.service` | Không đọc nội dung | Chưa kết luận về truy cập công khai |
| Chuỗi `smiot.*` theo loại (metric, span, log) | Chưa phân loại từng tên | Không gọi 78 tên là metric |
