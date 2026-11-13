# PROGRESS — SMIOT delivery status

**Latest UI redesign update (2026-11-12 04:13 UTC):** giao diện đã chuyển sang bộ thành phần chung (theme + ui_kit) và các trang đã được viết lại: Home biểu đồ theo farm, Bơm/Biến tần có xác nhận và chuỗi Đã gửi / ACK / Đã xác minh, Sự cố có hồ sơ sáu chặng và recovery_verdict chỉ đọc bằng chứng của đúng hồ sơ, Mùa vụ, Lịch, Thiết bị, Dự án, Datadog, Số đo, trang lô công khai. Kiểm tra: biên dịch toàn bộ file đã sửa, 240/240 unit test. **Chưa có:** kiểm tra trình duyệt trên desktop và 375px; kiểm chứng biểu đồ với MongoDB thật (aggregation `$dateTrunc` cần MongoDB 5.0+); triển khai EC2 và xác minh /login, /healthz (cần snapshot EBS và archive rollback trước khi thay source). **Giới hạn đã biết:** trạng thái bơm và biến tần trong bộ nhớ máy chủ chưa tách theo farm (service/mqtt.py); lệnh bấm tay không vào action_ledger nên mất khi khởi động lại; lệnh đồng bộ PID chưa gắn farm_key vì chưa có bên nhận để đối chiếu.

**Latest W3 update (2026-11-11 12:04 UTC):** clean bounded outage was executed. `smiot.service` was stopped and left untouched for 420 seconds; MongoDB, MQTT and EC2 were not stopped. The guarded SSM recovery later verified HTTP and fresh Mongo telemetry, and final readback showed all services active with `/healthz` 200. The Datadog monitor-triggered automatic start was **not proven**: raw `systemd.unit.active` points were 0, but monitor `342585838` did not transition during the clean wait. Do not call W3 Level 5 yet. Evidence: `outputs/evidence/w3_runtime_20261111T1204Z.json`.

**W3 repaired and verified (2026-11-11 12:55 UTC):** monitor `342585838` now uses a bounded 2-minute demo window; workflow rate limit is 60s; workflow waits for `/healthz` before calling the verifier; backend verifier waits for the correlated SSM command to become visible and terminal. Clean run `14f19151-5db3-4c40-a253-f6835ccdbf41` completed `Send_command → wait_for_smiot_health → verify_smiot_recovery → classify true → notify_verified_smiot_app`; SSM guard returned `recovered`, final service/Mongo/MQTT health was good, and monitor returned `OK`. W3 automatic recovery acceptance is now met for this synthetic drill. Evidence: `outputs/evidence/w3_runtime_20261111T1255Z.json`.

**Updated:** 2026-11-11  
**Rule:** “Done” means the stated proof exists. Local code is not deployment; a published config is not an end-to-end run.

## Baseline observed
- [x] Local source contains ten farm registry entries, 36 scenarios, MQTT command/status ACK paths, per-run evidence modules, and `/plc` controls.
- [x] Local source contains detector heartbeat publisher and Terraform W6 monitor declaration. The heartbeat thread is owned by the app process.
- [x] Local scenario API exists at `POST /api/demo/scenarios` and `GET /api/demo/scenarios/{scenario_run_id}`; bearer token `SMIOT_DEMO_CONTROL_TOKEN`; hashed idempotency, per-farm API lock, run-scoped stop ACK and Mongo-backed rate limits. Deployed with the app source; external calls remain gated until the token is securely configured on EC2.
- [~] W6 evaluation heartbeat code is deployed on EC2 and the Datadog metric catalog lists `smiot.detector.evaluation_heartbeat`; the published workflow and monitor still use watchdog/input-freshness signals. Healthy-path run evidence exists, but the detector-stalled branch and recovery are unproven.
- [ ] Repository worktree was already heavily modified before this task; changes must remain isolated.

## Runtime evidence already recorded in the project context
| Case | Evidence | What it supports | Remaining limit |
|---|---|---|---|
| W1 | Run `e4ec89c0-5bb4-483c-8df5-5d91afdedb4f` | Successful evidence → observation → app notification path on demo-stream trip | This investigation concluded the signal was injected demo data; do not claim physical pipe fault |
| W2 | Run `431269bb-eed6-4b35-965e-b935679e2a6e` | Monitor-triggered run succeeded; local interlock confirmation and app notification | Full fresh-data/Mongo recovery proof for this exact run still needs review |
| W3 | Run `c8c9bda9-f463-4338-9aa7-85df60f7cdaa` | Controlled app-service outage recovered; verifier true/recovered; health 200; MongoDB/MQTT active; app notification stored | Trigger was manual, not monitor-triggered; not a proof of automatic detection-to-recovery |
| W4 | Run `85fd6265-4b25-4327-8370-a5a8997e4b87` | Monitor-triggered fresh-status refusal | Need explicit no-SSM-invocation evidence in same incident |
| W5 | Run `129839c9-8b4e-4ab8-a247-87ead0eb2280` | Workflow healthy/no-dependency-breach branch and app notification | Does not prove separate MongoDB-vs-MQTT fault discrimination |
| W6 | `ebcd3f36-e460-4bdd-9dca-e4b841033ead` | Healthy-path workflow run; watchdog and external input freshness both returned 1; app notification API returned 202 and stored it | Evaluation heartbeat is listed in Datadog metrics catalog but is not queried by published workflow/monitor; stalled path/recovery unproven; evidence: `outputs/evidence/w6_run_20261110T124826Z.json` |
| W7 | Monitor and Bits toggle observed in Datadog UI | Configuration exists | End-to-end safe drill not verified |
| W8 | Monitor and Bits toggle observed in Datadog UI | Configuration exists | End-to-end advisory drill not verified |
| W9 | Monitor exists; metric emitter script prepared | Drill signals can be generated synthetically | No-ACK → safe state → matching ACK full proof not verified |
| W10 | Monitor exists; metric emitter script prepared | Provider failure/latency signals prepared synthetically | HOLD/fallback and recovered provider proof not verified |

## Local changes made during this task (deployed to EC2 after preflight)
- [x] Added and deployed opt-in authenticated scenario API in `main.py`; idempotency/concurrency/stop-ACK/rate-limit hardening is live. Secure EC2 token configuration and external-client ACK proof remain.
- [x] W6 has a separate detector evaluation-freshness metric deployed to EC2 and an updated Terraform query; the Datadog metric catalog lists the series, but the published workflow/monitor still use the older signals.
- [x] W3 incident close rejects CLEAR without matching verified ledger, prior ACK, monitor OK, fresh varying Mongo telemetry, and virtual outputs-off evidence; deployed, but this full gate has not yet been exercised end-to-end.
- [x] Added an opt-in Terraform monitor for W10 provider failures; not applied/live-verified.
- [x] Metric audit found W9 live monitor is not declared in Terraform; reconcile/import before Terraform apply. W1 workflow and Terraform use different query scopes; reconcile before apply.
- [x] Home already has Mongo-backed ten-farm multi-indicator overview and incident/notification section. No duplicate UI added; module-global selected-farm state is a multi-user race risk.

## Bits automatic investigations
- [x] Datadog UI toggles were observed enabled for W1–W5 and W7–W10 during the current session; W5 Mongo monitor was saved and reloaded showing Enabled.
- [x] W6 published workflow and monitor exist; the healthy-path workflow run was confirmed. Monitor 343029221 still checks watchdog liveness only.
- [ ] Enabled toggle does not prove a completed automatic Bits investigation. The monitor must transition into ALERT; no forced alert was generated here.
- [ ] Do not claim all ten cases are Level 5.

