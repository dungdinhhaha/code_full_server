# SMIOT Datadog dashboards — staged configuration

This Terraform module defines **five additional dashboards**. It intentionally does not manage the existing `nkc-685-vw8` dashboard, so applying this module will preserve it. The target is five custom dashboards from this module; the existing dashboard remains unmanaged.

## Views

1. `SMIOT | 10-Farm Portfolio`
2. `SMIOT | Incident & Recovery`
3. `SMIOT | IoT & MQTT Fleet`
4. `SMIOT | App, EC2, MongoDB & AI`
5. `SMIOT | Farm Data Quality`

The farm template variable includes `greenhouse_a` through `greenhouse_j`, verified in Datadog metric tag values. The widgets use metric names and dimensions observed in the current account. The existing dashboard's 12 widgets and its ID are untouched.

## Apply prerequisites

- Datadog US1 API endpoint is the default in `main.tf`.
- Supply `DD_API_KEY` and `DD_APP_KEY` through the environment or a secret manager. Do not put credentials in Terraform files, `.tfvars`, shell history, or source control.
- The Datadog MCP connection currently allows reads only. This module has **not** been applied to Datadog.
- Check the Terraform plan carefully before applying. It should show five dashboard creations and no changes/deletions to any existing dashboard.

## Known scope limits

- The 10 farm values are observed metric tags; the dashboard does not claim every farm has every metric continuously.
- MongoDB and host metrics are infrastructure-wide rather than farm-scoped.
- AI latency is available as a trace distribution. A verified AI error metric was not found, so no AI error widget is fabricated.
- Cloud Cost Management metrics were not verified in this organization, so the dashboard explains their omission rather than showing guessed cost data.
- Memory is labeled as a fraction (0–1), matching the metric's observed values; it is not falsely formatted as a percentage.
