"""pages/devices.py - Hồ sơ thiết bị của hệ thống SMIOT.

DEVICES là catalog tĩnh, lấy từ tài liệu thiết bị. Đây là thông số tham khảo của
thiết bị ảo, không phải phần cứng lắp đặt tại nhà màng.
"""

from datetime import date, datetime

from nicegui import app, ui

from components.ui_kit import facts, page_header, sim_badge, state_panel, status_chip
from pages.home import CUSTOM_CSS, sidebar, global_topbar
from pages.login import check_login
from service.auth import get_latest_flow, get_latest_node
from service.farm_registry import FARM_LABELS
from service.mongodb_store import collection

# ─────────────────────────────────────────────
# DEVICES DATA — ảnh từ Word, thông số tra cứu
# ─────────────────────────────────────────────
DEVICES = [
    {
        "id": 1,
        "name": "Module SIMATIC IOT2050",
        "model": "6ES7647-0BA00-0YA2",
        "category": "GATEWAY / IOT MODULE",
        "cat_color": "var(--sm-vine)",
        "image": "/static/device_images/device_8_image1.jpg",
        "short": "CPU Intel Atom® x6413E, RAM 4GB, eMMC 32GB, 2×RJ45, USB, RS485",
        "specs": {
            "CPU": "Intel Atom® x6413E (Elkhart Lake), 1.5 GHz (Boost 3.0 GHz)",
            "RAM": "4 GB LPDDR4x",
            "Lưu trữ": "32 GB eMMC + MicroSD",
            "Giao tiếp": "2 × RJ45 Gigabit, 2 × USB 3.0, RS232/422/485, PCIe Mini",
            "Hệ điều hành": "Yocto Linux / Ubuntu",
            "Nguồn": "24 VDC (10.8 – 28.8 V), max 9 W",
            "Nhiệt độ": "−20 °C đến +60 °C",
            "Bảo vệ": "IP20",
            "Ứng dụng": "MQTT gateway, Edge AI, Node-RED, Python IoT",
        },
        "description": "Máy tính công nghiệp IoT Siemens — hub trung tâm của hệ thống SMIOT. Thu thập, xử lý và chuyển tiếp dữ liệu cảm biến lên cloud.",
    },
    {
        "id": 2,
        "name": "Bộ lập trình LOGO! 230RCE Siemens",
        "model": "6ED1052-1FB08-0BA2",
        "category": "LOGIC MODULE / PLC MINI",
        "cat_color": "var(--sm-info)",
        "image": "/static/device_images/device_9_image2.jpeg",
        "short": "Nguồn cấp: 115–230V AC/DC, Ngõ vào: 8 DI, Ngõ ra: 4 Relay, Ethernet",
        "specs": {
            "Nguồn": "120/240 VAC hoặc 24 VDC",
            "Ngõ vào số": "8 DI (4 có thể là AI 0–10V)",
            "Ngõ ra số": "4 × Relay (8 A / 240 VAC)",
            "Kết nối": "Ethernet RJ45 (Modbus TCP, Web Server)",
            "Lập trình": "LOGO! Soft Comfort (FBD / LAD)",
            "Bộ nhớ": "400 khối chức năng",
            "Nhiệt độ": "0 °C đến +55 °C",
            "Bảo vệ": "IP20",
        },
        "description": "PLC nhỏ gọn Siemens điều khiển logic bơm tưới và các ngõ ra điện. Nhận lệnh từ IOT2050 qua Modbus TCP.",
    },
    {
        "id": 3,
        "name": "Module mở rộng DM8 Logo! 230RC Siemens",
        "model": "6ED1055-1FB00-0BA1",
        "category": "EXPANSION MODULE",
        "cat_color": "var(--sm-info)",
        "image": "/static/device_images/device_10_image3.jpg",
        "short": "Nguồn cấp: 230V AC/DC, Ngõ vào số: 4 DI (230V AC), Ngõ ra: 4 Relay",
        "specs": {
            "Ngõ vào số": "4 DI (120/240 VAC)",
            "Ngõ ra số": "4 × Relay (10 A / 240 VAC)",
            "Kết nối với Logo!": "Cáp nối trực tiếp (giao tiếp nội bộ)",
            "Nguồn": "120/240 VAC",
            "Nhiệt độ": "0 °C đến +55 °C",
            "Bảo vệ": "IP20",
        },
        "description": "Module mở rộng thêm 4 DI / 4 DO cho Logo! 230RCE khi số lượng I/O không đủ cho hệ thống.",
    },
    {
        "id": 4,
        "name": "Biến tần INVT GD20",
        "model": "GD20-0R7G-S2-BK",
        "category": "INVERTER (BIẾN TẦN)",
        "cat_color": "var(--sm-watch)",
        "image": "/static/device_images/device_11_image4.jfif",
        "short": "Công suất: 0.75kW (1HP), Điện áp vào: 1 Pha 220VAC, RS485 Modbus",
        "specs": {
            "Công suất": "0.75 kW (1 HP)",
            "Nguồn vào": "220 VAC ± 15%, 1 Pha",
            "Điện áp ra": "0 – 220 VAC, 3 Pha",
            "Tần số ra": "0 – 400 Hz",
            "Giao tiếp": "RS485 (Modbus RTU)",
            "Điều khiển": "Vector control V/F",
            "Bảo vệ": "IP20",
            "Chứng nhận": "CE, CCC",
        },
        "description": "Biến tần điều khiển tốc độ động cơ bơm nước qua RS485-Modbus. Cho phép điều chỉnh lưu lượng bơm chính xác.",
    },
    {
        "id": 5,
        "name": "Cảm biến pH DFRobot Gravity V2",
        "model": "SEN0169-V2",
        "category": "CẢM BIẾN NƯỚC",
        "cat_color": "var(--sm-vine-deep)",
        "image": "/static/device_images/device_7_image5.jfif",
        "short": "Dải đo: 0–14 pH, Tín hiệu Analog 0–3V, Cấp nguồn 3.3–5.5V",
        "specs": {
            "Dải đo": "0 – 14 pH",
            "Độ chính xác": "± 0.1 pH (25 °C)",
            "Tín hiệu ra": "Analog 0 – 3.0 V",
            "Điện áp cấp": "3.3 – 5.5 VDC",
            "Nhiệt độ": "5 °C đến +60 °C",
            "Hiệu chuẩn": "2-point / 3-point calibration",
        },
        "calibration": {
            "last": "15/04/2026",
            "cycle": "6 tháng",
            "next": "15/10/2026",
            "guide": "Sử dụng dung dịch chuẩn pH 4.00, 7.00 và 10.00 để hiệu chuẩn 3 điểm."
        },
        "description": "Cảm biến đo độ pH nước tưới, kết nối Analog vào ESP32. Dữ liệu gửi qua MQTT lên IOT2050.",
    },
    {
        "id": 6,
        "name": "Cảm biến EC DFRobot Gravity V2 (K=1)",
        "model": "DFR0300-H",
        "category": "CẢM BIẾN NƯỚC",
        "cat_color": "var(--sm-vine-deep)",
        "image": "/static/device_images/device_6_image6.jfif",
        "short": "Dải đo: 0–20 mS/cm, Tự bù nhiệt độ, Tín hiệu Analog 0–3.4V",
        "specs": {
            "Dải đo": "0 – 20 mS/cm",
            "Độ chính xác": "± 5% FS",
            "Tín hiệu ra": "Analog 0 – 3.4 V",
            "Điện áp cấp": "3.3 – 5.5 VDC",
            "Bù nhiệt độ": "Tự động (NTC)",
            "Nhiệt độ": "0 °C đến +40 °C",
        },
        "calibration": {
            "last": "16/04/2026",
            "cycle": "6 tháng",
            "next": "16/10/2026",
            "guide": "Hiệu chuẩn với dung dịch chuẩn 1413 μS/cm hoặc 12.88 mS/cm."
        },
        "description": "Cảm biến độ dẫn điện (EC) dung dịch dinh dưỡng / nước tưới — quan trọng cho canh tác nhà màng.",
    },
    {
        "id": 7,
        "name": "Cảm biến đất 3 trong 1 ES-SM-THEC-01",
        "model": "ES-SM-THEC-01",
        "category": "CẢM BIẾN ĐẤT",
        "cat_color": "var(--sm-ok)",
        "image": "/static/device_images/device_5_image7.jpeg",
        "short": "Đo: Nhiệt độ + Độ ẩm + EC đất, RS485 Modbus RTU, IP68",
        "specs": {
            "Thông số": "Nhiệt độ đất, Độ ẩm đất, EC đất",
            "Giao tiếp": "RS485 Modbus RTU",
            "Điện áp cấp": "12 – 24 VDC",
            "Dải đo nhiệt độ": "−20 °C đến +80 °C (± 0.5 °C)",
            "Dải đo độ ẩm": "0 – 100% (± 3%)",
            "Dải đo EC": "0 – 20 000 μS/cm",
            "Bảo vệ": "IP68",
        },
        "calibration": {
            "last": "12/02/2026",
            "cycle": "12 tháng",
            "next": "12/02/2027",
            "guide": "Làm sạch đầu dò bằng cồn và kiểm tra độ chính xác trong đất chuẩn."
        },
        "description": "Cảm biến 3 trong 1 cắm vào đất: đo nhiệt độ, độ ẩm và EC đất qua RS485 Modbus RTU.",
    },
    {
        "id": 8,
        "name": "Cảm biến Nhiệt Độ & Độ Ẩm SHT20 RS485",
        "model": "SHT20-RS485",
        "category": "CẢM BIẾN KHÔNG KHÍ",
        "cat_color": "var(--sm-info)",
        "image": "/static/device_images/device_1_image8.jfif",
        "short": "Đo: Nhiệt độ (±0.3°C) + Độ ẩm (±3%), RS485, IP65",
        "specs": {
            "Giao tiếp": "RS485 Modbus RTU",
            "Dải đo nhiệt độ": "−40 °C đến +125 °C (± 0.3 °C)",
            "Dải đo độ ẩm": "0 – 100% RH (± 3% RH)",
            "Điện áp cấp": "5 – 30 VDC",
            "Baud rate": "9600 bps",
            "Bảo vệ": "IP65",
        },
        "calibration": {
            "last": "08/03/2026",
            "cycle": "12 tháng",
            "next": "08/03/2027",
            "guide": "Đặt trong hộp chuẩn ẩm độ muối bão hòa để căn chỉnh sai lệch."
        },
        "description": "Cảm biến T&H không khí RS485 trong nhà màng. Đọc bởi ESP32 và gửi MQTT lên IOT2050.",
    },
    {
        "id": 9,
        "name": "ESP32 Dev Kit V1",
        "model": "ESP32-WROOM-32",
        "category": "VI ĐIỀU KHIỂN / GATEWAY",
        "cat_color": "var(--sm-act)",
        "image": "/static/device_images/device_2_image9.jfif",
        "short": "Dual-core 240MHz, WiFi + BLE, 38 GPIO, ADC 12-bit, RS485, MQTT",
        "specs": {
            "CPU": "Xtensa® LX6 dual-core 240 MHz",
            "Flash / RAM": "4 MB / 520 KB SRAM",
            "WiFi": "802.11 b/g/n (2.4 GHz)",
            "Bluetooth": "BLE 4.2",
            "GPIO": "38 chân (12 ADC, 2 DAC, UART, SPI, I²C, PWM)",
            "Giao tiếp cảm biến": "UART RS485, ADC (pH, EC)",
            "Điện áp": "3.3 VDC logic, USB 5V",
            "Lập trình": "Arduino IDE / MicroPython",
        },
        "description": "Vi điều khiển chính: thu thập dữ liệu toàn bộ cảm biến (RS485 + ADC) và truyền lên MQTT qua WiFi.",
    },
    {
        "id": 10,
        "name": "Cảm Biến Lưu Lượng YF-G1",
        "model": "YF-G1",
        "category": "CẢM BIẾN LƯU LƯỢNG",
        "cat_color": "var(--sm-net)",
        "image": "/static/device_images/device_3_image10.jpeg",
        "short": "Dải đo: 1–30 L/phút, Kết nối G1″, Tín hiệu xung Hall effect",
        "specs": {
            "Nguyên lý": "Hall effect (cánh quạt từ)",
            "Dải đo": "1 – 30 L/phút",
            "Kết nối ống": "G1″ (1 inch)",
            "Điện áp cấp": "5 – 18 VDC",
            "Tín hiệu ra": "Xung vuông, ~450 xung/lít",
            "Áp suất tối đa": "1.75 MPa",
            "Nhiệt độ chất lỏng": "≤ 120 °C",
        },
        "calibration": {
            "last": "10/01/2026",
            "cycle": "12 tháng",
            "next": "10/01/2027",
            "guide": "Đo đong thể tích thực tế và hiệu chỉnh hệ số K-factor trên ESP32."
        },
        "description": "Đồng hồ đo lưu lượng nước qua ống. Tín hiệu xung đọc bởi ESP32 để tính L/min và tổng L.",
    },
    {
        "id": 11,
        "name": "Cảm Biến Áp Suất TITEC",
        "model": "TITEC – Germany",
        "category": "CẢM BIẾN ÁP SUẤT",
        "cat_color": "var(--sm-info)",
        "image": "/static/device_images/device_4_image11.jfif",
        "short": "Tín hiệu: 4–20mA, Dải đo: 0–10 Bar, Nguồn: 24VDC, IP67",
        "specs": {
            "Tín hiệu ra": "4 – 20 mA (2-wire)",
            "Dải đo": "0 – 10 bar",
            "Nguồn cấp": "24 VDC",
            "Kết nối": "G1/4″ BSP",
            "Sai số": "± 0.5% FS",
            "Bảo vệ": "IP67",
            "Chứng nhận": "CE",
        },
        "calibration": {
            "last": "05/03/2026",
            "cycle": "12 tháng",
            "next": "05/03/2027",
            "guide": "So sánh giá trị với đồng hồ áp suất cơ học chuẩn tại điểm 0 và 3.0 BAR."
        },
        "description": "Cảm biến áp suất nước đường ống tưới nhỏ giọt. 4–20 mA → quy đổi áp suất → gửi IOT2050.",
    },
    {
        "id": 12,
        "name": "Node IoT giám sát môi trường",
        "model": "Custom ESP32 Node",
        "category": "NODE IOT",
        "cat_color": "var(--sm-ok)",
        "image": "/static/device_images/device_12_image12.png",
        "short": "ESP32 + SHT20 + ES-SM-THEC-01, WiFi MQTT, chu kỳ 10 giây",
        "specs": {
            "Vi điều khiển": "ESP32 Dev Kit V1",
            "Cảm biến tích hợp": "SHT20 (T&H KK) + ES-SM-THEC-01 (đất 3 in 1)",
            "Kết nối": "WiFi 2.4 GHz → MQTT Broker",
            "Giao tiếp cảm biến": "RS485 Modbus RTU",
            "Nguồn": "12 VDC",
            "Chu kỳ gửi": "10 giây",
            "Topic MQTT": "smiot/node1/, smiot/node2/",
        },
        "description": "Node IoT đặt trong nhà màng hoặc ngoài nhà màng, thu thập dữ liệu đất và không khí, gửi về MQTT broker mỗi 10 giây.",
    },
]

