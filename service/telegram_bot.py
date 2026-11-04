"""
service/telegram_bot.py — Telegram Bot Service (Chạy độc lập với main.py)
─────────────────────────────────────────────────────────────────────────
Nhận thông báo SCADA qua MQTT topic "farm/notify" và gửi lên Telegram.
Chỉ gửi cho 1 admin duy nhất (ADMIN_CHAT_ID trong .env)

Chạy thủ công:  python service/telegram_bot.py
Chạy service:   sudo systemctl start smiot-telegram
"""
import os
import sys
import json
import time
import threading

# Thêm đường dẫn thư mục gốc của project vào sys.path để import chéo dạng 'service.xxx'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paho.mqtt.client as mqtt

# ── Đọc cấu hình từ file .env ──
from dotenv import load_dotenv
# Load .env từ thư mục gốc project (1 cấp trên thư mục service/)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

# ── Telegram: Gửi tin nhắn bằng HTTP request thuần (không cần async) ──
import urllib.request
import urllib.parse

def send_telegram_message(text):
    """Gửi tin nhắn đến admin Telegram bằng HTTP request thuần túy.
    Không cần thư viện async, phù hợp chạy trong callback MQTT.
    """
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        print("⚠️ [TELEGRAM] Thiếu token hoặc chat_id, bỏ qua gửi tin.")
        return False

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        # Chuẩn bị dữ liệu gửi đi — dùng parse_mode HTML để in đậm, xuống dòng
        data = urllib.parse.urlencode({
            "chat_id": ADMIN_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }).encode("utf-8")

        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode())
            if result.get("ok"):
                print(f"✅ [TELEGRAM] Đã gửi: {text[:60]}...")
                return True
            else:
                print(f"❌ [TELEGRAM] API trả lỗi: {result}")
                return False
    except Exception as e:
        print(f"❌ [TELEGRAM] Lỗi gửi tin nhắn: {e}")
        return False

# ── Emoji & Label theo category/severity ──
SEVERITY_EMOJI = {
    "error": "🔴",
    "warning": "🟡",
    "info": "🟢"
}

CATEGORY_LABEL = {
    "inverter": "⚡ Biến tần",
    "plc": "🔧 PLC/Bơm",
    "sensor": "📡 Cảm biến",
    "schedule": "📅 Lịch tưới",
    "system": "🖥️ Hệ thống"
}

def format_notification(payload):
    """Định dạng thông báo thành tin nhắn đẹp cho Telegram (HTML format)."""
    msg = payload.get("message", "Không có nội dung")
    cat = payload.get("category", "system")
    sev = payload.get("severity", "info")
    t = payload.get("time", "")

    emoji = SEVERITY_EMOJI.get(sev, "ℹ️")
    label = CATEGORY_LABEL.get(cat, "📌 Khác")

    # Format tin nhắn dạng HTML cho Telegram
    return f"{emoji} <b>{label}</b>\n{msg}\n🕐 {t}"

# ── MQTT Client: Lắng nghe topic "farm/notify" ──
def on_connect(client, userdata, flags, rc):
    """Callback khi kết nối MQTT thành công → subscribe topic thông báo."""
    if rc == 0:
        print("✅ [MQTT] Bot đã kết nối MQTT Broker thành công")
        client.subscribe("farm/notify")
        print("   📡 Đang lắng nghe topic: farm/notify")
    else:
        print(f"❌ [MQTT] Kết nối thất bại, mã lỗi: {rc}")

def on_disconnect(client, userdata, rc):
    """Callback khi mất kết nối MQTT."""
    if rc != 0:
        print(f"⚠️ [MQTT] Mất kết nối (rc={rc}), đang thử kết nối lại...")

def on_message(client, userdata, msg):
    """Callback khi nhận message từ MQTT → format và gửi lên Telegram."""
    try:
        payload = json.loads(msg.payload.decode())
        text = format_notification(payload)
        send_telegram_message(text)
    except json.JSONDecodeError:
        print(f"⚠️ [MQTT] Payload không phải JSON: {msg.payload}")
    except Exception as e:
        print(f"❌ [MQTT] Lỗi xử lý tin nhắn: {e}")

