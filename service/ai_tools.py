"""Read-only MongoDB-backed tools for the Gemini assistant."""
from datetime import datetime, timedelta
from service import auth


def _check_offline(row):
    if not row or "timestamp" not in row: return row
    try:
        ts=datetime.strptime(row["timestamp"],"%Y-%m-%d %H:%M:%S")
        if datetime.utcnow()-ts>timedelta(minutes=15): return {"status":"OFFLINE","last_seen":row["timestamp"]}
    except Exception: pass
    return row


def get_current_telemetry(farm_key: str) -> dict:
    result={}
    try:
        for node_id in (1,2):
            row=auth.get_latest_node(farm_key,node_id)
            if row: result[f"node_{node_id}"]=_check_offline(row)
        water=auth.get_latest_water(farm_key)
        if water: result["water_quality"]=_check_offline(water)
        flow=auth.get_latest_flow(farm_key)
        if flow: result["flow"]=_check_offline(flow)
    except Exception as exc: print(f"❌ [AI_TOOLS] Lỗi get_current_telemetry: {exc}")
    return result


def get_sensor_history(farm_key: str,sensor_type: str,start_date: str,end_date: str) -> list:
    try:
        fn={"node":auth.get_telemetry_node_history,"water":auth.get_telemetry_water_history,"flow":auth.get_telemetry_flow_history}.get(sensor_type.lower())
        return fn(farm_key,start_date,end_date) if fn else []
    except Exception as exc: print(f"❌ [AI_TOOLS] Lỗi get_sensor_history: {exc}"); return []


def get_recent_system_warnings(limit: int = 10) -> list:
    try: return auth.get_recent_system_warnings(limit)
    except Exception as exc: print(f"❌ [AI_TOOLS] Lỗi get_recent_system_warnings: {exc}"); return []

def get_active_irrigation_schedules(farm_key: str) -> list:
    try: return auth.get_active_schedules(farm_key)
    except Exception as exc: print(f"❌ [AI_TOOLS] Lỗi get_active_irrigation_schedules: {exc}"); return []

def get_irrigation_history(farm_key: str,target_date: str) -> dict:
    result={"total_schedules":0,"total_actual_water":0.0,"details":[]}
    try:
        rows=auth.get_schedule_logs_for_date(farm_key,target_date); result["total_schedules"]=len(rows); result["details"]=[{k:r.get(k) for k in ("schedule_id","start_at","end_at","target_water","actual_water","status")} for r in rows]
        result["total_actual_water"]=sum(float(r.get("actual_water") or 0) for r in rows)
    except Exception as exc: print(f"❌ [AI_TOOLS] Lỗi get_irrigation_history: {exc}")
    return result

def get_system_mode(farm_key: str) -> dict:
    try: return {"mode":auth.get_inverter_mode(farm_key)}
    except Exception as exc: print(f"❌ [AI_TOOLS] Lỗi get_system_mode: {exc}"); return {"mode":"unknown"}

def get_total_water_consumption(farm_key: str,target_date: str) -> dict:
    try: return {"date":target_date,"total_water_liters":round(float(auth.get_total_actual_water(farm_key,target_date)),2)}
    except Exception as exc: print(f"❌ [AI_TOOLS] Lỗi get_total_water_consumption: {exc}"); return {"date":target_date,"total_water_liters":0.0}

def get_ai_agronomy_suggestion(farm_key: str) -> dict:
    try: return auth.get_latest_ai_water_suggest(farm_key) or {}
    except Exception as exc: print(f"❌ [AI_TOOLS] Lỗi get_ai_agronomy_suggestion: {exc}"); return {}

def get_future_schedules(farm_key: str) -> list:
    try: return auth.get_future_schedules(farm_key)
    except Exception as exc: print(f"❌ [AI_TOOLS] Lỗi get_future_schedules: {exc}"); return []