## This task’s implementation log
| Item | Status | Evidence / next step |
|---|---|---|
| Six planning files | Created | PRD, architecture, design, rules, tasks and progress at repository root |
| External virtual-scenario API | Deployed, gated | Bearer-token routes have idempotency, concurrency, ACK readback, and rate limiting; configure token securely and prove a real simulator ACK |
| W6 | Partially verified | Evaluation-heartbeat metric is listed in the correct Datadog metric catalog, but published workflow/monitor do not query it; healthy path and app notification are proven, stalled branch is not |
| Incident recovery guard | Deployed, not drilled | CLEAR evidence gate is on EC2; execute a controlled run proving it accepts valid and rejects incomplete evidence |
| W10 metric monitor | Partial/local | Provider-failure Terraform draft added; not applied |
| Datadog/EC2 changes | EC2 source deployed; no Datadog configuration changed | W6 healthy-path manual run executed and app notification stored; no workflow/monitor configuration was published or modified |
| Five browser tabs | Complete | Five tabs share one authenticated browser context: SMIOT app, Datadog workflows, monitors, dashboards, Bits; correct org `NO`, US1 site confirmed |


## Live rollout — 2026-11-10
- [x] Verified the intended AWS account/region and the SMIOT EC2 target through the AWS MCP.
- [x] Packed 149 source/resource files from `main.py`, `requirements.txt`, `pages/`, `service/`, `components/`, `static/`, `wokwi/`, and `scripts/`. The package excluded `.env`, database files, keys, build output, logs, and local outputs.
- [x] Staged package on EC2; remote Python compilation and imports for all runtime dependencies passed.
- [x] Created a pre-deploy EBS snapshot (completed) and a source rollback archive at `/root/smiot-rollback/code_before_20261110T1228Z.tgz`.
- [x] Deployed the staged source and restarted only `smiot.service` and `wokwi-bridge.service`.
- [x] Post-deploy SSM verification: `smiot.service`, `mongod.service`, `mosquitto.service`, and `wokwi-bridge.service` active; `/healthz` HTTP 200; hashes for `main.py`, `service/incident_lifecycle.py`, and `service/detector_heartbeat.py` match the local source.
- [x] Browser verification: Home renders 10 farms with MongoDB-backed status, incident and notification sections; selecting “Mở farm” renders Greenhouse A detail. No console errors were observed on the SMIOT page.
- [x] Read-only Datadog UI check: correct US1 org is `NO`; ten SMIOT workflows are published and one duplicate Ca 1 workflow remains unpublished. No Datadog configuration was changed.
- [ ] `SMIOT_DEMO_CONTROL_TOKEN` was not confirmed in EC2 app configuration. The external API returns unavailable until configured; no token value was read, generated or exposed.
- [ ] Pytest is not installed in the local Python environment, so the existing pytest suite was not run. Local and staged Python compilation and remote runtime-import checks passed.
- [ ] No new incident drill was run. Ten configured workflows do not yet mean ten Level 5 end-to-end proofs.


## W6 run follow-up — 2026-11-10
- [x] Confirmed published W6 workflow `d8e1b3db-1a54-4b4f-9be3-bf7e270a86f3` and monitor `343029221` remained intact after discarding the malformed unpublished draft.
- [x] Recorded healthy-path run `ebcd3f36-e460-4bdd-9dca-e4b841033ead`: watchdog heartbeat = 1, external input freshness = 1; notification endpoint returned HTTP 202 with `received`, `stored: true`, and `app_bell_updated: true` at `2026-11-10T12:48:26Z`.
- [ ] W6 still needs evaluation heartbeat wired into the published workflow and detector-specific monitor, plus a controlled missing-evaluation drill. No autonomous detector restart or recovery is claimed.
## Restarted implementation pass — 2026-11-10

**Scope:** reviewed the existing plan and made local-only changes. No Datadog or AWS configuration was written, and nothing was deployed to EC2.

- [x] W1/W4 pending workflow JSON: W1 query now matches the bounded synthetic producer tags and groups by farm/fault; W4 remains refusal-only. Missing health proof routes to unknown/escalation.
- [x] W2/W3/W5 pending workflow JSON: W2 is evidence-observation only and cannot CLEAR; W3 orders guarded command → exact-run/command/instance verifier → terminal notice; W5 distinguishes common dependency failure before single-service hypotheses.
- [x] W6–W10 pending workflow JSON: W6 requires watchdog, input freshness, and evaluation heartbeat; W7/W8 require approved stage envelope and remain advisory; W9 uses no-ACK + safe state + matching ACK; W10 requires a fresh provider success before recovery.
- [x] W9 app command provenance: command records are farm/actuator scoped; no-ACK uses the original farm and command ID; ACK is correlated to both. In-app simulator echoes those fields; optional Wokwi visual path does not include farm key and is not counted as proof.
- [x] W7/W8 agronomy and W10 AI fallback guard changes are local. The AI failure path now logs safely on Windows rather than raising a Unicode encoding error.
- [x] App Datadog-notification handler stores/display correlation fields (scenario, command, device, provenance) while leaving incident closure to the verifier.
- [x] Local checks: all 10 pending workflow JSON files parse, graph check found zero dangling edges or unreachable steps; Level-5 draft suite 4/4; W3 verifier 13/13; flatline recovery 5/5; probe 8/8; MQTT receiver 4/4; app notifications 17/17; AI fallback 20/20; crop evidence 6/6.
- [ ] Deploy local code/JSON changes and verify app notification from the published workflows.
- [ ] Run one correlated end-to-end drill per selected workflow; current local tests do not prove monitor trigger, Bits investigation, AWS action, live Mongo evidence, or Level 5.
- [ ] Reconcile live workflow count before writing: the Datadog UI session used during this pass showed 3 SMIOT workflows, while local snapshot documents say 10 had previously been updated/read back. The Chrome window was not the user's intended window, so do not treat that observation as authoritative until the correct session is checked.

## Live rollout follow-up — 2026-11-10 15:05 UTC
- [x] Deployed the verified local source bundle to EC2 through SSM with a completed pre-deploy EBS snapshot and source rollback archive.
- [x] Post-deploy health: `smiot.service`, MongoDB, MQTT and `wokwi-bridge.service` active; `/healthz` returned 200; deployed `main.py` checksum matched local.
- [x] Updated all 10 existing Datadog workflows without creating duplicates. Nine specs were applied with Terraform; W1 used the Datadog API because Terraform provider 4.30 rejects its API-supported `apiTrigger.rateLimit` field.
- [x] Corrected W10's convergent escalation step with `readinessGate: ANY`; Datadog API read-back confirmed 10/10 expected workflow handles, IDs, names and published states.
- [x] Final Terraform plan reports no pending changes for managed fields. W1 and W3 specs are excluded from Terraform drift detection for the documented provider/API serialization limitations.
- [x] Playwright has three tabs open: app home, Datadog workflows, Datadog monitors.
- [ ] No incident was injected and no workflow was manually executed in this rollout. The live configurations are deployed; end-to-end Level 5 behavior still needs controlled drills.
- Detailed sanitized rollout record: `outputs/deployment_evidence/smiot_rollout_20261110T150504Z.md`.
- [x] Read-only check found a pre-existing unpublished Ca 1 duplicate outside the 10 planned handles; this rollout did not create or modify it, and it remains unpublished.


- [x] Ran Datadog workflow W1 through Pup CLI; run `70ee0295-fd8a-4ce7-b20e-361a0eb61aa8` succeeded and the SMIOT app received its notification (2026-11-10 15:13Z). Read-only run; no device actuation; does not prove all ten workflows are Level 5.



## Sequential W1–W6 live drill — 2026-11-11 (stopped after W6 per request)

