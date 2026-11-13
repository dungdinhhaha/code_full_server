$ErrorActionPreference='Stop'
$j=Join-Path $env:TEMP ('smiot-backfill-scenario-' + [guid]::NewGuid().ToString('N') + '.json')
$py=@'
import json
from dotenv import load_dotenv
load_dotenv("/etc/smiot/app.env")
from service.mongodb_store import database
from service.scenario_evidence import _verify_post_scenario_telemetry
db=database(); out=[]
cur=db.operational_incidents.find({"status":{"$in":["open","holding","recovering"]},"scenario_run_id":{"$exists":True}}, {"_id":1,"incident_id":1,"farm_key":1,"node_id":1,"scenario_stopped_at":1,"scenario_run_id":1})
for d in cur:
    ok=False
    if d.get("scenario_stopped_at"):
        ok=_verify_post_scenario_telemetry(db, incident_id=str(d.get("_id")), run_id=str(d.get("scenario_run_id")), farm_key=str(d.get("farm_key")), node_id=d.get("node_id"), stopped_at=d.get("scenario_stopped_at"))
    out.append({"incident_id":d.get("incident_id") or d.get("_id"),"verified":ok})
print(json.dumps(out, default=str))
'@
$cmds=@('set -e','cd /opt/smiot','export PYTHONPATH=/opt/smiot',"/opt/smiot/.venv/bin/python - <<'PYCODE'`n$py`nPYCODE")
(@{commands=$cmds}|ConvertTo-Json -Compress)|Set-Content -Encoding ascii $j
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$j --comment 'SMIOT backfill scenario recovery verification' --query Command.CommandId --output text).Trim(); do {Start-Sleep 3;$r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json;if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){Write-Output $r.StandardOutputContent;if($r.Status -ne 'Success'){Write-Output $r.StandardErrorContent};break}}while($true); Remove-Item $j -Force -ErrorAction SilentlyContinue
