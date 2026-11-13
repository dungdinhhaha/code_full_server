# Brief Writer C — Tài liệu 03: Kiến trúc observability trên Datadog

Bạn là writer kỹ thuật cho dự án SMIOT Smart Farm dự thi Mini Hackathon MongoDB x Datadog. Repo: `D:\IOT Trung\code_full_server` (Windows, PowerShell; Python `py -3.12 -X utf8`). Viết tiếng Việt, văn phong báo cáo khoa học.

## 1. Phạm vi quyền
- **Được tạo/sửa đúng một tệp:** `docs/submission/03_kien_truc_observability_datadog.md`.
- **Không** sửa tệp khác, không commit git, không gọi Datadog/EC2/MongoDB sống (kể cả MCP), không đọc `.env`/`/etc/smiot/*`. Không ghi API/app key, token, IP, email, org ID, account AWS, instance ID.
- Thông tin Datadog chỉ lấy từ repo (`outputs/evidence/`, `docs/`, mã). Thiếu thì «CẦN NGƯỜI DÙNG: …».

## 2. Đọc trước
1. `docs/submission/00_PLAN.md` §0, §C.3, §D, §E.
2. `docs/submission/EVIDENCE_INDEX.md`.
3. `outputs/evidence/README.md`, `outputs/evidence/monitor_*.json` (6 tệp), `outputs/evidence/workflow_e2835af0-63fc-48e0-9562-2a1ee4a351d3.json`, ảnh trong `outputs/evidence/`.
4. `docs/DATADOG_GUARDED_RECOVERY.md` (thiết kế nhánh guard; phần trạng thái 04/11 đã cũ một phần).
5. `docs/INC-SMIOT-20261103T102822-D3B0F8A7_EVIDENCE.md` (Bits, log có cấu trúc, cardinality), `docs/INC-SMIOT-20261103T114321-BD19A22C_EVIDENCE.md` (Bits sửa kết luận).
6. `outputs/round2/ca1/*/explain.md`, `outputs/round2/ca2/A3_wait_detect`, `A4_workflow`, `A6_verify_recovery`; `outputs/drill_ca3_20261106T030613Z.json`.
7. `deploy/datadog/smiot-logs.yaml`, `deploy/datadog/drafts/*` (là **bản nháp**; chỉ mô tả cái đã có trên Datadog theo E-50…E-55).
8. `README.md` dòng 15–37 (DBM, Agent, dashboard 8 widget ngày 04/11).
- `docs/DATADOG_MULTI_CAUSE_SCENARIOS.md` là lịch sử (M3): chỉ dùng ý "từ chối hành động sai", không dùng phần trạng thái.

## 3. Kiểm trong mã trước khi viết
| Cần kiểm | Ở đâu |
|---|---|
| Metric app, kiểu gauge, tag | `service/telemetry_health.py:330-500`; `service/mqtt.py:300-335`; `service/datadog_metrics.py` |
| Metric probe ngoài app, chu kỳ, ngưỡng mở sự cố | `scripts/smiot_external_probe.py:1-60, 298-344` |
| Log JSON có cấu trúc (`incident.id`, `farm.key`, `node.id`) | `service/logger.py` (Grep `smiot.incident.json`), `deploy/datadog/smiot-logs.yaml` |
| APM span tên `smiot.*` | `service/mqtt.py:186, 312`, `service/operational_evidence.py:117`, `service/observability.py` |
| LLM Observability | `service/observability.py:40-90`, `service/ai_service.py:210-270`, `tests/test_llmobs.py` |
| Guard trên host, log `smiot.guarded_recovery` | `scripts/aws/smiot-recover-guarded.sh`, `scripts/aws/smiot-recovery-mongo-readback.py` |
| Quy tắc flatline phát `sensor_flatline` | `service/telemetry_health.py:35-37, 475-513` |
| `status_mismatch` và mở `false_offline` | `service/telemetry_health.py:300-350` |
| Ca → monitor/workflow trong app | `service/incident_blackbox.py:551-561` |
Nếu mã khác `00_PLAN.md`, theo mã và báo cáo.

