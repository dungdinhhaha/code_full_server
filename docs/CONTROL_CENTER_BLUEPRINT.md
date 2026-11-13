---
doc_id: SMIOT-DESIGN-CC
title: "Trung tâm giám sát và điều hành nhà màng dưa lưới SMIOT: bản thiết kế"
version: "1.1-draft"
date: "2026-11-09"
language: vi
data_label: synthetic
status: design-proposal
---

# Trung tâm giám sát và điều hành nhà màng dưa lưới SMIOT

Đây là **bản thiết kế đề xuất**, không phải mô tả hệ thống đã hoàn thành.

**Cách đọc trạng thái:** **[CÓ]** đã có trong mã hoặc hệ thống · **[MỘT PHẦN]** có nền nhưng chưa đủ · **[CHƯA]** chưa có.

**Phạm vi thực tế:** 10 nhà màng mô phỏng, thiết bị ảo và dữ liệu tổng hợp. Luồng liên tục trên EC2 do bộ phát nền của ứng dụng tạo; Wokwi không phải nguồn phát liên tục hiện tại.

**Thay đổi so với bản 0.2:** cây trồng và khí hậu được đưa lên thành nhóm đầu của ma trận lỗi (mã nhóm đổi từ A–E sang C/S/D/A/H, xem mục 6); thêm lớp cây trồng (mục 4), cơ chế trực và leo thang (mục 7), tiêu chí "xong" (mục 11), đặc tả giao diện theo lô (mục 12), kịch bản demo (mục 17), tham chiếu nông học (mục 18); lộ trình bị cắt còn phần làm được (mục 16).

**Thay đổi ở bản 0.4 (đính chính sau khi đọc thêm mã):** ba mục từng ghi là "mới" thực ra đã có nền trong dự án — lớp cây trồng (mục 4), động cơ kịch bản (mục 8.1) và cách xử lý tham chiếu nông học (mục 18). Bản 0.3 đã đánh giá thấp dự án ở những chỗ đó.

**Thay đổi ở bản 0.9:** đã **đọc được cấu hình AWS thật** (08/11). Kết quả: tám trong mười việc cloud đã có sẵn và làm đúng — IMDSv2 bắt buộc, Elastic IP, đĩa mã hóa, nhóm bảo mật chỉ mở 80 và 443, S3 có phiên bản và vòng đời. Chỉ còn bốn việc thật (mục 13.3), và cảnh báo về IP ở bản 0.8 đã được giải tỏa (mục 13.2). Đây là lần thứ **tám** bản thiết kế đánh giá thấp hiện trạng dự án.

**Thay đổi ở bản 1.2 (10/11):** W3 được sửa để không phụ thuộc `Get_command` từ Action Connection AWS: thao tác đó bị chính sách tổ chức chặn ở `ssm:ListCommands`. Workflow dùng app verifier trên EC2, kiểm tra kết quả guarded SSM theo đúng run ID, sức khỏe app/MongoDB/MQTT và telemetry mới; nhánh `If` phân loại `recovered`, `already_healthy` hoặc chưa xác minh. Lượt `d8cca009-e355-4791-8e8e-fa853d7971a2` hoàn tất và ghi thông báo vào chuông app; verifier trả `already_healthy`, nên lượt này chứng minh hệ thống khỏe sẵn và **không restart**, chưa chứng minh nhánh khởi động app khi dịch vụ dừng. Bằng chứng runtime: `outputs/workflow_imports/live_verified_20261110/W3_verified_run_d8cca009.json`.

**Thay đổi ở bản 1.3 (10/11, 10:24 UTC):** Đã triển khai mã nhận thông báo/correlation lên EC2 bằng gói đã quét, có bản sao lưu quay lui; sau triển khai `/`, `/healthz`, `/incident`, `/mongodb-lab` đều HTTP 200. Diễn tập W3 làm lộ lỗi thứ tự: run `65cbc329-4845-4243-9a6e-eeb1c94e5f4e` khởi chạy guarded recovery nhưng thông báo app chạy trước khi app lên lại và trả 502, khiến verifier không chạy; kết quả SSM sau đó là `recovered`. Đã bỏ thông báo sớm, nối `Send_command → verify_smiot_recovery`, thêm retry 12×5 giây. Run mới `c8c9bda9-f463-4338-9aa7-85df60f7cdaa` trong lúc app service bị dừng hoàn tất `SUCCEEDED`; verifier trả HTTP 200, `verified=true`, `status=recovered`; app notification trả 202 và được lưu; hậu kiểm xác nhận app, MongoDB, MQTT active và `/healthz` 200. Đây là **trigger API thủ công trong diễn tập outage**, chưa chứng minh monitor tự phát hiện/trigger. Bằng chứng: `outputs/workflow_imports/live_verified_20261110/W3_controlled_recovery_c8c9bda9.json`, `outputs/deployment_evidence/20261110_workflow_notification_update.json`.

**Thay đổi ở bản 1.1 (10/11):** đính chính một hiểu sai của chính bản thiết kế — "tự động" bị hiểu quá hẹp (chỉ tính việc cắt), nên bản trước kết luận sai rằng một nửa ma trận chỉ báo được. Thêm **bốn loại hành động tự động** (mục 7.3) và **danh mục 10 workflow phủ trọn 36 dòng ma trận** (mục 7.4): **34 trên 36 dòng tự động đủ cả ba bước phát hiện, điều tra, phản ứng**; chỉ C7 và C8 dừng ở con người vì hành động là thụ phấn tay và phun thuốc. Thêm bốn gói việc W11–W14 và đổi thứ tự ưu tiên (mục 16.1). Ảnh chụp monitor ngày 10/11 cho thấy **14 monitor**, nhiều hơn con số 6 ghi trong các bản trước; hai cái đang NO DATA (`AI ask latency high`, `PLC command latency high`) vì chưa có metric bơm vào.

**Thay đổi ở bản 1.0 (09/11):** cập nhật triển khai 10 farm lên EC2 và đánh dấu riêng những phần đã được xác minh bằng gói MQTT thực tế. Bộ phát hiện chạy trong ứng dụng, không phải 90 tiến trình thiết bị độc lập. Trong cửa sổ nghe 310 giây, đã nhận 1.300 gói từ 10 farm; cả 9 loại thiết bị ảo đều xuất hiện ở từng farm. Không thay đổi cấu hình Datadog.

**Cập nhật mã cục bộ ngày 09/11 (các phần dưới đây chưa deploy EC2, chưa apply Datadog):** bộ mô phỏng có kịch bản `pipe_leak` và liên động PLC ảo; các lượt scenario được nối vào incident riêng bằng `scenario_run_id`/farm/thời gian, ghi sự kiện trip/ACK vào Mongo idempotently và action ledger; app có producer metric safety/actuator/provenance (phụ thuộc cờ bật và chưa xác minh ingest); có Terraform monitor nháp cho các metric mới nhưng tắt mặc định. S2/S3 có finding có tương quan. VPD có metric; DLI vẫn không khả dụng vì thiếu chuỗi PAR/bức xạ phù hợp. **Riêng Home overview đã deploy và xác minh tương tác trên EC2 ngày 10/11;** các mục còn lại ở đoạn này vẫn chỉ là trạng thái mã cục bộ, chưa phải bằng chứng runtime trên EC2/Datadog.

**Cập nhật mã cục bộ ngày 10/11 (chưa deploy EC2):** Home đang được đổi sang một heatmap duy nhất 10 farm; mỗi hàng dùng mẫu MongoDB mới nhất, gồm nhiệt độ/độ ẩm không khí, độ ẩm đất, EC đất, pH, lưu lượng, thoát nước, phản hồi quạt và trạng thái freshness/incident. Khu vực dưới biểu đồ đọc sự cố đang mở và thông báo MongoDB, bỏ seed notifications. Nguồn `service/agronomic_thresholds.py` đặt ngưỡng advisory dùng chung toàn app: nhiệt độ không khí <10°C hoặc >35°C; độ ẩm không khí >85% là cảnh báo kiểm tra. Chúng tạo/clear Mongo notification khi có chuyển trạng thái trên bất kỳ farm nào, không điều khiển bơm. Độ ẩm đất vẫn chưa có ngưỡng vì cảm biến chưa hiệu chuẩn theo giá thể/field capacity. Bộ mô phỏng đã giảm gradient nhiệt/EC giả tạo giữa các farm. Đây là dữ liệu từ publisher thiết bị ảo lưu trong MongoDB, không phải cảm biến vật lý.

**Thay đổi ở bản 0.8:** bổ sung hai phần còn thiếu mà bản 0.7 chỉ nhắc rải rác — **danh mục thiết bị ảo** đã có và cần thêm (mục 9.1), và **các bước cài đặt cloud cụ thể** kèm lệnh kiểm tra hiện trạng (mục 13.1 đến 13.3), trong đó có cảnh báo: URL demo nhúng địa chỉ IP, nên gán Elastic IP sát hạn sẽ làm đổi URL và phải cấp lại chứng chỉ.

**Thay đổi ở bản 0.7 (sau khi đọc toàn bộ phần còn lại):** **một lời khuyên ở bản trước là nguy hiểm và đã bị rút** — "dọn các trang tĩnh cũ trong `static/`" sẽ làm hỏng trang PLC và trang biến tần, vì hai trang đó đọc `static/test_plc.html` và `static/test_inverter.html` **lúc chạy** (mục 22.4). Thêm: số chỗ khai cứng nhà màng tăng từ 5 lên **7** (mục 9); cơ chế đối chiếu lệnh và phản hồi **đã có** trong giao diện PLC và biến tần (mục 6 nhóm A); `pages/devices.py` là **danh mục sản phẩm tĩnh**, không phải sổ đăng ký thiết bị; bản đồ phủ kiểm thử (mục 11.4); kế hoạch cuối ở mục 16 viết lại theo toàn bộ mã đã đọc.

**Thay đổi ở bản 0.6 (sau khi đọc `pages/schedule.py`):** trạng thái theo người dùng **đã có khuôn đúng** trong `schedule.py` (`app.storage.user`), `home.py` mới là ngoại lệ — xem đính chính dưới bảng mục 15; thêm cảnh báo đơn vị phút so với lít cho lớp cân bằng nước (mục 4.4); thêm yêu cầu một aggregation duy nhất cho màn hình tổng quan (mục 12.1).

**Thay đổi ở bản 0.5 (sau khi đọc hộp đen, vòng đời sự cố và sổ lệnh):** thêm bốn đính chính lớn — lớp đo tác động đã có và chặt hơn bản thiết kế (mục 11.1), validator chỉ bị **tắt bằng cờ môi trường** chứ không thiếu (mục 11.2), việc lên 10 nhà màng vướng **năm chỗ khai cứng** gồm hai chỗ chặn bằng ngoại lệ (mục 9), và **điểm cắm chính xác** cho dải mục tiêu theo giai đoạn (mục 4.4). **Mục 22 ghi rõ phần nào đã đối chiếu mã, phần nào chưa đọc** — đọc mục đó trước khi tin bất kỳ trạng thái [CÓ]/[CHƯA] nào ở trên.

---

# PHẦN I — ĐỊNH HƯỚNG

## 1. Mục tiêu và phạm vi

Trung tâm phải trả lời sáu câu hỏi, **theo thứ tự ưu tiên này**:

1. **Cây có đang ở trong dải điều kiện phù hợp với giai đoạn không?** (khí hậu, nước, EC)
2. Dữ liệu cảm biến còn đáng tin để quyết định tưới không?
3. Cơ cấu chấp hành (bơm, van, quạt, lưới che) có đang an toàn không?
4. Hạ tầng phần mềm và mạng có khỏe không?
5. Khi có lỗi: đã làm gì, vì sao, và dữ liệu nào chứng minh đã phục hồi?
6. Ai đang chịu trách nhiệm xử lý việc đang mở?

Bản 0.2 xếp câu 1 xuống gần cuối. Đó là lỗi định hướng: một trung tâm **nhà màng dưa lưới** được đánh giá bằng việc nó bảo vệ vụ, không bằng việc nó bảo vệ máy chủ.

## 2. Nguyên tắc thiết kế

1. **Cây trồng là trung tâm.** Mọi tín hiệu kỹ thuật tồn tại để trả lời "vụ này có an toàn không". Màn hình mặc định là theo lô, không theo máy.
2. **Dải mục tiêu là cấu hình có phiên bản, không phải số cứng trong mã.** Trung tâm không cần biết con số nông học đúng; nó cần làm cho con số đang dùng **hiện rõ, có phiên bản, và kiểm toán được**. Khi kỹ sư nông học đổi dải, hệ thống ghi ai đổi, lúc nào, dải cũ là gì. Nguyên tắc này giải quyết chỗ hổng lớn nhất: nhóm chưa có kỹ sư nông học xác nhận ngưỡng.
3. **Chia vai:** Datadog điều tra và giám sát; MongoDB đo tác động và giữ bằng chứng; ứng dụng điều hành và điều hướng.
4. **An toàn vật lý xử lý ở biên** (PLC, cổng), không chờ đám mây. Datadog không đặt ở tầng đầu cho sự cố tính bằng giây.
5. **Từ chối khi chưa chắc** (fail-closed): dữ liệu mơ hồ thì giữ an toàn, không đoán.
6. **Hành động nhỏ nhất đủ an toàn**, có khóa, giới hạn tần suất và điều kiện chặn.
7. **Xác minh bằng dữ liệu đọc lại**, không bằng việc lệnh chạy xong.
8. **Ngữ cảnh trước ngưỡng:** cùng một tín hiệu có nguyên nhân khác nhau (rò ống hay mưa rò mái).
9. **Mỗi việc đang mở có một người chịu trách nhiệm.** Không có cảnh báo vô chủ.
10. **Thẻ metric ít chiều:** `farm`, `node`, `source`; mã sự cố, mã lô và mã lệnh nằm ở log, vết và MongoDB.
11. **Trung thực về mô phỏng:** không tuyên bố hiệu quả thực địa, MTTD/MTTR hay SLO khi chưa có nguồn đo.

---

# PHẦN II — THIẾT KẾ HỆ THỐNG

## 3. Kiến trúc theo tầng phản ứng

| Tầng | Vị trí | Thời gian | Việc |
|---|---|---|
| 0 | Phần cứng (phao, van xả áp, nhiệt kế cơ) | tức thời | Chặn mức nguy hiểm nhất, không cần phần mềm [CHƯA — ghi trong thiết kế lắp đặt] |
| 1 | Biên (PLC ảo, cổng) | 1–5 giây | Liên động PLC ảo dừng bơm/đóng van theo giới hạn thời gian/thể tích và mô phỏng áp thấp + lưu lượng cao [MỘT PHẦN — watchdog còn chạy trong cùng tiến trình app; không phải thiết bị độc lập] |
| 2 | Ứng dụng | 5–30 giây | Đánh giá dải mục tiêu, sự kiện khẩn qua MQTT, thông báo, ghi sổ hành động [MỘT PHẦN] |
| 3 | Datadog | 1–5 phút | Monitor, xu hướng, điều tra và workflow có điều kiện chặn. Cả ba ca có workflow đã xuất bản và nối monitor. Ca 1/Ca 2 chưa có diễn tập kích hoạt tự động từ monitor; Ca 1 chưa chứng minh nhánh từ chối restart. |
| 4 | Con người (ca trực) | phút–giờ | Xác nhận, duyệt hành động, cử kỹ thuật viên, bàn giao ca [CHƯA] |

Nguyên tắc chọn tầng: **thời gian gây hại quyết định tầng xử lý.** Tràn nước gây hại trong vài giây nên phải ở tầng 1. Sốc nhiệt gây hại trong vài chục phút nên tầng 2–3 chấp nhận được. EC tích tụ gây hại trong nhiều ngày nên tầng 3–4 là đủ.

## 4. Lớp cây trồng và khí hậu

**Đính chính so với bản 0.3 đầu:** lớp này **đã tồn tại một phần đáng kể** trong `service/mongodb_showcase.py`, và bản thiết kế trước đã đánh giá quá thấp. Những gì đã có [CÓ]:

- Mốc thụ phấn (`crop_cycles.fruit_set_at`) làm gốc tính ngày trong vụ; cửa sổ thu hoạch (`harvest_days_min`/`harvest_days_max`), ngày tham chiếu.
- GDD tích lũy và nhiệt độ trung bình trượt 7 ngày, tính **trong MongoDB** bằng `$setWindowFields`.
- Độ phủ mẫu theo ngày, phát hiện khoảng trống bằng `$shift`.
- **Cổng chất lượng dữ liệu cho kết luận nông học:** `day_complete` chỉ đúng khi độ phủ ≥ 80% và khoảng trống lớn nhất ≤ 3 giờ; GDD chỉ được tính cho ngày đạt. Đây đúng là nguyên tắc "dữ liệu không đáng tin thì không kết luận" mà bản trước trình bày như ý mới.
- Biến đặt tên `gdd_context` chứ không phải `gdd`, và `BASE_TEMP_C = 10.0` kèm chú thích "context indicator only; cultivar-specific agronomy is not configured" — mã đã tự tránh tuyên bố quá mức.

Phần **thật sự còn thiếu** là mục 4.1 (bốn chỉ số dẫn xuất), 4.2 (dải mục tiêu theo giai đoạn) và 4.4 (chiến lược tưới).

### 4.1 Bốn chỉ số dẫn xuất (chưa có)

| Chỉ số | Công thức / nguồn | Dùng để làm gì | Chi phí |
|---|---|---|---|
| **VPD** (thiếu hụt áp suất hơi, kPa) | `VPD = SVP(T) × (1 − RH/100)`, với `SVP(T) = 0,6108 × exp(17,27·T / (T + 237,3))` (Tetens) | Chỉ số khí hậu nhà màng được dùng nhiều nhất: cây có thoát nước được không, nguy cơ bệnh khi VPD quá thấp, đóng khí khổng khi quá cao | **Miễn phí** — tính từ `at` và `ah` đã có trong mỗi bản tin |
| **DLI** (tổng lượng sáng ngày, mol/m²/ngày) | Tích phân bức xạ theo ngày; `shortwave_radiation` đã lấy từ Open-Meteo, cần hệ số chuyển đổi sang PAR (ghi rõ hệ số đang dùng) | Nhu cầu nước và tốc độ sinh trưởng đi theo tổng sáng, không theo giờ trong ngày | **Gần miễn phí** — dữ liệu đã có |
| **Cân bằng nước ngày** | `nhu cầu (ET0 × hệ số cây) − đã cấp + đã thoát`, tích lũy theo ngày và theo lô | Biến "giám sát tưới" thành "điều hành tưới": thấy thừa hay thiếu, tích lũy bao nhiêu | Vừa — ET0 đã có, lượng cấp có trong nhật ký lịch, lượng thoát cần thêm |
| **Thể tích và EC nước thoát** | Cảm biến ảo mới trong bộ mô phỏng | Cách thật để điều hành tưới trên giá thể: tỷ lệ thoát và EC thoát cho biết đang tưới thừa/thiếu và muối có tích tụ không | Nhỏ — **thiết bị ảo nên chỉ cần sửa sketch và bộ mô phỏng, không phải mua phần cứng** |

Hai chỉ số đầu tính được ngay từ dữ liệu hiện có. Bản 0.2 đã bỏ sót cả bốn.

### 4.2 Dải mục tiêu theo giai đoạn (`stage_envelopes`, chưa có)

Mở rộng từ `crop_cycles` đã có: `crop_cycles` giữ mốc vụ và cửa sổ thu hoạch cho **một lô**; `stage_envelopes` giữ dải điều kiện cho **từng giai đoạn**, dùng chung nhiều lô. Một collection MongoDB, mỗi bản ghi là một dải có phiên bản:

