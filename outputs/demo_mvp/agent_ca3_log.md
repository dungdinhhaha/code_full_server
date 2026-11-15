# Agent Ca3 Log
Status: OK

incident_id: INC-SMIOT-SCENARIO-9EC2241CCB2F4236
SSM CommandId: a01c7f4d-1f77-42e0-bd01-29e530c5b02e (Status: Success)
Target: i-00bf2d3591d3ee0a2 (ap-southeast-2)

Fields filled:
- kind: service_down
- status: recovered
- farm_key / node_id: greenhouse_c / 1
- scenario / scenario_code: h1_service_down / H1
- monitor_id: 342585838
- workflow_id: 373ed0c0-4509-4fcd-a067-f54f0becc00e
- last_workflow_execution_id: 1567b5d6-6028-416c-afa5-5c0ca1eaeb67
- last_workflow_status: succeeded
- last_workflow_disposition: GUARDED_RECOVERY
- evidence.trace_ids: ["194897ec800c4ac7b1955f8d6647f0cd"]
- evidence.workflow_observations: 1 entry (disposition GUARDED_RECOVERY)
- evidence.action_command_ids: ["INC-SMIOT-SCENARIO-9EC2241CCB2F4236:hold"]
- recovery_verification.http_status: 200
- recovery_verification.verifier: smiot_external_probe
- action_ledger: requested_at / acknowledged_at / verified_at đều có timestamp
- synthetic: True

Errors: none
