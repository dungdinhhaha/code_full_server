# B0 đến B6: kiểm tra điều kiện sẵn sàng Ca 3 (chỉ đọc)

## Đã làm gì
- B0: `sts get-caller-identity` (profile aws-moi) và SSM DescribeInstanceInformation cho `i-00bf2d3591d3ee0a2`.
- B1: liệt kê snapshot completed của volume `vol-0fe7f6c8bac706a78`, lấy bản mới nhất.
- B2: không xác minh được Private Action Runner (Datadog MCP không kết nối, chưa có xác nhận người dùng).
- B3: định chạy `drill_ca3_service_down.ps1` ở chế độ DryRun. Lệnh bị auto-mode classifier từ chối; không thử lại.
- B4: SSM đọc `healthz`, `systemctl is-active`, trạng thái timer probe, 20 dòng journal probe. `probe.env` chỉ in tên biến, giá trị ẩn.
- B5: đọc trang Datadog Monitor List (q=SMIOT) và workflow `b83453ff`.
- B6: ghi `outputs/round2/_sync/B_ready.json`. Không tạo snapshot, không mute, không restart, không chạy `-Confirm`.

## Kỳ vọng
Đủ 6 điều kiện: SSM online, service active, healthz 200, snapshot <= 24 giờ, 5 monitor OK, runner online được xác minh. Mute phải kiểm chứng được. B3 dry-run phải pass.

## Thực tế
- B0 đạt: account 920235987407, SSM Online (ping 09:31 ICT).
- B1 đạt: snapshot mới nhất `snap-031033d62ae7116ce`, tạo 2026-11-05 20:54:22 UTC, tuổi khoảng 5.7 giờ lúc 02:36 UTC.
- B4 đạt: healthz 200 (`app`, `mongo`, `mqtt` đều ok) lúc 02:35:52 UTC. `smiot`, `mongod`, `mosquitto`, timer probe đều active. Probe chạy mỗi 30 giây, các dòng gần nhất có `app_up=1`, `dry_run=false`, `incident_action=none`.
- B5: trang monitor list cho 5 monitor đều OK (khớp theo tên; ID chỉ xác nhận cho 340356283 qua docs). Workflow `b83453ff`: lần chạy gần nhất Success (3s), 2 ngày trước; không thấy Step error mới.
- B2 chưa xác minh runner. B3 chưa chạy. Mute chưa kiểm chứng.
- Kết quả: `ready=false`.

## Nguyên nhân và ý nghĩa
- Chặn chính: chưa xác minh mute (không có quyền ghi, không khẳng định đã mute), chưa xác minh Private Action Runner (cần người dùng xác nhận), B3 dry-run bị classifier chặn.
- Datadog MCP (`plugin:datadog:mcp`) báo ENOTFOUND, nên monitor và workflow được đọc qua trình duyệt, ID từng monitor chưa xác nhận trực tiếp.
- aws-mcp `run_script` bị hook chặn vì thiếu Git Bash. Đã dùng AWS CLI profile `aws-moi` chỉ đọc, phù hợp với mục 0.5 của kế hoạch.
- Các điều kiện hạ tầng (SSM, service, healthz, snapshot, probe) đạt. Phần còn lại cần người dùng xác nhận hoặc xử lý, không phải lỗi hệ thống.
