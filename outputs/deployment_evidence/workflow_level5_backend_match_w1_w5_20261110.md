# Đối chiếu workflow W1–W5 với backend — 10/11/2026

Phạm vi: đọc bản JSON `live_verified_20261110`, mã nguồn cục bộ và các bản nháp. Không chạy workflow/sự cố, không sửa Datadog/AWS, không restart hay dừng dịch vụ.

## Kết luận nhanh

- Đường Datadog → app notification có backend nhận, xác thực Bearer, chuẩn hóa payload và ghi idempotent vào MongoDB `notifications`. Các bản live của W1–W5 đều có HTTP notification action. Tuy nhiên message đang chủ yếu là tổng quát, `event_id` là workflow instance ID, còn `incident_id` không được truyền; nên notification chưa nối chắc chắn vào incident.
- W1, W2, W4, W5 hiện là query → if/echo → notify. Đây là kiểm tra/tóm tắt tín hiệu; chưa truy vấn trực tiếp incident/action ledger, chưa có đối chiếu logs/traces đa nguồn bên trong workflow, và chưa có bước hậu xử lý xác nhận phục hồi. Bits Investigation là một nhánh riêng từ monitor, không có bằng chứng rằng kết luận Bits tự đi vào điều kiện của workflow.
- W3 hiện là đúng một lệnh SSM `Send_command` rồi HTTP notification. Không có bước poll kết quả command, kiểm tra `/healthz`, đối chiếu mẫu Mongo mới hoặc đóng/cập nhật incident. Nội dung thông báo nói CHỜ XÁC MINH, vì vậy không tuyên bố phục hồi — đây là ranh giới đúng, nhưng chưa phải chuỗi recovery hoàn chỉnh.
- Không thể gọi W1–W5 là Level 5. Mã nguồn có một phần incident lifecycle và safety evidence, nhưng workflow chưa tiêu thụ các bản ghi đó bằng một hợp đồng API rõ ràng.

## Đối chiếu từng workflow

| Ca | Khớp với backend | Thiếu / không khớp để đạt thiết kế Level 5 |
|---|---|---|
| **W1 PLC Safety Trip** | `service/mqtt.py` nhận event PLC ảo, phát `smiot.virtual_plc.safety_trip`, lưu trip evidence vào `incident_telemetry_evidence`/`operational_incidents`; khi có interlock ACK, phát `smiot.virtual_plc.safety_ack` và ghi action ledger/evidence. Query live dùng metric trip và tag `event:safety_trip`. Workflow giữ giới hạn không điều khiển actuator. | Query chỉ đọc metric tổng hợp; chưa đọc Mongo trip/ACK/ledger, và không xác minh ACK metric. Không gắn `incident_id`/command ID vào run. Không có post-check độc lập sau trip. |
| **W2 Sensor Flatline** | `service/telemetry_health.py` tính flatline từ 10 mẫu mới thực sự đã lưu trong MongoDB, kiểm tra độ tươi và phát `smiot.telemetry.sensor_flatline`; workflow query metric này. Backend sở hữu HOLD/CLEAR tại interlock/verifier; Datadog không gửi actuator command. | Workflow chỉ query metric flatline; không đọc `boot_id`, sequence, MQTT evidence, incident record, HOLD ledger hoặc ACK. Hai nhánh của workflow xác nhận/từ chối metric chứ chưa xác nhận trạng thái local interlock. `service/incident_lifecycle.py` còn khai báo monitor/workflow ID cũ cho flatline incident; cần cập nhật identity có kiểm soát hoặc chuyển ID vào cấu hình trước khi tuyên bố đã nối. Không được diễn đạt metric flatline thành “HOLD đã ACK” hoặc “đầu dò vật lý hỏng”. |
| **W3 EC2 App Recovery** | Live workflow trigger là monitor; AWS connection/region và SSM document `SMIOT-GuardedStartApp` được tham chiếu. JSON gửi thông báo CHỜ XÁC MINH, đúng với việc SendCommand chưa phải bằng chứng phục hồi. Script probe có kiểm tra HTTP, Mongo sample age và có thể ghi service-down incident. | Không có poll/get-command-invocation, không kiểm tra terminal status/SSM output, `/healthz`, dependency health hay mẫu Mongo mới sau command. `IncidentId` được điền từ `{{ InstanceId }}` nhưng không có bằng chứng biến này là canonical Mongo incident ID; cần truyền incident ID rõ ràng. Notification chỉ có `event_id={{InstanceId}}`, tên/ID workflow và message; thiếu `incident_id`, `farm_key`, `status`, `action_result`, `verification_result`. Không có nhánh thất bại/chờ xác minh sau khi command hoàn tất. |
| **W4 Status Mismatch / Refuse Restart** | Backend tính mismatch từ trạng thái UI so với mẫu Mongo mới và phát `smiot.telemetry.status_mismatch`, `smiot.telemetry.sample_age_seconds`; JSON query đúng các metric này. Điều kiện từ chối restart yêu cầu mismatch dương và sample age dưới ngưỡng. Workflow không chứa hành động restart, nên từ chối là an toàn. | Chưa kiểm tra health endpoint/APM hoặc log nguồn trong workflow; metric chỉ có farm/node scope, không có incident ID. Nhánh “REFUSED_RESTART” chỉ ghi Echo, chưa persist quyết định vào incident/action ledger; chưa xác minh monitor OK hoặc sample tiếp tục mới sau quyết định. `service/telemetry_health.py` còn hằng monitor/workflow ID lịch sử cho false-offline incident; cần xử lý identity mismatch trước khi khẳng định record trỏ tới workflow live hiện tại. |
| **W5 MongoDB/MQTT Triage** | Backend phát `smiot.dependency.mongo.up`, `smiot.dependency.mqtt.up`, ingest lag và tuổi sample; JSON query các tên metric tương ứng. Có nhánh phân loại và nhánh thiếu dữ liệu/query failure; không restart dependency. | Query `{*}` có thể gộp farm/service không liên quan vào cùng scalar; cần scope `env/service/farm` và sự cố. Chưa truy vấn logs/traces hay xác nhận lỗi gốc bằng probe read/write/publish/consume. Nhánh tuần tự ưu tiên Mongo rồi MQTT rồi ingest, chưa xử lý tình huống nhiều dependency cùng down hoặc nguyên nhân mơ hồ theo dạng multi-fault. Chưa có verification sau remediation (hiện cũng không remediation). |

