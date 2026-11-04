"""MongoDB-backed application persistence. Public function signatures remain stable."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from service.mongodb_store import as_dict, collection, database, next_id, client as mongo_client

FIXED_PERMISSIONS = [
    ("view_dashboard", "Xem Dashboard", "home"),
    ("inverter_toggle_control", "Bật/tắt Inverter", "inverter"),
    ("inverter_send_data", "Gửi dữ liệu Inverter", "inverter"),
    ("inverter_change_mode", "Đổi chế độ Auto/Manual", "inverter"),
    ("pump_1_control", "Điều khiển Bơm 1", "plc"), ("pump_2_control", "Điều khiển Bơm 2", "plc"),
    ("pump_3_control", "Điều khiển Bơm 3", "plc"), ("pump_4_control", "Điều khiển Bơm 4", "plc"),
    ("pump_5_control", "Điều khiển Bơm 5", "plc"), ("pump_6_control", "Điều khiển Bơm 6", "plc"),
    ("pump_7_control", "Điều khiển Bơm 7", "plc"), ("manage_users", "Quản lý User", "admin"),
    ("manage_schedule", "Quản lý Lịch tưới", "schedule"), ("export_schedule_logs", "Xuất báo cáo Excel", "schedule"),
]
FIXED_FARMS = [("greenhouse_a", "Greenhouse A", "🌿"), ("greenhouse_b", "Greenhouse B", "🍅"),
               ("greenhouse_c", "Greenhouse C", "🌱"), ("greenhouse_d", "Greenhouse D", "🏚️")]
ROLE_PRESETS = {"admin": [p[0] for p in FIXED_PERMISSIONS],
                "operator": ["view_dashboard", "inverter_toggle_control", "inverter_send_data", "inverter_change_mode", *[f"pump_{i}_control" for i in range(1, 8)]],
                "viewer": ["view_dashboard"]}
FARM_PRESETS = {"admin": [f[0] for f in FIXED_FARMS], "operator": ["greenhouse_a"], "viewer": ["greenhouse_a"]}


_PASSWORD_HASH_ITERATIONS = 310_000


def _hash_password(password: str) -> str:
    """Hash new passwords with salted PBKDF2; transparently migrate old SHA-256 hashes at login."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PASSWORD_HASH_ITERATIONS)
    return f"pbkdf2_sha256${_PASSWORD_HASH_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(stored_hash: str, password: str) -> tuple[bool, bool]:
    """Return (valid, needs_upgrade) for PBKDF2 and legacy unsalted SHA-256 hashes."""
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt_hex, digest_hex = stored_hash.split("$", 3)
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
            return hmac.compare_digest(digest.hex(), digest_hex), False
        except (ValueError, TypeError):
            return False, False
    legacy_digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(stored_hash, legacy_digest), True


def _ensure_ids(document: dict[str, Any]) -> dict[str, Any]:
    result = dict(document)
    result["id"] = result.get("id", result.get("_id"))
    result.pop("_id", None)
    for key, value in list(result.items()):
        if hasattr(value, "isoformat"):
            result[key] = value.strftime("%Y-%m-%d %H:%M:%S")
    return result


