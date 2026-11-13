import json
import paho.mqtt.client as mqtt
from pages.home import state
from datetime import datetime, timedelta, timezone
import time
from uuid import uuid4
from service.logger import get_logger
from service.observability import inject_mqtt_trace_context, traced, traced_mqtt_callback

logger = get_logger("MQTT")

mqtt_client = None


def prepare_actuator_command(topic, payload_dict, timeout_seconds=None):
    """Attach farm-scoped command identity and register its expected ACK deadline."""
    if topic not in {"farm/inverter", "farm/control"} or not isinstance(payload_dict, dict):
        return payload_dict

    from service.farm_registry import FARM_KEYS

    payload = dict(payload_dict)
    farm_key = str(payload.get("farm_key") or "").strip()
    if farm_key not in FARM_KEYS:
        raise ValueError("farm_key is required for farm-scoped actuator commands")

    is_inverter = topic == "farm/inverter"
    if is_inverter:
        target = payload.get("bit")
        channels = [("inverter", target)] if target in (0, 1, False, True, "0", "1") else []
        timeout = float(timeout_seconds or 120)
        actuator = "inverter"
    else:
        channels = []
        for index in range(8):
            value = payload.get(f"bit{index}")
            if value in (0, 1, False, True, "0", "1"):
                channels.append((f"q{index}", value))
        timeout = float(timeout_seconds or 10)
        actuator = "plc_pump"

    if not channels:
        return payload

    command_id = str(payload.get("command_id") or uuid4().hex)[:128]
    started_at = time.time()
    ack_deadline = started_at + max(1.0, timeout)
    payload.update({"farm_key": farm_key, "command_id": command_id})

    pending = state.setdefault("actuator_pending_by_command", {})
    current = state.setdefault("actuator_current_by_scope", {})
    for channel, target in channels:
        scope = f"{farm_key}|{actuator}|{channel}"
        previous_id = current.get(scope)
        previous = pending.get(previous_id) if previous_id else None
        if previous and previous.get("status") == "pending":
            # A newer command supersedes the old expected state on this exact farm/channel.
            previous["status"] = "superseded"
            previous["superseded_at"] = started_at
        record_id = f"{command_id}|{channel}"
        pending[record_id] = {
            "command_id": command_id,
            "farm_key": farm_key,
            "actuator": actuator,
            "channel": channel,
            "target": int(target in (1, True, "1")),
            "requested_at": started_at,
            "ack_deadline": ack_deadline,
            "status": "pending",
            "timeout_emitted": False,
            "synthetic": bool(payload.get("synthetic", False)),
            "incident_id": payload.get("incident_id"),
            "monitor_id": payload.get("monitor_id"),
        }
        current[scope] = record_id

    # Bound this operational cache if an upstream device stops replying indefinitely.
    while len(pending) > 500:
        oldest_id = next(iter(pending))
        pending.pop(oldest_id, None)
    return payload


def _set_actuator_publish_status(payload, topic, published):
    command_id = str(payload.get("command_id") or "")
    farm_key = str(payload.get("farm_key") or "")
    if not command_id or not farm_key:
        return
    pending = state.get("actuator_pending_by_command") or {}
    for record in pending.values():
        if record.get("command_id") == command_id and record.get("farm_key") == farm_key:
            if record.get("status") in {"acknowledged", "unacknowledged", "superseded"}:
                continue
            record["status"] = "pending" if published else "publish_failed"
            record["published_at"] = time.time() if published else None
            record["publish_topic"] = topic


def _record_matching_actuator_ack(payload, source="ack"):
    """Close only pending commands whose command ID and farm both match the device reply."""
    command_id = str(payload.get("command_id") or "").strip()
    farm_key = str(payload.get("farm_key") or "").strip()
    if not command_id or not farm_key:
        return False

    from service.farm_registry import FARM_KEYS
    if farm_key not in FARM_KEYS:
        return False

    pending = state.get("actuator_pending_by_command") or {}
    matched = [record for record in pending.values()
               if record.get("command_id") == command_id
               and record.get("farm_key") == farm_key
               # A timeout is an observation, not cancellation. Accept a late
               # matching device ACK so the ledger can close the same command
               # without permitting a retry or accepting another command's ACK.
               and record.get("status") in {"pending", "unacknowledged"}]
    if not matched:
        return False

    for record in matched:
        late_ack = record.get("status") == "unacknowledged"
        if record.get("actuator") == "inverter":
            observed = payload.get("bit", payload.get("status"))
        else:
            channel = str(record.get("channel") or "")
            bit_key = channel.replace("q", "bit", 1)
            outputs = payload.get("virtual_output") or payload.get("outputs") or {}
            observed = outputs.get(bit_key, payload.get(channel, payload.get(bit_key)))
        if observed is not None:
            record["target_matches"] = int(observed in (1, True, "1")) == record.get("target")
        else:
            record["target_matches"] = None
        record["status"] = "acknowledged"
        record["acknowledged_at"] = time.time()
        record["late_ack"] = late_ack
        record["ack_source"] = source
        verified = payload.get("verified")
        record["ack_verified"] = (
            record.get("target_matches") is True if verified is None
            else bool(verified) and record.get("target_matches") is not False
        )
        current = state.get("actuator_current_by_scope") or {}
        scope = f"{farm_key}|{record['actuator']}|{record['channel']}"
        if current.get(scope) == f"{command_id}|{record['channel']}":
            current.pop(scope, None)

    try:
        from service.datadog_metrics import emit_count
        for actuator in sorted({record["actuator"] for record in matched}):
            emit_count("smiot.actuator.command_acknowledged", [
                f"farm:{farm_key}", f"actuator:{actuator}", "event:acknowledged",
                f"source:{'device_ack' if source == 'ack' else 'device_readback'}",
            ])
        for actuator in sorted({record["actuator"] for record in matched if record.get("late_ack")}):
            emit_count("smiot.actuator.command_late_acknowledged", [
                f"farm:{farm_key}", f"actuator:{actuator}", "event:late_acknowledged",
                f"source:{'device_ack' if source == 'ack' else 'device_readback'}",
            ])
    except Exception as exc:
        logger.debug("Could not emit actuator ACK metric (%s)", type(exc).__name__)

    incident_ids = sorted({str(record.get("incident_id")) for record in matched
                           if record.get("incident_id")})
    logger.info(json.dumps({
        "event": "smiot_actuator_command_acknowledged",
        "farm_key": farm_key,
        "command_id": command_id,
        "channels": [record["channel"] for record in matched],
        "target_matches": all(record.get("target_matches") is True for record in matched),
        "device_verified": all(record.get("ack_verified") is True for record in matched),
        "late_ack": any(record.get("late_ack") is True for record in matched),
        "incident_id": incident_ids[0] if len(incident_ids) == 1 else None,
        "source": source,
        "synthetic": bool(payload.get("synthetic", False)),
    }, separators=(",", ":")))

    # Keep the legacy UI pending indicators in sync only for this exact command.
    inv_pending = state.get("inv_pending_cmd")
    if (inv_pending and inv_pending.get("command_id") == command_id
            and inv_pending.get("farm_key") == farm_key):
        state["inv_pending_cmd"] = None
    plc_pending = state.get("plc_pending_cmds") or {}
    for channel, command in list(plc_pending.items()):
        if command.get("command_id") == command_id and command.get("farm_key") == farm_key:
            plc_pending.pop(channel, None)
    return True

