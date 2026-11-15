# Agent Ca1 Log
Status: OK

incident_id: INC-SMIOT-SCENARIO-4BA1018CF70FBE24
SSM CommandId: df9a4315-ff1e-4b33-b6b9-66ccd7bc8947 (Status: Success)
Target: i-00bf2d3591d3ee0a2 (ap-southeast-2)

Fields filled:
- kind: false_offline
- status: recovered
- farm_key / node_id: greenhouse_a / 1
- scenario / scenario_code: f1_false_offline / F1
- monitor_id: 342585836
- workflow_id: ffd62026-6b63-40e4-9b46-6ac18d2d584f
- last_workflow_execution_id: 7077794c-38af-44ac-9e2f-bf0162ed5ad8
- last_workflow_status: succeeded
- last_workflow_disposition: REFUSED_RESTART
- evidence.trace_ids: ["5cdee52de6d94f1fadc1da561739154c"]
- evidence.workflow_observations: 1 entry (disposition REFUSED_RESTART)
- evidence.action_command_ids: ["INC-SMIOT-SCENARIO-4BA1018CF70FBE24:hold"]
- recovery_verification.computed_now: ONLINE
- recovery_verification.verifier: telemetry_health
- action_ledger: requested_at / acknowledged_at / verified_at đều có timestamp
- synthetic: True

Errors: none