DEVICE_CSS = """
.dev-bar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between;
           padding: 12px; margin: 16px 0; background: var(--sm-sunken);
           border: 1px solid var(--sm-net-soft); border-radius: var(--sm-r-m); }
.dev-search { width: 100%; max-width: 360px; }
.dev-chip { border: 1px solid var(--sm-net-soft); border-radius: var(--sm-r-s); background: var(--sm-surface);
            color: var(--sm-ink-2); font-size: 12px; font-weight: 600; padding: 4px 12px; }
.dev-chip.on { background: var(--sm-vine); border-color: var(--sm-vine); color: var(--sm-surface); }
.device-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.device-card { display: flex; flex-direction: column; min-width: 0; background: var(--sm-surface);
               border: 1px solid var(--sm-net-soft); border-radius: var(--sm-r-m); overflow: hidden; }
.device-img-wrap { width: 100%; aspect-ratio: 1 / 1; background: var(--sm-sunken); display: flex;
                   align-items: center; justify-content: center; padding: 16px; overflow: hidden; }
.device-img-wrap img { max-width: 100%; max-height: 100%; object-fit: contain; }
.device-card-body { padding: 14px 16px 16px; flex: 1; display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.device-cat { font-size: 11px; font-weight: 600; }
.device-name { font-size: 14px; font-weight: 700; color: var(--sm-ink); line-height: 1.4; }
.device-short { font-size: 12px; color: var(--sm-ink-3); line-height: 1.5; flex: 1;
                display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.device-btn { margin-top: 12px; width: 100%; border: 1px solid var(--sm-net); border-radius: var(--sm-r-s);
              color: var(--sm-ink); font-size: 12px; font-weight: 600; }
.dev-detail { display: grid; grid-template-columns: 300px minmax(0, 1fr); }
.dev-detail-img { background: var(--sm-sunken); display: flex; align-items: center; justify-content: center; padding: 24px; }
.dev-detail-img img { max-width: 100%; max-height: 100%; object-fit: contain; background: var(--sm-surface); }
.dev-detail-info { padding: 24px; display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.dev-note { font-size: 13px; color: var(--sm-ink-2); line-height: 1.5; }
.dev-block { display: flex; flex-direction: column; gap: 6px; }
.velxio-panel { margin: 16px 0 20px; padding: 16px; border: 1px solid var(--sm-net-soft); border-radius: var(--sm-r-m); background: linear-gradient(135deg, var(--sm-surface), var(--sm-sunken)); }
.velxio-head { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
.velxio-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-top:12px; }
.velxio-card { padding:14px; border:1px solid var(--sm-net-soft); border-radius:var(--sm-r-s); background:var(--sm-surface); min-width:0; }
.velxio-title { display:flex; align-items:center; gap:8px; font-weight:700; color:var(--sm-ink); }
.velxio-led { width:12px; height:12px; border-radius:50%; flex:0 0 auto; box-shadow:0 0 0 3px color-mix(in srgb, currentColor 15%, transparent); }
.velxio-led.ok { color:#159447; background:#22c55e; }
.velxio-led.warn { color:#d97706; background:#f59e0b; }
.velxio-led.bad { color:#dc2626; background:#ef4444; }
.velxio-led.stale { color:#64748b; background:#94a3b8; }
.velxio-meta { margin-top:8px; font-size:12px; line-height:1.5; color:var(--sm-ink-3); }
.velxio-state { margin-top:8px; font-size:12px; font-weight:700; }
.velxio-circuit { margin-top:14px; border:1px solid var(--sm-net-soft); border-radius:var(--sm-r-s); overflow:hidden; background:#10151b; }
.velxio-circuit-head { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; padding:10px 12px; background:#17202a; color:#f8fafc; }
.velxio-circuit-head .sm-note { color:#cbd5e1; }
.velxio-frame { display:block; width:100%; height:640px; border:0; background:#111827; }
.velxio-frame-viewport { width:100%; height:640px; overflow:hidden; background:#111827; }
.velxio-frame-viewport.pump-preview { height:820px; }
.velxio-frame-viewport.pump-preview .velxio-frame { height:820px; }
.velxio-frame-viewport .velxio-frame { width:1500px; max-width:none; }
.velxio-circuit-foot { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; padding:9px 12px; background:#17202a; color:#cbd5e1; font-size:12px; }
@media (max-width: 720px) { .dev-detail { grid-template-columns: 1fr; } }
@media (max-width: 720px) { .velxio-frame, .velxio-frame-viewport { height: 520px; } .velxio-frame-viewport.pump-preview, .velxio-frame-viewport.pump-preview .velxio-frame { height: 760px; } }
@media (max-width: 720px) { .velxio-frame-viewport .velxio-frame { width:1100px; } }
"""