All timestamps below are UTC. These were controlled demo/synthetic signals unless explicitly marked as an application-service stop. No physical actuator was called. Datadog API access was through the SMIOT EC2 environment; no credentials were copied into this record.

| Case | Live result | Evidence / limitations |
|---|---|---|
| W4 — Status mismatch / safe refusal | Monitor 342585836 alerted; workflow ffd62026-6b63-40e4-9b46-6ac18d2d584f run 0dc4ae11-cfab-43f3-b8dc-9a2e919aafa5 succeeded 00:16:57–00:17:02Z and notified the app. | Scenario run 9075ea6f-6dff-420a-933a-60a6d5e8944c, synthetic D2 false_offline. Workflow escalated because fresh status evidence was not confirmed. No restart was issued. Incident closure was not proven. |
| W1 — PLC safety trip | Monitor 342734303 alerted; workflow b9e72b04-1580-45f8-ae1e-628124a19065 run 3e9b0cb7-efab-4ade-83da-c374d4d2d438 succeeded 00:27:24–00:27:28Z and notified the app. | Scenario run d9d94b92-8aff-420a-933a-60a6d5e8944c, synthetic A2 pressure-zero in greenhouse_b. Virtual PLC readback showed safe mode active and valve closed. This proves the simulated safety path, not physical pump/valve behavior. |
| W9 — Actuator command unacknowledged | Monitor 342734743 alerted; workflow 47e95b24-db40-4cd5-b667-5b90e170b667 run 43c4c90c-c97b-4958-ade9-a638fdf7de57 succeeded 00:37:51–00:37:56Z and notified the app. | Synthetic metric run DRILL-W9-PERSIST-fe894038-1600-409f-b942-24b93225700e. No real actuator command or ACK path was exercised; metric/workflow handling only. |
| W2 — Sensor flatline | Monitor 342585819 alerted; workflow 2f9a3c1d-5292-4bc3-b4b9-cc03d4172724 run c16f7820-01ce-484d-a47c-a3497e14cd12 succeeded 00:53:40–00:53:45Z, then MQTT mode was returned to normal. Monitor later returned OK at 01:02:50Z. | Greenhouse_a Node2 synthetic 2.4% flatline. Normal samples at 00:56:37Z, 01:01:38Z and 01:02:38Z were observed. The app’s full stable-sample CLEAR verifier was not confirmed. |
| W5 — MongoDB dependency triage | Monitor 342585827 alerted; workflow d3f0705e-2cbd-430a-9a3a-b1fd02a42cc9 run 6a95dd41-2164-49fb-bd06-ba17a360a5a9 succeeded 01:06:48–01:06:53Z, classified the MongoDB signal and notified the app. Monitor returned OK by 01:16:35Z. | Synthetic dependency metric run DRILL-W5-MONGO-46d39d18-b708-424f-8adf-dcb465ba871d; MongoDB and MQTT services were never stopped. This proves triage of the synthetic signal, not a real database outage. |
| W3 — EC2 app service inactive | The app service was stopped at 01:17:45Z; MongoDB and MQTT remained active. Because the Datadog workflow had not yet recovered it, it was manually started via SSM at 01:24:10Z and /login returned HTTP 200 by 01:24:16Z. Monitor 342585838 then triggered workflow 373ed0c0-4509-4fcd-a067-f54f0becc00e, run 60b7c632-b8d7-42e7-98ea-701d9bc53aa7, which succeeded 01:24:59–01:25:24Z. Its SSM step, recovery verifier, and app notification all succeeded; verifier took the true branch. Monitor was OK by 01:26:58Z. | The workflow’s guarded start was configured for SMIOT-GuardedStartApp, DryRun=false. Since manual SSM start happened first, this run does not prove Datadog performed the recovery; it proves post-recovery verification and notification. A separate recovery-transition workflow invocation returned “Rate limit exceeded” at 01:26:59Z. |
| W6 — Detector heartbeat missing | Synthetic metric DRILL-W6-WATCHDOG-20261111T0125Z was sent as six zero gauges, then six one gauges. Monitor 343029221 entered Alert for greenhouse_a at 01:28:41Z. Workflow d8e1b3db-1a54-4b4f-9be3-bf7e270a86f3, run 587e0e22-5496-44ac-bd14-a2f4c6dbc2a3, succeeded 01:28:42–01:28:46Z; read_operational_signals, evidence check, classification, escalation/review and notify_smiot_app succeeded. | This was a metric-only simulation; the detector process was not stopped. The query API showed the test heartbeat back at 1, but monitor 343029221 still reported overall Alert at 01:34:45Z, so W6 recovery/CLEAR is unverified. Other grouped invocations for the same monitor returned “Rate limit exceeded” around 01:25:42–01:25:43Z; review grouping/rate limits before using this monitor across all farms. |

### End-of-drill health and scope

- [x] smiot.service, mongod.service, and mosquitto.service active; local /login returned HTTP 200 at 01:33:28Z and again at 01:34:45Z.
- [x] W5 synthetic dependency gauge restored; W2 sensor mode restored to normal; W6 synthetic heartbeat gauge restored to 1.
- [ ] W3 automatic remediation is not proven because manual recovery preceded its workflow run.
- [ ] W2 and W6 full monitor/app CLEAR evidence is not confirmed.
- [ ] W7, W8 and W10 were intentionally not injected; the drill stopped after W6 as requested.
- [ ] These results do not establish Level 5 for all workflows.

## W1–W6 upgrade planning — 2026-11-11

- [x] Reconciled `TASKS.md` gate G6 with the sequential live drill: W4/W1/W9/W2/W5/W3/W6 were exercised; this is partial verification, not completed Level 5 acceptance. W7/W8/W10 remain untouched after the requested stop at W6.
- [x] Added the ordered W1–W6 delivery plan to `TASKS.md`: shared latency timeline, incident correlation, duplicate-action guard, notification state contract, demo pacing and case-specific acceptance gates.
- [ ] No upgrade in that plan has been implemented or deployed in this planning pass. Monitor/workflow configuration and application services were not changed here; no new fault was injected.
- [ ] First execution gate: measure existing run timings and diagnose W3 monitor 342585838 before another service outage. W3's last run followed a manual app start, so automatic recovery remains unproven.
- [ ] W6 remains open: last observed monitor 343029221 was ALERT despite synthetic gauge returning to 1; grouped runs had rate-limit failures. Resolve per-group state and deduplication before claiming ten-farm detector recovery.
- [ ] W2 requires the app's stable-sample CLEAR proof; W1 needs same-incident ACK/readback/ledger; W4 needs explicit no-SSM evidence; W5 needs separate Mongo-vs-MQTT discrimination and post-action verification.

## Plan correction — 2026-11-11

- [x] Replaced the obsolete W4-first execution priority in `TASKS.md` with shared defects → W3 → W6 → W2 → W1 → W4 → W5. The previous file had conflicting priorities and time-bound statements that still said no incident drill had run.
- [x] Added R0–R4 gates: current live drift baseline, one hypothesis per failed observation, one small fix and bounded replay, explicit pass/fail, and measured stage pacing. This targets the repeated long drills without a diagnosed cause.
- [x] Clarified that AWS CLI performs AWS inspection/SSM operations; Terraform remains the configuration source of truth where IaC exists. S3 inspection is separate from the W3/W6/W2 blocking path.
- [ ] This planning correction did not change backend, Datadog, AWS or EC2 and did not run another drill. W3 automatic recovery, W6 group recovery and W2 app CLEAR remain open.
- [x] W2 follow-up fix applied locally after parallel review: freshness gate now follows the verifier's cadence-aware bound, and evidence IDs are limited to stable samples. Python compilation passed; no deployment or runtime drill yet.
- [x] W6 local workflow draft now uses the producer's evaluation heartbeat metric and states that it is app-owned evaluation freshness, not independent process liveness. Live monitor/state and farm filtering remain unverified; no publish/apply/deploy.

