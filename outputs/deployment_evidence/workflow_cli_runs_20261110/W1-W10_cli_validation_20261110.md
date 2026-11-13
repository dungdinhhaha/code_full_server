# Datadog W1–W10 CLI validation — 2026-11-10

## Kết quả

- Cả 10 workflow đều đã được chạy bằng Pup CLI; lượt mới nhất của từng workflow kết thúc `Success`.
- Cả 10 workflow hiện `Published`, có cả trigger Monitor và API.
- Terraform `plan` cuối cùng: không có thay đổi cần áp dụng.
- W2, W3, W4 và W5 đã được cập nhật API trigger qua Terraform để CLI gọi được.
- Không cần sửa hoặc triển khai backend EC2: W3 verifier đã ghi nhận `already_healthy`; `/healthz` trước đó xác nhận app, MongoDB, MQTT đều khỏe và telemetry mới.

## W3 được sửa và chạy lại

Lỗi cũ: Datadog lặp bước xác minh 13 lần dù backend đã trả trạng thái khỏe, rồi hết lượt chờ và gửi nhánh “chưa xác minh”.

Cấu hình hiện tại: bước verifier coi HTTP 202 là đang chờ, retry tối đa 12 lần, mỗi 10 giây; khi nhận 200 thì phân loại kết quả, nếu hết lượt/lỗi thì gửi thông báo chưa xác minh. Cấu hình live đã đọc lại; retry và fallback đúng như dự kiến.

Lượt kiểm chứng W3: `17e6954f-39a6-461c-b18c-32510d181f69`, 2026-11-10 16:05:24–16:05:29 UTC. `Send_command`, `verify_smiot_recovery`, `classify_smiot_recovery` (nhánh `true`) và `notify_verified_smiot_app` đều thành công. Kết quả là `already_healthy`; guard không khởi động lại dịch vụ vì ứng dụng đã khỏe.

## Kết quả theo workflow

| Ca | Trạng thái lượt CLI | Nhánh quan sát được |
|---|---|---|
| W1 | Success | Thiếu bằng chứng vận hành → fail-safe, thông báo |
| W2 | Success | Không xác nhận interlock tại thời điểm chạy → escalation an toàn |
| W3 | Success | Đã khỏe → xác minh, thông báo phục hồi/khỏe; không restart |
| W4 | Success | Không xác nhận tình huống cần từ chối restart → escalation an toàn |
| W5 | Success | Không phân loại được lỗi dependency → nhánh không có breach |
| W6 | Success | Không có bằng chứng detector breach → escalation an toàn |
| W7 | Success | Không xác nhận rủi ro cần hành động → escalation an toàn |
| W8 | Success | Không xác nhận rủi ro môi trường cần hành động → escalation an toàn |
| W9 | Success | Không xác nhận lỗi ACK → escalation an toàn |
| W10 | Success | Thiếu bằng chứng lỗi nhà cung cấp AI → fail-safe, thông báo |

## Giới hạn của lượt kiểm tra

Đây là lượt chạy API chủ động, không phải diễn tập tiêm lỗi. Vì vậy W1/W2/W4–W10 chủ yếu chứng minh workflow chạy được và đóng nhánh an toàn khi thiếu/không có tín hiệu vi phạm; chưa chứng minh từng nhánh lỗi và hành động khắc phục thực tế. `Success` của workflow không đồng nghĩa mọi ca đã đạt Level 5.

Các bước gửi thông báo trong các lượt đều báo thành công ở Datadog. Lượt này chưa đọc lại trực tiếp chuông thông báo trong giao diện ứng dụng.

## Bằng chứng máy đọc

`W1-W10_verified_latest.json` chứa workflow ID, run ID, thời gian UTC, trạng thái và trạng thái từng bước. Tập JSON không chứa khóa hay credential.
