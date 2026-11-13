# DESIGN — Contracts and operator experience

## Incident envelope
Every finding/action/evidence record should carry: `incident_id`, `scenario_run_id` (when a drill), `farm_key`, affected device/node, scenario code, `source`, `synthetic`, event time, severity, status, and evidence references. Include `lot_id` only when a verified farm/time assignment exists. Keep metric tags bounded (`farm`, `node`, `component`, `env`, `source`); put incident/run/command IDs in logs, traces, and MongoDB.

## Scenario API contract
- Existing local routes: `POST /api/demo/scenarios` (start/stop) and `GET /api/demo/scenarios/{scenario_run_id}` (status). They are opt-in via `SMIOT_DEMO_CONTROL_TOKEN` and use bearer authentication. The routes were deployed to EC2 on 2026-11-10; token configuration and external-call/ACK proof remain.
- Start: accept only known farm and catalog scenario; require `Idempotency-Key`; reserve the farm against concurrent API runs and reject reused run IDs; reply `queued` until simulator ACK is persisted. Current Mongo-backed limit is 20 write requests per token per 60 seconds.
- Status: return `queued|running|awaiting_ack|verifying|recovered|refused|failed|stopped|unverified`, timestamps, and sanitized evidence links; scope lookup to the run. Current limit is 120 reads per token per 60 seconds.
- Stop: cancel only the virtual scenario; await matching MQTT status ACK; record an audit entry. A successful publish is not stop confirmation. Compare the stop response command ID to the run-scoped latest ACK.
- Errors are explicit (`401/403`, `409` concurrent run, `422` invalid scenario, `429` rate limit, `503` dependency unavailable). Never return recovered on an accepted command alone.

## Recovery state machine
`DETECTED → INVESTIGATING → DECISION → ACTION_REQUESTED/REFUSED → ACKNOWLEDGED → VERIFYING → RECOVERED | UNVERIFIED | FAILED`

Requirements: same incident ID throughout; action guard before any action; unique command/idempotency key; capped retry and cooldown; ACK correlated to command/run; read-after-write Mongo check; fresh telemetry or service health; final notification only after verification. A refusal is a valid completed safe outcome when evidence shows action was unnecessary. No proof means `UNVERIFIED`, not success.

## W1–W10 demo contract
| Workflow | Trigger and evidence | Safe response | Recovery proof |
|---|---|---|---|
| W1 PLC trip | trip metric + PLC/MQTT log/trace + run/farm | local interlock; cloud investigates, no unsafe output | PLC ACK/readback, safe outputs, correlated ledger |
| W2 flatline | per-node fresh sample/sequence evidence + Mongo time series | HOLD decisions using stale/flat signal | changing, newly persisted samples and monitor recovery |
| W3 app service | service metric + logs/APM + guarded SSM evidence | restart only app service when guard permits | health + Mongo/MQTT + new persisted telemetry, then notify |
| W4 mismatch | fresh health/telemetry contradicts restart hypothesis | REFUSE; zero restart/SSM action | service remains healthy and refusal recorded |
| W5 dependency | separate Mongo and MQTT signals/logs | remediate only the failed dependency; otherwise no-op | connection/read/write or MQTT round trip + new Mongo sample |
| W6 detector | independent heartbeat, input age, evaluation age | alert/escalate; do not claim detector-only restart while same app process owns it | fresh heartbeat and completed evaluation after recovery |
| W7 soil moisture | trusted sensor, stage/config version, lot relationship | advisory/HOLD or human approval; no unapproved irrigation | fresh persisted data and decision record |
| W8 VPD/EC | validated environment readings and crop context | advisory/human approval | post-action sensor confirmation or explicit no-action result |
| W9 no ACK | command ID, expected ACK deadline, device state | suppress duplicate command; virtual safe mode | matching new ACK/readback and safe-state confirmation |
| W10 AI provider | provider error/latency + trace + decision context | deterministic safe fallback/HOLD; no stale AI result | provider success plus fresh valid decision trace |

## Operator screen
Home: one multi-signal status visualization for ten farms, freshness and open incident count; selecting a farm navigates directly. Below: active incidents/notifications with owner, age, severity, current step and clear next action. `/incident` is the single case timeline, linking to monitor, logs/traces, workflow run, Mongo evidence and application notification. Use plain labels and show synthetic provenance in detail/evidence views.

## Collision policy
- Different faults on the same device: preserve separate findings and command IDs; aggregate under a parent incident only if a shared cause is evidenced.
- Multiple farms: never apply a farm-specific command to another farm.
- Shared Mongo/MQTT outage: create one dependency incident with affected farms as evidence; do not emit ten contradictory recovery actions.
- Replayed or duplicated events: deduplicate by source event/command key and never close another scenario's incident.
