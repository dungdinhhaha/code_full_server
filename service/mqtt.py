import json
import paho.mqtt.client as mqtt
from pages.home import state
from datetime import datetime, timedelta
import time
from service.logger import get_logger
from service.observability import inject_mqtt_trace_context, traced, traced_mqtt_callback

logger = get_logger("MQTT")

mqtt_client = None

@traced("mqtt.publish")
def publish_mqtt(topic, payload_dict):
    global mqtt_client
    if mqtt_client:
        try:
            mqtt_client.publish(topic, json.dumps(inject_mqtt_trace_context(dict(payload_dict))))
            logger.info(f"Đã publish lên {topic}: {payload_dict}")
            # print(f"Đã publish lên {topic}: {payload_dict}")
        except Exception as e:
            print(f"Lỗi publish MQTT: {e}")

def add_notification(msg_text, category="system", severity="info"):
    """Thông báo 3-trong-1: RAM (Web UI) + DB (lịch sử) + MQTT (Telegram Bot)
    category: inverter / plc / sensor / schedule / system
    severity: info / warning / error
    """
    if "notifications" not in state:
        state["notifications"] = []
    # Tránh lặp lại thông báo y hệt liên tục
    if state["notifications"] and state["notifications"][0]["text"] == msg_text:
        return

    now_str = datetime.now().strftime("%H:%M:%S")

    # 1. Cập nhật RAM cho Web UI (giữ nguyên logic cũ)
    state["notifications"].insert(0, {
        "time": now_str,
        "text": msg_text
    })
    state["notifications"] = state["notifications"][:20] # Giới hạn 20 thông báo

    # 2. Lưu vào DB (lịch sử + phân tích AI sau này)
    try:
        from service.auth import save_notification
        save_notification(msg_text, category, severity)
    except Exception as e:
        print(f"⚠️ Lỗi lưu notification vào DB: {e}")

    # 3. Publish lên MQTT topic "farm/notify" để Telegram Bot nhận
    try:
        publish_mqtt("farm/notify", {
            "message": msg_text,
            "category": category,
            "severity": severity,
            "time": now_str
        })
    except Exception as e:
        print(f"⚠️ Lỗi publish notification MQTT: {e}")


MQTT_BROKER = "localhost" # Server đóng vai trò là broker
MQTT_PORT = 1883

def parse_utc_to_local(time_str):
    if not time_str:
        return ""
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        dt += timedelta(hours=7)
        return dt.strftime("%H:%M:%S")
    except Exception:
        return time_str

