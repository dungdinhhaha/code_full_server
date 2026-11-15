"""
Ca3 — service_down — greenhouse_c / node 1
Chạy: python outputs/demo_mvp/run_ca3.py
"""
import boto3, time, json

INSTANCE_ID = "i-00bf2d3591d3ee0a2"
REGION      = "ap-southeast-2"
PROFILE     = "aws-moi"
APP_URL     = "https://13-238-30-218.sslip.io"

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

run_id  = f"c3-{uuid.uuid4()}"
digest  = hashlib.sha256(run_id.encode()).hexdigest()[:16].upper()
iid     = f"INC-SMIOT-SCENARIO-{digest}"
from datetime import timedelta
now            = utc_now()
# Monitor query: last_2m + ~3m37s producer visibility delay → detection lag ~6 min
# Total response drill: ~9 min (GUARDED_RECOVERY, service restart + probe check)
fault_started  = now - timedelta(minutes=20)
detected       = now - timedelta(minutes=14)   # 6 min detection lag (last_2m + 3m37s)
opened         = detected
recovered      = now - timedelta(minutes=9)    # 5 min to respond, restart & verify
safe           = recovered
exec_id = str(uuid.uuid4())

db.operational_incidents.update_one({"_id": iid}, {"$setOnInsert": {
    "_id": iid, "incident_id": iid,
    "kind": "service_down", "status": "recovered",
    "farm_key": "greenhouse_c", "node_id": 1,
    "scenario_run_id": run_id, "scenario": "h1_service_down", "scenario_code": "H1",
    "monitor_id": "342585838",
    "workflow_id": "373ed0c0-4509-4fcd-a067-f54f0becc00e",
    "last_workflow_execution_id": exec_id,
    "last_workflow_status": "succeeded",
    "last_workflow_disposition": "GUARDED_RECOVERY",
    "last_action": "HOLD",
    "detected_at": detected, "fault_started_at": fault_started, "opened_at": opened,
    "recovered_at": recovered, "safe_at": safe, "updated_at": now,
    "synthetic": True,
    "evidence": {
        "scenario_run_ids": [run_id],
        "action_command_ids": [],
        "monitor_ids": ["342585838"],
        "workflow_ids": ["373ed0c0-4509-4fcd-a067-f54f0becc00e"],
        "trace_ids": [],
        "workflow_observations": [{
            "execution_id": exec_id,
            "workflow_id": "373ed0c0-4509-4fcd-a067-f54f0becc00e",
            "status": "succeeded", "disposition": "GUARDED_RECOVERY",
            "run_at": iso(opened), "synthetic": True,
        }],
    },
    "recovery_verification": {
        "http_status": 200, "newest_sample_age_s": 15,
        "verifier": "smiot_external_probe",
        "verified_at": recovered, "monitor_state": "OK", "synthetic": True,
    },
    "timeline": [{"at": fault_started, "event": "scenario_started", "by": "ca3_script"}],
}}, upsert=True)

# requested ~1 min after open, acked ~3 min, verified at recovery
aid = f"{iid}:hold"
db.action_ledger.update_one({"_id": aid}, {"$set": {
    "command_id": aid, "incident_id": iid,
    "action": "HOLD", "state": "verified",
    "farm_key": "greenhouse_c", "node_id": 1,
    "monitor_id": "342585838",
    "workflow_id": "373ed0c0-4509-4fcd-a067-f54f0becc00e",
    "source": "ca3_script", "synthetic": True,
    "requested_at": opened + timedelta(minutes=1),
    "acknowledged_at": opened + timedelta(minutes=2),
    "verified_at": recovered,
    "updated_at": now,
}, "$setOnInsert": {"created_at": opened}}, upsert=True)
db.operational_incidents.update_one({"_id": iid}, {"$addToSet": {"evidence.action_command_ids": aid}})

valid_from = datetime(2026, 10, 1, tzinfo=timezone.utc)
valid_to   = datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
collection("lot_sensor_assignments").update_one(
    {"_id": "greenhouse_c:node:1:demo-ca3-v1"},
    {"$set": {"farm_key": "greenhouse_c", "node_id": 1,
              "zone_id": "greenhouse_c_zone_1", "lot_id": "pepper-lot-ca3-demo-001",
              "valid_from": valid_from, "valid_to": valid_to,
              "mapping_source": "explicit_demo_fixture", "synthetic": True, "updated_at": now},
     "$setOnInsert": {"created_at": now}}, upsert=True)

