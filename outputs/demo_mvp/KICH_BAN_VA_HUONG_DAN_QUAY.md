# SMIOT: kịch bản và hướng dẫn quay demo MVP

Hai bản quay từ cùng một kịch bản:
- **Bản đầy đủ**, khoảng 9 phút 30 giây: giới thiệu toàn bộ tính năng, rồi demo một sự cố từ đầu đến cuối.
- **Bản ngắn**, khoảng 4 phút 30 giây: giữ các cảnh đánh dấu "(ngắn)".

Thuyết minh bằng tiếng Việt. Mọi thiết bị trong demo là thiết bị ảo; nói rõ điều này trong video.

## 1. Chọn kịch bản cho phần demo sự cố

Chỉ chọn kịch bản mà Datadog đã phát hiện trong các lần diễn tập đã đo (nguồn: `drill_suite_20261112T225228Z.json`, `drill_suite_pump_20261113T023126Z.json` trên EC2). Số đo là dữ liệu diễn tập, không phải cam kết hiệu năng.

| Kịch bản | Monitor | Datadog phát hiện sau | Datadog về OK sau | Dùng trong video |
|---|---|---|---|---|
| C10 (rò đường ống) | W1 | 79,1 s | 286,5 s | Kịch bản chính |
| A2 (áp bơm bằng 0) | W1 | 79,1 s | 286,3 s | Dự phòng |
| A3 (lưu lượng thấp) | W1 | 109,8 s | 317,6 s | Dự phòng |
| S3, A1, A4, S2, C2 | W7, W1, W9, W8 | không phát hiện, hoặc chưa về OK | không áp dụng | Không quay |

Về phục hồi của C10: monitor tự về OK khi dữ liệu trở lại bình thường. Workflow W1 đưa hệ thống về an toàn (SAFE_STOP, đóng van) và xác minh ACK/sổ lệnh; nó không tự chạy lại bơm. Trong lần đo, việc xóa chế độ an toàn do script diễn tập gửi. Khi quay, người vận hành bấm "Dừng kịch bản"; không nói "Datadog tự phục hồi hệ thống".

## 2. Chuẩn bị trước khi bấm quay

Mục nào chưa đạt thì dừng lại sửa, không quay.

1. Đăng nhập admin trước khi quay. Mật khẩu không được lộ trong video.
2. Thanh trên cùng hiện "Gateway đang nhận dữ liệu" (xanh). Nếu hiện "Gateway mất tín hiệu", kiểm tra broker MQTT và cầu nối Velxio trước.
3. Nhãn "Dữ liệu mô phỏng" vẫn hiện. Không ẩn.
4. Ba dự án Velxio (node1, node2, flow) chạy bản sketch v2; Serial Monitor có `MQTT connected` hoặc `MQTT ready`.
5. Nhà màng quay phần diễn tập: `greenhouse_j`. Thẻ hiển thị mẫu mới.
6. Không có diễn tập đang chạy; chế độ an toàn đã xóa.
7. Mở sẵn tab: Tổng quan, Sự cố, Datadog (/chart), Số đo, Bơm, Biến tần, Lịch tưới, Thiết bị, Mùa vụ và truy xuất, Dự án, Phân quyền; thêm tab Datadog monitor W1 và dashboard "SMIOT | 10-Farm Portfolio".
8. Chạy thử toàn bộ một lần không quay, bấm giờ. Phát hiện của Datadog mất khoảng 80 đến 110 giây; về OK mất khoảng 290 đến 320 giây.
9. Trạng thái thật: monitor nào đang Alert lúc quay (ví dụ W7, W8) thì giữ nguyên và nói đúng, không giả lập.
10. Ẩn khỏi khung hình: token, khóa API, ID tài khoản AWS, IP, email cá nhân, thanh dấu trang.

## 3. Kịch bản quay

### Phần A. Giới thiệu và tổng quan

