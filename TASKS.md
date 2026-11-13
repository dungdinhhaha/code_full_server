# TASKS — Delivery plan and ownership

**W3 result (2026-11-11 12:04 UTC):** clean automatic-recovery attempt completed but failed its acceptance gate. The app was stopped for 420 seconds without manual intervention; the monitor did not trigger despite raw `systemd.unit.active=0`. Guarded SSM recovery then restored the app and verified HTTP/Mongo telemetry. Next bounded repair is R1/R2 for W3 monitor evaluation: reconcile raw point timestamps, host/service grouping and evaluation state before changing query or window; then repeat one clean drill. Do not manually label this run recovered-by-Datadog.

**W3 acceptance closed (2026-11-11 12:55 UTC):** applied the measured timing fix and health-wait/verifier ordering. A clean monitor-triggered run succeeded end-to-end and returned the monitor to OK. Keep the 2-minute window and 60-second workflow rate limit explicitly labeled as demo-scoped; production policy should be revisited with a faster independent probe rather than silently shortening safety windows.

**Work log:** after every investigation, edit, deployment or drill, append the actual action and result to `ACTIVITY_LOG.md`; keep acceptance status in `PROGRESS.md`. Record failures and rollback as well as successes. Never log credentials.

- [x] Add Velxio device demonstration panel to `/devices` using MongoDB latest node/flow samples, explicit fresh/slow/stale LED states, and latest command incident/scenario context.
- [ ] Run browser/mobile smoke check after Velxio bridge contract passes; deploy only with Wokwi rollback retained.

**Current execution priority (revised 2026-11-11):** resolve shared trigger/verification defects, then W3 → W6 → W2 → W1 → W4 → W5. W9 already had a metric-path drill but is outside this repair pass; W7/W8/W10 remain queued. Make narrow changes; do not run another full sequence until the blocking case passes its own gate.

## Thiết kế lại giao diện: trung tâm quan sát, điều khiển và phục hồi (2026-11-12)

**Mục tiêu:** người vận hành nhìn một màn hình biết nhà màng nào cần chú ý và vì sao, đi tiếp tới thiết bị, lệnh, ACK, kết quả xác minh và hồ sơ sự cố của đúng farm đó. Mọi trạng thái lấy từ MongoDB, API hoặc phản hồi thiết bị ảo. Thiết bị ảo luôn mang nhãn "mô phỏng". Không thêm đường điều khiển phần cứng thật.

**Khảo sát:** agent chỉ đọc, model Haiku (bản Haiku mới nhất phiên làm việc cung cấp), loại Explore. Không chạy được `git status` vì máy không có `git` trong PATH; đã sao lưu `pages/`, `components/`, `tests/` và ba file nhật ký ra thư mục tạm trước khi sửa.

### Hệ thống thiết kế (agent chính sở hữu)
Bản đầu (hình vòm nhà màng, chữ Bricolage Grotesque) đã bị loại sau khi xem thử vì chưa đủ chuyên nghiệp. Bản đang dùng theo kiểu phòng điều khiển: chuẩn HMI ISA-101 (bình thường màu trầm, màu chỉ cho bất thường), mật độ bảng kiểu Grafana và Datadog, hồ sơ sự cố theo dòng thời gian có bằng chứng.
- Màu: nền `#F1F3F2`, mặt bảng `#FFFFFF`, mực `#14261D`, xanh điều hướng đậm `#0F241B`, xanh hành động `#1B6447`, đường kẻ `#E1E7E0`, cam `#F08A24` (cần theo dõi), đỏ `#C2362B` (cần xử lý), xám `#7A8580` (dữ liệu cũ hoặc chưa có). Bộ màu biểu đồ nằm trong `components/theme.py: CHART`.
- Chữ: một họ IBM Plex Sans cho toàn bộ, số `tabular-nums`, cỡ nền 13,5px.
- Trạng thái luôn có cả hình và chữ: ● bình thường, ▲ cần theo dõi, ■ cần xử lý, ○ chưa có dữ liệu. Mỗi số đo và mỗi biểu đồ ghi thời điểm và nguồn.
- Bốn trạng thái màn hình: đang tải, dữ liệu cũ, không có dữ liệu, lỗi kết nối (`components/ui_kit.py: state_panel`).
- Chuỗi bằng chứng ba bước cho lệnh: Đã gửi lệnh, Thiết bị đã ACK, Kết quả đã xác minh (`command_chain`). Bước chưa có bằng chứng hiển thị "đang chờ".
- Thành phần dùng chung: `page_header`, `panel`, `stat`/`stats`, `status_chip`, `farm_tabs`, `range_pills`, `echart_base`, `file_step`, `evidence_chain`, `confirm`, `ext_link`, `source_note`.

### Màn hình
```
Desktop                                           Điện thoại
+--------+--------------------------------------+ +---------------------+
| SMIOT  | Tên trang    [farm v] mô phỏng  chuông| | Tên trang  [farm v] |
| Quan   +--------------------------------------+ +---------------------+
|  sát   | Kết luận: 1 cần xử lý, 2 cần theo dõi | | kết luận            |
| Điều   | [Tất cả][A][B][C] ... [J]  thanh farm | | thanh farm (cuộn)   |
|  khiển | bảng nhiệt 10 farm x kênh | cần chú ý | | cần chú ý           |
| Mùa vụ |                           | tuổi mẫu  | | bảng nhiệt (cuộn)   |
| Quản   | nhiệt độ theo giờ | ẩm đất theo giờ  | | biểu đồ 1 cột       |
|  trị   | sự cố 24 giờ      | cần người duyệt  | +---------------------+
+--------+--------------------------------------+ | điều hướng dưới     |
```
- **Home (`/`)**: màn biểu đồ, mọi biểu đồ dựng từ aggregation MongoDB (`telemetry`, `operational_incidents`, `notifications`, `action_ledger`). Thanh farm cho mỗi nhà màng một chỗ riêng: chọn farm thì đổi sang số mới nhất, biểu đồ theo thời gian, thiết bị và lệnh gần đây, sự cố của đúng farm đó, không tải lại trang. Có lối tắt tới Bơm, Biến tần, Lịch tưới, Sự cố, Mùa vụ.
- **Vận hành (`/plc`, `/inverter`, `/schedule`, `/devices`, `/projects`)**: mỗi trang nêu farm đang chọn và nhãn mô phỏng; mỗi lệnh có chuỗi ba bước; lệnh rủi ro (bật bơm, chạy biến tần, đổi chế độ, chạy kịch bản, xóa lịch) cần xác nhận; thiếu dữ liệu thì khóa lệnh bật và nêu lý do.
- **Sự cố (`/incident`, `/incident/{id}`)**: hồ sơ sáu chặng: phát hiện, số đo và bối cảnh farm/lô, monitor/log/trace Datadog, quyết định, ACK, bằng chứng phục hồi. "Đã phục hồi" chỉ hiện khi chính hồ sơ đó có bằng chứng; ngược lại hiện "chưa xác minh".
- **Datadog (`/chart`)**: lối vào dashboard `rzf-su8-zgf`, monitor, log. `nkc-685-vw8` là ID lịch sử, không dùng làm liên kết.
- **Mùa vụ (`/mongodb-lab`, `/lot/{token}`)**: biểu đồ tiến độ theo giai đoạn, dải dự kiến kiểm tra hoặc thu hoạch, chất lượng dữ liệu, ảnh theo giai đoạn; ít chữ.
### Luồng người dùng cần chạy thông
1. Home → thấy farm cần chú ý và nguyên nhân → bấm farm → chi tiết farm.
2. Chi tiết farm → Bơm hoặc Biến tần của farm đó → gửi lệnh có xác nhận → thấy Đã gửi, ACK, Đã xác minh.
3. Chi tiết farm hoặc Home → sự cố liên quan → hồ sơ sự cố → mở đúng monitor, log, trace, dashboard Datadog.
4. Mùa vụ → chọn lô → tiến độ, mốc dự kiến, ảnh giai đoạn → trang công khai của lô.

### Quyền sở hữu file (không hai agent cùng sửa một file)
| Người sửa | File | Ghi chú |
|---|---|---|
| Agent chính | `components/theme.py`, `components/ui_kit.py` (mới); trong `pages/home.py` chỉ phần vỏ: `CUSTOM_CSS`, `global_topbar`, `sidebar` (sửa xong trước khi giao Agent 1); `pages/login.py`; `service/incident_blackbox.py` (đối chiếu ID Datadog); `tests/`; `TASKS.md`, `PROGRESS.md`, `ACTIVITY_LOG.md` | Layout, điều hướng, tích hợp, triển khai |
| Agent 1 (Sonnet) | `pages/home.py` (từ `metric_box` trở xuống: thẻ, chi tiết farm, `trang_chu`), `pages/farm_overview_component.py` | Không đổi tên key trong `state`, không sửa `sidebar`/`global_topbar`/`CUSTOM_CSS` |
| Agent 2a (Sonnet) | `pages/plc.py`, `pages/inverter.py` | Giữ nguyên hợp đồng sự kiện với `static/test_plc.html`, `static/test_inverter.html` (chỉ đọc) |
| Agent 2b (Haiku) | `pages/schedule.py`, `pages/devices.py`, `pages/project.py` | Đổi giao diện theo theme, sửa farm của trang Lịch |
| Agent 3a (Sonnet) | `pages/incident.py`, `pages/mongodb_lab.py` | Giữ tên `DD_BASE`, `DD_DASHBOARD` |
| Agent 3b (Haiku) | `pages/chart.py`, `pages/data_table.py`, `pages/public_lot.py` | `pages/traceability.py` chỉ là redirect, giữ nguyên |

