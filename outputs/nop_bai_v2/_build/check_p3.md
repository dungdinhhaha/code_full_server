# Kiểm chứng P3: khẳng định Datadog trong hồ sơ nop_bai_v2

Phạm vi: 7 file .docx trong outputs/nop_bai_v2 (đọc đoạn và bảng), service/datadog_*.py, service/observability.py, service/logger.py, main.py (route và biến môi trường), deploy/datadog (tf, json, yaml, tfstate chỉ đếm và đối chiếu ID), docs/datadog_config_snapshot/20261108T150159Z (chỉ đếm và đọc tên). Không gọi Datadog, không gọi mạng, không in giá trị token. Đường dẫn ngắn: "code" là D:\IOT Trung\code_full_server.

Ghi chú về cách đếm: "78 chuỗi smiot.*" được đối chiếu bằng hai cách, 83 chuỗi nằm trong dấu nháy (service, scripts, pages, main.py) và 87 theo regex thô (có cả smiot.service và tên unit).

| # | Khẳng định (file, mục) | Mã đối chiếu (file:dòng) | Kết quả | Gợi ý sửa |
|---|---|---|---|---|
| 1 | 03, Bảng 1: 19 metric DogStatsD gọi trực tiếp trong service/datadog_metrics.py | service/datadog_metrics.py (19 tên smiot.* duy nhất) | khớp | Không cần sửa |
| 2 | 03, Bảng 1: nhóm actuator 9, crop 5, device 2, sequence 3 | service/datadog_metrics.py (đếm theo tiền tố) | khớp | Không cần sửa |
| 3 | 03, §2.1: "78 chuỗi smiot.* duy nhất trong toàn bộ mã" | service/, scripts/, pages/, main.py: 83 chuỗi có nháy; 87 theo regex thô | sai | Đổi thành con số đã đếm lại (83 hoặc 87) và ghi quy tắc đếm; hoặc gọi rõ là "chuỗi tên sự kiện, span và metric" |
| 4 | 03, §2.1: 10 tên smiot.* ngoài Bảng 1 (samples_persisted, ingest_lag_ms, sample_age_seconds, status_mismatch, sensor_flatline, dependency.mongo.up, dependency.mqtt.up, actuator.command_acknowledged, virtual_plc.safety_trip, safe_mode.transition) | service/telemetry_health.py, service/datadog_metrics.py và các file liên quan (mỗi tên có ít nhất 1 chỗ dùng) | khớp | Không cần sửa |
| 5 | 03, §2.1 và Bảng 4 (07): DD_DOGSTATSD_PORT, mặc định 8125 | service/datadog_metrics.py:40, :84 | khớp | Không cần sửa |
| 6 | 03, Bảng 4 (07): DD_TRACE_AGENT_URL, mặc định nội bộ | service/observability.py:37 (mặc định 127.0.0.1:8126) | khớp | Ghi rõ giá trị mặc định 127.0.0.1:8126 nếu cần |
| 7 | 03, §2.2 và Bảng 4 (07): DATADOG_APM_ENABLED bật ddtrace | service/observability.py:31 | khớp | Không cần sửa |
| 8 | 03, §2.2: DD_SERVICE=smiot-smart-farm, DD_ENV=demo, DD_VERSION=1.0.0, DD_LOGS_INJECTION=true, ddtrace.patch_all() | service/observability.py:34-38, :46 | khớp | Không cần sửa |
| 9 | 03, Bảng 1 và 04: ddtrace>=4.16.1,<5.0 | requirements.txt (dòng ddtrace) | khớp | Không cần sửa |
| 10 | 03, §2.2: span mqtt.message.process, gemini.generate_content, smiot.ai.tool | service/mqtt.py:927; service/ai_service.py:232, :475 | khớp | Không cần sửa |
| 11 | 03, §2.3: Agent đọc incident_events.jsonl và recovery/*.jsonl, service smiot-smart-farm | deploy/datadog/smiot-logs.yaml (path, service) | khớp | Không cần sửa |
| 12 | 03, §2.3: theo PROGRESS.md (12/11), Agent trên EC2 có thêm system.log và error.log | PROGRESS.md không có chuỗi system.log hoặc error.log; smiot-logs.yaml không khai báo hai file này; service/logger.py:18, :29 chỉ tạo logs/system.log và logs/error.log | không kiểm được | Trích đúng dòng PROGRESS.md (12/11) hoặc bỏ câu này; nếu giữ, thêm hai file vào smiot-logs.yaml hoặc ghi rõ đây là cấu hình chỉ có trên EC2 |
| 13 | 03, Bảng 2: 5 dashboard SMIOT, số widget 6, 5, 7, 6, 7 theo 5 file JSON | deploy/datadog/terraform_farm_control_center/dashboards/*.json: farm-portfolio 6, farm-data-quality 5, iot-mqtt-fleet 7, incident-recovery 6, app-mongodb-ai 7 | khớp | Không cần sửa |
| 14 | 03, Bảng 2: ID dashboard rzf-su8-zgf, g8w-hj8-px7, kzx-fwc-sai, isq-rzw-a6s, mzj-a5m-yh9 | deploy/datadog và docs snapshot (mỗi ID có 2 chỗ; ID nằm trong terraform_farm_control_center/terraform.tfstate) | khớp | Không cần sửa |
| 15 | 03, Bảng 1 (mục Terraform): "5 dashboard JSON và một datadog_dashboard_json bổ sung trong main.tf", "5 + 1 dashboard" | deploy/datadog/terraform_farm_control_center/main.tf: chỉ có 1 resource datadog_dashboard_json với for_each trên fileset dashboards/*.json, tức 5 instance; tfstate có 5 instance | sai | Sửa thành "5 dashboard (1 resource for_each)" và bỏ phần "+1" |
| 16 | 03, §3 (live 13/11): tổ chức có 5 dashboard SMIOT; 03 Bảng 2 ghi tên "App, EC2, MongoDB & AI" và các tên khác | Không đọc được live (chỉ đọc, không gọi Datadog). Repo chỉ có 5 file JSON; snapshot 08/11 có 1 dashboard khác (nkc-685-vw8) | không kiểm được | Ghi rõ nguồn và ngày đọc; nếu muốn đối chiếu, chạy lại đọc chỉ đọc và lưu kết quả vào docs |
| 17 | 03, Bảng 1 (Terraform): tổng 23 định nghĩa monitor = 17 + 5 + 1 | deploy/datadog/terraform_monitors/monitors.tf: 16 trong for_each (locals) và 1 datadog_monitor detector_heartbeat (dòng 172); terraform_scenarios/terraform.tf: 5 resource (dòng 80, 115, 146, 177, 208); terraform_w2_greenhouse_j/main.tf: 1 monitor | khớp | Không cần sửa |
| 18 | 03, Bảng 3: 17 trong 19 monitor có ID nằm trong tfstate terraform_monitors (342585819, 820, 822, 823, 824, 825, 827, 828, 830, 831, 835, 836, 837, 838, 343029221, 343594185, 343594187) | deploy/datadog/terraform_monitors/terraform.tfstate (17 instance datadog_monitor) | khớp | Không cần sửa |
| 19 | 03, Bảng 3: 2 ID 342734303 (virtual PLC safety trip W1) và 342734743 (actuator command unacknowledged W9) | Không có trong repo; terraform_scenarios và terraform_w2_greenhouse_j không có tfstate | không kiểm được | Thêm tfstate hoặc ghi ID đọc từ live với ngày đọc; hoặc ghi chú rằng hai monitor này chưa được quản lý bằng IaC |
| 20 | 03, Bảng 3: tên "virtual PLC safety trip (W1)" và "SMIOT | sensor flatline" (có tiền tố thừa) | IaC: terraform_scenarios/terraform.tf:83 là "SMIOT | Virtual PLC protective stop"; terraform_monitors/monitors.tf:31 là "SMIOT | sensor flatline" | sai | Đổi tên trong Bảng 3 khớp với tên trong IaC hoặc ghi rõ đây là tên trên live; bỏ tiền tố "SMIOT |" thừa ở dòng 342585819 |
| 21 | 03, §4: tổ chức có 30 monitor, 19 có SMIOT trong tên (GET 13/11) | Không đọc được live. Snapshot 08/11 có 17 file monitor, trong đó các monitor SMIOT có ID khác (ví dụ 339977691, 340356283) | không kiểm được | Ghi rõ đây là số đọc live ngày 13/11, không phải số trong repo; nêu thêm số file snapshot 08/11 để tránh nhầm |
| 22 | 03, §5: tổ chức có 10 workflow SMIOT, đều published (GET 13/11) | Không đọc được live. Repo IaC chỉ có 1 datadog_workflow_automation (terraform_w2_greenhouse_j/main.tf); snapshot 08/11 có 3 file workflow | không kiểm được | Ghi rõ nguồn live và ngày đọc; không suy ra số workflow từ IaC |
| 23 | 03, Bảng 4: 10 ID workflow (ffd62026..., 2f9a3c1d..., 373ed0c0..., 50b3dc85..., b9e72b04..., d3f0705e..., d8e1b3db..., bb86206c..., 593a670c..., 47e95b24...) | Không có ID nào trong IaC hay tfstate; snapshot 08/11 có 3 ID khác (18d1b008..., b83453ff..., e2835af0...) | không kiểm được | Đối chiếu lại từ live và ghi ngày; hoặc lưu snapshot mới của workflow vào docs |
| 24 | 03, Bảng 4: 10 workflow không có W2, trong khi IaC có workflow W2 (published) | deploy/datadog/terraform_w2_greenhouse_j/main.tf: datadog_workflow_automation "w2_greenhouse_j" (published = true) | sai | Bổ sung W2 vào Bảng 4 hoặc ghi rõ W2 không nằm trong 10 workflow đã đọc |
| 25 | 03, Bảng 1 (Terraform): W2 có 12 bước trong w2-greenhouse-j.json | deploy/datadog/terraform_w2_greenhouse_j/w2-greenhouse-j.json (12 phần tử steps) | khớp | Không cần sửa |
| 26 | 03, §3.3 và 04: khôi phục Ca 3 có khóa, thời gian chờ giữa hai lần và danh sách lệnh cho phép | scripts/aws/smiot-recover-guarded.sh:11-13 (lock, cooldown_seconds=300), :99-100 (flock -n), :106-114 (cooldown). Danh sách lệnh cho phép chưa kiểm được trong phạm vi này | khớp | Không cần sửa; kiểm tra thêm danh sách lệnh cho phép nếu cần ghi là đã kiểm |
| 27 | 03, §4 và 04 (Bảng 3): 5 endpoint Datadog và khôi phục (recover, verify, recovery-verification, safe-mode/recovery-clear, notification) | main.py:625 (w2-greenhouse-j/recover), :698 (w2-greenhouse-j/verify), :801 (recovery-verification), :960 (internal/safe-mode/recovery-clear), :1010 (integrations/datadog/notification) | khớp | Không cần sửa |
| 28 | 03 và 04: token DATADOG_APP_NOTIFICATION_TOKEN cho endpoint nhận sự kiện; SAFE_MODE_RECOVERY_TOKEN cho endpoint xóa safe mode | main.py:628, :701, :811, :1017 (DATADOG_APP_NOTIFICATION_TOKEN); main.py:963 (SAFE_MODE_RECOVERY_TOKEN) | khớp | Không cần sửa (không in giá trị) |
| 29 | 04 (Bảng 3) và 03: SMIOT_RECOVERY_INSTANCE_ID; AWS_REGION mặc định ap-southeast-2 | main.py:836 (SMIOT_RECOVERY_INSTANCE_ID); main.py:847 (AWS_REGION, mặc định ap-southeast-2) | khớp | Không cần sửa |
| 30 | 03, §2.2 (ghi chú Datadog API): service/datadog_reader.py gọi /api/v2/events (lọc theo monitor_id) và /api/v2/logs/events (lọc theo incident_id) | service/datadog_reader.py:292 (/api/v2/events, filter monitor_id), :304 (/api/v2/logs/events, filter incident_id) | khớp | Không cần sửa |
| 31 | 03, §2.2: LLM Observability bật bằng DATADOG_LLMOBS_ENABLED | service/observability.py (có biến này) | khớp | Không cần sửa |
| 32 | Ghi chú nội bộ repo (không phải khẳng định trong hồ sơ): deploy/datadog/smiot-logs.yaml gắn tag env:production, trong khi DD_ENV mặc định là demo | deploy/datadog/smiot-logs.yaml (tags); service/observability.py:35 (DD_ENV=demo) | sai | Thống nhất tag env giữa smiot-logs.yaml và DD_ENV, hoặc ghi rõ đây là môi trường demo |

## Tóm tắt

- Khớp: 21 khẳng định.
- Sai: 5 mục (3, 15, 20, 24, 32). Mục 32 là mâu thuẫn trong repo, không phải khẳng định của hồ sơ.
- Không kiểm được: 6 mục (12, 16, 19, 21, 22, 23). Phần lớn là số đọc live ngày 13/11 mà không có trong repo, và snapshot 08/11 khác ngày nên không đối chiếu được ID.

## Ba lỗi quan trọng nhất

1. Mục 3: "78 chuỗi smiot.* duy nhất" không khớp với mã hiện tại (83 chuỗi có nháy, 87 theo regex thô).
2. Mục 15 và 24: "5 + 1 dashboard" sai (main.tf chỉ có 5 instance), và Bảng 4 (10 workflow) không có W2 trong khi IaC có workflow W2 published.
3. Mục 19, 21, 22, 23: hai ID monitor trong Bảng 3 không có trong repo, và số monitor, workflow, ID workflow đọc từ live không thể đối chiếu với IaC hoặc snapshot 08/11 (khác ngày).
