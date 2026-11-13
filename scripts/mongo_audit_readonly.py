"""Chi doc: do truoc khi toi uu MongoDB (SMIOT). Khong ghi, khong in gia tri du lieu.

Chay tren EC2:  cd /opt/smiot && PYTHONPATH=/opt/smiot .venv/bin/python scripts/mongo_audit_readonly.py
Chi in: so luong, ten truong, kieu BSON, ten index, gia tri enum (kind/status/action).
"""
import json
import os

try:
    from dotenv import load_dotenv
    load_dotenv("/etc/smiot/app.env")
except Exception:
    pass

from service.mongodb_store import database

ACTIVE = ["open", "holding", "recovering"]
GENERIC = ["false_offline", "service_down"]
db = database()
out = {}

out["server_version"] = db.client.server_info().get("version")
out["apply_validators_flag"] = os.getenv("SMIOT_APPLY_VALIDATORS", "(unset)")

inc = db["operational_incidents"]
dup_pipe = [
    {"$match": {"status": {"$in": ACTIVE}}},
    {"$group": {"_id": {"farm_key": "$farm_key", "node_id": "$node_id", "kind": "$kind"},
                "n": {"$sum": 1}}},
    {"$match": {"n": {"$gt": 1}}},
]
dups = list(inc.aggregate(dup_pipe))
out["active_total"] = inc.count_documents({"status": {"$in": ACTIVE}})
out["active_duplicate_groups_all_kinds"] = [
    {"kind": d["_id"].get("kind"), "farm_key": d["_id"].get("farm_key"),
     "node_id": d["_id"].get("node_id"), "count": d["n"]} for d in dups]
out["active_duplicate_groups_generic_kinds"] = [
    d for d in out["active_duplicate_groups_all_kinds"] if d["kind"] in GENERIC]

notif = db["notifications"]
out["notifications_created_at_types"] = {
    str(r["_id"]): r["n"] for r in notif.aggregate(
        [{"$group": {"_id": {"$type": "$created_at"}, "n": {"$sum": 1}}}])}
out["notifications_id_types"] = {
    str(r["_id"]): r["n"] for r in notif.aggregate(
        [{"$group": {"_id": {"$type": "$_id"}, "n": {"$sum": 1}}}])}

out["indexes"] = {}
for name in ("operational_incidents", "action_ledger", "schedule_logs", "findings", "telemetry",
             "notifications", "scenario_api_idempotency", "scenario_api_rate_limits"):
    try:
        out["indexes"][name] = [
            {"name": i.get("name"), "key": dict(i.get("key")), "unique": bool(i.get("unique")),
             "partial": i.get("partialFilterExpression"), "ttl": i.get("expireAfterSeconds")}
            for i in db[name].list_indexes()]
    except Exception as exc:
        out["indexes"][name] = f"error:{type(exc).__name__}"

out["collection_options"] = {}
for c in db.list_collections():
    if c["name"] in ("operational_incidents", "action_ledger", "notifications",
                     "scenario_api_idempotency", "scenario_api_rate_limits"):
        o = c.get("options", {})
        out["collection_options"][c["name"]] = {
            "has_validator": "validator" in o, "validationLevel": o.get("validationLevel"),
            "validationAction": o.get("validationAction")}
out["collections_present"] = sorted(c["name"] for c in db.list_collections())[:80]


def field_types(coll, sample=300):
    rows = coll.aggregate([
        {"$sample": {"size": sample}},
        {"$project": {"kv": {"$objectToArray": "$$ROOT"}}},
        {"$unwind": "$kv"},
        {"$group": {"_id": {"f": "$kv.k", "t": {"$type": "$kv.v"}}, "n": {"$sum": 1}}},
    ])
    res = {}
    for r in rows:
        res.setdefault(r["_id"]["f"], {})[r["_id"]["t"]] = r["n"]
    return res


out["field_types"] = {n: field_types(db[n]) for n in (
    "operational_incidents", "action_ledger", "notifications",
    "scenario_api_idempotency", "scenario_api_rate_limits")}
out["distinct"] = {
    "action_ledger.action": db["action_ledger"].distinct("action"),
    "action_ledger.state": db["action_ledger"].distinct("state"),
    "operational_incidents.kind": inc.distinct("kind"),
    "operational_incidents.status": inc.distinct("status"),
}
print(json.dumps(out, default=str, ensure_ascii=True))
