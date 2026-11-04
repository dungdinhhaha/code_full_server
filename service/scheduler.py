"""
service/scheduler.py — Background Scheduler
Quét và quản lý bật/tắt lịch trình tưới tự động chạy ngầm, độc lập với giao diện web.
"""

import time
import datetime
import threading
from service.logger import get_logger
from pages.home import state
from service.mqtt import publish_mqtt, add_notification
from service import auth

logger = get_logger("SCHEDULER")

FARMS = ['greenhouse_a', 'greenhouse_b', 'greenhouse_c', 'greenhouse_d']

def scheduler_start_tick():
    """Quét và kích hoạt lịch trình mới (bật bơm) cho tất cả các farm - Chạy mỗi 60s."""
    from service.auth import get_inverter_mode, auto_fail_missed_schedules
    
    # 1. Tự động quét và chuyển các lịch trình quá hạn (> 10 phút) sang failed
    for farm_key in FARMS:
        try:
            missed_ids = auto_fail_missed_schedules(farm_key)
            if missed_ids:
                for sch_id, start_time, is_silent in missed_ids:
                    if not is_silent:
                        add_notification(
                            f"❌ Lịch tưới #{sch_id} lúc {start_time} bị bỏ lỡ do hệ thống offline!",
                            category="schedule",
                            severity="error"
                        )
                state["_update_counter"] = state.get("_update_counter", 0) + 1
        except Exception as e:
            logger.error(f"[AUTO] Lỗi quét lịch trình quá hạn cho {farm_key}: {e}")

    # 2. Chặn kích hoạt nếu Gateway đang offline
    if not state.get("system_is_active", True):
        logger.warning("[AUTO] Gateway đang offline — Bỏ qua lịch tưới chu kỳ này.")
        return

    now = datetime.datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    for farm_key in FARMS:
        try:
            mode = get_inverter_mode(farm_key)
            pending = auth.get_pending_schedules(farm_key, current_date, current_time)
            
            if pending and mode != 'auto':
                logger.warning(f"[AUTO] [{farm_key}] Phát hiện {len(pending)} lịch trình đến giờ nhưng bị bỏ qua vì đang ở chế độ MANUAL.")
                continue

            for sch in pending:
                # Gửi MQTT bật inverter
                try:
                    payload = {
                        "device_name": "Inverter",
                        "bit": 1
                    }
                    publish_mqtt("farm/inverter", payload)

                    # Lưu lượng nước tích lũy lúc bắt đầu vào bộ nhớ tạm
                    if "flow_start_water" not in state:
                        state["flow_start_water"] = {}
                    state["flow_start_water"][sch["id"]] = state.get("flow_total", 0.0)

                    # Cập nhật trạng thái và ghi Log
                    auth.update_schedule_status(sch["id"], "pending_run")
                    auth.add_schedule_log(
                        sch["id"], farm_key,
                        now.strftime("%Y-%m-%d %H:%M:%S"),
                        sch["water_amount"],
                        status="pending_run"
                    )
                    logger.info(f"[AUTO] [{farm_key}] Gửi lệnh bit=1 kích hoạt lịch #{sch['id']}: {sch['water_amount']} phút")
                    
                    state["inv_has_started"] = False

                    # Đăng ký hàng đợi chờ phản hồi Biến tần từ Gateway (Timeout 2 phút)
                    state["inv_pending_cmd"] = {
                        "time": time.time(),
                        "target_bit": 1,
                        "schedule_id": sch["id"]
                    }
                    
                    state["inv_status"] = 1
                    state["inv_online"] = 1
                    state["inv_locked"] = True
                    state["inv_lock_time"] = time.time()
                    state["_update_counter"] = state.get("_update_counter", 0) + 1
                except Exception as e:
                    logger.error(f"[AUTO] [{farm_key}] Lỗi kích hoạt lịch #{sch['id']}: {e}")
        except Exception as e:
            logger.error(f"[AUTO] Lỗi quét khởi chạy lịch trình cho {farm_key}: {e}")