```
{
  crop: "melon", stage: "fruit_set",
  version: 3, effective_from: <ts>, author: "<user>",
  bands: {
    soil_moisture_pct: {min: …, max: …},
    vpd_kpa:           {min: …, max: …},
    air_temp_c:        {day: {min, max}, night: {min, max}},
    drain_ratio_pct:   {min: …, max: …},
    drain_ec:          {max: …}
  },
  source: "tham chiếu <tài liệu>, chưa hiệu chuẩn tại chỗ"
}
```

Quy tắc bắt buộc:
- **Hệ thống không chứa số nông học cứng trong mã.** Mọi dải nằm trong collection này.
- Mỗi dải có `source` ghi lấy từ đâu, và trạng thái hiệu chuẩn (`chưa hiệu chuẩn` là trạng thái hợp lệ và trung thực).
- Mỗi lần đổi dải sinh một bản ghi mới, dải cũ giữ lại. Khi điều tra một sự cố, hệ thống dùng dải **đang hiệu lực lúc đó**, không dùng dải hiện tại.
- Giao diện hiện rõ dải đang dùng và phiên bản, ngay cạnh biểu đồ.

### 4.3 Giai đoạn sinh trưởng chi tiết hơn

Bộ giai đoạn hiện có 5 mức (`sowing`, `seedling`, `vegetative`, `flowering_fruiting`, `harvest`) trong `service/traceability.py` [CÓ]. Dưa lưới cần tách `flowering_fruiting` vì yêu cầu nước và khí hậu khác nhau rõ rệt:

| Giai đoạn đề xuất | Đặc điểm cần theo dõi |
|---|---|
| `pollination` (thụ phấn) | Cửa sổ thời gian hẹp; nhiệt độ và VPD ngoài dải làm đậu quả kém |
| `fruit_set` (đậu quả) | Bắt đầu cần nước nhiều |
| `fruit_growth` (nuôi quả) | Giai đoạn quả lớn nhanh: thiếu nước gây hại nặng nhất; tưới không đều gây nứt |
| `netting` (tạo lưới) | Cần ổn định; biến động ẩm ảnh hưởng mẫu mã quả |
| `ripening` (chín) | Thường giảm nước để tăng độ ngọt |

Chuyển giai đoạn theo GDD tích lũy (`scripts/gdd_forecast.py` đã tính `GDD = max(0, T_tb − 10)` [CÓ], hệ số nền 10 °C chưa hiệu chuẩn) và theo người vận hành xác nhận. Ghi rõ: đây là bộ giai đoạn **đề xuất của nhóm**, chưa được kỹ sư nông học xác nhận.

### 4.4 Chiến lược tưới (thay cho chỉ chặn tưới)

**Điểm cắm chính xác đã tìm được.** `service/incident_lifecycle.py` → `record_blocked_irrigation_decision()` đã ghi quyết định tưới có khóa liên động [CÓ]:

```
nominal_rule:    "soil_humidity_below_30_pct_would_request_irrigation"
proposed_action: "IRRIGATE" nếu độ ẩm < 30, ngược lại "NO_ACTION"
applied_action:  "BLOCKED_HOLD"
reason:          "sensor quality incident is open; irrigation command is not permitted"
```

Ngưỡng **30% là số cứng**, không phụ thuộc giai đoạn. Đây là chỗ nhỏ nhất và có giá trị nhất để cắm `stage_envelopes` vào: thay `< 30` bằng dải của giai đoạn đang chạy, và ghi `envelope_version` vào document quyết định. Một thay đổi, và toàn bộ lớp cây trồng có đường vào luồng quyết định đã có sẵn.

Lưu ý: bộ lập lịch (`service/scheduler.py`) và giao diện lịch (`pages/schedule.py`) chạy **hoàn toàn theo thời gian** — người dùng nhập giờ bắt đầu và giờ kết thúc, hệ thống lưu **số phút** vào trường tên là `water_amount`. Không có ngưỡng cảm biến, ET0 hay giai đoạn trong luồng lập lịch. Nên "chiến lược tưới" là lớp mới nằm giữa lịch và khóa liên động, không phải sửa bộ lập lịch.

**Cảnh báo đơn vị cho lớp cân bằng nước:** `water_amount` và `target_water` là **phút**, còn `actual_water` là **lít** (tính từ chênh lưu lượng tích lũy trong `service/scheduler.py`). Tên trường `water_amount` dễ gây nhầm. Lớp cân bằng nước phải quy về một đơn vị và ghi rõ hệ số chuyển, nếu không mọi con số thừa/thiếu nước đều sai.

Các bước còn lại:

1. Nhu cầu ngày tính từ ET0, DLI và giai đoạn.
2. Chia thành các lượt trong ngày theo dải mục tiêu.
3. Sau mỗi lượt, đối chiếu lượng thực cấp và lượng thoát; điều chỉnh lượt sau.
4. Nếu dữ liệu không đáng tin: giữ lượt theo lịch an toàn (không tăng, không bỏ), và báo người vận hành — **không đoán**.
5. Mọi lượt ghi vào sổ hành động kèm dải đang dùng và lý do.

## 5. Bản đồ quan sát theo tầng

| Tầng quan sát | Đã có | Thiếu |
|---|---|---|
| **Cây trồng và khí hậu** | Mốc thụ phấn, cửa sổ thu hoạch, GDD tích lũy, trung bình trượt 7 ngày, độ phủ ngày, cổng `day_complete`, giai đoạn, truy xuất theo lô, ảnh theo giai đoạn [CÓ — `service/mongodb_showcase.py`, `service/traceability.py`] | **VPD, DLI, cân bằng nước, dải mục tiêu theo giai đoạn, số giờ ngoài dải** |
| Cảm biến | 5 chỉ số mỗi nút (`at`, `ah`, `st`, `sh`, `sec`), thẻ `farm`/`node`/`source`; thêm pH và EC nước ở kênh `id4`/`id5` và `measurement_type: water` [CÓ] | Điểm chất lượng mẫu, số mẫu bị loại, độ lệch giữa nút |
| Thiết bị và mạng | Tuổi mẫu, còn tươi, đứng số, lệch hiển thị, độ trễ nạp [CÓ] | Khởi động lại, hụt gói (cờ đã tính trong `service/telemetry_provenance.py`, chưa thành metric), nhịp tim, pin, sóng |
| Chấp hành | Dữ liệu lưu lượng có trong MongoDB và luồng live (`id3`: f1, f2, t1, t2; `measurement_type: flow`); PLC ảo có 8 đầu ra, cờ `safe_mode_active`, và **từ chối lệnh bật khi đang HOLD** (`command_rejected`) [MỘT PHẦN] | **Metric Datadog** cho lưu lượng, áp suất, trạng thái bơm/biến tần; quạt và lưới che; đo lệnh–xác nhận |
| Tưới tiêu | Nhật ký lịch tưới và `actual_water` tính từ chênh lưu lượng tích lũy [CÓ] | Kế hoạch so với thực cấp so với thoát, metric, số lượt thất bại |
| Thời tiết | Nhiệt độ, độ ẩm, bức xạ, ET0, một tọa độ cố định [MỘT PHẦN] | Lượng mưa, xác suất mưa, tọa độ theo nhà màng |
| Hạ tầng | MongoDB/MQTT lên–xuống, probe ngoài, systemd [CÓ] | Số liệu broker, hàng đợi |
| Ứng dụng | Vết cho MQTT, AI, ghi bằng chứng [MỘT PHẦN] | Vết liền mạch từ thao tác người dùng đến xác nhận thiết bị |
| Ca trực | Không có [CHƯA] | Ai đang trực, việc đang mở theo người, thời gian chờ xác nhận |
| Người dùng | Không có [CHƯA] | RUM, Synthetic |
| AI | Vết LLM Observability, nội dung bị che [CÓ] | Tỷ lệ từ chối, tỷ lệ lỗi nhà cung cấp |

## 6. Ma trận lỗi

Mỗi dòng phải có đủ sáu thứ: tín hiệu, bộ phát hiện, bậc phản ứng, nơi thực hiện, cách xác minh, kịch bản gieo lỗi. Mã nhóm: **C** cây trồng · **S** cảm biến · **D** thiết bị và mạng · **A** chấp hành · **H** hạ tầng.

### C. Cây trồng và khí hậu (nhóm ưu tiên cao nhất, mới)

| ID | Tình huống | Phát hiện | Bậc | Nơi | Hiện trạng | Ưu tiên |
|---|---|---|---|---|---|---|
| C1 | Độ ẩm đất ngoài dải của giai đoạn | So với `stage_envelopes` | 2 | Ứng dụng | [MỘT PHẦN] có gate khi thiếu envelope; chưa có dải hiệu chuẩn và finding tổng quát | **P1** |
| C2 | VPD ngoài dải (quá cao: cây đóng khí khổng; quá thấp: nguy cơ bệnh) | VPD tính từ `at`, `ah`; so dải | 1–2 | Ứng dụng | [MỘT PHẦN] có tính/metric VPD; chưa có dải được duyệt | **P1** |
| C3 | Sốc nhiệt giữa trưa | Nhiệt độ vượt dải ngày, kéo dài | 2–3 (mở thông gió) | Biên + ứng dụng | [CHƯA] | **P1** |
| C4 | Tưới thừa (nguy cơ úng rễ) | Tỷ lệ thoát cao, độ ẩm đất không giảm giữa các lượt | 2 | Ứng dụng | [CHƯA] | P2 |
| C5 | Thiếu nước ở giai đoạn quả lớn nhanh | Cân bằng nước âm tích lũy + giai đoạn | 2 + báo gấp | Ứng dụng | [CHƯA] | **P1** |
| C6 | EC tích tụ trong giá thể | EC thoát tăng dần so với EC cấp | 1–2 | Ứng dụng | [CHƯA] | P2 |
| C7 | Trượt cửa sổ thụ phấn | Giai đoạn `pollination` + khí hậu ngoài dải | 1 (báo, không tự xử lý) | Ứng dụng | [CHƯA] | P3 |
| C8 | Nguy cơ bệnh (độ ẩm cao kéo dài, VPD thấp ban đêm) | Số giờ liên tục ngoài dải | 1 | Ứng dụng | [CHƯA] | P3 |
| C9 | Mưa: nhu cầu nước giảm | Lượng mưa, bức xạ, ET0; **ưu tiên độ ẩm đất đo thực hơn dự báo** | 2 (giảm lượt) | Ứng dụng | [CHƯA] (có ET0, bức xạ; chưa có mưa) | P2 |
| C10 | Phân biệt rò ống với mưa rò mái | Độ ẩm tăng + nhật ký tưới + mưa + so các nhà màng | 1–2 | Ứng dụng + Datadog | [MỘT PHẦN] Có kịch bản synthetic áp thấp + lưu lượng cao để kích hoạt safe-stop; chưa có mưa, so sánh nhà màng, hay chẩn đoán nguyên nhân rò thật | P3 |

### S. Cảm biến

| ID | Lỗi | Phát hiện | Bậc | Nơi | Hiện trạng | Ưu tiên |
|---|---|---|---|---|---|---|
| S1 | Đứng số | 10 mẫu, chênh ≤ 0,01, trong 600 giây (theo mã hiện tại) | 2 HOLD | Ứng dụng | [CÓ] (Ca 2) | đã làm |
| S2 | Đột biến | Tốc độ thay đổi vượt giới hạn vật lý | 2 | Ứng dụng | [MỘT PHẦN] có finding gắn scenario; chưa đo precision/false positive | **P1** |
| S3 | Ngoài khoảng vật lý | Khoảng hợp lệ theo loại cảm biến | 2 | Ứng dụng | [MỘT PHẦN] finding ngoài miền có trong code; chưa diễn tập đủ | **P1** |
| S4 | Trôi dần | So với các nút cùng nhà màng (ngoại lai) | 1–2 | Ứng dụng + Datadog | [CHƯA] | P3 |
| S5 | Lệch giữa nút anh em | Chênh lệch bất thường | 1 | Ứng dụng | [CHƯA] | P3 |
| S6 | Nhiễu | Phương sai tăng | 1 | Ứng dụng | [CHƯA] | thấp |

### D. Thiết bị và mạng

| ID | Lỗi | Phát hiện | Bậc | Nơi | Hiện trạng | Ưu tiên |
|---|---|---|---|---|---|---|
| D1 | Dữ liệu cũ / mất tín hiệu | Tuổi mẫu; monitor cũ 339977703 trong snapshot 06/11; current ID chưa xác minh | 1 | Datadog | [CÓ trong snapshot cũ; current cần xác minh] | đã làm lịch sử |
| D2 | Hiển thị sai trong khi dữ liệu tươi | `status_mismatch`; monitor hiện tại `342585836` | 1 (từ chối restart) | Ca 1 `ffd62026-6b63-40e4-9b46-6ac18d2d584f` đã published và monitor `342585836` đã gọi đúng handle; run query-only `d63a1077-308e-4e05-81ad-e1471981577f` đi nhánh escalation, chưa chứng minh nhánh từ chối restart | [MỘT PHẦN] monitor/workflow đã nối và published; manual run đã đi nhánh escalation, chưa diễn tập được nhánh `REFUSED_RESTART` | cần bằng chứng |
| D3 | Thiết bị khởi động lại | Cờ `reboot_detected` | 1 | Ứng dụng + Datadog | [MỘT PHẦN] metric producer/call path có; chưa xác minh Datadog ingest và reboot qua app restart | P2 |
| D4 | Hụt gói, trùng, lùi số thứ tự | Cờ trong provenance | 1 | Ứng dụng + Datadog | [MỘT PHẦN] metric producer/call path có; chưa xác minh ingest | P2 |
| D5 | Giảm tần suất gửi | Tỷ lệ bản tin theo nút | 1 | Datadog | [CHƯA] | P2 |
| D6 | Thiết bị lạ / nhà màng không khớp | Bản tin từ thiết bị chưa đăng ký; hiện bị gán mặc định `greenhouse_a`. **Xác nhận: không có sổ đăng ký thiết bị** — `pages/devices.py` là danh mục sản phẩm tĩnh (12 mục khai cứng, ảnh lấy từ Word), không liên kết với telemetry | 1 | Ứng dụng | [CHƯA] | P2 |
| D7 | Pin, sóng, điện áp | Cần thiết bị báo | 1 | Datadog | [CHƯA] | sau |

### A. Cơ cấu chấp hành (mở rộng: không chỉ tưới)

| ID | Lỗi | Phát hiện | Bậc | Nơi | Hiện trạng | Ưu tiên |
|---|---|---|---|---|---|---|
| A1 | **Tràn nước / quá lượng** | Lưu lượng thực so với dự kiến **trong lúc chạy**, thể tích và thời gian tối đa | 3 (dừng bơm, đóng van) | **Biên** | [MỘT PHẦN] PLC ảo đã chặn theo thời gian/thể tích và áp thấp + lưu lượng cao; chưa so lưu lượng thực với mục tiêu tưới đã hiệu chuẩn | **P1** |
| A2 | Bơm chạy mà áp suất bằng 0 | Hiện chỉ ghi log ([service/mqtt.py:144](../service/mqtt.py)) | 3 | Biên | [MỘT PHẦN] | **P1** |
| A3 | Lưu lượng thấp bất thường (tắc, van kẹt) | So lưu lượng với lệnh | 1–2 | Biên + ứng dụng | [CHƯA] | **P1** |
| A4 | Lệnh không được xác nhận | **Đã có nền [MỘT PHẦN]:** `pages/plc.py` theo dõi `plc_pending_cmds` (mốc thời gian + `target_val`, hết hạn 10 giây) và `pages/inverter.py` theo dõi `inv_pending_cmd`; giao diện đã có trạng thái lệch (`pump-row-card-mismatch`, `toggle-mismatch`). Lệnh PLC cũng đã có vết APM `smiot.plc.command`. Thiếu: **metric Datadog** và đo độ trễ lệnh–xác nhận | 1–2 | Ứng dụng | [MỘT PHẦN] | P1 (mở rộng cái đã có, đừng làm mới) |
| A5 | **Quạt hoặc thông gió kẹt** (lệnh mở nhưng nhiệt độ không giảm) | Lệnh mở + nhiệt độ tiếp tục tăng sau N phút | 2–3 | Ứng dụng | [MỘT PHẦN] có scenario kẹt và metric feedback; chưa có detector phối hợp nhiệt độ theo thời gian | P2 |
| A6 | **Lưới che không phản hồi** | Lệnh so với trạng thái báo về | 1–2 | Ứng dụng | [CHƯA] | P3 |
| A7 | Cạn bồn | Cảm biến mực (ảo) | 2 | Biên | [CHƯA] | P3 |

### H. Hạ tầng phần mềm

| ID | Lỗi | Phát hiện | Bậc | Nơi | Hiện trạng | Ưu tiên |
|---|---|---|---|---|---|---|
| H1 | `smiot.service` dừng | Probe ngoài; monitor hiện tại 342585838 “SMIOT | smiot.service inactive” | 3 (start có guard) | Workflow `373ed0c0-4509-4fcd-a067-f54f0becc00e` “SMIOT | Guarded EC2 app recovery” | [CÓ] đã xuất bản/nối monitor; DryRun SSM thành công và skip khi app active. Chưa chứng minh nhánh start bằng outage thật | cần bằng chứng |
| H2 | MongoDB hoặc MQTT chết | Monitor hiện tại `342585827` (MongoDB) và `342585828` (MQTT) | 1 | Datadog | [MỘT PHẦN] monitor hiện diện; chưa có hành động phục hồi riêng được chứng minh | P3 |
| H3 | Mất kết nối đồng loạt (nguyên nhân chung) | Gom theo đồ thị phụ thuộc (mục 8.3) | 1 | Datadog + ứng dụng | [CHƯA] | P3 |
| H4 | Bộ phát hiện ngừng chạy (im lặng giả là an toàn) | Nhịp tim bộ phát hiện; monitor "no data" | 1 | Datadog | [CHƯA] | P2 |
| H5 | Đĩa đầy, thiếu tài nguyên | Metric EC2; guard kiểm đĩa | 1–2 | Datadog | [MỘT PHẦN] | thấp |
| H6 | AI lỗi hoặc quá tải | Trạng thái `provider_error` | 2 (HOLD, không tưới) | Ứng dụng | [CÓ] | đã làm |

## 7. Thang phản ứng, ca trực và leo thang

### 7.1 Thang phản ứng

| Bậc | Hành động | Điều kiện |
|---|---|---|
| 0 | Ghi nhận và bằng chứng | Luôn |
| 1 | Báo đúng người, đúng mức | Luôn |
| 2 | Giảm nhẹ an toàn (HOLD, giữ lượt an toàn, loại mẫu khỏi quyết định) | Dữ liệu mơ hồ |
| 3 | Hành động tự động | Chỉ khi hành động nằm trong danh sách cho phép, có khóa, giới hạn tần suất, kiểm điều kiện trước, và có cách xác minh |
| 4 | Leo thang con người | Khi bậc 3 bị từ chối, không thành công, hoặc quá thời gian chờ |

Mọi hành động bậc 2 trở lên phải ghi vào sổ hành động, gắn `incident_id`, và xác minh bằng dữ liệu đọc lại.

### 7.2 Ca trực và leo thang (mục mới)

Bản 0.2 có bậc 4 nhưng không có cơ chế. Thêm:

