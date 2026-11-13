# SMIOT telemetry credentials and runbook

This AWS Terraform stack refreshes the Datadog credentials used by the SMIOT
application and its workflow bridge. It is separate from
`infra/datadog-workflows`; it does not edit Datadog monitors, dashboards,
workflows, or organization settings.

## Security model

- The API key comes from `D:\attt\APP_KEY.txt` field `api_keys`; the application
  key comes from field `APP_KEY`.
- Both are sent only at apply time to Parameter Store `SecureString` resources
  through Terraform's write-only `value_wo` arguments and ephemeral variables.
  Their values are not stored in Terraform state or plans.
- The EC2 role can read only the two SMIOT Datadog parameters. KMS decrypt is
  constrained to SSM in this region and to those parameter encryption contexts.
- The SSM document contains no credentials. It reads them at run time, validates
  both keys plus the current monitor and workflow IDs against Datadog US, updates the app env,
  restarts only the SMIOT app and an already-running bridge, and checks `/healthz`.
- It leaves the Agent untouched when its API key already matches. Recovery-log
  read access is restored for the existing `dd-agent` supplementary group.

## Apply

Read both values privately from the local file into process environment only,
then run `terraform init`, `terraform validate`, `terraform plan`, and `terraform
apply`. Do not pass either credential as a command-line argument or put it in a
`.tfvars` file. The AWS profile is `aws-moi` in `ap-southeast-2`; Terraform
fails closed unless it sees the expected account and exactly one running host
with the configured Name tag.

After apply, invoke `SMIOT-ApplyDatadogTelemetry` once with SSM Run Command.
Check the SSM result, app health, Agent status, and incoming `smiot.*` metrics.