## Execution update — 2026-11-11 06:00 UTC

- [x] W2 cadence-aware verifier and freshness acceptance patch deployed to EC2 through SSM; only `scripts/verify_and_clear_demo_safe_mode.py` and `service/telemetry_health.py` were overlaid, and only `smiot.service` was restarted.
- [x] EC2 post-deploy readback: `smiot.service`, MongoDB and MQTT active; `/healthz` returned 200; the Mongo readback helper returned a current timestamp.
- [x] W6 workflow JSON published to the existing Datadog workflow `smiot-w06-detector-heartbeat`; read-back confirms the evaluation-heartbeat query and five steps.
- [ ] W2 has not yet passed its focused verifier/CLEAR drill; W6 has not yet passed monitor group/farm routing and recovery drill. Do not mark either workflow Level 5.
- [ ] The pre-deploy EBS snapshot was initiated but remained pending at the time of rollout; retain its ID in the activity log and verify completion separately.

## Parallel W2/W6 rehearsal — 2026-11-11 06:27 UTC

- [x] Created and ran a local-only parallel harness with separate W2/W6 farms, incident IDs, scenario IDs, timeouts and cleanup.
- [x] Evidence artifact created: `outputs/drill_parallel_w2_w6_20261111T062722Z_705fc108.json`.
- [x] Reviewer found and recorded two live blockers: W6 query must be proven farm-scoped (current workflow query is detector-scoped only), and W2/W6 live lock/idempotency/cleanup still require runtime evidence.
- [ ] Do not run the two live faults yet. The local rehearsal validates orchestration shape only; it does not validate Datadog monitor groups, workflow runs, Mongo persistence or app notifications.

## W2 account/metric correction — 2026-11-11 06:37 UTC

- [x] Confirmed the current Datadog key is valid on US1 and found the active W2 monitor `342585819`; the earlier `339977691` result was an obsolete/wrong monitor reference.
- [x] Confirmed live `smiot.telemetry.sensor_flatline` data for `farm:greenhouse_a,node:2` and completed a bounded S1 start → Mongo persistence ACK → stop run.
- [ ] The bounded run did not last the monitor's five-minute alert window, so it proves the metric/scenario path but not an Alert→workflow run. A longer alert drill is still optional and must be followed by restore.

## W6 synchronization — 2026-11-11 06:50 UTC

- [x] W6 monitor `343029221` now uses the same evaluation-heartbeat metric as the workflow and remains grouped by `farm`.
- [x] W6 workflow `d8e1b3db-1a54-4b4f-9be3-bf7e270a86f3` republished from the full Terraform JSON spec; it reads watchdog, input freshness and evaluation heartbeat evidence.
- [x] Fixed backend field contract: detector evaluation now recognizes compact MQTT node fields `at`/`ah`; deployed to EC2 and `/healthz` returned 200.
- [~] Evaluation heartbeat is now emitting `1` for farms, but monitor state is temporarily Alert until the old zero points leave the five-minute window. Wait for a full OK window before injecting W6 fault.

## W6 scoped fault injector — 2026-11-11 06:57 UTC

- [x] Added a synthetic-only MQTT control for `demo_detector_fault=stalled|normal` with `farm_key` and command ACK. It is farm-scoped and does not stop the shared app, MongoDB, MQTT broker, EC2, or any actuator.
- [x] Deployed `detector_heartbeat.py` and `demo_mode.py` to EC2; service and health check remained healthy.
- [x] Tested `greenhouse_b`: stalled ACK and normal ACK both returned `applied=true`, `mode_applied=true`, `synthetic=true`.
- [ ] A short ACK test is not an Alert→workflow proof. To test the live monitor, hold `stalled` longer than the monitor's five-minute window, then restore `normal` and wait for the farm group to return OK.

## W6 live drill — 2026-11-11 07:00–07:06 UTC

- [x] Held the scoped synthetic detector fault on `greenhouse_b` for 330 seconds, then restored `normal` automatically.
- [x] Received applied ACKs for both phases. Datadog evaluation heartbeat showed `0` for `greenhouse_b` during the hold and a new `1` after restore; other farms stayed at `1`.
- [~] Monitor group `greenhouse_b` is still Alert immediately after restore because the five-minute window still contains zero points. Wait for a full OK window and read back workflow run/terminal status before calling W6 complete.
- [!] After the recovery window, all 10 farm groups and latest heartbeat points are `1`, but the monitor API still reports `overall_state=Alert` while groups report `OK`. This is an unresolved Datadog monitor-state/readback discrepancy; W6 is not marked Level 5.
- [x] Re-read after the full window: monitor `343029221` is `OK`, all 10 farm groups are `OK`, and the latest five heartbeat points per farm are `1`.
- [ ] Optional final gate: read the new workflow execution for this fault and confirm it received `farm_key=greenhouse_b`; metric recovery alone is not workflow-run evidence.
- [x] Workflow read-back completed: run `dccdcfcc-a2e1-489f-a06b-a7aa54d3957e` succeeded from monitor `343029221`, group `farm:greenhouse_b`, transition `Recovered`.
- [!] Several concurrent farm instances at 07:01 ended `Rate limit exceeded`; W6 needs fan-out/rate-limit tuning before claiming a smooth multi-farm Level 5 run.
- [x] Fixed W6 monitor-trigger fan-out limit: `monitorTrigger.rateLimit` changed from `1/300s` to `10/300s`, workflow republished, and live read-back confirms `published=true`, 8 steps, same farm-scoped monitor trigger.
- [ ] Re-run a controlled multi-farm recovery only if needed; confirm no rate-limit errors and that app notifications remain idempotent.

## Live W2/W6 attempt — 2026-11-11 06:53 UTC

- [x] W2 bounded live scenario completed with correlated simulator ACK, MongoDB persistence ACK and clean stop on `greenhouse_a/node2`.
- [ ] W2 monitor/workflow Alert chain was not exercised because the scenario was intentionally short of the five-minute monitor window.
- [ ] W6 live fault was not injected: the app has no farm-scoped evaluation-heartbeat fault control, and stopping the app would affect all farms. Build a scoped injector before claiming a W6 live drill.

## Parallel W2/W6 local rehearsal harness — 2026-11-11 06:25 UTC

- [x] Created `scripts/drill_parallel_w2_w6.ps1`: two concurrent synthetic-only lanes use separate local farm scopes (`drill_w2_local`, `drill_w6_local`) and unique incident/run IDs. Preflight checks output path and ID/scope separation; a bounded timeout and `finally` job cleanup are included.
- [x] PowerShell parser syntax check passed. Evidence path format is `outputs/drill_parallel_w2_w6_<utc>.json`; the script records local-only mode and leaves live acceptance gates pending.
- [ ] The harness was not executed in this implementation step; no evidence JSON/run IDs were generated. No live fault, deployment, AWS operation or Datadog write occurred. W2 CLEAR and W6 target-group recovery remain unverified.
- [x] W4 `D2` and W1 `A2` ran concurrently on separate farms; both scenario ACKs and MongoDB persistence ACKs succeeded.
- [x] W1 local virtual PLC interlock independently stopped the pump, closed the valve and returned `verified=true`.
- [!] Datadog monitor coverage is incomplete: W4 monitor stayed OK because its live metric currently has groups only for `greenhouse_a/node1` and `greenhouse_a/node2`; W1 monitor is `No Data` because the virtual PLC safety-trip metric is not being emitted to Datadog. Do not claim Alert→workflow for these two until telemetry is fixed or the drill targets an actually emitted group.
- [x] Fixed W4 telemetry: D2 emits `smiot.telemetry.status_mismatch=1` on start and `0` on stop with farm/node tags.
- [x] Enabled custom DogStatsD metrics on EC2 and redeployed the W4/W6 backend patch; service and healthz remained healthy.
- [x] Re-ran W4/W1 concurrently. Datadog now sees W4 `Alert` on `farm:greenhouse_a,node:1` and W1 `Alert` instead of `No Data`; W1 local SAFE_STOP and Mongo persistence still pass.
- [ ] Read the corresponding W4/W1 workflow instances and restore both monitors to OK before declaring those chains complete.
- [x] Read W4 run `b06dac70-cc51-4148-923b-ee813a741619` and W1 run `d2d35133-1764-4320-b59f-9b9dc0a68001`; both `SUCCEEDED`.
- [x] W4 monitor `342585836` returned `OK` after stop/normal and the five-minute window.
- [x] Changed W1 monitor `342734303` missing-data behavior to `resolve`; after the recovery evaluation cycle it returned `OK` instead of `No Data`.
## W9 + W5 live synthetic drills — 2026-11-11