# Project public thật trên Velxio; đây là mạch ESP32 + DHT22 + cảm biến đất
# được mở từ gói Velxio của SMIOT, không phải ảnh minh họa dựng lại trong app.
VELXIO_PROJECT_URL = "https://velxio.dev/project/a652dc2a-b9f0-4923-8e82-4624509fc39f"
VELXIO_DIRECT_URL = VELXIO_PROJECT_URL
VELXIO_EMBED_URL = "https://velxio.dev/embed/a652dc2a-b9f0-4923-8e82-4624509fc39f"
VELXIO_PUMP_DIRECT_URL = "https://velxio.dev/project/449b7fc8-4980-494e-97b2-b0b43a5281f7"
VELXIO_PUMP_EMBED_URL = "https://velxio.dev/embed/449b7fc8-4980-494e-97b2-b0b43a5281f7"
VELXIO_FLOW_DIRECT_URL = "https://velxio.dev/project/fdc6b941-ade1-4859-8cd9-ef85b3b4598b"
VELXIO_FLOW_EMBED_URL = "https://velxio.dev/embed/fdc6b941-ade1-4859-8cd9-ef85b3b4598b"


def tidy(text: str) -> str:
    """Tiêu đề viết hoa toàn bộ trong dữ liệu -> chữ thường, chỉ viết hoa chữ đầu."""
    return text[:1].upper() + text[1:].lower() if text else ""


