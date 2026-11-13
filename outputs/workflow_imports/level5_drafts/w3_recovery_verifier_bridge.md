# W3 recovery verifier bridge

## What this local backend route verifies

`POST /api/integrations/datadog/recovery-verification` is read-only. It accepts a Datadog HTTP Connection bearer token and JSON:

```json
{
  "workflow_run_id": "<Datadog InstanceId workflow-run UUID>",
  "instance_id": "<configured SMIOT EC2 instance ID>"
}
```

The current W3 SSM document call passes Datadog's documented `{{InstanceId}}` workflow-run ID as the `IncidentId` SSM parameter. The bridge uses AWS Systems Manager `ListCommands` filtered by the fixed document and configured instance, matches `Parameters.IncidentId` exactly, requires one unique command, then calls `GetCommandInvocation`. It checks the guarded recovery script's final JSON output and current app/MongoDB/MQTT health plus telemetry freshness (maximum 180 seconds). It returns `pending` while the command is not visible/running or the health/fresh telemetry gate is not yet satisfied. It reports `recovered` only when the SSM invocation succeeded and the guard output says the guarded `start` was verified. If the guard says the app was already healthy, it reports `already_healthy`; this does not claim a restart. Refusal, failure, multiple matching commands, missing/invalid output, a bounded search limit, or unavailable AWS read access never counts as recovery.

## Runtime configuration

- Existing `DATADOG_APP_NOTIFICATION_TOKEN` on the app and matching bearer auth in Datadog's `SMIOT_APP_HTTP` connection.
- `SMIOT_RECOVERY_INSTANCE_ID` set to the single approved instance ID.
- `AWS_REGION=ap-southeast-2`.
- The app's AWS runtime identity needs `ssm:ListCommands` and `ssm:GetCommandInvocation`. AWS only supports resource-level restrictions for these read APIs through `Resource: "*"`, so the API itself enforces the fixed SSM document and one configured instance. If an SCP or role denies either action, this verifier returns unknown; it does not bypass policy.
- `boto3` and `botocore` are already project dependencies.

## Workflow integration gate

The current published W3 JSON only contains `com.datadoghq.aws.system_manager.sendCommand` followed by an app notification. The bridge deliberately avoids depending on the SendCommand output. Workflow integration still requires an explicit notification or HTTP request node to pass `{{InstanceId}}` and the configured EC2 instance ID, plus a documented bounded retry/branch for `pending`, `recovered`, `already_healthy`, and `not_verified`. Historical drafts using `com.datadoghq.aws.system_manager.getCommand` and `{{ Steps.Send_command.command.CommandId }}` are unverified experiments, not evidence of a supported Datadog action schema. Therefore the published workflow must remain explicitly **pending verification** until the HTTP node is configured and its execution is read back.

This local route and its tests are not deployed, the app AWS permission is not confirmed, and no SSM command or live recovery was run for this change.