Agent triển khai chỉ đọc `components/`, `service/`, `static/`, `main.py`. Cần đổi gì ngoài phần của mình thì báo agent chính.

### Tiêu chí nghiệm thu
- [ ] Nhìn Home biết farm nào cần chú ý và vì sao.
- [ ] Từ farm mở được thiết bị và sự cố liên quan.
- [ ] Hồ sơ sự cố chỉ dùng dữ liệu của đúng incident; "đã phục hồi" có bằng chứng.
- [ ] Liên kết Datadog mở đúng tài nguyên (dashboard `rzf-su8-zgf`).
- [ ] Không nút chết, không lỗi khi chuyển farm, chuyển tab.
- [ ] Dùng được trên desktop và điện thoại.
- [ ] Triển khai EC2; `/login` và `/healthz` trả kết quả tốt.

## Workstreams
| Owner | Workstream | Files/area | Acceptance |
|---|---|---|---|
| Luna A | Virtual scenario control API | `main.py`, `scripts/demo_scenario.py` | Deployed to EC2; API remains gated until `SMIOT_DEMO_CONTROL_TOKEN` is securely configured and a simulator ACK is verified |
| Luna B | W6 heartbeat alignment | `service/detector_heartbeat.py`, monitor Terraform | Separate evaluation freshness from process heartbeat; query/tags/flag match; verify live data before apply; app-process limitation explicit |
| Luna C | Incident/recovery contract | `service/incident_lifecycle.py`, verifier | Same incident ID; verified CLEAR requires matching ACK/ledger and recovery proof; no runtime proof yet |
| Luna D | Ten-farm overview | `pages/home.py`, overview component, app navigation | Existing Mongo-backed multi-signal ten-farm overview and incident section; assess module-global selected-farm race; avoid duplicate UI |
| Luna E | Metric contract alignment | W1/W2/W9/W10 emitters and `deploy/datadog/terraform_monitors/monitors.tf` | Match producer/query; mark W9 resource drift/import need; W10 provider monitor is local draft until plan/apply/live verification |

## Gate sequence
- [x] **G0 Inventory:** dirty worktree preserved; intended AWS account/region/EC2 verified; rollback archive created before source replacement.
- [x] **G1 Contracts:** API, incident envelope, farm/device IDs, status machine, concurrency behavior implemented locally.
- [x] **G2 Local implementation:** implementation merged in shared worktree and source/resource package deployed; worktree remains uncommitted.
- [~] **G3 Verification:** local and EC2 staging compilation plus runtime imports passed; the 2026-11-11 incident drills exposed the open defects listed below. Package inspection confirmed secret/database files excluded.
- [~] **G4 Datadog:** correct US1 org `NO` and ten published SMIOT workflows were previously verified; monitor/workflow runs were observed on 2026-11-11. W3 automatic start and W6 recovery remain unproven. Recheck live revisions before editing because prior observations are time-bound.
- [x] **G5 EC2:** pre-deploy snapshot and source rollback archive created; package scanned; app/bridge deployed; health and service smoke checks passed; rollback archive retained.
- [~] **G6 Drills:** W4, W1, W9, W2, W5, W3 and W6 were injected sequentially on 2026-11-11. Monitor/workflow/notification paths were observed, but the end-to-end evidence gates below remain open. W7/W8/W10 were not injected.
- [ ] **G7 Acceptance:** pending; do not mark Level 5 unless each step in `DESIGN.md` is evidenced on the same incident.

## Initial gaps to close
- [ ] Scenario API: deployed; securely configure token and prove external start/stop plus matching simulator ACK.
- [ ] W4: capture a complete monitor-triggered refusal and prove no SSM invocation.
- [ ] W1: tie live monitor to producer/query; verify ACK/readback and ledger in one run.
- [ ] W9: run no-ACK drill, suppress duplicate command, confirm safe state and subsequent matching ACK.
- [~] W2: cadence-aware verifier/freshness patch is deployed; active monitor `342585819` and flatline metric are confirmed. A bounded S1 run persisted and stopped cleanly, but the run was shorter than the five-minute Alert window; still prove Alert→workflow→CLEAR with a longer controlled drill.
- [ ] W5: separately exercise Mongo write failure and MQTT transport failure; don't claim dependency discrimination from a healthy branch.
- [ ] W3: repeat controlled outage from monitor trigger and show verifier before notification; never restart EC2/Mongo/MQTT.
- [~] W6: monitor and workflow now share `evaluation_heartbeat`, grouped by farm; backend emitter accepts the real MQTT `at/ah` fields and is deployed. Wait for a full five-minute OK window, then drill missing-evaluation handling; split detector process before detector-only restart claims.
- [ ] W7/W8/W10: complete one correlated safe advisory/fallback drill each; no unapproved agronomic/actuator action.

## Playwright/browser use
Use Terraform for supported Datadog configuration and AWS CLI for AWS inspection/SSM operations. Terraform files, not the AWS CLI, are the desired configuration source of truth where IaC exists. Browser access is for authentication, unsupported settings and final visual acceptance. Before `apply`, verify Datadog site/org and AWS account/region, inspect the plan, back up current JSON/revision and reconcile/import existing resources to avoid duplicates or replacement. If a setting is unsupported by Terraform, use a narrow API/CLI exception and read it back. Serialize writes to each resource; never print credentials.

## W1–W6 upgrade plan after the 2026-11-11 drill

**Scope and order:** finish W3 → W6 → W2 → W1 → W4 → W5. Fix shared timing, correlation and duplicate-run behavior before repeating a disruptive drill. Keep W7/W8/W10 out of this pass. Every live change must target the verified Datadog US1 organization and the intended AWS account/EC2 instance. Record the current JSON/revision before changing a monitor or workflow; reconcile Terraform state so the next apply does not undo a live fix.

**Configuration tools:** Terraform is the source of truth for supported Datadog monitors/workflows and AWS CLI is the source of truth for AWS inspection and operations. Workflow JSON is reviewed/versioned as Terraform input or fixture; do not rely on manual UI edits for repeatable changes. Workflow API fields rejected by the provider must be explicitly documented and handled through a narrow API/CLI exception, then read back and checked for drift.

### Why the previous plan did not unblock the project

The prior plan mixed inventory, architecture improvements and rehearsal into one long list, and retained an obsolete W4-first priority. It did not make each failed observation a single, bounded repair loop. The following gates replace that approach:

- [ ] **R0 — Freeze a current baseline (one pass).** Read live Datadog monitor group states, current workflow revisions, Terraform plan, EC2 service state and the exact code deployed. Compare with local files; write a small drift table. Do not re-investigate every historical run. Use the latest known failing runs: W3 `60b7c632-b8d7-42e7-98ea-701d9bc53aa7`, W6 `587e0e22-5496-44ac-bd14-a2f4c6dbc2a3`, W2 `c16f7820-01ce-484d-a47c-a3497e14cd12`.
- [ ] **R1 — Diagnose before changing.** For each failing case, record one falsifiable hypothesis, the exact observation that distinguishes it, and the smallest config/code change. W3: compare source metric timestamps and grouped monitor transition with `smiot.service` stop/start. W6: inspect per-farm monitor groups, query window and all active producers before altering rate limits. W2: inspect verifier reason and Mongo sample/ACK sequence before changing CLEAR rules.
- [ ] **R2 — One fix, one bounded replay.** Change only the failing component, deploy it, read back live state and run one scoped drill. Stop the drill at a documented timeout and restore normal service/mode. Capture actual cause if the hypothesis was wrong; revise the fix rather than running the whole sequence again.
- [ ] **R3 — Close or park the case.** Mark a case PASS only with its acceptance evidence; otherwise record FAILED with the exact failing stage and a next concrete action. Move to the next case only after a case passes or is explicitly parked as blocked. Do not call a successful workflow status a successful recovery.
- [ ] **R4 — Stage pacing contract.** Set a measured target for each demo step from observed latency; show a prepared incident immediately and run live detection concurrently. Treat Datadog evaluation time as real, not a promise of instant alert. The app UI must show `waiting_for_alert`, `investigating`, `verifying`, `recovered`/`pending_review` with timestamps so the audience never sees a silent wait.