def _velxio_snapshot(farm_key: str) -> list[dict]:
    """Đọc mẫu mới nhất từ MongoDB; không dựng trạng thái live cố định."""
    now = datetime.now().astimezone()
    try:
        n1, n2, flow = (get_latest_node(farm_key, 1), get_latest_node(farm_key, 2), get_latest_flow(farm_key))
    except Exception:
        n1 = n2 = flow = None
    rows = []
    for key, label, record, detail in (
        ("node1", "Node 1 · môi trường", n1, "Nhiệt độ/độ ẩm không khí và đất"),
        ("node2", "Node 2 · đất", n2, "Độ ẩm đất và EC"),
        ("flow", "Flow monitor · bơm", flow, "Lưu lượng và phản hồi đường ống"),
    ):
        ts = (record or {}).get("received_at") or (record or {}).get("timestamp")
        age = None
        if ts:
            try:
                parsed = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=now.tzinfo)
                age = max(0.0, (now - parsed).total_seconds())
            except (TypeError, ValueError):
                age = None
        if record is None or age is None:
            state, state_label = "stale", "Chưa có mẫu gần đây"
        elif age > 180:
            state, state_label = "stale", f"Mẫu đã cũ {int(age)} giây"
        elif age > 60:
            state, state_label = "warn", f"Mẫu chậm {int(age)} giây"
        else:
            state, state_label = "ok", "Đang nhận mẫu"
        rows.append({"key": key, "label": label, "detail": detail, "state": state,
                     "state_label": state_label, "record": record})
    return rows