def process_farm_data(payload):
    """ Xử lý dữ liệu Inverter / thiết bị công nghiệp """
    if payload.get("device_name") == "Inverter":
        # Chấp nhận cả status hoặc bit làm trạng thái chạy thực tế từ Gateway
        real_status = 1 if (payload.get("status") == 1 or payload.get("bit") == 1) else 0
        
        # Chỉ cập nhật trạng thái online nếu trường "online" thực sự tồn tại trong payload
        if "online" in payload:
            state["inv_online"] = 1 if payload.get("online") in [1, True, "1", "true"] else 0
        else:
            # Nếu không có trường "online" nhưng thiết bị đang chạy thực tế, thì chắc chắn thiết bị phải online
            if real_status == 1:
                state["inv_online"] = 1
            # Nếu state chưa có inv_online, mặc định khởi tạo là 1
            elif "inv_online" not in state:
                state["inv_online"] = 1
        
        state["inv_real_status"] = real_status
        state["inv_status"] = real_status
        if real_status == 1:
            if not state.get("inv_has_started", False):
                state["inv_has_started"] = True
                try:
                    from service.auth import get_schedules, update_schedule_status, update_schedule_log_start_time
                    
                    # Tính độ trễ nếu có lệnh được gửi từ schedule
                    latency_msg = ""
                    pending_cmd = state.get("inv_pending_cmd")
                    
                    # Ghi log thông số chạy
                    hz = payload.get("hz", 0.0)
                    p_cur = payload.get("p_cur", 0.0)
                    t2 = state.get("flow_total", 0.0)
                    
                    if pending_cmd and pending_cmd.get("target_bit") == 1:
                        latency = round(time.time() - pending_cmd.get("time", time.time()), 2)
                        latency_msg = f"Độ trễ phản hồi: {latency}s."
                    else:
                        logger.warning("CẢNH BÁO: Biến tần bắt đầu chạy (status=1) nhưng không có lệnh gửi từ Web! Khả năng chạy tay qua tủ điện.")
                    
                    logger.info(f"Biến tần báo status=1. {latency_msg} Thông số: hz={hz}, p_cur={p_cur}, t2={t2}L")

                    for farm in ['greenhouse_a', 'greenhouse_b', 'greenhouse_c', 'greenhouse_d']:
                        pending_run = [s for s in get_schedules(farm) if s['status'] == 'pending_run']
                        for sch in pending_run:
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            update_schedule_status(sch['id'], 'running')
                            update_schedule_log_start_time(sch['id'], now_str, 'running')
                            logger.info(f"[SCHEDULE] Lịch #{sch['id']} chuyển sang ĐANG CHẠY lúc {now_str}")
                            # print(f"▶️ [SCHEDULE] Lịch #{sch['id']} bắt đầu chạy thực tế lúc {now_str}")
                except Exception as e:
                    logger.error(f"[SCHEDULE] Lỗi cập nhật trạng thái bắt đầu: {e}")
            else:
                state["inv_has_started"] = True
        state["inv_hz"] = payload.get("hz", 0.0)
        state["inv_p_set"] = payload.get("p_set", 0.0)
        state["inv_p_cur"] = payload.get("p_cur", 0.0)
        state["inv_v_out"] = payload.get("v_out", 0)
        state["inv_i_out"] = payload.get("i_out", 0.0)
        state["inv_v_in"] = payload.get("v_in", 0.0)
        state["inv_i_in"] = payload.get("i_in", 0.0)
        state["inv_kp"] = payload.get("kp", 0.0)
        state["inv_ki"] = payload.get("ki", 0.0)
        state["inv_kd"] = payload.get("kd", 0.0)
        
        # Cảnh báo an toàn
        if real_status == 1:
            if state["inv_p_cur"] < 0.1 and state["inv_hz"] > 10.0:
                logger.warning(f"CẢNH BÁO AN TOÀN: Bơm đang chạy (hz={state['inv_hz']}) nhưng áp suất bằng 0 ({state['inv_p_cur']} BAR). Nguy cơ hụt nước/bể ống!")
        
        ts = payload.get("timestamp")
        state["inv_updated"] = parse_utc_to_local(ts) if ts else datetime.now().strftime("%H:%M:%S")

        # ── Schedule Integration: Khi Gateway báo tắt inverter (status=0) ──
        # Nếu có lịch đang 'running' → chuyển sang 'completed' và ghi log
        if payload.get("status") == 0 or payload.get("bit") == 0:
            if state.get("inv_has_started", False):
                try:
                    from service.auth import get_schedules, update_schedule_status, update_schedule_log
                    # Kiểm tra tất cả farm (vì không biết chính xác farm_key từ payload)
                    for farm in ['greenhouse_a', 'greenhouse_b', 'greenhouse_c', 'greenhouse_d']:
                        running = [s for s in get_schedules(farm) if s['status'] == 'running']
                        for sch in running:
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            # Tính toán hiệu số nước thực tế tưới
                            flow_start = state.get("flow_start_water", {}).pop(sch['id'], None)
                            if flow_start is not None:
                                actual_water = max(0.0, round(state.get("flow_total", 0.0) - flow_start, 2))
                            else:
                                actual_water = 0.0
                                
                            update_schedule_status(sch['id'], 'completed')
                            update_schedule_log(sch['id'], now_str, actual_water, 'completed')
                            logger.info(f"[SCHEDULE] Lịch #{sch['id']} HOÀN THÀNH — Thực tế tiêu thụ: {actual_water}L")
                            add_notification(f"Lịch tưới #{sch['id']} đã hoàn thành ({actual_water}L)", category="schedule", severity="info")
                    # Reset cờ sau khi xử lý xong các lịch running
                    state["inv_has_started"] = False
                    
                    # Log độ trễ ngắt
                    pending_cmd = state.get("inv_pending_cmd")
                    if pending_cmd and pending_cmd.get("target_bit") == 0:
                        latency = round(time.time() - pending_cmd.get("time", time.time()), 2)
                        logger.info(f"Biến tần báo status=0. Độ trễ ngắt: {latency}s.")
                    else:
                        logger.info("Biến tần đã tắt (status=0) từ bên ngoài hoặc thủ công.")
                        
                except Exception as e:
                    logger.error(f"[SCHEDULE] Lỗi cập nhật trạng thái kết thúc: {e}")

