# End-to-end incident evidence

## Scope

This is one synthetic smart-farm incident executed on the AWS-hosted SMIOT app. The assigned lot is a clearly labeled demo fixture, not a verified real-world crop-to-sensor relationship: `melon-lot-local-demo-001` (`greenhouse_a/node 2`, mapping source `explicit_demo_fixture`). No physical probe failure or physical repair is claimed. The virtual PLC confirms only simulated outputs.

Canonical incident: `INC-SMIOT-20261103T102822-D3B0F8A7`

## Single incident timeline (UTC, 2026-11-03)

| Time | Evidence and result |
|---|---|
| 10:28:22 | MongoDB incident opened for `greenhouse_a/node 2`; explicit synthetic lot mapping attached. |
| 10:28:25 onward | Repeated Node 2 soil-humidity samples at 2.4% were received and persisted in MongoDB. The detector raised the Datadog flatline metric after its consecutive-sample rule. |
| 10:28:25 | One interlock record says the nominal rule would request irrigation (`2.4% < 30%`), but the active data-quality incident blocked it as `BLOCKED_HOLD`. No pump start was sent. |
| 10:34:02 | Datadog monitor `339977691` entered Alert. The bridge's low-latency fallback sent one virtual `HOLD`; ACK at 10:34:02.401 confirmed every simulated output was off. |
| 10:34:14 observed | Datadog workflow execution `72ae7b55-0fab-46a8-92eb-7760baaf47ff` was observed successful while the monitor was Alert. HOLD was already latched, so the repeated action was safely suppressed. **The workflow did not cause the earlier HOLD.** |
| 10:34:55 and 10:35:46 | The publisher acknowledged switching Node 2 back to variable normal readings; subsequent samples were persisted under the same incident and lot. |
| 10:38:19 | Datadog monitor was `OK`; the recovery verifier found six fresh, varying MongoDB samples (39.5–40.6%, newest 10:37:55, 23.4 seconds old). It issued `CLEAR` and accepted it only after the virtual PLC ACK confirmed safe mode false and all outputs off. Incident status became `recovered`. |

## Cross-system evidence

- **Datadog monitor:** [SMIOT Node 2 flatline monitor](https://app.datadoghq.com/monitors/339977691), current state `OK` after the observed Alert.
- **APM:** [US Datadog APM search for this incident](https://app.datadoghq.com/apm/traces?query=service%3Asmiot-smart-farm%20%40incident.id%3AINC-SMIOT-20261103T102822-D3B0F8A7&from_ts=1793700560000&to_ts=1793702360000&live=false) showed 76 matching spans at verification time.
- **Logs:** [US Datadog Logs search for this incident](https://app.datadoghq.com/logs?query=service%3Asmiot-smart-farm%20%22INC-SMIOT-20261103T102822-D3B0F8A7%22&from_ts=1793700560000&to_ts=1793702600000&live=false) showed 10 matching logs, including action transitions.
- **MongoDB:** `operational_incidents`, `telemetry`, `incident_telemetry_evidence`, `operational_decisions`, `action_ledger`, and `lot_sensor_assignments` retain the linked context. The incident stores 14 fault samples, trace/log correlation IDs, the workflow execution, one blocked decision, acknowledged HOLD, verified CLEAR, and the recovery sample IDs.
- **Timing:** monitor detection to HOLD ACK was about 0.2 seconds. HOLD ACK to verified recovery was about 4 minutes 17 seconds.

## Datadog Bits investigation (same monitor alert)

- The completed Bits Investigation is [here](https://app.datadoghq.com/bits-ai/investigations/008cc971-b1be-4453-a9f4-fa947a704f51?investigation-view__mode=tree). It took 3 minutes and shows **1 verified hypothesis, 10 rejected hypotheses**.
- Its verified root cause is the synthetic source scenario: `smiot_demo_stream` began sending fixed 2.4% readings for `greenhouse_a/node 2`, replacing readings around 40%. Bits found other farms/nodes remained around 39–41%, MQTT and MongoDB stayed healthy, processing spans returned OK, and no physical actuator was triggered. This is a verified cause of the **simulation**, not proof of a physical probe failure.
- Bits' investigation timeline covers about 17:28–17:32 GMT+7. It reports a recovery-verifier attempt at 17:33 that correctly refused CLEAR because the monitor was still `ALERT`. Actual verified recovery happened later at 17:38; the investigation's historical “uncleared” finding was accurate at its timestamp, but it did not refresh to include the later recovery.
- Separately, the Bits Chat panel showed **6 of 19 events received** and an initial “no matching logs” message. That is a chat retrieval indicator, not the completion status of the Bits Investigation above. The UI does not explain what the denominator 19 represents, so its exact cause is unverified.
- A Datadog query confirmed the old correlation weakness: structured `@incident.id:<id>` and `@node:2` searches returned 0, while a free-text search for `node2_soil_humidity` plus the incident ID returned 20 telemetry log lines. Those dimensions existed only inside message text.

## Structured log correlation fix (2026-11-03)

- Updated the app to emit telemetry and action transitions as JSON lines in `/opt/smiot/logs/incident_events.jsonl`, with structured nested attributes `incident.id`, `farm.key`, and `node.id`; the Datadog Agent tails this file as `service:smiot-smart-farm`.
- Verified Agent configuration and restarted Agent and app services; both reported active. Wrote one explicit `structured_log_schema_validation` marker for this incident and confirmed Datadog returned it using the structured query below. The marker is a schema validation event, **not** a new sensor sample or action.
- Verified query: `service:smiot-smart-farm @incident.id:INC-SMIOT-20261103T102822-D3B0F8A7 @farm.key:greenhouse_a @node.id:2 @kind:structured_log_schema_validation` returned 1 log with all four parsed facets.
- This fixes correlation for new telemetry/action events. It does not retroactively convert the 20 historical plain-text telemetry logs, nor establish the undocumented meaning of Bits Chat's `6/19` counter.

## Honest boundary

This run proves the simulated data path, monitor, workflow observation, interlock, virtual action ACK, lot-scoped incident record, guarded recovery verifier, and a completed Bits root-cause investigation on one incident. The workflow's HOLD branch was deduplicated because the bridge had already acted; the bridge fallback was the actual HOLD sender. Bits correctly identified the synthetic source injection and correctly recorded that CLEAR was blocked while the monitor was still alert; its time window ended before the later recovery. New application logs now expose structured incident/farm/node dimensions; historical logs remain unparsed. Bits Chat's separate 6/19 retrieval counter is still undocumented. The lot assignment is synthetic, and this proves no physical hardware behavior. The Datadog API key used by the app could not read metric/span/log search APIs (403); the US Datadog UI/MCP were used to verify logs and spans, and the monitor API confirmed current state. No 7-day SLO claim is made.

## Relevant implementation

- `service/incident_lifecycle.py`
- `service/telemetry_health.py`
- `service/mqtt.py`
- `service/observability.py`
- `service/operational_evidence.py`
- `service/traceability.py`
- `pages/traceability.py`
- `scripts/wokwi_datadog_bridge.py`
- `scripts/verify_and_clear_demo_safe_mode.py`
