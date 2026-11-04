from nicegui import ui
from pages.home import CUSTOM_CSS, sidebar, global_topbar
from pages.login import check_login

# ─────────────────────────────────────────────
# DEVICES DATA — ảnh từ Word, thông số tra cứu
# ─────────────────────────────────────────────
DEVICES = [
    {
        "id": 1,
        "name": "Module SIMATIC IOT2050",
        "model": "6ES7647-0BA00-0YA2",
        "category": "GATEWAY / IOT MODULE",
        "cat_color": "#4361ee",
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
        "cat_color": "#00b4d8",
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
        "cat_color": "#00b4d8",
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
        "cat_color": "#f77f00",
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
        "cat_color": "#7c3aed",
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
        "cat_color": "#7c3aed",
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
        "cat_color": "#20bf6b",
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
        "cat_color": "#4cc9f0",
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
        "cat_color": "#ef233c",
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
        "cat_color": "#2ec4b6",
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
        "cat_color": "#2196f3",
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
        "cat_color": "#20bf6b",
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

CARD_CSS = """
.device-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 24px;
    max-width: 1200px;
    margin: 0 auto;
}

.device-card {
    width: 100%;
    background: white;
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    transition: box-shadow 0.2s, transform 0.15s;
}
.device-card:hover {
    box-shadow: 0 6px 24px rgba(0,0,0,0.13);
    transform: translateY(-2px);
}

.device-img-wrap {
    width: 100%;
    aspect-ratio: 1 / 1;
    background: #f8f9fc;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    padding: 16px;
}
.device-img-wrap img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
}

.device-card-body {
    padding: 14px 16px 16px;
    flex: 1;
    display: flex;
    flex-direction: column;
}
.device-cat {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 6px;
}
.device-name {
    font-size: 14px;
    font-weight: 700;
    color: #1a1a2e;
    margin-bottom: 6px;
    line-height: 1.4;
}
.device-short {
    font-size: 11px;
    color: #aaa;
    line-height: 1.5;
    flex: 1;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
}
.device-btn {
    margin-top: 14px;
    padding: 9px 0;
    background: white;
    border: 1.5px solid #e0e0e0;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 600;
    color: #1a1a2e;
    text-align: center;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
}
.device-btn:hover {
    background: #f0f4ff;
    border-color: #4361ee;
    color: #4361ee;
}
"""


def show_device_detail(device):
    """Mở dialog chi tiết thiết bị theo form tham chiếu với thiết kế responsive."""
    with ui.dialog() as dlg, ui.card().classes("p-0").style(
        "width:820px;max-width:95vw;max-height:90vh;"
        "border-radius:20px;overflow:hidden;box-shadow:0 25px 50px -12px rgba(0,0,0,0.25)"
    ):
        # Responsive 2-column layout: stacked on mobile, side-by-side on desktop
        with ui.element("div").classes("grid grid-cols-1 md:grid-cols-[320px_1fr] min-h-[460px] w-full"):
            
            # ── LEFT: Device Image ──────────────────────────────
            with ui.element("div").classes("bg-slate-50 flex items-center justify-center p-6 md:p-8"):
                with ui.element("div").style(
                    "background:white;padding:24px;border-radius:8px;"
                    "box-shadow:0 4px 14px rgba(0,0,0,0.05);width:100%;"
                    "aspect-ratio:1/1;display:flex;align-items:center;justify-content:center"
                ):
                    ui.image(device["image"]).style(
                        "max-width:100%;max-height:100%;object-fit:contain"
                    )

            # ── RIGHT: Info ─────────────────────────────────────
            with ui.element("div").classes("p-6 md:p-8 flex flex-col relative bg-white"):
                # Close × button
                ui.button("✕", on_click=dlg.close).style(
                    "position:absolute;top:16px;right:16px;"
                    "background:none;border:none;font-size:20px;"
                    "color:#64748b;cursor:pointer;padding:4px 8px;"
                    "line-height:1"
                ).props("flat dense")

                # Category label
                ui.label(device["category"]).style(
                    f"font-size:11px;font-weight:800;letter-spacing:.08em;"
                    f"text-transform:uppercase;color:{device.get('cat_color', '#2563eb')};"
                    f"margin-bottom:8px"
                )

                # Device name
                ui.label(device["name"]).style(
                    "font-size:24px;font-weight:800;color:#0f172a;"
                    "line-height:1.2;margin-bottom:16px"
                )

                # Brand & Model
                ui.label("THƯƠNG HIỆU & MODEL").style(
                    "font-size:10px;font-weight:700;color:#94a3b8;"
                    "letter-spacing:.05em;text-transform:uppercase;margin-bottom:4px"
                )
                brand_name = device.get("brand", device["name"].split()[0] if device["name"] else "")
                ui.label(f"{brand_name} - {device['model']}").style(
                    "font-size:15px;font-weight:500;color:#334155;margin-bottom:20px"
                )

                # Specs box
                ui.label("THÔNG SỐ KỸ THUẬT CHI TIẾT").style(
                    "font-size:10px;font-weight:700;color:#94a3b8;"
                    "letter-spacing:.05em;text-transform:uppercase;margin-bottom:8px"
                )
                specs_text = ", ".join(f"{k}: {v}" for k, v in device["specs"].items())
                with ui.element("div").classes("bg-blue-50/50 border border-blue-100/30 rounded-xl p-4 mb-4"):
                    ui.label(specs_text).style(
                        "font-size:13px;color:#1d4ed8;line-height:1.6;"
                        "font-style:italic"
                    )

                # Calibration Info (nếu có)
                if "calibration" in device:
                    ui.label("THÔNG TIN HIỆU CHUẨN").style(
                        "font-size:10px;font-weight:700;color:#94a3b8;"
                        "letter-spacing:.05em;text-transform:uppercase;margin-bottom:8px"
                    )
                    cal = device["calibration"]
                    with ui.element("div").classes("bg-purple-50/70 border border-purple-100/50 rounded-xl p-3 mb-5"):
                        with ui.row().classes("w-full justify-between items-center mb-1"):
                            ui.label(f"📅 Hiệu chuẩn cuối: {cal['last']}").style("font-size:12px;font-weight:700;color:#6b21a8")
                            ui.label(f"🔄 Chu kỳ: {cal['cycle']}").style("font-size:12px;font-weight:700;color:#6b21a8")
                        ui.label(f"🎯 Khuyên dùng: {cal['guide']}").style("font-size:11px;color:#7e22ce;line-height:1.4;font-style:italic")

                # Close button
                ui.button("Đóng cửa sổ", on_click=dlg.close).style(
                    "width:100%;background:#0f172a;color:white;"
                    "border-radius:12px;font-size:14px;font-weight:600;"
                    "padding:12px 0;cursor:pointer"
                ).props("flat")

    dlg.open()


# ─────────────────────────────────────────────
# PAGE
# ─────────────────────────────────────────────
@ui.page("/devices")
def trang_devices():
    if not check_login(): return
    
    ui.add_head_html(f"<style>{CUSTOM_CSS}{CARD_CSS}</style>")
    sidebar(active="Device")

    with ui.element("div").classes("main-content"):
        # Top bar
        global_topbar("Quản Lý Thiết Bị", "📱")

        with ui.element("div").classes("content-area"):
            # Title
            ui.label("Danh Mục Thiết Bị Hệ Thống").style(
                "font-size:22px;font-weight:800;color:#1a1a2e;text-align:center;"
                "margin-bottom:4px"
            )
            ui.label(
                "Danh sách các thiết bị phần cứng, cảm biến và bộ điều khiển trong hệ thống IoT."
            ).style(
                "font-size:13px;color:#aaa;text-align:center;margin-bottom:24px"
            )

            # State lưu thông tin tìm kiếm & bộ lọc
            filter_state = {"search": "", "category": "Tất cả"}

            @ui.refreshable
            def render_device_section():
                search_query = filter_state["search"]
                selected_cat = filter_state["category"]

                # Thanh bộ lọc và tìm kiếm (đặt bên trong refreshable để cập nhật trạng thái highlight)
                with ui.row().classes("w-full justify-between items-center gap-4 mb-6 bg-slate-50 p-3 rounded-2xl border border-slate-100"):
                    # Ô tìm kiếm
                    ui.input(
                        placeholder="Tìm thiết bị, model, tính năng...",
                        value=filter_state["search"],
                        on_change=lambda e: (filter_state.update({"search": e.value}), render_device_section.refresh())
                    ).props("outlined dense clearable").classes("w-full md:w-80 bg-white rounded-lg shadow-sm").style("font-size:13px")
                    
                    # Bộ lọc Chips
                    with ui.row().classes("items-center gap-2 flex-wrap"):
                        categories = ["Tất cả", "Cảm biến", "Gateway", "Điều khiển"]
                        for cat in categories:
                            is_active = (selected_cat == cat)
                            btn_style = "background: #3b82f6; color: white" if is_active else "background: white; color: #64748b"
                            btn_classes = "font-bold text-[11px] px-3 border border-slate-200"
                            if not is_active: btn_classes += " hover:border-blue-400 hover:text-blue-500"
                            
                            # Closure capturing
                            ui.button(
                                cat,
                                on_click=lambda c=cat: (filter_state.update({"category": c}), render_device_section.refresh())
                            ).style(btn_style).classes(btn_classes).props("rounded unelevated size=sm")

                # Lọc danh sách thiết bị
                filtered = DEVICES
                if search_query:
                    q = search_query.lower()
                    filtered = [
                        d for d in filtered 
                        if q in d["name"].lower() 
                        or q in d["model"].lower() 
                        or q in d["category"].lower() 
                        or q in d["description"].lower() 
                        or q in d["short"].lower()
                    ]
                
                if selected_cat != "Tất cả":
                    cat_map = {
                        "Cảm biến": ["CẢM BIẾN", "SENSOR"],
                        "Gateway": ["GATEWAY", "IOT MODULE", "NODE IOT", "VI ĐIỀU KHIỂN"],
                        "Điều khiển": ["INVERTER", "PLC", "LOGIC MODULE", "EXPANSION MODULE", "BIẾN TẦN"]
                    }
                    sub_keywords = cat_map.get(selected_cat, [])
                    filtered = [
                        d for d in filtered 
                        if any(kw in d["category"].upper() or kw in d["name"].upper() for kw in sub_keywords)
                    ]

                if not filtered:
                    with ui.column().classes("w-full items-center py-12 text-slate-400"):
                        ui.icon("inventory_2", size="48px").classes("mb-2")
                        ui.label("Không tìm thấy thiết bị nào phù hợp").classes("text-sm font-bold")
                    return

                # 4-column card grid
                with ui.element("div").classes("device-grid"):
                    for d in filtered:
                        with ui.element("div").classes("device-card"):
                            # Image square
                            with ui.element("div").classes("device-img-wrap"):
                                ui.image(d["image"]).style(
                                    "max-width:100%;max-height:100%;object-fit:contain"
                                )

                            # Body text
                            with ui.element("div").classes("device-card-body"):
                                ui.label(d["category"]).style(
                                    f"font-size:10px;font-weight:700;letter-spacing:.08em;"
                                    f"text-transform:uppercase;color:{d['cat_color']};margin-bottom:6px"
                                )
                                ui.label(d["name"]).style(
                                    "font-size:14px;font-weight:700;color:#1a1a2e;"
                                    "margin-bottom:6px;line-height:1.4"
                                )
                                ui.label(d["short"]).style(
                                    "font-size:11px;color:#aaa;line-height:1.5;"
                                    "overflow:hidden;display:-webkit-box;"
                                    "-webkit-line-clamp:3;-webkit-box-orient:vertical;flex:1"
                                )

                                # Nút xem chi tiết
                                device_ref = d  # capture for closure
                                ui.button(
                                    "Xem chi tiết",
                                    on_click=lambda dev=device_ref: show_device_detail(dev)
                                ).style(
                                    "margin-top:14px;padding:9px 0;background:white;"
                                    "border:1.5px solid #e0e0e0;border-radius:10px;"
                                    "font-size:12px;font-weight:600;color:#1a1a2e;"
                                    "text-align:center;cursor:pointer;width:100%;"
                                    "transition:background 0.15s,border-color 0.15s"
                                ).props("flat")

            # Render ban đầu cho phần thiết bị
            render_device_section()
