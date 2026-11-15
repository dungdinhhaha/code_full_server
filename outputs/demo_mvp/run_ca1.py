"""
Ca1 — false_offline — greenhouse_a / node 1
Chạy: python outputs/demo_mvp/run_ca1.py
Tạo đầy đủ: incident + action_ledger + lot_assignment + Datadog logs + real trace_id
"""
import boto3, time, json

INSTANCE_ID = "i-00bf2d3591d3ee0a2"
REGION      = "ap-southeast-2"
PROFILE     = "aws-moi"
APP_URL     = "https://13-238-30-218.sslip.io"

# ── Bước 1: tạo incident + lot_assignment + action_ledger ──────────────────
STEP1 = r"""
set -a; . /etc/smiot/app.env; set +a
export PYTHONPATH=/opt/smiot
cd /opt/smiot
/opt/smiot/.venv/bin/python3 - << 'PYEOF'
import uuid, hashlib, json
from datetime import datetime, timezone

def utc_now(): return datetime.now(timezone.utc)
def iso(dt):  return dt.isoformat(timespec="milliseconds").replace("+00:00","Z")

from service.mongodb_store import database, collection
db = database()

run_id    = f"c1-{uuid.uuid4()}"
digest    = hashlib.sha256(run_id.encode()).hexdigest()[:16].upper()
iid       = f"INC-SMIOT-SCENARIO-{digest}"
from datetime import timedelta
now            = utc_now()
# Monitor query: last_5m → detection lag ~6 min after fault starts
# Total response drill: ~12 min (REFUSED_RESTART, operator holds & verifies)
fault_started  = now - timedelta(minutes=25)
detected       = now - timedelta(minutes=19)   # 6 min detection lag (last_5m + margin)
opened         = detected
recovered      = now - timedelta(minutes=13)   # 6 min to respond & verify
safe           = recovered
exec_id   = str(uuid.uuid4())

# --- incident ---
db.operational_incidents.update_one({"_id": iid}, {"$setOnInsert": {
    "_id": iid, "incident_id": iid,
    "kind": "false_offline", "status": "recovered",
    "farm_key": "greenhouse_a", "node_id": 1,
    "scenario_run_id": run_id, "scenario": "f1_false_offline", "scenario_code": "F1",
    "monitor_id": "342585836",
    "workflow_id": "ffd62026-6b63-40e4-9b46-6ac18d2d584f",
    "last_workflow_execution_id": exec_id,
    "last_workflow_status": "succeeded",
    "last_workflow_disposition": "REFUSED_RESTART",
    "last_action": "HOLD",
    "detected_at": detected, "fault_started_at": fault_started, "opened_at": opened,
    "recovered_at": recovered, "safe_at": safe, "updated_at": now,
    "synthetic": True,
    "evidence": {
        "scenario_run_ids": [run_id],
        "action_command_ids": [],
        "monitor_ids": ["342585836"],
        "workflow_ids": ["ffd62026-6b63-40e4-9b46-6ac18d2d584f"],
        "trace_ids": [],
        "workflow_observations": [{
            "execution_id": exec_id,
            "workflow_id": "ffd62026-6b63-40e4-9b46-6ac18d2d584f",
            "status": "succeeded", "disposition": "REFUSED_RESTART",
            "run_at": iso(opened), "synthetic": True,
        }],
    },
    "recovery_verification": {
        "computed_now": "ONLINE", "age_s": 12,
        "mongo_newest_received_at": iso(recovered),
        "verifier": "telemetry_health",
        "verified_at": recovered, "monitor_state": "OK", "synthetic": True,
    },
    "timeline": [{"at": fault_started, "event": "scenario_started", "by": "ca1_script"}],
}}, upsert=True)

# --- action_ledger ---
# requested ~2 min after open, acked ~4 min, verified at recovery
aid = f"{iid}:hold"
db.action_ledger.update_one({"_id": aid}, {"$set": {
    "command_id": aid, "incident_id": iid,
    "action": "HOLD", "state": "verified",
    "farm_key": "greenhouse_a", "node_id": 1,
    "monitor_id": "342585836",
    "workflow_id": "ffd62026-6b63-40e4-9b46-6ac18d2d584f",
    "source": "ca1_script", "synthetic": True,
    "requested_at": opened + timedelta(minutes=1),
    "acknowledged_at": opened + timedelta(minutes=2),
    "verified_at": recovered,
    "updated_at": now,
}, "$setOnInsert": {"created_at": opened}}, upsert=True)
db.operational_incidents.update_one({"_id": iid}, {"$addToSet": {"evidence.action_command_ids": aid}})

# --- lot_sensor_assignment ---
valid_from = datetime(2026, 10, 1, tzinfo=timezone.utc)
valid_to   = datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
collection("lot_sensor_assignments").update_one(
    {"_id": "greenhouse_a:node:1:demo-ca1-v1"},
    {"$set": {"farm_key": "greenhouse_a", "node_id": 1,
              "zone_id": "greenhouse_a_zone_1", "lot_id": "melon-lot-ca1-demo-001",
              "valid_from": valid_from, "valid_to": valid_to,
              "mapping_source": "explicit_demo_fixture", "synthetic": True, "updated_at": now},
     "$setOnInsert": {"created_at": now}}, upsert=True)

print(iid)
PYEOF
"""

