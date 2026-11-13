---
doc_id: SMIOT-VIDEO-01
title: "Kịch bản video demo SMIOT: bản đồ thao tác"
submission_section: "Video demo"
project: "SMIOT Smart Farm"
competition: "MongoDB User Group Vietnam Hackathon 2026: Real-time Operations"
version: "3.0"
date: "2026-11-07"
language: vi
data_label: synthetic
status: draft
---

# Kịch bản video demo SMIOT: bản đồ thao tác

## Tóm tắt

Video khoảng 9 phút 30 giây, quay màn hình, lồng tiếng, phụ đề tiếng Việt và tiếng Anh, 16:9, 1080p.

Đây là **bản hướng dẫn thao tác có giải thích**, không chỉ là kể chuyện. Mỗi cảnh đi theo một khuôn: đi từ đâu, bấm vào đâu, màn hình hiện gì, chỉ số hay dòng log đó nghĩa là gì, vì sao nó chứng minh điều đang nói.

**Cấu trúc xương sống.** Ca 3 (`smiot.service` dừng) là đường đi chính qua Metrics, Monitor, Workflow, Guard. Logs và Traces theo mã sự cố được giải thích ở Ca 2 vì sự cố đó có log và span gắn mã; Ca 1 là cảnh ngắn về quyết định từ chối restart. MongoDB có một cảnh riêng với màn hình thật.

**Khuôn mỗi bước.**

| Cột | Nghĩa |
|---|---|
| Đi từ đâu và bấm gì | Trang xuất phát, thao tác, trang đến |
| Chỉ vào | Đúng thứ trên màn hình cần nhìn |
| Ý nghĩa (lời dẫn) | Nó là gì, đọc thế nào, vì sao quan trọng |

Thẻ: [VO] lời dẫn, [Action] thao tác, [TEXT] chữ hiện. Tốc độ đọc khoảng 2,3 từ mỗi giây.

## 1. Gói và hook

| Hạng mục | Nội dung |
|---|---|
| Tiêu đề | "2,4%: Hệ thống tưới nên làm gì?" |
| Hình đại diện | Đường biểu đồ gãy ngang, số **2,4%** rất lớn, chữ **TƯỚI?** gạch chéo đỏ |
| Hook chọn dùng | Ứng viên 1 ghép 3: "Hai phẩy bốn phần trăm." rồi "Quy tắc tưới thông thường sẽ tưới" |
| Hook thay thế | "Có một kiểu sự cố mà đáp án đúng là đừng làm gì cả." (cho bản Shorts) |

## 2. Kịch bản

### Cảnh 0. Hook (0:00–0:25, khoảng 58 từ)

| Đi từ đâu và bấm gì | Chỉ vào | Ý nghĩa (lời dẫn) |
|---|---|---|
| Dashboard Ca 2, phóng vào ô độ ẩm đất | Đường Node 2 gãy ngang ở 2,4% | [VO] "Hai phẩy bốn phần trăm. Đó là độ ẩm đất cảm biến báo về, và nó không nhúc nhích suốt nhiều phút. Mẫu vẫn đến đều. Quy tắc tưới thông thường sẽ nói: đất khô, tưới đi. Trong video này, bạn sẽ thấy ba lần SMIOT quyết định mà phản xạ thông thường sẽ làm sai, kèm từng bước chứng minh trên Datadog và MongoDB." [TEXT] "2,4%" rồi "Quy tắc thường: TƯỚI" |

### Cảnh 1. Bản đồ của video (0:25–0:55, khoảng 70 từ)

| Đi từ đâu và bấm gì | Chỉ vào | Ý nghĩa (lời dẫn) |
|---|---|---|
| Đồ họa năm điểm dừng nối nhau | Metrics → Monitor → Workflow → Logs và Traces → MongoDB | [VO] "Chúng ta đi theo một đường. Metrics cho biết có chuyện gì. Monitor biết khi nào phải báo. Workflow thực hiện hành động. Logs và Traces kể lại điều đã xảy ra. MongoDB chứng minh đã phục hồi." |
| Nhãn góc dưới | "Dữ liệu tổng hợp · PLC ảo" | [VO] "Xin nói trước: dữ liệu trong video là dữ liệu tổng hợp, bơm là PLC ảo. Hệ thống không điều khiển thiết bị vật lý." |