**Cảnh 1. Bài toán (0:00 đến 0:30) (ngắn)**
Màn hình: trang Tổng quan.
Lời: "Một nhà màng mất tín hiệu hay rò đường ống thì người vận hành thường biết muộn. SMIOT là trung tâm giám sát, điều hành và phục hồi sau sự cố cho 10 nhà màng dưa lưới. MongoDB là nền dữ liệu vận hành. Datadog là trung tâm quan sát, phát hiện, điều tra và phản ứng. Toàn bộ thiết bị trong demo là thiết bị ảo."
Thao tác: chỉ nhãn "Dữ liệu mô phỏng", chip Gateway.

**Cảnh 2. Đăng nhập và phân quyền (0:30 đến 0:50)**
Màn hình: trang đăng nhập (quay riêng từ bản đã chuẩn bị, không nhập mật khẩu thật trước ống kính), rồi vào thanh bên.
Lời: "Người dùng đăng nhập theo tài khoản. Menu hiển thị theo quyền: nhóm Quan sát, Điều khiển, Mùa vụ, Quản trị."
Thao tác: chỉ bốn nhóm menu bên trái.

**Cảnh 3. Tổng quan 10 nhà màng (0:50 đến 1:40) (ngắn)**
Màn hình: Tổng quan, chế độ "Tất cả".
Lời: "Dải trên cùng có năm số: nhà màng cần chú ý, sự cố đang mở, mẫu node cũ nhất, thông báo chờ người xem, lệnh chờ ACK. Bảng tín hiệu cho thấy 10 nhà màng theo nhiệt độ, độ ẩm, pH, lưu lượng, quạt. Khối Cần chú ý nói thẳng nhà màng nào cần làm gì."
Thao tác: chỉ dải KPI; bảng tín hiệu; khối Cần chú ý; biểu đồ tuổi mẫu; biểu đồ nhiệt độ và độ ẩm đất, chuyển 1 giờ, 6 giờ, 24 giờ; dòng thời gian sự cố 24 giờ; khối Cần người duyệt và Thông báo.

**Cảnh 4. Một nhà màng (1:40 đến 2:30)**
Màn hình: bấm thẻ tab `Greenhouse J`.
Lời: "Mỗi nhà màng có số đo mới nhất của hai node, biểu đồ theo thời gian, trạng thái thiết bị ảo, các lệnh gần đây. Mỗi lệnh đi qua ba bước: đã gửi, thiết bị đã ACK, kết quả đã xác minh. Phần thời tiết lấy từ Open-Meteo, dự đoán tưới của AI chỉ là đề xuất, không tự điều khiển bơm."
Thao tác: chỉ các thẻ số liệu; biểu đồ; khối "Thiết bị ảo"; "Lệnh gần đây" và chuỗi ba bước; "Sự cố đang mở"; "Dự báo thời tiết"; "Dự đoán tưới của AI".

**Cảnh 5. Chuông thông báo (2:30 đến 2:45)**
Màn hình: bấm biểu tượng chuông.
Lời: "Thông báo của hệ thống và của Datadog workflow đổ về đây, có liên kết thẳng tới hồ sơ sự cố."

### Phần B. Quan sát và điều khiển

**Cảnh 6. Datadog (2:45 đến 3:05)**
Màn hình: trang Datadog.
Lời: "Trang này mở dashboard, monitor và log của Datadog trong tab mới, để người vận hành đi từ ứng dụng sang công cụ quan sát mà không phải tìm."

**Cảnh 7. Số đo (3:05 đến 3:25)**
Màn hình: trang Số đo.
Lời: "Số đo cảm biến của nhà màng đang chọn, lấy từ dữ liệu đã lưu trong MongoDB, lọc theo khoảng ngày."

**Cảnh 8. Bơm (3:25 đến 3:50)**
Màn hình: trang Bơm.
Lời: "Bảng bơm gửi lệnh tới bộ mô phỏng PLC. Bật bơm cần xác nhận; tắt bơm gửi ngay. Sổ lệnh cho thấy từng lệnh đã gửi, đã ACK, đã xác minh hay chưa."
Thao tác: chỉ bảng bơm và sổ lệnh. Không bật bơm trong video.

**Cảnh 9. Biến tần (3:50 đến 4:10)**
Màn hình: trang Biến tần.
Lời: "Biến tần ảo có chạy, dừng, đổi chế độ, đồng bộ PID. Mọi thao tác nguy hiểm đều hỏi xác nhận."