### Shared work: make the sequence observable and smooth

- [ ] **S1 — Measure the bottleneck.** For one existing run per case, build a UTC timeline: scenario command/ACK → source sample or metric ingest → monitor ALERT → workflow start/end → action/guard → verifier response → app notification → monitor OK/CLEAR. Record elapsed seconds and missing links in `PROGRESS.md`; do not assume a workflow's `Success` means recovery.
- [ ] **S2 — Correlate one incident.** Carry `incident_id`, `scenario_run_id`, farm, node/device and command ID where applicable through app events, Mongo records, logs/spans, workflow inputs and app notification. Keep low-cardinality metrics grouped by farm/device/fault; put unique IDs in events/logs/spans rather than metric tags. A dashboard/incident view must link the same run, not unrelated examples.
- [ ] **S3 — Suppress duplicate actions.** Inspect monitor grouping and per-trigger rate limits, especially W6's ten-farm groups and W3's recovery transition. Use an idempotency key scoped to farm + resource + incident and one in-flight action per resource. Preserve each alert/finding while preventing repeated remediation and notification storms. Confirm that independent farms do not block one another.
- [ ] **S4 — Notification contract.** Publish `detected`, `investigating`, `action_taken`/`action_refused`, `verified_recovered` or `pending_review` as distinct states. Send a terminal recovery notice only after the verifier returns proof. If verification fails/times out, leave the incident open and show the reason. Ensure app bell/feed stores and displays the same incident and run IDs.
- [ ] **S5 — Demo pacing.** Prepare one previously recorded incident with clickable evidence for immediate presentation; run a new controlled incident in the background. Display live step status and measured elapsed time. Do not shorten production safety guards solely to fit the stage demo. Use an isolated demo scope if a shorter monitor evaluation window is needed; document that scope.
- [ ] **S6 — Verification gate.** For each case capture monitor ID/state history, workflow ID/run and step outputs, app incident/notification, Mongo sample/ledger and any device ACK/readback. Exercise both success and refusal/unknown branches. Mark Level 5 only when detect → evidence-based decision/action or refusal → post-action proof → terminal state all belong to one incident.

### Case-specific delivery and acceptance

- [ ] **W3 — actual automatic app recovery (first).** Diagnose why monitor 342585838 did not ALERT while `smiot.service` was inactive despite metric=0; check query grouping, evaluation window, missing-data semantics and metric timestamps. Ensure the published workflow waits for SSM command terminal result before calling the verifier, and the verifier requires HTTP health, healthy dependencies, Mongo telemetry newer than the action and monitor recovery. Repeat a bounded service-only outage with a prearranged rollback timer; do not manually start the app before the Datadog action. **Accept:** monitor ALERT precedes workflow, SSM guarded start actually starts the stopped service, verifier and terminal notice follow, monitor returns OK. Record the SSM command ID and timestamps. If the trigger does not arrive within the bounded window, restore the app and mark the attempt failed rather than implying automatic recovery.
- [ ] **W6 — detector-specific health and recovery.** Inspect why monitor 343029221 remained overall ALERT after the synthetic gauge returned to 1: read per-group state, evaluation window and the actual queried series. Separate detector evaluation heartbeat from app watchdog/input freshness and confirm a truly independent detector liveness signal if claiming detector-process failure. Align monitor/workflow tags and query with that producer. Remove grouped fan-out/rate-limit collisions through per-farm dedupe and scoped triggers. **Accept:** a controlled missing-evaluation case alerts only the target farm, one workflow classifies input-vs-detector, notification arrives, fresh evaluation is persisted, target monitor group returns OK and app incident is cleared by its verifier. Do not claim a detector restart from the metric-only drill.
- [ ] **W2 — stable-sample CLEAR.** Bind the flatline incident to the exact farm/node/boot_id and last pre-fault sequence. Require a mode-applied ACK, several post-fault samples with increasing sequence and valid variation, Mongo persistence after HOLD, and app verifier success before CLEAR. **Accept:** one incident shows ALERT → HOLD → normal command ACK → qualifying new samples → verifier CLEAR → monitor OK; a single new sample or MQTT command ACK alone cannot clear it.
- [x] W2 live harness prepared: persistent flatline mode, at least 420s hold, app-generated incident ID correlation across mode ACKs and following samples, normal reset in `finally`, monitor baseline/Alert/OK checks, and run-specific evidence JSON.
- [ ] W2 live harness has not been run; after backend/monitor review, execute it once and enrich its evidence with the exact Datadog workflow run and Mongo verifier/CLEAR result.
- [ ] **W1 — virtual PLC safe-state proof.** Bind trip, stop command, ACK/readback and `action_ledger` to the same farm/device/incident. Verify safe-mode latch, pump off and valve closed, and no subsequent ON command; require operator-approved reset after safe conditions. **Accept:** app and Datadog show the same incident and safe-state evidence; missing ACK/ledger leaves pending review. Label proof as virtual PLC behavior.
- [ ] **W4 — proved refusal.** Capture fresh backend health and Mongo sample/sequence in the same incident, then verify the refusal branch writes its reason and no SSM recovery command was issued for that run. **Accept:** monitor trigger → evidence → REFUSED_RESTART → no SSM command → continued fresh data → notification/closure or explicit pending state.
- [ ] **W5 — dependency discrimination.** Add separate, controlled Mongo write/read and MQTT publish/consume failure signals with a bounded synthetic or isolated test path; correlate each with app logs/traces and real dependency health. Route only a clear cause to its own guarded runbook; ambiguous evidence goes to review. **Accept:** two independent runs classify the right dependency, avoid broad restart, pass a post-action write/read or publish/consume check and show fresh Mongo telemetry before any recovered notice. A synthetic metric alone counts only as triage-path proof.

### Exit record

- [ ] Update `PROGRESS.md` after each case with changed files/config revision, UTC run IDs, measured stage latencies, evidence location, pass/fail of each acceptance condition and current service health. Do not mark a case complete from JSON validity, a successful workflow status, or a notification alone.

### Local parallel rehearsal harness — W2 + W6

- [x] Added `scripts/drill_parallel_w2_w6.ps1` to rehearse two isolated orchestration lanes concurrently using local synthetic records only. It assigns distinct local farm scopes, `incident_id` and `scenario_run_id` values, enforces a timeout, cleans up PowerShell jobs in `finally`, and writes `outputs/drill_parallel_w2_w6_<utc>.json`.
- [x] Script syntax parsed successfully. Running it would only emit fixture events and local evidence; it does not exercise a live simulator, AWS, Datadog, app, MQTT or MongoDB. No live W2/W6 acceptance is inferred from this harness.
- [ ] If the local harness is run, inspect its JSON evidence for both lane IDs and cleanup; before any live replay, complete R0/R1 baseline and collision/rate-limit review, then obtain case-specific authorization and keep each live fault isolated.

## Whole-system smooth-drill readiness (Datadog → app → AWS/EC2 → MongoDB/MQTT → S3)

This is a cross-layer checklist, not a prerequisite to fixing W3/W6/W2. Inspect the live path and actual S3 usage; S3 image/evidence work must not hold up monitor or verifier repairs. Implement only the layer implicated by the current failed gate, then replay that gate.

### Execution cards — exact order and evidence

