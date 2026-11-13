# Kế hoạch giao Codex: diễn tập 3 ca, chụp bằng chứng, giải thích nguyên nhân

Viết cho một AI lập trình (Codex) làm việc trong repo `D:\IOT Trung\code_full_server`. Tiếng Việt.
Cập nhật theo trạng thái thật ngày 06/11/2026 (đã đối chiếu trực tiếp với Datadog qua MCP). Đọc hết mục 0–3 trước khi làm.

---

## 0. Mục tiêu và định nghĩa "xong"

**Mục tiêu cuối** là trang `/incident` cho thấy đủ 3 ca, mỗi ca được diễn tập thật, có incident trong MongoDB, monitor/workflow Datadog và bằng chứng từng bước. Đây là tiêu chí nghiệm thu, không phải trạng thái hiện tại; xem bảng bên dưới để phân biệt tài nguyên live với draft/lịch sử.

| Ca | Sự việc | `kind` trong MongoDB | Monitor Datadog (ID) | Workflow | Cách mở sự cố |
|---|---|---|---|---|---|
| 1 | Báo offline sai: mẫu vẫn vào Mongo, giao diện báo offline | `false_offline` | Monitor chính hiện tại chưa xác minh; `339977703` là ID đối chứng từ Datadog cũ, không dùng làm ID hiện tại | JSON workflow guard cần import sau khi xác minh/tạo monitor chính | Watchdog mở incident khi có mismatch; workflow chỉ từ chối restart hoặc chuyển người xử lý |
| 2 | Node 2 đứng số đo (2,4%) | `soil_humidity_flatline` | Monitor Ca 2 hiện tại chưa xác minh; `339977691` là ID lịch sử | JSON workflow Ca 2 chưa live; cần xác minh monitor, endpoint và connection trước khi import | App/PLC ảo vào HOLD tại biên; Datadog chỉ điều phối xác minh |
| 3 | `smiot.service` dừng, MongoDB/MQTT khỏe | `service_down` | `342585838` — “SMIOT \| smiot.service inactive” (đã xác minh trên Datadog hiện tại) | `373ed0c0-4509-4fcd-a067-f54f0becc00e` — “SMIOT \| Guarded EC2 app recovery” (đã xuất bản và nối monitor) | Probe ngoài app mở sau 2 lần `app_up=0` liên tiếp; workflow dùng SSM guarded start |

**Phân biệt tài khoản:** các ID `339977703`, `339977691`, `340356283`, `341409441` và workflow `e2835af0…`, `18d1b008…`, `b83453ff…` thuộc cấu hình/tài khoản Datadog cũ. Chỉ giữ làm lịch sử bằng chứng; không nhập lại nguyên ID hoặc coi chúng là tài nguyên đang live trong tổ chức hiện tại. Snapshot `2026-11-08` là lịch sử, không phải cấu hình import cho tổ chức hiện tại.

**Một ca xong khi trả lời đủ 6 câu với dữ liệu thật:** (1) Chuyện gì xảy ra? (2) Phát hiện lúc nào? (3) Bằng chứng gốc là gì?
(4) Lô nào bị ảnh hưởng (hoặc "chưa xác định")? (5) Vì sao chọn hành động đó? (6) Dữ liệu nào chứng minh phục hồi?

**Monitor APM hiện có (chỉ để tham khảo, KHÔNG phải monitor của 3 ca):** Datadog tự tạo, trạng thái `OK`:
- `339985452` "[operation:fastapi.request] High Error Rate on {{service.name}}" (tỷ lệ lỗi > 10% trong 15 phút).
- `339992812` "[operation:websocket.receive] High Error Rate…" và `339992811` "[operation:websocket.close] High Error Rate…".
Ba monitor này theo dõi lỗi HTTP/WebSocket của service, không bắt được đứng số đo, lệch hiển thị hay dừng service. Không dùng chúng làm monitor của ca nào. Có thể đưa vào hồ sơ như "APM nền, đang OK".

