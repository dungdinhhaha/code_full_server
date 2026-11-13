# Datadog incident-scenario Terraform draft

This folder is a **guarded monitor draft**. Both monitor resources are disabled
by default and have an explicit precondition requiring the corresponding metric
to be confirmed in Datadog Metrics Explorer. Do not apply this folder before the
application metrics are deployed and observed.

## Why there are no scenario monitors yet

The current application emits sensor health gauges and a few telemetry metrics
through DogStatsD. The MQTT handler now emits the following count metrics and
structured logs when it persists a new virtual safety-trip or ACK record:

- `smiot.virtual_plc.safety_trip`
- `smiot.virtual_plc.safety_ack`
- metric tags include bounded `farm`, `source`, `fault_code` (plus the fixed
  actuator/event dimensions); correlation IDs remain in structured logs, not
  metric tags.

The provenance emitters define `smiot.device.reboot_detected`,
`smiot.telemetry.sequence_gap`, `smiot.telemetry.sequence_duplicate`, and
`smiot.telemetry.sequence_regression` as DogStatsD counts. Before enabling those
monitors, confirm that the app's ingest path calls the emitter, and verify each
metric in Datadog. A function definition alone is not proof of emitted data.

Until the app changes are deployed and each metric is visible in Datadog, its
Terraform gate must remain disabled. The current Agent log config tails
incident/recovery JSONL files; it does not establish that virtual PLC MQTT events
are already present in Datadog Logs.

Creating a monitor against a guessed metric or an unshipped log would create a
green-looking configuration that cannot detect the scenario. The local
`outputs/datadog_config_export/20261108T150159Z/terraform` bundle is the exported
configuration of the existing Datadog account (dashboard, monitors, SLO and
workflows); its README confirms that it has not been imported or applied.

## Implemented signal versus Datadog readiness

| Scenario / signal | Current producer | Datadog-ready? | Next prerequisite |
|---|---|---:|---|
| Soil flatline | `smiot.telemetry.sensor_flatline` DogStatsD gauge | Yes; existing monitor is in the account export | Import existing monitor into state before managing it |
| UI status mismatch | `smiot.telemetry.status_mismatch` DogStatsD gauge | Yes; existing monitor is in the account export | Import existing monitor into state before managing it |
| Stale sensor sample | `smiot.telemetry.sample_age_seconds` DogStatsD gauge | Yes; existing monitor is in the account export | Import existing monitor into state before managing it |
| Pump runtime/volume or low-pressure/high-flow trip | Virtual PLC MQTT event + ACK; MQTT handler emits `smiot.virtual_plc.safety_trip` and `smiot.virtual_plc.safety_ack` counts and structured logs | Pending live ingestion | Deploy with DogStatsD enabled and verify both metrics in Datadog; monitor remains opt-in |
| Pump on, no flow/pressure feedback | App finding `pump_on_without_water_feedback` | No | Persist/emit the finding as a bounded metric or JSON log and confirm it reaches Datadog |
| Simulated pipe pressure/flow mismatch | `pipe_leak` scenario drives virtual high flow + low pressure; virtual PLC emits a safety trip and closes the valve | App-level simulated signal exists; Datadog ingestion must still be confirmed | Trip monitor observes the interlock event and fault-code tag. It does not diagnose a physical pipe leak; confirm the synthetic metric in Datadog first |
| Vent stuck | Virtual PLC mismatch is available in MQTT telemetry | No | Forward the state/finding to Datadog; confirm tag dimensions and sample cadence |
| Soil spike / out of range | Scenario injection exists; generic signal path is not yet represented in Datadog | No | Emit validated bounded finding metrics/logs; then add monitors |
| Reboot / sequence provenance | DogStatsD count emitter functions define reboot, gap, duplicate and regression metrics | Not confirmed end to end | Ensure `emit_provenance_metrics` is called by the live ingest path and observe the metrics before enabling the gated monitors |

## Guarded monitor resources in this draft

- `datadog_monitor.virtual_plc_safety_trip[0]`: fires when the safety-trip count
  is greater than zero in five minutes. It records the local protective stop;
  it does **not** diagnose a physical pipe leak and must not restart a pump.
- `datadog_monitor.virtual_plc_safety_ack_imbalance[0]`: compares trip and ACK
  counts by farm and fault code over five minutes. This is only an **aggregate**
  imbalance; it cannot prove which command missed an ACK. Use the structured
  log's `command_id`/`scenario_run_id` for exact correlation.
- `datadog_monitor.device_reboot_event[0]`: flags an observed reboot count;
  a reboot may be planned maintenance and is not automatically a fault.
- `datadog_monitor.telemetry_sequence_gap[0]`: flags missing sequence numbers;
  it does not identify which transport or persistence layer lost the sample.
- `datadog_monitor.telemetry_sequence_integrity[0]`: flags duplicate or
  regressing sequence counts; investigate using boot/sequence provenance.

All `enable_*` variables default to `false`. Enable only after the signal
producer is deployed and the metrics are observed. No Datadog API write or
Terraform apply has been performed.

## Resource-creation gate

For each future monitor or workflow, all of these must be true before adding a
Terraform resource:

1. The signal name, count semantics and tags are implemented in app/edge code.
2. The signal is observed in Datadog Metrics or Logs from an actual scenario run.
3. The query returns the expected time series/logs with bounded tags (`farm`,
   `device_type`, `source`); put run/incident IDs in logs, not metric tags.
4. The recovery query and no-data behavior are decided and written down.
5. Existing resources are imported into Terraform state before any plan that
   could replace or duplicate them.

Do not apply the existing account snapshot as a new-account bootstrap without
review: monitor IDs, dashboard references and workflow handles belong to the
exported Datadog organization.