| Card | Inspect first | Change only if finding confirms it | Completion evidence |
|---|---|---|---|
| 01 — Baseline | Local commit/diff, deployed file hashes, Datadog US1 org and live monitor/workflow revision, Terraform state/plan, AWS account and region | Reconcile drift/import only for resources actually used by W3/W6/W2 | One inventory table mapping local file → live resource → revision/hash; no secret values |
| 02 — W3 metric/monitor | `342585838`: raw `systemd.unit.active` points before/while/after app stop, host/service tags, last evaluation, group transition, no-data policy | Edit `deploy/datadog/terraform_monitors/monitors.tf` only when query/window/tags are disproven by raw data; avoid changing a healthy producer | At least one controlled inactive interval yields ALERT while app is still inactive; record detection latency |
| 03 — W3 AWS action | Workflow `373ed0c0-4509-4fcd-a067-f54f0becc00e`, AWS connection, SSM document `SMIOT-GuardedStartApp`, role permissions and SSM command history | Fix only the missing permission, workflow edge or wait condition found; keep target `smiot.service` | Same incident: ALERT precedes SendCommand; SSM terminal success starts previously inactive service; no manual start before action |
| 04 — W3 verifier/notice | Recovery-verification endpoint, `service/incident_lifecycle.py`, `scripts/aws/smiot-recover-guarded.sh`, app notification | Correct exact command/instance matching and ordering; send terminal notice after verifier; enforce timeout → pending_review | HTTP healthy, Mongo/MQTT healthy, post-action Mongo sample, verifier true, final app notice and monitor OK in one run |
| 05 — W6 source | `service/detector_heartbeat.py`, detector process boundary, real metric points and tags | If heartbeat is app-owned, either split detector into a separately supervised unit or describe it as evaluation freshness rather than independent process liveness | Detector/evaluation stop is distinguishable from missing input; new evaluation is persisted after return |
| 06 — W6 monitor/fan-out | Monitor `343029221` per-farm groups, query/evaluation window, all producers for same tags, grouped workflow runs and rate-limit errors | Align monitor to intended series; scope trigger to target group; dedupe action by farm/resource/incident | One target farm alerts and later returns OK; one action/notification for that incident; other farms unaffected |
| 07 — W2 publisher/ingest | `service/mqtt.py`, `scripts/wokwi_datadog_bridge.py`, `service/telemetry_health.py`; requested/applied mode ACK, boot_id/sequence, Mongo sample timestamps | Add missing applied ACK or sequence provenance; correct stale/flatline calculation only if observed mismatch | Applied ACK plus first matching fault sample and recovery samples are visible for one node/run |
| 08 — W2 CLEAR | `service/incident_lifecycle.py`, `scripts/verify_and_clear_demo_safe_mode.py`, Mongo incident and action ledger | Require configured count of post-HOLD persisted samples with increasing sequence and valid variation; reject stale/other-node samples | Verifier reason shows pass/fail; only valid sequence clears HOLD; monitor returns OK and app reflects CLEAR |
| 09 — W1/W4/W5 | W1 PLC readback/ACK/ledger; W4 service-health sample plus SSM command history; W5 Mongo/MQTT probe outputs | Change only missing correlation, unsafe transition or wrong branch; keep faults independent | W1 safe state; W4 proved refusal with no SSM; W5 separate Mongo/MQTT classification and healthy probes, each same-incident |
| 10 — Home and Incident UI | `pages/home.py`, `pages/incident.py`, `service/incident_blackbox.py`, `service/datadog_notifications.py`; browser behavior on refresh and farm selection | Fix navigation/state race, stale labels, timeline filtering and notification overwrite | Click any farm without reload; one incident timeline contains only matching records; final state equals verifier and persists after reload |
| 11 — EC2 deployment | Source package manifest, systemd units, rollback archive/snapshot, disk and service health | Deploy only changed files, restart only affected service, restore package on failed health | Deployed hashes match reviewed files; app/Mongo/MQTT active, HTTP 200, telemetry fresh, rollback location recorded |
| 12 — S3 scope | Search live code/config and AWS bucket inventory for image/evidence use | If active, correct private IAM/encryption/lifecycle and run-specific evidence prefix; if absent, mark N/A | Verified object metadata/readback or explicit N/A with reason; no credentials/raw secrets |

**Per-card rule:** record the finding and hypothesis before modifying anything; use one small change and one bounded replay. Save monitor/workflow ID, Terraform plan/revision, SSM command ID, incident/run ID, UTC timestamps, app/Mongo/ACK evidence and measured delays in `ACTIVITY_LOG.md` and `PROGRESS.md`. A failed replay is an open item with the exact failed stage, not an invitation to restart the entire W1–W6 sequence.

### A. Datadog configuration and event flow

- [ ] Confirm correct US1 organization, API site, monitor/workflow IDs, published revisions and Terraform state; export a sanitized pre-change snapshot.
- [ ] Audit every W1–W6 monitor query against the exact metric producer name, tags, units, aggregation, evaluation window, no-data behavior and farm grouping. Resolve No Data, stale data, wrong scope and alert/OK delays.
- [ ] Read back each workflow graph and associations. Ensure trigger payload preserves farm, incident/run/device IDs; actions are idempotent; retries/timeouts are bounded; failure paths reach pending-review notification rather than false success.
- [ ] Fix W6 grouped-trigger fan-out and W3 recovery-transition rate limits. Prove one incident yields one action while separate farms remain independent.
- [ ] Keep Terraform authoritative for supported resources. Run fmt/validate/plan, inspect destructive or replacement changes, apply only the intended diff, then plan again and read back live configuration. Record API/CLI exceptions where provider support is incomplete.
- [ ] Measure monitor evaluation/notification latency. If stage pacing needs a faster signal, create a separately scoped demo monitor/config through Terraform; do not silently weaken operational monitors.

### B. Application/backend and UI

- [ ] Define one incident envelope and lifecycle: detected → investigating → action/refusal → verifying → recovered or pending_review. Enforce legal transitions and never label a workflow as recovered solely from its Success status.
- [ ] Propagate incident ID, scenario run ID, farm, device/node and command ID through API responses, Mongo incident/action records, structured logs, APM spans, workflow inputs and app notifications. Keep unique IDs out of metric tags to control cardinality.
- [ ] Make notification delivery idempotent and update the existing incident feed item by ID; show progress separately from terminal status. Include a short reason and evidence links.
- [ ] Use deadlines and cancellation for verification; surface timeout/reason to UI. Add per-resource concurrency/deduplication so overlapping incidents do not race, while unrelated farms can proceed.
- [ ] W3 verifier must check exact SSM command/instance/service, HTTP health, Mongo/MQTT dependencies and a telemetry record newer than the action. W2 verifier requires ACK plus a configured run of increasing, varying samples persisted to Mongo. W1 requires matching PLC virtual ACK/readback and ledger. W4 requires explicit refusal and proof no SSM command was sent. W5 requires dependency-specific probes. W6 requires fresh evaluation and persisted detector result.
- [ ] Validate the operator path: incident opens from notification, shows timeline/evidence, handles refresh/reconnect, and cannot clear while verification is pending.

### B2. Frontend/operator screens — concrete changes

- [ ] `pages/home.py`: show all ten farms from the existing Mongo-backed overview. Give each farm one combined health state derived from fresh sensor, device, dependency and open-incident signals; show `unknown/stale` when data is missing. Clicking a farm must open its detail immediately without requiring page reload; preserve selection on refresh/reconnect.
- [ ] `pages/incident.py`: display the selected incident's ordered timeline: source sample/command ACK, Datadog ALERT, workflow decision/action, verifier result, monitor OK and app CLEAR. Every step shows UTC time, status and a link/ID for its evidence. Missing evidence remains visibly pending; never fill the timeline from a different run.
- [ ] `service/incident_blackbox.py` and page consumer: query only records matching `incident_id` plus farm/device/run scope. Add a bounded time range and ordering so an old seeded event cannot be mistaken for the current drill.
- [ ] `service/datadog_notifications.py` and app bell: update one existing incident notification through lifecycle states instead of adding contradictory success messages. Show the verifier reason for `pending_review`; a workflow `Success` alone must not display “recovered”.
- [ ] `/plc` scenario control and its backend endpoint: show `requested → publisher applied ACK → first matching sample → alert → recovery`, plus a Stop/Reset action scoped to that run. Disable duplicate Start for the same farm/resource while a run is active; show timeout and reset status.
- [ ] Confirm responsive ten-farm overview and incident timeline on desktop presentation width and phone width; verify reload/reconnect does not lose the selected farm or incident. Capture only the screens needed for the operator demo.

### B3. Backend-to-frontend contract

- [ ] Define a response schema for portfolio farm state and incident timeline with `incident_id`, `scenario_run_id`, `farm_id`, `device_id`, `state`, `last_event_at`, `freshness`, `evidence_links` and `reason`. Return explicit `unknown` when source evidence is absent.
- [ ] Read incident status from the same persisted state machine used by the verifier; do not infer CLEAR in the UI from monitor OK, an HTTP 200, or the last notification text.
- [ ] Add/update backend indexes or bounded queries only after measuring the current home/incident query path; keep the ten-farm refresh responsive without scanning full telemetry history.

### C. AWS and EC2 operations

- [ ] With AWS CLI, verify active identity/account and `ap-southeast-2` before every write; inspect EC2 state, SSM managed-instance status, command history and IAM role permissions using least privilege. Never display credentials or secret values.
- [ ] Verify Datadog AWS connection assume-role and the exact permissions used by the workflow (send command, read command result, describe target as needed). Test the role connection and workflow action separately; connection success alone is not proof of SSM permissions.
- [ ] Check systemd units and dependencies (`smiot`, MongoDB, Mosquitto, bridge), disk/memory, app health, logs and telemetry freshness. Preserve a rollback path and bounded recovery timer before a service-stop drill.
- [ ] Limit W3 automation to `smiot.service`; prohibit EC2 reboot and MongoDB/MQTT restart. Capture command ID, terminal status and verifier result. Do not stop shared dependencies for W5; use isolated fault injection or synthetic health signals with explicit labels.
- [ ] Apply AWS changes through reviewed IaC/CLI, then read back actual IAM/SSM/resource state. No unrelated account, organization or network changes as part of these drills.

### Parallel W2/W6 test gate

- [x] Local rehearsal harness created and executed with independent farm/resource scopes, incident IDs, scenario IDs, timeout and cleanup.
- [ ] Before live parallel execution, verify W6 monitor/workflow query is scoped to the triggering farm/group; a detector-only global query can mask a failing farm with a healthy farm.
- [ ] Before live parallel execution, prove per-run lock/idempotency and cleanup readback for both lanes; a local fixture is not runtime evidence.