## 4. Front matter
```yaml
---
doc_id: SMIOT-SUB-03
title: "Kiến trúc observability trên Datadog"
submission_section: 5
project: "SMIOT Smart Farm"
competition: "Mini Hackathon MongoDB x Datadog 2026"
version: "0.9-draft"
date: "2026-11-0X"
language: vi
data_label: synthetic
datadog:
  site: "US1"
  service: "smiot-smart-farm"
  env: "demo"
  products_used: [infrastructure_agent, dogstatsd_metrics, log_management, apm, database_monitoring_mongodb, systemd_integration, monitors, workflow_automation, private_action_runner, dashboards, bits_ai_investigation, llm_observability]
  monitors: ["339977691", "339977703", "339990226", "339990232", "340356283", "341409441"]
  workflows: ["e2835af0-63fc-48e0-9562-2a1ee4a351d3", "18d1b008-fb24-4713-aa0b-a1432d84ea80", "b83453ff-e122-4148-9519-e698f2effa7f"]
  dashboard: "nkc-685-vw8"
evidence_index: "EVIDENCE_INDEX.md"
related_docs: [SMIOT-SUB-01, SMIOT-SUB-02, SMIOT-SUB-04]
reading_order: [SMIOT-SUB-01, SMIOT-SUB-04, SMIOT-SUB-02, SMIOT-SUB-03]
status: draft
---
```
Chỉ giữ trong `products_used` sản phẩm có bằng chứng trong repo.