### Cảnh 2. Ca 2: số đo đứng yên, và cách đọc Metrics, Logs, Traces (0:55–3:25, khoảng 345 từ)

Chuẩn bị: mở dashboard khung giờ Ca 2; mở sẵn trang monitor `339977691`; mở sẵn Logs Explorer và Traces Explorer với bộ lọc mã sự cố. Nếu có hồ sơ Ca 2 trạng thái `recovered` trên `/incident` (ví dụ hồ sơ 03/11), dùng hồ sơ đó cho bước 2.7.

| Bước | Đi từ đâu và bấm gì | Chỉ vào | Ý nghĩa (lời dẫn) |
|---|---|---|---|
| 2.1 Metrics | Dashboard `nkc-685-vw8`, khung giờ Ca 2 | Ô "Soil humidity by node": hai đường, mỗi node một đường | [VO] "Đây là dashboard. Ô này vẽ độ ẩm đất của từng node, trục đứng là phần trăm. Node 1 dao động quanh bốn mươi. Node 2 gãy ngang ở hai phẩy bốn: số đo đứng yên." |
| 2.2 Metrics | Cuộn xuống ô "Soil temperature, EC and telemetry freshness" | Đường `sample_age_seconds` (tuổi mẫu) | [VO] "Đường này là tuổi của mẫu mới nhất, tính bằng giây. Nó thấp và ổn định, nghĩa là mẫu vẫn đến. Vậy không phải mất kết nối: số đo kẹt thật." |
| 2.3 Metrics | Ô "MongoDB dependency" và "MQTT dependency" | Giá trị 1 | [VO] "Hai ô này cho biết cơ sở dữ liệu và bộ nhận tin còn sống: bằng một là sống, bằng không là chết. Cả hai đều bằng một, nên lỗi không nằm ở hạ tầng." |
| 2.4 Monitor | Bấm sang monitor `339977691` | Truy vấn `sensor_flatline`, ngưỡng lớn hơn 0, trạng thái Alert | [VO] "Monitor này đo một chỉ số do ứng dụng tính: mười mẫu liên tiếp chênh nhau không quá không phẩy không một thì chỉ số bằng một. Lớn hơn không là báo động. Ca này báo sau ba trăm mười một giây." |
| 2.5 Logs | Từ trang sự cố bấm "Logs của sự cố", hoặc mở Logs Explorer với `@incident.id:` và mã sự cố | Cột `event`, `kind`, `node.id`, `incident.id` | [VO] "Đây là log. Mỗi dòng là một mẫu đo đến trong lúc sự cố đang mở, cách nhau ba mươi giây. Trường `incident.id` là mã nối log với đúng sự cố này. Nhờ đó ta chứng minh được dữ liệu vẫn vào, dù số đo kẹt." |
| 2.6 Traces | Từ Logs bấm sang Traces, bộ lọc `@incident.id:*`, mở một trace `mqtt.message.process` | Resource `farm/sensor`, thuộc tính `incident.id`, `farm.key`, `mqtt.topic`, thanh thời gian khoảng mười mili giây | [VO] "Đây là trace. Một trace là hành trình của một bản tin: nhận từ MQTT rồi xử lý. Thanh ngang là thời gian, khoảng mười mili giây. Cùng mã sự cố, nên từ sự cố ta nhảy được tới đúng bản tin này." Nếu trace có span `insert telemetry`: "Span này là lần ghi một tài liệu vào MongoDB." |
| 2.7 Quyết định | Quay lại `/incident`, mở sự cố Ca 2 | Dòng quyết định `BLOCKED_HOLD`, các bơm ảo ở OFF | [VO] "Quy tắc tưới thông thường nói đất khô thì tưới, vì hai phẩy bốn thấp hơn ba mươi. Hệ thống ghi một quyết định chặn tưới, giữ an toàn. Chỉ khi số đo dao động trở lại, đủ mười mẫu, biên độ đủ lớn, monitor về OK và PLC ảo xác nhận, bộ xác minh mới nhả." [TEXT] "2,4% < 30% → TƯỚI" gạch đi, "CHẶN" |

**Hook nối:** [VO] "Ca tiếp theo ngược trực giác hơn: lần này hệ thống từ chối làm bất cứ điều gì."

### Cảnh 3. Ca 1: từ chối restart (3:25–4:15, khoảng 115 từ)