**Điều kiện nghiệm thu cuối:** mở `/incident` thấy 3 thẻ ca, mỗi thẻ có incident thật; mở từng incident thấy hồ sơ 6 câu, khung liên kết điều tra và thanh tua. Mỗi monitor/workflow phải được xác minh trong tổ chức Datadog hiện tại; không tính ID snapshot cũ. Các monitor ngoài kịch bản vẫn `OK`; mỗi bước diễn tập có ảnh chụp và file giải thích (mục 1.2).

---

## 1. Quy tắc cứng

### 1.1 An toàn (KHÔNG được vi phạm)
1. Không đọc, không in, không ghi lại nội dung `.env`, `/etc/smiot/app.env`, `/etc/smiot/probe.env`, khóa API, token, URI có mật khẩu, mật khẩu user Mongo. Chỉ được nói **tên** biến/user.
2. Không tạo, sửa, xóa user MongoDB, role, mật khẩu, quyền. Các user hiện tại (`datadog` đọc, `smiot_app` ghi) là dùng **tạm** theo yêu cầu người dùng; **không đổi quyền**. Ghi nhận trong báo cáo là cần thay bằng user hẹp sau khi xong.
3. Không đổi tên metric hay tag Datadog hiện có. Không đưa `incident_id` vào tag metric.
4. Không tạo bản ghi sự cố giả (insert tay, backfill, sửa timestamp). Mọi bản ghi phải do app/probe sinh ra khi diễn tập thật.
5. Dữ liệu là synthetic: giữ `synthetic: true` và hiển thị nhãn "Dữ liệu diễn tập". Không khẳng định cảm biến hay bơm vật lý hỏng/đã sửa.
6. Bits AI chưa xác nhận phục hồi: bằng chứng phục hồi đến từ verifier của app, dữ liệu Mongo đọc lại, ACK và monitor `OK`.
7. Không tuyên bố điểm số, SLO đạt, MTTR, "Atlas", "Vector Search". MongoDB là Community 8.0.34 self-managed, standalone: **không có transaction, không có Change Streams**.
8. Không git commit (máy không có `git`). Không xóa file ngoài danh sách được giao.
9. Mọi thao tác **ghi lên EC2 hoặc Datadog** phải qua cổng duyệt ở mục 6. Không chạy hai ca chồng nhau.

### 1.2 Chụp và giải thích từng bước (BẮT BUỘC cho mỗi bước diễn tập)
Với **mỗi bước** (lệnh, thay đổi cấu hình, quan sát monitor, mở trang) Codex phải tạo một thư mục `outputs/round2/<ca>/<số bước>_<tên ngắn>/` gồm:
- `screenshot_before.png` và `screenshot_after.png` (chụp trang Datadog, trang `/incident`, hoặc kết quả terminal dạng ảnh). Nếu không chụp được, ghi lý do vào `note.md`, **không bỏ qua**.
- `command.txt`: lệnh đã chạy (che secret), thời điểm UTC và ICT.
- `result.json`: kết quả thô (ví dụ dòng log JSON của probe, execution id, trạng thái monitor).
- `explain.md` gồm 4 mục:
  - **Đã làm gì:** một câu.
  - **Kỳ vọng:** trạng thái mong đợi.
  - **Thực tế:** trạng thái quan sát được (ghi đúng số liệu, kể cả khi lệch).
  - **Nguyên nhân và ý nghĩa:** vì sao xảy ra điều đó (dựa vào code hoặc log, nêu file:dòng hoặc tên monitor/workflow), và ý nghĩa với bài toán vận hành nhà kính. Không suy đoán: nếu chưa rõ nguyên nhân thì ghi "chưa xác định" và nêu cách kiểm tra.

Cuối mỗi ca có `outputs/round2/<ca>/SUMMARY.md` trả lời 6 câu hỏi, mỗi câu trỏ tới bước chứng minh.

