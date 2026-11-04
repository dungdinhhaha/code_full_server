# Datadog guarded SMIOT recovery

## Chosen recovery behavior

The Datadog Private Action Runner calls `recover-smiot-web`, which invokes
`/usr/local/sbin/smiot-recover-guarded` on the EC2 host.

| Observed condition | Workflow action |
| --- | --- |
| Login endpoint is healthy | No action; record `already_healthy` |
| systemd's own recovery restores the endpoint during a short grace period | No action; record `systemd_recovered_before_action` |
| App process is active, but its endpoint still fails | Refuse to restart; record app, MongoDB, MQTT, and disk state for investigation |
| App unit is stopped/failed, MongoDB and MQTT are active, root disk is below 85%, and MongoDB can be read | Run only `systemctl start smiot.service` |
| Any prerequisite or post-start proof fails | Refuse or report unverified; do not restart EC2, MongoDB, MQTT, Datadog Agent, or the app |

The start action is locked against concurrent runs and has a five-minute
cooldown. After start, it requires systemd active + HTTP 200 + a newer fresh
telemetry record read back from MongoDB. A successful command by itself is not
considered recovery. Each branch writes one structured JSON record to
`/opt/smiot/logs/recovery/guarded_recovery.jsonl`; the Datadog Agent collects it
with source `smiot-recovery`. Search Logs for
`service:smiot-smart-farm source:smiot-recovery event:smiot.guarded_recovery`.

## Why this pattern

Datadog documents that Private Action Runner scripts must be predefined and
that elevated commands should be narrowly allowlisted. Its monitor/workflow
guidance recommends triggering a workflow from an actionable monitor. The
systemd `start` operation only enqueues a unit start; `restart` explicitly
stops and then starts it. This design uses the least disruptive operation
matching the detected state and fails closed when the evidence is ambiguous.

References:

- https://docs.datadoghq.com/actions/private_actions/run_script/
- https://docs.datadoghq.com/monitors/notify/
- https://freedesktop.org/software/systemd/man/latest/systemctl.html

## Install on the EC2 host

Install `scripts/aws/smiot-recover-guarded.sh` as root at
`/usr/local/sbin/smiot-recover-guarded` and
`scripts/aws/smiot-recovery-mongo-readback.py` as root at
`/usr/local/sbin/smiot-recovery-mongo-readback`, both mode 0755. The second
helper reads the root-protected app environment itself and returns only the
latest telemetry timestamp; `dd-agent` must not receive read access to
`/etc/smiot/app.env`. Grant `dd-agent` only the exact commands
`/usr/bin/systemctl start smiot.service` and
`/usr/local/sbin/smiot-recovery-mongo-readback` through sudoers. Do not grant
restart, shell, arbitrary command, or arbitrary service parameters. Keep the
predefined runner entry bound to the fixed recovery script path.

## Proof record

Run the workflow manually while the service is healthy. Expected output is
`action=none`, `result=verified_healthy`, `reason=already_healthy`; the app's
systemd state and HTTP availability must remain unchanged. This validates the
no-op branch only. On 2026-11-04 the updated script was deployed through SSM,
the Datadog log-agent config passed `configcheck`, and the host remained healthy:
`smiot.service`, `mongod.service`, `mosquitto.service`, and `datadog-agent` were
active and `/login` returned HTTP 200. The no-op record was found in Datadog US1
with source `smiot-recovery`, including `event=smiot.guarded_recovery`,
`action=none`, `result=verified_healthy`, and `reason=already_healthy`.

A guarded start branch was drilled on 2026-11-04. The first Datadog run refused
because its restricted `dd-agent` user could not read the app secret file for
the MongoDB check. The app was restored through the guarded script, the monitor
returned to OK, and the workflow's healthy no-op path succeeded. The subsequent
fix runs the MongoDB readback through a root-owned, no-argument helper that
returns only the telemetry timestamp; the outage branch must be re-drilled
after this helper is installed before claiming automatic recovery is proven.
