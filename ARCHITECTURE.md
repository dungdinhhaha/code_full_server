# ARCHITECTURE — SMIOT Operations Center

**As of 2026-11-10.** This describes the observed repository plus target changes; labels matter.

## Current system (repository inspection)
- NiceGUI application (`main.py`, `pages/`, `service/`). Ten farms are listed in `service/farm_registry.py`.
- Virtual telemetry/device simulation is embedded in the app; MQTT transports virtual controls/status and ACKs. The application has a 36-scenario catalog, scenario run/evidence modules, and an admin `/plc` scenario interface.
- MongoDB Community is the operational persistence target for telemetry and incident/action evidence. Mongo readback is part of recovery verification.
- Datadog integration emits metrics/traces/log context, provides monitors and workflow automation; Terraform monitor files include W6 detector heartbeat.
- W6 detector heartbeat code runs as an app-owned background thread. It is not an independently restartable process. App and simulator share process fate: an app outage can stop both telemetry simulation and the in-process detector.

## Main data path
`virtual devices → MQTT → ingest/validation → MongoDB telemetry → detector/scenario evidence → Datadog metrics/logs/traces/monitor → Bits investigation → guarded workflow/bridge → MQTT ACK or service recovery → MongoDB readback → app incident/notification`

Datadog observes and coordinates; local interlocks own immediate safety. MongoDB stores operational history/evidence. The app is the operator surface. Correlation IDs must be carried as log/span fields and Mongo documents, not high-cardinality metric tags.

## Proposed external control boundary
The source now has opt-in external control routes `POST /api/demo/scenarios` and `GET /api/demo/scenarios/{scenario_run_id}`. They require a separate bearer secret named `SMIOT_DEMO_CONTROL_TOKEN`, validate farm/scenario/node against allowlists, and only publish synthetic messages to `farm/demo/control`. `POST` requires `Idempotency-Key`; MongoDB stores a hashed token-scope/key and body fingerprint, so retries replay rather than republish. It atomically reserves a per-farm API lock, refuses active/reused runs, and returns `queued`, not an applied/ACK claim. Stop is run/farm-scoped and status exposes the latest run-scoped ACK so the caller can verify the matching command. A Mongo-backed limiter allows 20 writes and 120 status reads per token during a 60-second window. The routes were deployed to EC2 on 2026-11-10. Token presence was not confirmed, so API runtime use is not verified and requests remain unavailable until that token is configured. Reuse the existing scenario service and `/plc` behavior. Never accept arbitrary shell commands, metric names, MQTT topics, or physical actuator targets.

## Recovery boundaries
- **W4:** refuse action when fresh health/telemetry contradicts a restart hypothesis; prove no AWS command was issued.
- **W1/W9:** virtual PLC/interlock reaches a safe state locally; cloud workflow cannot replace the local safety response.
- **W2/W5:** resolve data freshness or the specific dependency; avoid restarting unrelated services.
- **W3:** guarded app-service recovery only; verifier checks health, MongoDB/MQTT, and newly persisted telemetry. Notify recovered only after verifier success.
- **W6:** local code now separates the app watchdog heartbeat from detector evaluation freshness, and Terraform was updated locally to query evaluation freshness. Both are emitted by an app-owned thread; live deployment/ingestion/monitor behavior remains unverified. Do not claim detector-only restart until isolated or given a bounded, safe reset operation.

## Deployment model
EC2 in `ap-southeast-2` hosts the app, MongoDB Community, MQTT/service components and Datadog Agent according to existing deployment configuration. The 2026-11-10 source rollout preserved the dirty worktree, created an EBS snapshot and rollback archive, and passed health checks. Repeat those safeguards for future deployments. Datadog configuration must be checked in the logged-in US1 organization; do not use a connector if it resolves to another org.

## Failure isolation / concurrency
Each scenario run is isolated by `scenario_run_id`, farm, device scope, and time. Multiple faults on one farm can coexist only when declared; their event streams and monitors must not cross-close. Shared services may create a common-cause incident, but each child fault keeps its own evidence. Use bounded queues/timeouts and idempotency for duplicate/retried actions.