- [x] W9 emitter deployed to EC2; `command_unacknowledged` metric sent with farm/actuator scope; monitor `342734743` returned `OK` after the bounded drill.
- [x] W5 MongoDB synthetic-down branch triggered monitor `342585827`; workflow `d3f0705e-2cbd-430a-9a3a-b1fd02a42cc9` produced successful monitor-linked runs.
- [x] W5 MQTT synthetic-down branch triggered monitor `342585828`; workflow run completed successfully.
- [x] Sent `normal` dependency gauges and waited for recovery; monitors `342585827` and `342585828` both returned `OK`.
- [ ] W9 still needs a fresh same-window workflow run readback if the submission requires a new run rather than the existing monitor-linked success history; no physical actuator was called.
## W9/W5 final replay — 2026-11-11

- [x] W9 monitor `342734743` Alerted, new monitor-linked workflow run `5eed8483-a77c-4829-ba2d-2f2cf4b198ce` succeeded, normal signal sent, monitor returned `OK`.
- [x] W5 evidence saved to `outputs/evidence/w5_dependency_drill_runtime.json`; MongoDB and MQTT monitors both read back `OK`.
- [x] W4 local refusal notification patch validated (17/17 notification tests, 3/3 scenario evidence tests).
- [x] W9 local late-ACK correlation patch validated (5/5 MQTT receiver tests, py_compile).
- [ ] W4/W9 changes are not yet published/deployed or live-drilled; W5/W6 remain open.
- [x] W5 read-only dependency probe added for MongoDB ping and MQTT TCP health before/after each isolated drill.
- [x] W6 local spec queries now include `by {farm}` for watchdog/evaluation heartbeat; not yet published because grouped workflow schema needs read-back validation.
- [ ] W5/W6 still require deployment and bounded live acceptance.

## W6 read-only recheck — 2026-11-11

- [x] Monitor `343029221` is `OK` for all 10 farm groups and the latest evaluation heartbeat is `1` for each farm.
- [!] Recent farm-scoped W6 instances include successful runs plus instances still `Running`; telemetry is healthy, but the fan-out/backlog gate is not closed for a smooth Level 5 claim.
- [x] No new fault was injected during this recheck; next gate is to reconcile queued/running instances and enforce one in-flight action per farm.

## W7/W8 advisory drills — 2026-11-11

- [x] Added Mongo-backed crop context metrics: `smiot.crop.envelope.approved` and `smiot.crop.stage_context.valid`; deployed to EC2.
- [x] Created dedicated Terraform monitors W7 `343594187` and W8 `343594185`, both farm/node scoped and linked to the existing published workflows.
- [x] W7 bounded drill: Alert → workflow `bb86206c-6df8-4b1d-8016-175a2fc62e49` Success → normal signal → monitor OK.
- [x] W8 bounded drill: Alert → workflow `593a670c-d59c-4104-8658-df260245a21e` Success → normal signal → monitor OK.
- [!] These are synthetic advisory proofs only; no irrigation, ventilation, drainage, spray, nutrient or physical actuator action was issued.
- [x] Evidence saved to `outputs/evidence/w7_w8_advisory_drills_runtime.json`.

## W10 AI provider safety — 2026-11-11

- [x] Scoped the latency monitor to `status:provider_error` and a 2-minute demo window; Terraform validate/apply succeeded.
- [x] Deployed bounded W10 emitter with explicit failure and normal modes to EC2.
- [x] Failure signal produced monitor Alert; normal signal produced monitor OK.
- [x] Existing published workflow run and safe HOLD notification path retained; no Gemini or actuator was called.
- [!] A fresh trigger attempt was rate-limited by Datadog, so it is recorded as `RATE_LIMITED`, not falsely marked as a new workflow Success.
- [x] Evidence saved to `outputs/evidence/w10_ai_safety_drill_runtime.json`.

## W2 live drill — 2026-11-11

- [x] Verifier/runner patch deployed; service and `/healthz` healthy.
- [x] Flatline command ACK and first sample carried the same incident ID plus boot/sequence metadata.
- [!] Monitor `342585819` did not Alert during the attempted hold; normal reset did not yield a following sensor sample within timeout.
- [!] Drill recorded as `FAILED_ACCEPTANCE`, not Level 5. Evidence: `outputs/evidence/w2_live_drill_20261111_failed.json`.
- [ ] Investigate metric delivery, monitor grouping and publisher cadence before the next live replay.
- [x] Root cause confirmed from Datadog points/source: flatline detector needs 10 samples (~10 minutes); attempted hold was 420s. Reset helper timeout was 45s while publisher cadence is ~60s.
- [ ] Next replay: hold 720–900s, wait at least 90s for the first normal sample, then read workflow and monitor recovery.
- [x] 11-minute replay produced monitor Alert and workflow Success; normal ACK/sample returned.
- [x] Recovery readback completed: monitor `342585819` is `OK`, flatline is `0`, and soil humidity is back in the normal range.

## W2 live harness preparation — 2026-11-11

- [x] Replaced the stale-ACK-prone mode helper behavior with exact `command_id`, mode, farm/node and `incident_id` matching; first post-command sample must carry the same incident ID and records `boot_id`/sequence.
- [x] Added `scripts/run_w2_live_drill.ps1`: requires a 420-second fault hold by default, checks monitor baseline and Alert, correlates reset ACK/sample to the canonical app incident, resets to normal in `finally`, waits a full recovery window, and writes one JSON artifact per run.
- [!] Not executed. This is harness readiness only; no live fault was injected. The final artifact must be joined with the monitor-triggered workflow run and Mongo verifier CLEAR evidence before W2 acceptance.

## W2 pre-drill correction — 2026-11-11

- [x] Aligned watchdog's flatline lookback sizing with the node publisher cadence setting `SMIOT_SIM_NODE_INTERVAL_SECONDS`.
- [x] Reworked `scripts/run_w2_bounded_drill.ps1`: 720-second default hold, require a successful scenario ACK/run ID, and issue STOP in `finally`.
- [x] Python compile and PowerShell parser validation passed.
- [x] Fixed the CLEAR result validator's conflicting sample minimum: it now accepts only the verifier's explicit cadence-derived `required_samples`, while still enforcing 300s span, freshness, variation, correlated CLEAR ACK, and all virtual outputs OFF. Focused unit suite passed 6/6.
- [ ] No live W2 fault was run as part of this code change. Next acceptance must read the exact monitor alert, workflow execution, Mongo verifier/CLEAR evidence, and final monitor OK.