@traced("mqtt.publish")
def publish_mqtt(topic, payload_dict):
    global mqtt_client
    actuator_command = topic in {"farm/inverter", "farm/control"}
    if mqtt_client:
        try:
            info = mqtt_client.publish(topic, json.dumps(inject_mqtt_trace_context(dict(payload_dict))))
            published = getattr(info, "rc", mqtt.MQTT_ERR_SUCCESS) == mqtt.MQTT_ERR_SUCCESS
            if actuator_command:
                _set_actuator_publish_status(payload_dict, topic, published)
            logger.info(f"Đã publish lên {topic}: {payload_dict}")
            return published
        except Exception as e:
            if actuator_command:
                _set_actuator_publish_status(payload_dict, topic, False)
            print(f"Lỗi publish MQTT: {e}")
            return False
    if actuator_command:
        _set_actuator_publish_status(payload_dict, topic, False)
    return False

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
    """ Xử lý dữ liệu Inverter / thiết bị công nghiệp trong đúng farm scope """
    if payload.get("device_name") == "Inverter":
        farm_key = str(payload.get("farm_key", "greenhouse_a"))
        if state.get("_inverter_state_farm") != farm_key:
            state["_inverter_state_farm"] = farm_key
            state["inv_has_started"] = False
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

                    pending_run = [s for s in get_schedules(farm_key) if s['status'] == 'pending_run']
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
                    # Chỉ cập nhật lịch thuộc farm của inverter vừa gửi trạng thái.
                    running = [s for s in get_schedules(farm_key) if s['status'] == 'running']
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
        state["virtual_plc_feedback"] = {
            **(state.get("virtual_plc_feedback") or {}),
            "farm_key": payload.get("farm_key", "greenhouse_a"),
            "flow_line1_lpm": flow.get("f1"), "flow_line2_lpm": flow.get("f2"),
            "flow_line1_total_l": flow.get("t1"), "flow_line2_total_l": flow.get("t2"),
            "pressure_bar": flow.get("pressure_bar"),
            "safe_mode_active": flow.get("safe_mode_active"),
            "fault": flow.get("fault"),
            "pump_line1_on": flow.get("pump_line1_on"), "pump_line2_on": flow.get("pump_line2_on"),
            "valve_open": flow.get("valve_open"), "flow_updated_at": ts,
        }
        try:
            from service.datadog_metrics import emit_actuator_metrics
            emit_actuator_metrics(
                payload.get("farm_key", "greenhouse_a"),
                {key: state["virtual_plc_feedback"].get(key) for key in (
                    "flow_line1_lpm", "flow_line2_lpm", "flow_line1_total_l",
                    "flow_line2_total_l", "pressure_bar", "pump_line1_on",
                    "pump_line2_on", "valve_open", "safe_mode_active",
                )},
                str(payload.get("source") or "device_unclassified"),
            )
        except Exception as exc:
            logger.debug("Could not emit actuator feedback metric (%s)", type(exc).__name__)

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

    # Additive virtual feedback channels. These enrich the existing id3-id6 UI
    # and do not alter the legacy sensor payload contract.
    if "id7" in payload and isinstance(payload["id7"], dict):
        drain = payload["id7"]
        state["virtual_plc_feedback"] = {
            **(state.get("virtual_plc_feedback") or {}),
            "farm_key": payload.get("farm_key", "greenhouse_a"),
            "drain_l": drain.get("drain_l"), "drain_ec_ms_cm": drain.get("drain_ec_ms_cm"),
            "drain_updated_at": drain.get("measured_at") or drain.get("timestamp"),
        }
    if "id8" in payload and isinstance(payload["id8"], dict):
        ventilation = payload["id8"]
        state["virtual_plc_feedback"] = {
            **(state.get("virtual_plc_feedback") or {}),
            "farm_key": payload.get("farm_key", "greenhouse_a"),
            "vent_cmd": ventilation.get("command"), "vent_state": ventilation.get("state"),
            "fan_rpm": ventilation.get("fan_rpm"), "vent_stuck": ventilation.get("stuck"),
            "vent_updated_at": ventilation.get("measured_at") or ventilation.get("timestamp"),
        }
        try:
            from service.datadog_metrics import emit_actuator_metrics
            emit_actuator_metrics(
                payload.get("farm_key", "greenhouse_a"),
                {"fan_rpm": ventilation.get("fan_rpm"),
                 "vent_cmd": ventilation.get("command"),
                 "vent_state": ventilation.get("state")},
                str(payload.get("source") or "device_unclassified"),
            )
        except Exception as exc:
            logger.debug("Could not emit ventilation feedback metric (%s)", type(exc).__name__)

    # 4. Xử lý dữ liệu Node Cảm biến - id6
    if "id6" in payload and payload["id6"] is not None:
        nodes = payload["id6"]
        
        # Every received sample is evidence of a live path. Offline/stale is NOT
        # decided here: telemetry_health.compute_node_status (newest sample in
        # MongoDB) is the single source of truth. Here a freshly received sample
        # is only mapped through the same function (age 0 -> ONLINE).
        from service.telemetry_health import compute_node_status
        n1_online = "node1" in nodes
        n2_online = "node2" in nodes
        ts1 = nodes["node1"].get("timestamp") if n1_online else None
        ts2 = nodes["node2"].get("timestamp") if n2_online else None
        received_now = datetime.now()
        fault = state.get("fault_stale_cache")  # synthetic injected display-cache fault (demo)
        farm_of_payload = payload.get("farm_key", "greenhouse_a")

        def _cache_fault_active(node_id):
            return (isinstance(fault, dict) and fault.get("node") == node_id
                    and fault.get("farm", farm_of_payload) == farm_of_payload)

        # Gửi thông báo kết nối lại
        if n1_online and state.get("node1_status") in ("OFFLINE", "STALE") and not _cache_fault_active(1):
            add_notification("Node 1 đã kết nối lại", category="sensor", severity="info")
        if n2_online and state.get("node2_status") in ("OFFLINE", "STALE") and not _cache_fault_active(2):
            add_notification("Node 2 đã kết nối lại", category="sensor", severity="info")

        # Cập nhật dữ liệu cảm biến
        if "node1" in nodes:
            n1 = nodes["node1"]
            if n1_online:
                if not _cache_fault_active(1):
                    state["node1_status"] = compute_node_status(received_now, received_now)["status"]
                    state["node1_last_change_time"] = time.time()
                state["node1_raw_ts"] = ts1
            state["node1_air_temp"] = n1.get("at", state.get("node1_air_temp", 0.0))
            state["node1_air_hum"] = n1.get("ah", state.get("node1_air_hum", 0.0))
            state["node1_soil_temp"] = n1.get("st", state.get("node1_soil_temp", 0.0))
            state["node1_soil_hum"] = n1.get("sh", state.get("node1_soil_hum", 0.0))
            state["node1_ec"] = n1.get("sec", state.get("node1_ec", 0.0))
            state["node1_updated"] = parse_utc_to_local(ts1) if ts1 else datetime.now().strftime("%H:%M:%S")

        if "node2" in nodes:
            n2 = nodes["node2"]
            if n2_online:
                if not _cache_fault_active(2):
                    state["node2_status"] = compute_node_status(received_now, received_now)["status"]
                    state["node2_last_change_time"] = time.time()
                state["node2_raw_ts"] = ts2
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
    feedback = state.get("virtual_plc_feedback") or {}
    virtual = payload.get("device_name") == "SMIOT Virtual PLC" or payload.get("source") == "smiot_demo_stream"
    if virtual:
        outputs = payload.get("virtual_output")
        if not isinstance(outputs, dict):
            outputs = {f"bit{i}": payload.get(f"bit{i}", payload.get(f"q{i}", 0)) for i in range(8)}
        feedback.update({
            "farm_key": payload.get("farm_key", feedback.get("farm_key", "greenhouse_a")),
            "virtual_output": outputs,
            "safe_mode_active": payload.get("safe_mode_active", feedback.get("safe_mode_active")),
            "valve_cmd": payload.get("valve_cmd", feedback.get("valve_cmd")),
            "valve_state": payload.get("valve_state", feedback.get("valve_state")),
            "vent_cmd": payload.get("vent_cmd", feedback.get("vent_cmd")),
            "vent_state": payload.get("vent_state", feedback.get("vent_state")),
            "fan_rpm": payload.get("fan_rpm", feedback.get("fan_rpm")),
            "fault": payload.get("fault", feedback.get("fault")),
            "source": payload.get("source", "device_unclassified"),
            "updated_at": ts or datetime.now(timezone.utc).isoformat(),
        })
        state["virtual_plc_feedback"] = feedback


