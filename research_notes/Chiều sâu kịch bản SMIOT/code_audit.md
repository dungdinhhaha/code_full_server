# Kiểm toán khả năng chứng minh SMIOT

## 1. Kịch bản hiện tại có thể bị chứng minh sai ở đâu?

### Takeaway
Ưu tiên P0 là cô lập nguồn phát, lưu nguồn gốc và thời gian đo, phân biệt ACK broker với ACK thiết bị. Hiện code có thể khiến bridge bị dừng nhưng app vẫn thấy dữ liệu mới, hoặc monitor hồi phục mà thiết bị chưa được xác minh.

### Cited Findings
- App gọi `start_demo_mode()` khi import; demo mặc định bật nếu chưa đặt env. Nó seed 30 ngày số đo theo hàm sin và khởi chạy publisher liên tục cho bốn farm. Đây là xung đột với memory yêu cầu lịch sử không tự tạo/nội suy. Synthetic được gắn nhãn ở seed nhưng không bị tách khỏi mọi truy vấn phân tích. — [main.py:36](<D:/IOT Trung/code_full_server/main.py:36>), [demo_mode.py:30](<D:/IOT Trung/code_full_server/service/demo_mode.py:30>), [demo_mode.py:34](<D:/IOT Trung/code_full_server/service/demo_mode.py:34>), [demo_mode.py:289](<D:/IOT Trung/code_full_server/service/demo_mode.py:289>).
- Publisher trong app gửi greenhouse_a Node2=2.4 đều đặn và tạo flow >0 dù PLC giả lập báo mọi đầu ra tắt, inverter status=0. Do đó dữ liệu flow và pump không có quan hệ nhân quả vật lý; chạy song song Wokwi sẽ che khuất mất dữ liệu bridge hoặc kéo monitor về flatline. — [demo_mode.py:225](<D:/IOT Trung/code_full_server/service/demo_mode.py:225>), [demo_mode.py:235](<D:/IOT Trung/code_full_server/service/demo_mode.py:235>), [demo_mode.py:263](<D:/IOT Trung/code_full_server/service/demo_mode.py:263>).
- Metric sender chỉ có tags farm và node, không source/environment/scenario. Mock gửi thẳng DogStatsD và Wokwi qua app có thể trộn cùng time series. — [datadog_metrics.py:49](<D:/IOT Trung/code_full_server/service/datadog_metrics.py:49>), [mock_telemetry_to_datadog.py:78](<D:/IOT Trung/code_full_server/scripts/mock_telemetry_to_datadog.py:78>).
- Bridge đặt source=wokwi_synthetic và timestamp lúc bridge nhận, còn nhánh Mongo chỉ gắn synthetic metadata cho smiot_demo_stream. Hàm lưu time-series dùng datetime.now làm timestamp; mất thời điểm producer và bridge nếu cần đối chiếu độ trễ. — [wokwi_datadog_bridge.py:76](<D:/IOT Trung/code_full_server/scripts/wokwi_datadog_bridge.py:76>), [mqtt.py:340](<D:/IOT Trung/code_full_server/service/mqtt.py:340>), [auth.py:236](<D:/IOT Trung/code_full_server/service/auth.py:236>).
- sampleNumber Wokwi chỉ in Serial, không nằm trong payload. Hiện thiếu event_id/session_id/sequence để tính mất bản tin chính xác và chống replay. — [sketch.ino:114](<D:/IOT Trung/code_full_server/wokwi/smiot_demo/sketch.ino:114>), [sketch.ino:123](<D:/IOT Trung/code_full_server/wokwi/smiot_demo/sketch.ino:123>).
- Bridge phát CLEAR chỉ vì monitor về OK. Nó không kiểm tra người vận hành duyệt, chất lượng chuỗi phục hồi, timeout lệnh hay ACK thiết bị. publish ACK chứng minh broker nhận, không chứng minh LED/relay đã đổi. Wokwi xử lý HOLD/CLEAR rồi đổi LED nhưng không publish ACK cùng command_id. — [wokwi_datadog_bridge.py:160](<D:/IOT Trung/code_full_server/scripts/wokwi_datadog_bridge.py:160>), [wokwi_datadog_bridge.py:270](<D:/IOT Trung/code_full_server/scripts/wokwi_datadog_bridge.py:270>), [sketch.ino:55](<D:/IOT Trung/code_full_server/wokwi/smiot_demo/sketch.ino:55>).