def init_db():
    """Initialize Mongo collections and safe indexes; does not mutate SQLite."""
    db = database()
    db.command("ping")
    db.users.create_index("username", unique=True)
    db.schedules.create_index([("farm_key", ASCENDING), ("schedule_date", ASCENDING), ("start_time", ASCENDING)])
    db.schedule_logs.create_index([("farm_key", ASCENDING), ("start_at", DESCENDING)])
    db.schedule_logs.create_index([("schedule_id", ASCENDING), ("status", ASCENDING)])
    db.notifications.create_index([("created_at", DESCENDING)])
    db.telemetry.create_index([("meta.farm_key", ASCENDING), ("meta.measurement_type", ASCENDING), ("timestamp", DESCENDING)])
    db.telemetry.create_index([("meta.farm_key", ASCENDING), ("meta.measurement_type", ASCENDING), ("meta.node_id", ASCENDING), ("timestamp", DESCENDING)])
    db.traceability_events.create_index([("farm_key", ASCENDING), ("simulated_day", DESCENDING)])
    db.traceability_events.create_index([("farm_key", ASCENDING), ("lot_id", ASCENDING), ("simulated_day", ASCENDING), ("captured_at", ASCENDING)])
    db.traceability_events.create_index([("farm_key", ASCENDING), ("captured_at", DESCENDING)])
    db.crop_cycles.create_index([("public_share_token", ASCENDING)], unique=True, sparse=True)
    db.crop_stage_media.create_index([("farm_key", ASCENDING), ("lot_id", ASCENDING), ("stage_index", ASCENDING)])
    db.crop_stage_media.create_index([("farm_key", ASCENDING), ("lot_id", ASCENDING), ("stage_code", ASCENDING)], unique=True)
    db.action_ledger.create_index([("incident_id", ASCENDING), ("created_at", DESCENDING)])
    db.action_ledger.create_index([("state", ASCENDING), ("updated_at", DESCENDING)])
    db.operational_incidents.create_index([("farm_key", ASCENDING), ("node_id", ASCENDING), ("status", ASCENDING), ("opened_at", DESCENDING)])
    db.operational_incidents.create_index([("farm_key", ASCENDING), ("lot_id", ASCENDING), ("opened_at", DESCENDING)])
    db.lot_sensor_assignments.create_index([("farm_key", ASCENDING), ("node_id", ASCENDING), ("valid_from", DESCENDING)])
    db.operational_decisions.create_index([("incident_id", ASCENDING), ("created_at", DESCENDING)])

    for key, label, module in FIXED_PERMISSIONS:
        db.permissions.update_one({"_id": key}, {"$set": {"key": key, "label": label, "module": module}}, upsert=True)
    for farm_key, _, _ in FIXED_FARMS:
        db.inverter_mode.update_one({"_id": farm_key}, {"$setOnInsert": {"farm_key": farm_key, "mode": "manual"}}, upsert=True)

    # Match prior startup safety behavior: stale running records cannot resume pump actions.
    db.schedules.update_many({"status": "running"}, {"$set": {"status": "failed"}})
    db.schedule_logs.update_many({"status": "running"}, {"$set": {"status": "failed"}})

    if db.users.count_documents({}) == 0:
        bootstrap_password = os.getenv("SMIOT_BOOTSTRAP_ADMIN_PASSWORD")
        if not bootstrap_password:
            raise RuntimeError("MongoDB has no users; set SMIOT_BOOTSTRAP_ADMIN_PASSWORD to create the first admin securely")
        seed_default_user("admin", bootstrap_password, "Admin", "admin", "admin.png")
    print("✅ MongoDB đã khởi tạo thành công!")


def seed_default_user(username: str, password: str, fullname: str, role: str, avatar: str) -> int:
    user_id = next_id("users")
    collection("users").insert_one({"_id": user_id, "id": user_id, "username": username,
        "password": _hash_password(password), "fullname": fullname, "role": role, "avatar": avatar,
        "is_active": 1, "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "last_active": None, "permissions": ROLE_PRESETS.get(role, ROLE_PRESETS["viewer"]),
        "farms": FARM_PRESETS.get(role, FARM_PRESETS["viewer"])})
    return user_id


def verify_user(username: str, password: str):
    user = collection("users").find_one({"username": username, "is_active": 1})
    if not user:
        return None
    valid, needs_upgrade = _verify_password(str(user.get("password", "")), password)
    if not valid:
        return None
    if needs_upgrade:
        collection("users").update_one(
            {"_id": user.get("_id"), "password": user.get("password")},
            {"$set": {"password": _hash_password(password)}},
        )
    return {k: user.get(k) for k in ("id", "username", "fullname", "role", "avatar")}


def get_all_users():
    result = []
    for u in collection("users").find({}).sort("id", ASCENDING):
        row = _ensure_ids(u)
        row["perm_count"] = len(u.get("permissions", []))
        result.append({k: row.get(k) for k in ("id", "username", "fullname", "role", "avatar", "is_active", "created_at", "last_active", "perm_count")})
    return result


def get_user_by_id(user_id: int): return _ensure_ids(collection("users").find_one({"id": int(user_id)}))


def create_user(username: str, password: str, fullname: str, role: str = "operator"):
    user_id = next_id("users")
    doc = {"_id": user_id, "id": user_id, "username": username, "password": _hash_password(password),
           "fullname": fullname, "role": role, "avatar": "client.png", "is_active": 1,
           "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "last_active": None,
           "permissions": ROLE_PRESETS.get(role, ROLE_PRESETS["viewer"]), "farms": FARM_PRESETS.get(role, FARM_PRESETS["viewer"])}
    try: collection("users").insert_one(doc); return user_id
    except DuplicateKeyError: return None


