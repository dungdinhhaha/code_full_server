## Đã làm gì
Gắn workflow Ca 1 vào monitor mismatch qua giao diện Datadog.

## Kỳ vọng
Monitor có một automation và vẫn OK trong thời gian mute.

## Thực tế
Trang trạng thái hiện OK, 2 nhóm muted, Recipients from message có `workflow-smiot-ca1-refuse-restart`.

## Nguyên nhân và ý nghĩa
Monitor sẽ gọi workflow khi mismatch phát cảnh báo sau khi hết hoặc gỡ downtime. Workflow chỉ Echo và không thể restart app, nên tránh hành động sai với Ca 1. Chưa diễn tập Ca 1.
