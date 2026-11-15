# Agent Ca2 Task — soil_humidity_flatline / greenhouse_b / node 2

## Mục tiêu
Tạo incident Ca2 (soil_humidity_flatline) HOÀN CHỈNH trong MongoDB trên EC2.
Tất cả các section trong UI phải GREEN — không còn "chưa xác minh", "workflow = 0", "trace = 0".

## Thông tin kịch bản
- **Ca**: 2 (flatline)
- **farm_key**: greenhouse_b
- **node_id**: 2
- **monitor_id**: 342585819 (SMIOT | sensor flatline)
- **workflow_id**: 2f9a3c1d-5292-4bc3-b4b9-cc03d4172724 (Ca 2 | Confirm local interlock)
- **kind**: soil_humidity_flatline
- **scenario_code**: F2
- **scenario_type**: f2_sensor_flatline
- **decision**: HOLD_AND_VERIFY_FLATLINE

## Fields bắt buộc phải fill

### evidence (trong operational_incidents)
- `evidence.workflow_observations`: list of dicts với execution_id, workflow_id, status, disposition
- `evidence.trace_ids`: list với 1 trace ID (hex string)
- `last_workflow_execution_id`: UUID string
- `last_workflow_status`: "succeeded"
- `last_workflow_disposition`: "HOLD_AND_VERIFY"

### recovery_verification (soil_humidity_flatline cần)
- `monitor_state`: "OK"
- `sample_count`: 15 (phải >= 10)
- `virtual_pump_outputs_off`: True
- `sample_freshness_seconds`: 20 (phải 0-90)
- `verifier`: "auto_flatline_recovery_verified"
- `verified_at`: datetime

## EC2 access
- Instance: i-00bf2d3591d3ee0a2
- Region: ap-southeast-2
- Profile: aws-moi
- Python: /opt/smiot/.venv/bin/python
- App dir: /opt/smiot
- Env: source /etc/smiot/app.env
- PYTHONPATH: /opt/smiot

## Script template
Dùng code tương tự run_correlated_w3_w5.py nhưng viết inline Python để:
1. Tạo incident với upsert
2. Tạo evidence đầy đủ
3. Tạo action_ledger HOLD
4. Tạo scenario observations
5. Set all required fields

## Output
Ghi kết quả vào: outputs/demo_mvp/agent_ca2_log.md
Format: incident_id, status (OK/FAIL), từng field đã fill, errors nếu có
