---
doc_id: SMIOT-SUB-00
title: "Kế hoạch biên soạn bốn tài liệu hồ sơ nộp (mục 3, 4, 5, 11)"
project: "SMIOT Smart Farm"
version: "1.1"
date: "2026-11-07"
language: vi
owner: "principal technical editor (lập kế hoạch, không viết nội dung tài liệu)"
outputs:
  - docs/submission/01_kien_truc_giai_phap.md      # mục 3 hồ sơ, Writer A
  - docs/submission/02_kien_truc_du_lieu_mongodb.md # mục 4 hồ sơ, Writer B
  - docs/submission/03_kien_truc_observability_datadog.md # mục 5 hồ sơ, Writer C
  - docs/submission/04_mo_ta_su_co_van_hanh.md     # mục 11 hồ sơ, Writer A
shared:
  - docs/submission/EVIDENCE_INDEX.md
  - docs/submission/briefs/writer_A.md
  - docs/submission/briefs/writer_B.md
  - docs/submission/briefs/writer_C.md
status: plan
---

# Kế hoạch biên soạn bốn tài liệu hồ sơ nộp

Tài liệu này là kế hoạch, không phải nội dung nộp. Mọi sự thật dưới đây đã được đối chiếu với repo ngày 06/11/2026; chỗ nào chưa kiểm chứng được thì ghi rõ. Đường dẫn tính từ gốc repo.

## 0. Phát hiện chính khi rà soát (đọc trước)

### 0.1 Sự thật đã kiểm chứng trong repo

| # | Sự thật | Nguồn trong repo |
|---|---|---|
| F1 | Ba loại sự cố có `kind` cố định: `soil_humidity_flatline`, `false_offline`, `service_down` | `service/incident_blackbox.py:22` |
| F2 | Ánh xạ IDs trong mã/snapshot ngày 06/11 là lịch sử, không đại diện cho org Datadog hiện tại. Trạng thái hiện tại được đối chiếu trên web ngày 09/11: Ca 3 monitor `342585838`, workflow `373ed0c0-4509-4fcd-a067-f54f0becc00e` đã xuất bản/nối monitor; monitor/workflow Ca 1 và Ca 2 chưa xác minh trong org hiện tại. | Mã nguồn và xác minh UI Datadog hiện tại |
| F3 | Hộp đen: một aggregation bắt đầu từ `operational_incidents`, `$unionWith` lần lượt `incident_telemetry_evidence`, `operational_decisions`, `action_ledger`, `telemetry`; nhánh telemetry dùng `$setWindowFields` + `$shift` để đánh dấu khoảng thiếu mẫu (> 3 lần chu kỳ 30 s) | `service/incident_blackbox.py:1-15, 170-300` |
| F4 | Partial index `active_incident_by_scope` (chỉ sự cố `open/holding/recovering`); index `telemetry_by_incident_ts` có nhánh dự phòng bỏ partial filter | `service/incident_blackbox.py:39-60, 97-120` |
| F5 | `$jsonSchema` validator cho `operational_incidents`, `action_ledger` với `validationAction=warn`, `validationLevel=moderate` | `service/incident_blackbox.py:62-94, 123-148` |
| F6 | Index nghiệp vụ và Time Series tạo trong `init_db` | `service/auth.py:71-98` |
| F7 | Hình dạng document telemetry thật: `timestamp`, `meta{farm_key, source_table, measurement_type, node_id, source}`, `readings{…}`, `source{table, source, synthetic, provenance, app_received_at, incident_id?, message_id?…}` | `service/auth.py:291-304`, `service/telemetry_provenance.py:91-104`, `service/mongodb_telemetry.py:93-105` |
| F8 | Time Series tạo với `timeField=timestamp`, `metaField=meta`, `granularity=seconds` (trong script migrate) | `scripts/migrate_sqlite_telemetry_to_mongodb.py:115-135` |
| F9 | Không có `.watch(`, `start_session`, `with_transaction` trong `service/`, `pages/`, `scripts/` (grep 06/11) | grep |
| F10 | Quy tắc flatline: 10 mẫu, chênh lệch ≤ 0,01, cửa sổ 600 s | `service/telemetry_health.py:35-37, 475-513` |
| F11 | Metric app: `smiot.telemetry.status_mismatch`, `sample_age_seconds`, `fresh`, `sensor_flatline`, `samples_persisted`, `ingest_lag_ms`, `smiot.dependency.mongo.up`, `smiot.dependency.mqtt.up` | `service/telemetry_health.py:336-495`, `service/mqtt.py:307-330` |
| F12 | Probe ngoài app: `smiot.external.app_up`, `smiot.external.sample_age_seconds`, `smiot.external.mongo_up`; mở `service_down` sau 2 lần liên tiếp `app_up=0` | `scripts/smiot_external_probe.py:7-52, 202-260, 313-344` |
| F13 | Verifier CLEAR (mã hiện tại): cần ≥ 10 mẫu Node 2 tươi gắn incident, mẫu mới nhất ≤ 90 s, biên độ ≥ 0,5; chuỗi lý do trong mã vẫn ghi "six or more" | `scripts/verify_and_clear_demo_safe_mode.py:146-167` |
| F14 | LLM Observability trong mã: `LLMObs.enable(ml_app=… "smiot-smart-farm")`, nội dung vào/ra bị che; span Gemini qua `llm_observation` | `service/observability.py:50-73`, `service/ai_service.py:218-267`, `tests/test_llmobs.py` |
| F15 | Trang `/incident` và `/incident/{id}` chỉ cho admin hoặc quyền `manage_users` | `pages/incident.py:134-143, 653, 715` |
| F16 | 162 test đơn vị chạy đạt trên máy local ngày 06/11/2026 (`py -3.12 -X utf8 -m unittest discover -s tests`) | chạy trực tiếp trong phiên lập kế hoạch |
| F17 | Monitor IDs/queries xuất ngày 06/11 là snapshot tài khoản cũ; gồm Ca 1/2/3 cùng monitor dependency. Chỉ dùng làm bằng chứng lịch sử, không gán IDs đó cho org hiện tại. | `outputs/evidence/monitor_*.json` (snapshot lịch sử) |
| F18 | Workflow Ca 1 trong snapshot 06/11 có ba bước query→if→echo, nhánh `REFUSED_RESTART`/`ESCALATE_HUMAN`; chỉ là cấu hình lịch sử. JSON draft hiện tại phải import sau khi monitor chính và dữ liệu metric được xác minh. | `outputs/evidence/workflow_e2835af0-63fc-48e0-9562-2a1ee4a351d3.json` (lịch sử; không import ID cũ) |
| F19 | Diễn tập Ca 3 ngày 06/11: dừng 03:06:32Z, thấy dừng 03:06:47Z, phục hồi xác minh 03:13:30Z (418 s); `mongod`, `mosquitto` active suốt; tuổi mẫu tăng đến 406,7 s; **trường `workflow_execution_id`, `monitor_alert_time_utc`, `bits_investigation_id` để trống** | `outputs/drill_ca3_20261106T030613Z.json` |
| F20 | Diễn tập Ca 2 ngày 06/11 là lịch sử: T0 02:36:40Z; monitor cũ 339977691 trigger 02:41:51Z; execution cũ `e09175ca…`; trạng thái `recovered` khi đó chưa xác nhận. Không coi monitor/workflow này là tài nguyên live trong org hiện tại. | `outputs/round2/ca2/A3…A8`, `outputs/round2/_sync/A_status.json` |
| F21 | Hai hồ sơ Ca 2 ngày 03/11 đầy đủ: `INC-SMIOT-20261103T102822-D3B0F8A7` (Bits 1 giả thuyết xác minh, 10 bị loại; HOLD do bridge gửi, workflow bị khử trùng lặp) và `INC-SMIOT-20261103T114321-BD19A22C` (Bits sửa kết luận sau phản hồi; 7 mẫu phục hồi 39,3–41,0%) | `docs/INC-SMIOT-*_EVIDENCE.md` |
| F22 | Backup logic + restore drill: 154.618/154.618 mẫu Time Series, 1/1 incident; chưa có PITR, chưa restore EBS | `docs/MONGODB_BACKUP_RESTORE_DRILL_20261103.md` |

### 0.2 Mâu thuẫn giữa tài liệu cũ và mã/hiện trạng (writer không được chép tài liệu cũ)

