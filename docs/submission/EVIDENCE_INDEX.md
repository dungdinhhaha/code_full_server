---
doc_id: SMIOT-SUB-EVIDENCE
title: "Danh mục bằng chứng dùng chung cho hồ sơ SMIOT"
version: "1.0"
date: "2026-11-06"
language: vi
used_by: [SMIOT-SUB-01, SMIOT-SUB-02, SMIOT-SUB-03, SMIOT-SUB-04]
status_values: ["Đã kiểm chứng", "Chưa xác minh", "Cần người dùng"]
---

# Danh mục bằng chứng dùng chung

Cách trích: `[E-xx]` trong thân tài liệu. Trạng thái phản ánh lần kiểm tra ngày 06/11/2026 trong repo (không truy cập hệ thống sống). Đường dẫn tính từ gốc repo. Không ghi secret, IP, email, account, instance ID, org ID.

Writer không sửa tệp này. Cần bằng chứng mới thì ghi `[E-NEW: mô tả]` và báo cáo.

## 1. Tài liệu nền của dự án

| ID | Bằng chứng | Vị trí | Nội dung chứng minh | Trạng thái |
|---|---|---|---|---|
| E-01 | Checklist hồ sơ và danh sách không được tuyên bố | `docs/SUBMISSION_CHECKLIST.md` | Ranh giới tuyên bố | Đã kiểm chứng |
| E-02 | Khai báo dữ liệu, AI, thư viện, MongoDB | `docs/DECLARATIONS.md` | Dữ liệu tổng hợp; Community self-managed; nhiều ô `<ĐIỀN>` | Cần người dùng |
| E-03 | README, phần "Trạng thái hiện tại" và "Trạng thái cloud đã kiểm chứng" | `README.md` dòng 6–37 | Phiên bản MongoDB ghi nhận, DBM, dashboard 8 widget (04/11). Không trích phần lịch sử nhắc Atlas | Đã kiểm chứng (nội dung tài liệu) |
| E-04 | Bộ nhớ dự án | `SMIOT_MEMORY.json` | Kiến trúc, quy tắc cardinality; benchmark một lần (không có tệp kết quả gốc) | Chưa xác minh (benchmark) |

## 2. Mã nguồn