### D. MongoDB

- [ ] Verify the live database target without revealing URI/credentials; confirm expected version/topology, collections, indexes, validators and time-series schema via read-only checks.
- [ ] Ensure telemetry, `operational_incidents`, `action_ledger` and notification/event records share correlation fields and UTC timestamps. Add indexes only after checking query patterns and existing index state.
- [ ] Confirm idempotent incident/action writes and atomicity where needed; duplicate workflow delivery must not create repeated actions or contradictory CLEAR records.
- [ ] W2 acceptance: prove sequence/freshness/variation in stored samples after HOLD. W3: prove a new telemetry document after service recovery. W5: use bounded read/write probes and verify persisted result. W6: persist the evaluation outcome and timestamp. Capture sanitized query/result evidence.
- [ ] Check Mongo latency/errors during each drill and confirm no synthetic fault was mistaken for a real database outage.

### E. MQTT, virtual devices and actuator boundary

- [ ] Inventory each simulator/publisher, farm/device identity, cadence, heartbeat, `boot_id`, sequence number, command topic, ACK topic and stop behavior. Verify data reaches broker, app and Mongo in the expected order.
- [ ] Make scenario start/stop idempotent and run-scoped; require publisher ACK that the requested mode was applied, not just broker publish success. Stop/reset the scenario in a `finally`/timeout path.
- [ ] Keep local PLC interlocks authoritative for immediate safe action. Datadog may investigate and coordinate recovery but must not replace the safety interlock. No physical output is claimed from virtual readback.
- [ ] Exercise overlapping faults only after single-fault gates pass; maintain separate incident IDs and alerts, and verify one fault does not hide or clear another.

### F. S3 and evidence artifacts

- [ ] Inspect code and AWS configuration to determine whether S3 is currently used for images, exports, backups or evidence. Record bucket purpose, region, object key scheme and lifecycle; if S3 is not in the active path, mark it “not applicable” rather than adding an unnecessary dependency.
- [ ] If S3 is active: verify private access, least-privilege role, encryption, versioning/lifecycle and upload/download health with AWS CLI metadata checks; do not expose public objects or log signed URLs/secrets.
- [ ] Store sanitized drill evidence under a run-specific prefix containing date/incident/run ID; include monitor/workflow JSON snapshots, timing summary and screenshots/log extracts with secret redaction. Link object references from the progress record/app incident where appropriate.
- [ ] Verify an uploaded evidence object can be read by the intended reviewer role and that retention matches submission needs. Do not store `.env`, API keys, Mongo URIs or raw credentials in S3.

### G. Whole-system rehearsal gates

- [ ] **Gate 1 — preflight:** correct account/org/region, services healthy, metrics arriving, app and Mongo reachable, simulator ACKs, no stale open drill incident, rollback and evidence capture ready.
- [ ] **Gate 2 — single case:** inject exactly one bounded fault, follow the same incident through Datadog/backend/AWS or device/Mongo/app, verify terminal state, restore normal mode and confirm no duplicate action.
- [ ] **Gate 3 — stability:** observe at least one full monitor evaluation after recovery; confirm target group OK, fresh telemetry persisted, notification final state correct and unrelated farms remain healthy.
- [ ] **Gate 4 — demo ready:** rehearse the operator clicks using a saved incident; measure live path duration; pre-open evidence views; keep live injection optional if alert delay exceeds the presentation window.
- [ ] Record per gate pass/fail and evidence in `PROGRESS.md`. A case is complete only when its single-incident chain and stability gate pass; a drill that needed manual recovery is recorded as partial/fail for automatic remediation.

## W6 farm-scoped detector fault mechanism — 2026-11-11

- [x] Implement `demo_detector_fault` MQTT control with `synthetic=true` guard, farm scope, command ID and applied ACK.
- [x] Deploy the mechanism to EC2 without restarting shared dependencies; verify `/healthz` and service remain healthy.
- [x] Verify `stalled → ACK → normal → ACK` on `greenhouse_b`.
- [ ] Run the full Alert→workflow→recovery path by holding the scoped fault beyond the W6 monitor's five-minute evaluation window; then restore and verify the farm group and app evidence.
- [x] Live run completed: `greenhouse_b` fault held 330 seconds and automatically restored; metric transition 0→1 confirmed.
- [ ] Wait for the monitor recovery window and verify the W6 workflow run and terminal state; do not mark Level 5 from metric recovery alone.
- [x] W6 workflow fan-out fix: changed monitor trigger rate limit from `1/300s` to `10/300s`, republished JSON, and read back the published workflow.
- [ ] Re-run a controlled multi-farm recovery if a smooth fan-out proof is required; check for zero `Rate limit exceeded` instances and idempotent app notifications.

## W4 + W1 parallel live result — 2026-11-11

- [x] Ran W4 `D2` on `greenhouse_c/node1` and W1 `A2` on `greenhouse_d/node2` concurrently.
- [x] Confirmed scenario ACK, correlated sample, MongoDB persistence ACK and clean stop for both; W1 local safety interlock verified pump OFF and valve closed.
- [ ] Add Datadog telemetry for W1 safety-trip metric and align W4 status-mismatch monitor groups with all 10 farms before claiming their Alert→workflow chains.
- [x] Added W4 D2 status-mismatch metric emission with farm/node scope and reset-on-stop.
- [x] Enabled EC2 DogStatsD custom metrics and redeployed the backend patch.
- [x] Replayed W4/W1 in parallel; W4 and W1 monitors now reach `Alert` (W1 no longer `No Data`).
- [ ] Read workflow instances for W4/W1, then restore/verify monitor groups `OK` and record app notification status.
- [x] Read W4/W1 workflow instances; both latest runs succeeded.
- [x] Sent stop/normal, waited for monitor windows, and confirmed W4 and W1 monitors `OK`.
- [x] Set W1 missing-data policy to `resolve` so an expired safety-trip count is treated as recovered, not `No Data`.
- [x] W4 local refusal notification contract patched with explicit decision/action/no-infra-action metadata; tests pass.
- [x] W9 local late-ACK correlation patched with command/farm matching and regression test; tests pass.
- [ ] Publish/deploy W4 and W9 patches, then run bounded live drills; W5/W6 gaps remain open.
- [x] Added read-only W5 MongoDB/MQTT before/after probe script; no dependency stop or synthetic-only claim.
- [x] Updated local W6 workflow queries to farm-scoped heartbeat series; JSON validation passed.
- [ ] Review W6 grouped-column handling before publish; deploy W5 probe and run isolated Mongo/MQTT cases with post-action checks.

- [x] W9 bounded synthetic drill: deployed emitter, emitted actuator no-ACK signal with farm/actuator scope, verified monitor recovery and cleanup.
- [x] W5 bounded dependency drills: emitted MongoDB-down and MQTT-down independently, read monitor/workflow outcomes, restored both dependencies to normal and confirmed both monitors `OK`.
- [ ] W9 optional final evidence gate: capture a newly triggered monitor-linked workflow instance in the same timestamp window; keep current safe no-retry behavior.
- [x] W9 final replay completed: Alert → workflow Success → normal → monitor OK.
- [x] W5 runtime evidence JSON saved and both dependency monitors confirmed OK.
- [x] W6 read-only recheck: monitor `343029221` and all ten farm heartbeat groups are healthy; recent runs were inspected.
- [ ] Reconcile remaining W6 `Running`/queued instances and enforce one in-flight recovery per farm; then accept only a bounded target-farm run with fresh evidence and unaffected peer farms.
- [x] W7/W8 advisory metrics deployed; dedicated farm/node monitors created and linked to the existing workflows.
- [x] W7 and W8 bounded synthetic Alert → workflow Success → normal → OK drills completed; no actuator or schedule action was allowed.
- [x] W7/W8 runtime evidence saved to `outputs/evidence/w7_w8_advisory_drills_runtime.json`.
- [x] W10 emitter deployed; failure/normal signals verified monitor Alert → OK.
- [x] W10 monitor query separated provider-error series and applied through Terraform.
- [x] W10 runtime evidence saved to `outputs/evidence/w10_ai_safety_drill_runtime.json`.
- [!] W10 fresh monitor-triggered workflow attempt was Datadog rate-limited; do not claim a new Success run until cooldown allows one.
- [x] W2 backend verifier and runner fixes deployed; correlated flatline ACK/first sample verified.
- [!] W2 live acceptance failed: monitor stayed OK and normal reset produced no following sample; evidence recorded in `outputs/evidence/w2_live_drill_20261111_failed.json`.
- [ ] Investigate W2 metric delivery/monitor group routing and publisher sample cadence before rerunning; do not claim Level 5.
- [x] W2 log root cause identified: 420s hold < 10-sample detector requirement; normal ACK timeout 45s < 60s publisher cadence.
- [ ] Rerun W2 with 720–900s hold and normal-sample timeout >= 90s; capture monitor Alert, workflow run and CLEAR evidence.
- [x] W2 11-minute replay produced flatline metric `1`, monitor Alert and workflow Success; normal sample returned with matching incident ID.
- [x] After the recovery window, monitor `342585819` returned `OK`; flatline remained `0` and soil humidity returned to the normal range.
- [x] W2 pre-drill fixes: use actual node cadence for watchdog lookback and hold the scenario long enough for 10 stable samples + monitor evaluation; guaranteed STOP cleanup.
- [x] W2 recovery validator now accepts the cadence-derived sample minimum only when the verifier also proves the required stable span, freshness, data variation and correlated SAFE CLEAR ACK.
- [ ] Run W2 live after preflight; require same-case Alert → workflow → verifier CLEAR with fresh varying Mongo samples and final monitor OK.