- **Lịch trực** (`on_call_shifts`): ai trực khoảng nào. Mọi `finding` mức cao được gán cho người đang trực.
- **Đồng hồ leo thang theo mức độ:** mỗi mức có thời gian chờ xác nhận; hết thời gian mà chưa ai xác nhận thì leo lên người tiếp theo. Thời gian cụ thể do nhóm đặt và ghi vào cấu hình, không cứng trong mã.
- **Xác nhận và tạm hoãn** có lý do và thời hạn; tạm hoãn hết hạn thì cảnh báo quay lại.
- **Bàn giao ca** (`shift_handover`): ghi chú cuối ca, việc còn mở, việc đang chờ phụ tùng.
- **Chỉ số chất lượng trực:** số việc mở quá thời gian chờ, số lần leo thang, số cảnh báo trên mỗi nhà màng mỗi ngày (đo độ ồn).

### 7.3 Bốn loại hành động tự động

Bản trước hiểu "tự động" quá hẹp, chỉ tính việc cắt, nên kết luận sai rằng một nửa ma trận chỉ báo được. Tự động **không phải là sửa phần cứng**, mà là giữ cây an toàn và dữ liệu trung thực mà không chờ người. Bốn loại:

| Loại | Nghĩa | Ví dụ |
|---|---|---|
| **Cắt** | Dừng thứ đang gây hại | Tràn nước, bơm mất áp, cạn bồn |
| **Chuyển** | Dùng đường dự phòng, chạy tiếp ở mức tin cậy thấp hơn | Nút 2 đứng số thì quyết định tưới dùng nút 1, đánh dấu suy giảm |
| **Bù** | Đổi điều kiện để kéo về dải mục tiêu | Mở thông gió khi VPD cao hoặc quá nhiệt; tăng tỷ lệ thoát để rửa muối; đổi lượt tưới |
| **Chứng minh** | Đọc lại dữ liệu để xác nhận đã về bình thường | Áp cho cả ba loại trên, theo nguyên tắc số 7 |

Loại **Chuyển** là thứ còn thiếu rõ nhất trong mã hiện tại: khi một nút hỏng, hệ thống HOLD toàn bộ thay vì chạy tiếp ở mức suy giảm.

### 7.4 Mười workflow nghiệp vụ phủ 36 dòng ma trận