## Priority replay continuation — 2026-11-11

- [x] W5: deployed read-only probe and ran Mongo/MQTT before/after checks; both real dependencies were reachable before and after; synthetic dependency metric cycle returned monitors `342585827`/`342585828` to `OK`.
- [x] W6: live readback shows published 8-step workflow, all 10 farm monitor groups `OK`, and heartbeat points equal to 1. The local farm-grouped JSON draft remains unapplied pending schema-safe redesign.
- [!] W5: historical Datadog workflow list still contains `Rate limit exceeded` instances; do not call the latest W5 run a clean Level 5 acceptance until trigger rate limiting is separated from the dependency evidence.
- [x] W5 rate-limit mitigation: monitor trigger changed from 1/300s to 4/60s and applied with Terraform; a fresh MongoDB alert run `8f156db1-e6ee-497b-86e9-ae5140d5660c` completed successfully.
- [ ] W5 recovery window is running (`278b0da9-46c4-496d-ad16-c19dee71f870`); after six normal points across five minutes, verify monitor `342585827` returns `OK` and save final clean evidence.
- [x] W5 recovery completed: six normal points delivered; MongoDB and MQTT read-only probes succeeded before/after; monitors `342585827`/`342585828` are `OK`, recovered workflow run `ba3b0184-d235-4d40-80fe-d04157b1bc35`.
- [x] W6 target-farm drill: `greenhouse_b` only reached Alert, nine other farm groups remained OK; workflow run `010ee0e9-61a1-4bcd-92d1-a110282a346b` succeeded and its app notification was read back from MongoDB. Normal ACK returned heartbeat metric to 1.
- [ ] W6 terminal recovery: monitor group `farm:greenhouse_b` still reports Alert while recovery window ages out; re-read monitor/workflow and update evidence when it returns OK.
- [!] W6 final readback at 18:07 UTC: normal ACK succeeded and all latest target-farm heartbeat points are 1, but Datadog group `farm:greenhouse_b` remains Alert and no recovered workflow run is present. Evidence saved; no repeat fault injected. Investigate Datadog monitor evaluation/state before marking W6 closed.
## Priority replay — 2026-11-11

- [x] W4: published local refusal notification via targeted Terraform apply; scenario run `05b3c872-639b-4a97-8fa4-3a763473b3e0` persisted observation in MongoDB and stopped normally; monitor `342585836` read back `OK`.
- [x] W9: deployed late-ACK matcher and W5 probe script to EC2; service active and `/healthz=200`; synthetic drill command `63f8db3e-2714-4a58-ae78-0ef87a37da40` produced Alert and Recovered workflow instances; monitor `342734743` read back `OK`.
- [ ] W5/W6: runtime replay pending because the AWS CLI session expired before the read-only dependency probe could run. Refresh `aws-moi` then run W5 before/after probes and a single-farm W6 drill; do not publish the unverified farm-grouped W6 spec without schema readback.

## Priority W9/W4/W1/W10 branch readback — 2026-11-11

- [x] W1 bounded synthetic A2 pressure-zero scenario reached virtual SAFE_STOP; ACK context matched, outputs OFF, valve closed, Mongo ACK persistence true. Monitor `342734303` was OK. Scenario run `565ab740-e2a7-4ad2-abc5-e69dc677c509`; SSM command `d1eb7197-db3c-4cae-8ed2-f150ad830283`.
- [x] W4 monitor `342585836` read back OK. Scoped CloudTrail no-SSM finding is recorded in `outputs/evidence/w4_cloudtrail_no_ssm_audit_20261112.json`; do not generalize beyond the selected window.
- [!] W9 monitor `342734743` is OK, but this branch did not prove the late ACK round trip with a live matching command ID. Existing unit/synthetic evidence is not equivalent to runtime ACK proof.
- [!] W10 monitor `342585824` was OK before and after an isolated synthetic 6000 ms sample (SSM `146d541c-be95-4d22-8c61-5366a01ffc0f`, Success); Datadog received the point, but no Alert or new workflow run appeared. A normal cleanup command was attempted without captured command ID/result. Do not call this a fresh W10 acceptance.
- Evidence: `outputs/evidence/priority_w9_w4_w1_w10_branch_20261111.json`.

## W9 live late-ACK update — 2026-11-11

- [x] App-side live cycle verified: pending command → automatic ACK suppressed → timeout/no-ACK metric → exact late ACK → MongoDB ledger `acknowledged`. Farm `greenhouse_j`, output remained OFF, and the result was `verified`.
- [!] Datadog monitor `342734743` alerted and linked workflow run `f76b3ca8-c023-4d40-b3a2-76d63f91b5cc` was created, but that run ended `Rate limit exceeded`; a clean workflow-side success/recovery run is still required before claiming full W9 Level 5.
- Evidence: `outputs/evidence/w9_late_ack_live_20261111.json`.

## W9 live late-ACK harness — 2026-11-12

- [x] Added an authenticated admin-only `/api/demo/w9/late-ack` endpoint. It is disabled unless `SMIOT_DEMO_MODE` is enabled and uses the existing `SMIOT_DEMO_CONTROL_TOKEN` bearer guard plus a Mongo-backed one-request/minute limit.
- [x] Drill can only send a synthetic greenhouse_j virtual PLC command targeting bit0=OFF. It does not call a physical device or issue an ON command.
- [x] Fixed two simulator/runtime gaps found in the live attempt: the W9 status readback no longer echoes the pending command ID during this drill, and the endpoint imports the monotonic timer needed for its wait loop.
- [x] Late ACK matching still requires the exact command ID and farm; the verified ACK and match result are persisted in `action_ledger`.
- [x] Deployed to EC2 in ap-southeast-2; service active and `/healthz=200`.
- [x] Live endpoint returned verified in 7.22s: app command `69119628362046919ed68961948f08f4`, synthetic late ACK true, target OFF, exact farm/ID match, verified ACK, Mongo ledger acknowledged.
- [x] Datadog received both W9 timeout and late-ACK metrics; monitor `342734743` entered Alert.
- [!] W9 workflow was triggered as run `f76b3ca8-c023-4d40-b3a2-76d63f91b5cc` but returned `Rate limit exceeded`. App-side late-ACK and monitor detection passed; workflow execution/recovery remains unverified until the trigger limit window clears.
- [x] Focused MQTT receiver tests passed 5/5; Python compile check passed.
- Evidence: `outputs/evidence/w9_late_ack_20261112.json`; readback utility: `scripts/read_w9_acceptance.py`.


## UI/UX "Datadog dẫn đầu" (12/11/2026)

- [x] Hoàn thành P0 (trung thực dữ liệu) và P1 (Datadog dẫn đầu /incident và /incident/<id>) trong code local; chưa triển khai EC2.
- [x] P2 một phần: bảng dạng thẻ dưới 768 px, chữ giá trị dài xuống dòng.
- [x] 269/269 test OK (240 cũ + 29 mới trong tests/test_ui_datadog_first.py). Import các trang không lỗi. Đã render thật /incident và /incident/<id> bằng khung thử NiceGUI với dữ liệu giả lập chỉ dùng để kiểm giao diện; đã kiểm 375 px không tràn ngang và trạng thái "chưa cấu hình khóa Datadog". static/test_inverter.html đã dựng thật trên trình duyệt: không có điểm nào trước bản tin đầu tiên, nhãn trục HH:mm:ss.
- [!] Chưa kiểm trên dữ liệu MongoDB thật và khóa Datadog của EC2. Khóa trong .env cục bộ thuộc tổ chức Datadog cũ (thấy 6 monitor SMIOT mã 3399xxxxx đến 3414xxxxx, tất cả No Data; không thấy mã monitor theo cấu hình ca 3425xxxxx), nên chạy cục bộ sẽ hiện "Không có trong tổ chức Datadog". Cần kiểm lại trên EC2 sau khi triển khai.
- [!] Events API v2 và Logs list API v2 chưa được thử trên tổ chức có dữ liệu; cần khóa ứng dụng có quyền events_read và logs_read_data, thiếu quyền thì hiện thông báo 403 cho đúng mục đó.