---

## 2. Trạng thái thật hiện tại (đọc trước khi làm, đã xác minh)

**Code và EC2 (đã triển khai)**
- Bản code mới nhất trên EC2: triển khai lúc 20:55 UTC ngày 05/11 (UTC), gồm: trang `/incident` có khối "Hồ sơ 6 câu hỏi", tự làm mới (danh sách 10 giây, chi tiết 20 giây), thanh tua, khung liên kết theo nhóm; tự mở sự cố flatline khi node 2 đứng số đo thật; lệnh tiêm `stale_cache`; `/healthz`.
- Snapshot trước triển khai gần nhất: `snap-031033d62ae7116ce`. Backup code cũ: `/root/smiot-rollback/code_before_20261105-205529.tgz`.
- Probe ngoài app đã cài: `smiot-external-probe.timer` chạy mỗi 30 giây. `/etc/smiot/probe.env` (quyền 600, root):
  - `MONGODB_URI` dùng user `datadog` (đọc) — đã xác minh đọc được mẫu mới nhất.
  - `SMIOT_PROBE_MONGODB_URI_WRITE` dùng user `smiot_app` (ghi, tạm).
  - `SMIOT_PROBE_DRY_RUN=0`, `SMIOT_PROBE_RECORD_INCIDENT=1`, `SMIOT_PROBE_DRILL=1` (đánh dấu synthetic).
- Trạng thái probe lần kiểm tra cuối: `app_up=1`, `mongo_up=true`, `dry_run=false`, `incident_action=none` (app đang khỏe nên không mở gì).
- `smiot.service` đang `active`; `/healthz` trả `mongo ok`, `mqtt ok`.

**Dữ liệu trong `/incident` hiện có:** 2 bản ghi, đều là Ca 2 cũ ngày 03/11 (`INC-SMIOT-20261103T114321-BD19A22C`, `INC-SMIOT-20261103T102822-D3B0F8A7`). **Ca 1 và Ca 3 chưa có bản ghi nào trong MongoDB.** Ca 3 ngày 04/11 chỉ có trên Datadog (execution `41135755-2edd-429b-9c0f-9e73ae7c43a1`).

**Datadog hiện tại (đã kiểm tra trên web ngày 09/11/2026)**
- Monitor Ca 3 hiện tại là `342585838` “SMIOT | smiot.service inactive”; trạng thái `OK` khi kiểm tra. Monitor Ca 1/Ca 2 và workflow tương ứng chưa được xác minh trong tổ chức hiện tại.
- Workflow Ca 3 `373ed0c0-4509-4fcd-a067-f54f0becc00e` “SMIOT | Guarded EC2 app recovery” đang xuất bản và được nối với monitor Ca 3.
- Đã chạy một kiểm tra `DryRun=true` qua Datadog → AWS SSM; SSM trả `Success` và bỏ qua vì app đang active. Điều này xác nhận đường kết nối và nhánh bỏ qua an toàn, **không** chứng minh nhánh start thật.
- Các ID monitor/workflow trong snapshot 2026-11-08 thuộc tài khoản cũ; không tái sử dụng hoặc import chúng như tài nguyên hiện tại.
- JSON workflow Ca 1/Ca 2 chỉ là bản dự thảo đến khi monitor, endpoint/action schema, và connection cần thiết được xác minh. Không nhúng bearer token hoặc secret vào JSON.

**Code đã có sẵn cho cả 3 ca:** `open_incident`/`close_incident`, `start_flatline_incident` (tái sử dụng sự cố đang mở), `_track_false_offline` (Ca 1), `update_service_down_incident` trong probe (Ca 3), `pages/incident.py` (trang hộp đen).

