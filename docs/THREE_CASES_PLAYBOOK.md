# Playbook ba ca vận hành SMIOT

Dữ liệu là **tổng hợp (synthetic)** do chính đội tạo (publisher demo / Wokwi). Không ca nào khẳng định thiết bị vật lý hỏng hay đã sửa.
Bits Investigation chưa xác nhận phục hồi cho đến khi hồ sơ ca ghi điều đó. Không dùng playbook này để tuyên bố đạt SLO.

## Quy tắc chung (áp dụng cho cả ba ca)

1. **Một ca mỗi lần.** Không chạy chồng hai ca; chờ ca trước có hồ sơ xong và monitor về OK.
2. **Snapshot trước.** Có snapshot EBS hoàn tất trong 24 giờ (hiện có `snap-0634c5f0e1a247421`, tạo 2026-11-02, đã cũ hơn 24 giờ tại thời điểm viết; tạo snapshot mới trước khi diễn tập).
3. **Báo trước, mute/ghi chú đúng monitor.** Ca 1: 341409441 (mismatch) và 339977703 (stale, đối chứng); Ca 2: 339977691; Ca 3: 340356283. Chỉ mute/annotate monitor liên quan, không mute toàn bộ.
4. **Ghi mốc thời gian UTC và ICT (UTC+7)** cho từng bước. Datadog UI của tài khoản hiển thị UTC+07:00.
5. **Không đọc/in secret**, không dán `.env`, URI MongoDB, API/app key vào hồ sơ.
6. **Dừng khẩn chung:** nếu hai ca chồng nhau, mẫu không vào, hoặc không chắc, dừng thao tác, ghi `stopped_by_operator` và kiểm tra bằng lệnh chỉ đọc trước khi làm tiếp.

Điều kiện tiên quyết chung: SSM Online (`i-00bf2d3591d3ee0a2`, `ap-southeast-2`, profile `aws-moi`), `smiot.service`, `mongod`, `mosquitto`, Datadog Agent active; 6 monitor SMIOT ở OK (5 cũ và 341409441 mới); ghi lại tuổi mẫu mới nhất ban đầu.

---

## Ca 1 - Báo offline sai (mẫu còn vào MongoDB, workflow TỪ CHỐI restart)

**Kịch bản kích hoạt.** Trạng thái hiển thị/cache của node là OFFLINE trong khi MongoDB vẫn nhận mẫu mới. Lệnh diễn tập theo `docs/CODEX_PLAN_3_CASES.md`: `/opt/smiot/.venv/bin/python -X utf8 /opt/smiot/scripts/set_demo_ui_fault.py stale_cache --node 1 --minutes 6` (chỉ chạy sau G3). Khôi phục: cùng script với `normal --node 1`.

**Điều kiện tiên quyết.** Chung + publisher demo đang đẩy mẫu cho `greenhouse_a`; monitor 341409441 đã tạo, OK, gắn workflow `e2835af0-63fc-48e0-9562-2a1ee4a351d3`. Workflow này chỉ Echo lý do từ chối, không đọc Mongo trực tiếp và không có hành động EC2. Gỡ hoặc gia hạn downtime đúng thời điểm diễn tập (downtime ban đầu hết khoảng 06:08 ICT ngày 06/11).

**Trình tự.**
1. Chốt baseline: `smiot.telemetry.sample_age_seconds` và `smiot.external.sample_age_seconds` thấp, UI = ONLINE.
2. Báo trước, annotate monitor 339977703 và 341409441.
3. Kích hoạt `stale_cache` bằng lệnh ở trên. Ghi T0.
4. Quan sát: UI báo OFFLINE; Mongo vẫn có mẫu mới; `status_mismatch > 0`.
5. Đọc execution của workflow Ca 1: bước Echo ghi `REFUSED_RESTART`, **không** `systemctl start/restart`. Không đồng nhất Echo với guard truy vấn Mongo.
6. Chạy `normal --node 1`; chờ `status_mismatch` về 0.

**Quan sát được.**
- Datadog: `smiot.telemetry.status_mismatch` > 0; `sample_age_seconds` thấp; monitor stale 339977703 vẫn OK; execution workflow Ca 1 có Echo `REFUSED_RESTART`; **không** có `action:start`.
- Mongo: mẫu mới trong `telemetry` (Time Series) theo `meta.farm_key`, `meta.node_id`, `timestamp`.

