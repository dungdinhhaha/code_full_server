# A6 verify recovery

## Đã làm gì
Sau A5 (normal lúc 02:43:41Z), poll monitor 339977691 mỗi khoảng 30 giây cho đến khi về OK. Kiểm `/healthz` và lịch sử workflow sau khi khôi phục.

## Kỳ vọng
Incident chuyển `recovered`. Verifier thấy ≥7 mẫu dao động, HOLD đã ACK, CLEAR đã gửi. `/healthz` 200.

## Thực tế
- Monitor 339977691 vẫn Alert ở 02:45:22Z, 02:45:58Z, 02:46:33Z. Về OK lúc 02:47:07Z, khoảng 206 giây sau khi đặt normal.
- `/healthz` lúc 02:47:15Z: HTTP 200, app/mongo/mqtt ok, mẫu mới nhất cách 8.1 giây. smiot, mongod, mosquitto đều active.
- Không có execution workflow mới sau khi khôi phục. Execution duy nhất vẫn là e09175ca từ A4.
- Không đọc được trạng thái incident `recovered` và các điều kiện verifier vì `/incident` yêu cầu đăng nhập.

## Nguyên nhân và ý nghĩa
Tín hiệu flatline của monitor đã trở về 0 và monitor OK, cùng với healthz 200 và mẫu mới. Đây là bằng chứng khôi phục một phần, dựa trên monitor và healthz. Bằng chứng đầy đủ theo kế hoạch (incident recovered, HOLD đã ACK, CLEAR đã gửi) chưa xác định. Cách kiểm tra: người dùng mở `/incident`, xem hồ sơ incident Ca 2 và trạng thái recovered. Ca 3 không nên bắt đầu trước khi xác nhận mục này.
