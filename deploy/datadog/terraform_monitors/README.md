# SMIOT core monitors

This standalone US1 module defines 14 core Datadog monitors plus the W6 detector
heartbeat no-data monitor. It manages no
dashboard, workflow, or existing monitor. Credentials are read only from
`DD_API_KEY`/`DD_APP_KEY` by the Datadog provider and are not stored here.

The telemetry signals and tags are limited to the verified SMIOT metric names:
`status_mismatch`, `fresh`, `sensor_flatline`, `sample_age_seconds`,
`soil_ec`, `air_humidity`, `soil_humidity`, `air_temperature`,
`soil_temperature`, `samples_persisted`, `ingest_lag_ms`, Mongo/MQTT dependency
gauges, `systemd.unit.active`, and the two verified SMIOT traces. The three
environmental monitors use absence detection; no unverified value thresholds
are invented.
W6 additionally needs `SMIOT_DETECTOR_METRICS_ENABLED=true` on the app and uses
a five-minute no-data alert grouped by farm; do not apply this module until the
heartbeat metric has been observed in Datadog.

Run `terraform init` then `terraform fmt -check` and `terraform validate`.
This task intentionally does not run `terraform apply`.
