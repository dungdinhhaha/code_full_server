# SMIOT Datadog Agent key rotation and telemetry verification

**Evidence window:** 2026-11-10 04:36–04:43 UTC  
**Region:** ap-southeast-2  
**Changes:** Datadog Agent configuration only. No application, MongoDB, publisher, simulator, or actuator actions.

## Rotation

- Read the user-authorized rotated key file locally and selected its `api_keys` field without displaying or logging the value.
- Updated the existing SecureString parameter `/smiot/observability/datadog-us1-api-key`; the temporary encrypted transfer object was deleted after retrieval.
- Backed up the prior Agent configuration at `/var/backups/datadog-agent/datadog.yaml.pre-key-rotation-20261110T043640Z` with mode `0600`. Agent configuration remains mode `0640`.
- Agent configuration validation succeeded; `site` remained `datadoghq.com`.
- Restarted only `datadog-agent.service`. SSM execution ID: `1ca7782d-179e-40a2-a72d-e4ad8d56897c`.
- Datadog API key validation returned HTTP 200 / valid. Agent status reported API key valid, `Number of submission errors: 0`, and `Series Flushed: 27,106` at 2026-11-10 04:40 UTC.

## DogStatsD and application path

- UDP listener on port 8125 was present; Agent status showed 3,570 metric packets and 0 UDP packet-reading errors.
- App and Agent shared the same network namespace. App environment: `DATADOG_METRICS_ENABLED=true`, Agent host resolves to loopback, `DD_DOGSTATSD_PORT=8125`, and `DD_SITE=datadoghq.com`.
- Sent a non-actuating gauge canary `smiot.diagnostic.dd_agent_rotation_canary` to `127.0.0.1:8125` at approximately 04:40 UTC. Command reported datagram sent; this did not invoke any application route or actuator.
- DogStatsD detailed per-metric stats are disabled in the current Agent config. No configuration change was made to enable them.

## Datadog US1 query results

- At approximately 04:40 UTC, queries over the prior 30 minutes returned no data for the canary or existing SMIOT series, including `smiot.telemetry.soil_ec`, `smiot.telemetry.samples_persisted`, and `smiot.detector.heartbeat`.
- At approximately 04:43 UTC, metric catalog search over the prior 2 hours found no `smiot.diagnostic.dd_agent_rotation_canary` metric.
- The SMIOT metric catalog still lists older series (including `smiot.telemetry.soil_ec` and `smiot.telemetry.samples_persisted`) from earlier activity, but none were queryable in this recent window.

## Outcome / blocker

Agent authentication, forwarding status, local DogStatsD listener, and app-to-Agent namespace/destination checks are healthy. However, the local canary and SMIOT series have not become visible in the Datadog US1 metric query/catalog. The remaining gap is after Agent DogStatsD intake and before query visibility; this evidence does not establish whether Agent metric submission is reaching the same organization queried by the MCP connection or whether the intake is accepting these custom series. No W6 monitor was created because fresh detector-specific telemetry was not verified. The W6 workflow remains blocked pending a fresh `smiot.detector.heartbeat` series in the queried Datadog organization.

## Safety

No API key, AWS account identifier, ARN, instance identifier, public IP, or other credential value is included here. No app/Mongo/publisher/simulator/actuator service was restarted or changed.

## Direct Datadog API diagnostic (same US1 credentials)

**Time:** 2026-11-10 04:44–04:46 UTC

- Submitted one uniquely named, non-business gauge through `https://api.datadoghq.com/api/v1/series`, with tags `diagnostic:test` and a single-run identifier. The current `APP_KEY.txt` API/application credentials were read into process memory only; no values were printed or persisted.
- Series submission returned HTTP `202` (accepted).
- Queried the same metric through `https://api.datadoghq.com/api/v1/query` using the same credentials immediately and again over approximately 90 seconds. Every query returned HTTP `200`; no datapoint was visible.
- The request was accepted by the US1 series API, but no data became query-visible during this check. This establishes the API endpoints and credentials are accepted, but does not localize the ingestion/query-visibility delay to the Agent path.

## Direct canary poll through five minutes

**Poll window:** 2026-11-10 04:44:09–04:49:22 UTC

- Repeated query requests used an expanded window from `2026-11-10T04:40:00Z` through at least `2026-11-10T04:51:20Z`, which includes the canary submission timestamp. Requests with both wildcard scope (`{*}`) and exact tags (`diagnostic:test`, the single-run tag) returned HTTP `200`, API status `ok`, and zero series at 04:47:05Z, 04:48:10Z, 04:48:55Z, and 04:49:22Z.
- Metric metadata lookup returned HTTP `404` at 04:47:16Z and 04:49:22Z, indicating the metric was not registered in query-visible metadata during the polling window.
- Inspected the local JSON serialization shape of the exact PowerShell construction used for submission, using dummy values only: the `points` field serialized as `[timestamp,value]` (two flat elements), whereas the Datadog series API expects `[[timestamp,value]]` (one point pair). The timestamp was Unix seconds and the query window included it; wildcard scope also returned no data, so tag filtering does not explain the result. The flattened `points` array is the likely cause for HTTP 202 acceptance without an ingested/queryable point.
- No additional metric was submitted during this poll or serialization check.

## Correctly nested direct API canary

**Submission:** 2026-11-10 04:50:20.496 UTC  
**Last requested poll:** 2026-11-10 04:54:28.074 UTC

- Submitted one unique gauge, `smiot.diagnostic.direct_api_canary_corrected_20261110T045020Z`, with `diagnostic:test` and one run tag. Before posting, local serialization validation confirmed exactly one point pair nested under `points`: outer count `1`, inner count `2`. Credentials were read into process memory and not printed or stored.
- Series API response: HTTP `202`.
- Metric metadata endpoint: HTTP `200` by 04:50:21 UTC and still `200` at 04:54:28 UTC.
- Queries made immediately and repeatedly through 04:54:28 UTC returned HTTP `200`, API status `ok`, and `0` series for both wildcard scope and exact tags. Query windows started at `04:48:00Z` and extended at least through `04:55:26Z`, covering the submitted point timestamp.
- The corrected metric was registered in metadata, but no queryable point appeared by 04:54:28 UTC. This confirms the earlier flat point shape explained the first canary's non-registration, but the corrected request still has a separate ingestion-to-query visibility delay/failure. No further canary was submitted.
