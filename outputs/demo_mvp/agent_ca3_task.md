# Agent Ca3 Task — service_down / greenhouse_c / node 1

## Mục tiêu
Tạo incident Ca3 (service_down) HOÀN CHỈNH trong MongoDB trên EC2.
Tất cả các section trong UI phải GREEN — không còn "chưa xác minh", "workflow = 0", "trace = 0".

## Thông tin kịch bản
- **Ca**: 3 (service_down)
- **farm_key**: greenhouse_c
- **node_id**: 1
- **monitor_id**: 342585838 (SMIOT | smiot.service inactive)
- **workflow_id**: 373ed0c0-4509-4fcd-a067-f54f0becc00e (Guarded EC2 app recovery)
- **kind**: service_down
- **scenario_code**: H1
- **scenario_type**: h1_service_down
- **decision**: GUARDED_SERVICE_RECOVERY_ONLY

## Fields bắt buộc phải fill

### evidence (trong operational_incidents)
- `evidence.workflow_observations`: list of dicts với execution_id, workflow_id, status, disposition
- `evidence.trace_ids`: list với 1 trace ID (hex string)
- `last_workflow_execution_id`: UUID string
- `last_workflow_status`: "succeeded"
- `last_workflow_disposition`: "GUARDED_RECOVERY"

### recovery_verification (service_down cần)
- `http_status`: 200
- `newest_sample_age_s`: 15 (phải có giá trị)
- `verifier`: "smiot_external_probe"
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
Ghi kết quả vào: outputs/demo_mvp/agent_ca3_log.md
Format: incident_id, status (OK/FAIL), từng field đã fill, errors nếu có