### Inferences
- Tắt nguồn demo trong phạm vi scenario và mọi publisher thẳng DogStatsD; mỗi farm/node/scenario chỉ có một nguồn authoritative. Thêm source/env/schema_version tags có số lượng hữu hạn; để incident_id và message_id trong logs/documents, tránh tag metric cardinality cao.
- Giữ measured_at, gateway_received_at, app_received_at, persisted_at riêng; Wokwi có thể dùng session+sequence+uptime, gateway đóng dấu UTC. Không gán thời gian bridge là thời gian đo gốc.
- Cần ACK ứng dụng từ thiết bị với command_id/actual_state. Giữ HOLD qua restart, không tự CLEAR do monitor OK; operator approval hoặc policy rõ ràng cùng chuỗi dữ liệu đạt chất lượng.
- Bridge cần repair controller độc lập: không để tiến trình cần được sửa cũng là nơi duy nhất nhận lệnh sửa.

### Gaps
- Chưa chạy hệ thống, chưa xác minh env nào đang bật, phiên mock nào còn sống hay dữ liệu live Atlas hiện tại. Các phát hiện là hành vi có trong mã, không tuyên bố đã gây một sự cố production.

## 2. Độ sâu MongoDB, APM và AI đang đến đâu?

### Takeaway
Mongo là DB chính thật trong mã, nhưng ưu thế truy vấn/chi phí chưa có benchmark. Traceability hiện là timeline ảnh metadata, chưa là hồ sơ bằng chứng liên kết telemetry, sự cố và quyết định theo lô.

### Cited Findings
- Auth lưu telemetry trực tiếp Mongo với timestamp/meta/readings/source; historical query find+sort kéo toàn bộ khoảng ngày về Python, chưa downsample, limit hoặc pagination. — [auth.py:236](<D:/IOT Trung/code_full_server/service/auth.py:236>), [auth.py:247](<D:/IOT Trung/code_full_server/service/auth.py:247>).
- Index đã có farm+measurement+timestamp, nhưng traceability index farm+simulated_day không sát query farm+lot_id+sort(captured_at/simulated_day). get_all_schedule_logs còn đọc toàn bộ schedules của mọi farm rồi join trong Python. — [auth.py:49](<D:/IOT Trung/code_full_server/service/auth.py:49>), [auth.py:215](<D:/IOT Trung/code_full_server/service/auth.py:215>), [traceability.py:94](<D:/IOT Trung/code_full_server/service/traceability.py:94>).
- GDD dùng match/group/project/setWindowFields sum. Daily bucket UTC, không có source filter, không loại dữ liệu simulated, không phân loại coverage/missing-day trước tích lũy. GDD theo daily mean quan sát không cân theo nhịp lấy mẫu; thiếu mẫu có thể ảnh hưởng mean. — [gdd_forecast.py:51](<D:/IOT Trung/code_full_server/scripts/gdd_forecast.py:51>).
- Traceability group theo lot_id đếm event/stages/last_seen; event là synthetic image metadata. Không thấy product_batches/batch_events join telemetry hoặc incident/action/verification trong module này. — [traceability.py:46](<D:/IOT Trung/code_full_server/service/traceability.py:46>), [traceability.py:77](<D:/IOT Trung/code_full_server/service/traceability.py:77>).
- Tracing có inject/extract Datadog context trong MQTT, trace JSON gồm trace_id/span_id/duration/error, là nền tảng tốt. Tuy nhiên trace chỉ truyền khi payload producer có context; Wokwi payload không có context. Access log middleware là text, không thêm trace ID trực tiếp. — [observability.py:103](<D:/IOT Trung/code_full_server/service/observability.py:103>), [observability.py:122](<D:/IOT Trung/code_full_server/service/observability.py:122>), [middleware.py:8](<D:/IOT Trung/code_full_server/service/middleware.py:8>).
- ask_ai bắt HTTPError và trả string cảnh báo trong hàm được decorator trace, do đó span cha ask_ai có thể error=false dù generate_content child có lỗi. Code có span model/tool, nhưng audit chưa thấy explicit LLMObs instrumentation/token usage/cost/quality evaluations. — [ai_service.py:204](<D:/IOT Trung/code_full_server/service/ai_service.py:204>), [ai_service.py:333](<D:/IOT Trung/code_full_server/service/ai_service.py:333>).
- Demo APM chọn HOLD theo boolean flatline và gán flow_lpm=0 hoặc 20.5 bằng Python. Đây không phải ACK thiết bị/đo lưu lượng độc lập. — [demo_apm_irrigation_trace.py:80](<D:/IOT Trung/code_full_server/scripts/demo_apm_irrigation_trace.py:80>), [demo_apm_irrigation_trace.py:97](<D:/IOT Trung/code_full_server/scripts/demo_apm_irrigation_trace.py:97>).
- DD_VERSION mặc định 1.0.0, chưa phải bằng chứng Change Tracking thực tế của mỗi release. — [observability.py:33](<D:/IOT Trung/code_full_server/service/observability.py:33>).

