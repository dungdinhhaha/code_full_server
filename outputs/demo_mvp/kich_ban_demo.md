# Kịch bản Demo MVP — SMIOT Smart Farm

---

## PHẦN 1: MỞ ĐẦU — Vì sao cần sản phẩm này?

### 1.1 Thị trường nông nghiệp thông minh đang bùng nổ

> Trình chiếu slide số liệu thị trường (ảnh 37.png)

- **Toàn cầu**: thị trường Smart Agriculture từ **$14–23 tỷ USD (2024)** lên **$23–56 tỷ USD (2029–2032)**, tăng trưởng **10–13%/năm** (MarketsandMarkets, Verified Market Research, 360iResearch).
- **Áp lực tài nguyên**: 69% nước ngọt toàn cầu dùng cho nông nghiệp (FAO AQUASTAT); cần tăng **+50% sản lượng** vào 2050 so với 2012 (FAO, 2021).
- **Việt Nam**: xuất khẩu rau quả đạt **$8.5 tỷ USD** (2025); thị trường cảm biến nông nghiệp **$25.5 triệu → $64.9 triệu** (2025–2034, IMARC).

### 1.2 Vấn đề thực tế

Nhà kính hiện tại:
- Giám sát thủ công, phát hiện lỗi chậm (hàng giờ hoặc khi cây đã hư hại).
- Không có hệ thống ghi nhận sự cố tự động — mất dữ liệu truy xuất nguồn gốc.
- Thiếu liên kết giữa dữ liệu cảm biến, hành động xử lý và hồ sơ mùa vụ.

### 1.3 Giới thiệu SMIOT

**SMIOT** (Smart Monitoring for IoT) — nền tảng giám sát nhà kính thông minh, xây dựng trên:

| Thành phần | Vai trò |
|---|---|
| **Ứng dụng NiceGUI** | Giao diện vận hành: dashboard, điều khiển, xem hồ sơ |
| **MongoDB Atlas** | Lưu trữ hồ sơ sự cố, dữ liệu mùa vụ, truy xuất nguồn gốc |
| **Datadog** | Giám sát real-time, phát hiện bất thường, điều phối phản ứng tự động |

→ Ba thành phần phối hợp tạo vòng lặp khép kín: **Phát hiện → Phản ứng → Ghi nhận → Truy xuất**.

---

## PHẦN 2: GIỚI THIỆU CHỨC NĂNG — Từng tab của ứng dụng

### Nhóm "Quan sát"

#### Tab 1: Tổng quan (`/`)
> [Chụp screenshot trang chủ]

- Dashboard tổng hợp trạng thái tất cả nhà kính (greenhouse_a, b, c).
- Hiển thị số liệu cảm biến mới nhất: nhiệt độ, độ ẩm đất, độ ẩm không khí.
- **MongoDB**: đọc trạng thái thiết bị & dữ liệu mới nhất từ collection `telemetry`.
- **Datadog**: không trực tiếp trên trang này (data đã qua MongoDB).

#### Tab 2: Sự cố (`/incident`)
> [Chụp screenshot danh sách sự cố]
> [Chụp screenshot chi tiết 1 sự cố]

- Danh sách tất cả sự cố (đang xử lý & đã phục hồi).
- Nhấn vào 1 sự cố → hồ sơ đầy đủ gồm 3 pha:
  - **Pha 1 — Phát hiện**: Datadog monitor trigger → mở incident.
  - **Pha 2 — Điều tra**: Datadog log, APM trace, workflow observation.
  - **Pha 3 — Phản ứng**: Hành động HOLD/RESTART, xác minh phục hồi.
- **Vai trò phân chia rõ ràng**:
  - **Datadog →** điều tra (monitor, workflow, log, trace) — mọi link Datadog chỉ hiện khi có ID thật.
  - **MongoDB** = hồ sơ (incident document, action_ledger, timeline, evidence) + tác động (lô ảnh hưởng, khoảng thiếu mẫu).
  - **Ứng dụng** = điều hướng, hiển thị, không tranh công giữa hai bên.

##### Tác động kỹ thuật:
- Datadog giám sát 24/7, phát hiện lỗi trong **5–7 phút** thay vì hàng giờ.
- MongoDB lưu hồ sơ có cấu trúc (incident → action → evidence → lot impact) cho truy vấn sau này.