def _persist_virtual_sensor_channel(farm_key, envelope, channel, readings):
    """Append one additive virtual-device sample to the shared Mongo time series."""
    try:
        from service.mongodb_store import collection
        from service.telemetry_provenance import metadata_for_payload

        device_type = str(channel.get("device_type") or "virtual_sensor")[:48]
        device_id = channel.get("device_id")
        metadata = metadata_for_payload(
            {**envelope, **channel},
            track_key=(farm_key, device_type, str(device_id or device_type)),
        )
        metadata.update({
            "farm_key": farm_key,
            # Scenario scope must be declared by this device channel itself.
            # A top-level run may belong to another stream in the same envelope.
            "scenario_run_id": channel.get("scenario_run_id"),
            "lot_id": envelope.get("lot_id"),
            "incident_id": envelope.get("incident_id"),
        })
        metadata = {key: value for key, value in metadata.items() if value is not None}
        try:
            from service.datadog_metrics import emit_device_provenance_metrics
            emit_device_provenance_metrics(
                farm_key, device_type, metadata.get("source", "device_unclassified"), metadata,
            )
        except Exception as exc:
            logger.debug("Could not emit device provenance metric (%s)", type(exc).__name__)
        collection("telemetry").insert_one({
            "timestamp": metadata["app_received_at"],
            "meta": {"farm_key": farm_key, "source_table": f"telemetry_{channel['device_type']}",
                     "measurement_type": channel["device_type"]},
            "readings": readings,
            "source": {"table": f"telemetry_{channel['device_type']}", **metadata},
        })
        return True
    except Exception as exc:
        logger.warning("MongoDB could not persist virtual %s feedback (%s)", channel.get("device_type"),
                       type(exc).__name__)
        return False


def _record_scenario_ack(payload):
    """Persist simulator truth and refresh the UI projection without coupling failures."""
    run_id = str(payload.get("scenario_run_id", "")).strip()
    command_id = str(payload.get("command_id", "")).strip()
    status = str(payload.get("status", ""))
    if not run_id or not command_id or status not in {"started", "stopped", "rejected"}:
        return
    ack_at = payload.get("timestamp") or datetime.now(timezone.utc).isoformat()
    applied = payload.get("applied") if isinstance(payload.get("applied"), bool) else None
    message = str(payload.get("reason") or {
        "started": "Thiết bị đã xác nhận và áp dụng kịch bản.",
        "stopped": "Thiết bị đã xác nhận dừng kịch bản.",
        "rejected": "Thiết bị từ chối lệnh kịch bản.",
    }.get(status, "Đã nhận phản hồi kịch bản từ thiết bị."))[:240]
    ack = {"scenario_run_id": run_id, "command_id": command_id, "status": status,
           "applied": applied, "acknowledged_at": ack_at,
           "scenario_code": payload.get("scenario_code"),
           "scenario_type": payload.get("scenario_type"),
           "reason": payload.get("reason"), "message": message}
    by_run = state.setdefault("demo_scenario_ack_by_run", {})
    run_ack = by_run.setdefault(run_id, {"scenario_run_id": run_id, "acks": []})
    run_ack["acks"] = [item for item in run_ack.get("acks", []) if item.get("command_id") != command_id]
    run_ack["acks"].append(dict(ack))
    run_ack.update(ack)
    # Bound process-local UI history; durable event history is owned by Mongo.
    while len(by_run) > 50:
        by_run.pop(next(iter(by_run)))
    current = state.get("demo_scenario_control") or {}
    current_run = str(current.get("scenario_run_id") or "")
    expected_commands = {str(current.get(key) or "") for key in ("command_id", "start_command_id", "stop_command_id")}
    matches_current = not current_run or (
        current_run == run_id and (not any(expected_commands) or command_id in expected_commands)
    )
    if matches_current:
        current.update(ack)
        current["ack_persisted"] = None
        state["demo_scenario_control"] = current

    persisted = False
    inserted = False
    try:
        from service.mongodb_store import database
        from service.scenario_evidence import record_scenario_ack
        inserted = bool(record_scenario_ack(payload, db=database()))
        persisted = True  # False means idempotent replay, not failed persistence.
    except Exception as exc:
        logger.warning("Scenario ACK Mongo persistence failed (%s)", type(exc).__name__)
    run_ack["ack_persisted"] = persisted
    run_ack["duplicate_ack"] = not inserted if persisted else False
    if matches_current:
        state["demo_scenario_control"]["ack_persisted"] = persisted
        state["demo_scenario_control"]["duplicate_ack"] = not inserted if persisted else False


