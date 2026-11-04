# Chiều sâu MongoDB cho SMIOT

## MongoDB hiện được dùng sâu đến đâu và chuyên gia khai thác như thế nào?

### Takeaway
Kế hoạch hiện đủ nền tảng kỹ thuật nhưng câu chuyện MongoDB mới mạnh ở lưu telemetry và tính một chỉ số GDD. Mức sâu hơn phải là dữ liệu được đánh giá độ tin cậy, liên kết tới lô đang chịu ảnh hưởng, và tạo được hồ sơ trước/sau sự cố; hiệu năng và tiết kiệm phải có đo đối chứng, chưa có số đo thì chỉ là giả thuyết.

### Cited Findings
- `service/auth.py:49-55` có indexes; `:236-246` ghi telemetry với timestamp/meta/readings/source; `:247` đọc lịch sử theo farm và khoảng ngày. `scripts/gdd_forecast.py:50-100` có group nhiệt độ theo ngày rồi `$setWindowFields` cộng dồn. `service/traceability.py:77-91` hiện chỉ group số sự kiện và giai đoạn theo lot. Nguồn mã: [auth.py](<D:/IOT Trung/code_full_server/service/auth.py:236>), [GDD](<D:/IOT Trung/code_full_server/scripts/gdd_forecast.py:50>), [traceability](<D:/IOT Trung/code_full_server/service/traceability.py:77>).
- MongoDB khuyên chọn metadata ổn định, dùng metadata/time indexes theo truy vấn và batch insert khi có nhiều tài liệu; những lựa chọn này ảnh hưởng trực tiếp hiệu quả lưu và truy vấn. [Time Series best practices](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-best-practices/).
- Time Series grouping theo metadata và thời gian; metadata thay đổi thường xuyên tạo nhiều bucket thưa, giảm hiệu quả. Vì vậy không đưa `incident_id`, trace ID, seq hay thời gian thay đổi vào `meta`; chỉ farm/device/measurement ổn định ở đó. [Bucketing](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-bucketing/).
- `$setWindowFields` hỗ trợ tính trên cửa sổ tài liệu hoặc thời gian, phân vùng dữ liệu và phân tích chuỗi ngay trong database. [Window stage](https://www.mongodb.com/docs/manual/reference/operator/aggregation/setwindowfields/).
- MongoDB có computed pattern để lưu kết quả tính trước; materialized result dùng `$merge`/`$out` vào collection, có đánh đổi độ mới dữ liệu. [Computed values](https://www.mongodb.com/docs/manual/data-modeling/design-patterns/computed-values/computed-schema-pattern/), [Materialized views](https://www.mongodb.com/docs/manual/core/materialized-views/).
- Ví dụ thực tế Digitread Connect xử lý dữ liệu thiết bị tại edge, chỉ chuyển phần cần dùng lên nền tảng ứng dụng dùng Atlas Time Series. Giá trị là biến telemetry thành thông tin cho người sử dụng, không chỉ sao chép mọi số đo lên cloud. Đây là case study do nhà cung cấp công bố, không phải benchmark độc lập hay số tiết kiệm của SMIOT. [Digitread Connect](https://www.mongodb.com/solutions/customer-case-studies/digitread-connect).
- Kiến trúc predictive maintenance chính thức ghép telemetry, ngữ cảnh thiết bị, lịch sử, tài liệu và hành động; đây là reference architecture, chưa phải bằng chứng SMIOT có mô hình dự đoán đạt độ chính xác nào. [Architecture Center](https://www.mongodb.com/docs/atlas/architecture/current/solutions-library/predictive-maintenance/).

### Inferences
Các điểm sau là đề xuất và điểm chấm chủ quan, chưa là chức năng đã triển khai. Chấm 5 nhóm, mỗi nhóm 0-2: chiều sâu kỹ thuật; hợp vận hành; lợi ích đo được; khả năng chứng minh; khả thi trên hệ thống. Điểm sau chỉ đạt khi xây dựng và có bằng chứng.

| Chức năng | Kịch bản trong memory và điểm yếu | Kịch bản nâng cấp, lợi ích cụ thể và phép chứng minh | Điểm kế hoạch cũ → tiềm năng sau nâng cấp |
|---|---|---|---|
| Time Series + indexes + document model | Có telemetry trong TS, index và metadata; mới chứng minh đã lưu. Chưa đo storage/query hoặc mô hình thêm thiết bị. | Theo dõi cùng nhà kính nhưng nhiều loại thiết bị có readings khác nhau, schema_version rõ, metadata ổn định. Đo cùng tập dữ liệu và truy vấn 7/30 ngày ở TS và collection thường với index tương đương; báo dung lượng physical nếu quyền hỗ trợ, index size, latency p50/p95 và số dữ liệu trả về. Có thể đo thêm SQLite local nhưng phải công khai network/máy/index khác nhau, không dùng kết quả đó suy ra Mongo luôn nhanh hơn SQL. Chỉ batch write nếu độ trễ và tần suất thực tế cần. | 6/10 → 8/10 |
| Window analysis + chất lượng dữ liệu | Cộng dồn GDD là ví dụ đúng nhưng đơn giản; thiếu ngày trồng xác minh và dữ liệu missing có thể làm người xem hiểu sai. | Trên mỗi node, tính số mẫu hợp lệ, khoảng hở, stddev/min-max cửa sổ thời gian và chất lượng coverage trước khi tính GDD. Cảnh báo số đo đứng nhưng seq vẫn tăng. Không tự bù dữ liệu trống; hiển thị GDD chưa đủ dữ liệu hoặc GDD kèm coverage, phương pháp và thời gian nguồn. Đối chiếu một đoạn có/không flatline với phép tính độc lập và xác nhận kết quả aggregate khớp. SQL cũng có windows, nên lợi ích ở xử lý gần dữ liệu và giảm việc kéo toàn bộ raw về app, đo bytes transferred/app memory/request time. | 5/10 → 9/10 |
| Hồ sơ truy xuất có bằng chứng vận hành | Hiện lot chỉ có timeline sự kiện/giai đoạn; chưa chứng minh lot nào chịu ảnh hưởng của Node 2 và phục hồi thế nào. | Lot có farm, zone/node, planted_at/harvested_at xác minh hoặc gắn giả định; incident có phạm vi node và start/end. Khi mở lot, truy vấn theo node + khoảng thời gian chồng lấn, hiển thị phút mất coverage, sự cố, thời điểm HOLD, action execution và bằng chứng recovery. Không gắn nhãn chất lượng thực phẩm/đạt chuẩn chỉ vì monitor về OK. Đối chứng lot ở node khác hoặc ngoài khoảng sự cố phải không bị đánh dấu; lot đúng phạm vi có bằng chứng cùng incident_id. Lưu snapshot có version tại thời điểm chốt hồ sơ, không nhúng vô hạn telemetry vào một document. | 5/10 → 9/10 |
| Provenance + action ledger trên collection thường | Memory đã yêu cầu source/incident_id/seq nhưng chưa có bản thiết kế bảo đảm chống lặp và liên kết hành động. | Chuỗi source/device/boot_id/seq, observed_at, ingested_at giúp phân biệt lost/late/duplicate. Collection thường `incident_actions` có khóa duy nhất (incident_id, action_type, attempt), trạng thái requested/running/verified/failed; duplicate webhook phải chỉ có một lần tác động. Ghi raw nguồn riêng và lưu correction có version, không sửa lịch sử âm thầm. Mongo không tự làm audit bất biến; quyền database và chính sách app phải được kiểm chứng. Đối chứng gửi webhook hai lần và worker crash trước/sau tác động; không tuyên bố exactly-once chỉ nhờ unique key. | 5/10 → 9/10 |
| Materialized daily summaries + retention có chính sách | Memory chưa có computed summary, chủ trương giữ lịch sử nên không đặt TTL. | Tính tổng hợp theo farm/node/ngày hoặc giờ có quality coverage, GDD, lượng tưới có nguồn đo. `$merge` vào collection thường `daily_farm_summary`, chỉ cập nhật ngày dirty khi có backfill; lưu watermark/version. Đo app trả biểu đồ 30 ngày dùng raw so với summary, bytes và latency; dùng query đối chiếu cùng aggregate để kiểm tra đúng. TTL chỉ đề xuất cho dữ liệu chẩn đoán tạm thời tách riêng; không xóa telemetry/truy xuất hiện có. Nếu về sau TTL raw thì phải archive và verify trước, không để job tổng hợp và TTL chạy đua. | 3/10 → 8/10 |
| Change Streams cho incident/action state, optional | Chưa có; thêm chỉ để liệt kê công nghệ sẽ nông. | Chỉ watch collection thường `incidents` hoặc `incident_actions`: khi chuyển verified, UI và hồ sơ lot cập nhật không polling; worker lưu resume token, restart tiếp tục và dedup theo event ID. Đo DB requests giữa polling và watch cùng tốc độ event, end-to-end update latency, thử worker restart. Không watch TS, không để watch tự trực tiếp bật bơm. Chỉ làm nếu đủ thời gian và tier cho phép. | 2/10 → 8/10 |

### Gaps
- Chưa có benchmark SMIOT về dung lượng physical, p95, bytes transferred hoặc SQL baseline cấu hình tương đương; không được ghi tỷ lệ tiết kiệm giả.
- Phát hiện quan trọng từ audit: `main.py:36-37` gọi `start_demo_mode()`; `service/demo_mode.py:31` mặc định SMIOT_DEMO_MODE=true; `:34-87` sinh 30 ngày telemetry bằng công thức sin và gắn synthetic, kèm publisher live. Trong khi đó GDD pipeline hiện không lọc source/cohort, nên có nguy cơ tính lẫn dữ liệu lịch sử nguồn với seed. Phải chọn cohort cho mọi pipeline/proof, tách historical_verified/historical_unverified/wokwi/synthetic_seed, không gọi toàn bộ history hiện tại là dữ liệu thật. [Main](<D:/IOT Trung/code_full_server/main.py:36>), [Demo source](<D:/IOT Trung/code_full_server/service/demo_mode.py:31>), [GDD filter](<D:/IOT Trung/code_full_server/scripts/gdd_forecast.py:54>).
- Dữ liệu lịch sử app có thể dùng để phân tích, nhưng provenance vật lý và ngày trồng thật chưa được xác minh. Ngày/gdd model phải còn nhãn assumption.
- Cần đo nhịp gửi theo device và khoảng mất gói trước khi chọn cửa sổ/threshold; không lấy 30 mẫu cố định rồi gọi 5 phút khi nhịp gửi thay đổi.

## Các giới hạn nào làm kịch bản trông sâu nhưng thực ra không chạy được?

### Takeaway
Giữ telemetry đo đạc trong Time Series, nghiệp vụ và bằng chứng chuyển trạng thái trong collection thường. Không giả định các tính năng transaction, uniqueness, validation hay Change Streams chạy trực tiếp trên Time Series.

### Cited Findings
- Time Series không hỗ trợ Change Streams, Database Triggers, schema validation rules, unique indexes; không hỗ trợ ghi vào TS bên trong transaction. `$merge` có thể đọc TS và ghi sang collection khác, không dùng `$merge` để ghi đích là TS. [Time Series limitations](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-limitations/).
- Đổi sang collection thường để lưu incident/state cho phép đặt unique key và watch; Change Streams yêu cầu replica set/sharded deployment, resume token cần còn trong oplog, resume với pipeline/options nhất quán. [Change Streams](https://www.mongodb.com/docs/manual/changestreams/).
- M0/Free hiện có giới hạn 50 stage aggregation, không spill ra disk dù đặt allowDiskUse=true, 32 MB sort memory, 0.5 GB tính theo BSON chưa nén + indexes; không có Performance Advisor. Vì vậy compression physical không tự biến thành tăng quota Free. [Free cluster limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/).
- TTL TS không xóa ngay chính xác tại hạn; phải đợi toàn bucket hết hạn và lượt nền, có thể trễ thêm theo workload. [Time Series TTL](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-automatic-removal/).
- `$lookup` có thể chậm khi unindexed hoặc correlated trên dữ liệu lớn, nên thiết kế theo query và index; embedding/references đều có chỗ dùng. [Lookup](https://www.mongodb.com/docs/manual/reference/operator/aggregation/lookup/), [Data modeling](https://www.mongodb.com/docs/manual/data-modeling/best-practices/).

### Inferences
- Một collection thường idempotency/action ledger có thể khóa lặp workflow, nhưng raw TS write và ledger không atomically commit trong cùng transaction. Phải có trạng thái, cơ chế reconcile và kiểm chứng crash; tránh hứa exactly-once end-to-end.
- Nếu dùng `$lookup` cho hộ chiếu lot nên có cutoff, phạm vi hẹp hoặc query summary theo node/time rồi ghép có nguồn rõ. Không kéo toàn bộ telemetry vào mảng trong lot.
- Không cần Vector Search/geospatial/sharding để lấy điểm. Chỉ thêm khi có corpus manual vận hành, nhu cầu tìm ngữ nghĩa có đánh giá hoặc nhiều vị trí có câu hỏi thực tế; hiện chưa có bằng chứng phù hợp hơn core pipeline.

### Gaps
- Tier/version thực tế của cluster cần xác minh trước triển khai; tài liệu latest có thể mới hơn MongoDB version cụ thể của cluster. Free docs đang nêu server 8.0.
- Thông số thay đổi theo tier, không nên dùng mọi tính năng mới của manual current làm bảo đảm cho M0 hiện tại.

## Câu chuyện nào chứng minh giá trị hơn cách cũ?

### Takeaway
Đừng cố chứng minh MongoDB có một phép tính SQL không làm được. Chứng minh SMIOT dùng một mô hình dữ liệu phù hợp và một luồng phân tích có nguồn gốc để trả lời quyết định mà app cũ chưa trả lời được: lô nào đang thiếu bằng chứng vận hành, hành động nào đã bảo vệ nó, và dữ liệu nào xác nhận sự cố khép lại.

### Cited Findings
- Professional IoT case Digitread Connect tổ chức edge processing và dữ liệu cần thiết cho ứng dụng, thay vì chỉ thêm dashboard trên raw data. [Customer case](https://www.mongodb.com/solutions/customer-case-studies/digitread-connect).
- Các công cụ database đã hỗ trợ computed values, time windows và các lựa chọn embed/reference phục vụ workload; hiệu quả phụ thuộc thiết kế. [Computed pattern](https://www.mongodb.com/docs/manual/data-modeling/design-patterns/computed-values/computed-schema-pattern/), [Windows](https://www.mongodb.com/docs/manual/reference/operator/aggregation/setwindowfields/), [Modeling](https://www.mongodb.com/docs/manual/data-modeling/best-practices/).

### Inferences
- Demo đề xuất: app trước cho thấy Node 2 online và số 2.4; phiên bản mới nhận ra “online nhưng dữ liệu không đáng tin”, liên kết đúng lot và khoảng thời gian, HOLD có audit, chỉ đóng incident khi có chuỗi bằng chứng recovery; QR lot hiển thị cả khoảng thiếu chứng cứ thay vì dấu verified chung chung.
- Ba lợi ích có thể đo: (1) request UI history dùng summary truyền ít dữ liệu hơn raw path; (2) số lô bị đánh dấu ảnh hưởng đúng/không đúng theo control cases; (3) khoảng thời gian data quality không đáng tin được tính thống nhất ở Mongo và Datadog, không làm sai GDD/tổng hợp.
- Điểm “wow” của Mongo là hộ chiếu lô có chất lượng dữ liệu và action proof liên kết, không phải chỉ GDD hoặc timeline ảnh. Điểm “đủ yêu cầu” và “tận dụng sâu” phải tách biệt.

### Gaps
- Chưa chứng minh bảo vệ năng suất, tiết kiệm nước hay tiền thực tế vì không có thí nghiệm đối chứng với hệ thống tưới vật lý và chi phí vận hành; chỉ nên đo hiệu quả pipeline, dữ liệu và thao tác vận hành trước.
