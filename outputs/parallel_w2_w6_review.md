# Rà soát độc lập diễn tập song song W2/W6 — 11/11/2026

Đã đối chiếu TASKS, PROGRESS, ACTIVITY_LOG, harness local, workflow JSON W6 và monitor Terraform. Lượt này chỉ đọc tệp và ghi kết quả rà soát. Kết luận áp dụng cho cấu hình đã xem và bản đọc lại Datadog 06:00 UTC đã ghi trong nhật ký.

## Phát hiện

1. **W6 có thể bỏ sót lỗi của farm phát cảnh báo.** Monitor Terraform nhóm theo `farm` và kiểm tra giá trị thấp hơn 1. Workflow query dùng `max:smiot.detector.evaluation_heartbeat{detector:agronomic_advisory}` trên toàn bộ farm rồi chọn nhánh evidence observed nếu kết quả lớn hơn 0. Ví dụ, farm A trả 0 và farm B trả 1 thì phép max có thể trả 1 cho lần chạy do farm A kích hoạt. Cần kiểm tra workflow nhận chính xác nhóm farm kích hoạt và dùng cùng phạm vi metric. Nếu thiếu hoặc không xác thực được farm, ghi nhận pending/unknown. Bằng chứng cần có là W6 nhận biết A lỗi dù B khỏe, sau đó chính A trở về OK và có bằng chứng persisted evaluation của A. Đối chiếu thêm query monitor live và tình trạng giới hạn tần suất theo nhóm.
2. **Harness có thể báo exit code thành công khi lượt chạy thất bại.** Script ghi `local_parallel_rehearsal_timeout_or_error` hoặc `cleanup_incomplete` nhưng chỉ exit 1 khi `aborted`. Công cụ gọi chỉ kiểm exit code có thể ghi nhận sai. Nếu hai lượt gọi khởi động trong cùng một giây và dùng cùng thư mục, cả hai còn có thể ghi đè cùng tên JSON vì tên chỉ có timestamp đến giây. Khi dùng harness, đọc trường `result`, `cleanup.jobs_stopped` và xác nhận hai lane trong đúng artifact của lượt gọi. Tách tên artifact và trả exit code lỗi cho lượt timeout hoặc cleanup không thành công khi cập nhật harness.
3. **Harness chỉ diễn tập điều phối fixture local.** Hai PowerShell jobs có farm, incident và run riêng, tạo dữ liệu mô phỏng và ghi JSON local. Code không gọi simulator, AWS, Datadog, app, MQTT hay MongoDB. W2 đã triển khai bản vá theo nhật ký nhưng còn thiếu ACK, dữ liệu Mongo ổn định theo cadence, monitor OK và app CLEAR trong cùng incident. W6 đã publish workflow theo nhật ký nhưng còn thiếu định tuyến theo farm và xác minh recovery. Điều kiện hiện có trong TASKS yêu cầu từng ca độc lập đạt gate trước khi chồng fault.

## Tệp đối chiếu

- `scripts/drill_parallel_w2_w6.ps1` dòng 21–29, 57–102, 108–127
- `outputs/workflow_imports/w06_smiot-w06-detector-heartbeat.json` dòng 44–53, 75–98
- `deploy/datadog/terraform_monitors/monitors.tf` dòng 150
- `service/detector_heartbeat.py` dòng 137–153
- `TASKS.md` mục Local parallel rehearsal harness và Whole-system rehearsal gates
- `PROGRESS.md` mục Execution update 06:00 UTC và Parallel W2/W6 local rehearsal harness
