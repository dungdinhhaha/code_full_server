# SMIOT W6 detector metric gap

Captured `2026-11-10` UTC. Read-only diagnosis; no application, MongoDB, MQTT, Agent, workflow, monitor, or actuator changes were made during this pass.

## Current verification

- Connected Datadog MCP query for `max:smiot.detector.heartbeat{*}` and `max:smiot.telemetry.samples_persisted{*}`, `now-2h` through `now`: no data.
- Datadog metric catalog search for `smiot.detector.heartbeat`, `now-2h`: no metrics matched.
- AWS MCP `ec2:DescribeInstances` was denied by an explicit AWS Organizations service control policy. This prevented a fresh read-only SSM inspection of the live application's DogStatsD sends and Agent detailed flush/error state.

## Source path and limitations

- `service/mqtt.py`: after telemetry persistence, each valid node reading calls `record_reading_transition(...)` and then `emit_count("smiot.detector.heartbeat", ["detector:agronomic_advisory", "result:completed"])` inside a `try` block. If the advisory call raises, the heartbeat call is skipped and only a generic warning is logged.
- `service/datadog_metrics.py`: `emit_count` returns immediately unless `DATADOG_METRICS_ENABLED` is true; it sends a UDP datagram to `DD_AGENT_HOST:DD_DOGSTATSD_PORT`, defaulting to loopback port 8125. Socket errors are silently swallowed by design.
- Per the 04:40Z Agent evidence, DogStatsD detailed per-metric stats were disabled. Aggregate packet counts therefore cannot establish that this particular metric was emitted or accepted by the Agent.

## Available live evidence

- `smiot_ssm_readonly_live_health_20261110T042737Z.md`: at 04:27Z, the app, MQTT, MongoDB, Wokwi bridge, external probe timer, and Agent were healthy; `/healthz` was HTTP 200, and latest Mongo telemetry was fresh. App flags showed metrics enabled, loopback Agent destination, and US1 site.
- `smiot_agent_key_rotation_evidence_20261110T044000Z.md`: at 04:40Z, Agent key validation succeeded, Agent reported zero submission errors and 27,106 flushed series, DogStatsD reported 3,570 packets and zero UDP packet-reading errors. No per-metric accounting was enabled. A non-actuating local canary and existing SMIOT metrics were not queryable.
- Same evidence file: the correctly nested direct US1 API canary was accepted (HTTP 202) and its metric metadata registered (HTTP 200), but repeated wildcard and exact-tag queries returned zero points through 04:54:28Z. This shows acceptance/metadata registration without query-visible point data.
- `20261110_backend_deployment.json`: a service bundle including `service/` was deployed successfully at 03:42Z; it records fresh application health, but does not provide a per-file artifact manifest proving the deployed MQTT source revision.

## Blocker

The app source contains a heartbeat emitter and aggregate Agent/app health indicators look healthy, but this pass cannot confirm that the running EC2 app emitted this exact metric or whether the Agent successfully forwarded that exact DogStatsD series. Current US1 query and catalog evidence still show no real heartbeat metric point. A fresh live per-metric inspection is blocked by the AWS Organizations SCP denial; Agent detailed DogStatsD accounting is also disabled in the currently recorded configuration. Do not create the W6 monitor until a fresh queryable `smiot.detector.heartbeat` point is observed.