## W9 late-ACK harness — 2026-11-12

- [x] Add a synthetic-only authenticated late-ACK drill route with strict farm/actuator scope and timeout.
- [x] Deploy route, simulator ACK suppression, and ledger matching to EC2; verify app health.
- [x] Run one live round trip; verify unacknowledged -> acknowledged for exact command/farm, target OFF, Mongo ledger and Datadog metrics.
- [x] Read monitor and workflow state; save evidence.
- [!] Monitor `342734743` alerted and W9 workflow run `f76b3ca8-c023-4d40-b3a2-76d63f91b5cc` was rate-limited. Re-run workflow-only acceptance after Datadog trigger rate limit resets; do not repeat actuator injection until monitor returns to OK.

### W9 execution process (recorded)

1. Check the app is healthy and ensure no W9 drill is already running.
2. Call the admin-only, synthetic-only late-ACK endpoint on EC2.
3. Create a bounded `SET_OUTPUTS=OFF` command for `greenhouse_j`; never target a physical actuator.
4. Suppress only the virtual PLC's automatic ACK and keep the safe output OFF.
5. Wait for the timeout worker to persist `unacknowledged` and emit `smiot.actuator.command_unacknowledged`.
6. Publish one delayed ACK containing the exact `command_id` and `farm_key`.
7. Accept only an ACK with matching command, farm, actuator and OFF readback; persist `late_ack=true` and ledger state `acknowledged`.
8. Read Datadog monitor `342734743` and workflow `47e95b24-db40-4cd5-b667-5b90e170b667` without repeating the injection. A rate-limited workflow run is not accepted as Level 5 evidence.
9. Wait for the five-minute monitor window to recover to OK, then perform the workflow-only acceptance run and record the new run ID.

Evidence for the completed application/MongoDB round trip: `outputs/evidence/w9_late_ack_live_20261111.json`.


## UI/UX "Datadog dẫn đầu" (12/11/2026, chỉ sửa local, chưa triển khai EC2)

- [x] P0: gỡ 15 điểm khởi tạo tự đặt ở biểu đồ Biến tần; trục X HH:mm:ss; trạng thái rỗng "Chưa có bản tin biến tần ảo kể từ khi mở trang"; mốc cập nhật qua định dạng giờ Việt Nam.
- [x] P0: một múi giờ cố định UTC+7 cho nhãn giờ (fmt_time, _fmt, _vi_time) và trục biểu đồ ECharts (useUTC, cộng 7 giờ).
- [x] P0: "Monitor OK" luôn kèm mốc "lúc xác minh HH:MM (bản ghi MongoDB)"; trạng thái hiện tại của monitor ghi riêng, chip `stale` khi monitor không còn; thẻ "Xem monitor" tắt, thêm thẻ monitor hiện hành của ca (cấu hình ca).
- [x] P0: cross_check_verdict hạ "Đã phục hồi" xuống "Chưa xác minh" khi mọi mẫu sau CLEAR bằng giá trị lỗi; thêm câu giải thích HOLD chỉ cần ACK và hồ sơ thiếu lệnh HOLD; bảng mẫu đổi tên "5 mẫu đầu tiên sau mốc CLEAR (MongoDB)".
- [x] P0: danh sách không ẩn hồ sơ: khối Đang mở, tab Đủ bằng chứng / Thiếu bước / Tất cả đã đóng, phân trang 25 dòng, kiểm đủ bước chạy nền sau lần hiển thị đầu.
- [x] P1: service/datadog_reader.py: read_monitor_overview (một GET, cache 30 giây), snapshot có query, ngưỡng, đổi trạng thái, sự kiện monitor (Events v2), log khớp mã (Logs list v2), mỗi phần có lỗi riêng, ngân sách 12 giây, reason keys_missing; thiếu monitor_id vẫn đọc metric và log. Chỉ GET.
- [x] P1: /incident: khối "Datadog đang thấy gì" (đếm Alert/Warn/No Data/OK, 10 ô ca có chip trạng thái hiện tại, monitor SMIOT ngoài cấu hình ca), khối Đang mở, khối Hồ sơ đã đóng có cột "Phát hiện bởi" và 3 chấm pha.
- [x] P1: /incident/<id>: dải 3 pha Phát hiện / Điều tra / Phản ứng, mỗi pha viền theo vai (tím Datadog, xanh MongoDB); biểu đồ metric Datadog có vạch mốc và ngưỡng; biểu đồ chồng độ ẩm đất MongoDB và Datadog; lưới link Datadog đúng một lần; nhãn tiếng Việt cho mã cách xử lý.
- [x] P1: theme.py token --sm-dd, lớp dd-*/sm-phase*/sm-code; ui_kit.py phase_block, dd_state, dd_state_panel; bỏ màu #632CA6 viết cứng trong pages/.
- [x] P2 một phần: bảng chuyển thẻ dưới 768 px (_table stack), stat chữ dài xuống dòng, chữ chú thích tối thiểu 12 px cho .sm-source.
- [ ] Chưa làm: /chart có bảng monitor trực tiếp, hàng trạng thái Datadog và gộp "Cần người duyệt" trên Home, mục "Thêm" trên thanh điều hướng mobile, tab Node ở /data, các sửa nhỏ plc/schedule/devices/permission (ngoài phạm vi file được giao).
- [ ] Chưa làm: truy vấn MongoDB chỉ đọc để xác nhận giả thuyết M4 (mẫu 2.4 thuộc hồ sơ nào); không có chuỗi kết nối MongoDB trong phiên này.
- [x] Six-step web evidence pack: seeded one incident per W1–W10 with linked monitor/workflow/run reference, telemetry context, decision, ACK ledger and verified recovery; validated all ten with `case_file_state` returning six `done` states. Synthetic demo evidence is labelled and is not a replacement for fresh live Datadog runs.

## Hiển thị bằng chứng Datadog đúng mã sự cố — 2026-11-12

- [x] Phân biệt bằng chứng liên kết chính xác với bối cảnh cùng khung giờ: trace chỉ được đếm khi `trace_id` nằm trong hồ sơ của đúng incident; log chỉ được đếm khi Logs API trả về đúng `incident_id`.
- [x] Đổi nhãn Điều tra thành “Log khớp đúng mã sự cố”, “Trace gắn đúng mã sự cố” và “Workflow ghi trong hồ sơ”, tránh hiểu nhầm trace cùng giờ hoặc seed tổng hợp là bằng chứng live.
- [x] Khi chưa có log/trace liên kết, giao diện hiển thị số 0 và giải thích rõ “chưa có bằng chứng liên kết”, không tự ghép dữ liệu Datadog cùng khung giờ.
- [x] Chuẩn hóa `node1`/`node2` về số ở bản sao dùng để dựng timeline, không sửa dữ liệu MongoDB và không còn lỗi `invalid literal for int()` khi mở hồ sơ.
- [ ] Chưa tạo log/trace Datadog mới cho bộ hồ sơ synthetic; muốn có bằng chứng live cần một lượt chạy workflow/ứng dụng có `incident_id` được ghi vào log và span.
- [x] Scenario evidence path now resolves the exact `scenario_run_id + farm_key` to `incident_id` before writing the Datadog-correlated observation log/span; sensor payloads remain unchanged.
- [x] Run one fresh scenario after deployment and verify exact log/span search plus the incident detail page.
- [x] Chạy lại một ca riêng sau deploy với `scenario_run_id=cc797f61-01b9-4b63-9843-a2abbc85f2fc` và incident `INC-SMIOT-SCENARIO-960EFBDDBF4881C4`.
- [x] Bổ sung `/opt/smiot/logs/system.log` và `error.log` vào Datadog Agent; sau restart Agent, ca mới `scenario_run_id=a307f8a0-8da2-4838-b983-96a7cfdbc6f4` tạo incident `INC-SMIOT-SCENARIO-92C5A925F941F621`, Datadog API trả 2 log và 1 span khớp exact ID.
- [x] Chạy lại W1/W2/W7/W8 bằng scenario runner với incident riêng; đã có hồ sơ MongoDB và log Datadog exact ID. W1 có log nhưng chưa có span; W2/W7/W8 có cả log và span.
- [ ] W3/W5/W6/W9/W10: runner generic tạo được run và sample nhưng không nhận observation ACK MongoDB; phải dùng runner chuyên biệt của từng workflow để tạo incident correlation live, không lấy run generic này làm bằng chứng hoàn tất.
- [x] W3/W5: thêm `scripts/run_correlated_w3_w5.py`. Runner control-plane tạo ACK bắt đầu → incident MongoDB → bằng chứng dependency → quyết định → action ledger HOLD/verified → observation → recovery CLEAR; Datadog log/span mang cùng `incident_id`. Không dừng app/MongoDB/MQTT và không điều khiển thiết bị.
- [x] W3/W5: deploy runner lên EC2 và chạy từng ca; MongoDB readback `recovered` cho `61B502B2FD022B9C` và `B1797FE944C944F0`; log/span được phát với cùng incident ID. Trang hồ sơ có thể mở theo ID.
- [x] W10: thêm `scripts/run_w10_correlated.py` cho provider failure → HOLD/safe fallback → quyết định MongoDB → CLEAR sau provider recovery, với một `incident_id`/`scenario_run_id` xuyên suốt; runner chỉ mô phỏng control-plane và không gọi Gemini hay actuator thật.
- [ ] W10: MongoDB live readback `recovered` và Logs API trả 2 log exact ID cho lượt `INC-SMIOT-W10-20261112T074904-7243BB99`; APM span ngắn hạn chưa đọc lại được, nên vẫn ghi một phần correlation.