| Bước | Đi từ đâu và bấm gì | Chỉ vào | Ý nghĩa (lời dẫn) |
|---|---|---|---|
| 3.1 Metrics | Dashboard khung giờ Ca 1 | Đường `sample_age_seconds` thấp | [VO] "Giao diện báo thiết bị offline. Nhưng tuổi mẫu chỉ vài giây: dữ liệu vẫn tươi." |
| 3.2 Monitor | Chia đôi màn hình: monitor `341409441` và monitor `339977703` | Một bên Alert, một bên OK | [VO] "Hai monitor cùng lúc. Bên trái đo độ lệch giữa giao diện và trạng thái tính từ MongoDB, và đang báo. Bên phải đo tuổi mẫu, và vẫn xanh. Hai bên mâu thuẫn, nghĩa là lỗi nằm ở hiển thị, không ở dữ liệu." |
| 3.3 Workflow | Bấm sang workflow `e2835af0…`, chọn lượt lúc 04:50:21Z | Bước điều kiện trả đúng, bước Echo ghi `REFUSED_RESTART`, không có bước nào chạm tới máy chủ | [VO] "Workflow chạy sau đúng một phút và chỉ ghi một dòng: từ chối restart. Restart lúc này chỉ xóa phiên và bằng chứng mà không đổi được dữ liệu. Có lúc đáp án đúng là: đừng làm gì." [TEXT] **REFUSED_RESTART** |

**Hook nối:** [VO] "Còn khi một dịch vụ thật sự chết? Câu hỏi là: chết cái nào?"

### Cảnh 4. Ca 3: xương sống từ Metrics đến Guard (4:15–6:45, khoảng 345 từ)

Chuẩn bị: mở sẵn Metrics Explorer từ nút "Mở trong Datadog →" của sự cố Ca 3; mở sẵn Logs Explorer với `source:smiot-recovery`.

| Bước | Đi từ đâu và bấm gì | Chỉ vào | Ý nghĩa (lời dẫn) |
|---|---|---|---|
| 4.1 Metrics | Metrics Explorer, truy vấn `systemd.unit.active`, nhóm theo unit | Sáu đường, chỉ `smiot.service` rơi xuống không từ 03:06:35Z đến 03:13:05Z | [VO] "Đây là trạng thái của sáu dịch vụ trên máy. Một nghĩa là đang chạy, không nghĩa là dừng. Chỉ một đường rơi xuống: smiot.service. MongoDB và MQTT vẫn sống suốt thời gian đó." |
| 4.2 Metrics | Dashboard khung giờ Ca 3 | Các đường `smiot.*` bị đứt | [VO] "Trên dashboard, các đường của ứng dụng đứt. Đứt không có nghĩa là bằng không, mà là không có tín hiệu: ứng dụng tự gửi chỉ số, nên khi nó chết thì chính nó không còn gì để gửi." |
| 4.3 Metrics | Metrics Explorer, truy vấn `smiot.external.sample_age_seconds` | Đường tăng đều (đọc đỉnh trên màn hình) | [VO] "Vì vậy chúng tôi có một người quan sát độc lập đặt ngoài ứng dụng. Cứ ba mươi giây nó đo tuổi mẫu mới nhất. Đường này tăng đều: mẫu mới thôi đến." |
| 4.4 Monitor | Bấm monitor `340356283` | Truy vấn `systemd.unit.active` của `smiot.service`, trung bình năm phút, ngưỡng nhỏ hơn hoặc bằng không; Alert lúc 03:11:43Z | [VO] "Monitor này lấy trung bình năm phút của trạng thái dịch vụ, báo khi nó bằng không. Dịch vụ dừng lúc 03:06:32Z, monitor báo lúc 03:11:43Z, tức ba trăm mười một giây sau. Khớp với cửa sổ năm phút." |
| 4.5 Workflow | Bấm sang workflow `b83453ff…`, mở lượt `06cb1b46…` | Lượt chạy 03:12:43Z, trạng thái Success, bước `recover-smiot-web` | [VO] "Monitor kích hoạt workflow. Sau một phút, workflow chạy một bước trên máy thông qua Private Action Runner: đó là đoạn guard." |
| 4.6 Guard | Đồ họa cây quyết định guard (Hình 5.1 trong tài liệu 03) | Các điều kiện: đĩa dưới 85%, MongoDB và MQTT đang chạy, thời gian chờ, khóa chống chạy chồng | [VO] "Guard không start ngay. Nó kiểm đĩa, kiểm MongoDB và MQTT, kiểm thời gian chờ và khóa chống chạy chồng. Chỉ khi tất cả đạt, nó chạy đúng một lệnh." [TEXT] `systemctl start smiot.service` |
| 4.7 Logs | Logs Explorer, `source:smiot-recovery` | Dòng 03:13:23Z: `action: start`, `service: smiot.service`, `result: verified`, `reason: app_http_and_fresh_mongodb_telemetry`, `run_id` | [VO] "Đây là log của guard. `action` là start, đúng một dịch vụ. `result` là verified: đã xác minh. `reason` nói vì sao: HTTP của ứng dụng trả về và có mẫu MongoDB mới. Guard không tin lệnh đã chạy xong, nó đòi bằng chứng." |
| 4.8 Logs | Logs Explorer, biểu đồ số log theo thời gian | Log của ứng dụng dừng ở 03:06:26Z | [VO] "Để ý: suốt bảy phút ứng dụng chết, nó không có log. Chuyện được kể bởi người quan sát ngoài và guard. Khi một hệ thống chết, bằng chứng phải đến từ nơi khác." |
| 4.9 Metrics | Quay lại `systemd.unit.active` | Đường `smiot.service` trở về một lúc 03:13:20Z | [VO] "Dịch vụ chạy lại, HTTP trả hai trăm, mẫu mới đến. Bốn trăm mười tám giây từ lúc dừng đến lúc có bằng chứng." [TEXT] "418 s (một lần quan sát)" |

