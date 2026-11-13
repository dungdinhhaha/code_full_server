# Khai báo cho Ban tổ chức (BTC)

Các ô `<ĐIỀN>` do người dùng điền. Không bịa ngày hay thông tin chưa biết.

## 1. Dữ liệu
- Toàn bộ telemetry dùng trong demo và ba ca là **dữ liệu tổng hợp (synthetic)** do chính đội sinh ra (publisher demo `service/demo_mode.py`, cầu nối Wokwi mô phỏng `scripts/wokwi_datadog_bridge.py`, seed demo 30 ngày, lệnh tiêm lỗi demo `scripts/set_demo_sensor_fault.py`; `scripts/set_demo_ui_fault.py` khi được bổ sung). Nguồn được gắn nhãn trong mỗi bản ghi (`source.synthetic`, `source.source`). Dữ liệu demo hiển thị trên giao diện được ghi nhãn **SYNTHETIC**.
- Không có dữ liệu cá nhân hay dữ liệu production của tổ chức nào.
- Không có dataset công khai bên ngoài được sao chép vào dự án: `<ĐIỀN: xác nhận, hoặc liệt kê dataset (tên, nguồn, giấy phép)>`.
- Dự báo thời tiết/GDD dùng API Open-Meteo qua thư viện `openmeteo-requests`: `<ĐIỀN: xác nhận có dùng dữ liệu thời tiết công khai trong bài nộp không>`.
- Ca 2 chỉ chứng minh luồng dữ liệu phù hợp giả thuyết flatline mô phỏng; không khẳng định cảm biến vật lý hỏng hay đã sửa. Bơm/PLC là ảo.

## 2. Công cụ AI đã dùng
| Công cụ | Dùng để làm gì | Phần nào |
|---|---|---|
| Claude Code (Anthropic) | Viết/sửa mã, script, tài liệu, rà soát cấu hình | `<ĐIỀN: liệt kê thư mục/tệp chính>` |
| Gemini API (Gemini Flash-Lite, gọi qua HTTP REST) | Trợ lý hội thoại trong ứng dụng (`service/ai_service.py`, `service/ai_tools.py`) | Tính năng trợ lý khi chạy ứng dụng |
| `<ĐIỀN: công cụ AI khác nếu có, ví dụ Datadog Bits AI>` | `<ĐIỀN>` | `<ĐIỀN>` |

Đầu ra của AI được người dùng xem lại. Nội dung do AI tạo không đảm bảo đúng: `<ĐIỀN: cách đội kiểm chứng>`.
Ứng dụng có tích hợp trợ lý AI (`service/ai_service.py`); theo baseline Datadog A1 hiện **không có** LLM Observability span.

## 3. Thư viện mã nguồn mở (nguồn: `requirements.txt`)
Giấy phép dưới đây chưa được kiểm tra tự động trong phiên này; cột "Giấy phép" cần người dùng xác minh trên PyPI trước khi nộp.

| Thư viện | Ràng buộc phiên bản | Giấy phép |
|---|---|---|
| nicegui | (không ghim) | `<ĐIỀN>` |
| python-docx | (không ghim) | `<ĐIỀN>` |
| openmeteo-requests | (không ghim) | `<ĐIỀN>` |
| pandas | (không ghim) | `<ĐIỀN>` |
| requests-cache | (không ghim) | `<ĐIỀN>` |
| retry-requests | (không ghim) | `<ĐIỀN>` |
| paho-mqtt | (không ghim) | `<ĐIỀN>` |
| psutil | (không ghim) | `<ĐIỀN>` |
| python-dotenv | (không ghim) | `<ĐIỀN>` |
| openpyxl | (không ghim) | `<ĐIỀN>` |
| pymongo | >=4.0,<4.18 | `<ĐIỀN>` |
| ddtrace | >=4.16.1,<5.0 | `<ĐIỀN>` |
| boto3 | >=1.34,<2 | `<ĐIỀN>` |
| qrcode[pil] | >=8.0,<9 | `<ĐIỀN>` |

Phần mềm hạ tầng: MongoDB Community (xem mục 5), Mosquitto (MQTT broker), Datadog Agent, Ubuntu trên EC2. `<ĐIỀN: phiên bản và giấy phép đã xác minh>`

## 4. Thành phần có từ trước 17/10/2026
Cửa sổ build theo điều khoản: 17/10 - 31/10/2026 (BTC đã/chưa dời hạn: xem `docs/SUBMISSION_CHECKLIST.md`). Mọi thành phần tồn tại trước 17/10 phải khai báo.

| Thành phần / thư mục | Có từ trước 17/10? | Ngày commit đầu tiên | Phần bổ sung trong cửa sổ build |
|---|---|---|---|
| Ứng dụng NiceGUI (`main.py`, `pages/`, `service/`) | `<ĐIỀN>` | `<ĐIỀN>` | `<ĐIỀN>` |
| Mô-đun MQTT / ingest | `<ĐIỀN>` | `<ĐIỀN>` | `<ĐIỀN>` |
| Mô hình dữ liệu MongoDB, index | `<ĐIỀN>` | `<ĐIỀN>` | `<ĐIỀN>` |
| Tích hợp Datadog (metrics, monitor, workflow) | `<ĐIỀN>` | `<ĐIỀN>` | `<ĐIỀN>` |
| Script phục hồi có guard (`scripts/aws/*`) | `<ĐIỀN>` | `<ĐIỀN>` | `<ĐIỀN>` |
| Wokwi / thiết bị mô phỏng | `<ĐIỀN>` | `<ĐIỀN>` | `<ĐIỀN>` |
| Tài liệu và playbook | `<ĐIỀN>` | `<ĐIỀN>` | `<ĐIỀN>` |
| Hộp đen sự cố (`service/incident_blackbox.py`, `service/incident_lifecycle.py`) | `<ĐIỀN: người dùng xác nhận>` | `<ĐIỀN>` | `<ĐIỀN: người dùng xác nhận>` |
| Demo synthetic và lệnh tiêm lỗi (`service/demo_mode.py`, `scripts/set_demo_*.py`) | `<ĐIỀN: người dùng xác nhận>` | `<ĐIỀN>` | `<ĐIỀN: người dùng xác nhận>` |

Gợi ý tra cứu ngày: `git log --diff-filter=A --format="%ad %h" -- <đường dẫn>` (người dùng tự chạy và điền).

## 5. MongoDB
- **MongoDB Community Edition, tự quản lý (self-managed) trên EC2.** Không dùng MongoDB Atlas.
- Phiên bản ghi nhận: 8.0.34, chế độ standalone (`<ĐIỀN: xác nhận lại bằng lệnh chỉ đọc>`). Standalone không hỗ trợ transaction và Change Streams; hồ sơ không được tuyên bố các tính năng đó.
- Không dùng Atlas Search, Vector Search, Triggers, Charts hay Stream Processing.

## 6. Cam kết
- Không có secret trong repo/video/ảnh; đã quét lịch sử git: `<ĐIỀN: ngày và công cụ quét>`.
- Người khai báo: `<ĐIỀN: tên, vai trò>`; ngày: `<ĐIỀN>`.