def _latest_device_command(farm_key: str) -> dict | None:
    try:
        return collection("action_ledger").find_one(
            {"farm_key": farm_key},
            {"_id": 0, "command_id": 1, "state": 1, "action_code": 1, "incident_id": 1,
             "scenario_run_id": 1, "updated_at": 1, "acknowledged_at": 1, "verified_at": 1},
            sort=[("updated_at", -1)],
        )
    except Exception:
        return None


def _latest_velxio_profile_events(farm_key: str) -> dict[str, dict]:
    try:
        events = collection("device_profile_events").find(
            {"farm_key": farm_key, "source": "velxio_synthetic", "synthetic": True},
            {"_id": 0, "node_id": 1, "profile": 1, "dataset_id": 1, "applied": 1,
             "verified": 1, "incident_id": 1, "scenario_run_id": 1, "timestamp": 1,
             "received_at": 1},
        ).sort("received_at", -1).limit(30)
        return {str(row.get("node_id")): row for row in events if row.get("node_id")}
    except Exception:
        return {}


def device_shortcut(device: dict) -> tuple[str, str] | None:
    """Lối tắt tới trang điều khiển liên quan: biến tần, hoặc PLC và bơm."""
    category = device.get("category", "").upper()
    if "INVERTER" in category or "BIẾN TẦN" in category:
        return "Mở trang biến tần", "/inverter"
    if "PLC" in category or "LOGIC" in category or "EXPANSION" in category:
        return "Mở trang PLC và bơm", "/plc"
    return None