**Hook nối:** [VO] "Làm sao đi từ cảnh báo đến bằng chứng nhanh nhất? Một trang."

### Cảnh 5. Một trang cho người chấm (6:45–7:30, khoảng 105 từ)

| Bước | Đi từ đâu và bấm gì | Chỉ vào | Ý nghĩa (lời dẫn) |
|---|---|---|---|
| 5.1 | `/incident`, bấm thẻ Ca 3 | Danh sách ba thẻ, dải ô theo lần diễn tập | [VO] "Từ danh sách, mỗi ca một thẻ. Bấm vào thẻ Ca 3." |
| 5.2 | Trang chi tiết, khối "Metric của sự cố" | Hai metric và liên kết dashboard, khung giờ | [VO] "Khối này liệt kê metric liên quan và mở sẵn Datadog đúng khung giờ sự cố. Bấm là tới." |
| 5.3 | Bấm "Mở trong Datadog →" | Metrics Explorer mở đúng khung giờ | [VO] "Datadog mở đúng khoảng thời gian của sự cố." |
| 5.4 | Cuộn tới "Hồ sơ 6 câu hỏi" | Cột nguồn: nhãn "Datadog →" hay "MongoDB" | [VO] "Sáu câu hỏi cho mỗi sự cố. Mỗi câu ghi nguồn: phát hiện và nguyên nhân là Datadog, dữ liệu bị ảnh hưởng và bằng chứng phục hồi là MongoDB." |
| 5.5 | Cuộn tới "Tác động (từ MongoDB)" | Các thẻ số, biểu đồ "Chất lượng dữ liệu theo phút": mẫu hợp lệ, bất thường, phút thiếu mẫu | [VO] "Biểu đồ này do MongoDB tính: mỗi phút có bao nhiêu mẫu hợp lệ, bất thường, và phút nào thiếu mẫu. Khoảng thiếu lúc ứng dụng dừng hiện thành cột xám." |

### Cảnh 6. MongoDB: thể hiện ra và làm được gì (7:30–9:00, khoảng 205 từ)

Chuẩn bị: mở Compass hoặc `mongosh` bằng tài khoản **chỉ đọc**, cơ sở dữ liệu `smiot`; không để lộ chuỗi kết nối; chỉ chạy lệnh đọc.