| # | Tài liệu cũ nói | Hiện trạng | Cách xử lý trong hồ sơ |
|---|---|---|---|
| M1 | Story pack (`Kien_truc_giai_phap_MongoDB_Datadog.md` §2.2) dùng mẫu `readings.soil_humidity`, `source.sequence` | Mã ghi `meta.source_table`, `meta.source`; hộp đen đọc `readings.soil_hum` | Dùng hình dạng theo F7; document mẫu lấy từ lệnh chỉ-đọc (mục H) |
| M2 | Story pack và `build_docs.py` kể "hai kịch bản" | Nay có ba ca, Ca 1 là mới | Dùng ba ca và tên chuẩn ở mục D |
| M3 | `DATADOG_MULTI_CAUSE_SCENARIOS.md` ghi chưa có diễn tập outage, kết nối SSM role lỗi `sts:AssumeRole` | Các execution Ca 3 04/11 và 06/11 là lịch sử; workflow hiện tại dùng action AWS SSM qua connection đã test, không dùng SSM AssumeRole workflow cũ | Coi tài liệu đó là lịch sử; không mô tả role lỗi là trạng thái hiện tại |
| M4 | `DATADOG_GUARDED_RECOVERY.md` yêu cầu drill lại nhánh outage sau khi cài helper | Diễn tập 06/11 phục hồi được nhưng **không ghi tác nhân start** (workflow hay người) | Viết "phục hồi đã xác minh bằng HTTP 200 và mẫu Mongo mới"; chỉ nói "workflow đã start" khi người dùng cung cấp execution ID (E-82) |
| M5 | `DECLARATIONS.md` ghi "không có LLM Observability span" | Mã bật LLMObs; người dùng xác nhận span Gemini trên EC2 | Tài liệu 3 mô tả LLMObs; cần ảnh chụp (E-84). Báo người dùng sửa `DECLARATIONS.md` |
| M6 | Playbook ghi verifier "7 mẫu"; hồ sơ D3B0F8A7 ghi 6 mẫu | Mã hiện tại đòi ≥ 10 mẫu (F13) | Nêu số mẫu **quan sát được** của từng lần chạy; ngưỡng hiện tại = 10 theo mã; không nói ngưỡng của phiên bản cũ |
| M7 | README phần lịch sử nhắc "MongoDB Atlas" (dòng 53, 111) | Hệ thống chạy Community self-managed | Không trích các đoạn đó; báo người dùng (rủi ro công cụ đọc tự động thấy chữ "Atlas") |
| M8 | Tài liệu cũ nói Ca 1 monitor/workflow đã có hoặc chưa có | IDs 341409441/e2835af0… thuộc snapshot/tài khoản cũ; hiện trạng org mới chưa xác minh monitor/workflow Ca 1 | Ghi Ca 1 là draft/chưa live cho tới khi xác minh và import trong org hiện tại |
| M9 | README/dashboard nói có SLO widget và SLO 7 ngày | `outputs/evidence/README.md`: route SLO trả Page Not Found ngày 06/11 | Không tuyên bố SLO |
| M10 | Bits "164FBE41" (người dùng nêu) | Không có trong repo; repo có 3de8802a… (BD19A22C) và 008cc971… (D3B0F8A7) | Placeholder «CẦN NGƯỜI DÙNG: mã incident đầy đủ và link Bits của 164FBE41» |
| M11 | Playbook/Codex nói "5 monitor SMIOT" | Nay 6 monitor SMIOT + 3 monitor APM nền tự tạo | Dùng "6 monitor SMIOT" theo F17 |
| M12 | Benchmark 240 mẫu/23,701 ms vs 2 dòng/2,712 ms | Chỉ có trong `SMIOT_MEMORY.json` và story pack, không có file kết quả gốc | Chỉ dùng sau khi chạy lại `scripts/mongo_timeseries_benchmark.py` (mục H); nếu không chạy, ghi "một lần đo, chưa lưu kết quả gốc" |

### 0.3 Chỗ thiếu bằng chứng lớn nhất
1. Ca 1 chưa có lần diễn tập có incident thật trong MongoDB (theo evidence hiện có).
2. Ca 3 ngày 06/11 thiếu thời điểm monitor Alert, execution ID và log `smiot.guarded_recovery`.
3. Ca 2 ngày 06/11 thiếu xác nhận `recovered`, HOLD/CLEAR trong `action_ledger`.
4. Không có số liệu MongoDB thật (đếm bản ghi, index thật, explain IXSCAN) cho tài liệu 2.
5. Không có ảnh LLM Observability và ảnh `/incident` từng ca.

---

## A. Phân tích người chấm và quy tắc thiết kế

### A.1 Ban giám khảo con người
- **Đọc lướt (30 giây đầu)** tìm: (1) bài toán là gì và vì sao thật; (2) MongoDB dùng tính năng gì cụ thể; (3) Datadog dùng gì cụ thể; (4) có sự cố được phát hiện–điều tra–xử lý trọn vẹn không; (5) có trung thực về giới hạn không. Họ đọc tiêu đề, tóm tắt, hình đầu tiên, bảng.
- **Đọc kỹ** (chung kết, câu hỏi): kiểm ID monitor/workflow, mở link, đối chiếu mã; hỏi "phần nào làm trong 17–31/10", "dữ liệu thật hay tổng hợp", "tự động hay thủ công".
- Rủi ro mất điểm: tuyên bố quá mức (một câu sai làm mất tin cậy cả hồ sơ), mâu thuẫn giữa tài liệu, thuật ngữ trôi.

### A.2 Công cụ đọc tự động (nếu có)
- Cần cấu trúc ổn định: front matter YAML, tiêu đề đánh số cố định, bảng "Tuyên bố – Bằng chứng – Trạng thái", ID bằng chứng `[E-xx]` dẫn tới một danh mục chung.
- Cần thuật ngữ và ID nhất quán tuyệt đối giữa 4 tài liệu (cùng chuỗi `339977691`, cùng tên ca).
- Tránh chữ gây hiểu nhầm khi so khớp từ khóa: không viết "Atlas", "Change Streams", "MTTR" kể cả trong câu phủ định ở phần thân; chỉ nêu một lần trong mục "Hạn chế và phạm vi" dưới dạng "không sử dụng".

### A.3 Quy tắc thiết kế rút ra
1. Mỗi tài liệu mở bằng: front matter → **Tóm tắt** (≤ 200 từ) → **Đóng góp chính** (3–5 gạch, mỗi gạch có `[E-xx]`) → bảng **Đọc nhanh**.
2. Mỗi tuyên bố kỹ thuật có `[E-xx]`; câu không có bằng chứng phải viết dưới dạng thiết kế/dự kiến và gắn trạng thái.
3. Mỗi tài liệu có đúng một bảng "Tuyên bố – Bằng chứng – Trạng thái" ở chương Đánh giá, trạng thái ∈ {`Đã kiểm chứng`, `Chưa xác minh`, `Cần người dùng`}.
4. Mỗi tài liệu có chương "Hạn chế và phạm vi" riêng, không rải rác.
5. Tiêu đề chương đánh số cố định theo dàn ý mục C (không đổi số khi biên tập).
6. Hình/bảng đánh số "Hình 2.1", "Bảng 3.2"; mỗi hình có câu mô tả bằng chữ (cho người và máy không xem được ảnh).
7. Tài liệu 4 là nguồn chuẩn cho mốc thời gian ca; tài liệu 3 chuẩn cho định nghĩa monitor/workflow; tài liệu 2 chuẩn cho collection/trường/index; tài liệu 1 chỉ tóm tắt và trỏ chéo.

---

## B. Ma trận tiêu chí → tài liệu → chương → bằng chứng

> **Nhãn suy luận:** việc ghép 8 tiêu chí của thể lệ mục 8.1 vào 4 nhóm trên trang chính là **suy luận của đội**, BTC không công bố ánh xạ. Trong hồ sơ nộp, không trình bày ánh xạ này như của BTC; nếu dùng thì ghi "(suy luận của đội)".

