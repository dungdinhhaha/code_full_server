# Brief Writer A — Tài liệu 01 (Kiến trúc giải pháp) và Tài liệu 04 (Mô tả sự cố)

Bạn là writer kỹ thuật cho dự án SMIOT Smart Farm dự thi Mini Hackathon MongoDB x Datadog. Repo: `D:\IOT Trung\code_full_server` (Windows, PowerShell; Python `py -3.12 -X utf8`). Viết tiếng Việt, văn phong báo cáo khoa học.

## 1. Phạm vi quyền
- **Được tạo/sửa đúng hai tệp:** `docs/submission/01_kien_truc_giai_phap.md`, `docs/submission/04_mo_ta_su_co_van_hanh.md`.
- **Không** sửa bất kỳ tệp nào khác (kể cả `EVIDENCE_INDEX.md`, `00_PLAN.md`, `docs/*.md`, mã). Không commit git. Không truy cập EC2, MongoDB, Datadog sống. Không đọc `.env`, `/etc/smiot/*`, không in secret.
- Không ghi IP, hostname demo, email, account AWS, instance ID, tên bucket, org ID. URL demo viết `<URL_DEMO>`.

## 2. Đọc trước (bắt buộc, theo thứ tự)
1. `docs/submission/00_PLAN.md` — đặc biệt §0 (sự thật F1–F22, mâu thuẫn M1–M12), §C.1, §C.4, §D, §E.
2. `docs/submission/EVIDENCE_INDEX.md` — chỉ trích ID có trong đó.
3. `docs/THREE_CASES_PLAYBOOK.md`, `docs/EVIDENCE_TEMPLATE.md`.
4. `docs/INC-SMIOT-20261103T102822-D3B0F8A7_EVIDENCE.md`, `docs/INC-SMIOT-20261103T114321-BD19A22C_EVIDENCE.md`.
5. `docs/DATADOG_GUARDED_RECOVERY.md`, `docs/MONGODB_BACKUP_RESTORE_DRILL_20261103.md`.
6. `outputs/round2/ca1/*/explain.md`, `outputs/round2/ca2/*/explain.md` và `result.json`, `outputs/round2/ca3/B0_B6_readiness/explain.md`.
7. `outputs/drill_ca3_20261106T030613Z.json` (trường `marks`, `observations`, `datadog_fields_to_fill_manually`, `result`).
8. `outputs/evidence/README.md`, `outputs/evidence/workflow_e2835af0-63fc-48e0-9562-2a1ee4a351d3.json`, `outputs/evidence/monitor_*.json`.
- **Không chép** `outputs/20261104_smiot_story_pack/Kien_truc_giai_phap_MongoDB_Datadog.md` (đã cũ: hai kịch bản, document mẫu sai trường). Chỉ được tham khảo sơ đồ Mermaid và cập nhật.

## 3. Kiểm trong mã trước khi viết (Grep/Read đoạn cần)
| Cần kiểm | Ở đâu |
|---|---|
| Danh sách `kind` và bảng `CASES` | `service/incident_blackbox.py:22, 551-561` |
| `/incident` chỉ admin | `pages/incident.py:134-143` |
| Mở sự cố flatline, `open_incident`, `close_incident` | `service/incident_lifecycle.py:47-95, 311-370` |
| `_track_false_offline`, `status_mismatch` | `service/telemetry_health.py:300-350` |
| Quy tắc flatline | `service/telemetry_health.py:35-37, 475-513` |
| Verifier (≥ 10 mẫu, ≤ 90 s, biên độ ≥ 0,5) | `scripts/verify_and_clear_demo_safe_mode.py:146-167` |
| Probe mở `service_down` sau 2 lần | `scripts/smiot_external_probe.py:52, 202-260` |
| Guard host: chỉ `systemctl start`, lock, cooldown | `scripts/aws/smiot-recover-guarded.sh` (đọc để xác nhận) |
| Lệnh kích hoạt Ca 1/2/3 | `scripts/set_demo_ui_fault.py`, `scripts/set_demo_sensor_fault.py`, `scripts/drill_ca3_service_down.ps1` |
| Mô-đun app | `main.py`, `pages/`, `service/` (liệt kê, không mô tả chi tiết từng tệp) |
| Trợ lý AI an toàn khi lỗi | `service/ai_service.py`, `tests/test_ai_failsafe.py` |
Nếu mã khác với `00_PLAN.md`, **theo mã** và ghi chênh lệch vào báo cáo.

