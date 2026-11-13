## Đã làm gì
Xuất bản workflow Ca 1 với một bước Echo ghi lý do không restart.

## Kỳ vọng
Khi monitor mismatch gọi workflow, workflow hoàn tất mà không tác động EC2 hay thiết bị.

## Thực tế
Giao diện ghi Published; đồ thị nối Monitor trigger với Echo. Chưa có execution từ cảnh báo thật.

## Nguyên nhân và ý nghĩa
Metric mismatch được app phát khi UI báo OFFLINE trong lúc mẫu Mongo còn mới. Workflow từ chối mọi restart theo thiết kế. Đây là chính sách an toàn bảo thủ, chưa phải guard tự truy vấn tuổi mẫu Mongo; chưa thể tuyên bố đã kiểm chứng nhánh `G2_fresh_sample_refuse` trong script.
