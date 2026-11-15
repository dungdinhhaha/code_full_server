# Agent Ca1 Task — false_offline / greenhouse_a / node 1

## Mục tiêu
Tạo incident Ca1 (false_offline) HOÀN CHỈNH trong MongoDB trên EC2.
Tất cả các section trong UI phải GREEN — không còn "chưa xác minh", "workflow = 0", "trace = 0".

## Thông tin kịch bản
- **Ca**: 1 (false_offline)
- **farm_key**: greenhouse_a
- **node_id**: 1
- **monitor_id**: 342585836 (SMIOT | telemetry status mismatch)
- **workflow_id**: ffd62026-6b63-40e4-9b46-6ac18d2d584f (Ca 1 | Refuse restart when samples are fresh)
- **kind**: false_offline
- **decision**: REJECT_RESTART_DATA_PRESENT

## Fields bắt buộc phải fill

### evidence (trong operational_incidents)
- `evidence.workflow_observations`: list of dicts với execution_id, workflow_id, status, disposition
- `evidence.trace_ids`: list với 1 trace ID (hex string)
- `last_workflow_execution_id`: UUID string
- `last_workflow_status`: "succeeded"
- `last_workflow_disposition`: "REFUSED_RESTART"

### recovery_verification (false_offline cần)
- `computed_now`: "ONLINE"
- `age_s`: 12
- `mongo_newest_received_at`: ISO datetime string
- `verifier`: "telemetry_health"
- `verified_at`: datetime

## EC2 access
- Instance: i-00bf2d3591d3ee0a2
- Region: ap-southeast-2
- Profile: aws-moi
- Python: /opt/smiot/.venv/bin/python
- App dir: /opt/smiot
- Env: source /etc/smiot/app.env
- PYTHONPATH: /opt/smiot

## Output
Ghi kết quả vào: outputs/demo_mvp/agent_ca1_log.md
Format: incident_id, status (OK/FAIL), từng field đã fill, errors nếu có