## 4. Front matter (dùng cho cả hai tệp, đổi giá trị tương ứng)
```yaml
---
doc_id: SMIOT-SUB-01            # 04: SMIOT-SUB-04
title: "Kiến trúc giải pháp và ứng dụng SMIOT"   # 04: "Mô tả sự cố và tình huống vận hành được trình diễn"
submission_section: 3           # 04: 11
project: "SMIOT Smart Farm"
competition: "Mini Hackathon MongoDB x Datadog 2026"
version: "0.9-draft"
date: "2026-11-0X"
language: vi
data_label: synthetic
mongodb: {edition: "Community", version: "8.0.x (CẦN NGƯỜI DÙNG xác nhận)", deployment: "self-managed, standalone, EC2"}
datadog: {site: "US1", service: "smiot-smart-farm", env: "demo"}
cases:
  - {id: CA1, kind: false_offline, monitor: "341409441", control_monitor: "339977703", workflow: "e2835af0-63fc-48e0-9562-2a1ee4a351d3"}
  - {id: CA2, kind: soil_humidity_flatline, monitor: "339977691", workflow: "18d1b008-fb24-4713-aa0b-a1432d84ea80"}
  - {id: CA3, kind: service_down, monitor: "340356283", workflow: "b83453ff-e122-4148-9519-e698f2effa7f"}
evidence_index: "EVIDENCE_INDEX.md"
related_docs: [SMIOT-SUB-02, SMIOT-SUB-03, SMIOT-SUB-04]   # 04: [SMIOT-SUB-01, SMIOT-SUB-02, SMIOT-SUB-03]
reading_order: [SMIOT-SUB-01, SMIOT-SUB-04, SMIOT-SUB-02, SMIOT-SUB-03]
ai_tools_declared: true
status: draft
---
```

## 5. Dàn ý Tài liệu 01 (3.500–4.500 từ)
Giữ nguyên số chương.
- **Tóm tắt** (≤ 200 từ, 4 câu: bối cảnh – phương pháp – kết quả có số và `[E-xx]` – giới hạn).
- **Đóng góp chính** (5 gạch, mỗi gạch có `[E-xx]`):
  1. Ba lớp lỗi → ba phản ứng khác nhau, có phản ứng từ chối restart [E-16, E-55].
  2. Hành động duy nhất trên host là `systemctl start smiot.service` có allowlist, lock, cooldown 300 s, kiểm đĩa và dependency [E-24, E-43].
  3. Phục hồi định nghĩa bằng dữ liệu đọc lại (HTTP 200 + mẫu Mongo mới ≤ 180 s) [E-59, E-43].
  4. Chia vai: Datadog điều tra, MongoDB đo tác động, app điều hướng [E-17].
  5. Nhãn tổng hợp nằm trong từng document [E-13].
