# A0 preflight

## Đã làm gì
Chỉ đọc. Kiểm account 920235987407, SSM Online, `/healthz` trên EC2, trạng thái `smiot`, `mongod`, `mosquitto`, và timer `smiot-external-probe`. Kiểm script `set_demo_sensor_fault.py` có tồn tại.

## Kỳ vọng
Account đúng, SSM Online, healthz 200 với mongo ok và mqtt ok, các dịch vụ đều active.

## Thực tế
- Account 920235987407, SSM Online.
- healthz HTTP 200, body `app=ok, mongo=ok, mqtt=ok`, mẫu mới nhất cách đây 15 giây.
- smiot, mongod, mosquitto, smiot-external-probe.timer đều active.
- Script set_demo_sensor_fault.py có mặt.

## Nguyên nhân và ý nghĩa
Đạt đủ điều kiện đi tiếp. Không có lỗi tồn dư. Lần đầu chạy `aws ssm send-command` bị lỗi do BOM trong file JSON tham số. Đã ghi lại file không BOM và chạy lại thành công. Aws-mcp run_script bị hook chặn vì máy thiếu Git Bash, nên dùng AWS CLI profile aws-moi như kế hoạch cho phép.