def calibration_chip(device: dict, today: date):
    """Chip hạn hiệu chuẩn, tính từ ngày thật. Trả về None nếu thiết bị không có hiệu chuẩn."""
    cal = device.get("calibration")
    if not cal:
        return None
    try:
        due = datetime.strptime(cal["next"], "%d/%m/%Y").date()
    except (KeyError, ValueError):
        return status_chip("none", "Chưa rõ hạn hiệu chuẩn")
    days = (due - today).days
    if days < 0:
        return status_chip("watch", f"Quá hạn hiệu chuẩn {-days} ngày")
    return status_chip("watch" if days <= 30 else "ok", f"Còn {days} ngày")


def show_device_detail(device: dict):
    """Hồ sơ chi tiết thiết bị trong hộp thoại."""
    today = date.today()
    with ui.dialog() as dlg, ui.card().props("flat bordered").style(
            "width:820px;max-width:95vw;max-height:90vh;padding:0;overflow:auto"):
        with ui.element("div").classes("dev-detail"):
            with ui.element("div").classes("dev-detail-img"):
                ui.image(device["image"]).style("max-width:100%;max-height:100%;object-fit:contain")

            with ui.element("div").classes("dev-detail-info"):
                with ui.row().classes("w-full items-start justify-between no-wrap"):
                    ui.label(tidy(device["category"])).classes("device-cat").style(f"color:{device['cat_color']}")
                    ui.button(icon="close", on_click=dlg.close).props("flat round dense")
                ui.label(device["name"]).classes("sm-h2")
                ui.label("Thương hiệu và model").classes("sm-note")
                brand_name = device.get("brand", device["name"].split()[0] if device["name"] else "")
                ui.label(f"{brand_name} - {device['model']}").style("font-size:14px;color:var(--sm-ink)")

                ui.label("Thông số kỹ thuật").classes("sm-note")
                facts(device["specs"].items())

                if "calibration" in device:
                    cal = device["calibration"]
                    with ui.element("div").classes("dev-block"):
                        ui.label("Hiệu chuẩn").classes("sm-note")
                        calibration_chip(device, today)
                        facts([("Hiệu chuẩn gần nhất", cal["last"]),
                               ("Chu kỳ", cal["cycle"]),
                               ("Đến hạn", cal["next"]),
                               ("Hướng dẫn", cal["guide"])])

                ui.label(device["description"]).classes("dev-note")

                shortcut = device_shortcut(device)
                if shortcut:
                    ui.link(shortcut[0], shortcut[1]).classes("sm-link")

                ui.button("Đóng", on_click=dlg.close).props("unelevated no-caps").classes("sm-btn").style(
                    "align-self:flex-end;margin-top:auto")
    dlg.open()