Nhóm theo **mẫu phản ứng**, không theo loại lỗi. Mỗi dòng ma trận thuộc đúng một workflow. Bảng gồm 10 workflow nghiệp vụ (#1–#10); #0 là bộ điều phối dùng chung, nằm ngoài con số 10. Mục #8 có hai nhánh xử lý (8a VPD/EC, 8b thụ phấn/bệnh), không phải hai workflow nghiệp vụ bổ sung.

| # | Workflow | Phủ dòng | Phản ứng | Trạng thái |
|---|---|---|---|---|
| 0 | **Điều phối findings** | phễu chung | Một monitor trên `smiot.findings.open`, đọc `code` rồi rẽ nhánh. Mọi lỗi mới đi qua đây, không đẻ thêm monitor | [CHƯA] — W11 |
| 1 | **An toàn tức thời ở biên** | A1, A2, A7, C3 | **Cắt** tại PLC trong vài giây; workflow chỉ ghi `action_ledger`, mở sự cố, đính bằng chứng lưu lượng | [MỘT PHẦN] biên xong, thiếu phần ghi nhận |
| 2 | **Chất lượng dữ liệu** | S1–S6, D6 | **Chuyển** sang nút anh em, HOLD tưới, tự gỡ sau khi mẫu mới đạt | [MỘT PHẦN] có cho S1; thiếu failover |
| 3 | **Khôi phục dịch vụ** | H1, H2, H5 | **Cắt và bật lại** có điều kiện chặn; đĩa đầy thì tự xoay log | [MỘT PHẦN] W3 đã published, monitor nối và lượt d8cca009 đã xác minh `already_healthy`, đồng thời ghi chuông app; chưa diễn tập nhánh start khi dịch vụ dừng. H2/H5 còn thiếu. |
| 4 | **Từ chối hành động sai** | D2 | Tự quyết **không làm gì**, ghi `REFUSED_RESTART` kèm lý do | [MỘT PHẦN] Ca 1 đã publish/nối monitor; manual run mới đi nhánh escalation, chưa chứng minh `REFUSED_RESTART` hoặc trigger tự động |
| 5 | **Phân loại gốc rễ** | D1, D3, D4, D5, D7, H3 | **Chuyển**: đánh dấu nút suy giảm, loại khỏi quyết định, gom nhiều triệu chứng thành một sự cố gốc | [CHƯA] |
| 6 | **Nhịp tim bộ phát hiện** | H4 | Tự khởi động lại bộ phát hiện đã chết | [CHƯA] |
| 7 | **Điều chỉnh lượt tưới** | C1, C4, C5, C9, C10 | **Bù**: tính lại nhu cầu, đổi lượt kế tiếp, ghi lý do và `envelope_version` | [CHƯA] |
| 8a | **VPD và EC ngoài dải** | C2, C6 | **Bù**: mở thông gió; tăng tỷ lệ thoát để rửa muối | [CHƯA] |
| 8b | **Thụ phấn, nguy cơ bệnh** | C7, C8 | **Chỉ báo** — xem ranh giới bên dưới | [CHƯA] |
| 9 | **Chấp hành không phản hồi** | A3, A4, A5, A6 | Tự gửi lại lệnh một lần, vẫn lệch thì **chuyển** sang chế độ an toàn | [CHƯA] |
| 10 | **AI không khả dụng** | H6 | Tự HOLD, không đoán | [MỘT PHẦN] app có failsafe HOLD; monitor AI hiện NO DATA, chưa có bằng chứng Datadog workflow tự động |

**Mục tiêu thiết kế: 34 trên 36 dòng tự động đủ cả ba bước** (phát hiện, điều tra, phản ứng). Đây là độ phủ mục tiêu của thiết kế, không phải trạng thái đã triển khai; trạng thái thực được ghi ở cột cuối và đối chiếu tại mục 23.

**Ranh giới: hai dòng dừng ở con người, và đó là đúng.**
- **C7 trượt cửa sổ thụ phấn** — hành động là thụ phấn tay hoặc thả ong; không có cơ cấu nào để phần mềm điều khiển.
- **C8 nguy cơ bệnh** — hành động là phun thuốc; tự động phun theo mô hình chưa hiệu chuẩn là sai và nguy hiểm.

Với hai dòng này hệ thống vẫn tự động phát hiện và điều tra, rồi **tự chuẩn bị phiếu việc**: lô nào, từ lúc nào, bao nhiêu giờ ngoài dải, bằng chứng kèm theo. Người chỉ xác nhận đã làm.

Câu nói đúng cho hồ sơ: **tự động dừng tới nơi cần bàn tay chạm vào cây** — không tuyên bố tự động hoàn toàn.

## 8. Động cơ kịch bản và lớp phát hiện

### 8.1 Động cơ kịch bản

**Đính chính: nền đã có, không phải xây từ đầu.** Hiện trạng [CÓ]:

- `service/demo_mode.py` chạy bộ phát dữ liệu ảo cho 10 nhà màng; chu kỳ từng loại thiết bị cấu hình riêng, seed lịch sử theo giờ, và có PLC ảo hai chiều.
- **Kênh gieo lỗi đã có:** `farm/demo/control`/`farm/demo/status` hỗ trợ điều khiển legacy Node 2/UI và START/STOP sáu scenario hiện hành.
- **Xác minh vòng kín đã có:** `scripts/set_demo_sensor_fault.py` sau khi gửi lệnh còn chờ mẫu kế tiếp và kiểm giá trị đúng bằng 2,4% mới báo thành công; thất bại thì báo lỗi rõ ràng.
- Bản tin đã mang `boot_id`, `sample_sequence`, `uptime_seconds`, `measured_at`.

**Cập nhật 09/11 — phần lớn đã làm xong [CÓ]:**
- **Bộ ban đầu có sáu loại; hiện danh mục mã đã mở rộng thành 36** (mục 24). Mỗi lượt có hạt giống, phạm vi farm, ACK áp dụng và dừng; sự kiện trip/ACK chỉ nối với incident khi khớp `scenario_run_id` + farm. Backend cho chạy đồng thời trên tài nguyên độc lập và từ chối lượt xung đột; giao diện hiện còn chọn/hiển thị một lượt tại một thời điểm. Dừng scenario không xác nhận phục hồi. Dữ liệu vẫn là synthetic; `pipe_leak` không chứng minh hỏng đường ống vật lý.
- **Nhãn sự thật đã có:** `service/scenario_evidence.py` ghi `scenario_runs` và `scenario_run_events`, idempotent, có `tests/test_scenario_evidence.py`. Docstring ghi rõ nhãn kịch bản **chỉ nằm trên đường lệnh và xác nhận, không bao giờ chép vào telemetry cảm biến** — đúng yêu cầu không rò nhãn. Liên kết sự cố chỉ được ghi khi phạm vi và thời gian đều khớp.
- `scripts/demo_scenario.py` chạy kịch bản và chờ xác minh theo `scenario_run_id`.

**Việc còn phải làm:**
- Loại lỗi cho **mưa** và **trôi dần** chưa có.
- Các loại scenario mới hiện có mapping incident và xuất hiện trong hộp đen khi quan hệ run/farm/thời gian khớp. Tuy nhiên không tự CLEAR khi scenario dừng: trạng thái chuyển sang recovering; cần số đo phục hồi và xác nhận riêng. Chưa có monitor/workflow Datadog áp dụng từ xa.
- Chưa chạy lặp nhiều lần để tính độ chính xác và độ phủ (mục 11.4).

### 8.2 Lớp phát hiện thống nhất (`findings`)
Mọi bộ phát hiện xuất ra cùng một cấu trúc:

```
{farm_key, lot_id?, node_id?, group: "C|S|D|A|H", code: "C2", severity,
 confidence, evidence: {...}, envelope_version?, detected_at,
 scenario_run_id?, status: "open|acked|snoozed|closed", assignee?}
```

- Một collection `findings`; mọi màn hình và mọi hành động đọc từ đây, thay vì mỗi nơi tự suy luận.
- `envelope_version` ghi dải mục tiêu nào đã dùng để kết luận — điều tra sau này tái lập được.
- `$setWindowFields` tính trung bình trượt và độ lệch trong DB; gộp trùng theo `(farm_key, node_id, code)` trong một cửa sổ để chống rung.

### 8.3 Đồ thị phụ thuộc (gốc rễ thay vì triệu chứng)
- Topology `nhà màng → lô → nút → cảm biến → cổng → broker → ứng dụng → MongoDB` trong một collection nhỏ.
- `$graphLookup` để khi một cổng hoặc broker chết, hệ thống kết luận đây là gốc rễ và **ẩn** cảnh báo con cùng nhánh (H3), thay vì báo hàng chục cảnh báo rời.
- Cũng dùng để tính phạm vi ảnh hưởng: một cảm biến lỗi ảnh hưởng lô nào.

### 8.4 Giám sát chính hệ thống giám sát
- Mỗi bộ phát hiện có nhịp tim; bộ nào ngừng chạy thì monitor "no data" báo (H4).
- Đo độ trễ từ lúc có dữ liệu đến lúc có `finding` tương ứng.

### 8.5 Danh mục kịch bản vận hành đầy đủ

Đây là **thiết kế cho toàn bộ 36 mã lỗi trong ma trận**, không phải tuyên bố đã cài đủ. Cột cuối phản ánh mã hiện tại: **Có** = luồng chính đã có; **Một phần** = có nền nhưng thiếu phát hiện, bằng chứng hoặc phục hồi; **Thiết kế** = chưa có luồng thực thi. Ngưỡng không có nguồn hiệu chuẩn phải để ở cấu hình/chờ xác nhận; không tự bịa con số. Với mọi sự cố, timestamp đo, timestamp nhận, farm, thiết bị và mã lượt phải được giữ riêng.

#### Cây trồng và khí hậu

| Mã | Kịch bản và tín hiệu kích hoạt | Phản ứng đầu tiên | Điều kiện đóng sau phục hồi | Hiện trạng |
|---|---|---|---|---|
| C1 | Độ ẩm đất nằm ngoài dải của giai đoạn đã duyệt; thiếu dải thì kết quả là UNKNOWN | Không tăng/giảm lịch tưới theo phỏng đoán; giữ chế độ an toàn và báo người trồng | Mẫu mới hợp lệ nằm trong dải đã duyệt liên tiếp đủ cửa sổ; ghi `envelope_version` | Một phần: có cổng chặn khi thiếu envelope; chưa có bộ phát hiện đầy đủ và envelope hiệu chuẩn |
| C2 | VPD tính từ nhiệt độ/độ ẩm vượt dải của giai đoạn | Cảnh báo; nếu đầu vào không tin cậy thì không dùng VPD để điều khiển | Cảm biến đầu vào khỏe và VPD trở lại dải đã duyệt qua cửa sổ ổn định | Một phần: tính/metric VPD có; chưa có dải VPD được duyệt |
| C3 | Nhiệt độ tăng nhanh hoặc vượt dải kéo dài vào thời điểm nóng | Bộ điều khiển tại chỗ mở thông gió nếu trạng thái phản hồi cho phép; Datadog chỉ quan sát và báo | Nhiệt độ hạ dưới ngưỡng hồi có hysteresis, quạt xác nhận chạy; nếu không thì giao người trực | Thiết kế; chưa có luật nhiệt/đóng vòng |
| C4 | Nước thoát nhiều hoặc đất vẫn ướt sau các lượt tưới | Tạm giữ lượt tăng thêm; kiểm tra thoát nước và cảm biến | Độ ẩm/thoát nước trở lại vùng bình thường, người vận hành xác nhận không úng | Thiết kế; chưa có đo cân bằng thoát nước |
| C5 | Cân bằng nước tích lũy âm trong giai đoạn quả lớn | Báo thiếu nước; chỉ cho phép tưới theo lịch đã duyệt và dữ liệu đáng tin | Lượng cấp/thoát và độ ẩm xác nhận đã phục hồi; lưu lượng lệnh khớp phản hồi | Thiết kế; chưa có cân bằng nước theo lô |
| C6 | EC nước thoát tăng dai dẳng so với EC nước cấp | Cảnh báo kiểm tra pha dinh dưỡng; không tự đổi công thức | Nhiều mẫu cấp/thoát hợp lệ cho thấy chênh lệch đã về dải được chuyên gia duyệt | Thiết kế; chưa có EC nước thoát trong chuỗi vận hành |
| C7 | Lô đi qua cửa sổ thụ phấn đã cấu hình mà thiếu sự kiện xác nhận | Nhắc người trồng kiểm tra/ghi nhận; không tự suy đoán ngày thụ phấn | Sự kiện được người có quyền xác nhận hoặc cửa sổ được cập nhật có dấu vết | Thiết kế; không tự chữa được sự kiện nông học đã bỏ lỡ |
| C8 | Độ ẩm cao/VPD thấp kéo dài qua khoảng thời gian cấu hình | Tạo cảnh báo nguy cơ và yêu cầu kiểm tra cây; không kết luận cây đã nhiễm bệnh | Điều kiện khí hậu ổn định và người vận hành xác nhận kiểm tra | Thiết kế; chưa có mô hình bệnh đã hiệu chuẩn |
| C9 | Mưa đo được làm giảm nhu cầu tưới | Giảm lượt tưới tương lai có thể hủy an toàn; không đảo lệnh đang chạy chỉ dựa trên dự báo | Đo mưa và độ ẩm đất mới nhất nhất quán; lưu lý do thay lịch | Thiết kế; chưa lưu lượng mưa vào Mongo |
| C10 | **Nghi rò ống** khi bơm chạy, lưu lượng cao và áp suất thấp; **nghi rò mái** khi mưa/ẩm tăng lúc bơm tắt | Safe-stop tại PLC cho tín hiệu áp thấp + flow cao; ghi nhận chưa đủ căn cứ nếu thiếu mưa hoặc cảm biến | Chỉ kết thúc nhánh an toàn khi áp/lưu lượng ổn định; chẩn đoán rò thật cần kiểm tra hiện trường | Một phần: chỉ có kịch bản synthetic áp thấp + flow cao; chưa phân biệt mái/ống bằng dữ liệu thời tiết |

#### Cảm biến

| Mã | Kịch bản và tín hiệu kích hoạt | Phản ứng đầu tiên | Điều kiện đóng sau phục hồi | Hiện trạng |
|---|---|---|---|---|
| S1 | 10 mẫu gần như không đổi trong 600 giây theo luật hiện có | Đánh dấu số đo không tin cậy, HOLD quyết định phụ thuộc cảm biến | Nhiều mẫu mới dao động hợp lý và verifier xác nhận; không chỉ dựa vào lệnh reset | Có: Ca Node 2 |
| S2 | Một bước nhảy vượt tốc độ thay đổi vật lý đã cấu hình | Cách ly mẫu bất thường khỏi quyết định tưới; giữ mẫu gốc để điều tra | Các mẫu sau hợp lệ và không còn spike qua cửa sổ xác nhận | Một phần: finding có tương quan scenario; chưa đo độ chính xác/báo nhầm |
| S3 | Giá trị ngoài miền vật lý của loại cảm biến | Không dùng mẫu đó để điều khiển; kiểm tra đơn vị, thiết bị và nguồn gửi | Mẫu mới trong miền hợp lệ liên tiếp; nếu cần thì người vận hành xác nhận hiệu chuẩn | Một phần: finding ngoài miền có trong code; chưa diễn tập đầy đủ |
| S4 | Giá trị lệch dần khỏi đường cơ sở và các cảm biến cùng loại | Báo nghi drift, không tự chỉnh offset | So chuẩn/hiệu chuẩn xác nhận hoặc nhiều node đồng thuận trở lại | Thiết kế; không có chuẩn tham chiếu/đủ lịch sử |
| S5 | Hai node cùng khu đo chênh nhau vượt dải cấu hình | Không lấy trung bình để che bất đồng; đánh dấu vùng đo chưa chắc | Cảm biến được đối chiếu và sai lệch được giải thích | Thiết kế; chưa có lớp so sánh node |
| S6 | Phương sai/tần suất dao động tăng bất thường | Loại quyết định tự động nhạy với tín hiệu; báo kiểm tra dây/nguồn/cảm biến | Nhiễu giảm và mẫu mới ổn định qua cửa sổ | Thiết kế; chưa có bộ phát hiện nhiễu |

#### Thiết bị và mạng

| Mã | Kịch bản và tín hiệu kích hoạt | Phản ứng đầu tiên | Điều kiện đóng sau phục hồi | Hiện trạng |
|---|---|---|---|---|
| D1 | Tuổi mẫu vượt giới hạn hoặc không còn dữ liệu mới | Đánh dấu stale; không dùng dữ liệu cũ để tưới; Datadog cảnh báo đường dữ liệu | Nguồn gửi mẫu mới, Mongo đọc lại thấy mẫu mới và monitor hồi phục | Có: monitor stale hiện hữu; nguồn cụ thể cần điều tra |
| D2 | Giao diện báo offline nhưng Mongo vẫn nhận mẫu mới | Không restart thiết bị; JSON workflow ghi lý do từ chối restart | Cache/UI đọc lại trạng thái online từ mẫu mới; log chứng minh restart không xảy ra | Một phần: monitor `342585836` đã nối tới Ca 1 đã published; manual run đi nhánh escalation, chưa nhánh `REFUSED_RESTART`; draft cũ `a9e36b20-6ac5-4553-ba20-0d6fae58e6f4` còn tồn tại |
| D3 | `boot_id` đổi hoặc uptime giảm/đặt lại | Ghi nhận reboot, phân biệt với mất dữ liệu; kiểm tra các mẫu sau boot | Thiết bị gửi chuỗi mẫu mới liên tục; không coi reboot đơn lẻ là lỗi chưa phục hồi | Một phần: metric/cờ có trong code; chưa xác minh Datadog ingest và reboot qua restart app |
| D4 | Sequence nhảy, trùng hoặc lùi | Giữ bản gốc, đếm khoảng thiếu/trùng; loại bản tin lặp khỏi cập nhật trạng thái nếu cùng sequence | Sequence mới tăng hợp lệ và khoảng thiếu được xác định hoặc giữ là chưa rõ | Một phần: provenance/metric có; chưa xác minh runtime trên Datadog |
| D5 | Tốc độ bản tin giảm dưới cadence dự kiến theo từng loại thiết bị | Cảnh báo chất lượng luồng; kiểm tra publisher, broker và consumer theo thứ tự | Cadence khôi phục và mẫu tới Mongo đều; không suy ra nguyên nhân từ một metric | Thiết kế; chưa có monitor rate riêng |
| D6 | ID thiết bị không có trong registry hoặc gửi sai farm | Cách ly khỏi điều khiển; không tự gán `greenhouse_a`; ghi thiết bị chưa xác định | Chủ thiết bị đăng ký farm/loại hợp lệ và gửi bản tin mới đúng phạm vi | Thiết kế; chưa có registry thiết bị thật |
| D7 | Pin thấp, RSSI yếu hoặc điện áp ngoài dải do thiết bị gửi | Cảnh báo bảo trì, ưu tiên thay nguồn/kiểm tra sóng; không gửi lệnh reset mù | Đo pin/sóng/điện áp mới ổn định sau xử lý | Thiết kế; thiết bị hiện chưa phát đủ các trường này |

#### Cơ cấu chấp hành

| Mã | Kịch bản và tín hiệu kích hoạt | Phản ứng đầu tiên | Điều kiện đóng sau phục hồi | Hiện trạng |
|---|---|---|---|---|
| A1 | Thể tích/thời gian vượt giới hạn hoặc flow cao bất thường trong lúc tưới | Interlock tại chỗ dừng bơm, đóng van, latch safe mode; phát ACK và lưu số đo | Kiểm tra lưu lượng/áp suất ổn định; người vận hành xác nhận đường nước an toàn trước khi mở lại | Một phần: giới hạn runtime/volume và scenario synthetic có; không phải PLC vật lý, chưa so target tưới hiệu chuẩn |
| A2 | Bơm được xác nhận chạy nhưng áp suất bằng 0 | Dừng bơm tại biên, khóa bật lại, báo kiểm tra nguồn nước/ống/cảm biến áp | Áp suất dương và flow phản hồi phù hợp trong thử chạy có kiểm soát | Một phần: có log/metrics và safe-stop mô phỏng; chưa xác nhận đầu dò áp thật |
| A3 | Bơm bật nhưng lưu lượng thấp hơn mức tối thiểu sau grace period | Dừng hoặc giữ bơm theo interlock; không lặp bật/tắt; khoanh vùng van/tắc | Lệnh, flow và áp suất khớp trong lần chạy kiểm soát | Thiết kế; chưa có detector so lệnh-flow tổng quát |
| A4 | Không thấy ACK hoặc feedback không khớp lệnh trong timeout cấu hình | Đánh dấu command chưa xác nhận; không gửi lặp lệnh bật nguy hiểm | ACK có cùng `command_id`, state đọc lại khớp target | Một phần: UI/APM pending command có; metric và đo end-to-end còn thiếu |
| A5 | Quạt nhận lệnh chạy nhưng RPM/feedback không đổi hoặc nhiệt tiếp tục tăng | Nếu có nguy cơ nhiệt, local rule mở vùng thông gió dự phòng; báo người trực | Feedback quạt hợp lệ và nhiệt giảm; chỉ đóng finding quạt, không tự đóng finding nhiệt khác | Một phần: có scenario quạt kẹt; chưa có detector kết hợp nhiệt + feedback |
| A6 | Lưới che nhận lệnh nhưng trạng thái không đổi/không ACK | Dừng lệnh đối nghịch, giữ trạng thái hiện biết và báo người vận hành | Feedback vị trí mới khớp lệnh và được đọc lại | Thiết kế; chưa có thiết bị ảo/feedback đầy đủ |
| A7 | Mực bồn dưới mức tối thiểu | Chặn bơm có nguy cơ chạy khô; báo bổ sung nước | Mực bồn mới vượt ngưỡng hồi đã cấu hình và cảm biến hợp lệ | Thiết kế; chưa có cảm biến mực bồn |

#### Hạ tầng phần mềm

| Mã | Kịch bản và tín hiệu kích hoạt | Phản ứng đầu tiên | Điều kiện đóng sau phục hồi | Hiện trạng |
|---|---|---|---|---|
| H1 | `smiot.service` dừng trong khi Mongo/MQTT còn khỏe | Probe ngoài mở incident; current monitor `342585838` trigger workflow `373ed0c0-4509-4fcd-a067-f54f0becc00e` | HTTP/healthz, Mongo/MQTT và telemetry mới đều xác nhận; không đóng chỉ vì process active | Workflow live/monitor-linked; DryRun SSM thành công và skip khi app active; outage thật chưa diễn tập để chứng minh nhánh start |
| H2 | MongoDB hoặc MQTT không khỏe | Cảnh báo; app chuyển sang safe mode, không nhận lệnh tưới dựa trên dữ liệu không bền | Health check thành công và ghi/đọc thử dữ liệu an toàn; không restart cả EC2 nếu chỉ một dependency lỗi | Một phần: monitor có, workflow/guard phục hồi riêng chưa đủ |
| H3 | Nhiều farm/device mất cùng lúc do gateway/broker chung | Tạo một finding gốc ở dependency; liên kết symptom con thay vì gửi hàng loạt hành động | Dependency gốc khỏe và từng nhánh con có dữ liệu mới; đóng riêng symptom đã xác minh | Thiết kế; topology/correlation chưa có |
| H4 | Watchdog hoặc bộ phát hiện không còn heartbeat | Cảnh báo “không biết trạng thái”, không coi im lặng là bình thường; dùng probe ngoài nếu có | Heartbeat mới và kiểm tra detector xử lý được một tín hiệu tổng hợp an toàn | Thiết kế; chưa có heartbeat monitor |
| H5 | Đĩa đầy/CPU/RAM thiếu làm app hoặc DB suy giảm | Cảnh báo sớm; tránh restart nếu chưa xác định áp lực; dọn chỉ dữ liệu được phép hoặc tăng tài nguyên có duyệt | Disk/CPU/RAM trở về dải, service và dữ liệu mới xác nhận khỏe | Một phần: EC2 metrics có; guard dung lượng và playbook đầy đủ chưa |
| H6 | AI provider lỗi, timeout hoặc trả kết quả không hợp lệ | Bỏ quyết định AI; app áp dụng HOLD/luật an toàn xác định và ghi `provider_error` | Provider trả kết quả hợp lệ, kiểm tra schema thành công; không tự chạy lại hành động cũ | Có: trạng thái lỗi/HOLD có; cần tiếp tục đối chiếu AI Observability runtime |

### 8.6 Khi nhiều lỗi xảy ra hoặc tự hết cùng lúc

**Không gộp mọi lỗi thành một incident, và không đóng tất cả chỉ vì dashboard chuyển xanh.** Hệ thống giữ từng finding/incident riêng, đồng thời chỉ tạo một nhóm nguyên nhân chung khi có quan hệ dependency được chứng minh.

1. **Ghi nhận độc lập:** mỗi finding có khóa chống trùng dựa trên farm, component, mã lỗi và cửa sổ bắt đầu; mỗi hành động có `command_id`; mỗi scenario mô phỏng có `scenario_run_id`. Giữ cả thời điểm đo và thời điểm nhận để xử lý bản tin tới muộn.
2. **Tách nguyên nhân chung khỏi lỗi độc lập:** nếu broker/gateway ngừng và nhiều cảm biến cùng stale, một incident gốc liên kết các symptom con. Nếu đồng thời có rò nước và cảm biến đất lỗi, giữ hai incident riêng nhưng hiển thị cạnh nhau trên cùng farm. Không suy ra quan hệ chỉ vì xảy ra gần thời gian.
3. **Ưu tiên an toàn trước:** interlock tại chỗ được thực thi ngay và idempotent. Các action cùng tác động một bơm/van dùng khóa tài nguyên; safe-stop được phép ưu tiên, còn lệnh mở/bật/restart đối nghịch bị chặn cho tới khi trạng thái được đọc lại. Workflow Datadog không nằm trên đường ngắt khẩn cấp.
4. **Lỗi tự hết cũng cần bằng chứng:** một transient spike có thể tự đóng sau hysteresis và đủ mẫu hợp lệ nếu chưa tạo hành động vật lý. Một safety-trip, mất áp, hoặc hành động đã tác động thiết bị không tự `CLEAR` khi giá trị vừa bình thường; cần mẫu mới, ACK/feedback cùng command/run, và bước duyệt phù hợp.
5. **Phục hồi từng lỗi:** trạng thái mỗi finding chạy `open → acknowledged/mitigating → verifying → resolved`. Khi một tín hiệu hồi phục, chỉ finding đó chuyển sang verifying. Incident gốc chỉ đóng khi dependency gốc khỏe và tất cả symptom liên quan đã được xác minh; symptom chưa hồi phục vẫn mở.
6. **Tránh bão cảnh báo:** gộp notification theo incident gốc và cửa sổ ngắn, nhưng không xóa event hoặc finding riêng; giới hạn tần suất workflow và chỉ chạy một action cho cùng resource. Nếu mất MongoDB, giữ an toàn tại PLC, phát log/metric nếu đường gửi còn hoạt động, rồi reconcile event theo ID khi DB trở lại.
7. **Khi hai lỗi cùng hết:** bộ kiểm tra xử lý từng `finding_id` riêng, ghi `resolved_at` và bằng chứng khác nhau. Nếu có lỗi cha–con, khôi phục cha không tự xóa con; cần kiểm tra từng thiết bị đã gửi mẫu mới. Nếu chỉ có một tín hiệu chung cho cả hai, giữ cả hai ở `verifying` cho đến khi có phép đo phân biệt.

**Ví dụ trình diễn nhiều lỗi:** cùng lúc cảm biến đất phát spike, đường nước có áp thấp/flow cao, và broker chập chờn. PLC ảo dừng bơm trước; app tạo evidence trip cho đúng `scenario_run_id`; S2 tạo finding riêng và không dùng mẫu spike để tưới; D1/H3 chỉ nhóm các node stale nếu cùng gateway/broker được xác nhận là nguyên nhân. Khi broker ổn lại, chỉ finding stale được verify; pipe safety vẫn giữ latch cho tới khi kiểm tra nước, còn sensor spike cần mẫu hợp lệ riêng. Nếu các lỗi tự hết gần như đồng thời, chúng vẫn được đóng theo từng bằng chứng trên, không theo thứ tự cảnh báo hay một monitor tổng.

**Giới hạn hiện tại:** code giữ ID riêng cho nhiều lượt và chặn xung đột tài nguyên trong tiến trình mô phỏng; chưa có topology/root-cause graph hoàn chỉnh, khóa phân tán cho nhiều worker, cơ chế reconcile khi Mongo ngừng, UI điều khiển nhiều lượt cùng lúc, hay kiểm chứng race-condition nhiều lỗi thực tế. Trên hệ thống thật, cần khóa/serialize action theo thiết bị giữa nhiều worker và giữ riêng từng finding.

## 9. Mở rộng sang 10 nhà màng

**Trạng thái 09/11:** danh mục và luồng live đã mở rộng lên **10 nhà màng** (`greenhouse_a` đến `greenhouse_j`) và đã triển khai trên EC2. Gói MQTT của cả 10 farm đã được xác nhận trong cửa sổ nghe 310 giây. Phần này đã hoàn thành; các mục về sự cố riêng cho từng farm và màn hình tổng quan vẫn là phạm vi riêng, chưa được đánh dấu xong ở đây.

**Phạm vi sau khi mở rộng:** danh mục nhà màng đã tập trung ở `service/farm_registry.py`; `auth.py`, `demo_mode.py` và `telemetry_health.py` dùng danh mục 10 farm. PLC và biến tần cũng lấy farm đang chọn. Tuy vậy, Ca 2 (đứng số) vẫn được giới hạn rõ trong `service/incident_lifecycle.py` ở `greenhouse_a`/node 2 với một luồng sự cố. Monitor `342585819` đã nối tới workflow `2f9a3c1d-5292-4bc3-b4b9-cc03d4172724`; workflow đã published. Manual run `ac94d5ca-ebfd-4aea-96d0-b78314ccd5c3` (2026-11-09 17:42 UTC) hoàn tất qua nhánh escalation trong 3 giây; không gửi HOLD/CLEAR. Ca 1 và việc tổng quát hóa sự cố cho mọi farm cần được xác minh riêng.

| Trạng thái | Việc | Nội dung |
|---|---|---|
| [x] | Danh sách nhà màng | Danh mục dùng chung có 10 farm (`greenhouse_a`–`greenhouse_j`) trong `service/farm_registry.py`; bộ phát dùng danh mục này. Chưa chuyển danh mục sang collection `farms`/`provision_farm`. |
| [x] | Mô phỏng và MQTT | Một bộ phát nền trong dịch vụ ứng dụng tạo gói cho 9 loại thiết bị trên mỗi farm. Đã nghe MQTT và xác nhận đủ 10 farm; đây là thiết bị ảo trong một tiến trình, không phải 90 tiến trình độc lập. |
| [ ] | Lô | Cần đối chiếu lô từng farm và liên kết với sự cố trước khi đánh dấu hoàn tất. |
| [~] | Tải | Đã xác nhận luồng hoạt động: 1.300 gói/310 giây (~4,2 gói/giây) trong lần đo này. Chưa chạy kiểm thử tải/độ trễ, nên chưa xác nhận mức 10–30 gói/giây. |
| [ ] | Dữ liệu | Cần xác minh schema MongoDB, `farm_key`/`lot_id` trong `meta`, index và độ phủ bản ghi theo cả 10 farm. |
| [ ] | Thẻ Datadog | Chưa cập nhật hay xác minh Datadog trong đợt triển khai này. |

### 9.1 Danh mục thiết bị ảo: đã có và cần thêm

**Đã triển khai và xác minh live trên EC2 (09/11):** danh mục dưới đây gồm 9 loại thiết bị ảo cho mỗi farm. Trong cửa sổ MQTT 310 giây đã nhận 1.300 gói từ 10 farm; số gói dưới đây là số nhận được **cho mỗi thiết bị của mỗi farm** trong đúng cửa sổ đó, không phải tốc độ cố định được cam kết.

| Kênh | Thiết bị ảo | Gói nhận / farm / cửa sổ 310 giây |
|---|---|---:|
| `farm/sensor` | Node 1 | 5 |
| `farm/sensor` | Node 2 | 5 |
| `farm/sensor` | Đồng hồ lưu lượng | 5 |
| `farm/sensor` | Cảm biến EC nước | 1 |
| `farm/sensor` | Cảm biến pH nước | 1 |
| `farm/sensor` | Đồng hồ thoát nước | 1 |
| `farm/sensor` | Thông gió | 20 |
| `farm/status` | PLC ảo, gồm 8 kênh đầu ra bơm `q0`–`q7`/`bit0`–`bit7` | 61 |
| `farm/data` | Biến tần ảo | 31 |

Gói node còn có `boot_id`, `sample_sequence`, `uptime_seconds`. Gói PLC có trạng thái an toàn và trạng thái thông gió; lệnh điều khiển được xử lý qua MQTT.

**Chưa tách thành tiến trình riêng:** một bộ phát nền trong ứng dụng tạo các gói cho mọi thiết bị. Nếu dịch vụ ứng dụng dừng, bộ phát cũng dừng. Wokwi không phải nguồn phát liên tục đang chạy trên EC2.

**Các hạng mục thiết bị đã bổ sung và các phần mở rộng còn lại:**

| Trạng thái | Thiết bị / khả năng | Ghi chú |
|---|---|---|---|
| [x] | Cảm biến nước thoát | Có định danh `drain` và đã thấy gói MQTT từ đủ 10 farm. Chưa xác minh riêng trường đo và số liệu đã lưu trong MongoDB. |
| [x] | Thông gió / quạt | Có thiết bị ảo, PLC phát trạng thái và đã thấy gói của đủ 10 farm. Chưa diễn tập lỗi kẹt quạt. |
| [ ] | Cảm biến mực bồn | Chưa triển khai/xác minh (`tank_level_pct`). |
| [ ] | Máy đo mưa tại chỗ | Chưa triển khai/xác minh (`rain_mm`). |
| [ ] | Cảm biến sáng / PAR | Chưa triển khai; DLI có thể dùng dữ liệu thời tiết hiện có nếu được xác minh. |
| [ ] | Lưới che có phản hồi | Chưa triển khai/xác minh (`screen_cmd`, `screen_state`). |

Việc thiết bị đã gửi gói **không đồng nghĩa** các gói việc W3/W5/C3 (phân tích cân bằng nước, khóa liên động hoặc phát hiện lỗi) đã hoàn thành. Chỉ các thiết bị/gói MQTT ở bảng trên được đánh dấu x; các chức năng vận hành cần tiêu chí và bằng chứng riêng.

Mọi thiết bị ảo thêm vào phải giữ đúng khuôn đã có: gắn `synthetic: True`, có `timestamp` và `measured_at`, và nhận lệnh qua `farm/demo/control` với xác nhận trên `farm/demo/status`.

---

# PHẦN III — THIẾT KẾ TÍNH NĂNG

## 10. Danh mục tính năng theo vai trò

| Vai trò | Tính năng cần | Hiện trạng |
|---|---|---|
| **Người trồng** | Đèn xanh/vàng/đỏ cho từng nhà màng kèm một câu giải thích; thông báo khi cần hành động; lịch tưới và lý do | [CHƯA] |
| **Kỹ thuật viên** | Trang nhà màng theo tầng; `findings` kèm bằng chứng; chẩn đoán tầng lỗi (thiết bị / mạng / cloud) để biết có cần ra hiện trường; nhật ký hiệu chuẩn | [MỘT PHẦN] |
| **Kỹ sư nông học** | Xem và sửa `stage_envelopes` có phiên bản; xem số giờ ngoài dải theo lô và giai đoạn; cân bằng nước | [CHƯA] |
| **Vận hành / trực** | Tổng quan 10 nhà màng; hàng đợi việc theo mức độ; xác nhận, tạm hoãn, leo thang; bàn giao ca | [CHƯA] |
| **Quản trị** | Hộp đen sự cố 6 câu; sổ hành động; phân quyền; nhật ký kiểm toán | [CÓ: `/incident`, phân quyền] |
| **Người mua / kiểm định** | Liên kết chỉ đọc chứng minh nhật ký canh tác và dữ liệu đáng tin theo lô | [MỘT PHẦN: `public_share_token`] |

## 11. Đo lường và tiêu chí "xong"

### 11.1 Lớp đo tác động đã có, và chặt hơn bản thiết kế này

**Đính chính bản 0.5.** `service/incident_blackbox.py` → `compute_impact()` đã trả về [CÓ]:

| Trường | Nghĩa |
|---|---|
| `detect_seconds`, `safe_seconds`, `recovery_seconds` | Từ lúc bắt đầu lỗi đến phát hiện / vào an toàn / phục hồi |
| `unreliable_seconds`, `unreliable_hours` | Thời gian dữ liệu không đáng tin |
| **`unreliable_basis`** | **Câu giải thích con số đó được tính thế nào**, khác nhau theo từng loại sự cố |
| `unreliable_ongoing` | Còn đang diễn ra hay đã kết thúc |
| `lots_to_review`, `missing_sample_gaps`, `false_restart_count` | Phạm vi tác động |

Ba chi tiết cho thấy mã đã chặt hơn bản thiết kế:

1. **`None` nghĩa là "chưa xác định", và mã ghi rõ "khong doan".** Không có giá trị mặc định 0 để lấp chỗ trống.
2. **`_gap_in_incident()`**: một khoảng thiếu mẫu xảy ra **sau** lúc phục hồi không được tính cho sự cố này, vì cửa sổ dữ liệu kéo dài thêm sau phục hồi để có mẫu đối chiếu.
3. **`extract_recovery_evidence()`** lấy các mẫu sau lệnh CLEAR và gắn cờ `differs_from_fault` — chứng minh phục hồi bằng dữ liệu đọc lại, đúng nguyên tắc số 7.

Ngoài ra `hot_queries()` sinh truy vấn `find` tương đương `$match` của từng nhánh, để `scripts/explain_before_after.py` đo explain trước và sau index. Công cụ đo đã được thiết kế vào, không phải thêm mới.

**Trạng thái sau cập nhật:** các scenario mới đã có kind/CASE và hộp đen riêng, nhưng `compute_impact` hiện mới tính thời gian dữ liệu không tin cậy đầy đủ cho ba ca cũ (flatline, service_down, false_offline). Ca safety-trip mới có mốc và bằng chứng an toàn; chưa có số liệu phục hồi sau sửa chữa hay tính tác động nước/lô đủ để gọi là phục hồi hoàn chỉnh.

### 11.2 Validator không thiếu, chỉ bị tắt bằng cờ

**Đính chính bản 0.5.** `apply_incident_validators()` đã có và viết đúng: `$jsonSchema` cho `operational_incidents` và `action_ledger`, `validationAction=warn`, `validationLevel=moderate`, và không ném lỗi khi thiếu quyền `collMod`. Lý do báo cáo chạy thật không thấy validator: **`init_db` chỉ gọi nó khi `SMIOT_APPLY_VALIDATORS=true`, mặc định là `false`** (`service/auth.py:95-96`) — điều này đã được ghi trong `docs/submission/02_kien_truc_du_lieu_mongodb.md:383`.

Nghĩa là bật validator là **đổi một biến môi trường**, không phải viết mã. Tương tự, `ensure_incident_indexes()` có cơ chế thử lại bỏ `partialFilterExpression` khi máy chủ từ chối, và báo trạng thái `ok_fallback`. Hai việc này nên đưa lên đầu lộ trình vì gần như không tốn công.

### 11.3 Bản đồ phủ kiểm thử (bản 0.7)

19 tệp test, khoảng 2.260 dòng. Phủ **tập trung vào hệ sự cố**: `test_incident_blackbox`, `incident_autolink`, `incident_metrics`, `incident_graphs`, `incident_list`, `incident_navigation`, `incident_polish`, `incident_cases`, `attach_detected_at`, `gap_scope`, `flatline_auto`, `flatline_recovery`, `node_status`, `probe_autolink`, `healthz`, `ai_failsafe`, `llmobs`, `responsive_css`, `rv1_fixes`.

**Không có test cho:** lịch tưới và bộ lập lịch · đường lệnh PLC và biến tần · lớp cây trồng (`mongodb_showcase`) · cờ nguồn gốc dữ liệu (khởi động lại, hụt gói) · gieo lỗi trong `demo_mode`.

**Hệ quả cho kế hoạch:** phần mạnh nhất của dự án (hệ sự cố) cũng là phần được bảo vệ tốt nhất, nên **sửa vào đó là rủi ro cao** — có test sẽ bắt lỗi, nhưng đó là phần trung tâm của ba ca đang dùng cho hồ sơ. Ngược lại, mọi việc mới ở mục 16 (lớp cây trồng, chấp hành, gieo lỗi có nhãn) **rơi vào vùng chưa có test**, nên phải viết test cùng lúc, không để sau.

### 11.4 Tiêu chí "xong"

Mỗi mục trước khi gọi là xong phải qua được bài kiểm sau, chạy bằng động cơ kịch bản:

| Mục | Tiêu chí đạt |
|---|---|
| A1 tràn nước | Gieo lỗi 10 lần: biên cắt bơm trong ≤ 5 giây cả 10 lần; sổ hành động có 10 bản ghi kèm bằng chứng lưu lượng; 0 lần bỏ sót |
| S2, S3 đột biến và ngoài khoảng | Gieo mỗi loại 10 lần: phát hiện đúng ≥ 9/10; số báo nhầm trên dữ liệu bình thường 24 giờ mô phỏng ≤ ngưỡng nhóm đặt |
| C1, C2 ngoài dải | Dữ liệu ra ngoài dải sinh đúng một `finding` (không rung), có `envelope_version`, và giao diện hiện dải đang dùng |
| C9, C10 mưa | Kịch bản mưa: lượt tưới giảm; nhà màng không có nguyên nhân khác **không** bị báo rò ống; nhà màng bất thường thì bị báo |
| D3–D6 thiết bị | Cờ khởi động lại và hụt gói xuất hiện trên Datadog trong ≤ 2 phút sau khi gieo |
| H3 gốc rễ | Tắt một cổng ảo: đúng một cảnh báo gốc rễ, cảnh báo con bị ẩn |
| H4 nhịp tim | Dừng một bộ phát hiện: monitor báo trong cửa sổ đã đặt |
| F2 tổng quan | Một người chưa từng dùng hệ thống nhìn màn hình trong 30 giây và nói được: nhà màng nào có vấn đề, vấn đề gì, ai đang xử lý |
| Mỗi dòng ma trận lỗi | Có đủ sáu thứ ở mục 6, hoặc ghi rõ trạng thái "chưa" |

Mục nào không qua được trước 13/11 thì ghi là hướng phát triển, **không ghi là đã có**.

---

# PHẦN IV — THIẾT KẾ GIAO DIỆN

## 12. Kiến trúc thông tin và từng màn hình

Nguyên tắc: **màn hình mặc định chia theo lô và cây**, không theo tầng kỹ thuật. Tầng kỹ thuật là màn hình thứ hai, cho kỹ thuật viên.

### 12.1 Tổng quan 10 nhà màng (màn hình chủ, ưu tiên cao nhất)

Đây là mảnh còn thiếu để gọi hệ thống là "trung tâm".

```
┌──────────────────────────────────────────────────────────────┐
│ SMIOT · 10 nhà màng      Ca trực: <tên>   3 việc mở   ⏱ 09:41│
├──────────────────────────────────────────────────────────────┤
│ ┌─ NM-01 ────────┐ ┌─ NM-02 ────────┐ ┌─ NM-03 ────────┐    │
│ │ ● Bình thường  │ │ ▲ Cần theo dõi │ │ ■ Cần xử lý    │    │
│ │ Lô A12 · nuôi  │ │ Lô A08 · tạo   │ │ Lô A15 · nuôi  │    │
│ │ quả · ngày 34  │ │ lưới · ngày 52 │ │ quả · ngày 29  │    │
│ │ ẩm ✓ VPD ✓ EC ✓│ │ VPD thấp 2,5 h │ │ Tràn nước-đã   │    │
│ │ nước: +2%      │ │ nước: −8%      │ │ cắt bơm 09:38  │    │
│ └────────────────┘ └────────────────┘ └────────────────┘    │
│                    … 7 ô còn lại …                           │
├──────────────────────────────────────────────────────────────┤
│ Việc đang mở (3)                                             │
│ ■ NM-03 A1 tràn nước · đã cắt bơm · chờ xác nhận 3 phút      │
│ ▲ NM-02 C2 VPD dưới dải 2,5 giờ · giao <tên>                 │
│ ▲ NM-07 D3 nút 2 khởi động lại 4 lần/giờ · chưa giao         │
├──────────────────────────────────────────────────────────────┤
│ Hành động tự động 24 giờ: 2 cắt bơm · 1 start service        │
│ 1 từ chối restart (đúng) · 0 thất bại                        │
└──────────────────────────────────────────────────────────────┘
```

Mỗi ô nhà màng hiện: trạng thái tổng, lô và giai đoạn, ngày trong vụ, bốn chỉ số cây (ẩm, VPD, EC, cân bằng nước), và việc đang mở nếu có. **Chế độ phòng điều khiển:** nền tối, chữ lớn, tự làm mới, dùng cho màn hình treo tường và cho buổi demo.

**Yêu cầu kỹ thuật bắt buộc (học từ `pages/schedule.py`):** phần xem theo tuần hiện gọi `get_schedules()` và `get_total_actual_water()` **bảy lần trong một vòng lặp** cho bảy ngày. Với một nhà màng thì chấp nhận được; màn hình tổng quan 10 nhà màng mà làm theo khuôn đó sẽ thành 10 nhân số truy vấn mỗi lần làm mới. Màn hình này **phải dùng một aggregation duy nhất** gom theo nhà màng, rồi dựng giao diện từ kết quả đó.

### 12.2 Trang lô (cho người trồng và kỹ sư nông học)

- Dòng thời gian vụ: ngày trong vụ, giai đoạn, GDD tích lũy, dự kiến thu hoạch.
- Bốn biểu đồ chỉ số cây, **mỗi biểu đồ vẽ dải mục tiêu làm vùng nền** và ghi phiên bản dải đang dùng.
- Dải tô màu cho khoảng dữ liệu không đáng tin, lấy từ điểm chất lượng.
- Cân bằng nước: kế hoạch, đã cấp, đã thoát, tích lũy.
- Ảnh theo giai đoạn (đã có trong truy xuất).

### 12.3 Trang nhà màng theo tầng (cho kỹ thuật viên)

Năm khối: cảm biến, thiết bị và mạng, chấp hành, tưới tiêu, hạ tầng. Mỗi khối có trạng thái và các `findings` thuộc nhóm đó. Kèm **chẩn đoán tầng lỗi** để trả lời "có cần ra hiện trường không".

### 12.4 Hàng đợi việc (trung tâm cảnh báo)

Danh sách `findings` theo mức độ, có: người được giao, thời gian chờ còn lại trước khi leo thang, nút xác nhận và tạm hoãn kèm lý do, liên kết sang bằng chứng, hộp đen và Datadog, và sổ tay xử lý tương ứng mã lỗi.

### 12.5 Màn hình điện thoại cho người trồng

Một trang: danh sách nhà màng với đèn xanh/vàng/đỏ, mỗi dòng một câu giải thích bằng tiếng Việt thường. Bấm vào xem chi tiết lô. Thiết kế cho sóng yếu: tải nhẹ, có trạng thái mất kết nối.

### 12.6 Hộp đen sự cố và sổ hành động

Giữ nguyên `/incident` đã có (hồ sơ 6 câu, thanh tua, liên kết Datadog) [CÓ]. Thêm sổ hành động: mọi hành động tự động kèm lý do, dải đang dùng, và bằng chứng.

### 12.7 Quy ước thiết kế

- Ba trạng thái: bình thường (●), cần theo dõi (▲), cần xử lý (■). **Kèm hình dạng và chữ, không chỉ màu** (cho người khó phân biệt màu).
- Mỗi số liệu ghi rõ lúc đo và nguồn (thiết bị hay tổng hợp).
- Trạng thái rỗng, đang tải, lỗi đều có thiết kế riêng.
- Banner khi mất kết nối với máy chủ.
- Tôn trọng tùy chọn giảm chuyển động.
- Nhãn "Dữ liệu mô phỏng" hiện thường trực.

---

# PHẦN V — THIẾT KẾ NỀN TẢNG

## 13. Kiến trúc đám mây

Chưa đọc được cấu hình AWS thật trong phiên này (công cụ bị chặn do máy thiếu Git Bash). Mục này là **thiết kế đích**; viết IaC cho một ngăn xếp mới, không nhập máy đang phục vụ giám khảo.

```
Người dùng ─► Route 53 (tên miền riêng) ─► CloudFront (+WAF) ─► nginx/ứng dụng (EC2)
10 nhà màng mô phỏng ─► MQTT có xác thực + TLS ─► dịch vụ ingest
Ứng dụng + ingest ─► MongoDB replica set 3 nút (3 vùng khả dụng)
Datadog Agent + tích hợp AWS (CloudWatch, CloudTrail) ─► Datadog US1
Sao lưu ─► S3 (phiên bản, vòng đời, mã hóa KMS)
```

| Trụ | Việc chính | Khi nào |
|---|---|---|
| Quản trị tài khoản | MFA cho gốc, không dùng tài khoản gốc, CloudTrail, chuẩn gắn thẻ, AWS Budgets | Trước hạn, rẻ |
| Biên | Elastic IP, tên miền riêng (thay `sslip.io`), chứng chỉ ACM | Trước hạn |
| Mạng | VPC riêng, cơ sở dữ liệu ở mạng con riêng, truy cập chỉ qua SSM (không SSH) | Đích |
| Tính toán | Tách máy ứng dụng/ingest khỏi MongoDB; Auto Scaling cỡ 1 để tự thay máy hỏng | Đích |
| Dữ liệu | Đĩa mã hóa, ảnh chụp EBS theo lịch, S3 có phiên bản và vòng đời — làm ngay; replica set 3 nút — đích |
| Bảo mật | Secrets Manager có xoay vòng, IMDSv2, vai trò máy tối thiểu quyền, GuardDuty | Làm ngay phần rẻ |
| Độ tin cậy | Viết mục tiêu RPO/RTO và **thử bằng diễn tập thật** | Làm ngay: 1 diễn tập |
| Quan sát hạ tầng | Tích hợp AWS vào Datadog, thẻ đồng bộ `env`/`service`/`version` | Làm ngay |

### 13.1 Hiện trạng đã xác minh (08/11/2026, lệnh chỉ đọc)

Đọc trực tiếp từ tài khoản `920235987407`, vùng `ap-southeast-2`. **Tám trong mười việc đã có sẵn và làm đúng** — bản 0.8 đã đề xuất nhiều thứ đã tồn tại.

| Hạng mục | Kết quả | Trạng thái |
|---|---|---|
| Máy | `t3.small`, đang chạy, có instance profile `smiot-demo-instance-profile` | [CÓ] |
| **IMDSv2** | `HttpTokens: required` | **[CÓ], đã đúng** |
| **Elastic IP** | `13.238.30.218` là Elastic IP (`eipalloc-0f26652badc2d8858`) gắn vào máy | **[CÓ] — URL demo an toàn** |
| **Mã hóa đĩa** | `vol-0fe7f6c8bac706a78`, 30 GB, gp3, `Encrypted: true` | **[CÓ], đã đúng** |
| **Nhóm bảo mật** | `smiot-demo-web` chỉ mở TCP 80 và 443 ra `0.0.0.0/0`; nhóm `default` không có luật vào. **MongoDB 27017 và MQTT 1883 không hề mở ra Internet** | **[CÓ], đã đúng** |
| **S3 phiên bản** | `Enabled` trên bucket sao lưu | **[CÓ]** |
| **S3 vòng đời** | Hai quy tắc: `backups/` hết hạn 35 ngày, `smiot/` hết hạn 7 ngày | **[CÓ], đã đúng** |
| Ảnh chụp EBS | Có 5 ảnh chụp thủ công, mô tả kiểu "SMIOT pre-deploy …", gần nhất 05/11 | [MỘT PHẦN] |
| **CloudTrail** | **Không có trail nào** | **[CHƯA]** |
| **Ảnh chụp theo lịch (DLM)** | **Không có chính sách nào** | **[CHƯA]** |
| Ngân sách (Budgets) | Lệnh không trả kết quả; coi như chưa có, nên kiểm lại trên console | [CHƯA xác định] |

### 13.2 Cảnh báo về IP đã được giải tỏa

Bản 0.8 cảnh báo rằng gán Elastic IP có thể làm đổi URL demo. **Cảnh báo đó không còn áp dụng:** `13.238.30.218` đã là Elastic IP gắn sẵn, nên IP giữ nguyên khi máy dừng và bật lại, và URL `13-238-30-218.sslip.io` không bị mất. Việc chuyển sang tên miền riêng vẫn là hướng phát triển, nhưng không còn gấp.

### 13.3 Việc cloud thực sự còn thiếu

Danh sách rút từ mười bước xuống còn bốn:

| # | Việc | Nơi làm | Rủi ro | Giá trị |
|---|---|---|---|---|
| 1 | **Ảnh chụp EBS theo lịch** — hiện chỉ chụp tay trước mỗi lần triển khai, nên giai đoạn không triển khai thì không có bản sao nào. Một chính sách DLM chụp hằng ngày, giữ 7 bản | Console EC2 → Data Lifecycle Manager | Không | Cao |
| 2 | **Bật CloudTrail** — một trail đa vùng ghi vào S3 | Console CloudTrail | Không | Vừa (hồ sơ: chứng minh có kiểm toán) |
| 3 | **Cảnh báo ngân sách** cho khoản credit khoảng 100 USD, ngưỡng 50%, 80%, 100% | AWS Budgets (dịch vụ toàn cầu, dùng `us-east-1`) | Không | Vừa |
| 4 | **Metric tuổi bản sao lưu** cộng monitor: script sao lưu đẩy một gauge "số giây kể từ bản sao lưu thành công gần nhất" | Sửa `scripts/aws/mongodb_backup.sh`; monitor tạo trên giao diện Datadog | Thấp | Cao (sao lưu im lặng là rủi ro lớn nhất) |

Cả bốn việc **không chạm vào máy đang chạy**, làm được trong một buổi. Thêm hai việc tùy chọn: MFA cho tài khoản gốc, và chuẩn gắn thẻ `Project`/`Env`/`Owner`.

Riêng **một diễn tập khôi phục thật** (`scripts/aws/mongodb_restore_drill.sh`, chạy trên bản sao) vẫn là việc giá trị nhất cho hồ sơ, vì nó cho ra số đo RPO/RTO duy nhất đáng tin. Ảnh chụp ngày 02/11 còn ghi "restore drill pending" trong mô tả.

**Những thứ không làm trước hạn:** VPC riêng, tách MongoDB sang máy khác, replica set, Auto Scaling, CloudFront, WAF, tên miền riêng, IaC đầy đủ. Tất cả đều cần dừng dịch vụ hoặc dựng lại hạ tầng.

## 14. Backend

| # | Việc | Ưu tiên |
|---|---|---|
| B1 | Kiểm tra lược đồ bản tin MQTT (Pydantic), từ chối bản tin sai, **bỏ mặc định `greenhouse_a`** (D6) | **P1** |
| B2 | Lớp dẫn xuất: VPD, DLI, cân bằng nước; collection `stage_envelopes` có phiên bản | **P1** |
| B3 | Lớp phát hiện `detectors/` và collection `findings`; tách lớp truy cập dữ liệu khỏi `service/auth.py` | **P1** |
| B4 | API REST có phiên bản (`/api/v1/...`): tổng quan, lô, nhà màng, `findings`, hành động; OpenAPI tự sinh | P2 |
| B5 | Ca trực và leo thang: `on_call_shifts`, `shift_handover`, đồng hồ chờ xác nhận | P2 |
| B6 | Gộp trùng và giới hạn tần suất báo lỗi qua Telegram; tuyến xác minh phục hồi gọi trực tiếp có thời hạn thay vì tiến trình con | P2 |
| B7 | Không khởi động khi thiếu bí mật ở môi trường thật; giới hạn đăng nhập sai; nhật ký kiểm toán. **Không xóa `static/test_plc.html` và `static/test_inverter.html`** — hai tệp này là mã React đang chạy (mục 22.4). Chỉ xem xét `phan_quyen.html`, `project.html`, `schedule.html`, `test.html`, `environment-dashboard.*` sau khi mở từng tệp kiểm | P2 |
| B8 | Tách tiến trình ingest/worker khỏi tiến trình web | sau hạn |

## 15. Frontend

| # | Việc | Ưu tiên |
|---|---|---|
| F1 | Hệ thống thiết kế tối giản (ba trạng thái có hình dạng, khoảng cách, chữ); tách `pages/home.py` (1.547 dòng) thành thành phần dùng chung; **chuyển trạng thái dùng chung sang `app.storage.user` theo khuôn `pages/schedule.py` đã làm đúng** (xem đính chính bản 0.6 dưới bảng) | **P1** |
| F2 | **Tổng quan 10 nhà màng** (12.1) kèm chế độ phòng điều khiển | **P1** |
| F3 | Trang lô (12.2) với dải mục tiêu vẽ làm vùng nền | **P1** |
| F4 | Hàng đợi việc (12.4) | P2 |
| F5 | Trang nhà màng theo tầng (12.3) | P2 |
| F6 | Màn hình điện thoại cho người trồng (12.5) | P2 |
| F7 | Trạng thái mất kết nối, rỗng, lỗi; truy cập bàn phím; giảm chuyển động | P2 |
| F8 | Trang `stage_envelopes` cho kỹ sư nông học | P3 |
| F9 | RUM, PWA | sau hạn |

**Đính chính bản 0.6 — trạng thái theo người dùng đã có khuôn đúng trong dự án.** Bản 0.3 nói "trạng thái giao diện dùng chung" như một lỗi chung của cả ứng dụng. Thực tế `pages/schedule.py` **đã làm đúng**: dùng `app.storage.user['schedule_state']` cho ngày đang chọn và tuần đang xem, và `app.storage.user['current_farm']` cho nhà màng. `pages/home.py` là chỗ ngoại lệ với biến `state` ở mức module. Nên việc cần làm là **áp khuôn đã có của `schedule.py` vào `home.py`**, không phải phát minh cách mới.

Kèm theo một mâu thuẫn thật cần dọn: hiện có **hai cơ chế chọn nhà màng song song** — `app.storage.user['current_farm']` (schedule.py) và `state['selected_farm']` ở mức module (home.py). Hai chỗ này có thể lệch nhau.

---

# PHẦN VI — THỰC THI

## 16. Lộ trình (đã cắt gọn)

Bản 0.2 nhét quá nhiều việc vào 7 ngày. Bản này cắt còn phần làm được và có bằng chứng.

**Phạm vi giữ lại:** động cơ kịch bản + `findings` + lớp cây trồng (VPD, DLI, dải mục tiêu cắm vào khóa liên động ở mục 4.4) + A1 tràn nước ở biên + S2/S3 + tổng quan 10 nhà màng + hồ sơ. Phần còn lại ghi là hướng phát triển.

**Hai việc rẻ nhất, làm đầu tiên (bản 0.5):**
1. Bật `SMIOT_APPLY_VALIDATORS=true` và ghi lại kết quả `getCollectionInfos` — validator chuyển từ "chưa xác nhận" sang "đã xác nhận" bằng một biến môi trường (mục 11.2).
2. Chạy `scripts/explain_before_after.py` để lấy báo cáo index và explain — công cụ đã có, chỉ cần chạy và lưu kết quả.

**Quyết định phạm vi 10 nhà màng (mục 9):** Ca 2 bị chốt cứng ở `greenhouse_a`/node 2 bằng hai `ValueError`. Hai lựa chọn: **(a)** 10 nhà màng đều phát dữ liệu và đều có lớp cây trồng, nhưng sự cố chỉ sinh ở `greenhouse_a` — rẻ, trung thực, nói rõ phạm vi; **(b)** tổng quát hóa vòng đời sự cố theo nhà màng — đúng hơn nhưng phải sửa năm chỗ và ánh xạ monitor/workflow theo nhà màng. Mặc định chọn **(a)** trước 15/11, và ghi (b) là hướng phát triển.

### 16.1 Gói việc, xếp theo giá trị chia cho rủi ro

Sau khi đọc toàn bộ mã, đây là thứ tự đề xuất. Cột "Vùng" cho biết việc đó rơi vào phần đã có test hay chưa (mục 11.3).

| # | Gói việc | Nội dung cụ thể | Công | Rủi ro | Vùng |
|---|---|---|---|---|---|
| **W1** | **Bật những gì đã có** | `SMIOT_APPLY_VALIDATORS=true` rồi ghi `getCollectionInfos`; chạy `scripts/explain_before_after.py` lưu báo cáo index và explain | Rất nhỏ | Rất thấp | — |
| **W2** | **Chỉ số cây trồng** | VPD (Tetens) có metric; DLI chỉ tính khi có chuỗi PAR/bức xạ đã lưu đủ nhịp. Hiện DLI được trả trạng thái unavailable, không bịa giá trị. | Nhỏ | Thấp | VPD code cục bộ; DLI chờ nguồn dữ liệu |
| **W3** | **Dải mục tiêu theo giai đoạn** | Collection `stage_envelopes` có phiên bản; quyết định chỉ dùng envelope đã duyệt/hiệu chuẩn, ghi version; thiếu thì UNKNOWN + BLOCKED_HOLD. | Nhỏ–vừa | **Vừa** (chạm hệ sự cố đã có test) | Code cục bộ; chưa có envelope thực địa được xác nhận/triển khai |
| **W4** | **Nhãn sự thật cho gieo lỗi** | `scenario_evidence.py`; sáu loại lỗi có ACK, run id và mapping incident khi tương quan chính xác. Mưa/trôi và các ca ngoài danh sách này còn thiếu. | — | — | Đã triển khai mã cục bộ; chưa chạy test/diễn tập tích hợp lượt này |
| **W5** | **Chặn tràn nước ở biên** | PLC ảo có giới hạn thời gian/thể tích và scenario áp thấp + flow cao; dừng bơm, đóng van, safe mode; trip/ACK ghi Mongo + action ledger và phát metric. Terraform monitor có sẵn nhưng gated/off; chưa xác nhận ingest hoặc apply. Watchdog cùng tiến trình app. | Nhỏ | Thấp | Mã cục bộ đã nối; chưa deploy/diễn tập thật lượt này |
| **W6** | **Màn hình tổng quan 10 nhà màng** | Tổng quan ở Home; một aggregation, cache 10 giây, quyền farm, trạng thái thiếu dữ liệu hiển thị rõ. | Vừa | Thấp | **Đã deploy và xác minh giao diện/tương tác trên EC2 10/11:** 10 farm, hai biểu đồ, bảng trạng thái; bấm farm mở chi tiết, lựa chọn giữ qua nhịp tự làm mới, nút quay lại hoạt động. `py_compile` đạt, dịch vụ active, HTTP `/login` trả 200. Chưa audit riêng các điều kiện dữ liệu một aggregation, cache 10 giây và phân quyền farm. |
| **W7** | **Đột biến và ngoài khoảng** | Finding S2/S3 có tương quan farm/node/run/time, xuất hiện trong hộp đen. | Nhỏ | Thấp | Mã cục bộ; compile đạt, chưa diễn tập tích hợp lượt này |
| **W8** | **Metric tầng chấp hành và thiết bị** | Metric flow/pressure/pump/valve/fan/ventilation, VPD, reboot và sequence anomalies. Flow Mongo vẫn chưa lưu pressure/pump/valve trong document telemetry thường. | Nhỏ–vừa | Thấp | Call path đã viết; chưa xác nhận ingest Datadog |
| **W9** | **Mưa** | Thêm lượng mưa vào `weather_api`; phân biệt rò ống với mưa rò mái | Vừa | Thấp | Chưa có test |
| **W10** | 10 nhà màng có sự cố riêng | Bỏ hai chốt `ValueError`, sửa bảy chỗ khai cứng, ánh xạ monitor/workflow theo nhà màng | **Lớn** | **Cao** (chạm hệ sự cố) | Có test |
| **W11** | **Phễu `findings` lên Datadog** | Metric `smiot.findings.open` gắn thẻ `farm`/`group`/`severity` (**không** gắn `code`, giữ cardinality thấp); hai monitor theo mức độ; workflow 0 điều phối theo `code`. **Phải làm trước W7**, nếu không mỗi bộ phát hiện mới lại đẻ một monitor | Nhỏ–vừa | Thấp | Chưa có test |
| **W12** | **Chuyển sang nút anh em** | Khi một nút hỏng, quyết định tưới dùng nút còn lại và đánh dấu `confidence` suy giảm, thay vì HOLD toàn bộ. Biến hệ thống từ "đứng lại" thành "chạy tiếp có kiểm soát" | Nhỏ–vừa | Vừa (chạm luồng quyết định) | Chưa có test |
| **W13** | **Bù bằng thông gió và tỷ lệ thoát** | Luật mở thông gió khi VPD hoặc nhiệt độ ngoài dải; tăng tỷ lệ thoát khi EC tích tụ. Thiết bị ảo đã có `vent_cmd` và đồng hồ thoát, chỉ thiếu luật | Nhỏ | Thấp | Chưa có test |
| **W14** | **Tự khởi động lại bộ phát hiện** | Nhịp tim cho mỗi bộ phát hiện; bộ nào chết thì tự chạy lại rồi mới báo, thay vì chỉ báo | Nhỏ | Thấp | Chưa có test |

**Khuyến nghị cập nhật (bản 1.1):** thứ tự đổi thành **W1 → W11 → W5 (phần ghi nhận) → W14 → W7 → W12 → W8 → W13**. Lý do: W11 là phễu, phải có trước mọi bộ phát hiện mới; W5 phần còn lại rẻ nhất vì biên đã xong; W14 nhỏ và bảo vệ mọi thứ còn lại. W2, W3, W6 lùi xuống nếu thiếu thời gian. Vẫn bỏ W9 và W10.

**Khuyến nghị cũ (bản 0.7):** làm W1 đến W8, bỏ W9 và W10 khỏi phạm vi trước hạn. W10 là việc đắt nhất và rủi ro nhất, và theo mục 9 có thể thay bằng phương án (a): 10 nhà màng phát dữ liệu và có lớp cây trồng, sự cố chỉ sinh ở `greenhouse_a`, nói rõ phạm vi trong hồ sơ.

### 16.2 Lịch theo ngày

| Ngày | Hồ sơ | Nền tảng và phát hiện | Giao diện |
|---|---|---|---|
| 08/11 | Sửa tài liệu 03/04 theo `docs/submission/00_PLAN.md` mục J (bỏ Bits AI) | **W1** (nửa ngày là xong); B1 kiểm lược đồ bản tin | F1 |
| 09/11 | Điền số liệu MongoDB và kết quả W1 vào tài liệu 02 | **W2**, **W4**; AWS: Budgets, CloudTrail, Elastic IP | F1 |
| 10/11 | | **W3**, **W5** | **W6** bắt đầu |
| 11/11 | | **W7**, **W8**; đĩa mã hóa, ảnh chụp EBS | **W6** xong |
| 12/11 | **Quyết định phạm vi:** mục nào ghi "đã có" theo tiêu chí mục 11.4, mục nào ghi "hướng phát triển" | Một diễn tập khôi phục thật; chạy bộ kịch bản lấy số liệu | Tập kịch bản demo lần 1 |
| 13/11 | Dựng 5 file Word | **Đóng băng mã**; thu bằng chứng | Chụp ảnh; tập demo lần 2 |
| 14/11 | Quét secret toàn lịch sử git, rà checklist, **nộp** | | |
| 15/11 | Dự phòng | | |

**Nguyên tắc thi hành:**
- Mọi thay đổi trên nhánh riêng, thử ở môi trường staging trước khi lên máy đang phục vụ giám khảo.
- **W3 và W5 chạm vào hệ sự cố đang có test** — chạy `py -3.12 -X utf8 -m unittest discover -s tests` trước và sau mỗi lần sửa, và không gộp hai gói này trong một lần triển khai.
- Mọi gói ở vùng chưa có test phải viết test cùng lúc (mục 11.3).
- Không đổi mã từ 13/11.
- **Không xóa bất kỳ tệp nào trong `static/`** trước khi đọc nó (mục 22.4).

**Cắt khỏi phạm vi trước hạn** (ghi hướng phát triển): W9, W10, S4–S6, C3–C4, C6–C8, C10, A5–A7, D7, H2–H3, B4–B8, F4–F9, replica set, VPC riêng, IaC đầy đủ, ca trực và leo thang (mục 7.2).

## 17. Kịch bản demo 10 phút (mục mới)

| Phút | Việc | Giám khảo thấy gì |
|---|---|---|
| 0–1 | Mở Home tổng quan | 10 nhà màng; trạng thái dữ liệu, lô và incident chỉ khi có dữ liệu thực |
| 1–2 | Giải thích chia vai và lớp cây trồng | VPD và cổng dải mục tiêu; DLI hiện chưa có chuỗi đầu vào |
| 2–4 | **Gieo kịch bản nước** ở NM-03 | PLC ảo trong app dừng bơm/đóng van; Mongo ghi trip/ACK và action; đây là mô phỏng, không phải PLC vật lý. Monitor Datadog chỉ trình diễn sau khi metric được xác nhận ingest và monitor được bật |
| 4–6 | Mở trang lô NM-03 | Biểu đồ với dải mục tiêu, khoảng dữ liệu không đáng tin, cân bằng nước |
| 6–8 | **Gieo lỗi đứng số** (Ca 2 ở ứng dụng đã có; monitor `342585819` đã xác minh; workflow `2f9a3c1d-5292-4bc3-b4b9-cc03d4172724` đã published và nối monitor) | Phát hiện và HOLD tại app/PLC ảo; workflow đã nối trigger/xuất bản nhưng chưa có run tự động từ monitor; xác minh phục hồi bằng mẫu Mongo mới |
| 8–9 | Mở hộp đen sự cố | Hồ sơ 6 câu, dòng thời gian hợp nhất từ một aggregation |
| 9–10 | Mở timeline và bằng chứng | Nêu rõ sự cố còn `recovering` cho đến khi có số đo sau sửa chữa; không tuyên bố độ chính xác/độ phủ khi chưa chạy đủ lượt đánh giá |

Kịch bản phải chạy lại được từ trạng thái sạch, bằng một lệnh. Tập trước ít nhất hai lần.

## 18. Tham chiếu nông học

**Mã hiện tại đã xử lý việc này tốt, và chặt hơn bản thiết kế đầu tiên của mục này.** Trong `service/mongodb_showcase.py`, trường `note` đã: dẫn nghiên cứu giống dưa lưới Khang Nguyên (Galia) với các mốc lấy mẫu ngày 33, 36, 39, 42, 45; nói rõ đó **không** phải khoảng thu hoạch áp dụng cho mọi giống; ghi rằng giống của lô diễn tập chưa được xác nhận; và kết luận lịch này chỉ nhắc kiểm tra quả, **không dự báo ngày hái đã hiệu chuẩn**. Biến cũng đặt tên `gdd_context` thay vì `gdd`.

Giữ nguyên cách làm đó và áp cho phần mới. Nhóm **không** có kỹ sư nông học xác nhận trong khung thời gian này:

- Mọi dải mục tiêu lấy từ tài liệu đã công bố, ghi rõ nguồn trong trường `source` của `stage_envelopes`, và trạng thái **"chưa hiệu chuẩn tại chỗ"** — cùng khuôn với `note` đã có.
- Hồ sơ nộp trình bày lớp cây trồng như **cơ chế** (hệ thống thực thi và kiểm toán được dải mục tiêu bất kỳ), không như **kết luận nông học** (dải này là đúng cho dưa lưới Việt Nam).
- Các mục cần xác nhận khi có kỹ sư: dải độ ẩm đất và VPD theo giai đoạn, hệ số nhiệt độ nền cho GDD (mã đang dùng 10 °C), hệ số cây theo giai đoạn cho ET0, khoảng hợp lệ của EC, số vùng cảm biến tối thiểu cho 1.000 m², ngưỡng nguy cơ bệnh.
- Công thức VPD (Tetens) là vật lý, không phải tuyên bố nông học, nên dùng được trực tiếp.

## 19. Hướng phát triển (sau hạn)

- Nhiều tổ chức hoặc khách hàng: cách ly dữ liệu theo tổ chức, định danh và chứng chỉ riêng từng thiết bị, ACL theo topic.
- Xác thực và TLS cho thiết bị thật (sketch hiện kết nối không mật khẩu — chấp nhận được với thiết bị ảo, phải sửa trước khi có thiết bị thật).
- Nối băm sổ hành động để phát hiện sửa lén; chế độ chạy bóng và chạy lại luật trên dữ liệu vụ cũ ("nếu dùng dải mới, vụ trước có tránh được lần tưới sai không").
- MongoDB replica set thật (theo dõi thay đổi trên collection vận hành, không phải `telemetry`), VPC riêng, Auto Scaling, IaC đầy đủ. **Lưu ý: vấn đề "không có transaction" đã có câu trả lời trong mã** — `record_action_event()` dùng so-và-đặt (`query["state"] = old_state`), thứ tự trạng thái `ORDER` không cho lùi, bắt `DuplicateKeyError`, và chống phát lại khi MQTT QoS 1 gửi trùng. Nên replica set là để có tính sẵn sàng và theo dõi thay đổi, **không phải để sửa lỗi đúng đắn**.
- SLO theo khách, RUM, Synthetic, ứng dụng di động, báo cáo truy xuất cho người mua.
- So sánh ẩn danh giữa các nhà màng để mỗi lô học từ cả mạng lưới.
- Mở rộng chấp hành: quạt, lưới che, bồn (A5–A7).

## 20. Rủi ro và việc cần xác nhận

- **Lộ trình vẫn chặt.** Nếu chậm, cắt theo thứ tự: C5/C9 → D3–D6 → F3 → H4. Giữ A1, S2/S3, C1/C2, F2 và hồ sơ.
- Cấu hình Mosquitto (xác thực, ACL) chưa được kiểm tra.
- Lệnh điều khiển bơm có mang mã nhà màng hay không chưa được kiểm tra.
- Cấu hình AWS thật chưa đọc được trong phiên này; cần Git for Windows để công cụ AWS chạy, hoặc người dùng tự kiểm và cung cấp.
- Nội dung các trang tĩnh cũ trong `static/` (`test_*.html`, `phan_quyen.html`) chưa được mở để kiểm có lộ gì không.
- Hệ số chuyển bức xạ sang PAR cho DLI chưa chọn; phải ghi rõ hệ số đang dùng.
- Ban tổ chức xác nhận dữ liệu tổng hợp và thiết bị mô phỏng có hợp lệ không.
- Mọi thay đổi trên EC2 đang phục vụ giám khảo phải qua nhánh riêng, kiểm thử và có đường hoàn tác.

## 21. Chính sách tuyên bố

Chỉ ghi "đã có" cho mục qua được tiêu chí ở mục 11. Mục khác ghi "định hướng". Không tuyên bố thiết bị vật lý, khách hàng thật, hiệu quả thực địa, MTTD/MTTR, SLO đạt, hay "tự động khắc phục" khi bước thực hiện là thủ công. Không trình bày dải mục tiêu như kết luận nông học đã được xác nhận. Mọi số liệu trên 10 nhà màng mô phỏng ghi rõ là mô phỏng.

## 22. Cơ sở đối chiếu của bản thiết kế này

Mục này ghi rõ bản thiết kế dựa trên đâu, để người đọc biết chỗ nào cần kiểm lại.

### 22.1 Đã đọc mã và đối chiếu trực tiếp
`main.py` · `service/demo_mode.py` · `service/mongodb_showcase.py` · **`service/incident_blackbox.py`** · **`service/incident_lifecycle.py`** · **`service/operational_evidence.py`** · `service/datadog_metrics.py` · `service/weather_api.py` · `service/middleware.py` · `scripts/set_demo_sensor_fault.py` · `scripts/set_demo_ui_fault.py` · `wokwi/smiot_demo/sketch.ino` (phần phát dữ liệu) · `pages/chart.py`; và đọc một phần (grep hoặc đoạn) của `service/auth.py`, `service/mqtt.py`, `service/telemetry_health.py`, `service/telemetry_provenance.py`, `service/traceability.py`, `service/ai_service.py`, `service/scheduler.py`, `pages/home.py`, `pages/incident.py`, `pages/permission.py`, `scripts/aws/bootstrap_ubuntu.sh`, `scripts/aws/mongodb_backup.sh`.

Toàn bộ mô tả về hộp đen sự cố, vòng đời sự cố và sổ lệnh trong bản 0.5 nay **đã đối chiếu mã**, không còn lấy lại từ `docs/submission/00_PLAN.md`.

### 22.2 Chưa đọc
`scripts/explain_before_after.py` (chỉ thấy nó gọi `ensure_incident_indexes`) · `scripts/mongo_timeseries_benchmark.py` · `scripts/telemetry_quality_report.py` · `scripts/verify_and_clear_demo_safe_mode.py` · nội dung bên trong các tệp HTML ở `static/` (đã biết tệp nào được dùng, chưa đọc mã React bên trong) · `components/cards.py`, `components/layout.py` · `pages/login.py`, `pages/project.py`, `pages/traceability.py`, `pages/public_lot.py`, `pages/mongodb_lab.py`, `pages/permission.py` (chỉ grep) · từng tệp trong `tests/` (đã có bản đồ phủ ở mục 11.3, chưa đọc nội dung).

Bản 0.7 đã đọc: `pages/plc.py`, `pages/inverter.py` (grep đường lệnh), `pages/devices.py` (grep cấu trúc), `pages/data_table.py` (grep cấu trúc), và danh sách `tests/`.

### 22.2b Việc nhỏ ghi lại khi đọc `pages/schedule.py`
Hàm xuất Excel dùng đường dẫn `/tmp` khai cứng (`os.makedirs('/tmp')`, `/tmp/NhatKyTuoiTieu_<farm>.xlsx`). Chạy trên EC2 Linux thì được; chạy thử trên máy Windows sẽ tạo `C:\tmp` hoặc lỗi. Không chặn việc gì, nhưng nên dùng thư mục tạm theo hệ điều hành.

### 22.4 Cảnh báo: các tệp trong `static/` không phải rác

Bản 0.3 và 0.5 khuyên "dọn các trang tĩnh cũ trong `static/`". **Lời khuyên đó sai và đã bị rút.**

`pages/plc.py:367` và `pages/inverter.py:308` **mở tệp HTML lúc chạy**, dùng biểu thức chính quy lấy khối `<script type="text/babel">`, rồi chèn vào trang qua `ui.add_body_html`:

| Tệp | Vai trò | Xóa thì sao |
|---|---|---|
| `static/test_plc.html` | Mã React của bảng điều khiển 7 bơm | **Trang `/plc` mất bảng điều khiển** |
| `static/test_inverter.html` | Mã React của trang biến tần | **Trang `/inverter` mất giao diện** |
| `static/phan_quyen.html`, `project.html`, `schedule.html`, `test.html`, `environment-dashboard.html`, `environment-dashboard.js` | Không thấy tham chiếu nào từ Python | Có thể là tệp cũ thật, nhưng **vẫn phải mở đọc trước khi xóa**, và chúng đang được phục vụ công khai ở `/static` |

Hai điểm kỹ thuật kèm theo: React 18, Babel standalone và Tailwind đều tải từ CDN ngoài (`unpkg.com`, `cdn.tailwindcss.com`) **mỗi lần mở trang**, và Babel biên dịch ngay trên trình duyệt. Nếu mạng ở buổi demo chập chờn, hai trang này sẽ không hiện. Nên tải sẵn các thư viện đó về `static/` trước khi trình diễn — nhưng đó là việc sau 15/11, không nằm trong phạm vi mục 16.

### 22.3 Kết luận về độ tin của bản thiết kế này

Bản 0.3 đánh giá thấp dự án ở ba chỗ, bản 0.5 thêm bốn chỗ nữa. Khuôn mẫu đã rõ: **dự án này chặt hơn vẻ ngoài, và những gì trông như "chưa có" thường là "có nhưng bị tắt, bị khai cứng phạm vi, hoặc chỉ thiếu metric Datadog".** Khi lập kế hoạch cho một phần ở mục 22.2, đọc mã trước, đừng tin cột trạng thái.


## 23. Bản cấu hình Datadog tham khảo cho tài khoản mới

Bộ JSON và Terraform tại [docs/datadog_config_snapshot/20261108T150159Z/](datadog_config_snapshot/20261108T150159Z/README.md) được đọc từ tài khoản Datadog cũ. Đây là **snapshot lịch sử**, không phải cấu hình import cho tổ chức hiện tại. Không tái sử dụng ID workflow/monitor của snapshot như tài nguyên live và không áp dụng Terraform trước khi kiểm tra plan cùng account/site đích.

### Monitor đang có trong tổ chức Datadog hiện tại

> **Đã đọc trực tiếp danh sách trong phiên Datadog US1 ngày 10/11/2026:** 14 custom monitor. Trạng thái dưới đây là trạng thái giao diện tại lúc đọc, không phải lịch sử uptime. Ngoài 14 custom monitor còn có 7 host monitor và 2 APM monitor; bảng này tập trung vào 14 custom monitor của SMIOT.

| Monitor hiện tại | ID | Trạng thái quan sát được | Vai trò / ghi chú |
|---|---:|---|---|
| `SMIOT | AI ask latency high` | `342585824` | NO DATA | Cần xác minh ingest `smiot.ai.ask_latency_ms`. |
| `SMIOT | MQTT dependency unhealthy` | `342585828` | OK | Tín hiệu sức khỏe MQTT. |
| `SMIOT | MongoDB dependency unhealthy` | `342585827` | OK | Tín hiệu sức khỏe MongoDB. |
| `SMIOT | PLC command latency high` | `342585825` | NO DATA | Cần xác minh ingest `smiot.plc.command_latency_ms`. |
| `SMIOT | air temperature telemetry absent` | `342585830` | OK | Thiếu dữ liệu nhiệt độ không khí. |
| `SMIOT | persisted sample rate missing` | `342585823` | OK | Tốc độ mẫu đã ghi vào kho dữ liệu. |
| `SMIOT | sensor flatline` | `342585819` | OK | Ca 2; phát hiện độ ẩm đất Node 2 đứng số. |
| `SMIOT | smiot.service inactive` | `342585838` | OK | Ca 3; phát hiện dịch vụ ứng dụng ngừng hoạt động. |
| `SMIOT | soil humidity telemetry absent` | `342585835` | OK | Thiếu độ ẩm đất. |
| `SMIOT | soil temperature telemetry absent` | `342585837` | OK | Thiếu nhiệt độ đất. |
| `SMIOT | telemetry ingest lag` | `342585822` | OK | Độ trễ nhận telemetry. |
| `SMIOT | telemetry not fresh` | `342585820` | OK | Cờ freshness của telemetry. |
| `SMIOT | telemetry sample stale` | `342585831` | OK | Tuổi mẫu vượt ngưỡng. |
| `SMIOT | telemetry status mismatch` | `342585836` | OK | Ca 1; trạng thái giao diện không khớp dữ liệu mới trong MongoDB. |

Các ID `339977703`, `339977691`, `340356283`, `341409441`, `339990226`, `339990232` và các workflow `e2835af0…`, `18d1b008…`, `b83453ff…` là snapshot/tài nguyên lịch sử của tổ chức cũ. Không dùng chúng làm ID live hiện tại.

### Trạng thái ba workflow Datadog

| Ca | Trạng thái hiện tại | Workflow và monitor | Vai trò, điều kiện an toàn / khoảng trống |
|---|---|---|---|
| 1 — `false_offline` | Bản `ffd62026-6b63-40e4-9b46-6ac18d2d584f` đã published và nối monitor `342585836`; draft cũ `a9e36b20-6ac5-4553-ba20-0d6fae58e6f4` còn lại, chưa xóa | JSON: `outputs/workflow_imports/ca1_refuse_restart.json`; handle `@workflow-smiot-ca1-refuse-restart` | Backend phát `smiot.telemetry.status_mismatch` và `smiot.telemetry.sample_age_seconds` theo farm/node/source. JSON lọc đúng `greenhouse_a/node:1`; chỉ ghi `REFUSED_RESTART` nếu mismatch còn bật và mẫu Mongo còn mới (<90 giây), thiếu dữ liệu/lỗi thì không hành động. Manual run `d63a1077-308e-4e05-81ad-e1471981577f`: query và If thành công, đi nhánh escalation vì mismatch không xác nhận; không có hành động. Chưa có run tự động từ monitor và chưa kiểm chứng nhánh `REFUSED_RESTART`. |
| 2 — `soil_humidity_flatline` | Published và nối monitor `342585819` | Workflow `2f9a3c1d-5292-4bc3-b4b9-cc03d4172724`; handle `@workflow-smiot-ca2-confirm-local-interlock` | Backend tính flatline từ 10 mẫu mới được lưu trong MongoDB, theo từng farm/node; workflow chỉ xác nhận tín hiệu flatline, không khẳng định HOLD đã ACK. Manual run `ac94d5ca-ebfd-4aea-96d0-b78314ccd5c3` (2026-11-09 17:42 UTC) hoàn tất query, If và Echo escalation trong khoảng 3 giây; không gửi HOLD/CLEAR. Chưa có run tự động do monitor kích hoạt; HOLD do app/PLC ảo thực hiện tại biên, CLEAR chỉ qua verifier ứng dụng sau khi đủ bằng chứng. |
| 3 — `service_down` | Đã xuất bản và nối monitor | Workflow `373ed0c0-4509-4fcd-a067-f54f0becc00e`; monitor `342585838` | Runbook giới hạn ở guard và khởi động riêng `smiot.service`, không restart EC2/MongoDB/MQTT. AWS connection test gần nhất thành công trong Datadog US1, xác nhận Datadog assume được role. DryRun SSM trước đó tới guard trên EC2 và bỏ qua lệnh vì app đang active. Chưa chứng minh nhánh start khi app thật sự dừng; connection test không tự chứng minh mọi quyền thao tác AWS của workflow. |

### Khớp backend, truy vấn và quyền truy cập

- Ca 1: metric và tag trong JSON khớp với producer backend theo farm/node. Query đã chạy; monitor `342585836` gọi đúng handle của workflow đã published. Chỉ kiểm chứng được nhánh escalation; nhánh `REFUSED_RESTART` và run tự động do monitor kích hoạt chưa có bằng chứng.
- Ca 2: backend tính flatline từ 10 mẫu mới được lưu trong MongoDB, theo từng farm/node; workflow chỉ đọc metric này. Monitor `342585819` gọi đúng handle; manual test hoàn tất qua escalation. Chưa có run tự động do monitor kích hoạt. HOLD/ACK phải chứng minh riêng bằng action ledger/PLC ACK.
- Ca 3: AWS connection test mới nhất thành công, chứng minh Datadog assume được role. DryRun SSM trước đó đã tới guard và skip do app đang active. Chưa chứng minh nhánh start khi app dừng hoặc toàn bộ quyền cần thiết cho nhánh này.
- Datadog MCP: chưa xác nhận phiên MCP dùng cùng tổ chức US1 đang mở trong trình duyệt; công cụ MCP trong phiên này không có quyền ghi. Không dùng MCP để tạo/sửa workflow hoặc monitor, và không khẳng định API ghi hoạt động. Lần query metrics qua MCP trả về cú pháp hợp lệ nhưng không có điểm trong khoảng truy vấn; chưa xem đó là kết quả của đúng tổ chức cho tới khi xác minh identity.
- Ba JSON import/draft/adoption nằm trong `outputs/workflow_imports/`. `ca3_adoption.json` là hồ sơ ghi nhận workflow hiện hữu, **không phải** JSON để import tạo bản sao. Không nhúng API key, application key, bearer token hay mật khẩu vào JSON.

Terraform là bản biểu diễn được tạo từ cấu hình đọc được, không phải export Terraform nguyên gốc của Datadog. JSON workflow Ca 1/Ca 2 đã được published và monitor message đã gắn đúng handle; cần kiểm chứng bằng một alert event thật trước khi tuyên bố trigger tự động hoạt động, đồng thời cần dữ liệu để xác nhận nhánh tích cực; Ca 3 đã qua connection test và DryRun có guard, nhưng chỉ được coi là phục hồi tự động đã chứng minh sau khi kiểm tra được nhánh start trong điều kiện dịch vụ dừng an toàn. Probe không còn hardcode ID cũ; liên kết incident cần `SMIOT_PROBE_MONITOR_ID`/`SMIOT_PROBE_WORKFLOW_ID` trên EC2, chưa xác minh cấu hình runtime. Terraform plan sau khi cập nhật monitor message dự kiến 0 add / 1 change / 0 destroy; thay đổi duy nhất nằm ở monitor `systemd` và muốn gỡ handle recovery hiện có cùng đặt lại một số mặc định. Plan không được apply vì ngoài phạm vi thay đổi Ca 1/Ca 2.

Cloud Cost budgets chưa xuất được do quyền API trả 403; AWS CUR không có cấu hình nào được trả về. Không có API key, app key hay token trong bộ file.

## 24. Bộ chạy 36 kịch bản vận hành

`service/scenario_catalog.py` là danh mục chung cho 36 mã: C1–C10 (cây trồng/khí hậu), S1–S6 (cảm biến), D1–D7 (thiết bị và chất lượng dữ liệu), A1–A7 (cơ cấu), H1–H6 (ứng dụng/hạ tầng). Trang `/plc` và `scripts/demo_scenario.py` lấy cùng danh mục; các tên cũ như `pipe_leak`, `water_overrun` vẫn được ánh xạ để giữ tương thích.

Mỗi lượt có `scenario_run_id`, ACK áp dụng/dừng, bản tin đầu tiên liên quan, kết quả đánh giá riêng và bằng chứng MongoDB idempotent. Fault label không bị trộn vào telemetry cảm biến. Các kịch bản A/H chỉ tạo bằng chứng điều khiển giả lập; chúng **không** dừng ứng dụng thật, restart EC2, gọi Datadog, gửi lệnh tới thiết bị vật lý hoặc thay đổi dữ liệu vận hành thật.

### Nhiều sự cố cùng lúc

Backend cho phép các lượt trên cùng farm chạy đồng thời nếu dùng tài nguyên độc lập; lượt dùng chung đường nước/bơm, cùng kênh khí hậu, cùng node/cảm biến hoặc cùng kênh điều khiển sẽ bị từ chối. Mỗi lượt có mã riêng nên có thể điều tra và dừng riêng bằng CLI. Trang `/plc` hiện chỉ giữ một lượt đang chọn trong giao diện; chạy nhiều lượt đồng thời cần dùng các phiên CLI riêng, và mỗi lệnh dừng phải nêu đúng `scenario_run_id`. Không gom các triệu chứng thành một nguyên nhân duy nhất nếu chưa có bằng chứng phụ thuộc chung.

### Xác nhận phục hồi

`service/scenario_recovery.py` và lệnh `recovery-check` chỉ đánh giá bằng chứng hậu xử lý: đủ mẫu, dữ liệu mới, ngưỡng đã cấu hình, phản hồi cơ cấu và rà soát của người vận hành khi bắt buộc. Kết quả có thể là `recovering`, `unknown`, `recovered_pending_review` hoặc `recovery_verified`. Dừng kịch bản không đồng nghĩa phục hồi, và bộ kiểm tra không tự đóng incident.

### Bảng tiến độ

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Danh mục và bộ chọn đủ 36 mã C/S/D/A/H | ✅ Đã lập trình cục bộ | Trang `/plc` và CLI dùng chung catalog; tên cũ còn được ánh xạ. |
| Tiêm tín hiệu và đánh giá theo từng nhóm | ✅ Đã lập trình cục bộ | C/S/D có evaluator theo dữ liệu/ngữ cảnh; A/H phát bằng chứng giả lập riêng. |
| ACK, `scenario_run_id`, nối sự kiện vào Mongo idempotently | ✅ Đã lập trình cục bộ | Chỉ ghi khi simulator ACK khớp; chưa xác minh runtime mới trên EC2. |
| Dừng riêng một lượt và kiểm tra phục hồi | ✅ Đã lập trình cục bộ | STOP không tự CLEAR; `recovery-check` đánh giá bằng chứng được cung cấp. |
| Chặn hai kịch bản cùng chiếm cảm biến/kênh/đường nước | ✅ Đã lập trình cục bộ | Khóa tài nguyên chỉ trong tiến trình hiện tại; chưa phải khóa phân tán. |
| Chạy đồng thời lỗi độc lập | 🟡 Có ở backend/CLI | UI `/plc` vẫn chỉ quản lý một lượt đang chọn; nhiều worker thật chưa được kiểm chứng. |
| Hai cảnh báo độc lập cùng hiện, không che nhau | 🟡 Một phần | Lượt/finding có ID riêng; chưa kiểm chứng trải nghiệm UI và thông báo nhiều sự cố đồng thời. |
| Tự gom alert Datadog thành incident gốc khi có dependency chung | ⬜ Chưa làm | Cần topology/dependency evidence; không gom chỉ dựa vào thời điểm gần nhau. |
| Chạy đủ 36 lượt, gồm đồng thời và tự phục hồi | ⬜ Chưa diễn tập | Chưa bắn lệnh hoặc ghi dữ liệu trong lượt này; cần diễn tập có ACK và bằng chứng hậu xử lý. |
| Triển khai thay đổi hiện tại lên EC2 | ⬜ Chưa làm | Mã đang ở workspace local. |

**Ví dụ hai lỗi độc lập:** A2 (áp suất bơm bất thường) và C1/S1 (độ ẩm đất cao hoặc cảm biến đất sai) được giữ thành hai lượt/cảnh báo riêng. Liên động bơm có thể dừng bơm; dữ liệu đất vẫn được đánh giá riêng, và tưới bị giữ nếu số đo không đáng tin. Chỉ hiển thị chúng dưới cùng farm/thời điểm; không kết luận cái này gây ra cái kia nếu không có bằng chứng. Hiện quy tắc an toàn này được thể hiện trong catalog/evaluator, nhưng chưa có diễn tập đồng thời đã xác nhận trên EC2.

### Giới hạn cần giữ trong bản trình diễn

- C1/C2/C3/C5 chỉ tạo mẫu lỗi khi có stage envelope đã duyệt và hiệu chuẩn. C4/C6–C10 cần chính sách, lịch sử hoặc xác nhận ngoài hiện trường; thiếu thì trả `unknown/HOLD`.
- S4/S5/S6 và D5/D6/D7 cần đủ lịch sử, cadence, registry hoặc ngưỡng theo loại thiết bị; không bịa kết luận khi nguồn chưa được nối.
- H1–H6 là mô phỏng trên kênh sự kiện riêng, không chứng minh app/EC2/Datadog thật đã hỏng hay tự được sửa.
- Đây là triển khai mã nguồn; chưa khẳng định đã chạy đủ 36 lượt trên EC2 hoặc đã ghi/đọc lại bằng chứng runtime. Chỉ các lượt thực sự ACK và được xác nhận mới được báo là đã diễn tập.

## Cập nhật triển khai Datadog — 10/11/2026

Đã đăng và đọc lại qua Datadog US1 đủ **10 workflow nghiệp vụ (#1–#10)**. Bộ điều phối #0 vẫn nằm ngoài con số 10 theo định nghĩa tại mục 7.4. Bảy workflow mới dùng metric query, điều kiện, nhánh bằng chứng/chuyển người và lỗi truy vấn; chúng không gửi lệnh tới bơm, van, quạt, AI hay dịch vụ EC2. Ba workflow Ca 1–3 giữ nguyên.

| Ca kế hoạch | Workflow / ID | Trigger monitor | Trạng thái và giới hạn bằng chứng |
|---|---|---|---|
| #1 PLC an toàn | `SMIOT | W1 | Verify PLC safety trip evidence` / `b9e72b04-1580-45f8-ae1e-628124a19065` | `342734303` | Đã published/nối monitor; monitor No Data, chưa xác minh metric đã được deploy/ingest. Workflow chỉ yêu cầu đối chiếu PLC ACK và sổ MongoDB. |
| #2 Chất lượng dữ liệu | Ca 2 / `2f9a3c1d-5292-4bc3-b4b9-cc03d4172724` | `342585819` | Đã published/nối monitor; chỉ xác nhận metric, không gửi HOLD/CLEAR. |
| #3 Khôi phục dịch vụ | Ca 3 / `373ed0c0-4509-4fcd-a067-f54f0becc00e` | `342585838` | Đã published/nối monitor. Nhánh khởi động khi service thực sự dừng vẫn chưa được xác minh. |
| #4 Từ chối hành động sai | Ca 1 / `ffd62026-6b63-40e4-9b46-6ac18d2d584f` | `342585836` | Đã published/nối monitor; run trước đi nhánh escalation, chưa chứng minh nhánh REFUSED_RESTART hoặc trigger tự động. |
| #5 Phân loại gốc rễ | `SMIOT | W5 | Root cause dependency triage` / `d3f0705e-2cbd-430a-9a3a-b1fd02a42cc9` | `342585827`, `342585828` | Đã published/nối monitor Mongo/MQTT; workflow chỉ tổng hợp tín hiệu để điều tra, không restart. |
| #6 Nhịp bộ phát hiện | `SMIOT | W6 | Detector heartbeat review` / `d8e1b3db-1a54-4b4f-9be3-bf7e270a86f3` | Chạy thủ công | Đã published. Metric hiện phát sau lần đánh giá finding thành công, không phải heartbeat định kỳ; chưa thể dùng để phát hiện hoặc khởi động lại detector chết. |
| #7 Lượt tưới | `SMIOT | W7 | Irrigation schedule evidence review` / `bb86206c-6df8-4b1d-8016-175a2fc62e49` | `343594187` (advisory) + `342585835` (telemetry absent) | Đã diễn tập synthetic farm/node: Alert → workflow → normal → OK. Chỉ xem xét dữ liệu tươi và envelope MongoDB đã duyệt; không sửa lịch tưới. |
| #8 VPD/EC và nguy cơ cây | `SMIOT | W8 | Crop climate and EC evidence review` / `593a670c-d59c-4104-8658-df260245a21e` | `343594185` (advisory) + `342585831` (sample stale) | Đã diễn tập synthetic farm/node: Alert → workflow → normal → OK. Chỉ chuyển người xem xét; không tự mở quạt, xả/rửa, phun thuốc hay châm dinh dưỡng. |
| #9 Chấp hành không ACK | `SMIOT | W9 | Actuator acknowledgement verification` / `47e95b24-db40-4cd5-b667-5b90e170b667` | `342734743` | Đã published/nối monitor mới cho `smiot.actuator.command_unacknowledged`; monitor No Data cho tới khi mã mới được deploy và metric vào Datadog. Không tự gửi lại lệnh. |
| #10 AI không khả dụng | `SMIOT | W10 | AI failure safety verification` / `50b3dc85-dd20-4220-bda1-ec78d2a3d00f` | `342585824` | Đã published/nối monitor độ trễ AI; monitor No Data. Metric lỗi provider mới chỉ có trong mã cục bộ tới khi deploy; workflow yêu cầu xác minh HOLD trong app, không phát lệnh tưới. |

Các JSON định nghĩa W1, W5–W10 ở `outputs/workflow_imports/`; danh sách ID và trạng thái đọc lại nằm ở `outputs/workflow_imports/20261110_published_10_workflows.json`. **Published không đồng nghĩa đã diễn tập thành công:** các ca có trạng thái No Data, chưa deploy producer, hoặc thiếu chính sách nông học vẫn chưa được coi là tự động hoàn chỉnh.

### Kiểm tra luồng thông báo Datadog → app — 10/11/2026

- Kiểm tra trực tiếp đúng tổ chức US1: cả 10 workflow đều đang published. Chín monitor associations được khai trong manifest đều đọc được; monitor W1, W9, W10 đang `No Data`; W6 chưa có monitor và chỉ chạy thủ công.
- Phát hiện một liên kết sai: monitor W4 `342585836` vẫn nhắc workflow handle cũ `smiot-ca1-refuse-restart`, trong khi workflow published hiện tại có handle `smiot-ca1-refuse-restart-1`. Không thể khẳng định monitor đang gọi đúng W4 mới.
- Chưa có HTTP notification action từ bất kỳ workflow nào về chuông app. Backend trước thay đổi chỉ nhận sự kiện recovery-clear, không nhận event tổng quát từ workflow.
- Đã thêm mã cục bộ `POST /api/integrations/datadog/notification`: yêu cầu `DATADOG_APP_NOTIFICATION_TOKEN`, ghi MongoDB idempotent theo Datadog workflow run ID và cập nhật chuông; endpoint chưa được deploy nên chưa có bằng chứng app nhận event thật.
- Đã thêm `scripts/prepare_datadog_workflow_app_notifications.py` để xuất 10 JSON giữ nguyên graph, nối nhánh cuối đến HTTP action qua Datadog Action Connection. Mặc định chỉ xuất JSON; `--apply` mới cập nhật workflow. Không có khóa trong JSON. Connection ID và token chưa được tạo/cấu hình; chưa import/apply workflow.
- Home query đã đổi cục bộ từ aggregation sort/group trên toàn history sang truy vấn có giới hạn theo farm + measurement để dùng index telemetry hiện có. Python compile và kiểm tra transform JSON mẫu đạt; chưa deploy, chưa xác minh lại hết `ExecutionTimeout` trên app live.
- AWS CLI profile `aws-moi` chưa xác thực tại lần kiểm tra này; vì vậy chưa thể cập nhật `/etc/smiot/app.env`, deploy app, test POST thật hay xác minh app bell. Không được ghi nhận chuỗi Datadog → app là đã hoàn tất.

#### Cập nhật sau kiểm chứng — 10/11/2026

> Phần này thay thế các trạng thái triển khai cũ ngay phía trên khi hai phần mâu thuẫn. Bản cũ được giữ làm lịch sử tiến độ.

- Cả 10 workflow hiện đã published trong đúng tổ chức Datadog US1; W1 giữ trigger monitor và API, W4 đã sửa handle monitor sang workflow published hiện tại. HTTP Action Connection đã được nối vào nhánh thông báo của các workflow.
- Hai lượt kiểm tra an toàn W1 (`bfb0cf91-4580-4838-a9c5-05b270f73331`, `2026-11-10T04:29:25Z`; `6d3952d1-8ba9-4bfb-acd0-0dbb0b5cbadee`, `2026-11-10T04:29:41Z`) hoàn tất thành công; không có lệnh tới actuator. App nhận và lưu notification; home feed hiển thị các event không gắn farm dưới nhãn “Toàn hệ thống”. Health app/MongoDB/MQTT tốt tại lần kiểm tra, telemetry mới nhất khoảng 12 giây.
- **W3 chưa được xác minh phục hồi thật:** workflow còn đường gọi SSM rồi báo app; chưa có xác nhận command completion, `/healthz` và telemetry MongoDB mới sau hành động. Một lần gọi thủ công bị từ chối trước khi chạy bước nào; không tính là run phục hồi.
- **W6 chưa có heartbeat độc lập:** metric hiện chỉ phát sau khi detector xử lý finding thành công; direct API canary đã nhận metadata nhưng chưa có điểm truy vấn được. Chưa có monitor W6 hữu hiệu.
- W1/W9/W10 monitors được quan sát ở `No Data` trong lần kiểm tra; published workflow, notification thành công hoặc monitor tồn tại riêng lẻ đều chưa chứng minh tự xử lý end-to-end.
- Bằng chứng chi tiết: `outputs/deployment_evidence/smiot_notification_global_feed_20261110.md`, `outputs/deployment_evidence/smiot_w6_metric_gap_20261110.md`, `outputs/workflow_imports/level5_drafts/LIVE_UPDATE_REPORT_20261110.json`.

## 25. Thiết kế đích: nâng 10 workflow lên Level 5

### Định nghĩa hoàn thành

Level 5 là một luồng xử lý có quyết định dựa trên bằng chứng, không phải chỉ là workflow có nhiều bước. Mỗi ca phải theo được cùng một `incident_id` từ monitor → điều tra Bits → đối chiếu nguồn → hành động đúng hoặc từ chối an toàn → kiểm tra hậu hành động → cập nhật incident và thông báo app. Nếu thiếu nguồn, mẫu quá cũ, kết quả mơ hồ, action timeout hoặc kiểm tra hậu xử lý thất bại thì giữ incident mở với trạng thái `unknown`/`pending` và chuyển người xử lý; không báo `recovered`.

Datadog Bits Investigation và Workflow Automation là hai nhánh phản ứng độc lập từ alert: Bits phân tích nguyên nhân; workflow thực hiện guard/action/verification. Không giả định workflow tự nhận được kết luận ngôn ngữ tự nhiên của Bits nếu chưa có tích hợp tường minh. Bật “Investigate with Bits” cho monitor cần thực hiện và kiểm tra trong giao diện; cấu hình này hiện không được biểu diễn bằng workflow JSON/Terraform. Tham khảo [Bits investigations](https://docs.datadoghq.com/bits_ai/bits_investigation/investigate_issues/), [workflow triggers](https://docs.datadoghq.com/actions/workflows/trigger/) và [workflow building blocks](https://docs.datadoghq.com/actions/workflows/build/).

### Hợp đồng chung cho cả 10 ca

1. Monitor phát hiện triệu chứng có ý nghĩa; event mang `incident_id`, `farm_id`, `node_id`, `scenario_id` khi có. Không đưa `incident_id` vào metric tags vì cardinality cao; dùng log/span/event và MongoDB để nối chi tiết.
2. Bits điều tra metrics, logs, traces và bối cảnh dịch vụ/host. Workflow tự lấy các tín hiệu định lượng cần cho guard, không dựa vào Bits để tự sinh lệnh.
3. Guard kiểm tra dữ liệu mới, phạm vi tài nguyên, idempotency, cooldown, dependency health và quyền hành động. Từ chối an toàn là kết quả hợp lệ và phải ghi lý do.
4. Action giới hạn trong allowlist, có timeout và chống lặp. Thao tác vật lý/điều khiển nông học cần ngưỡng đã duyệt; nếu chưa có thì yêu cầu người duyệt.
5. Verification kiểm tra health và bằng chứng mới sau action (ACK, trace, telemetry được ghi MongoDB); so với mốc trước action. Chỉ verifier mới được ghi `recovered`/CLEAR.
6. Mọi nhánh kết thúc gửi notification vào app và lưu run/result. Lỗi action, timeout, dữ liệu không đủ hoặc verifier lỗi phải để incident mở và thông báo cần người xử lý.

### Thiết kế 10 workflow

| Workflow | Trigger và điều tra Bits | Guard, hành động hoặc từ chối an toàn | Điều kiện xác minh Level 5 |
|---|---|---|---|
| **W1 — PLC Safety Trip** | Trip/command mismatch; điều tra PLC state, command/ACK logs, trace và `action_ledger` MongoDB. | Giữ output ở safe-stop/latch; không tự bật bơm/van. Thiếu ACK hoặc ledger thì escalate. | Trip và ACK khớp; không có lệnh ON sau trip; action ledger lưu đúng `incident_id`; app báo kết quả. |
| **W2 — Sensor Flatline** | Mẫu lặp/sequence đứng; đối chiếu Mongo time series, sequence/`boot_id`, MQTT ingress, node logs và ingest trace để phân biệt sensor, node, mạng hay DB. | Đặt/HOLD quyết định tưới tại app/PLC; không tuyên bố đầu dò vật lý hỏng và không CLEAR từ Datadog. | Nhiều mẫu mới, sequence tăng, giá trị biến thiên hợp lệ được Mongo ghi sau mốc HOLD; verifier app mới giải phóng HOLD. |
| **W3 — EC2 App Recovery** | App inactive; Bits đối chiếu systemd, CPU/RAM/disk, app logs/APM, Mongo ping, MQTT health và tuổi telemetry. | Chỉ start `smiot.service` khi đúng instance, service thật sự inactive, dependencies healthy và disk guard đạt; không reboot EC2 hay restart Mongo/MQTT. | Kết quả SSM terminal thành công; `/healthz` tốt; telemetry MongoDB mới hơn mốc trước action; monitor hồi OK. Nếu thiếu bất kỳ dấu hiệu nào, giữ pending. |
| **W4 — Status Mismatch / Refuse Restart** | UI báo offline nhưng Mongo sample mới và app health tốt; Bits so status, sequence, source logs và trace. | Từ chối restart khi dữ liệu còn mới/backend khỏe; chỉ chuyển sang recovery workflow khi app thực sự down. | Ghi `REFUSED_RESTART` và lý do; chứng minh không gửi SSM action; telemetry mới tiếp tục vào và monitor hồi OK. |
| **W5 — MongoDB/MQTT Dependency Triage** | Dependency signal; Bits phân biệt broker, DB hoặc app bằng MQTT ACK, DB ping/write, logs và traces. | Chọn đúng runbook chuyên biệt khi một nguyên nhân rõ và guard đạt; nếu mơ hồ thì không restart hàng loạt, escalate. | Dependency lỗi được chọn đã khỏe; test publish/consume hoặc write/read thành công; sample mới vào MongoDB; lưu kết luận và action. |
| **W6 — Detector Health** | Heartbeat định kỳ độc lập với kết quả detector; Bits đối chiếu heartbeat, input age, process logs và Mongo freshness để phân biệt detector chết với không có input. | Restart đúng detector process tối đa một lần khi dependency khỏe; nếu thiếu heartbeat độc lập hoặc input thì không restart mù. | Heartbeat trở lại, detector xử lý input mới, kết quả được persist; monitor OK. **Trạng thái hiện tại:** chưa đạt do heartbeat chưa độc lập và chưa có metric point truy vấn được. |
| **W7 — Soil Moisture / Irrigation Risk** | Nguy cơ đất hoặc lịch tưới; Bits đối chiếu độ tin cậy/cadence cảm biến, crop stage, lịch, lưu lượng và thời tiết. | Dữ liệu lỗi thì HOLD lịch/chu kỳ tưới. Chỉ đề xuất/thi hành lượng tưới trong envelope theo giai đoạn đã được duyệt; nếu chưa duyệt thì xin người xác nhận. | Lịch/decision có ACK; flow/actuator phản hồi đúng; số đo đất mới sau tưới được lưu; không kết luận hiệu quả chỉ từ lệnh gửi. |
| **W8 — VPD/EC Risk** | VPD/EC ngoài dải; Bits ghép nhiệt độ, độ ẩm không khí, EC, giai đoạn cây, trạng thái quạt và sensor quality. | Sensor mâu thuẫn thì HOLD. Điều khiển quạt/dinh dưỡng chỉ theo giới hạn đã duyệt; nếu không, tạo đề xuất chờ người duyệt. | Thiết bị ACK đúng mục tiêu; số đo khí hậu/EC mới được persist và quay về dải đã duyệt; notification ghi rõ action hay chờ duyệt. |
| **W9 — Actuator No-ACK** | Lệnh không ACK; Bits nối command ID, MQTT publish/consume, timeout, actuator feedback và trace. | Chặn lặp lệnh ON; vào lockout/safe state. Tối đa một retry an toàn nếu policy cho phép, còn lại chuyển người xử lý. | ACK/feedback khớp command ID và trạng thái mục tiêu; ledger idempotent; không còn lệnh lặp treo. |
| **W10 — AI Provider Failure** | Gemini/provider timeout/5xx/latency; Bits đối chiếu LLM span, app logs, fallback/HOLD và quyết định MongoDB. | Mở circuit breaker/chuyển quy tắc dự phòng; nếu không có quyết định hợp lệ thì HOLD. Không dùng quyết định AI cũ để tưới. | Quyết định fallback/HOLD có trace và bản ghi Mongo; app ghi trạng thái; chỉ bật lại provider sau health check ổn định. |

### Ranh giới an toàn và liên kết dữ liệu

- Mỗi ca có `incident_id` duy nhất trong monitor event, workflow run context, log/span, MongoDB incident/action ledger và notification. Metrics chỉ giữ tag có cardinality thấp như `env`, `service`, `farm`, `node`, `scenario`.
- Chỉ nối incident với lô nếu `lot_sensor_assignments`/crop-cycle mapping có hiệu lực tại timestamp sự cố. Không suy ra quan hệ chỉ vì cùng farm hoặc gần thời gian.
- Nhiều lỗi cùng lúc tạo các incident riêng. Chỉ nhóm nguyên nhân khi dependency graph hoặc bằng chứng runtime chỉ ra quan hệ nhân quả; lỗi chia sẻ tài nguyên phải áp dụng interlock chung và tránh chạy hai recovery action cạnh tranh.
- Mọi hành động thiết bị phải được chặn an toàn tại app/PLC; Datadog quan sát và điều phối chậm hơn, không thay thế interlock cục bộ.

### Thứ tự hoàn thiện và tiêu chí nghiệm thu

1. Hoàn thiện đường metric/event và trigger cho monitor `No Data`; riêng W6 tạo heartbeat độc lập trước khi bật monitor.
2. Xác nhận Bits Investigation tự chạy với alert cho từng monitor phù hợp; ghi rõ monitor nào chưa hỗ trợ/đang tắt.
3. Bổ sung guard và verification hậu hành động; W3 trước tiên cần kết quả SSM terminal, `/healthz` và Mongo sample mới trong cùng incident.
4. Chạy từng ca trên simulator/safe mode, rồi đối chiếu workflow run, Bits investigation, log/trace, MongoDB và notification app theo một `incident_id`.
5. Chỉ đánh dấu Level 5 khi có cả đường thành công và nhánh từ chối/escalation đã được kiểm chứng. `Published`, JSON hợp lệ, connection test hoặc notification đơn lẻ không đủ.

Hiện trạng nghiệm thu theo bằng chứng ở ngày 10/11/2026: **10 workflow đã published; notification app được chứng minh bằng hai lượt an toàn W1; chưa có cơ sở gọi cả 10 workflow là Level 5.** W3 chưa có kiểm tra phục hồi sau SSM; W6 còn thiếu heartbeat độc lập/metric point; W1/W9/W10 monitor từng được quan sát `No Data`; các ca điều khiển nông học còn phụ thuộc envelope được duyệt và verification thực tế.