| ID | Bằng chứng | Vị trí | Nội dung chứng minh | Trạng thái |
|---|---|---|---|---|
| E-08 | Tạo Time Series | `scripts/migrate_sqlite_telemetry_to_mongodb.py:115-135` | `timeField=timestamp`, `metaField=meta`, `granularity=seconds` | Đã kiểm chứng (mã); cấu hình sống: E-80 |
| E-10 | Điểm vào ứng dụng và trang | `main.py`, `pages/` | Cấu trúc ứng dụng NiceGUI | Chưa xác minh (writer đọc) |
| E-11 | Ingest MQTT, metric ghi mẫu | `service/mqtt.py:307-330, 449-459` | `smiot.telemetry.samples_persisted`, `ingest_lag_ms`; gắn `incident_id` vào mẫu | Đã kiểm chứng |
| E-12 | Index nghiệp vụ, hình dạng document telemetry | `service/auth.py:71-98, 291-304` | Index compound; `meta{farm_key, source_table, measurement_type, node_id, source}`, `readings`, `source` | Đã kiểm chứng |
| E-13 | Nhãn nguồn và synthetic | `service/telemetry_provenance.py:91-104` | `source`, `synthetic`, `provenance`, `app_received_at` | Đã kiểm chứng |
| E-14 | Watchdog sức khỏe telemetry | `service/telemetry_health.py:35-37, 300-350, 389-513` | Flatline 10 mẫu/0,01/600 s; `status_mismatch`; `_track_false_offline`; `sample_age_seconds`; `dependency.*.up` | Đã kiểm chứng |
| E-15 | Vòng đời sự cố | `service/incident_lifecycle.py:47-95, 311-370` | `start_flatline_incident`, `open_incident`, `close_incident`, trạng thái `recovered` | Đã kiểm chứng |
| E-16 | Hộp đen sự cố | `service/incident_blackbox.py:1-148, 170-300, 551-561` | `$unionWith` 4 nhánh; `$setWindowFields`/`$shift`; partial index; `$jsonSchema` warn/moderate; bảng `CASES` | Đã kiểm chứng |
| E-17 | Trang `/incident` | `pages/incident.py:134-143, 653, 715, 911` | Chỉ admin; danh sách và chi tiết; khối `$unionWith` | Đã kiểm chứng |
| E-18 | Aggregation độ phủ/GDD | `service/mongodb_showcase.py:26-80, 170-180` | `$setWindowFields`, quy tắc ngày đủ dữ liệu | Đã kiểm chứng (mã) |
| E-19 | LLM Observability | `service/observability.py:50-73`; `service/ai_service.py:218-267`; `tests/test_llmobs.py` | `ml_app=smiot-smart-farm`, nội dung bị che, lỗi không làm vỡ app | Đã kiểm chứng (mã); sống: E-84 |
| E-20 | DogStatsD và tag | `service/datadog_metrics.py` | Tag hữu hạn farm/node/source | Chưa xác minh (writer đọc) |
| E-21 | Sổ hành động | `service/operational_evidence.py` | `action_ledger`, `smiot.safe_mode.transition` | Chưa xác minh chi tiết (writer đọc) |
| E-22 | Verifier CLEAR | `scripts/verify_and_clear_demo_safe_mode.py:146-167, 226-243` | ≥ 10 mẫu, ≤ 90 s, biên độ ≥ 0,5 (mã hiện tại) | Đã kiểm chứng |
| E-23 | Probe ngoài app | `scripts/smiot_external_probe.py:7-52, 202-260, 298-344` | `smiot.external.*`; mở `service_down` sau 2 lần `app_up=0` | Đã kiểm chứng |
| E-24 | Guard phục hồi trên host | `scripts/aws/smiot-recover-guarded.sh`; `scripts/aws/smiot-recovery-mongo-readback.py` | Chỉ `systemctl start smiot.service`; lock; cooldown; readback Mongo | Chưa xác minh chi tiết (writer đọc) |
| E-25 | Explain trước/sau | `scripts/explain_before_after.py` | Mặc định dry-run chỉ đọc; `executionStats`; IXSCAN/COLLSCAN | Đã kiểm chứng (mã) |
| E-26 | Benchmark Time Series | `scripts/mongo_timeseries_benchmark.py` | Raw vs aggregation, `executionStats` | Đã kiểm chứng (mã) |
| E-27 | Lệnh kích hoạt diễn tập | `scripts/set_demo_sensor_fault.py`, `scripts/set_demo_ui_fault.py`, `scripts/drill_ca3_service_down.ps1` | Kích hoạt có kiểm soát; Ca 3 mặc định dry-run | Đã kiểm chứng (tồn tại) |
| E-28 | Backup/restore | `scripts/aws/mongodb_backup.sh`, `scripts/aws/mongodb_restore_drill.sh` | `mongodump` + `mongoexport` Time Series | Đã kiểm chứng (tồn tại) |
| E-29 | Cấu hình Datadog trong repo | `deploy/datadog/smiot-logs.yaml`; `deploy/datadog/drafts/` | Thu log; bản nháp monitor/guard (nháp, chưa chắc đã tạo) | Đã kiểm chứng (tồn tại) |
| E-30 | Bộ test | `tests/` (17 tệp) | 162 test đạt, chạy local 06/11/2026 | Đã kiểm chứng |

## 3. Hồ sơ và tài liệu bằng chứng

| ID | Bằng chứng | Vị trí | Nội dung chứng minh | Trạng thái |
|---|---|---|---|---|
| E-40 | Hồ sơ Ca 2 `INC-SMIOT-20261103T102822-D3B0F8A7` | `docs/INC-SMIOT-20261103T102822-D3B0F8A7_EVIDENCE.md` | Timeline; `BLOCKED_HOLD`; Bits 1 xác minh/10 loại; 76 span, 10 log; HOLD do bridge gửi | Đã kiểm chứng (tài liệu) |
| E-41 | Hồ sơ Ca 2 `INC-SMIOT-20261103T114321-BD19A22C` | `docs/INC-SMIOT-20261103T114321-BD19A22C_EVIDENCE.md` | Timeline; 7 mẫu 39,3–41,0%; Bits sửa kết luận | Đã kiểm chứng (tài liệu) |
| E-42 | Diễn tập backup/restore | `docs/MONGODB_BACKUP_RESTORE_DRILL_20261103.md` | 154.618/154.618; 1/1; giới hạn | Đã kiểm chứng (tài liệu) |
| E-43 | Thiết kế phục hồi có guard | `docs/DATADOG_GUARDED_RECOVERY.md` | Bảng nhánh; allowlist sudoers; no-op 04/11 | Đã kiểm chứng (tài liệu); một phần đã cũ |
| E-44 | Playbook ba ca | `docs/THREE_CASES_PLAYBOOK.md` | Quy trình, tiêu chí xong, dừng khẩn | Đã kiểm chứng (tài liệu) |
| E-45 | Kịch bản đa nguyên nhân | `docs/DATADOG_MULTI_CAUSE_SCENARIOS.md` | Chỉ dùng phần thiết kế "từ chối hành động sai"; trạng thái trong đó đã cũ | Lịch sử |