**Còn thiếu so với mục tiêu:**
- Thẻ tóm tắt 3 ca ở đầu `/incident` và ánh xạ ca theo `kind` (chưa làm).
- Bộ lọc theo ca (chưa làm).
- Playbook Ca 1 và Ca 3 trong `docs/THREE_CASES_PLAYBOOK.md` (chưa cập nhật).

---

## 3. PHẦN A: Hoàn thiện `/incident` (sửa code, không đụng hạ tầng)

Được sửa: `pages/incident.py`, `service/incident_blackbox.py` (chỉ thêm hàm), `tests/test_incident_cases.py` (mới).
Không sửa `pages/home.py` (mục "Incident" đã có trong thanh bên, chỉ admin).

**A1. Ánh xạ ca một nguồn** (thêm vào `service/incident_blackbox.py`):
```python
CASES = {
    1: {"kind": "false_offline", "title": "Ca 1: báo offline sai",
        "summary": "Mẫu vẫn vào MongoDB nhưng giao diện báo offline; workflow phải từ chối restart.",
        "monitor_id": None, "control_monitor_id": None, "workflow_id": None},
    2: {"kind": "soil_humidity_flatline", "title": "Ca 2: node 2 đứng số đo",
        "summary": "Node 2 vẫn gửi mẫu nhưng độ ẩm kẹt ở 2,4%; đánh dấu không đáng tin, HOLD, chỉ CLEAR khi mẫu phục hồi được xác minh.",
        "monitor_id": None, "workflow_id": None},
    3: {"kind": "service_down", "title": "Ca 3: smiot.service dừng",
        "summary": "App dừng khi MongoDB/MQTT khỏe; chỉ khởi động lại smiot.service sau guard, rồi xác minh HTTP và mẫu mới.",
        "monitor_id": "342585838", "workflow_id": "373ed0c0-4509-4fcd-a067-f54f0becc00e"},
}
def case_for_kind(kind) -> int | None: ...   # hàm thuần; kind lạ -> None
```
Chỉ điền `monitor_id`/`workflow_id` của Ca 1 và Ca 2 sau khi tài nguyên được tạo/import và xác minh trong tổ chức Datadog hiện tại. Không dùng các ID snapshot cũ làm ID mặc định. Với Ca 3, dùng monitor `342585838` và workflow `373ed0c0-4509-4fcd-a067-f54f0becc00e`.

**A2. Trang danh sách `/incident`:**
- Đầu trang có **3 thẻ ca**. Mỗi thẻ: tiêu đề, mô tả một câu, ID monitor (có link `https://app.datadoghq.com/monitors/<id>`), trạng thái lần diễn tập gần nhất (`Chưa diễn tập` / `Đang mở` / `Đã phục hồi`), thời gian phát hiện và phục hồi, nút "Mở hồ sơ". Không có bản ghi thì thẻ xám, ghi "Chưa diễn tập", không bịa số.
- Bảng sự cố thêm cột "Ca" (Ca 1/2/3 theo `case_for_kind`) và bộ lọc Tất cả / Ca 1 / Ca 2 / Ca 3.

**A3. Trang chi tiết `/incident/{id}`:** giữ khối "Hồ sơ 6 câu hỏi", khung liên kết (4 nhóm + nhóm "Hạ tầng"), thanh tua, bảng tác động. Thêm nhãn "Ca N" ở đầu. Với Ca 1 chỉ hiện monitor đối chứng sau khi xác minh current ID; `339977703` là ID lịch sử, không đưa làm link live.

**A4. Test:** `tests/test_incident_cases.py` (unittest, không cần Mongo): `case_for_kind`; chọn lần diễn tập gần nhất theo ca (hàm thuần); dựng nhóm link có mặc định theo ca. Chạy `py -3.12 -X utf8 -m unittest discover -s tests`; hiện có 61 test đạt, không được giảm.

**Nghiệm thu A:** py_compile và test đạt; ghi rõ "chưa xem giao diện thật" nếu không mở được trình duyệt.

---