@traced("smiot.flow_and_sensor.process")
def process_farm_sensor(payload):
    """ Xử lý dữ liệu từ các Cảm biến nông nghiệp và Lưu lượng """
    
    # 1. Xử lý dữ liệu Lưu Lượng (Flow_Meter) - id3
    if "id3" in payload and payload["id3"] is not None:
        flow = payload["id3"]
        state["flow_line1"] = flow.get("f1", state["flow_line1"])
        state["flow_line2"] = flow.get("f2", state["flow_line2"])
        # Chỉ lấy chỉ số tích lũy t2 làm lưu lượng tổng
        state["flow_total"] = round(flow.get("t2", 0.0), 2)
        ts = flow.get("timestamp")
        state["flow_updated"] = parse_utc_to_local(ts) if ts else datetime.now().strftime("%H:%M:%S")

    # 2. Xử lý dữ liệu EC - id4
    if "id4" in payload and payload["id4"] is not None:
        ec_data = payload["id4"]
        state["node1_ec"] = ec_data.get("ec", state.get("node1_ec", 0.0))
        # Map đầy đủ thông số cho card EC riêng
        state["ec_val"] = ec_data.get("ec", 0.0)
        state["ec_v"] = ec_data.get("v", 0.0)
        state["ec_raw"] = ec_data.get("raw", 0)
        state["ec_online"] = ec_data.get("online", 1)
        ts = ec_data.get("timestamp")
        state["ec_updated"] = parse_utc_to_local(ts) if ts else datetime.now().strftime("%H:%M:%S")

    # 3. Xử lý dữ liệu PH - id5
    if "id5" in payload and payload["id5"] is not None:
        ph_data = payload["id5"]
        state["ph_value"] = ph_data.get("ph", 7.0)
        # Map đầy đủ thông số cho card pH riêng
        state["ph_val"] = ph_data.get("ph", 7.0)
        state["ph_mv"] = ph_data.get("mv", 0.0)
        state["ph_raw"] = ph_data.get("raw", 0)
        state["ph_online"] = ph_data.get("online", 1)
        ts = ph_data.get("timestamp")
        state["ph_updated"] = parse_utc_to_local(ts) if ts else datetime.now().strftime("%H:%M:%S")

    # 4. Xử lý dữ liệu Node Cảm biến - id6
    if "id6" in payload and payload["id6"] is not None:
        nodes = payload["id6"]
        
        n1_offline = False
        n2_offline = False
        n1_online = False
        n2_online = False
        ts1, ts2 = None, None
        
        if "node1" in nodes:
            n1 = nodes["node1"]
            ts1 = n1.get("timestamp")
            old_ts1 = state.get("node1_raw_ts")
            
            if ts1 and ts1 == old_ts1:
                # Timestamp chưa đổi, kiểm tra xem đã quá hạn (timeout) chưa (ví dụ: 120s = 2 phút)
                last_change_1 = state.get("node1_last_change_time", 0)
                if time.time() - last_change_1 > 120:
                    n1_offline = True
            else:
                # Có dữ liệu mới, đánh dấu để xử lý kết nối lại
                n1_online = True
                
        if "node2" in nodes:
            n2 = nodes["node2"]
            ts2 = n2.get("timestamp")
            old_ts2 = state.get("node2_raw_ts")
            
            if ts2 and ts2 == old_ts2:
                # Timestamp chưa đổi, kiểm tra xem đã quá hạn chưa (ví dụ 120s)
                last_change_2 = state.get("node2_last_change_time", 0)
                if time.time() - last_change_2 > 120:
                    n2_offline = True
            else:
                n2_online = True

        # Gửi thông báo mất kết nối
        if n1_offline and n2_offline:
            n1_changed = state.get("node1_status") != "OFFLINE"
            n2_changed = state.get("node2_status") != "OFFLINE"
            if n1_changed or n2_changed:
                state["node1_status"] = "OFFLINE"
                state["node2_status"] = "OFFLINE"
                add_notification("Node 1 và Node 2 mất kết nối đồng thời", category="sensor", severity="error")
        else:
            if n1_offline:
                if state.get("node1_status") != "OFFLINE":
                    state["node1_status"] = "OFFLINE"
                    add_notification("Không nhận được tín hiệu từ Node 1", category="sensor", severity="warning")
            if n2_offline:
                if state.get("node2_status") != "OFFLINE":
                    state["node2_status"] = "OFFLINE"
                    add_notification("Không nhận được tín hiệu từ Node 2", category="sensor", severity="warning")

        # Gửi thông báo kết nối lại
        if n1_online and state.get("node1_status") == "OFFLINE":
            add_notification("Node 1 đã kết nối lại", category="sensor", severity="info")
        if n2_online and state.get("node2_status") == "OFFLINE":
            add_notification("Node 2 đã kết nối lại", category="sensor", severity="info")

        # Cập nhật dữ liệu cảm biến
        if "node1" in nodes:
            n1 = nodes["node1"]
            if n1_online:
                state["node1_status"] = "ONLINE"
                state["node1_raw_ts"] = ts1
                state["node1_last_change_time"] = time.time()
            state["node1_air_temp"] = n1.get("at", state.get("node1_air_temp", 0.0))
            state["node1_air_hum"] = n1.get("ah", state.get("node1_air_hum", 0.0))
            state["node1_soil_temp"] = n1.get("st", state.get("node1_soil_temp", 0.0))
            state["node1_soil_hum"] = n1.get("sh", state.get("node1_soil_hum", 0.0))
            state["node1_ec"] = n1.get("sec", state.get("node1_ec", 0.0))
            state["node1_updated"] = parse_utc_to_local(ts1) if ts1 else datetime.now().strftime("%H:%M:%S")

        if "node2" in nodes:
            n2 = nodes["node2"]
            if n2_online:
                state["node2_status"] = "ONLINE"
                state["node2_raw_ts"] = ts2
                state["node2_last_change_time"] = time.time()
            state["node2_air_temp"] = n2.get("at", state.get("node2_air_temp", 0.0))
            state["node2_air_hum"] = n2.get("ah", state.get("node2_air_hum", 0.0))
            state["node2_soil_temp"] = n2.get("st", state.get("node2_soil_temp", 0.0))
            state["node2_soil_hum"] = n2.get("sh", state.get("node2_soil_hum", 0.0))
            state["node2_ec"] = n2.get("sec", state.get("node2_ec", 0.0))
            state["node2_updated"] = parse_utc_to_local(ts2) if ts2 else datetime.now().strftime("%H:%M:%S")

