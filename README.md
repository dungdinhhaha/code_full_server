# SMIOT Smart Farm Observability — Demo

> [!IMPORTANT]
> Phần telemetry cảm biến và phần GDD tăng tốc trong README này là **dữ liệu mô phỏng**. Chúng dùng để trình diễn pipeline và Datadog, không phải số đo từ cảm biến vật lý hay dự báo thu hoạch thực tế.

## Trạng thái cloud đã kiểm chứng — 2026-11-03 (đọc phần này trước)

Trạng thái dưới đây là snapshot mới nhất; các mục Atlas/AP1 và hướng dẫn chạy localhost ở các phần sau là **lịch sử trước khi chuyển môi trường**, không phải cấu hình cloud hiện tại.

- AWS profile `aws-moi` xác minh account 920235987407, region ap-southeast-2; EC2 i-00bf2d3591d3ee0a2 (t3.small) đang chạy. Profile mặc định trỏ account khác (255103685766), vì vậy dùng `--profile aws-moi` khi thao tác dự án. Các service smiot, mongod (MongoDB Community), mosquitto, nginx, datadog-agent, wokwi-bridge đều active.
- Kiểm tra HTTPS công khai từ desktop: /, /login, /data, /chart, /traceability đều trả HTTP 200; đây là smoke test thủ công, chưa phải Datadog Synthetic và chưa kiểm tra đăng nhập/luồng nghiệp vụ.
- MongoDB Community 8.0.34 trên cùng EC2 là cơ sở dữ liệu đang chạy của app; không phải Atlas. Collection telemetry là Time Series (timestamp, meta); dữ liệu cảm biến trong demo được gắn nhãn synthetic. App và DB cùng trên EC2 tạo điểm lỗi đơn, phù hợp demo ngắn hạn chứ chưa phải HA/production.
- Datadog canonical cho dự án là US1: [Dashboard SMIOT](https://app.datadoghq.com/dashboard/nkc-685-vw8). Dashboard có 9 widgets, gồm telemetry, trạng thái Mongo/MQTT, SLO và 2 biểu đồ MongoDB DBM theo database_instance: throughput truy vấn và tổng query execution time.
- Monitor [Node 2 flatline (synthetic demo)](https://app.datadoghq.com/monitors/339977691) đang theo dõi số đo live; trạng thái chuyển theo dữ liệu publisher, không mặc định phải Alert.
- Đã chạy và xác nhận luồng phục hồi đầu-cuối ngày 2026-11-03 trên dữ liệu mô phỏng: publisher ACK chuyển Node 2 sang flatline 2,4%; monitor chuyển Alert; Datadog workflow gọi bộ kiểm tra phục hồi trong app; app từ chối CLEAR khi monitor còn Alert; sau khi publisher ACK chế độ bình thường, monitor chuyển OK, app xác minh 6 mẫu MongoDB mới (38,6–40,2%, mới nhất dưới 90 giây), gửi CLEAR và nhận ACK từ virtual PLC với cả 8 đầu ra bơm OFF. Action ledger MongoDB ghi trạng thái `verified`; lần thử này chứng minh kênh telemetry phục hồi và logic an toàn của virtual PLC, không chẩn đoán hay sửa đầu dò vật lý.
- Bridge đã cập nhật để chỉ nhả cờ HOLD và phát lệnh LED Wokwi `CLEAR` sau khi nhận sự kiện MongoDB/MQTT `CLEAR` có trạng thái `verified` từ bộ kiểm tra app, với monitor OK, ít nhất 6 mẫu mới/dao động và outputs off. Nó không tự CLEAR chỉ vì monitor OK. Đã triển khai lên EC2 và xác nhận log bridge `Application recovery verifier confirmed CLEAR; bridge latch released and Wokwi visual output cleared`; simulator Wokwi không cần chạy để app xác minh/điều khiển virtual PLC, và hiện Wokwi CLI chưa hoạt động.
- [SLO Trusted Telemetry Pipeline Availability](https://app.datadoghq.com/slo/886b6bcadb0157948e6faeba54c8a50b) có target 99% / 7 ngày, warning 99,5%, dựa trên ba monitor freshness/Mongo/MQTT. SLO mới tạo ngày 2026-11-03 nên chưa có đủ 7 ngày lịch sử. Node 2 flatline cố ý không nằm trong SLO nền tảng.
- Logs–traces đã được truy vấn trực tiếp trên Datadog US1: trace MQTT → MongoDB có 12 spans, cùng trace ID tìm được 2 log liên quan (farm/sensor và save_farm_sensor_to_db).
- Datadog Database Monitoring (DBM) cho MongoDB Community đang bật: Agent 7.85.0, user monitor chỉ có quyền đọc + clusterMonitor; cấu hình rõ dbm: true, query_metrics.enabled: true, cluster smiot-community. API US1 truy vấn trong 15 phút gần nhất trả 87 điểm cho mongodb.queries.count (0.8–4 query/s, điểm cuối 2 query/s), 87 điểm mongodb.queries.time và 55 điểm mongodb.connections.current. Đây là hoạt động truy vấn thật của DB trên workload chủ yếu synthetic; không phải truy vấn AI hay telemetry cảm biến vật lý.
- Tắt riêng thu thập schema (collect_schemas.enabled: false) để tránh lỗi quyền đọc MongoDB internal Time Series bucket system.buckets.telemetry; không mở rộng quyền DBM user. Sau sửa, Agent check Mongo thành công và không còn lỗi permission/schema mới trong log.
- HTTPS qua Nginx trả HTTP 200 cho 5 route từ cả EC2 và smoke test thủ công bên ngoài; HTTP thường chuyển hướng 301 sang HTTPS. Chưa tạo Datadog Synthetic test định kỳ.
- Wokwi bridge trên AWS đang chạy và nối MQTT; log ghi rõ đầu vào synthetic và output HOLD ảo. Điều này không chứng minh simulator Wokwi đang phát dữ liệu liên tục hay thiết bị vật lý nhận lệnh. Không có lệnh bơm/PLC thật được gửi.
- Để demo không phụ thuộc giới hạn phiên Wokwi, app cloud bật `SMIOT_DEMO_MODE=true`: publisher chạy trong service SMIOT, gửi telemetry MQTT liên tục. Virtual PLC subscribe `farm/control`, cập nhật bit đầu ra ảo rồi publish `farm/status` để giao diện nhận phản hồi. Đây là vòng giao tiếp hai chiều trên MQTT; không điều khiển PLC/bơm vật lý. `SMIOT_DEMO_INTERVAL_SECONDS` mặc định 30 giây. Nguồn telemetry được gắn provenance nội bộ `smiot_demo_stream` để lọc khỏi số liệu cảm biến vật lý.
- GDD/window-function đã chạy qua MongoDB aggregation cho 30 ngày synthetic, theo cadence khai báo; kết quả chỉ minh họa phương pháp, không phải ngày trồng hay dự báo nông học đã xác nhận.
- Trang **Kế hoạch thu hoạch** (`/mongodb-lab`) kể câu chuyện mùa vụ dưa lưới: từ mốc đậu quả của một lô đến thời điểm bắt đầu kiểm tra quả, chuẩn bị nhân lực, đóng gói và lịch giao hàng. MongoDB Time Series gom mẫu nhiệt độ theo ngày; aggregation tính độ phủ, khoảng trống, xu hướng trượt 7 ngày và nhiệt tích lũy (GDD) bằng `$setWindowFields`. Mốc theo dõi tham khảo nghiên cứu dưa lưới Khang Nguyên tại Đại học Đồng Tháp. GDD giúp giải thích nhịp nhiệt, không tự chốt ngày hái. Hồ sơ mùa vụ nằm trong `crop_cycles` và `traceability_events`, còn nhiệt độ đọc từ collection telemetry hiện có. Xem [seed_harvest_story.py](scripts/seed_harvest_story.py). Thời gian đọc/aggregation là phép đo mỗi lần xem, không phải benchmark so SQL.
- AWS Cost Explorer cho 2026-10-26 đến 2026-11-02 trả mỗi ngày 0 USD nhưng `Estimated=true` và không có nhóm dịch vụ; `describe-budgets` không thấy budget nào. Đây chưa phải bằng chứng chi phí thực là $0. Cần đợi billing data và thiết lập budget/alert $50; chưa có đối chiếu Datadog usage hoặc cost/1.000 bản tin hợp lệ.
- **MongoDB backup/restore đã kiểm chứng (2026-11-03):** backup service/timer chạy trên EC2. `mongodump` cũ thất bại vì app user không được đọc `system.buckets.telemetry`; đã sửa bằng dump các collection nghiệp vụ và `mongoexport` Time Series qua collection API, đóng gói kèm manifest, tải lên S3 với SSE-S3 AES-256. Bản mới `backups/20261103T113718Z.tar.gz` có 154.618 mẫu telemetry. Đã tải chính object này về EC2 và restore vào các collection kiểm tra tạm: Time Series **154.618/154.618** và `operational_incidents` **1/1**; collection nguồn không bị thay đổi. Role EC2 chỉ được bổ sung `s3:GetObject` cho `backups/*`. Xem [bằng chứng backup/restore](docs/MONGODB_BACKUP_RESTORE_DRILL_20261103.md) và script [mongodb_backup.sh](scripts/aws/mongodb_backup.sh), [mongodb_restore_drill.sh](scripts/aws/mongodb_restore_drill.sh). Snapshot EBS mã hóa `snap-0634c5f0e1a247421` ở trạng thái `completed`, nhưng chưa diễn tập khôi phục snapshot.
- Việc còn lại trước production: xử lý điểm lỗi đơn, tạo HTTPS/public Synthetic kiểm tra định kỳ, xác minh Wokwi session thực, chờ đủ cửa sổ SLO và billing data. AWS Cost Explorer cho 2026-10-26 đến 2026-11-02 trả mỗi ngày 0 USD nhưng `Estimated=true` và không có nhóm dịch vụ; chưa có budget nào và chưa có đối chiếu Datadog usage hoặc cost/1.000 bản tin hợp lệ.

### Cập nhật sự cố mới nhất — 2026-11-03

- Sự cố `INC-SMIOT-20261103T114321-BD19A22C` đã được chạy xuyên suốt: publisher ACK flatline 2,4% → MongoDB nhận mẫu liên tục → Datadog monitor Alert → workflow xác nhận HOLD ảo, outputs OFF → publisher ACK chế độ bình thường → 7 mẫu MongoDB dao động 39,3–41,0% → monitor OK → bộ xác minh app gửi CLEAR và nhận ACK từ virtual PLC → incident `recovered`.
- Bits Investigation mới hoàn tất sau khi sửa kết luận ban đầu: nguyên nhân được xác định là kịch bản flatline được tiêm vào publisher; giả thuyết mất instrumentation/log bị bác bỏ vì sequence vẫn tăng và log/telemetry vẫn đến. Xem [hồ sơ bằng chứng đầu-cuối](docs/INC-SMIOT-20261103T114321-BD19A22C_EVIDENCE.md).
- Monitor US1 hiện có link Related Logs dùng structured attributes và vẫn giữ nguyên workflow trigger. Link đã mở thành công, trả 10 log Node 2 ở thời điểm xác minh.
- Bits Chat cũ vẫn hiển thị `6/19`. Bằng chứng hiện có chưa giải thích mẫu số 19; không tuyên bố bộ đếm này đã được sửa. Sự cố là synthetic, không chứng minh đầu dò thật hỏng/được sửa hoặc bơm vật lý đã hoạt động.
## Mục tiêu

SMIOT giám sát nhà kính dưa lưới bằng ứng dụng Python, MQTT, MongoDB Community trên EC2 và Datadog US1. MongoDB là kho dữ liệu chính; `farm_data.db` được giữ làm bản backup SQLite, không còn là nơi app ghi/đọc lúc chạy. Demo tập trung vào tình huống cảm biến độ ẩm đất Node 2 vẫn gửi dữ liệu nhưng bị kẹt ở 2,4%, trong khi Node 1 tiếp tục dao động.

## Kết quả đã thực hiện

### Dữ liệu và MongoDB

- Các bảng telemetry (`telemetry_sensor`, `telemetry_node`, `telemetry_water`, `telemetry_flow`) đã có trong MongoDB Atlas Time Series collection `smiot.telemetry`; đối chiếu qua API lịch sử cho thấy số dòng khớp SQLite lần lượt 2.076, 32.188, 34.937 và 21.407 tại thời điểm cutover.
- Schema lưu thời điểm tại `timestamp`, metadata tại `meta`, số đo tại `readings` và thông tin nguồn tại `source`.
- Sau cutover, luồng chạy chính là MQTT `farm/sensor` → ứng dụng SMIOT → MongoDB Time Series. Đã xác nhận HTTP app trả 200, telemetry Node tăng trong MongoDB khi publisher gửi, và file SQLite không đổi trong khoảng xác minh.
- Luồng demo hiện gửi dữ liệu Node 1 và Node 2 mỗi 30 giây. Node 2 mặc định dao động; chỉ giữ `soil_hum=2.4` sau khi bật chế độ lỗi qua MQTT.

### Datadog (US1 — tài khoản hiện tại)

- Dashboard vận hành US1: [SMIOT | Farm Operations & Recovery (US)](https://app.datadoghq.com/dashboard/nkc-685-vw8).
- Các metric cảm biến được gửi với tag `farm` và `node`:
  - `smiot.telemetry.air_temperature`
  - `smiot.telemetry.air_humidity`
  - `smiot.telemetry.soil_temperature`
  - `smiot.telemetry.soil_humidity`
  - `smiot.telemetry.soil_ec`
- Monitor flatline US1: [SMIOT | greenhouse_a Node 2 soil humidity flatline (synthetic demo)](https://app.datadoghq.com/monitors/339977691). Hiện **OK** sau khi chuỗi phục hồi được xác minh.
- Safe-mode workflow US1: [SMIOT Node 2 Safe Mode - Hold and Verify](https://app.datadoghq.com/workflow/18d1b008-fb24-4713-aa0b-a1432d84ea80), handle `smiot-node-2-safe-mode-hold-and-verify`. Workflow gọi endpoint ứng dụng ở cả Alert và Recovery; app tự kiểm tra monitor, số đo MongoDB mới và dao động, HOLD ACK, rồi gửi CLEAR chỉ khi mọi điều kiện qua. Đã kiểm chứng đầu-cuối ngày 2026-11-03; virtual PLC xác nhận mọi ngõ ra bơm OFF.
- Cấu hình Datadog hiện dùng US1 (`DD_SITE=datadoghq.com`). Script kiểm thử cũ `scripts\test_workflow_auto_trigger.py` đã bị vô hiệu hóa vì từng gửi metric rời vào monitor AP1 cũ; không dùng nó để xác minh luồng thật. Demo sự cố hiện phải đi qua publisher MQTT → MongoDB → monitor US1 → workflow → bộ xác minh phục hồi của ứng dụng.
- Đã gửi 6 mẫu phục hồi tổng hợp cho Node 2 qua MQTT và lưu trong MongoDB, độ ẩm đất lần lượt **40,8; 41,6; 42,3; 41,9; 43,1; 42,6%**. Chuỗi metric recovery có tag `source:synthetic_safe_mode_recovery`; sau khi Datadog nhận chuỗi này, monitor chuyển từ **Alert** sang **OK**. Đây là xác nhận pipeline/monitor trên dữ liệu mô phỏng, không phải bằng chứng đầu dò vật lý đã được sửa.
- Chạy lại chuỗi recovery bằng `py -3.12 -X utf8 scripts\demo_node2_safe_mode_recovery.py`. Script chỉ gửi dữ liệu cảm biến; không publish lệnh điều khiển phần cứng.
- Đã cấu hình APM tracing cho các đoạn xử lý MQTT, telemetry, Gemini, PLC mô phỏng và flow meter mô phỏng. Đã khởi động lại app chính với bản sửa giữ nguyên thought signature Gemini; Datadog APM xác nhận trace irrigation demo có 16 span trong cùng trace `6adee36e000000004bcd3bc4ec85d057`, gồm Gemini, tool call, MQTT, PLC và flow meter. App chính đang chạy ở `http://localhost:8080`; log cutover ở `logs/mongo-primary-app.out.log`.
- Gemini có thể trả 503 do tải dịch vụ. Demo xử lý an toàn bằng `HOLD`, không bật bơm khi chưa có quyết định hợp lệ.
- Bits Investigation đưa ra kết luận demo: đầu dò độ ẩm đất Node 2 có số đo đóng băng ở 2,4%; đây là kịch bản synthetic đã dựng, không phải chẩn đoán một cảm biến vật lý thật.

### GDD và Forecast

- `scripts/gdd_forecast.py` tính `GDD_ngày = max(0, nhiệt độ không khí trung bình ngày − 10°C)` rồi cộng dồn bằng MongoDB aggregation `$setWindowFields`.
- Đối chiếu hồi cứu trên dữ liệu lịch sử đến 2026-07-19 cho kết quả GDD tích lũy Node 1 = **1055,73**, Node 2 = **1089,23** theo giả định ngày bắt đầu 2026-05-31. Ngưỡng minh họa 900 GDD được chạm hồi cứu lần lượt ngày 2026-07-13 và 2026-07-10. Đây không phải ngày trồng hoặc ngày thu hoạch đã xác minh.
- Metric live `smiot.crop.gdd_cumulative` có tag `cohort:live_demo`; ngày bắt đầu demo 2026-10-26 chỉ là giả định.
- Metric forecast tăng tốc `smiot.demo.crop.gdd_cumulative` từng được gửi trên tài khoản AP1 cũ; monitor AP1 không thuộc tài khoản US1 và không được dùng làm bằng chứng hiện tại. Hiện chưa xác minh monitor forecast tương đương trong US1.
- `scripts/mock_gdd_forecast_demo.py` tiếp tục gửi metric giả mỗi phút để giữ monitor demo có dữ liệu. Không dùng kết quả này làm dự báo vụ mùa thật.

### Câu chuyện kế hoạch thu hoạch

- Màn `/mongodb-lab` dùng lô dưa lưới diễn tập `melon-lot-harvest-demo-2026-01` tại `greenhouse_a`, với mốc đậu quả được khai báo là 2026-10-01. Script `scripts/seed_harvest_story.py` tạo/upsert hồ sơ mùa vụ cùng các mốc truy xuất gieo trồng → cây con → sinh trưởng → đậu quả; tất cả đều gắn `synthetic: true`.
- Cửa sổ ngày 33–45 sau đậu quả (2026-11-03 đến 2026-11-15 theo mốc demo), mốc kiểm tra chất lượng ngày 39 (2026-11-09) giúp lên lịch nhân lực và đóng gói. Đây là tham khảo từ [nghiên cứu dưa lưới Khang Nguyên](https://dthujs.vn/index.php/dthujs/article/download/971/886/1945), không khẳng định giống hay ngày hái của lô demo. Cần kiểm tra vỏ, vân cuống và chất lượng quả.
- Telemetry nhiệt độ vẫn đến từ MongoDB Time Series đang dùng. Pipeline chỉ lấy lịch sử diễn tập v2 theo nhịp một mẫu/giờ để tính độ phủ 24 mẫu/ngày, gap tối đa 3 giờ, nhiệt độ trượt 7 ngày và GDD trên các ngày đủ dữ liệu; không trộn bản tin live dày hơn vào cùng phép tính. Độ tươi bản tin live được truy vấn riêng. Thiếu ngày hiện thành khoảng trống; không nội suy, và tổng GDD đang hiển thị là phần tích lũy có dữ liệu, không phải tổng trọn vụ. GDD base 10°C chỉ là chỉ báo ngữ cảnh vì chưa hiệu chuẩn ngưỡng thu hoạch cho giống. Các nghiên cứu cho thấy tích nhiệt quan trọng nhưng điều kiện và giống làm thay đổi công thức tối ưu: [USDA ARS](https://www.ars.usda.gov/ARSUserFiles/80420520/FullTextPublicationspdf/Publications/reddy/muskmelontemp.pdf).

### Dữ liệu nghiệp vụ trong MongoDB

- Đã chuyển và đối chiếu users (9, quyền 14, quan hệ quyền 57 và farm 12), inverter modes (4), schedules (668), schedule logs (663) và notifications (966).
- Users lưu quyền và farm dưới dạng mảng trong document; lịch, log, thông báo và mode dùng collection document thông thường để hỗ trợ cập nhật trạng thái.
- Các màn hình, trợ lý AI và scheduler hiện truy cập qua MongoDB; không còn truy vấn SQLite trực tiếp trong `main.py`, `pages/` hoặc `service/`.
- SQLite được giữ làm bản backup tại `D:\IOT Trung\code_full_server_backup_pre_mongodb_20261026\farm_data.db`; không xóa file nguồn. Bản sao mã trước cutover cũng ở thư mục backup đó.

### Phân tích dữ liệu vận hành

- Đã phân loại từng dòng trong **272** log `schedule_logs` có trạng thái `failed`. Chi tiết theo từng `log_id`: [CSV phân loại](reports/schedule_logs_failed_classification.csv); giải thích phương pháp và giới hạn bằng chứng: [báo cáo phân tích](reports/schedule_logs_failed_analysis.md).
- Kết quả: 65 dòng có notification lịch bị bỏ lỡ/offline; 185 dòng nhiều khả năng do nhánh tự đánh failed im lặng khi quá hạn trên 2 giờ và khớp lịch; 5 ứng viên chưa xác nhận; 7 bất thường timestamp; 6 thiếu `end_at`; 4 không đối chiếu được. Notification offline không chứng minh bơm vật lý hỏng. Không trình bày 272 dòng như 272 sự cố độc lập và không đưa tỷ lệ “41% failure rate” lên slide.
- Các thống kê 118 lần mất kết nối đồng thời và khoảng 30 lần bơm không phản hồi là nhóm sự kiện notification khác; cần nêu đúng định nghĩa, không cộng hay đồng nhất chúng với 272 log `failed`.

## Kiến trúc demo

```text
Wokwi ESP32 ──► public MQTT demo broker ──► local Wokwi bridge ──► MQTT: farm/sensor
      ▲                     │                                       │
      │                     └──── virtual HOLD/CLEAR commands ◄────┤
      │                                                             ▼
      └── red/green virtual LEDs ◄── workflow execution poller   SMIOT app
                                                                   ├──► MongoDB Atlas
                                                                   └──► DogStatsD / Datadog Agent

Wokwi stage events ──► local bridge ──► MQTT: farm/traceability/event
                                               └─► SMIOT MQTT handler ──► MongoDB metadata
                                                                            └─► /traceability UI reads image from app image store

MongoDB telemetry ──► GDD aggregation ──► smiot.crop.gdd_cumulative

Synthetic accelerated GDD ──► smiot.demo.crop.gdd_cumulative
                              └──► Synthetic Forecast Monitor
```

Wokwi starter files are in `wokwi/smiot_demo/`. The local bridge forwards synthetic sensor messages into `farm/sensor` and relays growth-stage metadata into `farm/traceability/event`. The generated JPEG stays in the app image store at `static/device_images/smiot_melon_growth_contact_sheet.jpg`; MongoDB's `traceability_events` collection stores its relative URL/path together with each lot/day/stage record. The authenticated `/traceability` page loads the image from the app and the event metadata from MongoDB. The image is a synthetic five-panel contact sheet, not a real camera capture. MQTT carries metadata only and must not carry secrets or private farm data. For production-scale real photos, move the image store to object storage (for example S3 or Cloudinary) and save the resulting URL/key in MongoDB.

To demo traceability without Wokwi, start the local MQTT broker and SMIOT app, then run `py -3.12 -X utf8 scripts\demo_traceability.py`. By default this publishes 15 simulated daily records for each of 10 lots (150 events) through the app's MQTT topic, waits for MongoDB persistence, and reports the demo lot IDs. Open the authenticated `/traceability` page and choose any lot. Use `--lots 5 --days 7` to create a smaller set. The same lot/day event IDs are updated on repeated runs, so rerunning does not create duplicate stage records.

## Yêu cầu chạy local

- Windows và Python 3.12.
- MQTT broker chạy local tại `localhost:1883` (ví dụ Mosquitto).
- Datadog Agent đang chạy; DogStatsD dùng `127.0.0.1:8125`, APM trace agent dùng `127.0.0.1:8126`.
- MongoDB Atlas Network Access cho phép IP máy đang chạy ứng dụng. App cần `MONGODB_URI`; MongoDB là nơi đọc/ghi chính.
- Các gói Python trong `requirements.txt`.

## Cấu hình bí mật

Đặt cấu hình trong `.env` ở thư mục dự án. Không đưa giá trị bí mật vào README, ảnh chụp, commit hoặc tin nhắn.

```dotenv
MONGODB_URI=<MongoDB Atlas connection string>
MONGODB_DATABASE=smiot
MONGODB_TELEMETRY_COLLECTION=telemetry

DATADOG_METRICS_ENABLED=true
DATADOG_APM_ENABLED=true
DD_API_KEY=<Datadog API key>
DD_APP_KEY=<Datadog Application key>
DD_SITE=datadoghq.com
```

Giữ `.env` riêng trên máy và không chia sẻ nội dung file. `DD_APP_KEY` chỉ cần cho thao tác Datadog API; gửi metric trực tiếp dùng `DD_API_KEY`.

## Chạy ứng dụng và luồng dữ liệu

Mở các cửa sổ PowerShell riêng, tại mỗi cửa sổ chạy:

```powershell
cd 'D:\IOT Trung\code_full_server'
```

### 1. Cài dependencies (nếu máy chưa cài)

```powershell
py -3.12 -m pip install -r requirements.txt
```

### 2. Khởi động ứng dụng SMIOT

Đảm bảo MongoDB Atlas Network Access cho phép IP hiện tại, Mosquitto và Datadog Agent đang chạy trước, sau đó:

```powershell
py -3.12 -X utf8 main.py
```

Mở [http://localhost:8080](http://localhost:8080). Ứng dụng đăng ký MQTT topic `farm/sensor` khi khởi động.

#### Chế độ demo tự nạp dữ liệu

`SMIOT_DEMO_MODE=true` được bật mặc định trong `.env`. Mỗi lần khởi động app sẽ bù các bản ghi lịch sử còn thiếu (không nhân đôi dữ liệu đã seed), rồi tự chạy MQTT publisher tổng hợp mỗi 30 giây. Bộ demo gồm 30 ngày telemetry theo giờ cho 4 nhà kính, lịch tưới đã hoàn tất, thông báo mẫu, và 10 lô truy xuất với 15 ngày/giai đoạn giả lập. Các gói live cập nhật node, lưu lượng, EC, pH, PLC và biến tần; mọi đầu ra PLC/bơm luôn ở trạng thái tắt. Node 2 của Greenhouse A chạy bình thường khi mới khởi động; chỉ giữ soil humidity ở 2,4% khi bật lỗi flatline. Lịch sử seed v2 giữ Node 2 bình thường ngoại trừ cửa sổ sự cố minh họa cố định 2026-11-01 00:00–06:00 UTC. Lịch sử seed v1 sai (Node 2 đứng 2,4% cả 30 ngày) được giữ nguyên trong MongoDB để kiểm toán nhưng bị loại khỏi màn hình và báo cáo; không xóa document khỏi Time Series collection.

Đổi trạng thái cảm biến Node 2 khi demo (chạy ở máy/EC2 có thể kết nối tới MQTT broker của ứng dụng):

```powershell
py -3.12 -X utf8 scripts\set_demo_sensor_fault.py normal
py -3.12 -X utf8 scripts\set_demo_sensor_fault.py flatline
```

Lệnh được gửi riêng qua `farm/demo/control`, không đi chung topic điều khiển PLC. Script đợi publisher xác nhận chế độ trên `farm/demo/status`, rồi đợi mẫu `farm/sensor` đầu tiên và in giá trị cùng thời điểm. `flatline` giữ Node 2 Greenhouse A ở 2,4% trên các gói live tiếp theo; `normal` cho số đo dao động lại quanh 40%. Sau khi tắt lỗi, monitor cần đủ dữ liệu bình thường trong cửa sổ đánh giá của nó mới chuyển về OK. Các lệnh chỉ đổi cảm biến tổng hợp, không điều khiển bơm/PLC vật lý.

Trong phần kể chuyện, mô tả kết luận là “luồng số đo Node 2 bị đứng” và `HOLD` là hành động an toàn trên mô phỏng. Bits cung cấp giả thuyết dựa trên telemetry/log/trace sẵn có; không dùng kết quả đó để khẳng định đầu dò ngoài đời đã hỏng hay đã được sửa. Chỉ tuyên bố phục hồi của luồng demo sau khi mẫu mới đã tới MongoDB và monitor đã hồi phục.

Mở `http://localhost:8080`, đăng nhập rồi xem Home, Data, Chart, Schedule, PLC và Traceability. Nhãn `DEMO · dữ liệu mô phỏng` đánh dấu rõ dữ liệu tổng hợp. Để tắt publisher/seed, đặt `SMIOT_DEMO_MODE=false`; có thể chỉnh chu kỳ bằng `SMIOT_DEMO_INTERVAL_SECONDS` (tối thiểu 10 giây). Dữ liệu demo được ghi vào MongoDB và tiếp tục tồn tại sau khi tắt app.

### 3. Gửi cảm biến giả qua ứng dụng

```powershell
py -3.12 -X utf8 scripts\mock_telemetry_to_datadog.py --publish-mqtt
```

Script chỉ phát bản tin cảm biến; không phát lệnh PLC. Dừng bằng `Ctrl+C` trong cửa sổ chạy script.

### 4. Tính GDD live và gửi metric định kỳ

```powershell
py -3.12 -X utf8 scripts\gdd_forecast.py --publish-datadog --watch --interval 300 --planted-at 2026-10-26 --cohort live_demo
```

Ngày `2026-10-26` trong lệnh trên là mốc demo đã dùng. Nếu biết ngày trồng thật, thay bằng ngày đó; nếu không, không diễn giải kết quả là dự báo mùa vụ thực tế.

### 5. Giữ Forecast Monitor giả lập có dữ liệu

```powershell
py -3.12 -X utf8 scripts\mock_gdd_forecast_demo.py
```

Lệnh này phát riêng metric có tag `source:synthetic`, mỗi 60 giây. Chỉ chạy khi cần trình diễn Forecast giả lập; dừng bằng `Ctrl+C`.

### 6. Chạy demo APM tưới mô phỏng (tùy chọn)

```powershell
py -3.12 -X utf8 scripts\demo_apm_irrigation_trace.py
```

Demo dùng topic `smiot/demo/...`, PLC và flow meter ở chế độ mô phỏng; không điều khiển thiết bị thật.

### 7. Kết nối Wokwi và xem phản hồi safe mode (tùy chọn)

Project Wokwi CLI, firmware ESP32 và cấu hình đã được chuẩn bị trong `wokwi/smiot_demo/`. ESP32 tự phát một sự kiện ảnh mỗi 15 giây (tương đương một ngày mô phỏng); metadata giai đoạn đi lên MQTT công khai. Bridge chuyển metadata vào MQTT nội bộ. Ảnh giả lập (contact sheet năm giai đoạn) được phục vụ từ `static/device_images/`; MongoDB `traceability_events` chỉ lưu đường dẫn ảnh cùng thông tin ngày/lô/giai đoạn. Ứng dụng hiển thị tại `http://localhost:8080/traceability`. Wokwi không chụp ảnh thật; firmware đánh dấu `image_captured: false`. Nếu Wokwi chưa kết nối được, chạy `py -3.12 -X utf8 scripts\demo_traceability.py` để gửi đủ năm giai đoạn qua MQTT nội bộ. Tạo token ở [Wokwi CI dashboard](https://wokwi.com/dashboard/ci), sau đó chạy trong PowerShell. Token được nhập ẩn và không lưu vào project:

```powershell
.\wokwi\smiot_demo\run-wokwi.ps1
```

Nếu chạy lệnh từ thư mục khác, dùng đường dẫn đầy đủ `D:\IOT Trung\code_full_server\wokwi\smiot_demo\run-wokwi.ps1`. Nhấn `Ctrl+C` để dừng mô phỏng.

Để gửi telemetry vào app, cần chạy thêm ứng dụng SMIOT, Mosquitto local và bridge như bên dưới. Công tắc bên trái giữ Node 2 ở 2,4%; gạt sang phải để giả lập phục hồi. Giữ channel mặc định `greenhouse-a-7f38c2d1` giống nhau ở firmware và bridge. Chạy:

```powershell
py -3.12 -X utf8 scripts\wokwi_datadog_bridge.py
```

Ứng dụng SMIOT và Mosquitto local phải đang chạy. Công tắc gạt trái giữ Node 2 tại 2,4%; sau khi monitor đánh Alert và workflow thành công, LED đỏ bật và LED xanh tắt. Gạt sang phải để dữ liệu thay đổi; khi monitor hồi phục OK, LED xanh bật lại. Đây chỉ là đèn trạng thái/đầu ra ảo, không điều khiển thiết bị thật. Broker công khai không có xác thực và không bảo đảm riêng tư.

## Lịch sử chuyển SQLite → MongoDB

Đã cutover app sang MongoDB làm nơi đọc/ghi chính. Telemetry đang ở Time Series `telemetry`; dữ liệu nghiệp vụ ở collections `users`, `permissions`, `inverter_mode`, `schedules`, `schedule_logs`, `notifications`. Script `scripts/migrate_sqlite_operational_to_mongodb.py` dùng upsert theo ID và đã xác minh số lượng trước khi bật app. Không chạy lại script nếu SQLite backup không phải cùng snapshot hoặc chưa rà soát các bản ghi mới phát sinh.

`farm_data.db` là backup để đối chiếu/rollback thủ công; app hiện không dùng SQLite làm fallback tự động. Giữ riêng backup, không xóa trong thời gian theo dõi cutover.

## Nhật ký và kiểm tra nhanh

Các log của tiến trình demo đã khởi chạy trong môi trường hiện tại:

- `logs/mongo-primary-app.out.log` — startup ứng dụng sau cutover; `logs/mongo-primary-app.err.log` — trace log và diagnostic. Datadog APM có spans gần đây cho service `smiot-smart-farm`.
- `logs/mongo-live-publisher.out.log` — cảm biến giả qua MQTT.
- `logs/gdd-live-watch.out.log` — phép tính GDD live.
- `logs/gdd-synthetic-forecast.out.log` — metric GDD giả tăng tốc.

Trong Datadog Metrics Explorer:

- Live GDD: `smiot.crop.gdd_cumulative`, filter `cohort:live_demo`, group by `node`.
- GDD giả: `smiot.demo.crop.gdd_cumulative`, filter `cohort:synthetic_accelerated_demo`, group by `node`.

## Việc còn lại trước khi nộp demo

- Quay video theo luồng: dashboard → phát hiện flatline → Bits Investigation → Forecast.
- Viết `SUBMISSION.md`, hoàn thiện slide và phần giải thích tác động.
- Giữ tách biệt dữ liệu lịch sử, live synthetic sensor và accelerated synthetic GDD trong hình ảnh/trình bày.
- Ngày trồng `2026-05-31` (hồi cứu) và `2026-10-26` (live demo), cùng ngưỡng 900°C·ngày, hiện là **giả định minh họa chưa được xác minh bằng hồ sơ lô hoặc nguồn nông học**. Chỉ gọi là demo/ước tính; không trình bày ngày thu hoạch như dự báo thực tế.
- Đã hoàn tất phân loại 272 dòng `schedule_logs`; giữ báo cáo CSV/Markdown đính kèm khi trình bày để giải thích cách phân loại và mức độ tin cậy.

## Ghi chú triển khai

App hiện ghi telemetry trực tiếp vào MongoDB. Nếu Atlas mất kết nối, lệnh ghi Mongo sẽ lỗi và được log; không có fallback tự động sang SQLite. Bản backup SQLite và bản sao code trước cutover được giữ riêng để rollback thủ công. Log khởi động vẫn có cảnh báo ddtrace không tự instrument được một phần PyMongo do lệch tương thích; thao tác Mongo lưu thành công nhưng có thể không có span Mongo riêng trong APM.