- **Bảng 0. Đọc nhanh** (bài toán; giải pháp; MongoDB dùng gì; Datadog dùng gì; ba ca; giới hạn; thứ tự đọc 01 → 04 → 02 → 03).
- **1 Đặt vấn đề.** 1.1 Bối cảnh nhà kính dưa lưới; 1.2 Câu hỏi vận hành: dữ liệu còn đủ tin cậy để quyết định tưới/lịch thu hoạch không; 1.3 Ba lớp lỗi (hiển thị sai trong khi dữ liệu tươi; dữ liệu đến nhưng đứng số; tiến trình app dừng trong khi DB/MQTT khỏe) và vì sao cần ba phản ứng khác nhau; 1.4 Phạm vi (dữ liệu tổng hợp từ publisher demo/Wokwi, PLC ảo, một EC2).
- **2 Yêu cầu và nguyên tắc thiết kế.** R1–R6 (xem `00_PLAN.md` §C.1). Mỗi nguyên tắc: phát biểu – lý do – nơi hiện thực `[E-xx]`.
- **3 Kiến trúc tổng thể.** 3.1 Hình 3.1 sơ đồ triển khai (Mermaid `flowchart LR`): Người vận hành →HTTPS→ Nginx → App NiceGUI; Publisher demo/Wokwi bridge →MQTT→ Mosquitto ↔ App; App ↔ MongoDB Community (Time Series + collection nghiệp vụ); PLC ảo ↔ Mosquitto; App, probe ngoài app, host, MongoDB integration → Datadog Agent → Datadog US1; Datadog → Monitor → Workflow → Private Action Runner → script guard → `systemctl start smiot.service`. Đoạn mô tả bằng chữ ngay sau hình. 3.2 Bảng 3.1 thành phần–trách nhiệm–tệp chính. 3.3 Ranh giới tin cậy và quyền tối thiểu (user Mongo đọc cho Datadog; sudoers chỉ hai lệnh; helper readback không trả secret) [E-43]. 3.4 Failure domain: app và MongoDB cùng một EC2.
- **4 Kiến trúc ứng dụng.** 4.1 Mô-đun; 4.2 Luồng ingest (Hình 4.1 `sequenceDiagram`: publisher → MQTT → app kiểm tra/gắn provenance → ghi `telemetry` → metric/log/trace); 4.3 Watchdog (`telemetry_health`); 4.4 Vòng đời sự cố (`open → holding → recovering → recovered/closed`, theo `ALL_STATUSES` trong `service/incident_blackbox.py:24`); 4.5 Verifier và probe ngoài app; 4.6 `/incident` (admin) = bảng điều hướng: câu 1, 2, 3, 5 tóm tắt + link Datadog; câu 4, 6 do MongoDB trả lời; 4.7 Trợ lý AI Gemini: khai báo; lỗi mô hình không làm vỡ app; không tự điều khiển bơm.
- **5 Luồng phát hiện–điều tra–xử lý.** Hình 5.1 vòng: tín hiệu → monitor → điều tra (Logs/APM/Bits) → quyết định có guard → hành động → xác minh bằng dữ liệu → đóng sự cố. Bảng 5.1: ba ca × (lớp lỗi, tín hiệu, monitor, hành động, bằng chứng phục hồi, trạng thái bằng chứng). Chi tiết trỏ sang Tài liệu 04.
- **6 Độ tin cậy và khả năng bảo trì.** Guard/lock/cooldown; idempotency theo `command_id` trong `action_ledger` (không có transaction); validator `warn`; 162 test đạt (06/11) [E-30]; backup/restore [E-42]; triển khai có snapshot và rollback (nêu là quy trình đã dùng, không tuyên bố tự động).
- **7 Đánh giá.** Bảng 7.1 Tuyên bố – Bằng chứng – Trạng thái (≥ 10 dòng).
- **8 Hạn chế và phạm vi.** Một EC2; dữ liệu tổng hợp; PLC ảo; Ca 1 chưa có lần diễn tập ghi incident (trừ khi E-81 có); tác nhân start Ca 3 06/11 chưa xác minh; SLO chưa có; Bits chỉ Ca 2; các tính năng MongoDB không dùng (một câu duy nhất: không dùng dịch vụ Atlas, không dùng change stream/transaction do chạy standalone).
- **9 Kết luận.** 1 đoạn, không quảng cáo.
- **Phụ lục A.** Bảng thành phần có từ trước 17/10: mọi ô ngày/phạm vi = «CẦN NGƯỜI DÙNG: …». **Phụ lục B.** Công cụ AI đã dùng (Claude Code; Codex; Gemini trong app; Datadog Bits AI) — mô tả vai trò, «CẦN NGƯỜI DÙNG» nếu chưa rõ. **Tài liệu tham khảo** (tài liệu Datadog/MongoDB chính thức đã trích trong repo).

