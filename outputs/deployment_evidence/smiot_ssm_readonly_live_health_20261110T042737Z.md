# SMIOT read-only live health check

Captured `2026-11-10T04:27:37Z` UTC. Diagnostics ran through SSM Run Command. Commands only read service state, app health, existing environment flags (not credentials), and the newest MongoDB timestamp. No services, publishers, workflows, or actuators were started, stopped, or changed.

## Readout

| Component | State at check | Notes |
|---|---|---|
| `smiot.service` | active/running/enabled | Local `/healthz` returned HTTP 200 at 04:27:37Z. |
| `mosquitto.service` | active/running/enabled | MQTT broker is up. |
| `mongod.service` | active/running/enabled | MongoDB ping succeeded. Latest telemetry record had `source:smiot_demo_stream`, timestamp `2026-11-10T04:26:04.394Z`, age 10.1 seconds at 04:26:14Z. |
| `wokwi-bridge.service` | active/running/enabled | Bridge is running. |
| `wokwi-sim.service` | inactive/dead/static | On-demand Wokwi cloud simulator; bootstrap bounds each run to 5 minutes. It is not the current publisher: recent Mongo rows are from the app's synthetic `smiot_demo_stream`. No Wokwi start was needed; avoided consuming simulator quota. |
| `smiot-external-probe.timer` | active/waiting/enabled | One-shot probe service is inactive/dead/static between timer runs, as expected. Its most recent result was `success`; the timer is actively scheduling it. |
| `datadog-agent.service` | active/running/enabled | DogStatsD port 8125 is configured. App flag `DATADOG_METRICS_ENABLED=true`; destination is US1 (`datadoghq.com`). No credential values were read. |

## W6 signal and blocker

The app's synthetic publisher is currently active; latest Mongo telemetry is fresh. The application, MQTT broker, MongoDB, bridge, external probe timer, and Datadog Agent all report active. This rules out a stopped synthetic publisher as the current cause of the missing W6 series.

A Datadog US1 metric query at approximately `2026-11-10T04:26Z` returned no points for `smiot.detector.heartbeat`, `smiot.detector.scenario_evaluation.completed`, `smiot.telemetry.samples_persisted`, or `smiot.external.app_up` in the previous hour. Thus the remaining blocker is the metrics delivery/instrumentation path: the checked-out source has a detector heartbeat emission, but live Datadog does not show that metric despite fresh Mongo writes and active Agent/probe. This read-only check cannot distinguish an undeployed code version from an Agent forwarding/auth/network issue; no deployment was attempted because the source checkout is broadly dirty and metrics are not currently observable.

No publisher was started. The only stopped candidate found is the separate, on-demand Wokwi simulator; current synthetic telemetry continues without it. Physical actuator units/commands were not queried or touched.

## Run references

- First read-only SSM check command: `1cbeae2b-5ce8-4e75-bfbb-59bea097b0f5` (completed, exit 0 at 04:26:14Z).
- Agent/config/probe health SSM check: `d691db93-d048-40b5-a415-465ac8bee34f` (completed, exit 0 at 04:26:58Z).
- Probe timer and local health SSM check: `03edb7da-d750-4e60-88a4-8c6a9b38b692` (completed, exit 0 at 04:27:37Z).
- Datadog US1 metrics query at ~04:26Z: no data for the four W6-related/app-pipeline metrics above.