def scheduler_stop_tick():
    """Quét các lịch trình đang chạy để chủ động tắt khi hết giờ - Chạy mỗi 5s."""
    # Chỉ chạy nếu Gateway đang online
    if not state.get("system_is_active", True):
        return

    now = datetime.datetime.now()

    for farm_key in FARMS:
        try:
            running_logs = auth.get_running_schedule_logs(farm_key)

            for log in running_logs:
                sch_id = log["schedule_id"]
                if sch_id is None:
                    continue
                start_at_str = log["start_at"]
                run_minutes = float(log["target_water"])  # target_water lưu số phút chạy cấu hình
                
                start_dt = datetime.datetime.strptime(start_at_str, "%Y-%m-%d %H:%M:%S")
                end_dt = start_dt + datetime.timedelta(minutes=run_minutes)
                
                if now >= end_dt:
                    # Nếu đã gửi lệnh tắt và đang chờ phản hồi từ Gateway thì không gửi lại
                    inv_pending = state.get("inv_pending_cmd")
                    if inv_pending and inv_pending.get("target_bit") == 0 and inv_pending.get("schedule_id") == sch_id:
                        continue
                        
                    logger.info(f"[AUTO] [{farm_key}] Lịch #{sch_id} đã chạy đủ {run_minutes} phút. Gửi lệnh tắt (bit=0)...")
                    
                    payload = {
                        "device_name": "Inverter",
                        "bit": 0
                    }
                    publish_mqtt("farm/inverter", payload)
                    
                    state["inv_pending_cmd"] = {
                        "time": time.time(),
                        "target_bit": 0,
                        "schedule_id": sch_id
                    }
                    
                    state["inv_status"] = 0
                    state["inv_locked"] = True
                    state["inv_lock_time"] = time.time()
                    state["_update_counter"] = state.get("_update_counter", 0) + 1
        except Exception as e:
            logger.error(f"[AUTO] [{farm_key}] Lỗi kiểm tra tắt lịch trình: {e}")

import psutil

def monitor_system_resources():
    """Kiểm tra sức khỏe máy chủ (CPU, RAM, Disk) và cảnh báo nếu vượt ngưỡng 90%."""
    try:
        cpu_percent = psutil.cpu_percent(interval=None) # Lấy CPU lập tức
        ram_info = psutil.virtual_memory()
        ram_percent = ram_info.percent
        disk_info = psutil.disk_usage('/')
        disk_percent = disk_info.percent
        
        logger.info(f"[MONITOR] System Health: CPU={cpu_percent}%, RAM={ram_percent}%, Disk={disk_percent}%")
        
        # Cảnh báo nếu CPU hoặc RAM quá cao (>90%)
        if cpu_percent > 90.0 or ram_percent > 90.0:
            msg = f"<b>⚠️ Cảnh báo Tài nguyên!</b>\nMáy chủ đang quá tải:\nCPU: {cpu_percent}%\nRAM: {ram_percent}%"
            publish_mqtt("farm/notify", {
                "message": msg,
                "category": "system",
                "severity": "warning",
                "time": datetime.datetime.now().strftime("%H:%M:%S")
            })
            logger.warning(f"[MONITOR] Đã gửi cảnh báo quá tải lên Telegram. CPU={cpu_percent}%, RAM={ram_percent}%")
    except Exception as e:
        logger.error(f"[MONITOR] Lỗi khi đọc System Resources: {e}")

def scheduler_loop():
    """Vòng lặp chạy ngầm tuần hoàn."""
    logger.info("Bắt đầu khởi chạy luồng ngầm Background Scheduler...")
    time.sleep(5.0)  # Chờ hệ thống MQTT và DB kết nối ổn định
    logger.info("Luồng ngầm Background Scheduler đã hoạt động ổn định!")

    last_start_tick = 0.0
    last_stop_tick = 0.0
    last_monitor_tick = 0.0

    while True:
        try:
            now_time = time.time()

            # 1. Quét tắt mỗi 5 giây
            if now_time - last_stop_tick >= 5.0:
                last_stop_tick = now_time
                scheduler_stop_tick()

            # 2. Quét bật mỗi 60 giây (tương đương 1 phút)
            if now_time - last_start_tick >= 60.0:
                last_start_tick = now_time
                scheduler_start_tick()
                
            # 3. Giám sát phần cứng mỗi 15 phút (900 giây)
            if now_time - last_monitor_tick >= 900.0:
                last_monitor_tick = now_time
                monitor_system_resources()

        except Exception as e:
            logger.error(f"Lỗi trong vòng lặp Background Scheduler: {e}")

        time.sleep(1.0)

def start_background_scheduler():
    """Khởi chạy Background Thread cho Scheduler."""
    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()
    logger.info("Đã khởi chạy luồng Background Thread cho Scheduler (Bật mỗi 60s, Tắt mỗi 5s)")