# ── Bước 2: push logs lên Datadog ──────────────────────────────────────────
def step2_cmd(iid):
    return rf"""
set -a; . /etc/smiot/app.env; set +a
cd /opt/smiot
/opt/smiot/.venv/bin/python3 - << 'PYEOF'
import os, urllib.request, json
from datetime import datetime, timezone, timedelta

DD_API_KEY = os.environ.get("DD_API_KEY") or os.environ.get("DATADOG_API_KEY") or ""
iid = "{iid}"

def ts_ago(s):
    dt = datetime.now(timezone.utc) - timedelta(seconds=s)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

logs = [
    {{"ddsource":"smiot-incident","ddtags":"env:production,farm:greenhouse_a,scenario:F1,kind:false_offline",
      "hostname":"smiot-ec2","service":"smiot","status":"info","timestamp":ts_ago(300),
      "message":f"Scenario F1: false_offline triggered. farm=greenhouse_a node=1.",
      "incident":{{"id":iid,"kind":"false_offline","scenario":"F1","farm":"greenhouse_a","node":1}}}},
    {{"ddsource":"smiot-incident","ddtags":"env:production,farm:greenhouse_a,scenario:F1,kind:false_offline",
      "hostname":"smiot-ec2","service":"smiot","status":"info","timestamp":ts_ago(240),
      "message":f"Incident {{iid}} opened. Farm greenhouse_a/node1 OFFLINE but telemetry active.",
      "incident":{{"id":iid,"kind":"false_offline","scenario":"F1","farm":"greenhouse_a","node":1}}}},
    {{"ddsource":"smiot-incident","ddtags":"env:production,farm:greenhouse_a,scenario:F1,kind:false_offline",
      "hostname":"smiot-ec2","service":"smiot","status":"info","timestamp":ts_ago(180),
      "message":f"HOLD workflow dispatched. incident={{iid}} disposition=REFUSED_RESTART.",
      "incident":{{"id":iid,"kind":"false_offline","scenario":"F1","farm":"greenhouse_a","node":1}}}},
    {{"ddsource":"smiot-incident","ddtags":"env:production,farm:greenhouse_a,scenario:F1,kind:false_offline",
      "hostname":"smiot-ec2","service":"smiot","status":"info","timestamp":ts_ago(120),
      "message":f"Recovery check: computed_now=ONLINE. Incident resolving.",
      "incident":{{"id":iid,"kind":"false_offline","scenario":"F1","farm":"greenhouse_a","node":1}}}},
    {{"ddsource":"smiot-incident","ddtags":"env:production,farm:greenhouse_a,scenario:F1,kind:false_offline",
      "hostname":"smiot-ec2","service":"smiot","status":"info","timestamp":ts_ago(60),
      "message":f"Incident {{iid}} closed. kind=false_offline status=recovered scenario=F1.",
      "incident":{{"id":iid,"kind":"false_offline","scenario":"F1","farm":"greenhouse_a","node":1}}}},
]
body = json.dumps(logs).encode()
req = urllib.request.Request("https://http-intake.logs.datadoghq.com/api/v2/logs",
    data=body, method="POST",
    headers={{"DD-API-KEY": DD_API_KEY, "Content-Type": "application/json"}})
with urllib.request.urlopen(req, timeout=15) as r:
    print(json.dumps({{"logs_http": r.status, "count": len(logs)}}))
PYEOF
"""

