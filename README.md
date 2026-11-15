# SMIOT Smart Farm

Hệ thống giám sát nhà kính IoT thông minh — phát hiện sự cố tự động, phản ứng end-to-end và ghi nhận bất biến.

## Kiến trúc

| Thành phần | Vai trò |
|---|---|
| **NiceGUI** | Web app — dashboard, quản lý sự cố, điều khiển thiết bị, mùa vụ |
| **Datadog** | Monitor giám sát 24/7, Workflow xử lý tự động, Log + APM Trace điều tra |
| **MongoDB** | Incident document, action_ledger append-only, telemetry, crop_cycles |

## Tính năng chính

- Dashboard tổng quan 10 nhà kính, số đo real-time
- Quản lý sự cố 3 pha: Phát hiện → Điều tra → Phản ứng
- Tự động fix lỗi qua Datadog Workflow (false alarm, sensor hỏng, service down)
- Điều khiển bơm, biến tần, lịch tưới từ xa qua PLC
- Mùa vụ & truy xuất nguồn gốc (QR code)
- Kết nối Datadog portal (monitor, workflow, log, LLM Observability)

## Yêu cầu

- Python 3.10+
- MongoDB (local hoặc remote)
- Datadog Agent (trên server giám sát)
- Datadog API/APP key

## Cài đặt

```bash
git clone https://github.com/dungdinhhaha/code_full_server.git
cd code_full_server
pip install -r requirements.txt
```

## Biến môi trường

Tạo file `.env` hoặc export:

```
MONGODB_URI=mongodb://localhost:27017
DD_API_KEY=<your-datadog-api-key>
DD_APP_KEY=<your-datadog-app-key>
DD_SITE=ap1.datadoghq.com
```

## Chạy

```bash
python main.py
```

App chạy tại `http://localhost:8080`.

## Cấu trúc thư mục

```
main.py                 # Entry point — NiceGUI app
pages/                  # Các trang UI (tab)
components/             # UI components (cards, layout)
service/                # Business logic, MongoDB, Datadog, AI
scripts/                # Script tiện ích (demo scenario, seed data, probe)
tests/                  # Test suite
deploy/                 # Datadog terraform config
infra/                  # Telemetry & workflow infra
velxio/                 # Wokwi IoT node simulation
docs/                   # Tài liệu nộp bài & use case
outputs/                # Kết quả demo, submission
```

## Tech Stack

- **Backend/Frontend**: NiceGUI (Python)
- **Database**: MongoDB
- **Observability**: Datadog (APM, Log, Monitor, Workflow, LLM Obs)
- **IoT Simulation**: Wokwi ESP32
- **Cloud**: AWS EC2
- **Tracing**: ddtrace

## License

MIT
