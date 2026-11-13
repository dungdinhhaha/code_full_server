| Mục | Vị trí | Kết quả | Đoạn trích |
|---|---|---|---|
| operational_incidents ghi từ incident_lifecycle.py | service/incident_lifecycle.py | đạt | incidents.insert_one(incident) (dòng 95); collection("operational_incidents").update_one(...) |
| incident_telemetry_evidence ghi từ scenario_evidence.py | service/scenario_evidence.py | đạt | db["incident_telemetry_evidence"].update_one( (dòng 183) |
| crop_cycles ghi từ demo_mode.py | service/demo_mode.py | còn lỗi | Chỉ tìm thấy find_one collection("crop_cycles") (dòng 173); không có lệnh ghi |
| crop_stage_media ghi từ traceability.py | service/traceability.py | còn lỗi | Chỉ tìm thấy find collection("crop_stage_media") (dòng 50); không có lệnh ghi |
| lot_sensor_assignments ghi từ scenario_evidence.py | service/scenario_evidence.py | còn lỗi | scenario_evidence.py chỉ có find_one db["lot_sensor_assignments"] (dòng 205); lệnh ghi nằm ở service/incident_lifecycle.py dòng 44 |
| action_ledger ghi từ operational_evidence.py | service/operational_evidence.py | đạt | ledger = collection("action_ledger") (dòng 41); ledger.update_one(query, {"$set": doc, ...}) (dòng 94) |
| action_ledger ghi từ incident_lifecycle.py | service/incident_lifecycle.py | còn lỗi | Chỉ tìm thấy find_one collection("action_ledger") (dòng 335); không có lệnh ghi |
| action_ledger ghi từ main.py | main.py | còn lỗi | Chỉ tìm thấy find_one db["action_ledger"] (dòng 589); không có lệnh ghi |
| service/incident_blackbox.py không là nguồn ghi | Bảng 2, cột Nguồn ghi | đạt | Không có dòng Bảng 2 nào trỏ tới service/incident_blackbox.py trong cột Nguồn ghi |
| $unionWith: 7 nhánh (không phải 4) | Mục 5; Bảng 5 | đạt | Văn bản: 'dùng 7 nhánh $unionWith'; mã: 7 lệnh $unionWith tại service/incident_blackbox.py dòng 345, 359, 373, 391, 412, 427, 472 |
| Không có: cuộc thi | Toàn văn hồ sơ (đoạn và bảng) | đạt | Số lần khớp: 0 |
| Không có: chuyên ngành | Toàn văn hồ sơ (đoạn và bảng) | đạt | Số lần khớp: 0 |
| Không có: chưa làm | Toàn văn hồ sơ (đoạn và bảng) | đạt | Số lần khớp: 0 |
| Không có: đang bổ sung | Toàn văn hồ sơ (đoạn và bảng) | đạt | Số lần khớp: 0 |
| Không có: email | Toàn văn hồ sơ (đoạn và bảng) | đạt | Số lần khớp: 0 |
| Không có: IP | Toàn văn hồ sơ (đoạn và bảng) | đạt | Số lần khớp: 0 |
| Không có: mongodb:// | Toàn văn hồ sơ (đoạn và bảng) | đạt | Số lần khớp: 0 |
| Không có: giá trị bí mật | Toàn văn hồ sơ (đoạn và bảng) | đạt | Số lần khớp: 0 |