def process_farm_status(payload):
    """ Xử lý dữ liệu trạng thái PLC """
    state["plc_online"] = payload.get("online", state.get("plc_online", 0))
    state["plc_device_name"] = payload.get("device_name", "PLC_LOGO")
    
    # Lấy q0-q7 và bit0-bit7
    for i in range(8):
        q_key = f"q{i}"
        bit_key = f"bit{i}"
        if q_key in payload:
            val = payload[q_key]
            state[q_key] = 1 if (val == 1 or val is True or str(val).lower() == 'true') else 0
        if bit_key in payload:
            val = payload[bit_key]
            state[bit_key] = 1 if (val == 1 or val is True or str(val).lower() == 'true') else 0
            
    ts = payload.get("timestamp")
    state["plc_updated"] = ts if ts else datetime.now().strftime("%H:%M:%S")

def trigger_ui_update():
    """ Tăng biến đếm để báo hiệu UI cần cập nhật """
    state["_update_counter"] = state.get("_update_counter", 0) + 1

@traced("smiot.telemetry.persist")
def save_farm_sensor_to_db(farm_key, payload):
    """Lưu dữ liệu cảm biến riêng lẻ dựa theo các key tương ứng trong payload MQTT."""
    try:
        from service.auth import save_telemetry_flow, save_telemetry_water, save_telemetry_node
        from service.telemetry_provenance import metadata_for_payload
        source_metadata = metadata_for_payload(payload)
        source_metadata["farm_key"] = farm_key
        lag_ms = source_metadata.get("device_to_app_lag_ms", source_metadata.get("bridge_to_app_lag_ms"))
        if lag_ms is not None:
            from service.datadog_metrics import emit_health_gauge, metric_tags
            node_ids = [node_id for node_id, name in ((1, "node1"), (2, "node2")) if name in (payload.get("id6") or {})]
            for node_id in node_ids:
                emit_health_gauge("smiot.telemetry.ingest_lag_ms", lag_ms,
                                  metric_tags(farm_key, node_id, source_metadata.get("source", "other")))
        
        # 1. Lưu lưu lượng (id3)
        if "id3" in payload and payload["id3"] is not None:
            flow = payload["id3"]
            try:
                save_telemetry_flow(
                    farm_key,
                    flow.get("f1"),
                    flow.get("f2"),
                    flow.get("t1"),
                    flow.get("t2"),
                    source_metadata=source_metadata,
                )
            except Exception as e:
                print(f"⚠️ Lỗi lưu DB Flow: {e}")

        # 2. Lưu EC nước (id4)
        if "id4" in payload and payload["id4"] is not None:
            ec_data = payload["id4"]
            try:
                save_telemetry_water(
                    farm_key,
                    ph_val=None,
                    ec_val=ec_data.get("ec"),
                    source_metadata=source_metadata,
                )
            except Exception as e:
                print(f"⚠️ Lỗi lưu DB EC nước: {e}")

        # 3. Lưu pH nước (id5)
        if "id5" in payload and payload["id5"] is not None:
            ph_data = payload["id5"]
            try:
                save_telemetry_water(
                    farm_key,
                    ph_val=ph_data.get("ph"),
                    ec_val=None,
                    source_metadata=source_metadata,
                )
            except Exception as e:
                print(f"⚠️ Lỗi lưu DB pH nước: {e}")

        # 4. Lưu Node Cảm biến (id6)
        if "id6" in payload and payload["id6"] is not None:
            nodes = payload["id6"]
            if "node1" in nodes:
                n1 = nodes["node1"]
                try:
                    save_telemetry_node(
                        farm_key,
                        node_id=1,
                        air_temp=n1.get("at"),
                        air_hum=n1.get("ah"),
                        soil_temp=n1.get("st"),
                        soil_hum=n1.get("sh"),
                        ec=n1.get("sec"),
                        source_metadata=source_metadata,
                    )
                    from service.datadog_metrics import emit_node_metrics
                    emit_node_metrics(farm_key, 1, n1, source_metadata.get("source", "device_unclassified"))
                except Exception as e:
                    print(f"⚠️ Lỗi lưu DB Node 1: {e}")
                    
            if "node2" in nodes:
                n2 = nodes["node2"]
                try:
                    save_telemetry_node(
                        farm_key,
                        node_id=2,
                        air_temp=n2.get("at"),
                        air_hum=n2.get("ah"),
                        soil_temp=n2.get("st"),
                        soil_hum=n2.get("sh"),
                        ec=n2.get("sec"),
                        source_metadata=source_metadata,
                    )
                    from service.datadog_metrics import emit_node_metrics
                    emit_node_metrics(farm_key, 2, n2, source_metadata.get("source", "device_unclassified"))
                except Exception as e:
                    print(f"⚠️ Lỗi lưu DB Node 2: {e}")
    except Exception as e:
        print(f"⚠️ Lỗi import hoặc xử lý hàm save_farm_sensor_to_db: {e}")