## 4. PHẦN B: Triển khai (cổng G1)
Dùng đúng quy trình đã chạy thành công: snapshot → đóng gói (không kèm `.env`, `scratch`, `.pem`) → tải S3 `smiot/deploy_<ts>.tgz` → SSM: backup `/root/smiot-rollback/code_before_<ts>.tgz`, giải nén vào `/tmp/smiot_new`, kiểm cú pháp bằng `/opt/smiot/.venv/bin/python`, `cp -a` vào `/opt/smiot`, `chown -R smiot:smiot`, `systemctl restart smiot.service`, chờ 25 giây, kiểm `/healthz` 200 và `is-active`; lỗi thì tự rollback. Chỉ restart `smiot.service`. Chụp kết quả theo mục 1.2.
Sau triển khai: 5 monitor vẫn `OK`, `/incident` HTTP 200.

---

## 5. PHẦN C: Việc làm tay trên Datadog (Codex chỉ soạn nội dung và hướng dẫn, không tự tạo)

**D1. Monitor Ca 1 chính `status_mismatch`** (dự thảo, chưa xác minh/live trong tổ chức hiện tại):
- Nguồn: `deploy/datadog/drafts/monitor_ca1_status_mismatch.json`.
- Query: metric `smiot.telemetry.status_mismatch` > 0 (kiểm tra metric đã có dữ liệu trước; nếu chưa có thì phải diễn tập Ca 1 để metric xuất hiện).
- Tag: `service:smiot-smart-farm`, `env:demo`, `project:smiot`, `scenario:false-offline`.
- Tắt tiếng lúc tạo, đặt `notify_no_data=false`. Message nêu rõ "không restart node khi mẫu Mongo còn mới".
- Chỉ cập nhật ID vào `CASES[1]` sau khi xác minh monitor nhận metric và có trạng thái đúng trong tổ chức hiện tại. ID lịch sử 341409441 không được coi là tài nguyên hiện tại.

**D2. Workflow guard Ca 1** (JSON dự thảo, chưa live): query freshness của hai nguồn; nếu cả hai số đo hữu hạn và dưới ngưỡng thì ghi `REFUSED_RESTART`; nếu thiếu/stale/query lỗi thì `ESCALATE_HUMAN`. Không restart EC2/node. Chỉ import và gắn vào D1 sau khi D1 đã được xác minh; rate limit theo phạm vi tài nguyên, không dùng ID workflow cũ.

**D3. Workflow Ca 2:** JSON chỉ được import sau khi xác minh endpoint kiểm tra phục hồi, xác thực bằng Datadog connection/secret và schema của action. Không đặt bearer token tĩnh trong JSON. HOLD do ứng dụng/PLC ảo xử lý tại biên; workflow không CLEAR khi chỉ monitor đã về OK. Chỉ cho CLEAR khi verifier xác nhận incident khớp, ACK/HOLD đúng và có chuỗi mẫu mới dao động; thiếu bằng chứng thì giữ HOLD và báo người xử lý.

**D4. Xuất bằng chứng sớm:** xuất ảnh/JSON từ tổ chức Datadog hiện tại. Đánh dấu riêng Ca 1/Ca 2 là draft nếu chưa import và xác minh; Ca 3 là workflow đang xuất bản. Không dùng snapshot 2026-11-08 làm cấu hình import hiện tại.

---

## 6. Cổng duyệt (người dùng xác nhận trước khi Codex chạy)

| Cổng | Hành động | Điều kiện |
|---|---|---|
| G1 | Triển khai code mới (restart `smiot.service`) | Phần A xong, test đạt, snapshot `completed` |
| G2 | Diễn tập Ca 2 (ghi vào MQTT demo, sinh sự cố thật) | 5 monitor `OK`, không có diễn tập khác đang chạy |
| G3 | Diễn tập Ca 1 | D1 và D2 đã tạo, `CASES[1]` đã cập nhật |
| G4 | Diễn tập Ca 3 (dừng `smiot.service` thật) | Snapshot mới, Private Action Runner online, monitor `342585838` đúng tổ chức, mute đúng monitor, probe `RECORD=1`; DryRun đã qua nhưng nhánh start thật chưa được chứng minh |

