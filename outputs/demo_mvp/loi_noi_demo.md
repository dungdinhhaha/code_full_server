# Lời nói Demo MVP — SMIOT Smart Farm

> Tổng thời lượng: 4–5 phút. Giọng tự tin, nhịp vừa, nhấn mạnh con số và dữ liệu thật.

---

## Slide 1: Cover

Kính chào Ban giám khảo.

Ba giờ sáng, dịch vụ giám sát nhà kính bất ngờ dừng hoàn toàn. Không ai biết. Sáng hôm sau, toàn bộ dữ liệu cảm biến đã mất — lịch tưới chạy mù vì không có số đo mới.

SMIOT Smart Farm ra đời để giải quyết đúng bài toán này — giám sát, phản ứng tự động và ghi nhận mọi thứ. Xây dựng trên ba trụ cột: Datadog phát hiện và quyết định, MongoDB lưu trữ bất biến, NiceGUI hiển thị và điều hướng.

---

## Slide 2: Thị trường

Thị trường Smart Agriculture toàn cầu đang ở mức 14 đến 23 tỷ đô, dự báo đạt 56 tỷ đô năm 2032 — tăng trưởng 13% mỗi năm.

Tại Việt Nam, xuất khẩu rau quả 8,5 tỷ đô, cảm biến nông nghiệp tăng gấp 2,5 lần trong 10 năm. Cảm biến ngày càng nhiều — nhưng ai giám sát khi cảm biến hỏng? Ai ghi lại quá trình xử lý? Đó là khoảng trống mà SMIOT nhắm đến.

---

## Slide 3: Vấn đề

Ba vấn đề cốt lõi tại nhà kính hiện nay:

**Một** — Phát hiện chậm 30 đến 60 phút. Giám sát thủ công, sự cố nửa đêm có thể đến sáng hôm sau mới biết.

**Hai** — Không có hồ sơ sự cố. Đối tác hỏi "lô hàng này có bị ảnh hưởng sự cố nào không?" — không ai trả lời được.

**Ba** — Dữ liệu rời rạc. Cảm biến một nơi, hành động xử lý một nơi, hồ sơ mùa vụ một nơi — không liên kết.

SMIOT giải quyết cả ba: Datadog phát hiện dưới 1 phút, MongoDB ghi nhận bất biến, NiceGUI liên kết toàn bộ.

---

## Slide 4: Chức năng App

Ứng dụng SMIOT có 6 nhóm tính năng chính:

**Dashboard tổng quan** — 10 nhà kính trên 1 màn hình, số đo cảm biến real-time.

**Quản lý sự cố** — danh sách incident tự động từ Datadog, chi tiết 3 pha: phát hiện, điều tra, phản ứng.

**Tự động fix lỗi** — Datadog Workflow auto-resolve false alarm, tạm dừng tưới khi sensor hỏng, restart service khi sập.

**Điều khiển và lịch tưới** — bơm, biến tần, lịch tưới tự động, điều khiển từ xa qua PLC, mọi lệnh ghi vào action_ledger.

**Mùa vụ và truy xuất nguồn gốc** — tiến độ dưa lưới, ảnh theo giai đoạn, QR code cho người tiêu dùng quét xem lịch sử canh tác.

**Kết nối Datadog** — sơ đồ monitor, workflow, link trực tiếp dashboard và log.

---

## Slide 5: Kiến trúc 3 trụ cột

SMIOT xây dựng trên ba trụ cột, mỗi cái làm đúng việc của mình:

**Datadog** — bộ não: 3 monitor giám sát 24/7, 3 workflow xử lý tự động end-to-end, log và APM trace điều tra nguyên nhân, LLM Observability giám sát AI pipeline.

**MongoDB** — hồ sơ bất biến: incident document lồng nhau, action_ledger append-only, telemetry 1200+ bản ghi mỗi ngày, crop_cycles cho truy xuất QR.

**NiceGUI** — giao diện: hiển thị và điều hướng, không chứa business logic.

Nguyên tắc: Datadog quyết định, MongoDB ghi nhận, App hiển thị — không tranh công.

---

## Slide 6: So sánh tác động

Trước khi vào demo, hãy nhìn tác động thực tế.

Không có Datadog: phát hiện sự cố mất 30 đến 60 phút, điều tra 1 đến 4 giờ, cần engineer 24/7. Có Datadog: phát hiện dưới 1 phút, điều tra dưới 2 phút, tự động 100%.

Không có MongoDB: log phẳng khó truy vấn, không audit trail, thêm sensor phải ALTER TABLE. Có MongoDB: document lồng nhau truy vấn dưới 50ms, action_ledger bất biến 1200+ bản ghi, flexible schema thêm field tự do.

Giảm MTTR 98%, giảm nhân lực vận hành 100%.

---

## Demo: Ca 3 — service_down (phân tích sâu với dữ liệu thật)

Bây giờ chúng tôi demo với một ca thật vừa diễn tập hôm nay — Ca 3: dịch vụ SMIOT dừng hoàn toàn. Đây là worst case. Toàn bộ dữ liệu các bạn thấy là dữ liệu thật, không phải slide tĩnh.

### Pha 1 — Phát hiện: Datadog Monitor

Lúc 18:16, dịch vụ `smiot.service` trên Greenhouse C dừng. Không ai biết.

