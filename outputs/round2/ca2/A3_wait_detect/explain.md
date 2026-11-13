# A3 wait detect

## Đã làm gì
Sau T0 = 02:36:40Z, poll monitor 339977691 mỗi khoảng 30 giây qua Datadog MCP. Kiểm 5 monitor còn lại để chắc không Alert ngoài kịch bản. Đọc healthz một lần qua SSM. Thử mở `/incident` để tìm bản ghi mới.

## Kỳ vọng
Monitor 339977691 chuyển Alert trong vòng 10 phút. `/incident` có bản ghi mới `soil_humidity_flatline`. Chụp ảnh lúc Alert.

## Thực tế
- Monitor 339977691 chuyển OK sang Alert. Datadog ghi `last_triggered_ts` 02:41:51Z, tức 311 giây sau T0. Lần poll thấy Alert đầu tiên là 02:42:57Z.
- Bốn monitor ngoài kịch bản (340356283, 339977703, 339990226, 339990232) và Ca 1 (341409441) đều vẫn OK. Không có Alert ngoài kịch bản.
- healthz lúc 02:41:06Z: HTTP 200, app/mongo/mqtt ok, mẫu mới nhất cách 28.5 giây. smiot, mongod, mosquitto đều active.
- `/incident` không đọc được vì trang yêu cầu đăng nhập. Không xác nhận được bản ghi incident mới. Không có ảnh chụp.

## Nguyên nhân và ý nghĩa
Alert đúng như kỳ vọng, sau khoảng 5 phút. Đây là thời gian monitor dùng cửa sổ last_2m và chu kỳ đánh giá. Chưa xác nhận được incident do app mở vì không có quyền vào `/incident`. Cần người dùng đăng nhập và kiểm tra, hoặc cấp phiên đã đăng nhập.