**Điều kiện dừng khẩn mọi ca:** `/healthz` không phục hồi sau 5 phút; Mongo hoặc MQTT báo lỗi; monitor ngoài kịch bản `Alert`; workflow `Step error`. Khi đó: đặt lại lỗi publisher về `normal`, hoặc `systemctl start smiot.service`; rollback từ backup nếu cần; ghi lại và báo người dùng.

---

## 7. PHẦN E: Diễn tập từng ca (mỗi ca riêng, cách nhau ít nhất 10 phút)

Chuẩn bị chung: chụp 5 monitor trước; ghi đồng hồ UTC và ICT.

**E1. Ca 2 — node 2 đứng số đo (G2)**
1. Trước: `/healthz` ổn; xác minh monitor Ca 2 trong tổ chức hiện tại đang `OK`. ID `339977691` chỉ là lịch sử.
2. Trên EC2 (qua SSM): `/opt/smiot/.venv/bin/python -X utf8 /opt/smiot/scripts/set_demo_sensor_fault.py flatline`.
3. Chờ: 10 mẫu liên tiếp 2,4% → `sensor_flatline` > 0 → monitor Ca 2 đã xác minh chuyển `Alert`. Ứng dụng/PLC ảo thực hiện HOLD; workflow Datadog chỉ chạy sau khi monitor đã được nối và chỉ gọi verifier đã xác minh. Incident `soil_humidity_flatline` xuất hiện ở `/incident`.
4. Phục hồi: `... set_demo_sensor_fault.py normal`. Verifier kiểm ≥ 7 mẫu dao động, HOLD đã ACK, gửi CLEAR; monitor về `OK`; incident chuyển `recovered`.
5. Chụp và giải thích từng bước; mở link logs/trace/Bits thật và ghi link đúng.

**E2. Ca 1 — báo offline sai (G3)**
1. Trước: monitor đối chứng và D1 trong tổ chức hiện tại đều `OK`; node 1 đang gửi mẫu. Không dùng ID monitor cũ nếu chưa xác minh.
2. Trên EC2: `... set_demo_ui_fault.py stale_cache --node 1 --minutes 6`. Thời hạn phải đủ để monitor kịp bắt; nếu chưa kịp thì tăng `--minutes` (tối đa 30), không sửa code.
3. Kỳ vọng: giao diện báo node 1 OFFLINE; mẫu vẫn vào Mongo; `status_mismatch=1`; monitor D1 `Alert`; workflow Ca 1 đã import từ JSON và nối D1 sẽ từ chối restart; monitor đối chứng vẫn phân biệt được trạng thái mất dữ liệu thật.
4. Hết hạn hoặc `... set_demo_ui_fault.py normal --node 1`: ONLINE, `status_mismatch=0`, monitor về `OK`, incident đóng kèm bằng chứng mẫu Mongo.
5. Ghi nhận: số lần restart nhầm = 0.

**E3. Ca 3 — dừng `smiot.service` (G4)**
1. Trước: snapshot mới; Private Action Runner online; probe `RECORD=1`, `DRILL=1`; 4 monitor còn lại `OK`.
2. Dry-run: `.\scripts\drill_ca3_service_down.ps1` (mặc định `-DryRun`).
3. Chạy thật: `.\scripts\drill_ca3_service_down.ps1 -Confirm -MonitorsOkAttested -MuteNoted -MaxWaitSec 420`.
4. Kỳ vọng: probe mở `service_down` sau 2 lần `app_up=0`; monitor `342585838` mất thời gian theo cửa sổ truy vấn để chuyển `Alert`; workflow `373ed0c0-4509-4fcd-a067-f54f0becc00e` chỉ khởi động `smiot.service` sau guard; HTTP 200; mẫu Mongo mới; monitor `Recovered`; probe đóng incident khi `app_up=1` và mẫu < 180 giây. DryRun hiện mới chứng minh kết nối SSM và skip khi app đang active, chưa chứng minh nhánh start thật.
5. Nếu sau `-MaxWaitSec` service chưa lên: báo người dùng, ghi là phục hồi thủ công.
6. Quay video một lượt, đồng hồ trong khung hình.

