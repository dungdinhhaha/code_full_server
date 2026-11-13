# Review hồ sơ nộp bài v2 (Haiku, chỉ đọc)

Phạm vi: 7 file docx trong `outputs/nop_bai_v2/` (01 đến 07), đọc đoạn và bảng bằng python-docx. Không đọc mã dự án, không sửa file. Hình ảnh trong `_build/img` chưa được kiểm tra nội dung.

## 1. Năm yêu cầu bắt buộc của đề bài

1. Ứng dụng dùng MongoDB làm nền dữ liệu vận hành và bằng chứng.
2. Datadog là trung tâm của cả ba pha (phát hiện, điều tra, phản ứng); MongoDB là nền dữ liệu và bằng chứng.
3. Pha Phát hiện: monitor và cảnh báo bắt được lỗi, suy giảm hoặc rủi ro trước khi người dùng biết.
4. Pha Điều tra: nối metrics, logs, traces và bối cảnh vận hành để tìm nguyên nhân.
5. Pha Phản ứng: khắc phục và chứng minh hệ thống trở lại bình thường bằng dữ liệu.

## 2. Bảng vấn đề

| File | Vị trí | Vấn đề | Mức (cao/vừa/thấp) | Gợi ý sửa |
|---|---|---|---|---|
| 01 | Mục 3.2 (đoạn chính) | Phân vai ghi Datadog chỉ "điều tra: quan sát, phát hiện và điều phối", MongoDB "tác động", app "điều hướng". Datadog không được gán vai trò ở pha Phản ứng và pha Phát hiện, trái yêu cầu Datadog trung tâm ba pha. | cao | Phân vai theo pha: Datadog giữ phát hiện (monitor), điều tra (metric, log, trace theo incident_id), điều phối workflow có guard, và xác nhận phục hồi (monitor về OK). MongoDB giữ hồ sơ và bằng chứng, ghi lệnh. App thực thi lệnh có guard. Nêu bằng chứng Datadog của từng pha, không dùng giọng tranh công. |
| 01 | Mục 2.1 | Pha Phát hiện mở đầu bằng watchdog và findings trong MongoDB; monitor Datadog chỉ là gạch đầu dòng thứ tư. Vai trò trung tâm của Datadog ở phát hiện không rõ. | cao | Đưa monitor Datadog lên đầu mục như lớp phát hiện chính; watchdog ghi vào MongoDB là lớp bổ trợ. |
| 01 | Mục 2.1 | "Monitor Datadog trên metric smiot.* (19 monitor SMIOT)" chưa được chứng minh: 03 Bảng 3 không ghi query hay tên metric của từng monitor. | vừa | Ghi metric trong query của các monitor chính, hoặc bỏ cụm "trên metric smiot.*". |
| 01 | Mục 2.3 | Pha Phản ứng nêu MQTT ACK, guard khởi động lại, xác minh bằng health, MongoDB, MQTT. Không có bằng chứng Datadog (monitor chuyển về OK) cho việc trở lại bình thường. | cao | Thêm bằng chứng Datadog: thời điểm Alert và OK của monitor cho mỗi ca (ví dụ Ca 1 có sẵn: Alert 04:49:21Z, OK 05:00:21Z). |
| 01 | Mục 1 và caption Bảng 2 (mục 5) | Ghi "mỗi ca được ghép với monitor và workflow đọc trực tiếp từ Datadog", nhưng W10 có monitor "Theo ảnh giao diện 13/11", không có ID. Nguồn caption ghi "Datadog API". | cao | Ghi W10 nguồn ảnh giao diện, hoặc tra ID monitor và đọc lại qua API rồi cập nhật bảng. Sửa caption cho đúng nguồn. |
| 01 | Bảng 2 (mục 5) | Ô bị lẫn ký tự phân cách: "SMIOT \| telemetry status mismatch", "Ca 1 \| Refuse restart..."; cột bị lệch. Tên monitor không thống nhất (có hoặc không tiền tố "SMIOT"). | vừa | Tách cột đúng, bỏ "\|" trong ô, dùng một quy cách tên monitor cho toàn hồ sơ. |
| 01 | Bảng 3 (mục 5) | Cột "Trạng thái trên app" dễ bị đọc là trạng thái Datadog. "Alert" của W7 và "No Data" của W10 không được giải thích. | vừa | Ghi trong tiêu đề cột "trạng thái giao diện app lúc 11:02:50", và chú thích ý nghĩa Alert, No Data. |
| 01 | Mục 5 | Nhãn Ca 1-3 và W1, W5-W10 dùng song song. W2 và W3 xuất hiện trong mã (w2-greenhouse-j, w3_recovery_verification) nhưng không được định nghĩa trong hồ sơ. | vừa | Thêm một đoạn định nghĩa nhãn W, và ánh xạ W2, W3 với ca hoặc giải thích tên. |
| 01 | Mục 5, Bảng 2 | Tên Ca 2 là "Node 2 đứng số đo", còn 05 và 06 ghi "độ ẩm đất Node 2 đứng yên". | thấp | Thống nhất một tên ca ở mọi file. |
| 01 | Bảng 5 (mục 7) và caption Bảng 6 (03) | 23 định nghĩa monitor trong mã và 19 monitor live không được đối chiếu; người đọc không hiểu chênh lệch 4. | vừa | Ghi: 23 định nghĩa trong mã, 19 monitor SMIOT trên tổ chức ngày 13/11, và lý do chênh lệch có nguồn. |
| 02 | Mục 1 (đoạn 1) | "Datadog đảm nhiệm điều tra; app điều hướng; MongoDB tác động và giữ bằng chứng". Lặp lại cách phân vai của 01 3.2, cùng thiếu vai Datadog ở phát hiện và phản ứng. | cao | Đồng bộ với sửa ở 01 3.2. |
| 02 | Mục 3.2 (trong 02 mục 1 và 03 mục 1) | 02 mục 1 nói "Datadog ... phát hiện và điều phối", còn 01 mục 2.1 nói phát hiện là watchdog ghi vào MongoDB. Hai file mâu thuẫn về ai phát hiện. | cao | Chọn một cách mô tả thống nhất trong 01, 02, 03. |
| 02 | Bảng 1 và Bảng 2 | Trên server có 24 collection (không tính hệ thống), trong mã có 26 tên. Không nêu collection nào trong mã chưa có trên server. | vừa | Thêm cột "có trên server (13/11)" vào Bảng 2, hoặc ghi tên hai collection thiếu. |
| 02 | Bảng 1 (validator 0) và mục 6.2 | Mục 6.2 mô tả $jsonSchema cho 6 collection như một tính năng đang dùng. Bảng 1 cho biết trên server có 0 validator. | vừa | Ghi rõ trong mục 6.2 rằng validator chưa áp dụng trên server (0 validator). |
| 02 | Mục 3 | "36 lệnh khai báo ... có chủ đích trùng lặp để khởi tạo an toàn": câu này gây hiểu nhầm như lỗi thiết kế. Tổng 19 + 11 + 6 = 36, còn stage_envelopes thêm 2. | thấp | Mô tả trung tính: chỉ mục khai báo ở ba nơi, tổng 36 lệnh cộng 2 lệnh stage_envelopes. |
| 02 | Mục 5 | Khoảng dòng "345-480" và "472-480" không khớp với pipeline (345-472). | thấp | Sửa số dòng theo mã hiện tại. |
| 02 | Mục 4 | Nêu script benchmark so sánh executionStats nhưng không có kết quả. Người đọc kỳ vọng có số đo. | thấp | Nếu có số đo có nguồn, đưa vào bảng; nếu không, nêu rõ script là công cụ đo, không kèm số. |
| 02 | Bảng 7 (mục 7) | Liệt kê collection theo ca nhưng không chỉ rõ bằng chứng phục hồi (ví dụ action_ledger ở trạng thái verified, mẫu telemetry sau khi phục hồi). | vừa | Thêm cột "bằng chứng phục hồi" cho từng ca. |
| 03 | Mục 1 (đoạn 1) | "Datadog là lớp quan sát và điều tra". Mở đầu hồ sơ quan sát đã thu hẹp vai Datadog, trái yêu cầu Datadog trung tâm cả ba pha. | cao | Viết lại: Datadog là trung tâm ba pha: phát hiện (monitor), điều tra (metric, log, trace theo incident_id), phản ứng (workflow có guard), xác nhận phục hồi (monitor về OK). |
| 03 | Mục 2.2 và 2.3 | Nêu trace và log có incident_id nhưng không có ví dụ trace hoặc log cụ thể cho ca nào. | vừa | Thêm một hình chụp hoặc trích log và trace của Ca 1 đến Ca 3 (không chứa ID tài khoản, token). |
| 03 | Mục 2.3 | "Theo PROGRESS.md (12/11) ... có thêm system.log và error.log": nguồn là ghi chép nội bộ, không phải trạng thái đọc trực tiếp 13/11. | thấp | Ghi nguồn đọc 13/11 hoặc bỏ đoạn này. |
| 03 | Mục 4, Bảng 3 | Cột "Tên" chứa cả loại và vai trò ("SMIOT \| sensor flatline \| query alert \| ..."), cột bị lệch so với 4 cột tiêu đề. | vừa | Tách thành 4 cột: ID, tên, loại, vai trò. |
| 03 | Mục 4 (đoạn 1) | Không giải thích trạng thái Alert và No Data của W7, W10 khi Bảng 5 đưa vào. | thấp | Giữ thống nhất giữa 01, 03, 06. |
| 03 | Mục 3, Bảng 2 | Tiêu đề "Dashboard (live 13/11)" nhưng số widget lấy từ file JSON. Cột tên dashboard chứa "SMIOT \| 10-Farm Portfolio", lệch cột. | thấp | Sửa tiêu đề cột và tách tên dashboard. |
| 03 | Mục 5, Bảng 4 | Cột "Gắn với" chứa "SMIOT \| Ca 1 \| ..." và lệch cột. | vừa | Tách cột: ID, tên workflow, ca. |
| 03 | Mục 5 (đoạn cuối) | "Kịch bản diễn tập (A1 đến S6)" dễ hiểu là toàn bộ 36 mã; thực tế đây là danh mục 36 mã theo 5 nhóm. | thấp | Ghi "danh mục 36 kịch bản (nhóm A, C, D, H, S)". |
| 03 | Mục 6, Bảng 6 | W2 greenhouse_j có monitor sensor flatline và workflow w2-greenhouse-j. Không nói rõ W2 có phải Ca 2 và workflow khôi phục có phải Ca 3 không. | vừa | Ghi ánh xạ W2 với ca, nếu đúng. |
| 03 | Mục 7 | Liệt kê endpoint /recover của w2-greenhouse-j, nhưng Ca 3 có tên workflow "Guarded EC2 app recovery". Không có ánh xạ tên workflow với endpoint. | vừa | Thêm bảng ánh xạ workflow, endpoint, ca. |
| 04 | Mục 4 (đoạn cuối, sau Bảng 3) | "Các biến khóa Datadog, URI MongoDB và khóa dịch vụ AI/Telegram được khai báo trong mã nguồn tương ứng": câu mơ hồ, dễ đọc là khóa nằm trong mã. Mâu thuẫn với 01 Bảng 4 ("không có giá trị mặc định trong mã"). | cao | Viết lại: giá trị khóa đọc từ biến môi trường, không có giá trị mặc định trong mã. Chỉ nêu tên biến. |
| 04 | Bảng 2 (mục 2.1) | Datadog Agent ghi "Tùy chọn cho quan sát". Trái với vai trò trung tâm của Datadog. | cao | Ghi Datadog Agent là thành phần bắt buộc để chạy phát hiện, điều tra và phản ứng đầy đủ. |
| 04 | Bảng 3 (mục 4) | Thiếu tên biến MongoDB URI (mục 3.1 nói "biến URI"), khóa Gemini và Telegram. | vừa | Thêm tên biến, không thêm giá trị. Đồng bộ với 07 Bảng 6. |
| 04 | Bảng 4 (mục 5) | Không có bước áp dụng Terraform lên Datadog. Cách đưa monitor, dashboard, workflow lên tổ chức không được nêu. | thấp | Thêm bước "áp dụng Terraform" hoặc ghi rõ đã áp dụng. |
| 04 | Mục 9 | "Bảng kích hoạt từng ca nằm trong tài liệu 05": 05 Bảng 4 chỉ ghi "Theo cấu hình ca trong app" cho 7 trên 10 ca. | vừa | Ghi tên cấu hình hoặc bước cụ thể để kích hoạt từng ca. |
| 05 | Bảng 2 (mục 4, FR) | Không có yêu cầu chức năng cho thời gian phát hiện trước người dùng và cho chứng minh phục hồi bằng monitor Datadog. | vừa | Thêm FR về phát hiện (đo thời gian) và FR về xác nhận phục hồi bằng trạng thái monitor. |
| 05 | Mục 2 (bảng phần mềm) | Datadog Agent là "Tùy chọn" nhưng mục 7.2 yêu cầu kiểm tra monitor, log, dashboard. Mâu thuẫn nội bộ và với yêu cầu trung tâm. | cao | Đổi thành bắt buộc cho pha quan sát và phản ứng. |
| 05 | Bảng 4 (mục 6.2), cột "Cách kích hoạt" | 7 trên 10 ca ghi "Theo cấu hình ca trong app; chưa đối chiếu trực tiếp trên giao diện". Cụm "chưa đối chiếu" là nội dung chưa làm, trái quy định. Cách kích hoạt không đủ để tái lập. | cao | Bỏ cụm "chưa đối chiếu". Thay bằng bước cụ thể (tên cấu hình, thao tác UI, lệnh API). Nếu chưa kiểm trên giao diện, thực hiện kiểm trước khi nộp. |
| 05 | Bảng 7 (mục 8) | Tiêu chí chấp nhận chỉ có 3 ca. 7 ca còn lại không có tiêu chí. | vừa | Thêm tiêu chí cho đủ 10 ca, hoặc nêu tiêu chí chung kèm bảng ngoại lệ. |
| 05 | Mục 7.2 | Danh sách monitor chỉ ghi theo tên ("sensor flatline, telemetry status mismatch, smiot.service inactive, W1, W9") không có ID. | thấp | Thêm ID monitor tương ứng với tên. |
| 06 | Bảng 1 (mục 2), các hàng W6, W7, W8, Ca 2 | Cột bị lệch: hàng W6 và W7 và W8 có ô "W6" hoặc "W7" nằm ở cột Monitor, tên monitor nằm ở cột Workflow. Ca 2 có tiền tố "SMIOT" không thống nhất. | cao | Sửa bảng: cột Monitor là tên và ID monitor, cột Workflow là tên và ID workflow. Bỏ ô thừa. |
| 06 | Bảng 2 (mục 3.3) | Cột "Monitor (ID live)" của Ca 2 có ô thừa "SMIOT". | vừa | Sửa theo cùng quy cách như Bảng 1. |
| 06 | Bảng 3 (mục 3.4) | Hàng W6, W7, W8 có 5 ô trong khi bảng có 4 cột. Ô "Phản ứng" hiện "Hồ sơ sự cố và bằng chứng trong MongoDB", ô "Điều tra" hiện tên monitor. W10 ghi "Theo workflow W10" ở cột Phát hiện, không có monitor. | cao | Sửa cột: Phát hiện là monitor, Điều tra là hồ sơ hoặc bằng chứng, Phản ứng là workflow. W10: ghi monitor đã đọc, hoặc nguồn ảnh giao diện như Bảng 1 của 01. |
| 06 | Mục 3.1, 3.2, 3.3 (các gạch "Bằng chứng") | Tham chiếu "EVIDENCE_INDEX E-55, E-81" trỏ tới tài liệu không có trong bộ hồ sơ. Người đọc không kiểm được bằng chứng. | cao | Đưa bảng bằng chứng (E-xx, nguồn, thời điểm) vào phụ lục của 06, hoặc ghi nguồn và thời điểm ngay trong câu. |
| 06 | Bảng 1, dòng W5 | "(ánh xạ suy theo tên)" là dấu hiệu ánh xạ chưa được xác nhận, không đủ làm bằng chứng. | vừa | Xác nhận ID monitor qua API và bỏ cụm "suy theo tên". |
| 06 | Mục 4.2 (Bảng 5), mục 4.3 (Bảng 6) | Trong 8 mã diễn tập, monitor phát hiện được 4 (A3, C10, S3, A2). Không phát hiện được 4 (S2, C2 ở 12/11; A1, A4 ở 13/11). Hồ sơ không tóm tắt tỷ lệ này và không nêu nguyên nhân. | cao | Thêm đoạn tóm tắt trung tính: phát hiện 4 trên 8 mã, nêu mã nào chưa phát hiện, nguyên nhân dự kiến và hướng xử lý. |
| 06 | Mục 4.3 (Bảng 6), dòng A2 | A2 có phát hiện 79,1 s và về OK 286,3 s, gần như trùng C10 (79,1 s và 286,5 s). Khả năng chép nhầm. | vừa | Kiểm lại từ file drill_suite_pump_20261113T023126Z.json. Ghi nguồn file và khóa dữ liệu. |
| 06 | Bảng 5 (mục 4.2) và các mã không về OK | Pha Phản ứng (trở lại bình thường bằng dữ liệu) có S3 "không về OK trong dữ liệu ghi nhận", còn S2, C2, A1, A4 không có số liệu về OK. Thiếu bằng chứng trở lại bình thường cho các mã này. | cao | Ghi lý do monitor không chuyển Alert hoặc không có chu kỳ OK. Bổ sung bằng chứng thay thế cho mã đó (mẫu telemetry mới, ACK, trạng thái sự cố đóng). |
| 06 | Mục 1 (đầu) | "Tài liệu mô tả danh mục kịch bản sự cố" dùng "kịch bản sự cố" cho danh mục sự cố. Trái quy định: "ca" là sự cố, "kịch bản" chỉ là demo trực tiếp. | cao | Đổi thành "danh mục ca sự cố và danh mục kịch bản demo". |
| 06 | Mục 1 (đoạn bullet thứ hai) | Thời điểm phát hiện đọc từ monitor theo chu kỳ, nhưng chu kỳ đọc và sai số của số giây không được nêu. | vừa | Ghi chu kỳ đọc monitor và sai số ước lượng. |
| 06 | Mục 4.2 (bullet thứ ba) | "Số mẫu MongoDB có scenario_run_id là 0" là phát hiện quan trọng về liên kết dữ liệu nhưng không giải thích. Dễ bị hiểu là thiếu bằng chứng MongoDB. | vừa | Ghi lý do (liên kết bằng incident_id, không bằng scenario_run_id) và cách truy vết bằng chứng. |
| 06 | Mục 4 (đoạn đầu) | Ánh xạ kịch bản vào ca chỉ nêu bằng văn xuôi, không có bảng. Không thống nhất với 05 Bảng 4. | vừa | Thêm bảng ánh xạ kịch bản, ca, monitor, workflow. |
| 06 | Mục 4.2, Bảng 5, cột Kịch bản | Mã C2 ghi "scenario_type C2", không có tên kịch bản như các mã khác. | thấp | Điền tên kịch bản cho đồng nhất. |
| 06 | Mục 3.2 (Ca 2) | Phản ứng là "Confirm local interlock", là xác nhận, không phải khắc phục. Chưa nêu kết quả khắc phục. | thấp | Nêu rõ kết quả khắc phục hoặc xác nhận, và dữ liệu chứng minh. |
| 07 | Bảng 6 (mục 6) | Tiêu đề "Biến môi trường theo tên" nhưng thiếu MongoDB URI, khóa Gemini, Telegram có trong mã và 04. | vừa | Đồng bộ danh sách biến với 04 Bảng 3. |
| Chung | Toàn bộ hồ sơ | "Diễn tập" được dùng cho cả số lần chạy ca (Bảng 3 của 01) và kịch bản (06 mục 4). Thuật ngữ bị nhập nhằng. | vừa | Dùng "số lần chạy" cho ca, "lần chạy kịch bản demo" cho kịch bản. |
| Chung | Toàn bộ hồ sơ | Nhãn "ca", "kịch bản", "diễn tập" và tên ca không thống nhất giữa các file (Ca 2 có hai tên). | vừa | Lập một bảng thuật ngữ ở đầu 01 và áp dụng cho cả bộ. |
| Chung | Các file có tham chiếu bằng chứng | EVIDENCE_INDEX không đi kèm bộ hồ sơ. | cao | Đưa một phụ lục bằng chứng vào bộ nộp. |