##### Tác động kinh tế:
- Giảm thời gian downtime nhà kính → ít mất mùa hơn.
- Hồ sơ sự cố liên kết với lô hàng → chứng minh chất lượng cho đối tác thu mua.

#### Tab 3: Datadog (`/chart`)
> [Chụp screenshot trang Datadog]

- Cổng dẫn sang Datadog: Dashboard vận hành, Monitor, Log, LLM Observability.
- **Datadog**: toàn bộ nội dung — dashboard telemetry cảm biến, tài nguyên EC2, MongoDB metrics.
- **MongoDB**: không trực tiếp (data hiển thị trên Datadog dashboard).

#### Tab 4: Số đo (`/data`)
> [Chụp screenshot trang số đo]

- Bảng dữ liệu cảm biến chi tiết theo thời gian.
- **MongoDB**: nguồn dữ liệu — đọc từ collection `telemetry`, hiển thị dạng bảng/biểu đồ.

---

### Nhóm "Điều khiển"

#### Tab 5: Bơm (`/plc`)
> [Chụp screenshot trang bơm]

- Điều khiển bơm tưới cho từng nhà kính.
- **MongoDB**: lưu trạng thái bơm, lịch sử bật/tắt.

#### Tab 6: Biến tần (`/inverter`)
> [Chụp screenshot trang biến tần]

- Giám sát và điều khiển biến tần.
- **MongoDB**: lưu cấu hình & trạng thái biến tần.

#### Tab 7: Lịch tưới (`/schedule`)
> [Chụp screenshot trang lịch tưới]

- Lập lịch tưới tự động theo thời gian.
- **MongoDB**: lưu lịch tưới, trạng thái thực hiện.

#### Tab 8: Thiết bị (`/devices`)
> [Chụp screenshot trang thiết bị]

- Quản lý danh sách thiết bị (node cảm biến, PLC, biến tần).
- **MongoDB**: collection `devices` — metadata thiết bị.

---

### Nhóm "Mùa vụ"

#### Tab 9: Mùa vụ và truy xuất (`/mongodb-lab`)
> [Chụp screenshot trang mùa vụ]
> [Chụp screenshot QR code truy xuất]

- **Chức năng cốt lõi của MongoDB trong sản phẩm:**
  - Chọn nhà kính + lô hàng → xem tiến độ canh tác (gieo, ra hoa, đậu quả, thu hoạch).
  - Ảnh theo giai đoạn, điều kiện tích lũy (GDD, tổng nước tưới, tổng ánh sáng).
  - Chất lượng dữ liệu: số mẫu thu được / kỳ vọng, % coverage.
  - **QR code truy xuất nguồn gốc** — quét → trang public xem toàn bộ lịch sử lô hàng.
- **MongoDB aggregation pipeline**: `load_harvest_story()` tổng hợp từ `telemetry`, `lot_sensor_assignments`, `operational_incidents` → tạo câu chuyện mùa vụ hoàn chỉnh.
- **Datadog**: gián tiếp — sự cố được liên kết qua `incident_id` trong hồ sơ lô.

##### Tác động kỹ thuật:
- MongoDB aggregation xử lý truy vấn phức tạp (join nhiều collection, tính toán tích lũy) ngay trong database.
- Mỗi lô hàng có hồ sơ bất biến — không thể sửa ngược.

##### Tác động kinh tế:
- Truy xuất nguồn gốc tăng giá trị nông sản (đạt chuẩn VietGAP/GlobalGAP).
- QR code cho phép người mua xác minh — tăng niềm tin, tăng giá bán.

---

### Nhóm "Quản trị"

#### Tab 10: Dự án (`/projects`)
- Quản lý danh sách nhà kính/dự án.

#### Tab 11: Phân quyền (`/permission`)
- Phân quyền người dùng: admin, manager, viewer.

---

## PHẦN 3: DEMO 3 CA LỖI

> Chạy lần lượt `run_ca1.py`, `run_ca2.py`, `run_ca3.py` trước khi demo. Mỗi ca tạo đầy đủ: incident MongoDB + Datadog logs + APM trace.