Sau mỗi ca: `explain_before_after.py --incident-id <id>` (dry-run) và lưu JSON vào `outputs/round2/`.

---

## 8. Việc chỉ người dùng làm được
- Xác minh/tạo monitor Ca 1 và Ca 2, import JSON workflow Ca 1/Ca 2 sau khi action/connection được kiểm tra; workflow Ca 3 đã xuất bản và nối monitor.
- Quyết định có thay user `smiot_app` bằng user hẹp sau diễn tập không.
- Xác nhận hạn nộp 08/11 với BTC bằng văn bản; điền `<ĐIỀN>` trong `docs/DECLARATIONS.md`.
- Chọn khung giờ diễn tập Ca 3; quay video.
- Thu hồi khóa Gemini nếu từng bị lộ ra repo công khai.

---

## 9. Điểm cần Codex kiểm tra và báo cáo (không tự giả định)
1. Snapshot cũ có tag `managed_by:codex` trên monitor `339990226` và `339990232`; nếu cần đối chiếu thì coi đây là lịch sử, không suy ra trạng thái của monitor hiện tại.
2. Metric `smiot.telemetry.status_mismatch` đã có dữ liệu trên Datadog chưa (nếu chưa thì Ca 1 chỉ diễn tập được sau khi có ít nhất một lần phát).
3. Monitor và workflow Ca 1/Ca 2 trong tổ chức hiện tại sau khi import; không dùng ID lịch sử `18d1b008`.
4. Định dạng link Datadog trong `pages/incident.py` (`/apm/trace/`, `/bits-ai/investigations/`, `/logs?query=`): đã bấm thử chưa.
5. Bits AI: có sẵn 4 lần điều tra (Node 2 ×2, node 1 stale ×1, EC2 ×1, đều `conclusive`); đọc kết luận chi tiết trước khi đưa vào hồ sơ.
6. Nguyên nhân các lần `Rate limit exceeded`/`Step error` của workflow trong tài khoản cũ chỉ là kiểm tra lịch sử. Với workflow hiện tại, ghi nhận execution mới và chỉ kết luận dựa trên log/run tương ứng.

---

## 10. Thứ tự làm
1. Phần A (sửa code, test, chụp và giải thích). Không cần duyệt.
2. Người dùng làm D1, D2 (và D3 nếu muốn); Codex cập nhật `CASES[1]`.
3. G1 → Phần B → kiểm 5 monitor.
4. G2 → E1 (Ca 2); chờ 10 phút.
5. G3 → E2 (Ca 1); chờ 10 phút.
6. G4 → E3 (Ca 3).
7. Gom bằng chứng: `outputs/round2/<ca>/` đầy đủ ảnh và `explain.md`, `SUMMARY.md` mỗi ca; ảnh `/incident` (3 thẻ + hồ sơ từng ca); cập nhật `docs/THREE_CASES_PLAYBOOK.md`, `docs/SUBMISSION_CHECKLIST.md`.
8. Quét secret trong file mới; xuất bằng chứng Datadog (D4).

**Báo cáo cuối:** bảng 3 ca × 6 câu (đã có/thiếu, kèm link tới bước chứng minh); danh sách file đã sửa; kết quả test; trạng thái 5 monitor; các điểm mục 9 đã trả lời; những gì chưa xác minh.