## 6. Dàn ý Tài liệu 04 (5.500–7.000 từ)
- **Tóm tắt; Đóng góp chính** (5 gạch theo `00_PLAN.md` §C.4).
- **Bảng 0. Tổng quan ba ca**: tên ca, `kind`, monitor, workflow, hành động mong đợi, lần diễn tập có bằng chứng, mức hoàn thiện bằng chứng (Đầy đủ / Một phần / Đã cấu hình, chưa diễn tập).
- **1 Phương pháp diễn tập.** 1.1 Nguyên tắc chung (một ca mỗi lần; snapshot trước; dữ liệu tổng hợp; mốc UTC + ICT; không tạo bản ghi giả) [E-44]; 1.2 Khung 6 câu [E-44]; 1.3 Chia vai (Hình 1.1: câu 1, 2, 3, 5 ← Datadog; câu 4, 6 ← MongoDB; app hiển thị và dẫn link); 1.4 Tiêu chí "xong" từng ca.
- **2 Ca 1 — Báo offline sai** · **3 Ca 2 — Độ ẩm đất Node 2 đứng yên** · **4 Ca 3 — `smiot.service` dừng**. Mỗi chương có đủ: x.1 Giả thuyết và kịch bản kích hoạt; x.2 Phát hiện; x.3 Điều tra; x.4 Quyết định và hành động (lý do + phương án bị loại); x.5 Tác động trên dữ liệu; x.6 Phục hồi và bằng chứng; x.7 Bảng dòng thời gian UTC/ICT; x.8 Bảng 6 câu (cột: Câu hỏi, Trả lời, Nguồn [E-xx], Trạng thái); x.9 Giới hạn. Mỗi ca một Hình `sequenceDiagram`.
  - **Ca 1 dữ liệu được dùng:** monitor 341409441 query `max(last_5m)… status_mismatch… by {farm,node} > 0`; monitor đối chứng 339977703 `sample_age_seconds > 120`; workflow e2835af0 ba bước (cấu hình 06/11): đọc tuổi mẫu từ hai metric Datadog, rẽ nhánh theo ngưỡng, Echo `REFUSED_RESTART` hoặc `ESCALATE_HUMAN`; trigger monitor 1/300 s; không gọi MongoDB trực tiếp, không tác động EC2 [E-50, E-55]; kích hoạt bằng `set_demo_ui_fault.py stale_cache --node 1` [E-27, E-44]. Kết quả diễn tập: «CẦN NGƯỜI DÙNG: E-81». Nếu chưa có, ghi rõ "đã cấu hình, chưa diễn tập có ghi nhận" và trình bày tiêu chí kiểm chứng dự kiến.
  - **Ca 2 dữ liệu được dùng:** lần chuẩn `INC-SMIOT-20261103T114321-BD19A22C` [E-41] (T0 11:43:21Z; Alert 11:48:51Z; HOLD ACK 11:49:59.805Z; phục hồi xác minh 13:39:56.487Z; 7 mẫu 39,3–41,0%; Bits sửa kết luận); lần `…D3B0F8A7` [E-40] (`BLOCKED_HOLD`, HOLD do bridge fallback, workflow khử trùng lặp; Bits 1 xác minh/10 loại); lần 06/11 [E-56] (T0 02:36:40Z, trigger 02:41:51Z, execution e09175ca thành công, OK 02:47:07Z; `recovered` «CẦN NGƯỜI DÙNG: E-86»). Bits "164FBE41": «CẦN NGƯỜI DÙNG: E-73». Ngưỡng verifier theo mã hiện tại = 10 mẫu [E-22]; số mẫu từng lần = số trong hồ sơ lần đó.
  - **Ca 3 dữ liệu được dùng:** execution 04/11 `41135755…` [E-74]; drill 06/11 [E-59]: dừng 03:06:32.578Z, thấy dừng 03:06:47.964Z, xác minh 03:13:30.893Z, 418 s; `mongod`, `mosquitto` active suốt; HTTP 000 khi dừng; tuổi mẫu lớn nhất 406,7 s; phục hồi = unit active + HTTP 200 + mẫu Mongo mới trong 180 s. Ai/cái gì start service: «CẦN NGƯỜI DÙNG: E-82». Không viết "workflow tự động start" khi chưa có E-82.
