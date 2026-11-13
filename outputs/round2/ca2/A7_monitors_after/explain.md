# A7 monitors after

## Đã làm gì
Chờ monitor 339977691 về OK (đã về OK lúc 02:47:07Z), rồi kiểm cả 6 monitor (5 monitor SMIOT theo kế hoạch và monitor Ca 1 chỉ đọc).

## Kỳ vọng
5 monitor OK. Ghi `ca2_recovered_utc` và `five_monitors_ok_utc`.

## Thực tế
Cả 6 monitor đều OK lúc 02:47:45Z. Monitor 339977691 OK từ 02:47:07Z. Không có Alert ngoài kịch bản.

## Nguyên nhân và ý nghĩa
Điều kiện 5 monitor OK đạt. `ca2_recovered_utc` để trống vì chưa xác định được trạng thái incident `recovered` (mục A6). Theo cổng Ca 3, ca2_recovered_utc phải có và đã qua 10 phút, nên cổng này chưa đạt. Cần người dùng xác nhận incident Ca 2 đã recovered trên `/incident` trước khi ghi nhận ca2_recovered_utc.