## 3. Điểm đề bài mở yêu cầu nhưng hồ sơ chưa thể hiện rõ

1. Datadog ở pha Phát hiện: không có số liệu thời gian phát hiện so với thời điểm người dùng biết (ví dụ thời điểm đầu tiên giao diện hiện OFFLINE so với thời điểm monitor Alert). Chỉ có thời gian monitor phát hiện theo chu kỳ đọc.
2. Tỷ lệ phát hiện: 4 trên 8 mã chạy được monitor phát hiện, chưa được tóm tắt và chưa có kế hoạch cải thiện.
3. Datadog ở pha Điều tra: chưa có ví dụ cụ thể về metric, log và trace của một ca được nối với nhau bằng incident_id (ảnh hoặc trích dẫn có nguồn).
4. Datadog ở pha Phản ứng: chưa có biểu đồ hoặc bảng trước và sau khắc phục, lấy từ metric hoặc monitor Datadog, cho một ca.
5. Trở lại bình thường bằng dữ liệu: chỉ có số đếm phục hồi (Bảng 3 của 01). Chưa có chuỗi dữ liệu trước và sau khắc phục cho từng ca (ví dụ telemetry, trạng thái sự cố đóng, monitor OK).
6. Đóng vòng bằng MongoDB: hồ sơ có dòng thời gian hộp đen nhưng chưa có ví dụ đầu ra của pipeline cho một ca, để chứng minh MongoDB giữ bằng chứng đủ để dựng lại diễn biến.
7. Ánh xạ ca với W2, W3 và với endpoint khôi phục: chưa rõ.
8. Hình ảnh và biểu đồ: các caption có sẵn, nhưng chưa kiểm tra nội dung hình trong `_build/img`. Cần đối chiếu từng hình với số liệu trong bảng.

## 4. Kiểm tra quy định

- Không thấy tên cuộc thi, ngành, chuyên ngành.
- Không thấy token, khóa, mật khẩu, chuỗi kết nối, IP, email, ID tài khoản trong bảy file. Các ID monitor, workflow, dashboard có trong hồ sơ là ID công khai trong tổ chức.
- Có cụm "chưa đối chiếu trực tiếp" trong 05 Bảng 4, vi phạm quy định không viết mục chưa làm.
- Có "kịch bản sự cố" trong 06 mục 1, vi phạm phân biệt ca và kịch bản.
- Số liệu có nguồn ở phần lớn bảng. Ngoại lệ: W10 monitor (ảnh giao diện, 01 và 06), A2 (nghi chép nhầm), các ô tham chiếu EVIDENCE_INDEX không kèm tài liệu.
- Tổng số đếm đã kiểm: 10 nhà màng, 36 kịch bản (7+10+7+6+6), 19 DogStatsD, 19 monitor, 5 dashboard, 10 workflow, 23 định nghĩa monitor (17+5+1), 36 lệnh chỉ mục (19+11+6), 25 collection nghiệp vụ cộng _counters: khớp.