**Tiêu chí xong.** Hiển thị ONLINE khớp Mongo; `status_mismatch` về 0; monitor Ca 1 Recovered; số lần restart = 0 trong cửa sổ ca; có mẫu Mongo mới sau thời điểm sửa.

**Rủi ro.** Restart oan làm mất phiên và bằng chứng; ngưỡng sai gây flapping; metric chưa tồn tại nên monitor không phát.

**Dừng khẩn.** Hủy kích hoạt kịch bản (hồi trạng thái cũ); chặn workflow bằng cách pause/mute monitor Ca 1; không restart tay.

**Bảng 6 câu (điền).**

| # | Câu hỏi | Trả lời | Bằng chứng/ID |
|---|---|---|---|
| 1 | Chuyện gì xảy ra? | | |
| 2 | Phát hiện lúc nào? | | |
| 3 | Bằng chứng gốc? | | |
| 4 | Lô nào ảnh hưởng? | | |
| 5 | Vì sao chọn hành động này (từ chối restart)? | | |
| 6 | Dữ liệu nào chứng minh phục hồi? | | |

---

## Ca 2 - Node 2 đứng số đo (đánh dấu không đáng tin, HOLD, CLEAR sau mẫu phục hồi đã xác minh)

**Kịch bản kích hoạt.** Publisher demo chuyển Node 2 sang flatline 2,4% độ ẩm đất (tổng hợp):
`py -X utf8 scripts/set_demo_sensor_fault.py flatline` (hồi: `... normal`). Mô tả chính xác là "dữ liệu đứng phù hợp với giả thuyết flatline", không phải cảm biến vật lý hỏng.

**Điều kiện tiên quyết.** Chung + monitor 339977691 OK + workflow Node 2 published + không có incident Node 2 đang mở + `scripts/verify_and_clear_demo_safe_mode.py` có trên EC2.

**Trình tự.**
1. Baseline: giá trị `soil_humidity` Node 2 đang dao động; ghi tuổi mẫu.
2. Báo trước; annotate monitor 339977691.
3. Bật flatline; ghi T0 (UTC và ICT). Incident mở trong `operational_incidents`.
4. Monitor 339977691 Alert; workflow ghi HOLD vào `action_ledger`; bơm ảo giữ OFF. Dữ liệu Node 2 được đánh dấu không đáng tin cho đến khi có mẫu phục hồi.
5. Tắt flatline (`normal`); chờ mẫu dao động trở lại.
6. Verifier xác minh nhiều mẫu tươi và dao động (lần trước: 7 mẫu), rồi **mới** gửi CLEAR; xác nhận bơm ảo OFF; đánh dấu incident `recovered`.

**Quan sát được.**
- Datadog: monitor 339977691 Alert rồi OK; `smiot.telemetry.sensor_flatline`; log/trace `@incident.id:<ID>`; workflow execution.
- Mongo: `telemetry` (mẫu vẫn tăng sequence, chứng minh publisher/ingest không dừng), `operational_incidents`, `action_ledger` (HOLD, CLEAR verified), `incident_telemetry_evidence`.

**Tiêu chí xong.** CLEAR chỉ sau mẫu phục hồi đã xác minh; `action_ledger` có HOLD và CLEAR verified; incident `recovered`; monitor OK; mọi bơm ảo OFF suốt ca.

**Rủi ro.** CLEAR sớm khi cửa sổ mẫu chưa đủ; workflow bị rate limit (1/300 s, từng 4 lần "Rate limit exceeded"); Bearer token nằm trong spec workflow (nên chuyển sang connection); nhầm lẫn "đứng số đo" với hỏng vật lý.

**Dừng khẩn.** Chạy `set_demo_sensor_fault.py normal`; giữ HOLD (không CLEAR tay); pause workflow Node 2; ghi `stopped_by_operator`.

**Bảng 6 câu (điền).**

| # | Câu hỏi | Trả lời | Bằng chứng/ID |
|---|---|---|---|
| 1 | Chuyện gì xảy ra? | | |
| 2 | Phát hiện lúc nào? | | |
| 3 | Bằng chứng gốc? | | |
| 4 | Lô nào ảnh hưởng? | | |
| 5 | Vì sao chọn hành động này (HOLD, chỉ CLEAR sau xác minh)? | | |
| 6 | Dữ liệu nào chứng minh phục hồi? | | |