### Inferences
- Pipeline chất lượng trước GDD: lọc provenance, daily coverage/missing, rolling stddev và age, đánh dấu untrusted; báo khoảng mù thay vì lấp/đổi giá trị. Không kết luận flatline đơn thuần là hỏng vật lý: cảm biến lượng tử hóa có thể đứng trong đất ổn định, cần age/sequence/reference và điều kiện vận hành.
- Time series workload nên demonstrate server-side downsample (5min/hour/day), explain executionStats, số docs trả về và latency cùng điều kiện. So sánh SQLite đủ index trên cùng workload/dataset; không khẳng định Mongo thắng chung mọi trường hợp.
- Hồ sơ lô cần actual lot_id -> node/zone + khoảng trồng, incident bắt đầu/kết thúc, thời gian thiếu dữ liệu, nguồn và quality flags, action ACK và verification. Synthetic image giữ vai trò minh họa, không là ảnh thực địa.
- LLMObs chỉ có giá trị sâu nếu đo tool/error/token/latency và việc AI có tuân thủ HOLD trong tình huống untrusted; cost chỉ khi có usage và bảng giá đúng. Tách model outcome/provider availability/safety decision; error=false của root không đồng nghĩa tưới thành công.
- SLO nên đo fresh-and-trusted decision windows và verified command success, không chỉ HTTP 200. Mẫu số độc lập với nguồn bị chết để không mất cả lỗi lẫn tổng sự kiện.

### Gaps
- Không có benchmark/Explain/latency p95/cost theo hóa đơn trong lần audit. Không chấm ưu thế DB hoặc tiết kiệm tiền bằng số phần trăm tự đặt.
- Không có evidence trong scope cho SLO, Incident Management/Notebooks, LLMObs hoàn chỉnh hay live Change Tracking. Các mục đó trong memory là ý định, không nên ghi hoàn tất.

## 3. Câu chuyện tích hợp nào vừa sâu vừa triển khai được?

### Takeaway
Một lô dưa có hồ sơ chất lượng dữ liệu theo thời gian, gặp hai loại sự cố khác nhau: mất transport tự sửa được và cảm biến đứng giá trị phải cô lập. Mongo lưu bằng chứng gốc và tính ảnh hưởng; Datadog giảm bước chẩn đoán và thực hiện phản ứng có kiểm tra.

### Cited Findings
- Cả hai scenario transport và flatline cùng tiêu chí 6 bản tin phục hồi đã được ghi vào memory, nhưng phần bằng chứng/cô lập chưa được triển khai đủ trong các module audit. — [memory.md:43](<D:/IOT Trung/code_full_server/memory.md:43>).
- Wokwi có công tắc fault khiến Node2 về 2.4, chuyển lại normal dựa trên node1+noise; bridge và state control tách rời thời gian thực qua MQTT. — [sketch.ino:100](<D:/IOT Trung/code_full_server/wokwi/smiot_demo/sketch.ino:100>), [wokwi_datadog_bridge.py:95](<D:/IOT Trung/code_full_server/scripts/wokwi_datadog_bridge.py:95>).

### Inferences
- Scenario A: baseline -> dừng bridge -> độc lập chứng minh source còn phát, broker/app/DB còn khỏe -> app age metric Alert -> Bits chọn hoặc inconclusive -> policy xác minh process target -> restart tối đa 1 -> kiểm chứng source seq đối chiếu Mongo + 6 mẫu mới -> OK; không giấu data gap. Negative control: dừng nguồn Wokwi thay vì bridge -> workflow từ chối restart do không đủ precondition.
- Scenario B: switch frozen soil2 nhưng sequence/other channels still changing -> quality pipeline đánh dấu untrusted -> Alert/Bits -> command HOLD -> Wokwi ACK actual virtual relay off -> persist -> operator restores switch -> 6 mẫu chất lượng, unlock có policy -> lot timeline có blind/untrusted interval. Negative control: monitor OK nhưng thiếu actuator ACK -> vẫn HOLD, không resolve action.
- Chứng minh giá trị: so thời gian/tác vụ thủ công và assisted trên cùng fault run, cùng định nghĩa detect/diagnose/restore; đo số alert trùng/false positive; số database rows returned/scanned và query duration; khôi phục có evidence chéo không phụ thuộc dashboard.
- Ưu tiên: P0 nguồn gốc/cô lập/time/seq/ACK; P1 quality pipeline + bridge restart controller và verified recovery; P2 lot impact + SLO + LLM guardrail evidence; P3 forecast khi đủ lịch sử. Các “điểm mục tiêu” chỉ hợp lệ sau khi có các bộ evidence.

### Gaps
- Cần tiêu chí lỗi vật lý được chuyên gia nông học/thiết bị xác nhận trước khi suy từ 2.4 sang hỏng cảm biến. Khóa an toàn trong mô phỏng không chứng minh giảm thiệt hại cây/nước ngoài thực tế.