@traced_mqtt_callback("mqtt.message.process")
def on_message(client, userdata, msg):
    try:
        # Cập nhật thời gian nhận tín hiệu toàn hệ thống
        state["system_last_seen"] = time.time()
        if not state.get("system_is_active", True):
            state["system_is_active"] = True
            add_notification("Hệ thống đã hoạt động trở lại", category="system", severity="info")

        topic = msg.topic
        payload = json.loads(msg.payload.decode())

        if topic == "farm/traceability/event":
            from service.traceability import save_capture_event
            event = save_capture_event(payload)
            logger.info(
                "Đã lưu sự kiện truy xuất vào MongoDB: lot=%s day=%s stage=%s",
                event["lot_id"], event["simulated_day"], event["stage"],
            )
        elif topic == "farm/data":
            process_farm_data(payload)
            trigger_ui_update()
        elif topic == "farm/sensor":
            selected_farm = {
                "Greenhouse A": "greenhouse_a", "Greenhouse B": "greenhouse_b",
                "Greenhouse C": "greenhouse_c", "Greenhouse D": "greenhouse_d",
            }.get(state.get("selected_farm", "Greenhouse A"), "greenhouse_a")
            is_demo_stream = payload.get("source") == "smiot_demo_stream"
            incident_id = payload.get("incident_id")
            if incident_id:
                try:
                    from service.logger import log_incident_event
                    node2 = (payload.get("id6") or {}).get("node2") or {}
                    log_incident_event(
                        incident_id=str(incident_id),
                        farm_key=str(payload.get("farm_key", "unknown")),
                        node_id=2,
                        kind="telemetry_received",
                        measurement="soil_humidity",
                        value_pct=node2.get("sh"),
                        message_id=f"{payload.get('device_id', 'demo')}:{payload.get('boot_id', 'boot')}:{payload.get('sample_sequence', '')}",
                        sample_sequence=payload.get("sample_sequence"),
                        source=payload.get("source", "unknown"),
                    )
                except Exception:
                    pass
            update_selected_ui = not is_demo_stream or payload.get("farm_key", "greenhouse_a") == selected_farm
            if update_selected_ui:
                process_farm_sensor(payload)
            try:
                save_farm_sensor_to_db(payload.get("farm_key", "greenhouse_a"), payload)
                node2 = (payload.get("id6") or {}).get("node2") or {}
                if (incident_id and payload.get("farm_key") == "greenhouse_a"
                        and float(node2.get("sh", -1)) == 2.4):
                    from service.incident_lifecycle import record_fault_sample, record_blocked_irrigation_decision
                    message_id = f"{payload.get('device_id', 'demo')}:{payload.get('boot_id', 'boot')}:{payload.get('sample_sequence', '')}"
                    record_fault_sample(str(incident_id), message_id, float(node2["sh"]))
                    record_blocked_irrigation_decision(str(incident_id), float(node2["sh"]), message_id)
                    from service.incident_lifecycle import add_incident_log_evidence
                    add_incident_log_evidence(str(incident_id), message_id, "flatline_telemetry_received")
            except Exception as db_err:
                print(f"Lỗi lưu DB Sensor: {db_err}")
            if update_selected_ui:
                trigger_ui_update()
        elif topic == "farm/ai":
            amount_ml = payload.get("amount_ml")
            farm_key = payload.get("farm_key", "greenhouse_a")
            state["ai_water_suggest"] = amount_ml if amount_ml is not None else state.get("ai_water_suggest", 0)
            state["van_status"] = payload.get("van_status", state.get("van_status", 0))
            ts = payload.get("timestamp")
            state["ai_time"] = parse_utc_to_local(ts) if ts else datetime.now().strftime("%H:%M:%S")
            
            # Lưu dữ liệu AI suggest vào SQLite DB để phục vụ Bot Telegram
            if amount_ml is not None:
                try:
                    from service.auth import save_ai_water_suggest
                    save_ai_water_suggest(farm_key, float(amount_ml))
                    logger.info(f"Đã lưu gợi ý AI xuống DB: {farm_key} -> {amount_ml} ml")
                except Exception as db_err:
                    logger.error(f"Lỗi lưu AI suggest xuống DB: {db_err}")
            trigger_ui_update()
        elif topic == "farm/status":
            process_farm_status(payload)
            trigger_ui_update()
        elif topic == "farm/command/event":
            from service.operational_evidence import record_action_event
            event_state = str(payload.get("ledger_state", ""))
            if event_state in {"requested", "published", "verified", "failed"}:
                record_action_event(payload, event_state)
                logger.info("smiot_action_ledger command_id=%s state=%s", payload.get("command_id"), event_state)
        elif topic == "farm/command/ack":
            from service.operational_evidence import record_action_event
            record_action_event(payload, "acknowledged")
            logger.info("smiot_action_ledger command_id=%s state=acknowledged target=virtual_device", payload.get("command_id"))
            
    except Exception as e:
        import traceback
        print(f"Lỗi xử lý MQTT: {e}")
        traceback.print_exc()