| Nhóm (trang chính) | Tiêu chí 8.1 (ghép: suy luận) | Tài liệu chính | Chương/mục | Bằng chứng |
|---|---|---|---|---|
| Sáng tạo 30% | (6) Sáng tạo, AI hợp lý | 01 §2, §4.6; 03 §7–8; 04 §5 | Ba lớp lỗi → ba hành động, có hành động "từ chối"; Bits có sửa kết luận; LLMObs che nội dung | E-16, E-55, E-41, E-19, E-84 |
| Kỹ thuật 30% | (2) MongoDB | 02 toàn bộ | §3–§8 | E-12, E-16, E-08, E-42, E-80 |
| Kỹ thuật 30% | (3) Datadog | 03 toàn bộ | §2–§8 | E-50…E-55, E-29, E-23, E-24 |
| Kỹ thuật 30% | (5) Kiến trúc, tin cậy, bảo trì | 01 §3, §6; 02 §8; 03 §5 | guard, idempotency, validator, test, backup | E-24, E-21, E-16, E-30, E-42 |
| Tác động 30% | (1) Bài toán gắn thực tế | 01 §1; 04 §1 | Dữ liệu không đáng tin → quyết định tưới/thu hoạch sai | E-18, E-40 |
| Tác động 30% | (4) Luồng phát hiện–điều tra–xử lý | 04 toàn bộ; 01 §5 | Ba ca × 6 câu | E-40, E-41, E-56, E-59, E-81, E-82 |
| Tác động 30% | (7) Tác động vận hành | 04 §5; 01 §1 | Chặn tưới khi dữ liệu không tin cậy (bản ghi `BLOCKED_HOLD`); không restart oan | E-40, E-55 |
| Trình bày 10% | (8) MVP, tài liệu, video | cả 4 + định dạng (mục F) | Front matter, mục lục, nhất quán | E-17, E-83 |

---

## C. Đặc tả từng tài liệu

Quy ước độ dài: số từ tiếng Việt phần thân, không tính bảng phụ lục.

### C.1 Tài liệu 01 — Kiến trúc giải pháp và ứng dụng (mục 3) — Writer A
- **Tệp:** `docs/submission/01_kien_truc_giai_phap.md`; `doc_id: SMIOT-SUB-01`.
- **Mục đích:** cho người đọc thấy toàn cảnh hệ thống và lý do thiết kế trong 5 phút; trỏ sang 02/03/04 cho chi tiết.
- **Độc giả:** giám khảo đọc lướt; giám khảo kỹ thuật kiểm kiến trúc.
- **Độ dài:** 3.500–4.500 từ.
- **Dàn ý:**
  - Tóm tắt; Đóng góp chính; Bảng 0 "Đọc nhanh".
  - 1 Đặt vấn đề: 1.1 Bối cảnh nhà kính dưa lưới; 1.2 Câu hỏi vận hành ("dữ liệu còn đủ tin cậy để quyết định tưới/thu hoạch không?"); 1.3 Ba lớp lỗi khác bản chất cần ba phản ứng khác nhau; 1.4 Phạm vi (dữ liệu tổng hợp, PLC ảo, một EC2).
  - 2 Yêu cầu và nguyên tắc thiết kế: R1 truy vết theo `incident_id`; R2 hành động nhỏ nhất; R3 fail-closed khi bằng chứng mơ hồ; R4 phục hồi chứng minh bằng dữ liệu đọc lại; R5 chia vai Datadog/MongoDB/app; R6 giữ cardinality metric thấp.
  - 3 Kiến trúc tổng thể: 3.1 Sơ đồ triển khai; 3.2 Thành phần và trách nhiệm; 3.3 Ranh giới tin cậy và quyền tối thiểu; 3.4 Failure domain.
  - 4 Kiến trúc ứng dụng: 4.1 Mô-đun (`main.py`, `pages/`, `service/`, `scripts/`); 4.2 Luồng ingest; 4.3 Watchdog sức khỏe telemetry; 4.4 Vòng đời sự cố; 4.5 Verifier và probe ngoài app; 4.6 Trang `/incident` (admin) là bảng điều hướng; 4.7 Trợ lý AI và an toàn khi lỗi.
  - 5 Luồng phát hiện–điều tra–xử lý tổng quát (tóm tắt ba ca, trỏ 04).
  - 6 Độ tin cậy và khả năng bảo trì: guard, lock, cooldown, idempotency theo `command_id`, validator `warn`, 162 test, backup/restore, quy trình triển khai có rollback.
  - 7 Đánh giá: bảng Tuyên bố – Bằng chứng – Trạng thái.
  - 8 Hạn chế và phạm vi.
  - 9 Kết luận.
  - Phụ lục A: Khai báo thành phần có từ trước 17/10 («CẦN NGƯỜI DÙNG»); Phụ lục B: Công cụ AI đã dùng; Tài liệu tham khảo.
- **Hình/bảng bắt buộc:** Hình 3.1 sơ đồ triển khai (Mermaid `flowchart`: người vận hành → Nginx → app; publisher → Mosquitto ↔ app; app ↔ MongoDB; app/probe → Agent → Datadog; riêng Ca 3: Datadog workflow → AWS SSM action → guarded start `smiot.service`); Hình 4.1 sequence ingest; Hình 5.1 vòng phát hiện–điều tra–xử lý–xác minh; Bảng 3.1 thành phần; Bảng 5.1 ba ca × (lớp lỗi, tín hiệu, hành động, bằng chứng phục hồi); Bảng 7.1 tuyên bố–bằng chứng.
- **Điểm hay (chỉ tuyên bố kiểm chứng được):**
  1. Ba lớp lỗi → ba phản ứng khác nhau, trong đó có phản ứng **từ chối** restart (Ca 1) [E-16, E-55].
  2. Hành động phục hồi duy nhất được phép trên host là `systemctl start smiot.service`, có allowlist, lock, cooldown 300 s, kiểm đĩa và dependency trước [E-24, E-43].
  3. "Phục hồi" được định nghĩa bằng dữ liệu đọc lại (HTTP 200 + mẫu Mongo mới ≤ 180 s), không bằng việc lệnh chạy xong [E-59, E-43].
  4. Chia vai rõ: Datadog điều tra, MongoDB đo tác động, app điều hướng [E-17].
  5. Nhãn dữ liệu tổng hợp nằm ngay trong document (`source.synthetic`, `meta.source`) [E-13].
- **Hạn chế bắt buộc nêu:** một EC2 (app + MongoDB chung failure domain); dữ liệu tổng hợp; PLC ảo; Ca 1 chưa diễn tập (nếu đến lúc nộp vẫn chưa); tác nhân start Ca 3 ngày 06/11 chưa xác minh.

### C.2 Tài liệu 02 — Kiến trúc dữ liệu và data model trên MongoDB (mục 4) — Writer B
- **Tệp:** `docs/submission/02_kien_truc_du_lieu_mongodb.md`; `doc_id: SMIOT-SUB-02`.
- **Mục đích:** chứng minh MongoDB được chọn và dùng theo bài toán, có số liệu thật.
- **Độc giả:** giám khảo MongoDB; người kiểm mã.
- **Độ dài:** 5.000–6.500 từ.
- **Dàn ý:**
  - Tóm tắt; Đóng góp chính; Bảng 0 "Đọc nhanh" (phiên bản, chế độ, collection chính, tính năng dùng, tính năng không dùng).
  - 1 Đặt vấn đề dữ liệu: 1.1 Hai loại dữ liệu (chuỗi thời gian khối lượng lớn; hồ sơ vòng đời sự cố/hành động); 1.2 Câu hỏi truy vấn Q1–Q5 (mẫu mới nhất theo farm/node; cửa sổ quanh sự cố; sự cố đang mở theo phạm vi; timeline hợp nhất; độ phủ/GDD).
  - 2 Triển khai và hệ quả thiết kế: Community 8.0 tự quản, standalone; không transaction → idempotency bằng `command_id` + máy trạng thái; không change stream → watchdog/polling.
  - 3 Data model: 3.1 Sơ đồ quan hệ; 3.2 Bảng collection (mục đích, khóa, trường, nơi ghi `file:dòng`, mẫu truy vấn); 3.3 Document mẫu thật (ẩn giá trị nhạy cảm); 3.4 Lý do nhúng/tham chiếu; 3.5 Gắn sự cố với lô theo hiệu lực thời gian (`lot_sensor_assignments.valid_from`).
  - 4 Time Series `telemetry`: tùy chọn, chiều `meta`, chỉ mục phụ, hệ quả với backup (bucket nội bộ).
  - 5 Chỉ mục và ràng buộc: 5.1 Bảng index; 5.2 Partial index; 5.3 `$jsonSchema` chế độ cảnh báo; 5.4 Explain trước/sau.
  - 6 Aggregation: 6.1 Hộp đen `$unionWith` 4 nhánh; 6.2 Phát hiện khoảng thiếu mẫu bằng `$setWindowFields`/`$shift`; 6.3 Độ phủ và GDD (`service/mongodb_showcase.py`); 6.4 Truy vấn tác động (lô ảnh hưởng, giờ dữ liệu không đáng tin).
  - 7 MongoDB trong luồng sự cố: trả lời câu 4 và câu 6 của hồ sơ sự cố.
  - 8 Vận hành dữ liệu: backup logic, restore drill, quyền tối thiểu (user đọc cho Datadog, tắt thu schema để không cần quyền bucket), DBM.
  - 9 Đánh giá: bảng số đo (đếm, kích thước, explain) + bảng Tuyên bố – Bằng chứng – Trạng thái.
  - 10 Hạn chế và phạm vi. 11 Kết luận. Phụ lục: lệnh chỉ-đọc đã chạy và kết quả.
