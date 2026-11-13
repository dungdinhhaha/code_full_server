$ErrorActionPreference='Stop'
$j=Join-Path $env:TEMP ('smiot-close-w9-' + [guid]::NewGuid().ToString('N') + '.json')
$py=@'
import json
from dotenv import load_dotenv
load_dotenv("/etc/smiot/app.env")
from service.mongodb_store import database
db=database(); ids=["INC-SMIOT-W9-DRILL-2DFA79E1EE","INC-SMIOT-W9-DRILL-B9F5377EC7"]
out=[]
for i in ids:
    d=db.operational_incidents.find_one({"_id":i})
    events=(d or {}).get("timeline") or []
    if d and any(e.get("event") in {"late_ack_received","recovered_late_ack"} for e in events):
        r=db.operational_incidents.update_one({"_id":i,"status":{"$in":["open","holding","recovering"]}}, {"$set":{"status":"recovered","recovery_verification":{"verified":True,"method":"matching_late_ack_backfill","synthetic":True}}})
        out.append({"id":i,"modified":r.modified_count})
print(json.dumps(out))
'@
$cmds=@('set -e','cd /opt/smiot','export PYTHONPATH=/opt/smiot',"/opt/smiot/.venv/bin/python - <<'PYCODE'`n$py`nPYCODE")
(@{commands=$cmds}|ConvertTo-Json -Compress)|Set-Content -Encoding ascii $j
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$j --comment 'SMIOT close verified W9 backlog' --query Command.CommandId --output text).Trim(); do {Start-Sleep 3;$r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json;if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){Write-Output $r.StandardOutputContent;break}}while($true); Remove-Item $j -Force -ErrorAction SilentlyContinue