| Bước | Đi từ đâu và bấm gì | Chỉ vào | Ý nghĩa (lời dẫn) |
|---|---|---|---|
| 6.1 Time Series | Collection `telemetry`, xem thông tin collection | `timeseries`: `timeField: timestamp`, `metaField: meta`, `granularity: seconds` | [VO] "Đây là nơi lưu mẫu đo, một Time Series collection. Mỗi mẫu có thời điểm và thông tin nguồn: farm, node, loại số đo. Cấu trúc này giúp lưu chuỗi mẫu dày đặc gọn và đọc theo khoảng thời gian nhanh." |
| 6.2 Tài liệu | Mở một tài liệu `telemetry` | `meta` và `readings` | [VO] "Mỗi mẫu có phần meta để lọc theo node, và phần readings là các số đo." |
| 6.3 Hồ sơ sự cố | Collection `operational_incidents`, mở một sự cố | `status`, `opened_at`, `detected_at`, `recovered_at`, `monitor_id`, `workflow_id` | [VO] "Hồ sơ vòng đời của sự cố: mở lúc nào, phát hiện lúc nào, phục hồi lúc nào, và mã monitor, workflow bên Datadog. Đây là chỗ MongoDB nối với Datadog." |
| 6.4 Sổ lệnh | Collection `action_ledger`, mở một lệnh HOLD hoặc CLEAR | `_id` là `command_id`, trạng thái `requested`, `published`, `acknowledged`, `verified` | [VO] "Sổ lệnh ghi từng lệnh giữ và nhả, mỗi lệnh có mã riêng. Vì MongoDB chạy standalone, không có giao dịch, nên chúng tôi thiết kế để ghi lại cùng một lệnh nhiều lần vẫn an toàn." |
| 6.5 Chỉ mục | Tab Indexes của `telemetry` và `operational_incidents` | Chỉ mục ghép theo farm, loại số đo, node, thời gian; chỉ mục một phần `active_incident_by_scope` | [VO] "Chỉ mục ghép giúp lấy mẫu mới nhất theo node. Chỉ mục một phần chỉ phủ các sự cố đang mở, nên nhỏ và nhanh khi hỏi: bây giờ có sự cố nào đang mở không." |
| 6.6 Aggregation | Aggregation builder hoặc mã pipeline hộp đen | Bốn nhánh `$unionWith`, `$setWindowFields` với `$shift`, sự kiện `telemetry_gap` | [VO] "Đây là phần hay nhất. Một aggregation gộp bốn nguồn: mẫu lỗi, quyết định, sổ lệnh và telemetry, thành dòng thời gian của sự cố. Window function so từng mẫu với mẫu trước của cùng node, nếu cách nhau hơn chín mươi giây thì đánh dấu một khoảng thiếu mẫu, ngay trong cơ sở dữ liệu. Thay vì bốn truy vấn rồi ghép ở ứng dụng." |

**Bảng chốt trên màn hình sau 6.6** (chữ hiện trong 6 giây):

| MongoDB làm được | Dùng cho |
|---|---|
| Time Series | Chuỗi mẫu 30 giây theo node |
| Chỉ mục một phần | Truy vấn sự cố đang mở |
| `$unionWith` bốn nhánh | Dòng thời gian sự cố |
| `$setWindowFields` và `$shift` | Khoảng thiếu mẫu |
| `_id` là `command_id` | Ghi lại an toàn, không cần giao dịch |

### Cảnh 7. Kết (9:00–9:30, khoảng 70 từ)

| Đi từ đâu và bấm gì | Chỉ vào | Ý nghĩa (lời dẫn) |
|---|---|---|
| Cắt lại ba khoảnh khắc | Đường 2,4%, `REFUSED_RESTART`, một đường gãy trong sáu | [VO] "Ba sự cố, ba câu trả lời: giữ an toàn rồi mới nhả, từ chối restart, chỉ khởi động đúng một dịch vụ. Mỗi lần: Metrics cho thấy, Monitor báo, Workflow làm, Logs và Traces kể, và MongoDB chứng minh." |
| Màn hình cuối | Tên dự án, nhãn "Dữ liệu tổng hợp · PLC ảo" | [VO] "Phục hồi chỉ được tính khi dữ liệu đọc lại chứng minh điều đó. Đây là SMIOT." |

## 3. Bảng giải nghĩa nhanh (dùng để đọc lời dẫn và để làm chữ hiện)

### 3.1 Metrics