- **Hình/bảng bắt buộc:** Hình 3.1 `erDiagram`; Hình 6.1 sơ đồ pipeline hộp đen (flowchart các nhánh `$unionWith`); Bảng 3.2 collection; Bảng 5.1 index; Bảng 6.1 stage pipeline; Bảng 9.1 số đo; Bảng 9.2 tuyên bố–bằng chứng.
- **Điểm hay:**
  1. Một aggregation duy nhất hợp nhất 5 nguồn thành timeline sự cố [E-16].
  2. Khoảng thiếu mẫu được tính ngay trong DB bằng window function [E-16].
  3. Partial index chỉ cho sự cố đang mở [E-16].
  4. Validator `warn/moderate` bảo vệ chất lượng mà không chặn ghi khi vận hành [E-16].
  5. Backup Time Series qua API logic và restore drill đếm khớp [E-42].
- **Hạn chế bắt buộc:** standalone; một EC2; validator chỉ cảnh báo; benchmark một lần; chưa PITR/EBS restore; dữ liệu tổng hợp; GDD chưa hiệu chuẩn nông học.

### C.3 Tài liệu 03 — Kiến trúc observability trên Datadog (mục 5) — Writer C
- **Tệp:** `docs/submission/03_kien_truc_observability_datadog.md`; `doc_id: SMIOT-SUB-03`.
- **Mục đích:** chứng minh tín hiệu được thiết kế theo câu hỏi vận hành, monitor có thể hành động, điều tra liên kết theo `incident_id`.
- **Độc giả:** giám khảo Datadog.
- **Độ dài:** 5.000–6.500 từ.
- **Dàn ý:**
  - Tóm tắt; Đóng góp chính; Bảng 0 "Đọc nhanh" (site US1, service, env, sản phẩm Datadog đã dùng).
  - 1 Đặt vấn đề quan sát: "app sống" ≠ "dữ liệu tươi" ≠ "hiển thị đúng".
  - 2 Kiến trúc thu thập: Agent trên EC2; DogStatsD; log JSON (`deploy/datadog/smiot-logs.yaml`, `incident_events.jsonl`, `guarded_recovery.jsonl`); APM `ddtrace`; MongoDB integration + DBM; systemd; probe ngoài app; LLM Observability.
  - 3 Mô hình tín hiệu: 3.1 Bảng metric (tên, kiểu, tag, nguồn `file:dòng`); 3.2 Quy tắc tag và cardinality; 3.3 Khóa tương quan (`@incident.id`, `@farm.key`, `@node.id`, trace ID).
  - 4 Monitor: 4.1 Bảng monitor SMIOT, phân biệt IDs hiện tại đã xác minh với snapshot lịch sử; 4.2 Thiết kế đối chứng Ca 1 (IDs cũ 341409441/339977703 chỉ là lịch sử, current IDs cần xác minh); 4.3 Ba monitor APM nền (không thuộc ca).
  - 5 Workflow và hành động có guard: 5.1 Ba workflow theo trạng thái (Ca 1/Ca 2 là JSON draft chưa live; Ca 3 đang published); 5.2 AWS SSM action/guard Ca 3; 5.3 nhánh fail-closed; 5.4 rate limit và điều kiện xác minh trước khi CLEAR.
  - 6 Dashboard `nkc-685-vw8`.
  - 7 Điều tra: 7.1 Pivot Logs/APM theo `incident_id`; 7.2 Bits AI (chỉ Ca 2; kết quả và lần sửa kết luận); 7.3 Giới hạn của Bits.
  - 8 LLM Observability cho trợ lý Gemini.
  - 9 Đánh giá: quan sát từ các lần diễn tập (thời điểm thực đo, một lần) + bảng Tuyên bố – Bằng chứng – Trạng thái.
  - 10 Hạn chế và phạm vi. 11 Kết luận. Phụ lục: bảng ID và đường dẫn.
- **Hình/bảng bắt buộc:** Hình 2.1 luồng tín hiệu vào Datadog; Hình 5.1 cây quyết định guard (flowchart G0…G7, đánh dấu nhánh đề xuất); Bảng 3.1 metric; Bảng 4.1 monitor; Bảng 5.1 workflow; Bảng 9.1 tuyên bố–bằng chứng.
- **Điểm hay:**
  1. Mô hình monitor đối chứng: khi tài nguyên hiện tại được xác minh, phân biệt "dữ liệu vẫn tươi" và "hiển thị sai"; IDs trong ảnh cũ là bằng chứng lịch sử.
  2. Metric `status_mismatch` đo trực tiếp sự không nhất quán giữa UI và dữ liệu [E-14].
  3. Probe ngoài tiến trình app để quan sát khi app dừng [E-23].
  4. Ca 3 hiện gọi runbook SSM định nghĩa trước với guard; workflow Ca 1/Ca 2 chưa được tuyên bố live cho tới khi import/xác minh.
  5. `incident_id` nằm ở log/trace/MongoDB, không ở tag metric [E-40, E-43].
- **Hạn chế bắt buộc:** monitor/workflow Ca 1 và Ca 2 chưa xác minh trong org hiện tại; Ca 3 workflow đã published và nối monitor nhưng mới xác minh bằng DryRun (skip khi app active), chưa chứng minh nhánh start thật; IDs từ snapshot 08/11 và bằng chứng 06/11 là lịch sử, không import nguyên xi.

### C.4 Tài liệu 04 — Mô tả sự cố và tình huống vận hành được trình diễn (mục 11) — Writer A
- **Tệp:** `docs/submission/04_mo_ta_su_co_van_hanh.md`; `doc_id: SMIOT-SUB-04`.
- **Mục đích:** trình bày ba ca như ba thí nghiệm có giả thuyết, quy trình, kết quả, giới hạn; trả lời 6 câu cho mỗi ca.
- **Độc giả:** mọi giám khảo; nguồn chuẩn cho video/thuyết trình.
- **Độ dài:** 5.500–7.000 từ.
- **Dàn ý:**
  - Tóm tắt; Đóng góp chính; Bảng 0 tổng quan ba ca (mức độ hoàn thiện bằng chứng từng ca).
  - 1 Phương pháp diễn tập: nguyên tắc chung (một ca mỗi lần, snapshot, dữ liệu tổng hợp, mốc UTC + ICT, không tạo bản ghi giả); khung 6 câu; chia vai Datadog/MongoDB/app; tiêu chí "xong".
  - 2 Ca 1 — Báo offline sai. 3 Ca 2 — Độ ẩm đất Node 2 đứng yên. 4 Ca 3 — `smiot.service` dừng. Mỗi chương ca có tiểu mục cố định: x.1 Giả thuyết và kịch bản kích hoạt; x.2 Phát hiện (Datadog); x.3 Điều tra (Datadog); x.4 Quyết định và hành động (lý do, phương án loại trừ); x.5 Tác động trên dữ liệu (MongoDB); x.6 Phục hồi và bằng chứng; x.7 Dòng thời gian (UTC/ICT); x.8 Bảng 6 câu; x.9 Giới hạn.
  - 5 So sánh ba ca (triệu chứng, lớp lỗi, hành động đúng, hành động sai bị loại).
  - 6 Trình diễn trên `/incident` (admin): người xem thấy gì, cách truy cập «CẦN NGƯỜI DÙNG: tài khoản giám khảo».
  - 7 Đánh giá: bảng Tuyên bố – Bằng chứng – Trạng thái. 8 Hạn chế và phạm vi. 9 Kết luận.