def update_user(user_id: int, fullname: str = None, role: str = None, password: str = None):
    updates = {}
    if fullname: updates["fullname"] = fullname
    if role: updates["role"] = role
    if password: updates["password"] = _hash_password(password)
    if updates: collection("users").update_one({"id": int(user_id)}, {"$set": updates})


def delete_user(user_id: int): collection("users").delete_one({"id": int(user_id)})


def get_all_permissions(): return [{"key": k, "label": l, "module": m} for k, l, m in FIXED_PERMISSIONS]

def get_user_permissions(user_id: int):
    user = collection("users").find_one({"id": int(user_id)}, {"permissions": 1})
    return (user or {}).get("permissions", [])

def set_user_permissions(user_id: int, perm_keys: list): collection("users").update_one({"id": int(user_id)}, {"$set": {"permissions": list(dict.fromkeys(perm_keys))}})
def check_permission(user_id: int, perm_key: str) -> bool:
    return collection("users").count_documents({"id": int(user_id), "permissions": perm_key}, limit=1) > 0

def get_all_farms(): return [{"key": k, "label": l, "emoji": e} for k, l, e in FIXED_FARMS]
def get_user_farms(user_id: int):
    u = collection("users").find_one({"id": int(user_id)}, {"farms": 1}); return (u or {}).get("farms", [])
def set_user_farms(user_id: int, farm_keys: list): collection("users").update_one({"id": int(user_id)}, {"$set": {"farms": list(dict.fromkeys(farm_keys))}})
def update_user_activity(user_id: int): collection("users").update_one({"id": int(user_id)}, {"$set": {"last_active": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}})


def get_inverter_mode(farm_key: str) -> str:
    row = collection("inverter_mode").find_one({"farm_key": farm_key}); return row.get("mode", "manual") if row else "manual"
def set_inverter_mode(farm_key: str, mode: str): collection("inverter_mode").update_one({"_id": farm_key}, {"$set": {"farm_key": farm_key, "mode": mode}}, upsert=True)


def _permission_ok(user_id): return not user_id or check_permission(user_id, "manage_schedule")
def bulk_add_schedules(farm_key: str, dates: list, start_time: str, water_amount: float, user_id: int = None):
    if not _permission_ok(user_id): return False
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    docs=[]
    for d in dates:
        sid=next_id("schedules"); docs.append({"_id":sid,"id":sid,"farm_key":farm_key,"schedule_date":d,"start_time":start_time,"water_amount":water_amount,"status":"pending","created_at":now})
    if docs: collection("schedules").insert_many(docs)
    return True

def delete_schedule(schedule_id: int, user_id: int = None):
    if not _permission_ok(user_id): return False
    collection("schedules").delete_one({"id":int(schedule_id)}); return True

def edit_schedule(schedule_id: int, start_time: str, water_amount: float, user_id: int = None):
    if not _permission_ok(user_id): return False
    collection("schedules").update_one({"id":int(schedule_id)}, {"$set":{"start_time":start_time,"water_amount":water_amount}}); return True

def reset_schedule_to_pending(schedule_id: int, user_id: int = None):
    if not _permission_ok(user_id): return False
    now=datetime.now(); collection("schedules").update_one({"id":int(schedule_id),"status":"failed"},{"$set":{"status":"pending","schedule_date":now.strftime("%Y-%m-%d"),"start_time":now.strftime("%H:%M")}}); return True