## Bố cục trang Home (12/11/2026)

- [x] Sửa tooltip hiện chữ `<br/>`, bảng tín hiệu vừa khít desktop, xếp lại lưới 3 hàng (số tổng, bảng cạnh Cần chú ý, biểu đồ đều chiều cao), gộp thông báo trùng khi hiển thị. Chỉ local, chưa triển khai EC2.
- [x] 274/274 test OK. Đã render thật bằng khung thử với dữ liệu giả lập: 1450 px và 375 px không tràn ngang trang.
- [!] Chưa kiểm trên dữ liệu MongoDB thật. Số "Lệnh chờ ACK" là truy vấn mới (action_ledger, trạng thái requested/published trong 24 giờ) chưa chạy trên DB thật; nếu lỗi sẽ hiện dấu gạch. Số lần gộp chỉ tính trên các bản ghi đã đọc (tối đa 30 mỗi nhà màng).

## W3/W5 correlated runner (12/11/2026)

- [x] Added `scripts/run_correlated_w3_w5.py` for isolated synthetic W3/H1 and W5/H2 control-plane runs. It resolves one exact `scenario_run_id` to one MongoDB `incident_id`, writes dependency evidence, decision, HOLD ledger, observation, recovery evidence and CLEAR state, and emits correlated Datadog log/span tags.
- [x] Python compile check passed; full unit suite passed 277/277. Runner does not stop or restart services and does not operate real hardware.
- [ ] EC2 execution and Datadog exact-ID readback remain pending; do not call W3/W5 live Level 5 until those readbacks pass.

## W10 provider failure correlation (2026-11-12)

- Added `scripts/run_w10_correlated.py`; compile check passed.
- Deployed and ran on EC2 via SSM. Latest run: `INC-SMIOT-W10-20261112T074415-F6AB2339`, `scenario_run_id=b91cc3d0-78bf-4577-b52d-68381d739a0a`, MongoDB status `recovered`, `synthetic=true`, fallback verified.
- Datadog Logs API returned 2 exact-ID events. APM span query returned 0 for this short-lived runner, so the W10 case remains partial until a persisted span is read back; do not call it full Level 5.

## W6/W9 specialized correlation (12/11/2026)

- Implemented service/special_incident_correlation.py for farm-scoped synthetic incident creation, timeline events, correlated log/span emission, and evidence-based recovery.
- W6 demo_detector_fault now carries an incident ID; normal ACK is only a recovery request, and detector_heartbeat closes after a fresh evaluation.
- W9 late-ACK now registers a pending command with incident ID, adds incident ID to timeout metric/log, and closes on exact late ACK match.
- Added scripts/run_w6_correlated_drill.ps1 and scripts/run_w9_correlated_drill.ps1. Focused tests pass 3/3; py_compile passed. EC2/Datadog readback remains pending.

## Latest specialized rollout (12/11/2026)

- Deployed specialized correlation modules/runners to EC2; service active and healthz 200.
- W3 `INC-SMIOT-SCENARIO-61B502B2FD022B9C`, W5 `INC-SMIOT-SCENARIO-B1797FE944C944F0`, W6 `INC-SMIOT-W6-DRILL-735089BF22`, and W10 `INC-SMIOT-W10-20261112T074904-7243BB99` are recovered in MongoDB with exact IDs in their synthetic evidence paths.
- W9 latest `INC-SMIOT-W9-DRILL-0AAF284684` has the correct command timeout, matching late ACK, and final MongoDB status `recovered` after the terminal-state patch.

## Scenario verification fix (12/11/2026)

- Scenario stopped ACKs no longer remain indefinitely in `recovering`: the app checks for a post-stop telemetry sample scoped to the exact farm/node and records `scenario_recovery_verified` only when found.
- Backfill closed 17 active scenario incidents using existing post-stop telemetry. Two remaining active incidents are non-scenario W9 records in greenhouse_j.

## Velxio migration safety (12/11/2026)

- Added an isolated systemd template and reversible EC2 install/rollback scripts for the Velxio synthetic bridge.
- Default is disabled; Wokwi remains untouched and can be restored immediately.
- Local shell syntax validation passed. EC2 deployment is intentionally pending the bridge contract/UI end-to-end checks.
- Deployment variable mismatch fixed: systemd now passes `VELXIO_CHANNEL`, and the installer writes both channel aliases. Read-only review found Node1 intentionally publishes telemetry only (no ACK), while Node2 ACKs actuator commands but the supplied sketches do not implement `SET_PROFILE`; missing profile ACKs are therefore expected, not a Mongo persistence bug.

## Hiển thị đúng bằng chứng sự cố (12/11/2026)