print(iid)
PYEOF
"""

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
    {{"ddsource":"smiot-incident","ddtags":"env:production,farm:greenhouse_c,scenario:H1,kind:service_down",
      "hostname":"smiot-ec2","service":"smiot","status":"error","timestamp":ts_ago(300),
      "message":f"Scenario H1: smiot.service inactive on farm=greenhouse_c.",
      "incident":{{"id":iid,"kind":"service_down","scenario":"H1","farm":"greenhouse_c","node":1}}}},
    {{"ddsource":"smiot-incident","ddtags":"env:production,farm:greenhouse_c,scenario:H1,kind:service_down",
      "hostname":"smiot-ec2","service":"smiot","status":"error","timestamp":ts_ago(240),
      "message":f"Incident {{iid}} opened. service_down farm=greenhouse_c node=1. Health check failed.",
      "incident":{{"id":iid,"kind":"service_down","scenario":"H1","farm":"greenhouse_c","node":1}}}},
    {{"ddsource":"smiot-incident","ddtags":"env:production,farm:greenhouse_c,scenario:H1,kind:service_down",
      "hostname":"smiot-ec2","service":"smiot","status":"info","timestamp":ts_ago(180),
      "message":f"HOLD workflow dispatched. incident={{iid}} disposition=GUARDED_RECOVERY.",
      "incident":{{"id":iid,"kind":"service_down","scenario":"H1","farm":"greenhouse_c","node":1}}}},
    {{"ddsource":"smiot-incident","ddtags":"env:production,farm:greenhouse_c,scenario:H1,kind:service_down",
      "hostname":"smiot-ec2","service":"smiot","status":"info","timestamp":ts_ago(120),
      "message":f"Recovery check: HTTP 200 from smiot probe. service active.",
      "incident":{{"id":iid,"kind":"service_down","scenario":"H1","farm":"greenhouse_c","node":1}}}},
    {{"ddsource":"smiot-incident","ddtags":"env:production,farm:greenhouse_c,scenario:H1,kind:service_down",
      "hostname":"smiot-ec2","service":"smiot","status":"info","timestamp":ts_ago(60),
      "message":f"Incident {{iid}} closed. kind=service_down status=recovered scenario=H1.",
      "incident":{{"id":iid,"kind":"service_down","scenario":"H1","farm":"greenhouse_c","node":1}}}},
]
body = json.dumps(logs).encode()
req = urllib.request.Request("https://http-intake.logs.datadoghq.com/api/v2/logs",
    data=body, method="POST",
    headers={{"DD-API-KEY": DD_API_KEY, "Content-Type": "application/json"}})
with urllib.request.urlopen(req, timeout=15) as r:
    print(json.dumps({{"logs_http": r.status, "count": len(logs)}}))
PYEOF
"""

def step3_cmd(iid, app_url):
    return rf"""
set -a; . /etc/smiot/app.env; set +a
cd /opt/smiot
curl -s -o /dev/null "{app_url}/incident/{iid}"
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
        for s in json.loads(r.read()).get("data",[]):
            tid = (s.get("attributes") or {{}}).get("trace_id")
            if tid: break
except Exception as e:
    print(f"trace query: {{e}}")

if tid:
    database().operational_incidents.update_one({{"_id":iid}},{{"$set":{{"evidence.trace_ids":[str(tid)]}}}})
    print(json.dumps({{"trace_id":tid,"set":True}}))
else:
    print(json.dumps({{"trace_id":None,"set":False}}))
PYEOF
"""

def ssm(session, cmd, label, wait=30):
    c = session.client("ssm", region_name=REGION)
    resp = c.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
                          Parameters={"commands": [cmd]})
    cid = resp["Command"]["CommandId"]
    print(f"[{label}] CommandId: {cid}")
    for _ in range(wait):
        time.sleep(5)
        inv = c.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
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
    print("=== Ca3: service_down / greenhouse_c / node 1 ===")

    print("\n[1/3] Tạo incident + action_ledger + lot_assignment...")
    out1, st1 = ssm(sess, STEP1, "step1")
    if st1 != "Success" or not out1: print("FAILED step1"); raise SystemExit(1)
    iid = out1.strip().splitlines()[-1]
    print(f"      incident_id: {iid}")

    print("\n[2/3] Push Datadog logs...")
    ssm(sess, step2_cmd(iid), "step2")

    print("\n[3/3] Tạo real APM trace...")
    ssm(sess, step3_cmd(iid, APP_URL), "step3")

    print(f"\n✅ Ca3 xong. incident_id: {iid}")
    print(f"   URL: {APP_URL}/incident/{iid}")
