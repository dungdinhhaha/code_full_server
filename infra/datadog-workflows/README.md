# Datadog Workflow Automation

Manages the ten existing SMIOT workflows by Terraform. Supply credentials only through `DD_API_KEY` and `DD_APP_KEY` environment variables; do not store secrets in this directory. Import each existing workflow before applying. Specs are in `specs/` as JSON.

Provider compatibility notes:
- W1 retains the Datadog API-trigger rate limit in the applied JSON. Provider 4.30 rejects this API-supported field, so Terraform ignores W1 spec drift.
- W3 spec is ignored by Terraform after apply because Datadog normalizes terminal edge serialization; the live graph is confirmed by API read-back. Keep JSON specs as source of truth and review any future changes before applying.