## Hợp đồng notification API hiện có

Nguồn: `main.py` route `POST /api/integrations/datadog/notification`, `service/datadog_notifications.py`.

- Header bắt buộc: `Authorization: Bearer <secret>`; secret phải ở Datadog HTTP Connection và `DATADOG_APP_NOTIFICATION_TOKEN` trên app, tuyệt đối không ghi vào JSON.
- Bắt buộc: `event_id` (string, tối đa 160 ký tự), `message` (string, tối đa 500 ký tự).
- Tùy chọn hiện được chấp nhận/lưu: `incident_id`, `workflow_name`, `workflow_id`, `farm_key`, `category`, `severity`.
- `event_id` được hash thành Mongo `_id` để idempotency; trả `202 received` hoặc `200 duplicate`; app bell chỉ cập nhật khi insert mới.
- Thiếu trong schema hiện tại nếu muốn biểu diễn rõ kết quả level-5: `monitor_id`, `workflow_run_id` (nên tách tên khỏi `event_id`), `decision`, `action`, `action_result`, `verification_status`, `evidence_refs`, `occurred_at`. Không nên gửi raw secrets, output nhạy cảm, hay tags cardinality cao.

Identity mismatch cần xử lý: `service/incident_lifecycle.py` đang giữ `MONITOR_ID`/`WORKFLOW_ID` lịch sử cho flatline; `service/telemetry_health.py` giữ ID lịch sử cho false-offline. Vì vậy dù workflow trigger monitor live mới, incident Mongo có thể lưu liên kết cũ. Không sửa các hằng này bằng suy đoán; nên chuyển chúng sang cấu hình runtime đã kiểm tra, hoặc workflow/API ghi liên kết live sau khi xác thực incident/farm/node.

Đề xuất hợp đồng versioned (chưa triển khai): giữ tương thích các trường hiện tại, bổ sung `schema_version`, canonical `incident_id`, `monitor_id`, `workflow_run_id`, `status` enum (`investigating|refused|action_started|pending_verification|recovered|escalated`), `decision_code`, `action_code`, `verification` object và danh sách reference ID log/span/Mongo document. Backend phải validate enum/độ dài, xác thực farm, dùng idempotency ổn định theo `workflow_run_id + event_kind`, và chỉ cập nhật incident khi incident tồn tại cùng farm. Notification không tự đóng incident; chỉ verifier phía app được phép ghi `recovered` sau khi kiểm tra dữ liệu hậu hành động.