## 4. Đầu ra diễn tập và ảnh chụp

| ID | Bằng chứng | Vị trí | Nội dung chứng minh | Trạng thái |
|---|---|---|---|---|
| E-50 | Xuất cấu hình 6 monitor SMIOT | `outputs/evidence/monitor_{339977691,339977703,339990226,339990232,340356283,341409441}.json` | Query, tag, cửa sổ | Đã kiểm chứng |
| E-51 | Ảnh 6 monitor OK | `outputs/evidence/datadog_smiot_six_monitors_ok.png` | Trạng thái 06/11 (Ca 1 đang mute) | Đã kiểm chứng |
| E-52 | Ảnh dashboard | `outputs/evidence/datadog_smiot_dashboard.png` | Dashboard `nkc-685-vw8` | Đã kiểm chứng |
| E-53 | Ảnh workflow Ca 2 | `outputs/evidence/datadog_workflow_18d1b008-fb24-4713-aa0b-a1432d84ea80.png` | Cấu trúc workflow | Đã kiểm chứng |
| E-54 | Ảnh workflow Ca 3 | `outputs/evidence/datadog_workflow_b83453ff-e122-4148-9519-e698f2effa7f.png` | Cấu trúc workflow | Đã kiểm chứng |
| E-55 | Monitor và workflow Ca 1 | `outputs/evidence/datadog_ca1_monitor_341409441.png`, `datadog_ca1_workflow_e2835af0.png`, `workflow_e2835af0-63fc-48e0-9562-2a1ee4a351d3.json` (cấu hình cũ, một bước Echo, đã lỗi thời); cấu hình hiện tại đọc 06/11 qua Datadog [E-NEW] | Cấu hình 06/11: ba bước: đọc tuổi mẫu từ hai metric Datadog (`smiot.telemetry.sample_age_seconds` và `smiot.external.sample_age_seconds`), rẽ nhánh theo `threshold_seconds` (mặc định 90 s), rồi ghi `REFUSED_RESTART` hoặc `ESCALATE_HUMAN`; không gọi EC2 và không tác động thiết bị; trigger monitor giới hạn 1 lượt mỗi 300 s | Đã kiểm chứng (cấu hình 06/11); ảnh và JSON trong outputs là bản cũ; chưa có execution thật |
| E-56 | Diễn tập lại Ca 2 ngày 06/11 | `outputs/round2/ca2/A0…A8/`, `outputs/round2/_sync/A_status.json` | T0 02:36:40Z; trigger 02:41:51Z; execution `e09175ca-6eed-41a7-8dee-9066d3f366ef` thành công; OK 02:47:07Z | Đã kiểm chứng một phần; `recovered` chưa xác nhận |
| E-57 | Sẵn sàng Ca 3 | `outputs/round2/ca3/B0_B6_readiness/explain.md` | Điều kiện hạ tầng đạt; runner/mute chưa xác minh | Đã kiểm chứng (tài liệu) |
| E-58 | Dry-run Ca 3 | `outputs/drill_ca3_20261106T030543Z.json` | Kiểm tra trước, không dừng service | Đã kiểm chứng |
| E-59 | Diễn tập Ca 3 ngày 06/11 | `outputs/drill_ca3_20261106T030613Z.json` | Dừng 03:06:32Z → xác minh 03:13:30Z (418 s); dependency active; trường Datadog để trống | Đã kiểm chứng một phần; tác nhân start: E-82 |
| E-60 | Ảnh story pack | `outputs/20261104_smiot_story_pack/evidence/` (`smiot-bits-node2-investigation-latest.png`, `smiot-node2-apm.png`, `smiot-node2-logs.png`, `smiot-ec2-workflow-execution.png`, `smiot-dashboard-us.png`, …) | Bits Ca 2, APM, Logs, execution Ca 3 ngày 04/11 | Đã kiểm chứng (ảnh tồn tại); kiểm che thông tin trước khi dùng |

