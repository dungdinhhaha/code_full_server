## Đã làm gì
Tạo monitor Ca 1 bằng giao diện Datadog và đặt downtime hai giờ.

## Kỳ vọng
Monitor nhận metric `smiot.telemetry.status_mismatch`, ở trạng thái OK trước diễn tập và không gửi cảnh báo khi workflow chưa sẵn sàng.

## Thực tế
Monitor 341409441 ở trạng thái OK, có hai nhóm node; giao diện ghi Muted và không có người nhận. Chưa gắn workflow, chưa diễn tập và chưa có bản ghi incident Ca 1.

## Nguyên nhân và ý nghĩa
Query kiểm tra mismatch theo farm/node trong cửa sổ 5 phút. Downtime giữ cảnh báo im lặng trong lúc hoàn thiện guard, không thay đổi dữ liệu hay trạng thái thiết bị. Chưa thể chứng minh nhánh từ chối restart chỉ bằng monitor.