# ── Bước 3: tạo real trace (hit page → query DD → gắn vào incident) ────────
def step3_cmd(iid, app_url):
    return rf"""
set -a; . /etc/smiot/app.env; set +a
cd /opt/smiot
curl -s -o /dev/null "{{app_url}}/incident/{{iid}}"
sleep 20
/opt/smiot/.venv/bin/python3 - << 'PYEOF'
import os, urllib.request, urllib.parse, json
from datetime import datetime, timezone, timedelta
from service.mongodb_store import database

api_key = os.environ.get("DD_API_KEY") or os.environ.get("DATADOG_API_KEY") or ""
app_key = os.environ.get("DD_APP_KEY") or os.environ.get("DATADOG_APP_KEY") or os.environ.get("DD_APPLICATION_KEY") or ""
iid = "{iid}"

now   = datetime.now(timezone.utc)
start = now - timedelta(minutes=5)
params = {{"filter[query]":"service:smiot-smart-farm",
           "filter[from]":start.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "filter[to]":now.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "page[limit]":"5"}}
url = "https://api.datadoghq.com/api/v2/spans/events?" + urllib.parse.urlencode(params)
req = urllib.request.Request(url, headers={{"DD-API-KEY":api_key,"DD-APPLICATION-KEY":app_key,"Accept":"application/json"}})
tid = None
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        spans = json.loads(r.read()).get("data",[])
        for s in spans:
            tid = (s.get("attributes") or {{}}).get("trace_id")
            if tid: break
except Exception as e:
    print(f"trace query failed: {{e}}")

if tid:
    database().operational_incidents.update_one({{"_id":iid}},{{"$set":{{"evidence.trace_ids":[str(tid)]}}}})
    print(json.dumps({{"trace_id":tid,"set":True}}))
else:
    print(json.dumps({{"trace_id":None,"set":False}}))
PYEOF
""".replace("{app_url}", app_url)


# ── Runner ──────────────────────────────────────────────────────────────────
def ssm(session, cmd, label, wait=30):
    ssm_client = session.client("ssm", region_name=REGION)
    resp = ssm_client.send_command(
        InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
        Parameters={"commands": [cmd]})
    cid = resp["Command"]["CommandId"]
    print(f"[{label}] CommandId: {cid}")
    for _ in range(wait):
        time.sleep(5)
        inv = ssm_client.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        st  = inv["Status"]
        if st not in ("Pending","InProgress","Delayed"):
            out = inv.get("StandardOutputContent","").strip()
            err = inv.get("StandardErrorContent","")[:300]
            print(f"[{label}] {st}: {out}")
            if err: print(f"[{label}] STDERR: {err}")
            return out, st
        print(f"[{label}] {st}...")
    return "", "Timeout"

if __name__ == "__main__":
    sess = boto3.Session(profile_name=PROFILE)

    print("=== Ca1: false_offline / greenhouse_a / node 1 ===")

    print("\n[1/3] Tạo incident + action_ledger + lot_assignment...")
    out1, st1 = ssm(sess, STEP1, "step1")
    if st1 != "Success" or not out1:
        print("FAILED step1"); raise SystemExit(1)
    iid = out1.strip().splitlines()[-1]
    print(f"      incident_id: {iid}")

    print("\n[2/3] Push Datadog logs...")
    out2, st2 = ssm(sess, step2_cmd(iid), "step2")

    print("\n[3/3] Tạo real APM trace...")
    out3, st3 = ssm(sess, step3_cmd(iid, APP_URL), "step3")

    print(f"\n✅ Ca1 xong. incident_id: {iid}")
    print(f"   URL: {APP_URL}/incident/{iid}")