## 5. Đối tượng trên Datadog (ID tham chiếu)

| ID | Đối tượng | Giá trị | Trạng thái |
|---|---|---|---|
| E-70 | Monitor SMIOT | 339977691, 339977703, 339990226, 339990232, 340356283, 341409441 | Đã kiểm chứng (E-50) |
| E-71 | Workflow | `e2835af0-63fc-48e0-9562-2a1ee4a351d3` (Ca 1), `18d1b008-fb24-4713-aa0b-a1432d84ea80` (Ca 2), `b83453ff-e122-4148-9519-e698f2effa7f` (Ca 3) | Đã kiểm chứng (E-53…E-55, E-16) |
| E-72 | Dashboard | `nkc-685-vw8` | Đã kiểm chứng (E-52) |
| E-73 | Bits AI investigation | `008cc971-b1be-4453-a9f4-fa947a704f51` (D3B0F8A7); `3de8802a-d62c-4983-b2d9-07c7dc3bdf1c` (BD19A22C); "164FBE41" | Hai ID đầu: Đã kiểm chứng (E-40, E-41); 164FBE41: Cần người dùng |
| E-74 | Workflow execution | `72ae7b55-0fab-46a8-92eb-7760baaf47ff` (Ca 2, 03/11); `41135755-2edd-429b-9c0f-9e73ae7c43a1` (Ca 3, 04/11); `e09175ca-6eed-41a7-8dee-9066d3f366ef` (Ca 2, 06/11) | Đã kiểm chứng (tài liệu) |
| E-75 | Monitor APM nền (không thuộc ca) | 339985452, 339992812, 339992811 | Đã kiểm chứng (tài liệu `docs/CODEX_PLAN_3_CASES.md`) |

## 6. Bằng chứng còn thiếu (giữ chỗ)

| ID | Cần có | Ai cung cấp | Trạng thái |
|---|---|---|---|
| E-80 | Kết quả lệnh chỉ-đọc MongoDB (phiên bản, standalone, tùy chọn Time Series, số bản ghi, index thật, validator, document mẫu, collStats) — `00_PLAN.md` §H.2 | Người dùng | Cần người dùng |
| E-81 | Bản ghi Ca 1 (Datadog): monitor 341409441 Alert 04:49:21Z; lượt `a782b12c…` (04:50:21Z) Success, nhánh REFUSED_RESTART; monitor OK 05:00:21Z; lượt Recovered `9c014532…` (05:01:22Z). Ảnh: `ca1-alert-event.png`, `ca1-recovered-event.png` | Người dùng | Đã kiểm chứng (Datadog) |
| E-82 | Ca 3 ngày 06/11 (Datadog): monitor 340356283 Alert 03:11:43Z, Recovered 03:13:43Z; workflow `b83453ff…` lượt `06cb1b46…` (03:12:43.914Z) chạy `recover-smiot-web` thành công. Đầu ra lệnh EC2 chưa đọc được (SCP chặn `ssm:GetCommandInvocation`). Ảnh: `ca3-alert-event.png` | Người dùng | Đã kiểm chứng (Datadog); đầu ra EC2 chưa xác minh |
| E-83 | Ảnh `/incident` (3 thẻ ca) và `/incident/<id>` từng ca | Người dùng | Cần người dùng |
| E-84 | Ảnh LLM Observability (`ml_app:smiot-smart-farm`, nội dung bị che, span Gemini) | Người dùng | Đã có ảnh `datadog-llm-observability.png` |
| E-85 | Explain trước/sau (`scripts/explain_before_after.py`, dry-run) và benchmark chạy lại | Người dùng | Cần người dùng |
| E-86 | Ca 2 ngày 06/11: incident ID, `action_ledger` HOLD/CLEAR, trạng thái `recovered` | Người dùng | Cần người dùng |
