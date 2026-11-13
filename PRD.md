# PRD — SMIOT Greenhouse Operations Center

**Date:** 2026-11-10  
**Status:** Working product requirements; separate code, deployed state, and verified evidence.

## Product
A single operations center for ten virtual muskmelon greenhouses. Operators should see which farm needs attention, open one incident, understand the evidence, choose a guarded response, and verify recovery. It is an operational simulation; device telemetry and actuators are virtual unless a physical source is explicitly integrated and verified.

## Users and outcomes
- **Farm operator:** see farm health and crop risks; understand what needs action now.
- **On-call engineer:** investigate service, MQTT, MongoDB, detector, and actuator faults without broad/reckless restarts.
- **Judge/demo audience:** follow one incident consistently from signal to investigation, safe action/refusal, persisted evidence, and recovery.

## Scope
- Ten farms (`greenhouse_a` through `_j`), farm/device-specific telemetry, nine virtual device categories per farm, MongoDB Community as operational store, MQTT command/status ACK, app notifications, Datadog monitors/workflows/Bits, and guarded AWS service recovery.
- Existing catalog of 36 scenarios is reused; do not make a second simulator or scenario catalog.
- Local source now includes bearer-token start/stop/status routes for virtual scenarios; deployment, token provisioning, rate behavior, and simulator ACK still need runtime acceptance.
- No pump/valve/fan hardware operation. Simulated actuator controls remain virtual and fail-safe.

## Product acceptance
1. Home gives one legible ten-farm overview across multiple relevant indicators, not a single humidity metric; clicking a farm opens that farm directly without full-page reload.
2. Each scenario run has unique `scenario_run_id` and `incident_id`, explicit synthetic provenance, allowlisted farm/scenario, an operator/action record, and run status.
3. Simulated devices have independent identity, cadence, readings, sequence/boot context, and command ACK; one scenario affects only its declared scope unless explicitly configured as a concurrency drill.
4. A safe start/stop/status API is authenticated with a separately provisioned admin-controlled bearer token, idempotent, rate-limited, and never targets physical hardware.
5. For priority workflows, one correlated incident can be followed through monitor → investigation → guarded action or refusal → MongoDB/action evidence → verification → app notification. Unknown verification never means recovered.
6. Dashboard, monitor, workflow, evidence, and app notification state correspond to the same incident/run; no assembled screenshots from unrelated drills are presented as one incident.

## Priority
First: W4 → W1 → W9 → W2 → W5 → W3. Then close W6 and improve W7/W8/W10. W6 heartbeat is already present in local source and Terraform; prove deployed ingestion and live monitor rather than creating a duplicate.

## Out of scope
Real crop-yield promises, validated agronomy claims without an expert-approved source, real actuator control, automatic EC2 reboot, fabricated AWS/Datadog costs, and claiming a workflow is Level 5 solely because its monitor or Bits toggle is enabled.