- **Hình/bảng bắt buộc:** Hình 1.1 khung 6 câu và chia vai; Hình 2.1/3.1/4.1 sequence từng ca; Bảng x.7 timeline; Bảng x.8 6 câu; Bảng 5.1 so sánh.
- **Điểm hay:**
  1. Ca 1 coi việc **không** restart là kết quả đúng, có monitor đối chứng [E-55, E-50].
  2. Ca 2: HOLD trước, CLEAR chỉ sau verifier đọc mẫu Mongo [E-41, E-22].
  3. Một `incident_id` xuyên Datadog (log/trace) và MongoDB (incident, ledger) [E-40].
  4. Bits AI được dùng như công cụ điều tra có thể sai và đã được sửa (BD19A22C) — dùng AI hợp lý [E-41].
  5. Ca 3: dependency khỏe suốt thời gian dừng (đo được), phục hồi xác minh bằng mẫu Mongo mới [E-59].
- **Dữ liệu từng ca được phép dùng:** Ca 2: hồ sơ 03/11 (F21) và lần 06/11 (F20) là lịch sử; không dùng IDs cũ như tài nguyên hiện tại. Ca 3: execution 04/11 và drill 06/11 (F19) là lịch sử; DryRun workflow hiện tại chỉ xác minh kết nối/nhánh skip, không chứng minh start thật. Ca 1: cấu hình monitor/workflow trong F17/F18 là snapshot lịch sử; kết quả diễn tập cần bằng chứng mới.

---

## D. Quy tắc nhất quán xuyên 4 tài liệu

### D.1 Bảng thuật ngữ chuẩn

| Dùng | Thuật ngữ gốc | Không dùng |
|---|---|---|
| sự cố | incident | biến cố, lỗi (khi nói về bản ghi) |
| mã sự cố | `incident_id` (`INC-SMIOT-<UTC>-<8HEX>`) | ID lỗi |
| giám sát/monitor | Datadog monitor | cảnh báo (khi nói về đối tượng monitor) |
| quy trình tự động | Datadog Workflow (Workflow Automation) | kịch bản tự động |
| lượt chạy quy trình | workflow execution | — |
| bộ chạy hành động riêng | Private Action Runner | — |
| điều kiện chặn | guard | khóa |
| trạng thái an toàn | safe mode / HOLD | khóa bơm |
| gỡ trạng thái an toàn | CLEAR | mở khóa |
| bộ xác minh phục hồi | recovery verifier (`scripts/verify_and_clear_demo_safe_mode.py`) | — |
| đứng số đo | flatline | treo cảm biến, cảm biến hỏng |
| lệch trạng thái hiển thị | status mismatch | — |
| mẫu/bản tin telemetry | telemetry sample | dữ liệu cảm biến thật |
| dữ liệu tổng hợp | synthetic data | dữ liệu giả, dữ liệu thật |
| PLC ảo | virtual PLC | PLC, bơm (không kèm "ảo") |
| hộp đen sự cố | incident black box (`/incident`) | — |
| điều tra Bits AI | Bits AI Investigation | AI tự sửa |
| tự quản | self-managed | on-premise |
| bộ sưu tập chuỗi thời gian | Time Series collection | — |
| chỉ mục một phần | partial index | — |

### D.2 Tên ca và trạng thái Datadog hiện tại
- **Ca 1 — Báo offline sai** (`false_offline`) · monitor chính và workflow trong org hiện tại: **chưa xác minh/chưa live**. `341409441`, `339977703`, `e2835af0…` chỉ là IDs lịch sử từ tài khoản cũ.
- **Ca 2 — Độ ẩm đất Node 2 đứng yên** (`soil_humidity_flatline`) · monitor và workflow trong org hiện tại: **chưa xác minh/chưa live**. `339977691`, `18d1b008…` chỉ là IDs lịch sử từ tài khoản cũ.
- **Ca 3 — `smiot.service` dừng** (`service_down`) · monitor hiện tại `342585838` “SMIOT | smiot.service inactive” · workflow hiện tại `373ed0c0-4509-4fcd-a067-f54f0becc00e` “SMIOT | Guarded EC2 app recovery” (published, monitor-linked; DryRun qua SSM thành công, nhánh start thật chưa xác minh).
- IDs cũ `340356283`, `339990226`, `339990232` không được gán là current nếu chưa kiểm tra lại trên web. Dashboard `nkc-685-vw8` và site/service/env cần xác minh riêng trong org mới trước khi đưa thành thông tin hiện tại.
- Lần đầu nhắc trong mỗi tài liệu: viết đầy đủ "Ca 2 — Độ ẩm đất Node 2 đứng yên"; sau đó "Ca 2".
- Thời gian: ISO 8601 UTC, kèm ICT trong bảng timeline (`2026-11-06 02:41:51Z / 09:41:51 ICT`).
- Không ghi: org ID, account AWS, instance ID, tên bucket, IP, hostname demo, email. URL demo viết `<URL_DEMO>` («CẦN NGƯỜI DÙNG: quyết định có ghi hostname không, vì hostname chứa IP công khai»).

### D.3 Trích bằng chứng
- Cú pháp `[E-xx]` (một hoặc nhiều: `[E-16, E-40]`), trỏ tới `docs/submission/EVIDENCE_INDEX.md`.
- Mã nguồn trích kèm `file:dòng` trong bảng, không dán đoạn mã dài (tối đa 15 dòng/khối, chỉ khi cần).
- Writer **không sửa** `EVIDENCE_INDEX.md`; cần ID mới thì dùng `[E-NEW: mô tả]` và liệt kê trong báo cáo.

### D.4 Con số được phép dùng (và nguồn)

| Con số | Ý nghĩa | Nguồn | Cách viết bắt buộc |
|---|---|---|---|
| 10 mẫu, 0,01, 600 s | Quy tắc phát hiện flatline | E-14 | "theo mã hiện tại" |
| ≥ 10 mẫu, ≤ 90 s, biên độ ≥ 0,5 | Điều kiện verifier CLEAR | E-22 | "theo mã hiện tại" |
| 2 lần liên tiếp, chu kỳ 30 s | Probe mở `service_down` | E-23, E-44 | — |
| < 85% đĩa, cooldown 300 s, ≤ 180 s tuổi mẫu | Guard Ca 3 | E-24, E-43, E-59 | — |
| 1/300 s | Rate limit trong workflow Ca 1 lịch sử; phải xác minh lại khi dựng JSON mới | E-55 (lịch sử) | — |
| 311 s; 206 s | T0→trigger monitor; normal→OK (Ca 2, 06/11) | E-56 | "một lần quan sát" |
| 418 s; 406,7 s | dừng→phục hồi xác minh; tuổi mẫu lớn nhất (Ca 3, 06/11) | E-59 | "một lần quan sát" |
| 1 xác minh / 10 bị loại | Bits D3B0F8A7 | E-40 | — |
| 7 mẫu 39,3–41,0% | Phục hồi BD19A22C | E-41 | — |
| 6 mẫu 39,5–40,6% | Phục hồi D3B0F8A7 | E-40 | — |
| 154.618/154.618; 1/1 | Restore drill 03/11 | E-42 | — |
| 162 test đạt | Chạy local 06/11 | E-30 | ghi ngày |
| 6 monitor SMIOT | — | E-50 | — |
| 8 widget | Dashboard, đếm 04/11 | E-03 | ghi ngày; chụp lại trước khi dùng |
| Benchmark 98,9% | — | E-04 | **Không dùng** trừ khi chạy lại (H.2) |

Cấm: MTTD, MTTR, "% giảm cảnh báo", "đạt SLO", ước tính tiết kiệm nước/chi phí, điểm tự chấm. Thời lượng một lần diễn tập được nêu như quan sát đơn lẻ, không gọi là MTTD/MTTR.

