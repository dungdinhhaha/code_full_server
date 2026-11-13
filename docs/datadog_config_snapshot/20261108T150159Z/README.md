# Datadog configuration snapshot

Snapshot copied from outputs/datadog_config_export/20261108T150159Z on 2026-11-08.

## Contents

- json/: read-only JSON for the current US Datadog dashboard, 17 monitors, 1 SLO, 3 workflows, and other readable configuration inventory.
- terraform/: generated Terraform equivalents for the dashboard, monitors, SLO, and workflows.
- Parent README.md and json/manifest.json: scope and limitations.

## Important for a new Datadog account

This is a snapshot of the prior account. Dashboard, monitor, SLO, and workflow IDs in the JSON are identifiers from that account. They are useful as references, but they do not identify resources in a new account.

The Terraform is generated configuration, not a native Datadog UI export. Review the provider schema, update account-specific queries/tags as needed, then create resources in the new account. Do not run terraform apply against the existing account without importing and reviewing every resource; that may create duplicates or change live resources.

Provide credentials through local environment variables DD_API_KEY and DD_APP_KEY; never add them to these files. The export contains no credentials and no raw telemetry.

Some Cloud Cost configuration could not be exported: budgets returned 403 and no AWS CUR configuration was returned.