## W6/W9 specialized correlation (2026-11-12)

- [x] W6 detector injector opens one farm-scoped incident and returns its incident_id in stalled/normal ACKs.
- [x] W6 recovery closes only after a fresh detector evaluation, not merely after clearing the demo flag.
- [x] W9 late-ACK injector registers the pending command with the same incident ID; timeout and matching late ACK are correlated.
- [x] Added isolated runners: scripts/run_w6_correlated_drill.ps1 and scripts/run_w9_correlated_drill.ps1.
- [x] Focused tests: tests/test_w6_w9_correlation.py; compile checks passed.
- [x] Deploy and execute both specialized drills on EC2; W6 `INC-SMIOT-W6-DRILL-735089BF22` recovered after fresh evaluation; W9 latest `INC-SMIOT-W9-DRILL-0AAF284684` recovered after timeout → matching late ACK.

## Correlation rollout — 2026-11-12 (latest)

- [x] Deployed specialized correlation code and runners to EC2; `smiot.service=active`, `/healthz=200`.
- [x] W3 correlated run: `INC-SMIOT-SCENARIO-61B502B2FD022B9C`, recovered; W5: `INC-SMIOT-SCENARIO-B1797FE944C944F0`, recovered.
- [x] W6 live farm-scoped drill: `INC-SMIOT-W6-DRILL-735089BF22`, stalled → fresh detector evaluation → normal, MongoDB status `recovered`.
- [x] W10 correlated run: `INC-SMIOT-W10-20261112T074904-7243BB99`, recovered with safe fallback; Logs API exact-ID evidence present.
- [ ] W9 rerun produced timeout and matching late-ACK timeline, but final MongoDB status still reads `recovering`; keep W9 open until the terminal-state patch is deployed and a new run returns `recovered`.

## Scenario verification stuck state — 2026-11-12

- [x] Fixed scenario stop verification: a stopped ACK now requires a fresh telemetry sample after the exact stop time and matching farm/node before the incident becomes `recovered`.
- [x] Backfilled active scenario incidents with post-stop telemetry evidence; 17 records verified and closed. Only 2 non-scenario active incidents remain, both greenhouse_j.
- [x] Deployed `scenario_evidence.py`; service active and `/healthz=200`.

## Velxio migration safety (2026-11-12)

- [x] Added isolated `velxio-bridge.service`; it does not replace or disable `wokwi-bridge.service`.
- [x] Added root-only install/rollback scripts with `SMIOT_VELXIO_ENABLE=false` by default, channel validation, health check, and rollback.
- [ ] Upload Velxio bridge source and install on EC2 after bridge contract tests and UI checks pass.
- [ ] Keep Wokwi as rollback until Velxio sensor → local MQTT → MongoDB → UI and command → ACK are verified end to end.
- [x] Normalized the deployment variable names: systemd uses `VELXIO_CHANNEL`; installer writes both `VELXIO_CHANNEL` and `SMIOT_VELXIO_CHANNEL` for compatibility.
- [ ] Velxio Node1 is telemetry-only and has no ACK path by design; Node2 ACK exists only for actuator commands. Profile-switch ACKs are not emitted by the supplied Velxio sketches, so they cannot be shown as app profile ACKs until firmware is extended or profile switching is kept app-local.
# Velxio bridge integration (2026-11-12)

## Velxio source handoff for devices 1–3 (2026-11-13)

- [x] Keep the EC2 virtual publisher and Velxio from writing duplicate samples for the same `farm_key` + device.
- [x] Apply source ownership independently to Node 1 (`node1`), Node 2 (`node2`), and the third Velxio project, the flow meter (`flow`).
- [x] Refresh ownership only when a valid Velxio sensor message arrives; the lease defaults to 35 seconds (minimum 20 seconds).
- [x] Let EC2 resume the affected stream automatically after Velxio stops sending; other devices and farms continue normally.
- [x] Deploy the updated backend and bridge to EC2 with a remote backup; syntax-compile both files, restart the required services, and confirm both active plus `/healthz` 200.
- [ ] Read back actual Velxio sensor samples for Node 2 and the flow meter, then confirm EC2 resumes each stream after the lease expires.
- [ ] Confirm the third Velxio project publishes the bridge's `sensor/flow` topic; it maps to the existing flow schema, not a new MongoDB `node3` schema.

## Velxio Node 2 pump sketch repair (2026-11-13)

- [x] Apply ArduinoJson 7 API updates and fix PubSubClient payload type in the Node 2 sketch.
- [x] Replace unsupported buzzer `tone()` use with ESP32 LEDC support for Arduino core 2.x and 3.x.
- [x] Keep Wi-Fi/MQTT reconnects nonblocking so the command loop stays responsive.
- [x] Add the complete external dependencies (`ArduinoJson`, `PubSubClient`) to the Velxio project; WiFi and `esp_arduino_version.h` are provided by the ESP32 Arduino core.
- [x] Save the updated sketch to the existing public Velxio Node 2 project and compile it successfully in Velxio and locally for ESP32 DevKit V1.
- [x] Run the simulator and confirm MQTT command → virtual output response → ACK against the active project channel; return outputs to OFF.

- [x] Add additive `scripts/velxio_mqtt_bridge.py`; keep the existing Wokwi bridge unchanged.
- [x] Normalize Velxio node/flow telemetry to `farm/sensor` with `farm_key`, sequence/boot provenance and `source=velxio_synthetic`.
- [x] Preserve `command_id`, `incident_id`, and `scenario_run_id` through command, status and ACK paths.
- [x] Add allowlist support for `velxio_synthetic` in provenance, health and Datadog metric tagging.
- [x] Add contract tests for node, flow, command/ACK correlation and farm isolation.
- [ ] Configure credentials/channel and run the bridge against the chosen MQTT broker.
- [ ] Deploy to EC2 only after an explicit integration test and security review.
- [x] Deploy bridge/UI/provenance to EC2 with remote rollback backup; verify `/healthz=200`, `/devices=200`, `/=200`.
- [x] Install the isolated Velxio systemd unit disabled; keep Wokwi active and untouched.
- [ ] Run an intentional Velxio sensor → local MQTT → MongoDB → UI and command → ACK end-to-end test before enabling the bridge.
- [x] Enable Velxio bridge and complete bounded sensor relay + command/ACK contract test on EC2.
- [ ] When presenting, run the actual three Velxio simulator tabs against the configured public channel; keep Wokwi available as rollback.
- [x] Create a Public Velxio circuit project and embed the real project view in `/devices`; add fullscreen fallback link and verify deployed route.
- [x] Create Public Velxio project for node2/pump and add it as a selectable circuit tab with LED/buzzer view.
- [x] Fix Velxio iframe stuck on Loading/blank space by separating static circuit iframes from the refreshable telemetry panel; run local tests and redeploy.
- [x] Remove the unused white right pane inside Velxio embed while preserving the real circuit canvas and fullscreen fallback.
- [ ] Create Public Velxio project for node3/flow if the demo needs a separate flow-monitor board visible.
- [x] Fix Velxio Node 1 DHT22 GPIO initialization with the Adafruit DHT library, preserving GPIO4 wiring and omitting invalid (NaN) readings rather than publishing substitutes.
- [x] Make Wi-Fi/MQTT reconnects nonblocking, set PubSubClient buffer to 512 bytes, and verify live DHT22 readings plus MQTT publishes every 10 seconds.
- [x] Read back the latest `greenhouse_j` MongoDB telemetry (`source=velxio_synthetic`, `air_temp=29.0`, `air_hum=72.0`) and save the live sketch/circuit snapshot in `velxio/node1_environment/`.