---

## Ca 3 - `smiot.service` dừng, dependencies khỏe (chỉ start sau guard)

**Kịch bản kích hoạt.** Operator dừng đúng một unit `smiot.service` trên EC2. Dùng `scripts/drill_ca3_service_down.ps1` (mặc định dry run; dừng thật chỉ với `-Confirm`).

**Điều kiện tiên quyết.** Chung + `mongod`/`mosquitto` active + đĩa gốc < 85% + helper readback `/usr/local/sbin/smiot-recovery-mongo-readback` đã cài + monitor 340356283 OK + snapshot < 24 giờ. Lưu ý: nhánh outage của guard cần được drill lại sau khi cài helper trước khi gọi là đã chứng minh (theo `docs/DATADOG_GUARDED_RECOVERY.md`).

**Trình tự.**
1. Dry run: `.\scripts\drill_ca3_service_down.ps1` (kiểm tra chỉ đọc, ghi evidence JSON vào `outputs/`).
2. Báo trước; annotate monitor 340356283 (và monitor Ca 3 nháp nếu đã tạo).
3. Live: `.\scripts\drill_ca3_service_down.ps1 -Confirm -MonitorsOkAttested -MuteNoted`.
4. Monitor Alert -> workflow EC2 chạy guard: chỉ `systemctl start smiot.service` khi các guard qua (khoảng trống ingest ghi nhận, cooldown 300 s).
5. Xác minh: systemd active, HTTP 200 và mẫu Mongo mới hơn baseline với tuổi <= 180 s.

**Quan sát được.**
- Datadog: monitor 340356283 Alert rồi OK; `smiot.external.app_up` 0 rồi 1; `smiot.external.sample_age_seconds` tăng rồi về thấp; log `source:smiot-recovery event:smiot.guarded_recovery` (`action:start result:verified`); workflow execution; `smiot.*` trong app no-data trong lúc dừng.
- Mongo: khoảng trống ingest trong `telemetry` (timestamp), mẫu mới sau thời điểm start.
- Host (chỉ đọc qua SSM): `systemctl is-active`, journal của `smiot.service`.

**Tiêu chí xong.** Guard `result=verified`; `app_up = 1`; mẫu Mongo mới sau lúc start; monitor Recovered; không restart `mongod`/`mosquitto`/Agent/EC2; evidence JSON của drill có `recovered_verified_http_and_new_mongo_sample`.

**Rủi ro.** Dừng nhầm giờ cao điểm; guard từ chối (đĩa, dependency, cooldown) -> app phải start tay có kiểm soát; Datadog chưa chứng minh nhánh start tự động sau khi helper mới cài; ghi chú rằng bước dừng là thao tác của operator.

**Dừng khẩn.** `systemctl start smiot.service` qua SSM document `SMIOT-GuardedStartApp` (`DryRun=false`) hoặc sudo trên host; không restart EC2/mongod/mosquitto/Agent. Tuyệt đối không chạy thêm ca khác.

**Bảng 6 câu (điền).**

| # | Câu hỏi | Trả lời | Bằng chứng/ID |
|---|---|---|---|
| 1 | Chuyện gì xảy ra? | | |
| 2 | Phát hiện lúc nào? | | |
| 3 | Bằng chứng gốc? | | |
| 4 | Lô nào ảnh hưởng (khoảng trống ingest)? | | |
| 5 | Vì sao chọn hành động này (start sau guard, không restart)? | | |
| 6 | Dữ liệu nào chứng minh phục hồi? | | |

---

## Lịch sử có sẵn (chỉ tham chiếu, không thay hồ sơ mới)
- Ca 2: `docs/INC-SMIOT-20261103T114321-BD19A22C_EVIDENCE.md`.
- Ca 3: workflow execution `41135755-2edd-429b-9c0f-9e73ae7c43a1` (2026-11-04) đã start -> verified; theo baseline A1 chưa có log stop đối chiếu và Bits chưa ghi hypothesis/action.
- Ca 1: đã có monitor 341409441 và workflow `e2835af0-63fc-48e0-9562-2a1ee4a351d3`; chưa có incident diễn tập mới, log/trace riêng hoặc execution Alert thật.