## 5. Dàn ý (5.000–6.500 từ), giữ nguyên số chương
- **Tóm tắt; Đóng góp chính** (5 gạch theo `00_PLAN.md` §C.3, mỗi gạch `[E-xx]`). **Bảng 0. Đọc nhanh.**
- **1 Đặt vấn đề quan sát.** Ba câu hỏi tách biệt: tiến trình có sống; dữ liệu có tươi và có biến thiên; giao diện có phản ánh đúng dữ liệu. Mỗi câu một nhóm tín hiệu.
- **2 Kiến trúc thu thập.** Hình 2.1 (Mermaid `flowchart`): app (DogStatsD, log JSON, ddtrace, LLMObs) + probe ngoài app (DogStatsD) + host/systemd + MongoDB integration/DBM + log guard JSONL → Agent → US1 → dashboard/monitor → workflow → Private Action Runner. Đoạn mô tả bằng chữ. Nêu: probe chạy ngoài tiến trình app (timer 30 s) để vẫn đo được khi app dừng [E-23, E-44].
- **3 Mô hình tín hiệu.** 3.1 Bảng 3.1 metric: tên, kiểu, tag, nguồn `file:dòng`, câu hỏi nó trả lời (ít nhất: `smiot.telemetry.sensor_flatline`, `status_mismatch`, `sample_age_seconds`, `fresh`, `samples_persisted`, `ingest_lag_ms`, `smiot.dependency.mongo.up`, `smiot.dependency.mqtt.up`, `smiot.external.app_up`, `smiot.external.sample_age_seconds`, `smiot.external.mongo_up`, `systemd.unit.active`, các metric `smiot.telemetry.*` cảm biến). 3.2 Quy tắc tag: chiều hữu hạn (farm, node, source, env, service); `incident_id`/`command_id` không làm tag metric. 3.3 Khóa tương quan: `@incident.id`, `@farm.key`, `@node.id`, trace ID; bài học từ D3B0F8A7 (trước sửa: thuộc tính nằm trong message; sau sửa: log JSON có cấu trúc) [E-40].
- **4 Monitor.** 4.1 Bảng 4.1 sáu monitor SMIOT: ID, tên, query nguyên văn (từ E-50), cửa sổ, ngưỡng, tag `scenario`, workflow gắn kèm, ca. 4.2 Thiết kế đối chứng Ca 1: 341409441 (lệch hiển thị) phải Alert trong khi 339977703 (dữ liệu cũ) vẫn OK → bằng chứng "dữ liệu còn tươi" nằm ngay trong trạng thái monitor. 4.3 Monitor APM nền 339985452, 339992812, 339992811 (không thuộc ca) [E-75]. 4.4 Lý do chọn cửa sổ (ví dụ `max(last_2m)` cho flatline; `avg(last_5m)` cho systemd làm chậm phát hiện 3–5 phút theo kế hoạch) — chỉ nêu đánh đổi, không đưa số MTTD.
- **5 Workflow và hành động có guard.** 5.1 Bảng 5.1 ba workflow: tên, trigger, rate limit, bước, tác động. Ca 1: Echo `REFUSED_RESTART`, 1/300 s, không truy vấn MongoDB, không tác động EC2 [E-55]. Ca 2: gọi endpoint app; app tự kiểm tra rồi HOLD/CLEAR [E-41, E-53]. Ca 3: Private Action Runner chạy script định nghĩa sẵn [E-54, E-43]. 5.2 Allowlist: sudoers chỉ `systemctl start smiot.service` và helper readback không tham số [E-43]. 5.3 Hình 5.1 cây quyết định guard (G0 healthy → no-op; G1 systemd tự hồi; G3 app active nhưng HTTP lỗi → từ chối; G4 trạng thái lạ → từ chối; G5 đĩa/mongod/mosquitto/readback; G6 lock + cooldown 300 s; G7 start; verify HTTP 200 + mẫu mới). Nhánh G2 "mẫu còn tươi → từ chối" ghi rõ **đề xuất, chưa có trong script** (E-29 drafts). 5.4 Rate limit và bài học lịch sử (4 lần "Rate limit exceeded" ngày 03/11 [E-56]).
- **6 Dashboard `nkc-685-vw8`.** Nội dung theo ảnh E-52 và README (8 widget, đếm 04/11); «CẦN NGƯỜI DÙNG: ảnh chụp mới» nếu cần số hiện tại. Không tuyên bố SLO (route SLO không truy cập được 06/11).
- **7 Điều tra.** 7.1 Pivot Logs/APM theo `@incident.id` (76 span, 10 log ở D3B0F8A7) [E-40]. 7.2 Bits AI: chỉ Ca 2; D3B0F8A7 có 1 giả thuyết xác minh và 10 bị loại; BD19A22C kết luận ban đầu sai một giả thuyết, được sửa sau phản hồi và chạy lại [E-41]; "164FBE41" «CẦN NGƯỜI DÙNG: E-73». 7.3 Giới hạn: Bits không phải nguồn xác nhận phục hồi; cửa sổ thời gian của Bits có thể kết thúc trước khi phục hồi; bộ đếm "6/19" trong Bits Chat chưa giải thích.
- **8 LLM Observability.** `LLMObs.enable(ml_app="smiot-smart-farm")`, nội dung vào/ra bị che; span cho lời gọi Gemini; lỗi Datadog không làm vỡ lời gọi mô hình (test). Ảnh: «CẦN NGƯỜI DÙNG: E-84». Không mô tả nội dung prompt.
- **9 Đánh giá.** 9.1 Quan sát từ diễn tập (một lần đo, không gọi MTTD/MTTR): Ca 2 06/11 T0 → trigger 311 s, normal → OK 206 s [E-56]; Ca 3 06/11 dừng → xác minh 418 s, dependency active suốt [E-59] (thời điểm monitor Alert và execution: «CẦN NGƯỜI DÙNG: E-82»). 9.2 Bảng Tuyên bố – Bằng chứng – Trạng thái (≥ 12 dòng).
- **10 Hạn chế và phạm vi.** Trial sắp hết (bằng chứng đã xuất ở `outputs/evidence/`); tạo/sửa monitor bằng UI (ghi qua MCP bị chặn); API key của app không đọc được API tìm kiếm (403) [E-40]; SLO không truy cập được; Bits chỉ Ca 2 và không xác nhận phục hồi; workflow Ca 1 ba bước theo cấu hình 06/11; tác nhân start Ca 3 ngày 06/11 chưa xác minh; chưa có Synthetic test định kỳ; monitor 339990226/339990232 mang tag `managed_by:codex` (giữ nguyên).
- **11 Kết luận.** **Phụ lục.** Bảng ID và đường dẫn tương đối Datadog (`/monitors/<id>`, `/workflow/<id>`, `/dashboard/nkc-685-vw8`); tham chiếu tài liệu Datadog chính thức đã trích trong `docs/DATADOG_GUARDED_RECOVERY.md`.

