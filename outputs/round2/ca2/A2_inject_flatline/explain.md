# A2 inject flatline

## Đã làm gì
Chạy `set_demo_sensor_fault.py flatline` trên EC2 qua SSM AWS-RunShellScript. Ghi T0 = 02:36:40Z (09:36:40 ICT).

## Kỳ vọng
Lệnh exit 0, publisher báo ACK flatline, mẫu đầu tiên sau khi đổi có độ ẩm đất đóng băng.

## Thực tế
Exit 0. Publisher ACK: "Node 2 flatline mode applied." Mẫu đầu tiên sau khi đổi: soil_humidity=2.4% lúc 02:37:07Z. Lệnh mất 27 giây.

## Nguyên nhân và ý nghĩa
Lỗi đã được bật trên luồng dữ liệu giả (dữ liệu diễn tập, không phải cảm biến thật). Việc Alert hay không sẽ kiểm ở A3. Đây là lần bơm lỗi đầu tiên trong đợt này; theo kế hoạch không được chạy lại trong 300 giây.
