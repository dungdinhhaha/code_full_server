# SMIOT — Project Memory / Handoff

## 1. Mục tiêu

SMIOT là trung tâm quan sát và phục hồi có kiểm soát cho 10 nhà màng dưa lưới. Mục tiêu Level 5 cho một ca là:

`monitor phát hiện → workflow điều tra nhiều nguồn → chọn hành động đúng hoặc từ chối an toàn → kiểm tra health + dữ liệu MongoDB mới → app xác nhận phục hồi`.

Không tuyên bố Level 5 chỉ vì workflow `Success`, monitor `OK`, HTTP 200 hoặc dữ liệu mô phỏng tự trở lại bình thường.

## 2. Repository và môi trường

- Repo chính: `D:\IOT Trung\code_full_server`
- Local env của ứng dụng: `D:\IOT Trung\code_full_server\.env`
- File sao lưu env cũ: `D:\IOT Trung\code_full_server\.env.pre-us-20261103`
- Datadog API/Application key (chỉ đọc khi cần, không in/commit): `D:\attt\APP_KEY.txt`
- AWS profile: `aws-moi`
- AWS region: `ap-southeast-2`
- EC2 instance: `i-00bf2d3591d3ee0a2`
- EC2 app env: `/etc/smiot/app.env` (root, không in giá trị)
- EC2 probe env: `/etc/smiot/probe.env` (root, quyền 600, không in giá trị)
- Mongo admin env nếu có: `/etc/smiot/mongo-admin.env` (không giả định file tồn tại)
- Datadog site: US1, `datadoghq.com`

Không đưa API key, Application key, Mongo URI, mật khẩu, ARN, IP công khai hoặc số tài khoản vào log, JSON workflow, GitHub hay S3.

## 3. Terraform / Datadog source of truth

- Workflow Terraform: `infra/datadog-workflows/`
- Workflow specs: `infra/datadog-workflows/specs/w1.json` … `w10.json`
- Workflow Terraform entrypoint: `infra/datadog-workflows/main.tf`
- Scenario monitor Terraform: `deploy/datadog/terraform_scenarios/`
- Monitor Terraform: `deploy/datadog/terraform_monitors/`
- 10-farm dashboards Terraform: `deploy/datadog/terraform_farm_control_center/`
- Datadog config snapshots: `docs/datadog_config_snapshot/`
- Workflow import/evidence snapshots: `outputs/workflow_imports/`

Quy tắc Terraform:

1. Chỉ dùng Terraform để thay đổi monitor, dashboard, workflow nếu resource đã có state/import rõ ràng.
2. Trước mỗi write: kiểm tra đúng Datadog US1, API key hợp lệ và resource ID.
3. `terraform plan` trước `apply`; không xóa/sửa resource ngoài phạm vi.
4. Sau `apply`: đọc lại API, workflow phải `published=true`, monitor query/trigger phải khớp producer backend.
5. Nếu Terraform chưa quản lý resource live, dùng API script có backup JSON trước; sau đó import vào state.
6. Không để secret trong `.tf`, `.tfstate`, JSON hoặc Git.

Lệnh kiểm tra mẫu (không in secret):

```powershell
aws sts get-caller-identity --profile aws-moi
aws ec2 describe-instances --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2
```

## 4. Datadog IDs hiện có

### Workflow

| Ca | Workflow ID | Mục đích |
|---|---|---|
| W1 | `b9e72b04-1580-45f8-ae1e-628124a19065` | PLC safety trip evidence |
| W2 | `2f9a3c1d-5292-4bc3-b4b9-cc03d4172724` | Sensor flatline / local interlock review |
| W3 | `373ed0c0-4509-4fcd-a067-f54f0becc00e` | Guarded EC2 app recovery |
| W4 | `ffd62026-6b63-40e4-9b46-6ac18d2d584f` | Status mismatch / refuse restart |
| W5 | `d3f0705e-2cbd-430a-9a3a-b1fd02a42cc9` | MongoDB/MQTT dependency triage |
| W6 | `d8e1b3db-1a54-4b4f-9be3-bf7e270a86f3` | Detector heartbeat |
| W7 | `bb86206c-6df8-4b1d-8016-175a2fc62e49` | Irrigation evidence review |
| W8 | `593a670c-d59c-4104-8658-df260245a21e` | VPD/EC crop-risk review |
| W9 | `47e95b24-db40-4cd5-b667-5b90e170b667` | Actuator acknowledgement verification |
| W10 | `50b3dc85-dd20-4220-bda1-ec78d2a3d00f` | AI/provider failure safety |

### Monitor IDs

- W1 PLC safety trip: `342734303`
- W2 sensor flatline: `342585819`
- W3 service inactive: `342585838`
- W4 status mismatch: `342585836`
- W5 MongoDB unhealthy: `342585827`; MQTT unhealthy: `342585828`
- W6 detector heartbeat: `343029221`
- W7 soil humidity absent: `342585835`
- W8 telemetry sample stale: `342585831`
- W9 actuator command unacknowledged: `342734743`
- W10 AI ask latency/provider signal: `342585824`

