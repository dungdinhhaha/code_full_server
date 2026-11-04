# End-to-end incident evidence — 2026-11-03

## Scope and conclusion

Canonical incident: `INC-SMIOT-20261103T114321-BD19A22C`.

This is one synthetic incident executed through the AWS-hosted SMIOT application. Node 2's publisher was deliberately switched into a flatline mode at 2.4% and later returned to variable readings. The evidence proves that the telemetry pipeline detected the synthetic condition, held the virtual outputs safely, and cleared the virtual hold only after verified recovery. It does **not** prove physical probe failure or repair, nor operation of a physical pump or PLC.

The Bits Investigation for this same monitor incident is [available in Datadog](https://app.datadoghq.com/bits-ai/investigations/3de8802a-d62c-4983-b2d9-07c7dc3bdf1c?investigation-view__mode=tree). Its corrected conclusion identifies the injected flatline scenario and rejects instrumentation/data-loss, monitor-state, resource-exhaustion, and deployment hypotheses. The initial pass incorrectly marked an instrumentation gap as verified; after feedback and a resumed investigation, that hypothesis was rejected based on advancing sample sequence numbers and telemetry logs.

## Timeline (UTC, 2026-11-03)

| Time | Evidence |
|---|---|
| 11:43:21 | Incident opened for `greenhouse_a`, Node 2. The publisher ACKed the requested synthetic flatline mode. |
| 11:43 onward | Node 2 kept sending and MongoDB kept persisting 2.4% soil-humidity samples. The sample sequence advanced (14 inspected telemetry events covered sequence 301–353), so this was not a stopped publisher or missing instrumentation. |
| 11:48:51 | Datadog monitor `339977691` entered Alert. |
| 11:49:59.805 | `datadog_safe_mode_workflow` HOLD was acknowledged in the action ledger. Virtual outputs remained OFF. |
| 13:36:45 | Publisher ACKed return to normal mode; the first varying soil-humidity sample was 40.8%. |
| 13:39:45.903 | Latest of seven fresh, varying MongoDB recovery samples; values ranged from 39.3% to 41.0%. |
| 13:39:56.487 | Monitor was OK; the application recovery verifier accepted the seven fresh samples and acknowledged HOLD record, sent CLEAR, received the virtual PLC acknowledgement, verified all virtual pump outputs OFF, and marked the MongoDB incident `recovered`. |

Times are UTC. Datadog UI displays UTC+07:00 for this account.

## Follow the evidence

- **Monitor:** [Node 2 soil-humidity flatline](https://app.datadoghq.com/monitors/339977691). It is currently `OK`; the event timeline contains the Alert and subsequent recovery.
- **Bits:** [Corrected investigation](https://app.datadoghq.com/bits-ai/investigations/3de8802a-d62c-4983-b2d9-07c7dc3bdf1c?investigation-view__mode=tree). Use this investigation for the canonical incident rather than the older Bits Chat's partial retrieval view.
- **Logs:** [Correlated incident logs](https://app.datadoghq.com/logs?from_ts=1793706000000&live=false&query=service%3Asmiot-smart-farm%20%40incident.id%3AINC-SMIOT-20261103T114321-BD19A22C%20%40farm.key%3Agreenhouse_a%20%40node.id%3A2&stream_sort=asc&to_ts=1793713482142). The monitor message now also includes a [live Node 2 log query](https://app.datadoghq.com/logs?query=service%3Asmiot-smart-farm%20%40farm.key%3Agreenhouse_a%20%40node.id%3A2%20%40source%3Asmiot_demo_stream), using structured log attributes rather than treating them as tags. The live query was verified to return 10 matching logs at the time of this run.
- **APM:** [Traces correlated to the incident ID](https://app.datadoghq.com/apm/traces?end=1793713483043&historicalData=true&paused=true&query=service%3Asmiot-smart-farm%20%40incident.id%3AINC-SMIOT-20261103T114321-BD19A22C&start=1793706000000). Search by the same incident ID to follow the application's processing and action spans.
- **MongoDB action/incident records:** `operational_incidents` records the incident lifecycle and recovery; `action_ledger` records HOLD and verified CLEAR; telemetry records provide the samples used by the recovery verifier. The verifier explicitly leaves virtual pump outputs OFF.
- **AWS verifier:** `scripts/verify_and_clear_demo_safe_mode.py` is deployed on EC2. Its idempotent retry path was corrected so an already-verified CLEAR returns success before checking a rolling window that has since expired. A repeat invocation returned `already_verified_and_cleared` for this incident.

## Bits “6/19” status

The older Bits Chat displayed `6/19` events received. That view was attached to an earlier alert/chat context, while the current canonical incident has its own completed investigation. The UI/API evidence available here does not define what the denominator 19 counts, so its exact retrieval cause remains **unverified**. Do not describe `6/19` as the number of investigation hypotheses or claim it was fixed. The current Bits investigation is complete and has a corrected conclusion; the separate counter remains unexplained.

## Datadog monitor log correlation

The monitor message was updated in US1 to include a structured-attribute log link for `service:smiot-smart-farm`, `@farm.key:greenhouse_a`, `@node.id:2`, and `@source:smiot_demo_stream`. The Alert message still contains the existing `@workflow-smiot-node-2-safe-mode-hold-and-verify` trigger. Both Alert and Recovery messages now include the log link. Opening the query returned logs, including post-recovery telemetry. This improves navigation/correlation; it does not cause the logs themselves to acquire an `incident.id` when none is present.

## Limits

- This proves a synthetic source-mode transition and the application's safe handling. It does not diagnose or repair real hardware.
- The lot association is a synthetic demo mapping; no real crop-lot impact is asserted by this evidence.
- Bits' separate `6/19` retrieval denominator remains unexplained.
- The verified CLEAR applies only to the virtual PLC outputs; every simulated pump output stayed OFF.