def _record_virtual_device_profile_ack(payload):
    """Persist a Velxio dataset switch ACK, scoped to the original command and farm."""
    farm_key = str(payload.get("farm_key") or "")
    profile_command_id = str(payload.get("profile_command_id") or "")
    node_id = str(payload.get("node_id") or "")
    if farm_key not in __import__("service.farm_registry", fromlist=["FARM_KEYS"]).FARM_KEYS:
        return
    if not profile_command_id or node_id not in {"node1", "node2", "flow"}:
        return
    if payload.get("source") != "velxio_synthetic" or payload.get("synthetic") is not True:
        return
    event = {key: payload.get(key) for key in (
        "command_id", "profile_command_id", "incident_id", "scenario_run_id", "scenario_code",
        "farm_key", "device_id", "node_id", "profile", "dataset_id", "applied", "verified",
        "source", "synthetic", "timestamp",
    )}
    event["received_at"] = datetime.now(timezone.utc)
    event["event"] = "virtual_device_profile_ack"
    try:
        from service.mongodb_store import collection
        collection("device_profile_events").update_one(
            {"_id": profile_command_id}, {"$set": event}, upsert=True,
        )
    except Exception as exc:
        logger.warning("Velxio profile ACK Mongo persistence failed (%s)", type(exc).__name__)
    history = state.setdefault("velxio_profile_ack_by_node", {})
    history[f"{farm_key}|{node_id}"] = event
    logger.info(json.dumps({"event": "virtual_device_profile_ack_persisted",
                            "farm_key": farm_key, "node_id": node_id,
                            "profile": event.get("profile"), "dataset_id": event.get("dataset_id"),
                            "command_id": event.get("command_id"), "incident_id": event.get("incident_id"),
                            "applied": event.get("applied"), "verified": event.get("verified"),
                            "synthetic": True}, separators=(",", ":")))
    trigger_ui_update()

def trigger_ui_update():
    """ Tăng biến đếm để báo hiệu UI cần cập nhật """
    state["_update_counter"] = state.get("_update_counter", 0) + 1

def _emit_samples_persisted(farm_key, node_id, source):
    """Additive counter: one per node sample successfully written to MongoDB."""
    try:
        from service.datadog_metrics import emit_count, metric_tags
        emit_count("smiot.telemetry.samples_persisted", metric_tags(farm_key, node_id, source))
    except Exception:
        pass