**Cảnh 10. Lịch tưới (4:10 đến 4:30)**
Màn hình: trang Lịch tưới.
Lời: "Lịch tưới trong ngày, dòng hoạt động, tổng nước thực tế mỗi ngày trong tuần. Dữ liệu đọc từ MongoDB."

**Cảnh 11. Thiết bị (4:30 đến 4:55)**
Màn hình: trang Thiết bị, ba tab Node 1, Node 2, Node 3.
Lời: "Ba thiết bị ảo ESP32 trong Velxio: cảm biến môi trường, bơm và LED, đo lưu lượng. Chúng gửi dữ liệu qua MQTT."

### Phần C. Mùa vụ và quản trị

**Cảnh 12. Mùa vụ và truy xuất (4:55 đến 5:35)**
Màn hình: Mùa vụ và truy xuất.
Lời: "MongoDB giữ cả vòng đời mùa vụ. Màn hình cho thấy tiến độ dưa lưới, điều kiện tích lũy, chất lượng dữ liệu theo ngày và ảnh theo từng giai đoạn. Mã QR của lô mở trang công khai chỉ đọc."
Thao tác: chỉ bốn khối; mở trang công khai của lô nếu có sẵn mã QR.

**Cảnh 13. Dự án và Phân quyền (5:35 đến 6:00)**
Màn hình: Dự án, rồi Phân quyền.
Lời: "Trang Dự án tóm tắt tín hiệu theo nhà màng, quyền truy cập và người dùng. Trang Phân quyền cấp quyền theo nhà màng và theo chức năng. Quản trị viên mới xem được hồ sơ sự cố và chạy diễn tập."

### Phần D. Sự cố: Phát hiện, Điều tra, Phản ứng

**Cảnh 14. Datadog đang thấy gì (6:00 đến 6:35) (ngắn)**
Màn hình: trang Sự cố, khối "Datadog đang thấy gì".
Lời: "Mười ca sự cố được theo dõi bằng monitor và workflow của Datadog. Mỗi thẻ cho biết trạng thái hiện tại, lần đổi trạng thái cuối, số lần diễn tập. Số đếm do ứng dụng ghi nhận từ MongoDB."
Thao tác: rê chuột qua từng thẻ; dừng ở W1; chỉ nút Monitor và Workflow. Nếu chụp ảnh số đếm, ghi mốc thời gian.

**Cảnh 15. Chạy kịch bản (6:35 đến 7:05) (ngắn)**
Màn hình: trang Bơm, khối "Diễn tập thiết bị ảo" (chỉ admin thấy).
Lời: "Để minh họa, tôi chọn kịch bản rò đường ống. Thiết bị ảo sẽ phát dữ liệu sai như thật. Từ lúc này, việc phát hiện và xử lý do Datadog dẫn dắt."
Thao tác: chọn nhà màng `greenhouse_j`; ô "Kịch bản" chọn `C10`; seed mặc định; bấm "Chạy kịch bản".

**Cảnh 16. Pha 1, Phát hiện (7:05 đến 7:50) (ngắn)**
Màn hình: Datadog, monitor W1.
Lời: "Cảm biến lưu lượng ảo báo lưu lượng cao, áp suất thấp. Monitor của Datadog chuyển sang Alert. Trong lần đo của chúng tôi, Datadog phát hiện sau khoảng 79 giây."
Thao tác: tải lại trang cho tới khi Alert. Chỗ chờ: cắt hoặc tua nhanh, kèm đồng hồ trên màn hình.

**Cảnh 17. Pha 2, Điều tra (7:50 đến 8:40) (ngắn)**
Màn hình: hồ sơ sự cố vừa tạo, rồi Datadog logs lọc theo `incident_id`.
Lời: "Điều tra có hai nguồn. Datadog cho metric, log, trace gắn mã sự cố. MongoDB giữ hồ sơ, sổ lệnh và dữ liệu cảm biến quanh thời điểm sự cố. Một mã sự cố đủ để dựng lại diễn biến."
Thao tác: cuộn ba bước của hồ sơ; mở logs Datadog; quay lại.