def add_schedule(farm_key: str, schedule_date: str, start_time: str, water_amount: float):
    sid=next_id("schedules"); collection("schedules").insert_one({"_id":sid,"id":sid,"farm_key":farm_key,"schedule_date":schedule_date,"start_time":start_time,"water_amount":water_amount,"status":"pending","created_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}); return sid

def _latest_actual(schedule_id):
    row=collection("schedule_logs").find_one({"schedule_id":schedule_id},{"actual_water":1},sort=[("start_at",DESCENDING)])
    return row.get("actual_water") if row else None

def get_schedules(farm_key: str, date: str = None):
    q={"farm_key":farm_key}
    if date: q["schedule_date"]=date
    sort=[("start_time",ASCENDING)] if date else [("schedule_date",DESCENDING),("start_time",ASCENDING)]
    docs=list(collection("schedules").find(q).sort(sort))
    ids=[x["id"] for x in docs]
    latest={}
    if ids:
        for log in collection("schedule_logs").find({"schedule_id":{"$in":ids}},{"schedule_id":1,"actual_water":1,"start_at":1}).sort("start_at",DESCENDING):
            latest.setdefault(log["schedule_id"],log.get("actual_water"))
    result=[]
    for doc in docs:
        row=_ensure_ids(doc); row["actual_water"]=latest.get(doc["id"]); result.append(row)
    return result

def update_schedule_status(schedule_id: int, status: str): collection("schedules").update_one({"id":int(schedule_id)},{"$set":{"status":status}})
def get_pending_schedules(farm_key: str, date: str, current_time: str):
    lower=(datetime.strptime(current_time,"%H:%M")-timedelta(minutes=10)).strftime("%H:%M")
    return [_ensure_ids(x) for x in collection("schedules").find({"farm_key":farm_key,"schedule_date":date,"start_time":{"$gte":lower,"$lte":current_time},"status":"pending"})]

def auto_fail_missed_schedules(farm_key: str):
    now=datetime.now(); cutoff=(now-timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"); silent=(now-timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"); out=[]
    schedules=collection("schedules"); logs=collection("schedule_logs")
    for row in schedules.find({"farm_key":farm_key,"status":"pending"}):
        expected=f"{row.get('schedule_date')} {row.get('start_time')}:00"
        if expected >= cutoff: continue
        lid=next_id("schedule_logs")
        with mongo_client().start_session() as session:
            with session.start_transaction():
                result=schedules.update_one({"_id":row["_id"],"status":"pending"},{"$set":{"status":"failed"}},session=session)
                if not result.modified_count: continue
                logs.insert_one({"_id":lid,"id":lid,"schedule_id":row["id"],"farm_key":farm_key,"start_at":expected,"end_at":now.strftime("%Y-%m-%d %H:%M:%S"),"target_water":row.get("water_amount"),"actual_water":0.0,"status":"failed"},session=session)
        out.append((row["id"],row.get("start_time"),expected < silent))
    return out

def add_schedule_log(schedule_id: int, farm_key: str, start_at: str, target_water: float, status: str = 'running'):
    lid=next_id("schedule_logs"); collection("schedule_logs").insert_one({"_id":lid,"id":lid,"schedule_id":schedule_id,"farm_key":farm_key,"start_at":start_at,"end_at":None,"target_water":target_water,"actual_water":None,"status":status}); return lid

def update_schedule_log_start_time(schedule_id: int, new_start_at: str, new_status: str): collection("schedule_logs").update_one({"schedule_id":int(schedule_id),"status":"pending_run"},{"$set":{"start_at":new_start_at,"status":new_status}})
def update_schedule_log(schedule_id: int, end_at: str, actual_water: float, status: str): collection("schedule_logs").update_one({"schedule_id":int(schedule_id),"status":"running"},{"$set":{"end_at":end_at,"actual_water":actual_water,"status":status}})
def get_today_logs(farm_key: str):
    today=datetime.now().strftime("%Y-%m-%d"); return [_ensure_ids(x) for x in collection("schedule_logs").find({"farm_key":farm_key,"start_at":{"$regex":f"^{today}"}}).sort("start_at",DESCENDING)]
def clear_today_logs(farm_key: str):
    today=datetime.now().strftime("%Y-%m-%d"); collection("schedule_logs").delete_many({"farm_key":farm_key,"start_at":{"$regex":f"^{today}"}})
def get_all_schedule_logs(farm_key: str):
    schedules={x["id"]:x for x in collection("schedules").find({}, {"id":1,"schedule_date":1,"start_time":1})}
    out=[]
    for x in collection("schedule_logs").find({"farm_key":farm_key}).sort("id",DESCENDING):
        s=schedules.get(x.get("schedule_id"),{}); out.append({"id":x.get("id"),"schedule_date":s.get("schedule_date"),"start_time":s.get("start_time"),"farm_key":x.get("farm_key"),"target_water":x.get("target_water"),"actual_water":x.get("actual_water"),"status":x.get("status"),"start_at":x.get("start_at"),"end_at":x.get("end_at")})
    return out

def get_running_schedule_logs(farm_key: str): return [_ensure_ids(x) for x in collection("schedule_logs").find({"farm_key":farm_key,"status":"running"})]
def get_total_actual_water(farm_key: str, date: str):
    row=next(collection("schedule_logs").aggregate([{"$match":{"farm_key":farm_key,"start_at":{"$regex":f"^{date}"}}},{"$group":{"_id":None,"total":{"$sum":{"$ifNull":["$actual_water",0]}}}}]),None); return row["total"] if row else 0

def save_notification(message: str, category: str = "system", severity: str = "info"):
    nid=next_id("notifications"); collection("notifications").insert_one({"_id":nid,"id":nid,"message":message,"category":category,"severity":severity,"created_at":datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")})
def get_recent_notifications(limit: int = 50): return [_ensure_ids(x) for x in collection("notifications").find({}).sort("created_at",DESCENDING).limit(max(0,int(limit)))]


def _ts_collection(): return collection("telemetry")
def _ts_time(value):
    if isinstance(value,datetime): return value
    if value is None: return None
    dt=datetime.fromisoformat(str(value).replace("Z","+00:00")); return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
def _telemetry_doc(farm_key, table, measurement, readings, extra=None, source_metadata=None):
    meta={"farm_key":farm_key,"source_table":table,"measurement_type":measurement}
    source={"table":table}
    if extra:
        extra=dict(extra)
        if "node_id" in extra: meta["node_id"]=int(extra.pop("node_id"))
        source.update(extra)
    if source_metadata:
        source.update(source_metadata)
        if source.get("source"):
            meta["source"] = source["source"]
    received_at = _ts_time(source.get("app_received_at")) if source.get("app_received_at") else None
    doc={"timestamp":received_at or datetime.now(timezone.utc),"meta":meta,"readings":readings,"source":source}
    _ts_collection().insert_one(doc)
def _history(table,farm_key,start_date,end_date,measurement=None,node_id=None):
    q={"meta.farm_key":farm_key,"meta.source_table":{"$in":[table,table+'_live']},"timestamp":{"$gte":_ts_time(start_date+" 00:00:00"),"$lte":_ts_time(end_date+" 23:59:59")},"source.demo_seed_version":{"$ne":"smiot-demo-history-v1"}}
    if measurement: q["meta.measurement_type"]=measurement
    if node_id is not None: q["meta.node_id"]=int(node_id)
    out=[]
    for x in _ts_collection().find(q).sort("timestamp",ASCENDING):
        r={"farm_key":farm_key,"timestamp":x["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),"id":(x.get("source") or {}).get("row_id")}; r.update(x.get("readings",{}));
        # Node history queries are farm-wide, so preserve node_id from each TS document.
        # The chart and data-table pages use it to separate readings by sensor node.
        stored_node_id=(x.get("meta") or {}).get("node_id")
        if stored_node_id is None:
            # Backfilled SQLite records kept node_id in source before the metadata fix.
            stored_node_id=(x.get("source") or {}).get("node_id")
        if stored_node_id is not None: r["node_id"]=int(stored_node_id)
        elif node_id is not None: r["node_id"]=int(node_id)
        out.append(r)
    return out

def save_telemetry_sensor(farm_key: str,state: dict):
    r={}
    for i in (1,2):
        n=state.get(f"node{i}",{}); r.update({f"node{i}_{k}":n.get(src) for k,src in (("at","at"),("ah","ah"),("st","st"),("sh","sh"),("ec","sec"))})
    water=state.get("water",{}); ph=state.get("ph",{}); ec=state.get("ec",{})
    r.update({"flow_f1":water.get("f1"),"flow_f2":water.get("f2"),"flow_t1":water.get("t1"),"flow_t2":water.get("t2"),"water_ph":ph.get("ph"),"water_ec":ec.get("ec"),"ai_water_suggest":state.get("ai_water_suggest")})
    _telemetry_doc(farm_key,"telemetry_sensor","snapshot",r)
def get_telemetry_sensor_history(farm_key: str,start_date: str,end_date: str): return _history("telemetry_sensor",farm_key,start_date,end_date,"snapshot")

def save_telemetry_node(farm_key: str,node_id: int,air_temp: float,air_hum: float,soil_temp: float,soil_hum: float,ec: float,source_metadata: dict = None):
    _telemetry_doc(farm_key,"telemetry_node","node",{"air_temp":air_temp,"air_hum":air_hum,"soil_temp":soil_temp,"soil_hum":soil_hum,"ec":ec},{"node_id":int(node_id)},source_metadata)
def save_telemetry_water(farm_key: str,ph_val: float,ec_val: float,source_metadata: dict = None): _telemetry_doc(farm_key,"telemetry_water","water",{"ph_val":ph_val,"ec_val":ec_val},source_metadata=source_metadata)
def save_telemetry_flow(farm_key: str,flow_f1: float,flow_f2: float,flow_t1: float,flow_t2: float,source_metadata: dict = None): _telemetry_doc(farm_key,"telemetry_flow","flow",{"flow_f1":flow_f1,"flow_f2":flow_f2,"flow_t1":flow_t1,"flow_t2":flow_t2},source_metadata=source_metadata)
def get_telemetry_node_history(farm_key: str,start_date: str,end_date: str): return _history("telemetry_node",farm_key,start_date,end_date,"node")
def get_telemetry_water_history(farm_key: str,start_date: str,end_date: str): return _history("telemetry_water",farm_key,start_date,end_date,"water")
def get_telemetry_flow_history(farm_key: str,start_date: str,end_date: str): return _history("telemetry_flow",farm_key,start_date,end_date,"flow")
def save_ai_water_suggest(farm_key: str,amount_ml: float): _telemetry_doc(farm_key,"telemetry_sensor","snapshot",{"ai_water_suggest":amount_ml})

def _latest_ts(farm_key,table,measurement,node_id=None):
    q={"meta.farm_key":farm_key,"meta.source_table":{"$in":[table,table+'_live']},"meta.measurement_type":measurement,"source.demo_seed_version":{"$ne":"smiot-demo-history-v1"}}
    if node_id is not None:q["meta.node_id"]=int(node_id)
    return _ts_collection().find_one(q,sort=[("timestamp",DESCENDING)])
def get_latest_node(farm_key: str,node_id: int):
    x=_latest_ts(farm_key,"telemetry_node","node",node_id)
    if not x:return None
    r={"farm_key":farm_key,"node_id":node_id,"timestamp":x["timestamp"].strftime("%Y-%m-%d %H:%M:%S")};r.update(x.get("readings",{}));return r
def get_latest_water(farm_key: str):
    x=_latest_ts(farm_key,"telemetry_water","water");return ({"farm_key":farm_key,"timestamp":x["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),**x.get("readings",{})} if x else None)
def get_latest_flow(farm_key: str):
    x=_latest_ts(farm_key,"telemetry_flow","flow");return ({"farm_key":farm_key,"timestamp":x["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),**x.get("readings",{})} if x else None)
def get_latest_ai_water_suggest(farm_key: str):
    x=_ts_collection().find_one({"meta.farm_key":farm_key,"meta.source_table":"telemetry_sensor","readings.ai_water_suggest":{"$ne":None}},sort=[("timestamp",DESCENDING)])
    return ({"ai_water_suggest":x["readings"].get("ai_water_suggest"),"timestamp":x["timestamp"].strftime("%Y-%m-%d %H:%M:%S")} if x else None)

# Query helpers used by the application UI, scheduler, and AI tools.
def get_schedule_logs_for_date(farm_key: str, date: str):
    return [_ensure_ids(x) for x in collection("schedule_logs").find({"farm_key":farm_key,"start_at":{"$regex":f"^{date}"}}).sort("start_at",ASCENDING)]

def get_active_schedules(farm_key: str):
    return [_ensure_ids(x) for x in collection("schedules").find({"farm_key":farm_key,"status":{"$in":["pending","running"]}}).sort([("schedule_date",ASCENDING),("start_time",ASCENDING)])]

def get_future_schedules(farm_key: str):
    today=datetime.now().strftime("%Y-%m-%d")
    return [_ensure_ids(x) for x in collection("schedules").find({"farm_key":farm_key,"status":"pending","schedule_date":{"$gte":today}}).sort([("schedule_date",ASCENDING),("start_time",ASCENDING)]).limit(20)]

def get_recent_system_warnings(limit: int = 10):
    return [_ensure_ids(x) for x in collection("notifications").find({"severity":{"$in":["warning","error"]}}).sort("created_at",DESCENDING).limit(max(0,int(limit)))]