@traced("smiot.telemetry.persist")
def save_farm_sensor_to_db(farm_key, payload):
    """Lưu dữ liệu cảm biến riêng lẻ dựa theo các key tương ứng trong payload MQTT."""
    try:
        from service.auth import save_telemetry_flow, save_telemetry_water, save_telemetry_node
        from service.telemetry_provenance import metadata_for_payload
        source_metadata = metadata_for_payload(payload)
        source_metadata["farm_key"] = farm_key
        # Broker-side evidence for failure-domain classification (producer vs app/ingest).
        from service.telemetry_health import note_broker_message
        for _nid, _name in ((1, "node1"), (2, "node2")):
            if _name in (payload.get("id6") or {}):
                note_broker_message(farm_key, _nid)
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
            flow_metadata = metadata_for_payload(
                {**payload, **flow, **({"scenario_run_id": flow["scenario_run_id"]}
                                         if flow.get("scenario_run_id") else {})},
                track_key=(farm_key, "flow_meter", str(flow.get("device_id") or "id3")),
            )
            flow_metadata["farm_key"] = farm_key
            if flow.get("scenario_run_id"):
                flow_metadata["scenario_run_id"] = str(flow["scenario_run_id"])[:100]
            try:
                from service.datadog_metrics import emit_device_provenance_metrics
                emit_device_provenance_metrics(
                    farm_key, "flow_meter", flow_metadata.get("source", "device_unclassified"), flow_metadata,
                )
            except Exception as exc:
                logger.debug("Could not emit flow provenance metric (%s)", type(exc).__name__)
            try:
                save_telemetry_flow(
                    farm_key,
                    flow.get("f1"),
                    flow.get("f2"),
                    flow.get("t1"),
                    flow.get("t2"),
                    source_metadata=flow_metadata,
                )
            except Exception as e:
                print(f"⚠️ Lỗi lưu DB Flow: {e}")

        # 2. Lưu EC nước (id4)
        if "id4" in payload and payload["id4"] is not None:
            ec_data = payload["id4"]
            ec_metadata = metadata_for_payload(
                {**payload, **ec_data, **({"scenario_run_id": ec_data["scenario_run_id"]}
                                           if ec_data.get("scenario_run_id") else {})},
                track_key=(farm_key, "ec_sensor", str(ec_data.get("device_id") or "id4")),
            )
            ec_metadata["farm_key"] = farm_key
            if ec_data.get("scenario_run_id"):
                ec_metadata["scenario_run_id"] = str(ec_data["scenario_run_id"])[:100]
            try:
                from service.datadog_metrics import emit_device_provenance_metrics
                emit_device_provenance_metrics(farm_key, "ec_sensor", ec_metadata.get("source", "device_unclassified"), ec_metadata)
            except Exception as exc:
                logger.debug("Could not emit EC provenance metric (%s)", type(exc).__name__)
            try:
                save_telemetry_water(
                    farm_key,
                    ph_val=None,
                    ec_val=ec_data.get("ec"),
                    source_metadata=ec_metadata,
                )
            except Exception as e:
                print(f"⚠️ Lỗi lưu DB EC nước: {e}")

        # 3. Lưu pH nước (id5)
        if "id5" in payload and payload["id5"] is not None:
            ph_data = payload["id5"]
            ph_metadata = metadata_for_payload(
                {**payload, **ph_data, **({"scenario_run_id": ph_data["scenario_run_id"]}
                                           if ph_data.get("scenario_run_id") else {})},
                track_key=(farm_key, "ph_sensor", str(ph_data.get("device_id") or "id5")),
            )
            ph_metadata["farm_key"] = farm_key
            if ph_data.get("scenario_run_id"):
                ph_metadata["scenario_run_id"] = str(ph_data["scenario_run_id"])[:100]
            try:
                from service.datadog_metrics import emit_device_provenance_metrics
                emit_device_provenance_metrics(farm_key, "ph_sensor", ph_metadata.get("source", "device_unclassified"), ph_metadata)
            except Exception as exc:
                logger.debug("Could not emit pH provenance metric (%s)", type(exc).__name__)
            try:
                save_telemetry_water(
                    farm_key,
                    ph_val=ph_data.get("ph"),
                    ec_val=None,
                    source_metadata=ph_metadata,
                )
            except Exception as e:
                print(f"⚠️ Lỗi lưu DB pH nước: {e}")

        # 4. Lưu Node Cảm biến (id6)
        if "id6" in payload and payload["id6"] is not None:
            nodes = payload["id6"]
            persisted_node_ids = set()
            if "node1" in nodes:
                n1 = nodes["node1"]
                node_metadata = metadata_for_payload({**payload, **n1}, track_key=(farm_key, 1))
                node_metadata["farm_key"] = farm_key
                if n1.get("scenario_run_id"):
                    node_metadata["scenario_run_id"] = str(n1["scenario_run_id"])[:100]
                try:
                    from service.datadog_metrics import emit_provenance_metrics
                    emit_provenance_metrics(farm_key, 1, node_metadata.get("source", "device_unclassified"), node_metadata)
                except Exception as exc:
                    logger.debug("Could not emit node provenance metric (%s)", type(exc).__name__)
                try:
                    save_telemetry_node(
                        farm_key,
                        node_id=1,
                        air_temp=n1.get("at"),
                        air_hum=n1.get("ah"),
                        soil_temp=n1.get("st"),
                        soil_hum=n1.get("sh"),
                        ec=n1.get("sec"),
                        source_metadata=node_metadata,
                    )
                    from service.datadog_metrics import emit_node_metrics
                    emit_node_metrics(farm_key, 1, n1, node_metadata.get("source", "device_unclassified"))
                    _emit_samples_persisted(farm_key, 1, node_metadata.get("source", "device_unclassified"))
                    from service.detector_heartbeat import mark_detector_input
                    mark_detector_input(farm_key)
                    persisted_node_ids.add(1)
                except Exception as e:
                    print(f"⚠️ Lỗi lưu DB Node 1: {e}")
                    
            if "node2" in nodes:
                n2 = nodes["node2"]
                node_metadata = metadata_for_payload({**payload, **n2}, track_key=(farm_key, 2))
                node_metadata["farm_key"] = farm_key
                if n2.get("scenario_run_id"):
                    node_metadata["scenario_run_id"] = str(n2["scenario_run_id"])[:100]
                try:
                    from service.datadog_metrics import emit_provenance_metrics
                    emit_provenance_metrics(farm_key, 2, node_metadata.get("source", "device_unclassified"), node_metadata)
                except Exception as exc:
                    logger.debug("Could not emit node provenance metric (%s)", type(exc).__name__)
                try:
                    save_telemetry_node(
                        farm_key,
                        node_id=2,
                        air_temp=n2.get("at"),
                        air_hum=n2.get("ah"),
                        soil_temp=n2.get("st"),
                        soil_hum=n2.get("sh"),
                        ec=n2.get("sec"),
                        source_metadata=node_metadata,
                    )
                    from service.datadog_metrics import emit_node_metrics
                    emit_node_metrics(farm_key, 2, n2, node_metadata.get("source", "device_unclassified"))
                    _emit_samples_persisted(farm_key, 2, node_metadata.get("source", "device_unclassified"))
                    from service.detector_heartbeat import mark_detector_input
                    mark_detector_input(farm_key)
                    persisted_node_ids.add(2)
                except Exception as e:
                    print(f"⚠️ Lỗi lưu DB Node 2: {e}")

            try:
                from service.telemetry_findings import evaluate_and_persist_scenario_findings
                finding_payload = {
                    "farm_key": farm_key,
                    "source": source_metadata.get("source", "device_unclassified"),
                    "id6": {
                        name: node for name, node in nodes.items()
                        if isinstance(node, dict) and node.get("scenario_run_id")
                    },
                }
                if finding_payload["id6"]:
                    evaluate_and_persist_scenario_findings(finding_payload)
            except Exception as exc:
                logger.warning("Scenario sensor finding evaluation failed (%s)", type(exc).__name__)

            # Shared, advisory-only melon thresholds run for every farm after
            # its sample is persisted. They write transition notices to MongoDB
            # but never issue actuator commands.
            for _name, _node_id in (("node1", 1), ("node2", 2)):
                _readings = nodes.get(_name)
                if not isinstance(_readings, dict):
                    continue
                try:
                    from service.agronomic_thresholds import record_reading_transition
                    record_reading_transition(farm_key, _node_id, _readings)
                    from service.detector_heartbeat import has_advisory_input, mark_detector_evaluation
                    if _node_id in persisted_node_ids and has_advisory_input(_readings):
                        mark_detector_evaluation(farm_key)
                        from service.datadog_metrics import emit_count
                        emit_count("smiot.detector.advisory_evaluation.completed", [
                            "detector:agronomic_advisory", "result:completed",
                        ])
                except Exception as exc:
                    logger.warning("Agronomic advisory persistence failed (%s)", type(exc).__name__)

        # Additive drain and ventilation virtual-device records. Keep them in
        # the common telemetry time series with stable metadata dimensions.
        for key, device_type, fields in (
            ("id7", "drain_sensor", ("drain_l", "drain_ec_ms_cm")),
            ("id8", "ventilation_feedback", ("command", "state", "fan_rpm", "stuck")),
        ):
            channel = payload.get(key)
            if isinstance(channel, dict):
                readings = {name: channel[name] for name in fields if name in channel and channel[name] is not None}
                if readings:
                    _persist_virtual_sensor_channel(
                        farm_key, payload, {**channel, "device_type": device_type}, readings,
                    )
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

        if topic == "farm/demo/device_profile/ack":
            _record_virtual_device_profile_ack(payload)
        elif topic == "farm/traceability/event":
            from service.traceability import save_capture_event
            event = save_capture_event(payload)
            logger.info(
                "Đã lưu sự kiện truy xuất vào MongoDB: lot=%s day=%s stage=%s",
                event["lot_id"], event["simulated_day"], event["stage"],
            )
        elif topic == "farm/data":
            from service.farm_registry import FARM_KEYS_BY_LABEL
            selected_farm = FARM_KEYS_BY_LABEL.get(state.get("selected_farm", "Greenhouse A"), "greenhouse_a")
            if payload.get("source") != "smiot_demo_stream" or payload.get("farm_key", "greenhouse_a") == selected_farm:
                process_farm_data(payload)
                trigger_ui_update()
        elif topic == "farm/sensor":
            from service.farm_registry import FARM_KEYS_BY_LABEL
            selected_farm = FARM_KEYS_BY_LABEL.get(state.get("selected_farm", "Greenhouse A"), "greenhouse_a")
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
            from service.ai_service import classify_ai_payload
            ai = classify_ai_payload(payload)
            amount_ml = ai["amount_ml"]
            farm_key = payload.get("farm_key", "greenhouse_a")
            # amount_ml=None (no data / provider error) must never be shown as 0 ml
            # nor keep an old value: 0 ml is only a real "no water" recommendation.
            state["ai_water_suggest"] = amount_ml
            state["ai_status"] = ai["status"]
            state["ai_reason"] = ai["reason"]
            if ai["hold"] or amount_ml is None:
                # Any non ok/no_water AI status (error, timeout, no_data, missing) -> HOLD:
                # never show the valve as open from this message.
                state["van_status"] = 0
                logger.warning(json.dumps({"event": "smiot_ai_hold", "farm": farm_key,
                                           "ai_status": ai["status"], "reason": ai["reason"],
                                           "action": "HOLD_no_irrigation_command"}, separators=(",", ":")))
            else:
                state["van_status"] = payload.get("van_status", state.get("van_status", 0))
            ts = payload.get("timestamp")
            # Giờ hiển thị luôn là giờ Việt Nam (UTC+7), kể cả khi server (EC2) chạy UTC.
            state["ai_time"] = parse_utc_to_local(ts) if ts else datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S")

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
            if payload.get("command_id"):
                readback_matched = _record_matching_actuator_ack(payload, source="device_readback")
                if readback_matched:
                    # The virtual PLC publishes its read-back on farm/status;
                    # persist that exact read-back into the ledger before the
                    # separate command ACK arrives.
                    from service.operational_evidence import record_action_event
                    pending = state.get("actuator_pending_by_command") or {}
                    matched_records = [r for r in pending.values()
                                       if r.get("command_id") == payload.get("command_id")
                                       and r.get("farm_key") == payload.get("farm_key")]
                    incident_ids = sorted({str(r.get("incident_id")) for r in matched_records if r.get("incident_id")})
                    evidence_payload = {
                        **payload,
                        "action": payload.get("action") or "SET_OUTPUTS",
                        "incident_id": incident_ids[0] if len(incident_ids) == 1 else payload.get("incident_id"),
                        "target_matches": all(r.get("target_matches") is True for r in matched_records),
                        "ack_verified": all(r.get("ack_verified") is True for r in matched_records),
                        "source": "virtual_plc_readback_verifier",
                    }
                    record_action_event(evidence_payload, "acknowledged")
                    if evidence_payload["target_matches"] and evidence_payload["ack_verified"]:
                        record_action_event({
                            **evidence_payload,
                            "verification": {
                                "verified": True,
                                "method": "virtual_plc_status_readback",
                                "command_id": payload.get("command_id"),
                                "farm_key": payload.get("farm_key"),
                                "virtual_output": payload.get("virtual_output") or payload.get("outputs"),
                            },
                        }, "verified")
            if payload.get("event") in {"virtual_plc_safety_trip", "virtual_plc_water_limit_exceeded"}:
                try:
                    from service.mongodb_store import database
                    from service.scenario_evidence import find_scenario_incident, record_virtual_safety_trip
                    db = database()
                    incident_id = find_scenario_incident(
                        db, str(payload.get("scenario_run_id") or ""), str(payload.get("farm_key") or "")
                    )
                    inserted = record_virtual_safety_trip(payload, db=db)
                    if inserted:
                        from service.datadog_metrics import emit_count, metric_tags
                        tags = metric_tags(str(payload.get("farm_key") or "unknown"), "actuator", "smiot_demo_stream")
                        fault_tag = str(payload.get("fault_code") or "")
                        if fault_tag not in {"PIPE_PRESSURE_FLOW_MISMATCH", "PUMP_RUNTIME_OR_VOLUME_LIMIT",
                                             "PUMP_PRESSURE_ZERO", "PUMP_FLOW_BELOW_MINIMUM"}:
                            fault_tag = "other"
                        tags.extend(["event:safety_trip", f"fault_code:{fault_tag}"])
                        emit_count("smiot.virtual_plc.safety_trip", tags)
                        logger.warning(json.dumps({
                            "event": "smiot_virtual_plc_safety_trip", "incident_id": incident_id,
                            "scenario_run_id": payload.get("scenario_run_id"),
                            "command_id": payload.get("command_id"), "farm": payload.get("farm_key"),
                            "fault_code": payload.get("fault_code"), "reason": payload.get("reason"),
                            "pressure_bar": payload.get("pressure_bar"), "flow_lpm": payload.get("flow_lpm"),
                            "synthetic": True,
                        }, separators=(",", ":")))
                except Exception as exc:
                    logger.warning("Virtual PLC safety trip evidence persistence failed (%s)", type(exc).__name__)
            from service.farm_registry import FARM_KEYS_BY_LABEL
            selected_farm = FARM_KEYS_BY_LABEL.get(state.get("selected_farm", "Greenhouse A"), "greenhouse_a")
            if payload.get("source") != "smiot_demo_stream" or payload.get("farm_key", "greenhouse_a") == selected_farm:
                process_farm_status(payload)
                trigger_ui_update()
        elif topic == "farm/demo/status":
            if payload.get("event") == "scenario_ack":
                _record_scenario_ack(payload)
                trigger_ui_update()
        elif topic == "farm/demo/evidence":
            observation_persisted = False
            persist_error = None
            incident_id = None
            try:
                run_id = str(payload.get("scenario_run_id") or "")
                if run_id:
                    evidence_state = state.setdefault("demo_scenario_observation_by_run", {})
                    evidence_state[run_id] = {
                        "scenario_run_id": run_id,
                        "scenario_code": payload.get("scenario_code"),
                        "status": payload.get("status"),
                        "response": payload.get("response"),
                        "reason": payload.get("reason"),
                        "observed_at": payload.get("observed_at"),
                        "synthetic": True,
                    }
                    while len(evidence_state) > 50:
                        evidence_state.pop(next(iter(evidence_state)))
                from service.mongodb_store import database
                from service.scenario_evidence import find_scenario_incident, record_scenario_observation
                db = database()
                incident_id = find_scenario_incident(
                    db, run_id, str(payload.get("farm_key") or "")
                ) if run_id else None
                # Keep the scenario evidence path correlated end-to-end.  The
                # sensor payload remains unchanged; the Datadog log/span gets
                # the verified incident id only after MongoDB confirms the
                # exact run + farm relationship.
                from service.observability import trace_span
                with trace_span(
                    "smiot.scenario.observe",
                    resource=str(payload.get("scenario_code") or payload.get("scenario_type") or "scenario"),
                    **{"incident.id": incident_id, "scenario.run_id": run_id,
                       "farm.key": payload.get("farm_key")},
                ):
                    inserted = record_scenario_observation(payload, db=db)
                observation_persisted = bool(inserted)
                if inserted:
                    logger.info(json.dumps({
                        "event": "smiot_scenario_observation",
                        "incident_id": incident_id,
                        "scenario_code": payload.get("scenario_code"),
                        "scenario_run_id": payload.get("scenario_run_id"),
                        "farm_key": payload.get("farm_key"),
                        "status": payload.get("status"),
                        "synthetic": True,
                    }, separators=(",", ":")))
                    trigger_ui_update()
            except Exception as exc:
                persist_error = type(exc).__name__
                logger.warning("Scenario observation persistence failed (%s)", persist_error)
            client.publish("farm/demo/evidence/ack", json.dumps({
                "event": "scenario_observation_ack",
                "incident_id": incident_id,
                "scenario_run_id": payload.get("scenario_run_id"),
                "scenario_code": payload.get("scenario_code"),
                "farm_key": payload.get("farm_key"),
                "persisted": observation_persisted,
                "duplicate_or_rejected": not observation_persisted and persist_error is None,
                "error": persist_error,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "synthetic": True,
            }, separators=(",", ":")), qos=1)
        elif topic == "farm/command/event":
            from service.operational_evidence import record_action_event
            event_state = str(payload.get("ledger_state", ""))
            if event_state in {"requested", "published", "verified", "failed"}:
                record_action_event(payload, event_state)
                logger.info("smiot_action_ledger command_id=%s state=%s", payload.get("command_id"), event_state)
        elif topic == "farm/command/ack":
            from service.operational_evidence import record_action_event
            ack_matched = _record_matching_actuator_ack(payload, source="ack")
            action_payload = payload
            if ack_matched:
                pending = state.get("actuator_pending_by_command") or {}
                matched_records = [record for record in pending.values()
                                   if record.get("command_id") == payload.get("command_id")
                                   and record.get("farm_key") == payload.get("farm_key")]
                incident_ids = sorted({str(record.get("incident_id")) for record in matched_records
                                       if record.get("incident_id")})
                action_payload = {
                    **payload,
                    "late_ack": any(record.get("late_ack") is True for record in matched_records),
                    "target_matches": all(record.get("target_matches") is True for record in matched_records),
                    "ack_verified": all(record.get("ack_verified") is True for record in matched_records),
                    "incident_id": incident_ids[0] if len(incident_ids) == 1 else payload.get("incident_id"),
                }
            if payload.get("event") == "virtual_interlock_ack":
                # Resolve the exact simulator run before linking its safe-stop ACK.
                # A matching farm + scenario_run_id is required; never infer a lot.
                try:
                    from service.mongodb_store import database
                    from service.scenario_evidence import find_scenario_incident, record_virtual_safety_ack
                    db = database()
                    incident_id = find_scenario_incident(
                        db, str(payload.get("scenario_run_id") or ""), str(payload.get("farm_key") or "")
                    )
                    run = db["scenario_runs"].find_one(
                        {"_id": str(payload.get("scenario_run_id") or ""),
                         "farm_key": str(payload.get("farm_key") or "")},
                        {"node_id": 1},
                    )
                    action_payload = {**payload, "action": "SAFE_STOP", "target": "smiot_virtual_plc",
                                      "incident_id": incident_id, "node_id": (run or {}).get("node_id")}
                    ack_inserted = record_virtual_safety_ack(payload, db=db)
                    if ack_inserted:
                        from service.datadog_metrics import emit_count, metric_tags
                        tags = metric_tags(str(payload.get("farm_key") or "unknown"), "actuator", "smiot_demo_stream")
                        fault_tag = str(payload.get("fault_code") or "")
                        if fault_tag not in {"PIPE_PRESSURE_FLOW_MISMATCH", "PUMP_RUNTIME_OR_VOLUME_LIMIT",
                                             "PUMP_PRESSURE_ZERO", "PUMP_FLOW_BELOW_MINIMUM"}:
                            fault_tag = "other"
                        tags.extend(["event:safety_ack", f"fault_code:{fault_tag}"])
                        emit_count("smiot.virtual_plc.safety_ack", tags)
                        logger.warning(json.dumps({
                            "event": "smiot_virtual_plc_safety_ack", "incident_id": incident_id,
                            "scenario_run_id": payload.get("scenario_run_id"),
                            "command_id": payload.get("command_id"), "farm": payload.get("farm_key"),
                            "fault_code": payload.get("fault_code"), "reason": payload.get("reason"),
                            "outputs_off": payload.get("outputs_off"),
                            "valve_closed": payload.get("valve_closed"),
                            "safe_mode_active": payload.get("safe_mode_active"), "synthetic": True,
                        }, separators=(",", ":")))
                except Exception as exc:
                    logger.warning("Virtual PLC safety ACK evidence persistence failed (%s)", type(exc).__name__)
                    action_payload = {**payload, "action": "SAFE_STOP", "target": "smiot_virtual_plc",
                                      "incident_id": None, "node_id": None}
            if ack_matched and action_payload.get("late_ack") and action_payload.get("incident_id"):
                try:
                    from service.special_incident_correlation import recover_special_incident, record_special_event
                    late_incident = str(action_payload["incident_id"])
                    late_farm = str(action_payload.get("farm_key") or "")
                    record_special_event(late_incident, "late_ack_received", farm_key=late_farm,
                                         details={"command_id": action_payload.get("command_id"),
                                                  "ack_verified": action_payload.get("ack_verified")},
                                         status="recovering")
                    recover_special_incident(
                        late_incident, farm_key=late_farm,
                        verification={"command_id": action_payload.get("command_id"),
                                      "farm_key": late_farm,
                                      "late_ack": True,
                                      "ack_verified": bool(action_payload.get("ack_verified")),
                                      "source": "matching_device_ack"},
                        event="recovered_late_ack",
                    )
                    if action_payload.get("ack_verified"):
                        from service.mongodb_store import collection
                        collection("operational_incidents").update_one(
                            {"_id": late_incident, "farm_key": late_farm},
                            {"$set": {"status": "recovered"}},
                        )
                except Exception as exc:
                    logger.debug("Could not persist correlated W9 late ACK (%s)", type(exc).__name__)
            record_action_event(action_payload, "acknowledged")
            # For the virtual PLC, an ACK that includes a matching read-back
            # output is the verifier's evidence.  Do not wait for a soil sample
            # to prove an actuator command that has no direct agronomic effect.
            # Physical-device paths still require their own verifier.
            if (ack_matched and action_payload.get("action") in {"SET_OUTPUTS", "SET_VALVE", "SET_VENT", "SET_INVERTER"}
                    and action_payload.get("ack_verified") is True
                    and action_payload.get("target_matches") is True
                    and action_payload.get("command_id")):
                try:
                    record_action_event({
                        **action_payload,
                        "source": "virtual_plc_readback_verifier",
                        "verification": {
                            "verified": True,
                            "method": "virtual_plc_ack_readback",
                            "command_id": action_payload.get("command_id"),
                            "farm_key": action_payload.get("farm_key"),
                            "virtual_output": action_payload.get("virtual_output"),
                        },
                    }, "verified")
                except Exception as exc:
                    logger.debug("Could not persist virtual PLC readback verification (%s)", type(exc).__name__)
            if ack_matched and action_payload.get("late_ack") and action_payload.get("ack_verified") and action_payload.get("incident_id"):
                try:
                    from service.mongodb_store import collection
                    collection("operational_incidents").update_one(
                        {"_id": str(action_payload["incident_id"]), "farm_key": str(action_payload.get("farm_key") or "")},
                        {"$set": {"status": "recovered"}},
                    )
                except Exception:
                    pass
            logger.info("smiot_action_ledger command_id=%s state=acknowledged target=virtual_device", payload.get("command_id"))
            
    except Exception as e:
        import traceback
        print(f"Lỗi xử lý MQTT: {e}")
        traceback.print_exc()