- Đã sửa `pages/incident.py` để không gọi trace cùng khung giờ là trace của incident. Chỉ `evidence.trace_ids` mới được tính là trace liên kết; Logs API vẫn lọc theo chuỗi `incident_id` chính xác.
- Đã sửa `service/incident_blackbox.py` để chuẩn hóa nhãn node như `node1` trước khi dựng timeline; dữ liệu lưu trong MongoDB không bị thay đổi.
- Kiểm tra tĩnh: `py_compile` cho hai file đã sửa qua. Bộ seed 10 hồ sơ vẫn giữ trạng thái synthetic và sáu bước `done`; không tạo bằng chứng Datadog giả.
- Việc còn lại: triển khai hai file lên EC2 và kiểm tra trực tiếp một hồ sơ; nếu log/trace liên kết chưa tồn tại, trang phải tiếp tục hiển thị 0 và ghi rõ thiếu bằng chứng.
- Đã triển khai lên EC2 bằng SSM; kiểm tra lại sau restart: `smiot.service=active`, `health_http=200`, MongoDB/MQTT đang lắng nghe. Lần kiểm tra đầu gặp race lúc cổng 8080 vừa mở, không phải lỗi ứng dụng.
- Ca diễn tập riêng `INC-SMIOT-SCENARIO-565435A465282EBB` đã tạo hồ sơ thật trong MongoDB nhưng Datadog trả 0 log/0 span khớp exact ID. Đã bổ sung correlation ở nhánh `farm/demo/evidence`: sau khi xác minh run + farm, log có `incident_id` và span có tag `incident.id`; chưa tuyên bố hoàn tất cho đến khi chạy lại sau deploy.
- Đã chạy lại ca riêng sau bản vá correlation: `scenario_run_id=cc797f61-01b9-4b63-9843-a2abbc85f2fc`, incident MongoDB `INC-SMIOT-SCENARIO-960EFBDDBF4881C4`, có ACK quan sát và hồ sơ `recovering`. Tìm exact incident ID trên Datadog vẫn trả 0 log/0 span trong cửa sổ chạy; vì vậy giao diện đúng khi hiển thị “chưa có bằng chứng liên kết”, chưa được phép tự ghép trace/log cùng giờ. App đã deploy và `/healthz=200`; việc còn thiếu nằm ở Agent forwarding/index hoặc đang đọc nhầm tổ chức Datadog, không còn ở bộ lọc giao diện.
- Đã sửa đường forwarding: Datadog Agent trên EC2 trước đó chỉ tail `incident_events.jsonl` và recovery; bổ sung `system.log`/`error.log` vào `smiot.d/conf.yaml`, restart Agent và xác nhận config active. Ca mới `INC-SMIOT-SCENARIO-92C5A925F941F621` (`scenario_run_id=a307f8a0-8da2-4838-b983-96a7cfdbc6f4`) được Datadog API đọc thấy 2 log và 1 APM span khớp exact incident ID. Đây là bằng chứng live đầu tiên của correlation; MCP explorer có thể trễ, nhưng app dùng cùng Datadog API đã có dữ liệu.
- Đã chạy 9 ca còn lại với scope farm riêng. W1/A2 (`EB45FE637845A41F`), W2/S1 (`EB1C57AC2399320C`), W7/S2 (`EA9A4856506E86E4`) và W8/S3 (`98FCAF125547F848`) có incident MongoDB; Datadog API trả log exact ID, W2/W7/W8 có thêm span. W3/H1, W5/H2, W6/H4, W9/A4, W10/H6 chỉ hoàn tất start/sample/stop nhưng generic scenario path không trả observation ACK, nên chưa có incident_id live để nối Datadog. Cần chạy runner chuyên biệt theo từng workflow.
- Velxio UI: `/devices` now reads latest MongoDB node/flow samples per selected farm, shows green/yellow/gray LED states for fresh/slow/stale data, and displays latest command plus incident/scenario correlation. Local compile passed; EC2 rollout waits for bridge contract validation.
- Velxio rollout: bridge, UI, provenance and health allowlists are now deployed additively to EC2 with a remote rollback backup. `/healthz`, `/devices` and `/` return 200; MongoDB, MQTT and `smiot.service` are active. The Velxio bridge is installed but disabled until a real Velxio sensor stream is intentionally connected; Wokwi remains the active rollback/default path.
- Velxio end-to-end contract check: bridge is now enabled. A bounded Velxio-compatible stream reached local MQTT and MongoDB with `source=velxio_synthetic`; a virtual pump subscriber received the command and returned an exact correlated ACK, which the app received and stored in `action_ledger`. The temporary publisher stopped; the bridge remains enabled for the live demo session.
- Velxio circuit presentation: imported `node1_environment.zip`, saved the project as Public, and embedded the real Velxio project in `/devices` with a fullscreen fallback link. This is the actual Velxio circuit/firmware view, not an HTML/CSS redraw. EC2 route verification remains green (`/healthz=200`, `/devices=200`).
- Fixed the initial iframe refusal by using Velxio's official Share/Embed URL (`/embed/...`) instead of the editor URL. Direct project link remains available as fallback; EC2 verified again with `/healthz=200` and `/devices=200`.
- Added a second Public Velxio project for the virtual pump (`node2_virtual_pump.zip`). `/devices` now has tabs for the real environment circuit and the pump/LED circuit. When the pump project is running, SMIOT control commands can be reflected by the pump LEDs/buzzer through the existing bridge topic and correlated ACK path.
- Fixed the Velxio blank/loading panel: the embedded circuits are now rendered once outside the 10-second refreshable MongoDB status panel, so simulator sessions are preserved while telemetry cards update.
- Fixed the remaining white panel inside the Velxio embed by clipping the unused right-side pane and using a stable desktop-width iframe; the real circuit is now centered and visible in `/devices`.
# Velxio adapter — 2026-11-12

Implemented an additive adapter at `scripts/velxio_mqtt_bridge.py` based on the Velxio three-device demo. It translates node1/node2/flow messages into the existing SMIOT `farm/sensor` envelope and forwards only allowlisted control actions. Correlation IDs are retained end-to-end and all messages are marked `synthetic=true`, `source=velxio_synthetic`. Wokwi remains the existing default path. Local contract tests pass (4/4); full suite passes (281/281). No EC2 deployment was performed.

## Velxio source handoff — 2026-11-13

The EC2 simulator now grants independent 35-second source leases to Velxio for greenhouse_j Node 1, Node 2, and the flow meter (the third Velxio device/project). A valid Velxio sensor message refreshes only its own lease; while fresh, EC2 skips that exact stream and continues publishing every other device. If Velxio stops, EC2 resumes that stream at the next publisher loop after lease expiry. The bridge sends the lease heartbeat before relaying the sample to avoid a duplicate at handoff. Deployed to EC2 with a remote backup; both affected services are active and `/healthz` returns 200. Runtime takeover after expiry still needs a live stream check.

## Velxio Node 1 DHT22 fix — 2026-11-12

DHTesp called `digitalWrite(LOW)` before configuring its GPIO as output, causing Velxio's emulator warning. Replaced it with the Adafruit DHT library used by Velxio's public ESP32 DHT22 example; the modeled sensor remains wired to GPIO4. Invalid DHT readings are omitted rather than replaced with constants. Wi-Fi/MQTT reconnects are nonblocking, and PubSubClient uses a 512-byte buffer. Live compile passed; Serial returned `at=29.0`, `ah=72.0`, and `MQTT publish OK` every 10 seconds. EC2 MongoDB read-back confirmed the latest `greenhouse_j` sample with `source=velxio_synthetic`, `air_temp=29.0`, and `air_hum=72.0`. Local source snapshot: `velxio/node1_environment/`.

## Velxio Node 2 pump sketch repair — 2026-11-13

Updated the active Velxio Node 2 project at `velxio/node2_virtual_pump/` and on Velxio. Fixed ArduinoJson 7 usage, MQTT ACK byte-buffer typing, ESP32 LEDC buzzer setup across Arduino core 2.x/3.x, and nonblocking Wi-Fi/MQTT reconnects. Velxio detected the required `ArduinoJson` and `PubSubClient` libraries and compiled successfully for ESP32 DevKit V1. A local Arduino CLI compile also passed (70% flash, 14% RAM). Live simulator check passed: Wi-Fi/MQTT connected, app command `32dc620f6b6d4031a176814abb80fdcb` switched one virtual output on and received matching verified status; the Velxio Serial Monitor printed `virtual pumps on=1/7`. Sent an OFF command (`b9f43f4b566646f0ac5828176ae0e62e`), app returned to 0/7, and Serial confirmed `virtual pumps on=0/7`. This verifies the virtual path only; no physical pump is attached.

To make the sound noticeable, increased the successful ACK tone from 100 ms to 380 ms (failed ACK tone 650 ms) and recompiled successfully in Velxio. The circuit screenshot during the prior 1/7 test showed the first green LED lit. Recompiling reset ESP32 outputs to their safe boot state (all OFF). The app currently reports no allowed pumps for the selected account, so I did not bypass authorization to trigger another command; audible output after the longer tone remains unverified.

## Velxio Node 2 → Node 3 → app status — 2026-11-13

Node 1 and Node 3 simulators are running in Velxio and publishing normal synthetic samples to the shared public MQTT broker. Node 2 compiles and is subscribed to actuator commands; it is not a periodic sensor publisher. Local app source includes all three Velxio circuit tabs and latest profile event/status cards. Bridge logic already switches all three to fault profile on scenario start and back to normal on stop/clear, with exact farm and command correlation. Focused bridge contract suite passes 7/7.

The deployed EC2 app is behind the local source: `/devices` still renders the previous one/two-board presentation and has no Node 3 tab; Mongo-backed Velxio cards have no latest samples. Thus simulator-level success is confirmed, but this session did not verify the complete three-device flow through EC2/MongoDB/UI or the recovery ACK path. AWS CLI `aws-moi` is expired, preventing deployment and live read-back. Next action is reauthenticate AWS CLI, deploy the local changes, then run and read back one controlled fault → recovery cycle for all three devices.

- Velxio device page clarified: embedded circuits are previews; standalone Velxio links run each node. Node 2 preview height increased for lower indicators. UI-only change; no firmware/backend changes.