## 5. Current verified state

### Completed / strongest evidence

- **W1:** synthetic PLC safety trip on `greenhouse_d/node2`; local virtual PLC returned safe-stop, pump OFF, valve closed, ACK and Mongo persistence. Datadog workflow run `d2d35133-1764-4320-b59f-9b9dc0a68001` succeeded. Monitor `342734303` returned `OK` after `on_missing_data=resolve`.
- **W4:** synthetic status mismatch on `greenhouse_c/node1`; workflow run `b06dac70-cc51-4148-923b-ee813a741619` succeeded. Restart was refused safely; monitor `342585836` returned `OK` after normal/stop.
- **W6:** farm-scoped detector fault on `greenhouse_b`; heartbeat `0→1`, workflow run `dccdcfcc-a2e1-489f-a06b-a7aa54d3957e` succeeded and monitor `343029221` recovered. Rate-limit was changed to `10/300s` and workflow republished.
- **W3:** controlled recovery run succeeded with verifier `status=recovered` in earlier evidence, but automatic monitor-trigger path is not fully proven.
- **W2:** many bounded drills, metric path and Mongo persistence are working. Remaining gap is a full five-minute monitor Alert→workflow→verifier CLEAR chain; do not rerun unnecessarily.

### Still incomplete / next work

- **W9:** monitor/workflow exist but positive live unacknowledged-command chain is not complete. The synthetic emitter exists at `scripts/emit_w9_w10_synthetic_metrics.py`; the last attempted emitter deployment was interrupted. Continue by deploying the updated emitter, verify the metric query and trigger, read workflow instance, then restore normal state.
- **W5:** no complete live Mongo-vs-MQTT fault discrimination run yet. Use synthetic gauges only; never stop real MongoDB/MQTT. Emit one dependency down at a time, verify W5 branch, then send normal values and confirm both monitors return `OK`.
- **W10:** synthetic emitter exists but provider-failure live chain is not complete.

## 6. Important scripts

- W4/W1 parallel drill: `scripts/run_w4_w1_parallel.ps1`
- W2 bounded drill: `scripts/run_w2_bounded_drill.ps1`
- W6 live drill: `scripts/run_w6_live_drill.ps1`
- W9/W10 synthetic metrics: `scripts/emit_w9_w10_synthetic_metrics.py`
- W9 bounded sender: `scripts/run_w9_bounded_drill.ps1`
- W5 dependency metrics (local, synthetic): `scripts/emit_w5_dependency_metrics.py`
- W1/W4 monitor check: `scripts/check_w1_w4_monitors.py`
- W2 account/metric check: `scripts/check_datadog_w2_account.py`
- W9 runtime check: `scripts/check_w9_runtime.py`
- W1 missing-data patch: `scripts/patch_w1_monitor_missing_data.py`
- W6 workflow publisher: `scripts/publish_w6_workflow.py`
- AWS/EC2 deploy scripts: `scripts/deploy_*.ps1`, `scripts/enable_datadog_metrics_ec2.ps1`

## 7. Safe drill protocol

1. Preflight AWS identity, EC2 SSM, `/healthz`, Mongo/MQTT health, Datadog account and metric presence.
2. Use `synthetic=true`, unique `scenario_run_id`, farm/device scope and bounded timeout.
3. Never stop shared MongoDB/MQTT or reboot EC2 for a synthetic drill.
4. Local PLC/interlock remains the immediate safety authority; Datadog observes, investigates and coordinates.
5. Read the workflow instance and monitor group; a workflow `Success` is not recovery proof.
6. Send `normal`/stop in a `finally` path and wait for the full monitor evaluation window.
7. Verify fresh Mongo sample, app notification, action ledger, health and monitor `OK`.
8. Append every action/result to `ACTIVITY_LOG.md`, `PROGRESS.md` and `TASKS.md`.

## 8. Logging and evidence

- Activity log: `ACTIVITY_LOG.md`
- Current progress: `PROGRESS.md`
- Work queue: `TASKS.md`
- Design/architecture: `docs/CONTROL_CENTER_BLUEPRINT.md`
- Submission evidence index: `docs/submission/EVIDENCE_INDEX.md`
- Never store secrets in evidence. Redact URLs with credentials, tokens and full connection strings.

## 9. Recommended continuation order

1. Finish W9 positive synthetic chain and restore monitor `OK`.
2. Run W5 Mongo-down and MQTT-down separately with synthetic gauges; read branch and restore both to `1`.
3. Re-read W3 automatic monitor path; do not claim automatic Level 5 until monitor-triggered run is captured.
4. Keep W2 as completed bounded work; only perform its long Alert window if final submission explicitly requires automatic monitor evidence.
5. Re-run integration tests before deploying backend changes, then deploy only the changed files to `smiot.service`.

## 10. Level 5 acceptance record

For every claimed Level 5 case, record: monitor ID/state transition, workflow ID/run ID, exact branch decision, action or safe refusal, incident/scenario ID, app notification status, MongoDB fresh sample timestamp, health check, cleanup command, and final monitor group state. If any item is missing, mark the case `partial` rather than `Level 5`.