### D.5 Thứ tự đọc khuyến nghị và tham chiếu chéo
- Thứ tự: 01 → 04 → 02 → 03 (toàn cảnh → ba ca → dữ liệu → quan sát). Ghi câu này trong Bảng 0 của mỗi tài liệu.
- Tham chiếu chéo dạng `(xem Tài liệu 02, §6.1)`; không chép lại nội dung chi tiết của tài liệu khác quá 3 câu.
- Nguồn chuẩn: mốc thời gian → 04; định nghĩa monitor/workflow → 03; collection/trường/index → 02; sơ đồ tổng thể và nguyên tắc → 01.

---

## E. Văn phong học thuật tiếng Việt

1. **Giọng văn:** trung tính, mô tả – lập luận – kiểm chứng. Câu ngắn (≤ 30 từ), một ý một câu.
2. **Xưng hô:** "nhóm", "hệ thống", "SMIOT"; không dùng "chúng tôi cam kết", "bạn".
3. **Thì:** việc đã làm dùng "đã" + mốc thời gian; thiết kế dùng hiện tại ("hệ thống ghi…"); việc chưa làm dùng "chưa" hoặc "dự kiến", không dùng tương lai khẳng định.
4. **Tóm tắt:** 4 câu theo thứ tự bối cảnh – phương pháp – kết quả chính (có số và `[E-xx]`) – giới hạn.
5. **Mỗi ca/thí nghiệm:** Giả thuyết → Cách kiểm chứng → Kết quả quan sát → Diễn giải → Hạn chế.
6. **Bảng/hình:** chú thích trên bảng ("Bảng 3.2. …"), dưới hình ("Hình 3.1. …"); mỗi hình có đoạn mô tả bằng chữ ngay sau.
7. **Công thức:** viết dạng chữ hoặc code inline, ví dụ `gap_seconds > 3 × 30`; `GDD_ngày = max(0, T_tb − 10)`.
8. **Thuật ngữ tiếng Anh:** lần đầu ghi "tiếng Việt (gốc)", sau đó dùng một dạng.
9. **Từ cấm:** "đột phá", "hoàn hảo", "toàn diện", "tối ưu nhất", "thông minh vượt trội", "đảm bảo 100%", "tự động khắc phục" (trừ khi có execution ID chứng minh và ghi rõ phạm vi), "tự phục hồi", "AI tự sửa", "chắc chắn thắng", "production-ready", "dữ liệu thật", "cảm biến hỏng", "đã sửa cảm biến", "real-time" (dùng "định kỳ 30 s"), "Atlas", "Change Streams", "MTTR", "MTTD", "SLO đạt".
10. **Không** đưa mâu thuẫn hạn nộp vào tài liệu nộp.

---

## F. Định dạng đầu ra và công cụ

### F.1 Kiểm tra môi trường (06/11/2026, máy local)

| Công cụ | Trạng thái |
|---|---|
| Python 3.12 + `python-docx` | **Có** |
| PyMuPDF (`fitz`), `reportlab`, `openpyxl` | **Có** |
| `markdown` (Python), `pypandoc`, `docx2pdf`, `weasyprint`, `pdf2image` | **Không có** |
| `pandoc`, LibreOffice/`soffice`, `wkhtmltopdf`, `git` trên PATH | **Không có** |
| Node v24 | **Có** |
| `node_modules` trong `outputs/20261104_smiot_story_pack/`: `docx`, `marked`, `@viz-js/viz`, `sharp`, `@napi-rs/canvas`, `pdf-lib`, `playwright` | **Có** (thư mục tồn tại; trình duyệt Playwright chưa thấy trong thư mục mặc định → chưa xác minh) |
| Microsoft Word (`WINWORD.EXE`, Office16) | **Có tệp**; xuất PDF qua COM **chưa thử**; `pywin32` không có (dùng COM qua PowerShell) |
| `build_docs.py` | Dùng `python-docx`, đã có hàm bìa, đầu/chân trang, số trang (`fldSimple PAGE`), bảng tô màu, chèn ảnh; nội dung cũ (hai kịch bản) **không dùng lại** |
| `render_pdf.py` | Chỉ chuyển PDF → PNG để QA; cần `pdf2image` (không có) → hiện chạy không được; thay bằng PyMuPDF |

### F.2 Quy trình đề xuất (giai đoạn sau khi 4 bản Markdown được duyệt; không thuộc việc của writer)
1. Nguồn chuẩn: 4 tệp Markdown trong `docs/submission/`.
2. Hình: Mermaid trong Markdown (GitHub hiển thị được). Khi xuất DOCX, agent chính chuyển từng hình sang DOT → `@viz-js/viz` → SVG → `sharp` → PNG trong `docs/submission/figures/`.
3. DOCX: script Node dùng `marked` (đọc token) + `docx` (dựng tài liệu) **hoặc** mở rộng `build_docs.py` (python-docx) với trình đọc Markdown tối giản. Mỗi DOCX gồm: bìa (tên dự án, tên tài liệu, mục hồ sơ, phiên bản, ngày, nhãn "Dữ liệu tổng hợp"), trường TOC (Word cập nhật khi mở), đầu trang "SMIOT · Hồ sơ Mini Hackathon MongoDB x Datadog · Mục N", chân trang số trang, kiểu Heading 1–3 đánh số, chú thích bảng/hình.
4. PDF: Word COM `ExportAsFixedFormat` (cần thử 1 lần); dự phòng: in PDF thủ công từ Word.
5. QA: PyMuPDF render trang → PNG, kiểm tràn bảng, font tiếng Việt, mục lục.
6. Chạy quét secret/IP/email trên Markdown và DOCX trước khi nộp (mục I).

---

## G. Phân công writer

| Writer | Tài liệu | Tệp được phép tạo/sửa | Lý do ghép |
|---|---|---|---|
| A | 01 + 04 | `docs/submission/01_kien_truc_giai_phap.md`, `docs/submission/04_mo_ta_su_co_van_hanh.md` | Cả hai kể luồng đầu-cuối và nguyên tắc chia vai; 01 tóm tắt ba ca mà 04 là nguồn chuẩn → một người viết thì không lệch. 01 nhẹ, 04 nặng → tổng tương đương B, C |
| B | 02 | `docs/submission/02_kien_truc_du_lieu_mongodb.md` | Cần đọc sâu mã MongoDB và chuẩn bị bảng số liệu chỉ-đọc |
| C | 03 | `docs/submission/03_kien_truc_observability_datadog.md` | Cần đọc sâu monitor/workflow/probe/guard/LLMObs |

- Không writer nào sửa `00_PLAN.md`, `EVIDENCE_INDEX.md`, `briefs/`, hay bất kỳ tệp ngoài danh sách của mình.
- Ba writer có thể chạy song song. Phụ thuộc: B và C không chờ A; A dùng bảng ID ở mục D.2 thay vì chờ 02/03.
- Brief tự chứa: `docs/submission/briefs/writer_A.md`, `writer_B.md`, `writer_C.md`.
- Sau khi nhận 4 bản: agent chính chạy checklist mục I, gộp yêu cầu `[E-NEW]` vào `EVIDENCE_INDEX.md`, rồi mới xuất DOCX/PDF.

---

## H. Việc cần người dùng, lệnh chỉ-đọc, bằng chứng cần xuất

### H.1 Thông tin chỉ người dùng cung cấp
1. Tên đội, thành viên, vai trò (mục 2 hồ sơ; không đưa email/điện thoại vào repo).
2. Thành phần có từ trước 17/10 và ngày (máy không có `git`; README cho thấy app có lịch sử chuyển SQLite → MongoDB, có dữ liệu users/schedules đã di chuyển) → điền Phụ lục A của 01 và `docs/DECLARATIONS.md`.
3. Giấy phép thư viện (`docs/DECLARATIONS.md` §3) và danh sách công cụ AI đã dùng (Claude Code, Codex, Gemini, Bits AI).
4. Xác nhận phiên bản MongoDB (8.0.34 theo README) và chế độ standalone.
5. Mã incident đầy đủ + link Bits của "164FBE41"; incident ID của lần Ca 2 ngày 06/11.
6. Ca 3 ngày 06/11 là bằng chứng lịch sử. Ca 3 hiện có monitor `342585838` và workflow `373ed0c0-4509-4fcd-a067-f54f0becc00e`; execution DryRun đã xác minh kết nối nhưng chưa chứng minh nhánh start thật. Cần execution ID/log cho lần outage thật trước khi nói workflow đã start service.
7. Ca 1: đã diễn tập chưa; nếu có: incident ID, mốc thời gian, execution có `REFUSED_RESTART`, số lần restart = 0.
8. Quyết định ghi hostname demo (chứa IP) hay không; tài khoản giám khảo cho `/incident`.
9. Sửa `README.md` (đoạn lịch sử "Atlas") và `docs/DECLARATIONS.md` (LLMObs) — ngoài phạm vi writer.