def start_mqtt_listener():
    """Khởi chạy MQTT client cho bot — tự động reconnect khi mất kết nối."""
    # Tạo client ID riêng để không xung đột với MQTT client của main.py
    client = mqtt.Client(client_id="smiot_telegram_bot")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    # Vòng lặp kết nối — tự thử lại nếu broker chưa sẵn sàng
    while True:
        try:
            print(f"🔄 [MQTT] Đang kết nối đến {MQTT_BROKER}:{MQTT_PORT}...")
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            # loop_forever() tự xử lý reconnect bên trong
            client.loop_forever()
        except ConnectionRefusedError:
            print(f"⚠️ [MQTT] Broker từ chối kết nối, thử lại sau 5s...")
            time.sleep(5)
        except Exception as e:
            print(f"⚠️ [MQTT] Lỗi kết nối: {e}, thử lại sau 5s...")
            time.sleep(5)

def poll_telegram_messages():
    """Vòng lặp Long Polling để nhận và xử lý tin nhắn từ Admin Telegram."""
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ [POLLING] Không thể chạy polling vì thiếu bot token.")
        return

    # Import động để tránh circular import
    from service.ai_service import ask_ai, AI_ENABLED

    offset = 0
    print("🤖 [POLLING] Đang khởi chạy luồng nhận tin nhắn Telegram...")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            req = urllib.request.Request(url, method="GET")
            
            with urllib.request.urlopen(req, timeout=35) as response:
                result = json.loads(response.read().decode("utf-8"))
                
            if result.get("ok"):
                for update in result.get("result", []):
                    # Cập nhật offset để tránh nhận trùng tin nhắn
                    offset = update.get("update_id") + 1
                    
                    message = update.get("message")
                    if not message:
                        continue
                        
                    chat = message.get("chat", {})
                    chat_id = str(chat.get("id"))
                    text = message.get("text", "")
                    
                    # Chỉ xử lý tin nhắn từ ADMIN_CHAT_ID
                    if chat_id != str(ADMIN_CHAT_ID):
                        print(f"🔒 [POLLING] Bỏ qua tin nhắn từ người lạ (Chat ID: {chat_id})")
                        continue
                        
                    if not text:
                        continue
                        
                    print(f"📥 [POLLING] Nhận tin nhắn từ Admin: '{text}'")
                    
                    # Xử lý phản hồi AI trong một Thread phụ để tránh chặn vòng lặp nhận tin nhắn
                    def handle_and_reply(msg_text):
                        reply_text = ask_ai(msg_text)
                        send_telegram_message(reply_text)
                        
                    threading.Thread(target=handle_and_reply, args=(text,), daemon=True).start()
                    
        except urllib.error.URLError as e:
            # Thử lại sau 5s khi gặp lỗi mạng/timeout
            time.sleep(5)
        except Exception as e:
            print(f"❌ [POLLING] Lỗi trong vòng lặp polling: {e}")
            time.sleep(5)

# ── Entry point ──
if __name__ == "__main__":
    print("=" * 50)
    print("🤖 SMIOT Telegram Bot — Khởi động")
    print("=" * 50)

    # Kiểm tra cấu hình bắt buộc
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Thiếu TELEGRAM_BOT_TOKEN trong file .env!")
        print("   Hãy tạo bot trên @BotFather và thêm token vào .env")
        exit(1)
    if not ADMIN_CHAT_ID:
        print("❌ Thiếu ADMIN_CHAT_ID trong file .env!")
        print("   Hãy lấy chat_id từ @userinfobot và thêm vào .env")
        exit(1)

    print(f"   📡 MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"   📱 Admin Chat ID: {ADMIN_CHAT_ID}")
    print(f"   🔔 Lắng nghe: farm/notify")
    print("─" * 50)

    # Gửi tin nhắn test khi bot khởi động
    send_telegram_message("🟢 <b>SMIOT Bot đã khởi động</b>\nBot đang lắng nghe thông báo từ hệ thống.")

    # Khởi chạy luồng Polling để nhận tin nhắn Telegram (AI Chatbot)
    polling_thread = threading.Thread(target=poll_telegram_messages, daemon=True)
    polling_thread.start()

    # Bắt đầu lắng nghe MQTT
    start_mqtt_listener()