## Trạng thái triển khai và hướng sửa chính xác

1. **W1/W2/W4/W5:** dùng endpoint query backend đã xác thực (hoặc signed event) để workflow lấy incident theo `monitor_id + farm/node + active status`, trả canonical `incident_id` cùng evidence references; không tìm “incident đang mở mới nhất” toàn cục. Sau đó gửi notification có incident ID và trạng thái kết luận; chưa thêm Mongo DB action trực tiếp vào workflow trước khi xác định quyền/API action được hỗ trợ.
2. **W3:** giữ SSM command có guard, nhưng chèn bước chờ/kéo kết quả theo `CommandId` và `InstanceId`, giới hạn thời gian; chỉ sau terminal success gọi verifier app. Verifier kiểm tra HTTP health, Mongo sample `received_at` sau action baseline, dependencies và incident ID. Thành công mới trả `recovered`; lỗi/timeout trả `pending_verification` hoặc `escalated`. Cần xác minh action catalog có API poll tương thích trước khi bổ sung JSON — không đoán step/action ID.
3. **Mọi ca:** tạo Bits Investigation từ monitor và xác minh trên UI; không coi JSON workflow là cấu hình Bits. Nối cùng incident ID qua monitor event, workflow, log/span, Mongo incident và app notification bằng biến/endpoint đã kiểm chứng.
4. Chỉ sau khi xác nhận contract, quyền và action schema mới sửa JSON deployable. Hiện bản nháp W1/W2/W4/W5 có fan-in thông báo; đây chưa phải bản Level 5 và chưa được apply.

## File đối chiếu

- Live JSON: `outputs/workflow_imports/live_verified_20261110/` (W1, W2, W3, W4, W5).
- Bản nháp local: `outputs/workflow_imports/level5_drafts/`.
- Backend: `main.py`; `service/datadog_notifications.py`; `service/telemetry_health.py`; `service/incident_lifecycle.py`; `service/mqtt.py`; `service/scenario_evidence.py`; `scripts/smiot_external_probe.py`; `scripts/aws/smiot-recover-guarded.sh`.
- Không đọc file env hoặc khóa; không thực hiện lệnh ghi nào trong Datadog/AWS/MongoDB.

## Cập nhật local sau đối chiếu — 10/11/2026

- Đã thay mapping stale bằng resource hiện hành đã có trong live export: W2 `342585819` / `2f9a3c1d-5292-4bc3-b4b9-cc03d4172724`; W4 `342585836` / `ffd62026-6b63-40e4-9b46-6ac18d2d584f`. Sửa ở `service/incident_lifecycle.py`, `service/telemetry_health.py`, `service/incident_blackbox.py` và test mapping. Chỉ là thay đổi local, chưa triển khai EC2.
- W1, khi trip hoặc ACK được tìm bằng exact simulator run/farm và lưu vào Mongo, nay gắn monitor `342734303` cùng workflow `b9e72b04-1580-45f8-ae1e-628124a19065` vào incident. Workflow draft query cả trip và ACK metric; message nêu rõ đây là aggregate candidate, chưa chứng minh cùng command/incident. Cần Mongo command_id correlation trước khi xác nhận.
- W5 draft giới hạn metric Mongo/MQTT theo tag `service:smiot-smart-farm,env:demo` đã có trong producer, đồng thời có nhánh nhận biết cả hai dependency aggregate cùng degraded. Telemetry ingest/freshness vẫn chỉ là fleet-level hint; không gán farm/root cause cụ thể.
- W2/W4 app notifications thêm `farm_key=greenhouse_a`, trường đã được backend hỗ trợ. Không truyền `incident_id` vì workflow template không có nguồn canonical đã xác minh; không suy đoán biến trigger.
- Bốn draft W1/W2/W4/W5 vẫn chưa được apply lên Datadog. W1/W2/W4/W5 chưa có incident-specific query API, Bits conclusion handoff, hoặc post-action verifier; vì vậy chưa đạt Level 5.
- Kiểm tra chạy được: `tests/test_incident_autolink.py` — 13 tests OK. `pytest` không cài; test được chạy trực tiếp bằng unittest runner của file.