### H.2 Lệnh chỉ-đọc cần chạy (cho tài liệu 02; người dùng chạy qua SSM với user đọc `datadog`, không in URI)
```javascript
// mongosh, db smiot — CHỈ ĐỌC
db.version()
db.hello()                                   // không có setName => standalone
db.getCollectionInfos({name: "telemetry"})   // options.timeseries: timeField, metaField, granularity
db.getCollectionNames().forEach(c => { if (!c.startsWith("system.")) print(c, db[c].estimatedDocumentCount()) })
["telemetry","operational_incidents","incident_telemetry_evidence","operational_decisions","action_ledger","lot_sensor_assignments"].forEach(c => printjson({c, idx: db[c].getIndexes().map(i => ({name: i.name, key: i.key, partial: i.partialFilterExpression || null, unique: !!i.unique}))}))
["operational_incidents","action_ledger"].forEach(c => printjson({c, v: db.getCollectionInfos({name: c})[0].options}))
db.operational_incidents.aggregate([{$group: {_id: {kind: "$kind", status: "$status", synthetic: "$synthetic"}, n: {$sum: 1}}}])
db.telemetry.aggregate([{$sort: {timestamp: -1}}, {$limit: 1}, {$project: {_id: 0, timestamp: 1, meta: 1, readingKeys: {$objectToArray: "$readings"}, sourceKeys: {$objectToArray: "$source"}}}])
db.telemetry.aggregate([{$group: {_id: "$source.synthetic", n: {$sum: 1}}}])
db.runCommand({collStats: "telemetry"})      // chỉ lấy size, storageSize, totalIndexSize, timeseries.*
db.action_ledger.aggregate([{$group: {_id: {action: "$action", state: "$state"}, n: {$sum: 1}}}])
```
Script chỉ-đọc trong repo:
- `py -3.12 -X utf8 scripts/explain_before_after.py --incident-id <ID>` (mặc định dry-run, không tạo/xóa index) → lưu stdout vào `outputs/round2/explain_<ID>.txt`.
- `py -3.12 -X utf8 scripts/mongo_timeseries_benchmark.py --farm greenhouse_a --hours 1` (explain `executionStats`, chỉ đọc) → lưu JSON.
- `py -3.12 -X utf8 scripts/telemetry_quality_report.py` (kiểm lại là chỉ đọc trước khi chạy).
- `py -3.12 -X utf8 -m unittest discover -s tests` (local) — đã chạy 06/11: 162 đạt.

### H.3 Bằng chứng phải chụp/xuất trước khi trial Datadog hết (ưu tiên giảm dần)
1. Monitor Ca 1/Ca 2: chỉ chụp sau khi tài nguyên được xác minh/import trong org hiện tại. Ca 3: monitor `342585838`; IDs 339977691/340356283/341409441 là lịch sử.
2. Workflow execution lịch sử: `e09175ca…` (Ca 2, 06/11), `41135755…` (Ca 3, 04/11), execution Ca 3 ngày 06/11; không dùng các mã này làm bằng chứng chạy workflow trong org hiện tại. Ca 1 cần execution mới nếu diễn tập.
3. Bits AI investigation Ca 2 (3de8802a…, 008cc971…, 164FBE41) — ảnh cây giả thuyết.
4. Logs: truy vấn `service:smiot-smart-farm @incident.id:<ID>` và `source:smiot-recovery event:smiot.guarded_recovery`.
5. APM trace theo `@incident.id`; LLM Observability: danh sách span `ml_app:smiot-smart-farm` (ảnh cho thấy nội dung bị che).
6. Dashboard `nkc-685-vw8` (ảnh toàn trang + JSON export).
7. Metric explorer: `smiot.telemetry.status_mismatch`, `smiot.external.app_up`, `smiot.external.sample_age_seconds` quanh cửa sổ diễn tập.
8. Trang `/incident` (3 thẻ ca) và `/incident/<id>` từng ca (đăng nhập admin).
Lưu vào `outputs/evidence/` với tên `<ngày>_<loại>_<id>.png`; che email/IP trước khi đưa vào hồ sơ.

### H.4 Rủi ro
- **Hạn nộp:** người dùng xác nhận 08/11/2026 theo email BTC (trang web ghi 31/10). Chỉ ghi ở đây; không nêu trong tài liệu nộp. Commit/tệp cuối phải xong trước hạn.
- **Trial Datadog** còn khoảng 10 ngày; Bits AI hết credit đến 01/12 → không chạy thêm Bits cho Ca 1/Ca 3.
- **Ca 1 chưa diễn tập** → tài liệu 04 có thể phải nộp với Ca 1 ở trạng thái "đã cấu hình, chưa diễn tập".
- **Ca 3 tác nhân start chưa rõ** → nếu là thao tác tay, phải ghi "phục hồi thủ công có kiểm soát".
- **Công cụ đọc tự động** có thể bắt chữ "Atlas" trong README lịch sử.
- **Hostname demo chứa IP.**
- **Thời gian:** 3 writer song song + 1 vòng rà soát + xuất DOCX trong ≤ 2 ngày.

---

## I. Checklist rà soát chéo cuối (agent chính chạy trên cả 4 tài liệu)

**Cấu trúc**
- [ ] Front matter YAML đủ khóa (mục D, brief) và parse được.
- [ ] Có Tóm tắt ≤ 200 từ, Đóng góp chính có `[E-xx]`, Bảng 0, chương Đánh giá có bảng Tuyên bố – Bằng chứng – Trạng thái, chương Hạn chế và phạm vi, Kết luận.
- [ ] Đánh số chương/hình/bảng đúng dàn ý; mỗi hình có đoạn mô tả bằng chữ.

**Nhất quán**
- [ ] Tên ca, `kind`, ID monitor/workflow/dashboard khớp mục D.2 (grep từng ID trên 4 tệp).
- [ ] Mốc thời gian trong 01/03 khớp 04.
- [ ] Tên collection/trường/index trong 01/03/04 khớp 02.
- [ ] Mọi `[E-xx]` tồn tại trong `EVIDENCE_INDEX.md`; mọi `[E-NEW]` đã được xử lý hoặc chuyển thành placeholder.
- [ ] Thuật ngữ theo D.1.

**Trung thực (danh sách cấm)**
- [ ] Không tuyên bố Atlas Search/Vector Search/Triggers/Charts/Stream Processing; không Change Streams; không transaction.
- [ ] Không MTTD/MTTR/% giảm cảnh báo/SLO đạt; không điểm tự chấm.
- [ ] Không nói thiết bị vật lý hỏng/đã sửa; mọi dữ liệu cảm biến gắn nhãn tổng hợp.
- [ ] Không "tự động khắc phục" khi bước là thủ công hoặc tác nhân chưa xác minh (Ca 3 06/11).
- [ ] Không nói Bits AI xác nhận phục hồi; Bits chỉ Ca 2.
- [ ] Workflow Ca 1 nếu được import phải query freshness metric rồi rẽ nhánh fail-closed; không gọi trực tiếp MongoDB, không restart tự động; IDs cũ không dùng làm current.
- [ ] Ngưỡng verifier ghi theo mã hiện tại (10 mẫu); số mẫu từng lần ghi theo hồ sơ lần đó.
- [ ] Không có đoạn mâu thuẫn hạn nộp.

**Bảo mật**
- [ ] Grep: không key/token/URI Mongo, không IP, không email, không account AWS, instance ID, tên bucket, org ID.
- [ ] Ảnh nhúng đã che thông tin nhạy cảm.

**Thể lệ**
- [ ] Có khai báo dữ liệu tổng hợp và nguồn; công cụ AI; phần có từ trước 17/10 (hoặc placeholder «CẦN NGƯỜI DÙNG»).
- [ ] Không còn placeholder nào khi nộp, hoặc người dùng đã duyệt danh sách placeholder còn lại.