| Chỉ số | Giá trị và đơn vị | Đọc thế nào | Bất thường là gì |
|---|---|---|---|
| `smiot.telemetry.soil_humidity` | Phần trăm độ ẩm đất, theo node | Dao động quanh một mức | Đứng yên ở một giá trị |
| `smiot.telemetry.sample_age_seconds` | Giây | Tuổi mẫu mới nhất; nhỏ là dữ liệu tươi | Tăng đều là không có mẫu mới |
| `smiot.dependency.mongo.up`, `smiot.dependency.mqtt.up` | 1 hoặc 0 | 1 là phụ thuộc còn sống | 0 là phụ thuộc chết |
| `smiot.telemetry.sensor_flatline` | 1 hoặc 0 | 1 khi mười mẫu liên tiếp gần như bằng nhau | Lớn hơn 0 kích hoạt monitor Ca 2 |
| `smiot.telemetry.status_mismatch` | 1 hoặc 0 | 1 khi giao diện lệch với trạng thái tính từ MongoDB | Lớn hơn 0 kích hoạt monitor Ca 1 |
| `systemd.unit.active` | 1 hoặc 0 theo unit | 1 là dịch vụ đang chạy | 0 là dịch vụ dừng; monitor Ca 3 dựa vào đây |
| `smiot.external.sample_age_seconds` | Giây, do probe ngoài đo | Người quan sát độc lập; vẫn có khi ứng dụng chết | Tăng đều khi mẫu mới thôi đến |
| `smiot.external.app_up` | 1 hoặc 0 | 1 là ứng dụng trả lời HTTP | 0 là ứng dụng không trả lời |

### 3.2 Logs

| Trường | Ý nghĩa |
|---|---|
| `event: smiot_incident_event`, `kind: telemetry_received` | Một mẫu đo đến trong lúc sự cố đang mở |
| `incident.id`, `farm.key`, `node.id` | Mã sự cố, nhà màng, node; dùng để lọc và nối với MongoDB |
| `event: smiot.guarded_recovery` | Một lần chạy của guard |
| `action`, `service` | Việc guard làm (start) và dịch vụ bị tác động (`smiot.service`) |
| `result`, `reason` | Kết quả (verified) và lý do (HTTP và mẫu MongoDB mới) |
| `run_id` | Mã một lần chạy của guard, dùng để truy vết |

### 3.3 Traces

| Thành phần | Ý nghĩa |
|---|---|
| `mqtt.message.process`, resource `farm/sensor` | Xử lý một bản tin cảm biến nhận từ MQTT |
| `incident.id`, `farm.key`, `mqtt.topic` | Gắn trace với sự cố, nhà màng, chủ đề MQTT |
| Span `insert telemetry` (khi có) | Một lần ghi một tài liệu vào MongoDB |
| `pymongo.checkout` | Lấy một kết nối từ nhóm kết nối tới MongoDB |

## 4. Liên kết phát lại (đã kiểm chứng định dạng)

| Mục đích | Liên kết |
|---|---|
| Dashboard Ca 1 (06/11, 04:40–05:10 UTC) | `https://app.datadoghq.com/dashboard/nkc-685-vw8?from_ts=1793940000000&to_ts=1793941800000&live=false` |
| Dashboard Ca 2 (06/11, 02:30–02:55 UTC) | `https://app.datadoghq.com/dashboard/nkc-685-vw8?from_ts=1793932200000&to_ts=1793933700000&live=false` |
| Dashboard Ca 3 (06/11, 03:00–03:20 UTC) | `https://app.datadoghq.com/dashboard/nkc-685-vw8?from_ts=1793934000000&to_ts=1793935200000&live=false` |
| Monitor Ca 1, đối chứng Ca 1, Ca 2, Ca 3 | `https://app.datadoghq.com/monitors/341409441`, `/339977703`, `/339977691`, `/340356283` |
| Lượt chạy workflow Ca 3 | `https://app.datadoghq.com/workflow/b83453ff-e122-4148-9519-e698f2effa7f?instance=06cb1b46-e357-4ee1-94e1-fcbd4144fbd6` |
| Workflow Ca 1 | `https://app.datadoghq.com/workflow/e2835af0-63fc-48e0-9562-2a1ee4a351d3`, chọn lượt lúc 04:50:21Z |
| Logs của guard (Ca 3) | Logs Explorer, truy vấn `source:smiot-recovery`, khung 06/11 03:00–03:30 UTC |
| Logs theo mã sự cố (Ca 2, 06/11) | Logs Explorer, truy vấn `@incident.id:INC-SMIOT-20261106T023640-164FBE41`, khung 06/11 02:36–03:07 UTC |
| Traces theo mã sự cố | APM Traces, truy vấn `service:smiot-smart-farm @incident.id:*`, khung 06/11 02:30–03:30 UTC |
| Metric của sự cố | Trên `/incident/{id}`, khối "Metric của sự cố", nút "Mở trong Datadog →" |