### Ca 1: Trạng thái sai lệch (`false_offline`)
- **Nhà kính**: greenhouse_a / node 1
- **Tình huống**: Datadog monitor phát hiện status_mismatch — node báo OFFLINE nhưng telemetry vẫn hoạt động.
- **Chuỗi xử lý**:
  1. Monitor `max(last_5m)` trigger → phát hiện sau ~6 phút.
  2. Workflow tự động đánh giá → disposition: **REFUSED_RESTART** (không restart vì node thực tế vẫn hoạt động).
  3. Hành động: HOLD → xác minh telemetry bình thường → đóng sự cố.
- **Thời gian phản ứng**: ~6 phút.
- **Ý nghĩa**: Hệ thống đủ thông minh để KHÔNG hành động khi phát hiện false positive — tránh restart không cần thiết gây gián đoạn.

> [Mở `/incident/{ca1_id}` — chụp screenshot hồ sơ sự cố]

### Ca 2: Cảm biến đất phẳng (`soil_humidity_flatline`)
- **Nhà kính**: greenhouse_b / node 2
- **Tình huống**: Độ ẩm đất không thay đổi trong thời gian dài → nghi cảm biến hỏng.
- **Chuỗi xử lý**:
  1. Monitor `max(last_5m)` flatline → phát hiện sau ~7 phút.
  2. Workflow → disposition: **SENSOR_RESET_SCHEDULED** (lên lịch reset cảm biến).
  3. Hành động: HOLD → chờ reset → xác minh giá trị thay đổi trở lại → đóng.
- **Thời gian phản ứng**: ~9 phút.
- **Ý nghĩa**: Phát hiện cảm biến hỏng trước khi dữ liệu sai ảnh hưởng quyết định tưới tiêu.

> [Mở `/incident/{ca2_id}` — chụp screenshot hồ sơ sự cố]

### Ca 3: Dịch vụ ngừng hoạt động (`service_down`)
- **Nhà kính**: greenhouse_c / node 1
- **Tình huống**: Dịch vụ SMIOT trên EC2 bị dừng (systemd unit inactive).
- **Chuỗi xử lý**:
  1. Monitor `avg(last_2m)` systemd + ~3m37s visibility delay → phát hiện sau ~6 phút.
  2. Workflow → disposition: **GUARDED_RECOVERY** (khởi động lại có kiểm soát).
  3. Hành động: HOLD → restart service → external probe xác minh HTTP 200 → đóng.
- **Thời gian phản ứng**: ~5 phút.
- **Ý nghĩa**: Sự cố nghiêm trọng nhất — dịch vụ chết hoàn toàn. Hệ thống tự phục hồi và xác minh bằng probe bên ngoài.

> [Mở `/incident/{ca3_id}` — chụp screenshot hồ sơ sự cố]

---

## TỔNG KẾT: VAI TRÒ 3 THÀNH PHẦN

| | MongoDB | Datadog | Ứng dụng |
|---|---|---|---|
| **Phát hiện** | — | Monitor giám sát metric 24/7 | Hiển thị trạng thái |
| **Điều tra** | — | Log, APM trace, workflow | Dẫn link sang Datadog |
| **Phản ứng** | Ghi nhận hành động (action_ledger) | Workflow tự động quyết định | Hiển thị hồ sơ phản ứng |
| **Lưu trữ** | Hồ sơ sự cố, timeline, evidence | Log lưu trữ dài hạn | Không lưu trữ |
| **Truy xuất** | Aggregation pipeline → câu chuyện mùa vụ | Liên kết qua incident_id | QR code, trang public |

### Giá trị kinh tế tổng hợp
- **Giảm thời gian phát hiện** từ hàng giờ → 5–7 phút (Datadog monitor).
- **Giảm rủi ro hành động sai** — workflow tự động đánh giá trước khi hành động (Ca 1: REFUSED_RESTART).
- **Truy xuất nguồn gốc** cho nông sản — tăng giá trị thương mại (MongoDB + QR).
- **Hồ sơ sự cố bất biến** — chứng minh SLA cho đối tác và bảo hiểm nông nghiệp.

### Giá trị kỹ thuật tổng hợp
- **MongoDB**: document model linh hoạt cho incident (nested evidence, timeline), aggregation pipeline mạnh cho truy xuất.
- **Datadog**: observability toàn diện (metric → monitor → workflow → log → trace), tích hợp sâu với ứng dụng qua API.
- **Ứng dụng**: NiceGUI render real-time, phân quyền, không tranh công với Datadog/MongoDB — chỉ điều hướng và hiển thị.