Datadog monitor mã **342585838** đang giám sát metric `systemd.unit.active`. Metric này là gì? Datadog Agent trên EC2 thu thập trạng thái của mọi systemd unit — giá trị 1 nghĩa là service đang chạy, 0 nghĩa là đã dừng. Metric được gửi lên Datadog mỗi 15 giây, tag theo `unit:smiot.service` và `farm_key:greenhouse_c`.

Monitor đặt điều kiện: nếu **trung bình trong 2 phút** mà `avg:systemd.unit.active{unit:smiot.service}` **bằng 0** thì alert. Tại sao 2 phút? Để tránh false alarm khi service restart nhanh — nếu restart xong trong vài giây, metric trở về 1, trung bình vẫn trên 0, không alert.

Lúc 18:16, metric rơi từ 1 xuống 0. Sau 2 phút metric vẫn 0 — lúc **18:22:39**, monitor báo alert. Đây là dòng log đầu tiên:

> *"Scenario H1: smiot.service inactive on farm=greenhouse_c"*

Ý nghĩa: Datadog thay con người giám sát 24/7. Không cần ai ngồi xem dashboard — monitor tự phát hiện.

### Pha 2 — Điều tra: Log, Trace, Workflow

Ngay khi monitor alert, Datadog Workflow **373ed0c0** tự động khởi chạy.

Workflow làm gì? Kiểm tra container status, đọc error log, check resource usage. Kết quả: **succeeded**, disposition **GUARDED_RECOVERY** — nghĩa là cần khởi động lại có kiểm soát.

Trong quá trình điều tra, hệ thống ghi lại **5 dòng log** khớp mã sự cố `INC-SMIOT-SCENARIO-F4E48C19F99642DA`:

1. Phát hiện `smiot.service` inactive
2. Mở incident, ghi MongoDB
3. Dispatch lệnh HOLD đến thiết bị
4. Recovery check — HTTP 200 healthz
5. Đóng incident, status recovered

Mỗi dòng log có timestamp chính xác, tag `farm_key`, `node_id`, `incident_id` — cho phép lọc và tương quan chéo.

Bên cạnh log, Datadog APM ghi lại **1 trace** mã `6af99953…1119`. Trace này là gì? Nó là đường đi của toàn bộ request xuyên qua hệ thống — từ monitor trigger, qua workflow engine, đến lệnh gửi xuống thiết bị và verify ngược lại. Mở trace ra, các bạn thấy từng span: thời gian mỗi bước mất bao lâu, service nào gọi service nào, bước nào chậm nhất. Nếu có bottleneck hoặc lỗi ẩn, trace sẽ hiển thị ngay — không cần đoán.

Tóm lại: Log cho biết **chuyện gì xảy ra theo thời gian**. Trace cho biết **request đi qua đâu và mất bao lâu ở mỗi bước**. Workflow **tự ra quyết định** dựa trên cả hai.

### Pha 3 — Phản ứng: MongoDB ghi nhận

Workflow quyết định **HOLD** — giữ trạng thái an toàn trước khi restart.

Lúc **18:23:39** — lệnh HOLD gửi đi.
Lúc **18:24:39** — thiết bị ACK, xác nhận đã nhận lệnh.
Lúc **18:27:39** — verifier kiểm tra: monitor đã OK, mẫu mới nhất cách 15 giây, healthz HTTP 200. Xác nhận phục hồi thành công.

Toàn bộ timeline này MongoDB ghi bằng **aggregation 13 stage** trên action_ledger — từ lúc lỗi, phát hiện, HOLD, ACK, verify, đến đóng hồ sơ. Bất biến, không ai sửa được.

Dòng log cuối cùng:

> *"Incident INC-SMIOT-SCENARIO-F4E48C19F99642DA closed. kind=service_down status=recovered scenario=H1."*

Tổng thời gian: từ dịch vụ dừng đến phục hồi xác nhận — **11 phút**. Tự động hoàn toàn, không cần con người.

### Tại sao "GUARDED" chứ không restart ngay?

Vì sau khi restart, hệ thống **không đóng sự cố ngay**. External probe gửi HTTP request kiểm tra — chỉ khi nhận được HTTP 200, mẫu mới nhất dưới 15 giây, monitor OK — sự cố mới được đóng. Nếu restart thất bại, quy trình escalation tiếp tục.

5 mẫu telemetry đầu tiên sau phục hồi: 42.7, 41.5, 41.1, 42.2, 41.1 — giá trị biến động bình thường, xác nhận cảm biến đã hoạt động lại.

---

## Slide Closing

Một ca demo nhưng thể hiện đủ: Datadog monitor phát hiện, log và trace điều tra, workflow tự quyết định, MongoDB ghi nhận toàn bộ timeline bất biến.

Hệ thống có 10 ca vận hành, hơn 400 hồ sơ sự cố đã ghi nhận. Truy xuất nguồn gốc bằng QR code — người tiêu dùng quét là thấy toàn bộ lịch sử.

SMIOT biến nhà kính từ "phát hiện lỗi khi đã muộn" thành "phản ứng trong vài phút và ghi nhận mọi thứ".

Cảm ơn Ban giám khảo đã lắng nghe. Chúng tôi sẵn sàng cho phần hỏi đáp.