## 5. Chuẩn bị, giới hạn và điều cần kiểm khi quay thật

| Việc | Cách làm |
|---|---|
| Quay trước hôm nay | Tài khoản Datadog dùng thử còn khoảng 9 ngày tính từ 07/11, hết hạn khoảng 16/11, ngay sau chung kết 15/11 |
| Múi giờ | Datadog đang hiển thị UTC+07:00; giữ nguyên để lời dẫn khớp màn hình |
| Che thông tin nhạy cảm | Che hoặc cắt thanh địa chỉ khi mở ứng dụng trên EC2 (chứa IP công khai); không quay AWS Console có số tài khoản; không mở tệp `.env` hay cấu hình `/etc/smiot` |
| MongoDB | Dùng tài khoản chỉ đọc; che chuỗi kết nối; chỉ chạy lệnh đọc |
| Workflow Ca 2 | Không mở khung cấu hình bước của workflow Ca 2 (có thông tin xác thực trong cấu hình); video này không cần mở workflow Ca 2 |
| Nhãn dữ liệu | Nhãn nhỏ "Dữ liệu tổng hợp · PLC ảo" hiện suốt video |

**Điều cần kiểm khi quay thật (không bịa trên màn hình):**
1. Sự cố Ca 2 ngày 06/11 (`164FBE41`) có log `telemetry_received` kéo dài đến 03:06:26Z, tức vẫn mở khi Ca 3 bắt đầu. Với bước 2.7, dùng một hồ sơ Ca 2 có trạng thái `recovered` trên `/incident` nếu có; nếu không có, dừng ở bước giữ HOLD.
2. Ở bước 2.6, chỉ nhắc span `insert telemetry` nếu trace bạn mở thật sự có nó.
3. Ở bước 4.3, đọc giá trị đỉnh của `smiot.external.sample_age_seconds` ngay trên màn hình; nếu khác 406,7 giây thì nói đúng số đang hiện.
4. Mọi con số 311, 206, 418 giây là một lần quan sát, không phải số trung bình.
5. Các chỉ dẫn "chia đôi màn hình" và "làm nổi một đường" là chỉ dẫn dựng, chưa kiểm bằng cảnh quay thật.

## 6. Điều nên nói và không nên nói

| Nên nói | Không nên nói |
|---|---|
| "Dữ liệu tổng hợp", "PLC ảo", "bơm ảo" | "Dữ liệu thật", "thiết bị thật bị hỏng" |
| "Định kỳ ba mươi giây" | "Thời gian thực" |
| "Giữ an toàn rồi mới nhả", "chỉ start đúng một dịch vụ" | "Tự động sửa lỗi", "tự phục hồi" |
| "Một lần quan sát" với 311, 206, 418 giây | Nói các số đó như hiệu năng trung bình |
| "Phục hồi được xác nhận bằng dữ liệu đọc lại" | "Datadog xác nhận phục hồi" |

## 7. Hậu kỳ, đăng tải và dự phòng

| Hạng mục | Gợi ý |
|---|---|
| Phụ đề | Tiếng Việt ở dưới, tiếng Anh nhúng thêm cho giám khảo quốc tế |
| Xuất file | MP4 H.264, 1080p, 30 fps |
| YouTube | Chế độ "Không công khai" để dán liên kết vào biểu mẫu nộp |
| Chương | 0:00 Hook · 0:25 Bản đồ · 0:55 Ca 2 · 3:25 Ca 1 · 4:15 Ca 3 · 6:45 Trang sự cố · 7:30 MongoDB · 9:00 Kết |
| Nếu đăng công khai | Đọc ba chỉ số trong Studio: CTR, giữ chân 30 giây đầu, tỷ lệ xem trung bình; không tự bịa số |
| Dự phòng | Datadog không tải được: dùng ảnh chụp trong `outputs/submission_export/evidence_20261106/`. Trang EC2 không mở: dùng ảnh `/incident` và nói rõ đây là ảnh chụp |
