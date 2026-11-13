# SMIOT source rollout evidence — 2026-11-10

## Result

The current local application source was deployed to the project EC2 instance in `ap-southeast-2`. This was an application-source rollout; Datadog configuration was not changed.

## Preflight

- AWS caller identity matched the expected SMIOT account and region; the target EC2 instance was running and SSM managed.
- Pre-deploy EBS snapshot completed: `snap-06c850cab314396b7`.
- Source rollback archive: `/root/smiot-rollback/code_before_20261110T1228Z.tgz`.
- Staged package: `smiot/deploy_20261110T1218Z.tgz`, 149 files, 27,992,559 bytes.
- Package scope: `main.py`, `requirements.txt`, `pages/`, `service/`, `components/`, `static/`, `wokwi/`, `scripts/`.
- Excluded `.env` files, databases, key files, local logs/output, generated build artifacts, and bytecode.
- EC2 staging compile, package exclusion check, and imports for runtime dependencies passed. The local tree also passed `python -m compileall -q main.py pages service scripts`.
- The existing pytest suite could not run because `pytest` is not installed in the local Python environment.

## Deployment and verification

- SSM deployment command: `876ba439-7c8f-4e51-8579-ed6e8143b7a3` — Success.
- SSM post-deploy verification command: `aa0770d0-0d6f-47b3-87f9-c6e98ad7b92e` — Success.
- Restarted only `smiot.service` and `wokwi-bridge.service`.
- Post-deploy: app, MongoDB, MQTT broker, and Wokwi bridge were active; `/healthz` returned HTTP 200.
- SHA-256 checks for local vs EC2 `main.py`, `service/incident_lifecycle.py`, and `service/detector_heartbeat.py` all matched.
- Public app UI loaded. The Home page showed 10 farms and MongoDB-backed incident/notification sections. Clicking “Mở farm” displayed Greenhouse A details. The SMIOT page reported zero browser console errors.

## Datadog scope and remaining gates

- Read-only Datadog UI inspection confirmed organization `NO` on US1 (`datadoghq.com`). The workflow list showed ten published SMIOT workflows and one unpublished duplicate Ca 1 workflow.
- No Datadog workflow, monitor, dashboard, or organization setting was changed in this rollout.
- The EC2 presence of `SMIOT_DEMO_CONTROL_TOKEN` was not confirmed. Until the token is securely configured, the new external scenario API stays unavailable by design; no token value was read or exposed.
- No new incident drill was run. Configured workflow count is not proof that all ten workflows reached Level 5.
- The W6 metric still needs confirmation in Datadog, and W3's strict CLEAR gate still needs a controlled accept/reject drill.

## UTC timeline

- 2026-11-10 12:17 UTC — pre-deploy snapshot created.
- 2026-11-10 12:18 UTC — deployment package uploaded and staged.
- 2026-11-10 12:28 UTC — source backup created; application and bridge deployed and restarted.
- 2026-11-10 12:29 UTC — services, HTTP health, and selected file hashes verified.