def start_timeout_checker():
    import threading
    import time
    
    # Đảm bảo các biến lưu hàng đợi được khởi tạo trong state
    if "plc_pending_cmds" not in state:
        state["plc_pending_cmds"] = {}
    if "inv_pending_cmd" not in state:
        state["inv_pending_cmd"] = None

    def checker_loop():
        while True:
            try:
                time.sleep(1.0)
                now = time.time()
                changed = False

                # 1. Kiểm tra Timeout Biến tần (2 phút = 120s)
                inv_pending = state.get("inv_pending_cmd")
                if inv_pending:
                    target_bit = inv_pending.get("target_bit")
                    sch_id = inv_pending.get("schedule_id")
                    
                    # Nếu trạng thái thực nhận được từ Gateway đã khớp (đọc từ inv_real_status)
                    if state.get("inv_real_status", 0) == target_bit:
                        state["inv_pending_cmd"] = None
                        changed = True
                    # Nếu quá 2 phút (120 giây) chưa phản hồi
                    elif now - inv_pending.get("time", now) > 120.0:
                        if sch_id:
                            # Chế độ tự động (Auto): Cập nhật cơ sở dữ liệu lịch trình thành failed (LỖI)
                            from service import auth as service_auth
                            try:
                                service_auth.update_schedule_status(sch_id, "failed")
                                # Đồng thời cập nhật trạng thái bản ghi nhật ký (logs) sang failed
                                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                service_auth.update_schedule_log(sch_id, now_str, 0.0, "failed")
                            except Exception as db_err:
                                print(f"❌ [SCADA TIMEOUT] Lỗi cập nhật trạng thái DB: {db_err}")
                            
                            action_str = "kích hoạt" if target_bit == 1 else "tắt"
                            add_notification(f"❌ Cảnh báo: Biến tần không phản hồi {action_str} tự động lịch trình #{sch_id} sau 2 phút!", category="inverter", severity="error")
                            print(f"❌ [SCADA TIMEOUT] Lịch trình #{sch_id} {action_str} Biến tần thất bại!")
                        else:
                            # Chế độ thủ công (Manual)
                            action_str = "bật" if target_bit == 1 else "tắt"
                            add_notification(f"❌ Cảnh báo: Biến tần không phản hồi lệnh {action_str} sau 2 phút!", category="inverter", severity="error")
                        
                        # Rollback nút bấm và trạng thái gạt về trạng thái thực tế cũ trước lệnh
                        state["inv_status"] = 0 if target_bit == 1 else 1
                        state["inv_online"] = 0
                        state["inv_locked"] = False
                        # Reset thời gian khóa để xóa cooldown 30s lập tức
                        state["inv_lock_time"] = 0
                        state["inv_pending_cmd"] = None
                        changed = True

                # 2. Kiểm tra Timeout PLC Pumps (10s - Theo rơ-le Q)
                plc_pending = state.get("plc_pending_cmds")
                if plc_pending:
                    # print(f"⏰ [DEBUG SCADA] Đang có {len(plc_pending)} lệnh PLC chờ: {plc_pending}")
                    to_remove = []
                    for idx, cmd in list(plc_pending.items()):
                        target_val = cmd.get("target_val")
                        q_key = f"q{idx}"
                        cmd_time = cmd.get("time", now)
                        elapsed = now - cmd_time
                        # print(f"   -> Bơm {idx + 1}: Mục tiêu={target_val}, Rơ-le thực tế={state.get(q_key, 0)}, Đã trôi qua={elapsed:.1f}s")
                        
                        # Nếu rơ-le vật lý thực tế đã đạt trạng thái mong muốn
                        if state.get(q_key, 0) == target_val:
                            # print(f"   ✅ Bơm {idx + 1} phản hồi thành công! Xóa khỏi hàng đợi.")
                            to_remove.append(idx)
                            changed = True
                        # Nếu quá 10 giây chưa có phản hồi
                        elif elapsed > 10.0:
                            print(f"   ❌ Bơm {idx + 1} Hết giờ phản hồi (Timeout)! Bắn cảnh báo.")
                            add_notification(f"❌ Cảnh báo: Bơm {idx + 1} không phản hồi tiếp điểm Q{idx} sau 10 giây!", category="plc", severity="error")
                            to_remove.append(idx)
                            # Rollback trạng thái nút bấm về bằng rơ-le Q thực tế
                            state[f"bit{idx}"] = state.get(q_key, 0)
                            changed = True
                            
                    for idx in to_remove:
                        plc_pending.pop(idx, None)

                if changed:
                    trigger_ui_update()

            except Exception as e:
                print(f"Error in SCADA timeout checker: {e}")

    t = threading.Thread(target=checker_loop, daemon=True)
    t.start()
    print("🚀 Đã khởi động Trọng tài quét ngầm SCADA (Inverter 2p, PLC 10s)")

def start_mqtt():
    global mqtt_client
    client = mqtt.Client()
    mqtt_client = client
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.subscribe("farm/data")
        client.subscribe("farm/sensor")
        client.subscribe("farm/ai")
        client.subscribe("farm/status")
        client.subscribe("farm/traceability/event")
        client.subscribe("farm/command/event")
        client.subscribe("farm/command/ack")
        client.loop_start()
        print("Đã khởi động MQTT Client thành công!")
        
        # Khởi chạy trọng tài quét ngầm
        start_timeout_checker()
    except Exception as e:
        print(f"Không thể khởi động MQTT: {e}")