## 6. Điểm hay (chỉ khi đã kiểm)
1. Monitor đối chứng cho Ca 1 [E-50, E-55].
2. Metric `status_mismatch` đo trực tiếp sự lệch UI–dữ liệu [E-14].
3. Probe ngoài app đo được khi app dừng [E-23].
4. Workflow chỉ chạy script định nghĩa sẵn, fail-closed [E-24, E-43].
5. `incident_id` ở log/trace/MongoDB, không ở tag metric [E-40].

## 7. Danh sách cấm (nguyên văn từ người dùng)
Không tuyên bố Atlas Search/Vector Search/Triggers/Charts/Stream Processing; không tuyên bố Change Streams; không đưa MTTD/MTTR/% giảm cảnh báo/SLO đạt khi chưa có nguồn đo; không nói thiết bị vật lý hỏng/đã sửa; không coi dữ liệu tổng hợp là dữ liệu thật; không nói "tự động khắc phục" nếu bước thực hiện là thủ công; không nói Bits AI xác nhận phục hồi khi chưa; không ghi điểm tự chấm; không lộ key/IP/email. Chỗ thiếu thông tin: placeholder «CẦN NGƯỜI DÙNG: …», không bịa.
Thêm: không nói workflow Ca 1 kiểm tra MongoDB; không nói workflow Ca 3 đã start service ngày 06/11 khi chưa có E-82; không mô tả bản nháp trong `deploy/datadog/drafts/` như đã triển khai; không nêu chuyện hạn nộp; không trình bày ánh xạ tiêu chí như của BTC.

## 8. Văn phong
Theo `00_PLAN.md` §E. Query monitor để trong code inline nguyên văn. Thuật ngữ §D.1. Tham chiếu chéo `(xem Tài liệu 04, §4.6)`. Mốc thời gian ca lấy đúng như Tài liệu 04 sẽ dùng (nguồn: E-40, E-41, E-56, E-59).

## 9. Checklist tự kiểm
- [ ] Query 6 monitor chép đúng từ `outputs/evidence/monitor_*.json`.
- [ ] Workflow ID đủ 36 ký tự, khớp `00_PLAN.md` §D.2.
- [ ] Mọi metric trong Bảng 3.1 Grep thấy trong mã.
- [ ] Không key/token/IP/email/org ID; không link có tham số chứa thông tin nhạy cảm.
- [ ] Grep từ cấm: MTTR, MTTD, SLO đạt, tự động khắc phục, Atlas, Change Stream, dữ liệu thật, hỏng.
- [ ] Mọi `[E-xx]` tồn tại; số chương khớp; độ dài 5.000–6.500 từ.

## 10. Báo cáo
Tin nhắn ≤ 300 từ: đường dẫn tệp; số từ; chỗ mã khác `00_PLAN.md`; danh sách `[E-NEW]`; placeholder còn lại; ảnh/xuất Datadog cần chụp gấp (theo thứ tự ưu tiên) trước khi trial hết.