# ─────────────────────────────────────────────
# PAGE
# ─────────────────────────────────────────────
@ui.page("/devices")
def trang_devices():
    if not check_login():
        return

    ui.add_head_html(f"<style>{CUSTOM_CSS}{DEVICE_CSS}</style>")
    sidebar(active="Device")

    with ui.element("div").classes("main-content"):
        global_topbar("Thiết bị", "")

        with ui.element("div").classes("content-area"):
            slot = page_header(
                "Thiết bị",
                "Danh mục thiết bị của hệ thống SMIOT.",
            )
            with slot:
                sim_badge()
            ui.label("Đây là hồ sơ thông số tham khảo của thiết bị ảo, không phải phần cứng lắp đặt "
                     "tại nhà màng.").classes("sm-note")

            # Mạch Velxio là vùng tĩnh: không đặt iframe trong refreshable,
            # nếu không mỗi lần đọc MongoDB lại phá phiên mô phỏng và để lại khoảng trắng.
            def velxio_circuit_panel():
                with ui.element("section").classes("velxio-panel"):
                    with ui.element("div").classes("velxio-head"):
                        with ui.element("div"):
                            ui.label("Thiết bị trình diễn · Velxio").classes("sm-h3")
                            ui.label("Bản xem sơ đồ Velxio. Muốn chạy mô phỏng và xem đèn/còi, mở mạch riêng trên Velxio bên dưới.").classes("sm-note")
                        ui.link("Mở điều khiển PLC", "/plc").classes("sm-link")
                    with ui.element("div").classes("velxio-circuit"):
                        with ui.element("div").classes("velxio-circuit-head"):
                            with ui.element("div"):
                                ui.label("Sơ đồ mạch (xem trước)").classes("sm-h3")
                                ui.label("Khung này chỉ xem sơ đồ; phiên chạy và điều khiển nằm trên trang Velxio riêng.").classes("sm-note")
                        with ui.tabs().classes("w-full bg-slate-800 text-white") as circuit_tabs:
                            environment_tab = ui.tab("Node 1 · cảm biến")
                            pump_tab = ui.tab("Node 2 · bơm và LED")
                            flow_tab = ui.tab("Node 3 · lưu lượng")
                        with ui.tab_panels(circuit_tabs, value=environment_tab).classes("w-full p-0"):
                            with ui.tab_panel(environment_tab).classes("p-0"):
                                with ui.element("div").classes("velxio-frame-viewport"):
                                    ui.html(
                                        f'<iframe class="velxio-frame" src="{VELXIO_EMBED_URL}" '
                                        'title="Mạch cảm biến Velxio SMIOT" allow="autoplay; clipboard-read; clipboard-write"></iframe>',
                                        sanitize=False,
                                    )
                            with ui.tab_panel(pump_tab).classes("p-0"):
                                with ui.element("div").classes("velxio-frame-viewport pump-preview"):
                                    ui.html(
                                        f'<iframe class="velxio-frame" src="{VELXIO_PUMP_EMBED_URL}" '
                                        'title="Mạch bơm và LED Velxio SMIOT" allow="autoplay; clipboard-read; clipboard-write"></iframe>',
                                        sanitize=False,
                                    )
                            with ui.tab_panel(flow_tab).classes("p-0"):
                                if VELXIO_FLOW_EMBED_URL:
                                    with ui.element("div").classes("velxio-frame-viewport"):
                                        ui.html(
                                            f'<iframe class="velxio-frame" src="{VELXIO_FLOW_EMBED_URL}" '
                                            'title="Mạch lưu lượng Velxio SMIOT" allow="autoplay; clipboard-read; clipboard-write"></iframe>',
                                            sanitize=False,
                                        )
                                else:
                                    with ui.element("div").classes("velxio-frame-viewport"):
                                        ui.label("Mạch Node 3 đang được chuẩn bị trong Velxio.").classes("sm-note")
                        with ui.element("div").classes("velxio-circuit-foot"):
                            ui.label("Mô phỏng phải chạy riêng trên Velxio; chọn đúng mạch tương ứng với node cần trình diễn.")
                            ui.link("Mở mạch cảm biến ↗", VELXIO_DIRECT_URL).props("target=_blank").classes("sm-link")
                            ui.link("Mở mạch bơm ↗", VELXIO_PUMP_DIRECT_URL).props("target=_blank").classes("sm-link")
                            if VELXIO_FLOW_DIRECT_URL:
                                ui.link("Mở mạch lưu lượng ↗", VELXIO_FLOW_DIRECT_URL).props("target=_blank").classes("sm-link")

            velxio_circuit_panel()

            # Trạng thái MongoDB cập nhật định kỳ, tách khỏi iframe để không reload mạch.
            @ui.refreshable
            def velxio_demo_panel():
                farm_key = app.storage.user.get("current_farm", "greenhouse_a")
                farm_label = FARM_LABELS.get(farm_key, farm_key)
                snapshot = _velxio_snapshot(farm_key)
                latest_cmd = _latest_device_command(farm_key)
                profile_events = _latest_velxio_profile_events(farm_key)
                with ui.element("section").classes("velxio-panel"):
                    with ui.element("div").classes("velxio-head"):
                        with ui.element("div"):
                            ui.label(f"Trạng thái thiết bị · {farm_label}").classes("sm-h3")
                            ui.label("Dữ liệu đọc từ MongoDB, tự làm mới mỗi 10 giây").classes("sm-note")
                        ui.link("Mở điều khiển PLC", "/plc").classes("sm-link")
                    with ui.element("div").classes("velxio-grid"):
                        for item in snapshot:
                            record = item["record"] or {}
                            readings = (record.get("readings") or record) if isinstance(record, dict) else {}
                            with ui.element("article").classes("velxio-card"):
                                with ui.element("div").classes("velxio-title"):
                                    ui.element("span").classes(f"velxio-led {item['state']}")
                                    ui.label(item["label"])
                                ui.label(item["detail"]).classes("velxio-meta")
                                if item["key"] in {"node1", "node2"}:
                                    ui.label(
                                        f"Nhiệt độ {readings.get('air_temp', readings.get('air_temp_c', '—'))} °C · Ẩm đất {readings.get('soil_hum', '—')} %"
                                    ).classes("velxio-meta")
                                else:
                                    ui.label(
                                        f"Lưu lượng {readings.get('flow_f1', '—')} L/ph · Tổng {readings.get('flow_t1', '—')} L"
                                    ).classes("velxio-meta")
                                ui.label(item["state_label"]).classes("velxio-state").style(
                                    f"color:{ {'ok':'#159447','warn':'#b45309','stale':'#64748b'}.get(item['state'], '#64748b')}"
                                )
                                profile = profile_events.get(item["key"], {})
                                if profile:
                                    profile_label = "Bộ lỗi" if profile.get("profile") == "fault" else "Bộ bình thường"
                                    profile_result = "đã xác nhận" if profile.get("verified") else "chưa xác minh"
                                    ui.label(f"{profile_label} · {profile.get('dataset_id') or '—'} · {profile_result}").classes("velxio-meta")
                                else:
                                    ui.label("Bộ dữ liệu: chưa nhận ACK từ Velxio").classes("velxio-meta")
                    if latest_cmd:
                        cmd_state = str(latest_cmd.get("state") or "unknown")
                        incident = latest_cmd.get("incident_id") or latest_cmd.get("scenario_run_id")
                        suffix = f" · mã {incident}" if incident else ""
                        ui.label(f"Lệnh gần nhất: {latest_cmd.get('action_code') or '—'} · {cmd_state}{suffix}").classes("velxio-meta")
                    else:
                        ui.label("Chưa có lệnh gần nhất trong sổ lệnh của farm này.").classes("velxio-meta")

            velxio_demo_panel()
            ui.timer(10.0, velxio_demo_panel.refresh)

            filter_state = {"search": "", "category": "Tất cả"}
            categories = ["Tất cả", "Cảm biến", "Gateway", "Điều khiển"]
            cat_map = {
                "Cảm biến": ["CẢM BIẾN", "SENSOR"],
                "Gateway": ["GATEWAY", "IOT MODULE", "NODE IOT", "VI ĐIỀU KHIỂN"],
                "Điều khiển": ["INVERTER", "PLC", "LOGIC MODULE", "EXPANSION MODULE", "BIẾN TẦN"],
            }

            def pick_category(cat: str):
                filter_state["category"] = cat
                category_chips.refresh()
                device_grid.refresh()

            def on_search(e):
                filter_state["search"] = e.value or ""
                device_grid.refresh()

            with ui.element("div").classes("dev-bar"):
                ui.input(placeholder="Tìm thiết bị, model, tính năng", value="", on_change=on_search) \
                    .props("outlined dense clearable").classes("dev-search")

                @ui.refreshable
                def category_chips():
                    with ui.row().classes("items-center gap-2 flex-wrap"):
                        for cat in categories:
                            active = filter_state["category"] == cat
                            ui.button(cat, on_click=lambda c=cat: pick_category(c)) \
                                .props("flat no-caps dense") \
                                .classes("dev-chip on" if active else "dev-chip")

                category_chips()

            @ui.refreshable
            def device_grid():
                search_query = filter_state["search"].strip().lower()
                selected_cat = filter_state["category"]
                filtered = DEVICES
                if search_query:
                    filtered = [
                        d for d in filtered
                        if search_query in d["name"].lower()
                        or search_query in d["model"].lower()
                        or search_query in d["category"].lower()
                        or search_query in d["description"].lower()
                        or search_query in d["short"].lower()
                    ]
                if selected_cat != "Tất cả":
                    sub_keywords = cat_map.get(selected_cat, [])
                    filtered = [
                        d for d in filtered
                        if any(kw in d["category"].upper() or kw in d["name"].upper() for kw in sub_keywords)
                    ]

                if not filtered:
                    state_panel("empty", "Không tìm thấy thiết bị phù hợp",
                                "Thử từ khóa khác hoặc chọn nhóm Tất cả.")
                    return

                today = date.today()
                with ui.element("div").classes("device-grid"):
                    for d in filtered:
                        with ui.element("article").classes("device-card"):
                            with ui.element("div").classes("device-img-wrap"):
                                ui.image(d["image"]).style("max-width:100%;max-height:100%;object-fit:contain")
                            with ui.element("div").classes("device-card-body"):
                                ui.label(tidy(d["category"])).classes("device-cat").style(f"color:{d['cat_color']}")
                                ui.label(d["name"]).classes("device-name")
                                ui.label(d["short"]).classes("device-short")
                                with ui.row().classes("items-center gap-2 flex-wrap").style("margin-top:6px"):
                                    calibration_chip(d, today)
                                shortcut = device_shortcut(d)
                                if shortcut:
                                    ui.link(shortcut[0], shortcut[1]).classes("sm-link").style("font-size:12px")
                                ui.button("Xem chi tiết", on_click=lambda dev=d: show_device_detail(dev)) \
                                    .props("flat no-caps").classes("device-btn")

            device_grid()
