# A5 set normal

## Đã làm gì
Chạy `set_demo_sensor_fault.py normal` trên EC2 qua SSM. Ghi `ca2_normal_set_utc` = 02:43:41Z. Không cần lặp lại.

## Kỳ vọng
Lệnh exit 0. Publisher ACK về trạng thái normal. Mẫu sau khi đổi có độ ẩm đất dao động lại.

## Thực tế
Exit 0 sau 26 giây. Publisher ACK: "Node 2 normal mode applied." Mẫu đầu tiên sau khi đổi: soil_humidity=40.0% lúc 02:44:07Z.

## Nguyên nhân và ý nghĩa
Lỗi flatline đã được gỡ trên luồng dữ liệu giả. Mẫu 40.0% không còn đóng băng. Đây là điểm bắt đầu khôi phục. Việc monitor và incident về trạng thái OK/recovered sẽ kiểm ở A6 và A7.
