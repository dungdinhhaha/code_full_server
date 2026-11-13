# A8 summary

## Đã làm gì
Viết `outputs/round2/ca2/SUMMARY.md` với 6 câu trả lời, mỗi câu trỏ tới bước. Chưa chạy dry-run `explain_before_after.py`.

## Kỳ vọng
SUMMARY đủ 6 câu. JSON dry-run lưu trong thư mục ca2. `A_status.state=done`.

## Thực tế
SUMMARY đã viết đủ 6 câu, nhưng ba câu về incident (phát hiện, ID, phục hồi) còn ghi "chưa xác định". Dry-run không chạy được vì thiếu `--incident-id`, và không lấy được id khi chưa đăng nhập `/incident`.

## Nguyên nhân và ý nghĩa
Đây là điểm chưa hoàn thành. Muốn chạy dry-run cần người dùng đăng nhập `/incident` và cung cấp id incident Ca 2 (hoặc cấp phiên đã đăng nhập cho trình duyệt). Trạng thái ghi trong `A_status.json` là `done` kèm cảnh báo, để người dùng quyết định trước Ca 3.