- **5 So sánh ba ca.** Bảng 5.1: triệu chứng; lớp lỗi; dữ liệu Mongo có còn vào; hành động đúng; hành động sai bị loại (restart oan; CLEAR sớm; restart EC2/mongod).
- **6 Trình diễn trên `/incident`** (admin): 3 thẻ ca, hồ sơ 6 câu, thanh tua, khung link; ảnh «CẦN NGƯỜI DÙNG: E-83»; tài khoản giám khảo «CẦN NGƯỜI DÙNG».
- **7 Đánh giá** (Bảng Tuyên bố – Bằng chứng – Trạng thái). **8 Hạn chế và phạm vi.** **9 Kết luận.**

## 7. Danh sách cấm (nguyên văn từ người dùng)
Không tuyên bố Atlas Search/Vector Search/Triggers/Charts/Stream Processing; không tuyên bố Change Streams; không đưa MTTD/MTTR/% giảm cảnh báo/SLO đạt khi chưa có nguồn đo; không nói thiết bị vật lý hỏng/đã sửa; không coi dữ liệu tổng hợp là dữ liệu thật; không nói "tự động khắc phục" nếu bước thực hiện là thủ công; không nói Bits AI xác nhận phục hồi khi chưa; không ghi điểm tự chấm; không lộ key/IP/email. Chỗ thiếu thông tin: placeholder «CẦN NGƯỜI DÙNG: …», không bịa.
Thêm: không nêu chuyện hạn nộp/mâu thuẫn ngày; không trình bày ánh xạ 8 tiêu chí → 4 nhóm như của BTC; không nói workflow Ca 1 "kiểm tra MongoDB"; không dùng số benchmark 98,9%.

## 8. Văn phong
Theo `00_PLAN.md` §E: trung tính, câu ≤ 30 từ; "nhóm/hệ thống"; việc đã làm có mốc thời gian; mỗi ca theo Giả thuyết → Kiểm chứng → Kết quả → Diễn giải → Hạn chế; thuật ngữ theo §D.1; từ cấm §E.9. Trích bằng chứng `[E-xx]`; cần ID mới ghi `[E-NEW: mô tả]`. Tham chiếu chéo: `(xem Tài liệu 02, §6.1)`; không chép nội dung tài liệu khác quá 3 câu.

## 9. Checklist tự kiểm (chạy trước khi báo cáo)
- [ ] Front matter parse được; số chương khớp dàn ý.
- [ ] Mỗi tài liệu có Tóm tắt, Đóng góp chính, Bảng 0, Đánh giá (bảng 3 cột trạng thái), Hạn chế, Kết luận.
- [ ] Grep ID: 341409441, 339977703, 339977691, 340356283, e2835af0…, 18d1b008…, b83453ff…, nkc-685-vw8 đúng chuỗi.
- [ ] Mốc thời gian khớp nguồn (đối chiếu lại từng ô timeline).
- [ ] Không có từ cấm (grep: Atlas, Change Stream, MTTR, MTTD, SLO, tự động khắc phục, hỏng, đã sửa, dữ liệu thật, 100%).
- [ ] Không IP/hostname/email/account/instance/bucket/org ID.
- [ ] Mọi `[E-xx]` có trong `EVIDENCE_INDEX.md`.
- [ ] Độ dài trong khoảng mục tiêu (đếm từ bằng PowerShell: `(Get-Content <tệp> -Raw -Encoding utf8 -split '\s+').Count`).

## 10. Báo cáo
Kết thúc bằng tin nhắn ≤ 300 từ gồm: đường dẫn hai tệp; số từ mỗi tệp; danh sách `[E-NEW]` cần thêm; danh sách placeholder «CẦN NGƯỜI DÙNG» còn lại; mọi chỗ mã khác `00_PLAN.md`; điều chưa chắc chắn.