## Velxio 3-node app integration — 2026-11-13

- [x] Node 1 simulator is running on Velxio and emits periodic MQTT JSON with `farm_key=greenhouse_j`, `profile=normal`, `dataset_id=node1-normal-v1`, sequence/boot ID, and `synthetic=true`; serial confirms MQTT connected and publish OK.
- [x] Node 2 profile firmware compiles and connects to the MQTT broker. Its runtime currently confirms subscription to actuator commands; this is an actuator board and does not publish periodic sensor samples. A new profile-command ACK/read-back still needs a fresh command.
- [x] Node 3 flow monitor compiles, connects to MQTT, and serial confirms periodic `flow=0.00`, `pressure=0.00`, `fault=none` normal samples. Values are synthetic because no pulse is being generated in the simulator.
- [x] Local `pages/devices.py` contains three Velxio tabs and Mongo-backed device status/profile ACK cards. Public profile project links are set for Node 1 (`b32cdb93…`), Node 2 (`449b7fc8…`), and flow (`fdc6b941…`).
- [x] Bridge contract maps scenario START to `fault`, STOP/CLEAR to `normal` for node1, node2, and flow; preserves incident/run/command IDs and only accepts exact farm/device/profile ACKs. Fault and normal use separate dataset IDs per device.
- [x] Focused tests: `test_velxio_contracts.py` 7/7; Python compile checks pass for devices page, bridge and MQTT service; `git diff --check` clean.
- [ ] Current EC2 `/devices` is still the earlier deployment: it embeds Node 1 and Node 2 only; the newly added Node 3 tab is not live there. Its three Velxio status cards currently show no latest sample. Therefore this session has not verified Node 2/Node 3 MQTT → EC2 bridge → MongoDB → app read-back.
- [ ] Deployment/readback blocked because AWS CLI profile `aws-moi` reports expired session. No new deployment or live fault/clear drill was performed in this session.
- [ ] After AWS session renewal: deploy local app/bridge changes; verify `/healthz`, `/devices`, exact greenhouse_j samples for all 3 device streams and profile ACKs; run one controlled START_SCENARIO → fault datasets/ACKs → STOP/CLEAR → normal datasets/ACKs cycle; verify MongoDB and UI return to normal. Keep outputs OFF and do not claim physical hardware.


## Kế hoạch tối ưu MongoDB (giáo sư Mongo, 2026-11-13)

Căn cứ: mongo_prof_schema.md, mongo_prof_query.md, mongo_prof_features.md và mongo_meta.json (scratchpad). Phân tích tĩnh, chưa chạy explain. Chưa làm gì trên dữ liệu thật.

Nguyên tắc: không đổi dữ liệu trước khi sao lưu; mọi thay đổi chỉ mục/validator/TTL làm trên bản sao hoặc có rollback; thay đổi code phải có test; không triển khai khi chưa được duyệt; không xóa dữ liệu của hồ sơ sự cố; số liệu hiển thị vẫn chỉ từ MongoDB/API/thiết bị ảo.

### Bước 0 - Đo trước khi sửa (chỉ đọc, qua SSM, không in giá trị)
- 0.1 Đếm trùng sự cố đang mở cùng phạm vi (farm_key, node_id, kind, status trong open/holding/recovering).
- 0.2 Đếm $type của notifications.created_at và kiểu _id (string/int/date).
- 0.3 listCollections: validator thật của từng collection; có đủ 4 collection findings, agronomic_advisories, scenario_api_idempotency, scenario_api_farm_locks không.
- 0.4 $indexStats cho telemetry, traceability_events, action_ledger, schedule_logs (chỉ mục nào chưa được dùng).
- 0.5 explain executionStats cho 5 truy vấn nóng: Home telemetry mới nhất, action_ledger theo farm, hộp đen sự cố, schedule_logs theo schedule_id, notifications 30 gần nhất.
- 0.6 Xác nhận Mongo standalone hay replica set (hello).
Tiêu chí: file mongo_baseline.md với số đo thật; quyết định bước sau dựa trên số này.

### Bước 1 - Sửa nhanh, giá trị cao, rủi ro thấp (Haiku A: service/incident_lifecycle.py, service/operational_evidence.py, service/incident_blackbox.py)
- 1.1 Index unique partial cho sự cố đang hoạt động theo phạm vi + bắt DuplicateKeyError trong open_incident; dọn trùng nếu 0.1 thấy có (đóng thủ công, không xóa).
- 1.2 Thống nhất enum action giữa incident_blackbox.py:99 và operational_evidence.py:23 (thêm SET_OUTPUTS, SET_VALVE, SET_VENT, SET_INVERTER); test chung.
- 1.3 Sửa hộp đen: sort giảm dần, limit, rồi sort tăng dần để không cắt mẫu cuối (incident_blackbox.py:387-392, 561-581); test mẫu cuối còn nguyên, add_trailing_gap không báo thiếu giả.
- 1.4 Timeline $push thêm $slice giới hạn; observation khử trùng đúng khóa.
Nghiệm thu: test mới đạt; 274+ test cũ đạt; không có hai sự cố active cùng phạm vi.

### Bước 2 - Chỉ mục và truy vấn (Haiku B: service/auth.py, pages/farm_overview_component.py, pages/incident.py, service/mongodb_store.py)
- 2.1 Tạo chỉ mục: findings {incident_id, detected_at}; action_ledger {farm_key, updated_at:-1}; schedule_logs {schedule_id, start_at}; schedules/users theo trường id. Tạo qua hàm bootstrap có sẵn (idempotent), cho phép tắt.
- 2.2 /incident: bỏ N+1 (gộp một aggregation hoặc đọc kết quả đã tính sẵn), phân trang trước khi dựng timeline; nghiệm thu: tải lần đầu dưới 2 giây trên dữ liệu thật.
- 2.3 _history có limit và projection (auth.py:314-339); get_schedules không kéo toàn bộ log; get_latest_ai_water_suggest thêm meta.measurement_type vào truy vấn.
- 2.4 mongodb_store.py: thêm socketTimeoutMS, maxTimeMS cho truy vấn UI.
Nghiệm thu: explain trước/sau cho 5 truy vấn nóng cho thấy IXSCAN và docsExamined giảm.

### Bước 3 - Tính đúng đắn và vòng đời dữ liệu (Haiku C: service/mqtt.py, các nơi ghi notifications, scripts/, tests/)
- 3.1 Chuẩn hóa notifications.created_at về datetime ở MỌI nơi ghi (auth.py:291, agronomic_thresholds.py:82/92, main.py:936); script migration có sao lưu cho dữ liệu cũ; đọc vẫn chịu được chuỗi cũ.
- 3.2 Gắn $jsonSchema validator (validationLevel moderate, validationAction warn trước, sau đó error) cho collection có hợp đồng rõ: operational_incidents, action_ledger, notifications.
- 3.3 TTL: scenario_api_idempotency và scenario_api_rate_limits (an toàn); notifications và telemetry chỉ sau khi người dùng chốt thời gian giữ.
- 3.4 Ghi MQTT: gom ghi, đưa ra khỏi luồng paho hoặc dùng hàng đợi giới hạn; ghi meta.node_id nhất quán cho nhánh MQTT; thêm on_connect đăng ký lại.
Nghiệm thu: test cho từng thay đổi; migration chạy khô trước, có sao lưu.

### Bước 4 - Việc cần quyết định/chủ hệ thống (không giao agent)
- Thời gian giữ notifications/telemetry (TTL).
- Replica set một nút + transaction + Change Streams: cần khởi động lại mongod, rủi ro vận hành; chỉ làm sau khi Bước 1-3 ổn và có sao lưu.
- Xóa chỉ mục nghi dư (telemetry.meta_1_timestamp_1, traceability_events.farm_key_1_simulated_day_-1) chỉ sau $indexStats.

### Không làm lúc này
Vector Search, Atlas Search, $graphLookup, $merge rollup, mã hóa trường: chưa có nhu cầu đo được.

### Thứ tự, phân chia, triển khai
Bước 0 trước. Bước 1, 2, 3 chia theo file nên 3 Haiku chạy song song, không đụng nhau. Mỗi agent chạy test, cập nhật ACTIVITY_LOG.md. Triển khai EC2 theo mẫu cũ (snapshot EBS, sao lưu file, chỉ restart smiot.service), thay đổi chỉ mục và migration thực hiện sau triển khai code, có sao lưu và đo lại.

- [x] Velxio UI: label embedded circuits as preview, clarify simulation runs separately, retain per-node standalone links, and expand Node 2 preview viewport for lower LED/buzzer visibility.
