# INC-<ID>_EVIDENCE.md - mẫu hồ sơ sự cố (chuẩn 6 câu)

Sao chép file này thành `docs/INC-SMIOT-<YYYYMMDDThhmmss>-<8HEX>_EVIDENCE.md`. Xóa các dòng hướng dẫn. Không ghi secret, URI, IP công khai, email.

## Phạm vi và kết luận
- Mã sự cố: `INC-SMIOT-...`
- Ca: 1 / 2 / 3
- Dữ liệu: tổng hợp (synthetic), nguồn: `<smiot_demo_stream | wokwi_synthetic | ...>`
- Kết luận một đoạn. Nêu rõ giới hạn: không chứng minh thiết bị vật lý hỏng/sửa; Bits `<đã/chưa>` xác nhận phục hồi.

## Timeline (UTC; ghi thêm ICT UTC+7)
| UTC | ICT | Sự kiện | Nguồn (monitor/log/doc) |
|---|---|---|---|
| | | Bắt đầu (T0) | |
| | | Monitor Alert | monitor `<ID>` |
| | | Hành động (HOLD / từ chối restart / start) | workflow `<execution id>` |
| | | Mẫu phục hồi đầu tiên | |
| | | Monitor OK / Recovered | |

## Sáu câu
1. **Chuyện gì xảy ra?** (triệu chứng quan sát được, không phải nguyên nhân phỏng đoán)
   - Trả lời:
   - Bằng chứng:
2. **Phát hiện lúc nào?** (thời điểm monitor Alert, ID monitor, độ trễ so với T0)
   - Trả lời:
   - Bằng chứng:
3. **Bằng chứng gốc là gì?** (log/metric/trace/doc MongoDB cụ thể kèm query)
   - Trả lời:
   - Query/Link:
4. **Lô/khoảng dữ liệu nào bị ảnh hưởng?** (farm, node, lô nếu có mapping tổng hợp, khoảng thời gian, số bản ghi từ Aggregation Pipeline)
   - Trả lời:
   - Pipeline/kết quả:
5. **Vì sao chọn hành động này?** (phương án đã loại trừ, rủi ro)
   - Trả lời:
   - Phương án loại trừ:
6. **Dữ liệu nào chứng minh đã phục hồi?** (monitor Recovered + mẫu/metric mới sau thời điểm X)
   - Trả lời:
   - Bằng chứng:

## Liên kết bằng chứng
- Monitor: 
- Log (`@incident.id`): 
- APM trace (`@incident.id`): 
- Workflow execution: 
- Bits Investigation (nếu có; ghi trạng thái xác nhận): 
- MongoDB: collection `<operational_incidents | action_ledger | telemetry | ...>`, filter `<...>`
- File evidence drill (nếu có): `outputs/drill_ca3_<utc>.json`

## Giới hạn
- 
- 

## Số đo (chỉ ghi nếu có nguồn đo; không ước tính)
| Chỉ số | Giá trị | Nguồn đo |
|---|---|---|
| Thời gian phát hiện | | |
| Thời gian vào trạng thái an toàn | | |
| Số lần restart | | |
| Giờ dữ liệu không đáng tin | | |