---

## J. Cập nhật 07/11/2026 và kế hoạch cho từng tệp Word

Mục này **ghi đè** các chỗ mâu thuẫn ở phần trên. Năm bản Markdown 01–05 đã có thân bài (bản nháp 06/11); việc còn lại là sửa theo J.1, rồi dựng thành năm tệp Word theo J.2.

### J.1 Thay đổi so với kế hoạch 06/11

| # | Thay đổi | Hệ quả cho tài liệu |
|---|---|---|
| U1 | **Bỏ Bits AI khỏi hồ sơ** (quyết định của người dùng 07/11: hết credit, không trình bày) | Xóa mục 7.2/7.3 của 03, các dòng Bits trong 01 (Phụ lục B, Bảng 5.1), 04 (Ca 2 điều tra bằng Bits, "điểm hay" số 4), 05 nếu có. Bỏ `bits_ai_investigation` khỏi `products_used`. Phần điều tra chỉ còn Logs/APM/Monitor/Workflow theo `@incident.id`. Các hồ sơ 03/11 vẫn dùng được cho mốc thời gian, nhưng không kể chuyện Bits sửa kết luận. Bỏ các placeholder E-73. |
| U2 | **Đã có số liệu MongoDB thật** (đọc bằng user chỉ-đọc, 07/11): 8.0.34, standalone; `telemetry` ≈ 342.546 bản ghi, Time Series (`timeField=timestamp`, `metaField=meta`); `operational_incidents` 7; `action_ledger` 25; `incident_telemetry_evidence` 241; có index ghép farm/measurement/node/time; `explain()` chọn đúng index, 101 keys / 101 docs | Tài liệu 02: thay các ô «CẦN NGƯỜI DÙNG: H.2-x» tương ứng bằng số này, ghi "đọc ngày 07/11/2026, một lần". `explain` chỉ là thống kê tầng cursor, **không** dùng làm so sánh trước/sau; Bảng 5.4 vẫn để trống phần "trước". |
| U3 | **Validator và TTL chưa thấy trên DB chạy thật** (mã định nghĩa `$jsonSchema` `warn/moderate` nhưng bản đọc 07/11 chưa thấy; không có TTL index) | 01, 02, 03: viết "định nghĩa trong mã, chưa xác nhận trên cơ sở dữ liệu đang chạy"; chuyển trạng thái trong bảng Tuyên bố từ `Đã kiểm chứng` sang `Chưa xác minh`; bỏ "validator" khỏi danh sách tính năng đã dùng trong front matter cho đến khi có kết quả `getCollectionInfos`. Không nhắc TTL. |
| U4 | **LLM Observability đã bật và kiểm chứng** (span `smiot-smart-farm`, nội dung bị che, chỉ lưu tên mô hình/nhà cung cấp/cờ usage) | 03 §8: chuyển E-84 từ placeholder sang "đã xác minh 07/11" (cần ảnh chụp từ người dùng). Sửa `docs/DECLARATIONS.md` (dòng "không có LLM Observability span"). |
| U5 | **Dashboard `nkc-685-vw8` nay 12 widget** (thêm EC2 CPU, EC2 RAM, MongoDB connections/ops/s, MongoDB storage) | 03 §6 và Bảng 0 của 01/03: đổi "8 widget" thành "12 widget (đếm 07/11)"; chụp lại ảnh toàn trang. |
| U6 | **Trang `/chart` chỉ điều hướng** (3 thẻ: Dashboard vận hành, Quan sát AI, Tất cả monitor), không còn biểu đồ trong app | 01 §4.6 và 04 §6: mô tả `/chart` như bảng điều hướng sang Datadog, nhất quán với nguyên tắc R5. Thẻ "Dự đoán từ AI" hiện dự đoán cũ kèm giờ UTC+7; producer `farm/ai` chưa có, **không** dùng làm cảnh demo. |
| U7 | Hồ sơ nộp bằng **Word (.docx)**, người dùng sẽ chỉnh thêm trong Word | Xem J.2; ưu tiên cấu trúc sạch (Heading 1–3, bảng thật, chú thích), không ép bố cục phức tạp. |
| U8 | `docs/submission/05_tai_lieu_use_case.md` đã tồn tại (SMIOT-SUB-05) nhưng chưa nằm trong kế hoạch | Thêm vào J.2 như tài liệu phụ; mục "mục đích thứ ba" còn «ĐANG BỔ SUNG». |

Vẫn giữ nguyên: danh sách cấm (§E.9, brief mục 7), thuật ngữ §D.1, ID §D.2, chia vai Datadog/MongoDB/app.

### J.2 Kế hoạch từng tệp Word

Quy ước chung: mỗi tệp một nguồn Markdown; bìa (tên dự án, tên tài liệu, mục hồ sơ, phiên bản, ngày, nhãn "Dữ liệu tổng hợp"); mục lục tự cập nhật; Heading 1–3 đánh số; bảng thật có hàng tiêu đề; hình Mermaid chuyển thành PNG kèm đoạn mô tả bằng chữ; chân trang có số trang. Thư mục đầu ra `outputs/submission_word/`; tên tệp không dấu.

| Tệp Word | Nguồn | Mục hồ sơ | Việc sửa nội dung trước khi dựng | Còn thiếu từ người dùng | Mức sẵn sàng |
|---|---|---|---|---|---|
| `SMIOT_01_Kien_truc_giai_phap.docx` | `01_kien_truc_giai_phap.md` | 3 | U1 (bỏ Bits), U3 (validator), U5, U6; cập nhật Hình 3.1 thêm trang `/chart` điều hướng; Phụ lục B bỏ Bits AI | Phụ lục A (thành phần có từ trước 17/10), phiên bản MongoDB đã xác nhận | Cao |
| `SMIOT_02_Du_lieu_MongoDB.docx` | `02_kien_truc_du_lieu_mongodb.md` | 4 | U2 (điền số liệu thật Bảng 9.1), U3; ghi rõ `explain` không phải so sánh trước/sau; thêm một dòng giới hạn "không có validator/TTL đã xác nhận trên DB chạy" | Kết quả `getCollectionInfos` cho validator; (tuỳ chọn) lần đo `explain` trước/sau nếu muốn khoe tối ưu | Cao |
| `SMIOT_03_Observability_Datadog.docx` | `03_kien_truc_observability_datadog.md` | 5 | U1 (xóa §7.2–7.3 và mọi nhắc Bits), U4, U5; §7 chỉ còn pivot Logs/APM; dọn mục Hạn chế (bỏ "Bits chỉ Ca 2") | Ảnh dashboard 12 widget, ảnh LLM Observability (E-84), ảnh 6 monitor | Trung bình (chờ ảnh) |
| `SMIOT_04_Mo_ta_su_co.docx` | `04_mo_ta_su_co_van_hanh.md` | 11 | U1 (Ca 2 điều tra không qua Bits; bỏ "điểm hay" số 4), U6; giữ nguyên mốc thời gian | Ca 1: kết quả diễn tập (hoặc ghi "đã cấu hình, chưa diễn tập"); Ca 3 06/11: execution ID và tác nhân start; Ca 2 06/11: xác nhận `recovered`; ảnh `/incident` từng ca | Trung bình (Ca 1, Ca 3 thiếu bằng chứng) |
| `SMIOT_05_Use_case.docx` | `05_tai_lieu_use_case.md` | phụ lục | U1, U6; điền hoặc bỏ «mục đích thứ ba» | Quyết định có nộp kèm không | Thấp, tuỳ chọn |

Thứ tự thực hiện: (1) sửa 03 và 04 theo U1 vì ảnh hưởng nhiều nhất; (2) điền số liệu vào 02; (3) cập nhật 01 và 05; (4) rà checklist mục I trên cả năm tệp; (5) xuất Word; (6) người dùng chèn ảnh chụp và điền placeholder còn lại.

### J.3 Việc cập nhật brief
Ba brief `briefs/writer_A.md`, `writer_B.md`, `writer_C.md` là bản 06/11. Khi sửa nội dung, áp dụng J.1 thay cho các câu về Bits AI, validator đã dùng, "8 widget" và «CẦN NGƯỜI DÙNG: H.2-x» đã có số liệu.