def _emit_actuator_command_unacknowledged(actuator, target, timeout_seconds, channel=None,
                                         farm_key=None, command_id=None):
    """Record an existing command timeout without retrying or changing outputs."""
    from service.farm_registry import FARM_KEYS

    farm_key = str(farm_key or "").strip()
    if farm_key not in FARM_KEYS or not command_id:
        logger.warning("Skipping uncorrelated actuator timeout metric: farm or command ID missing")
        return False

    expected_channel = (f"q{channel}" if isinstance(channel, int) else channel)
    if actuator == "inverter" and expected_channel is None:
        expected_channel = "inverter"
    command_records = [record for record in (state.get("actuator_pending_by_command") or {}).values()
                       if record.get("command_id") == command_id
                       and record.get("farm_key") == farm_key
                       and record.get("channel") == expected_channel]
    if command_records and any(record.get("status") != "pending" for record in command_records):
        return False

    emitted = state.setdefault("actuator_timeout_emitted", [])
    timeout_key = f"{command_id}|{farm_key}|{actuator}|{channel}"
    if timeout_key in emitted:
        return False
    emitted.append(timeout_key)
    del emitted[:-500]

    incident_id = next((record.get("incident_id") for record in command_records
                        if record.get("incident_id")), None)
    actuator_tag = actuator if actuator in {"inverter", "plc_pump"} else "other"
    target_tag = "on" if target == 1 else "off" if target == 0 else "unknown"
    tags = [f"farm:{farm_key}", f"actuator:{actuator_tag}", "event:unacknowledged",
            f"target:{target_tag}"]
    if channel is not None:
        tags.append("channel:pump")
    if incident_id:
        tags.append(f"incident_id:{str(incident_id)[:100]}")
    try:
        from service.datadog_metrics import emit_count
        emit_count("smiot.actuator.command_unacknowledged", tags)
    except Exception as exc:
        logger.debug("Could not emit actuator command timeout metric (%s)", type(exc).__name__)
    logger.warning(json.dumps({
        "event": "smiot_actuator_command_unacknowledged",
        "farm": farm_key,
        "command_id": str(command_id)[:128],
        "incident_id": incident_id,
        "actuator": actuator_tag,
        "channel": channel,
        "target": target_tag,
        "timeout_seconds": timeout_seconds,
        "synthetic": bool(command_records and command_records[0].get("synthetic")),
    }, separators=(",", ":")))
    if incident_id:
        try:
            from service.special_incident_correlation import record_special_event
            record_special_event(str(incident_id), "actuator_command_unacknowledged",
                                 farm_key=farm_key,
                                 details={"command_id": str(command_id)[:128],
                                          "actuator": actuator_tag, "channel": channel,
                                          "timeout_seconds": timeout_seconds},
                                 status="holding")
        except Exception as exc:
            logger.debug("Could not persist correlated W9 timeout (%s)", type(exc).__name__)
    return True


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

                # W9's canonical timeout path is farm + command scoped. Device ACKs
                # are accepted only from matching command_id/farm_key pairs.
                pending_commands = state.get("actuator_pending_by_command") or {}
                for record in list(pending_commands.values()):
                    if (record.get("status") != "pending"
                            or record.get("timeout_emitted")
                            or now < float(record.get("ack_deadline", now + 1))):
                        continue
                    emitted = _emit_actuator_command_unacknowledged(
                        record.get("actuator"), record.get("target"),
                        max(1, int(float(record.get("ack_deadline", now))
                                  - float(record.get("requested_at", now)))),
                        channel=record.get("channel"), farm_key=record.get("farm_key"),
                        command_id=record.get("command_id"),
                    )
                    record["timeout_emitted"] = bool(emitted)
                    record["status"] = "unacknowledged" if emitted else "unverified"
                    record["timed_out_at"] = now

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
                        _emit_actuator_command_unacknowledged(
                            "inverter", target_bit, 120,
                            farm_key=inv_pending.get("farm_key"),
                            command_id=inv_pending.get("command_id"),
                        )
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
                            _emit_actuator_command_unacknowledged(
                                "plc_pump", target_val, 10, channel=idx,
                                farm_key=cmd.get("farm_key"), command_id=cmd.get("command_id"),
                            )
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
        client.subscribe("farm/demo/status", qos=1)
        client.subscribe("farm/demo/evidence", qos=1)
        client.subscribe("farm/demo/device_profile/ack", qos=1)
        client.subscribe("farm/traceability/event")
        client.subscribe("farm/command/event")
        client.subscribe("farm/command/ack")
        client.loop_start()
        print("Đã khởi động MQTT Client thành công!")
        
        # Khởi chạy trọng tài quét ngầm
        start_timeout_checker()
    except Exception as e:
        print(f"Không thể khởi động MQTT: {e}")