**Cảnh 18. Pha 3, Phản ứng và chứng minh (8:40 đến 9:20) (ngắn)**
Màn hình: hồ sơ sự cố, chuỗi lệnh, trang Bơm.
Lời: "Workflow của Datadog đưa hệ thống về chế độ an toàn và xác minh ACK. ACK chỉ cho biết thiết bị ảo đã nhận lệnh; kết quả chỉ tính là xác minh khi số đo đọc lại khớp. Người vận hành bấm Dừng kịch bản, ứng dụng phục hồi sau khoảng một đến hai giây; monitor về OK khi dữ liệu trở lại bình thường."
Thao tác: chỉ chuỗi ba bước; bấm "Dừng kịch bản"; chỉ dòng phục hồi. Monitor về OK mất khoảng 290 đến 320 giây: tua nhanh hoặc quay riêng rồi ghép, kèm nhãn "tua nhanh" hoặc "quay riêng".

**Cảnh 19. Kết (9:20 đến 9:35) (ngắn)**
Màn hình: Tổng quan.
Lời: "SMIOT cho thấy cả vòng phát hiện, điều tra, phản ứng trên cùng một nền dữ liệu: MongoDB giữ bằng chứng, Datadog dẫn dắt từng pha. Thiết bị là thiết bị ảo; số đo trong video là dữ liệu diễn tập."

## 4. Hướng dẫn quay

### Dụng cụ
- OBS Studio (miễn phí). Bản nhanh có thể dùng Xbox Game Bar (Win+G).
- Micro rời hoặc tai nghe có mic, phòng yên tĩnh.
- Trình duyệt: hồ sơ riêng cho demo, không tiện ích, không dấu trang.

### Cài đặt OBS
1. Video: 1920x1080, 30 FPS.
2. Đầu ra: MKV rồi Remux sang MP4 (tránh mất file khi lỗi), bitrate 8000 Kbps.
3. Nguồn: "Thu cửa sổ" cho trình duyệt, không thu toàn màn hình.
4. Bật "Không làm phiền" của Windows.

### Hiển thị
- Phóng trình duyệt 110 đến 125%.
- Làm nổi con trỏ chuột, di chậm.
- Chỗ chờ không để trống: nói tiếp phần kiến trúc hoặc cắt khi dựng.

### Quy trình
1. Quay thử cả kịch bản, bấm giờ từng cảnh.
2. Quay theo cảnh, mỗi cảnh một file; nói sai thì quay lại cảnh đó.
3. Cảnh 18: quay riêng đoạn monitor về OK, ghép sau, ghi nhãn.
4. Dựng: cắt chỗ chờ, tua nhanh có nhãn, thêm phụ đề cho số quan trọng (79 giây, 1 đến 2 giây).
5. Xuất MP4 1080p; nghe lại cả video trước khi nộp.

### Khi nói
- Nói "thiết bị ảo", "dữ liệu diễn tập".
- Không nói Datadog phát hiện mọi kịch bản; không nói Datadog tự phục hồi.
- 79 giây và 1 đến 2 giây là số của lần đo, không phải đảm bảo.
- Không đọc hay hiển thị token, mật khẩu, khóa API.

## 5. Khi có sự cố lúc quay

| Tình huống | Cách xử lý |
|---|---|
| "Gateway mất tín hiệu" trước khi chạy | Dừng quay; kiểm tra broker MQTT và cầu nối Velxio. |
| Datadog chưa Alert sau 3 phút | Dừng kịch bản, chờ monitor về OK, quay lại từ cảnh 15. |
| Đã có diễn tập đang chạy | Bấm "Dừng kịch bản", chờ vài giây rồi chạy lại. |
| Chế độ an toàn còn bật | Xóa trước khi quay; không quay khi còn bật. |
| Monitor về OK quá lâu | Quay riêng đoạn về OK và ghép, ghi nhãn. |

## 6. Điều chưa kiểm trực tiếp

- Mô tả từng trang dựa trên mã giao diện, chưa chạy ứng dụng để xem từng màn. Chạy thử một lần trước khi quay.
- Thao tác chi tiết trong hồ sơ sự cố của C10 (cảnh 17, 18) theo thiết kế; cần xác nhận khi chạy thử.
