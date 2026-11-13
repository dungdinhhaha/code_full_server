$ErrorActionPreference='Stop'
$run='cc797f61-01b9-4b63-9843-a2abbc85f2fc'
$payload=Join-Path $env:TEMP 'stop-read-demo.json'
$py=@'
import json, os
from service.mongodb_store import database
run_id = os.environ['RUN_ID']
db = database()
run = db['scenario_runs'].find_one({'_id': run_id}, {'_id':1,'incident_id':1,'status':1,'scenario_code':1,'farm_key':1}) or {}
inc = None
if run.get('incident_id'):
    inc = db['operational_incidents'].find_one({'_id': run['incident_id']}, {'_id':1,'incident_id':1,'monitor_id':1,'workflow_id':1,'last_workflow_execution_id':1,'evidence':1,'status':1})
print(json.dumps({'run':run,'incident':inc}, default=str, ensure_ascii=False))
'@
$b64=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($py))
$commands=@(
  "cd /opt/smiot; export PYTHONPATH=/opt/smiot; /opt/smiot/.venv/bin/python scripts/demo_scenario.py stop --run-id $run --farm greenhouse_a --timeout 12",
  "echo $b64 | base64 -d > /tmp/read-demo-incident.py; set -a; . /etc/smiot/app.env; set +a; cd /opt/smiot; export PYTHONPATH=/opt/smiot; RUN_ID=$run /opt/smiot/.venv/bin/python /tmp/read-demo-incident.py; rm -f /tmp/read-demo-incident.py"
)
[IO.File]::WriteAllText($payload,(@{commands=$commands}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payload --comment 'stop W4 demo and read incident identity' --query Command.CommandId --output text).Trim()
do { Start-Sleep 5; $r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json; if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){Write-Output $r.StandardOutputContent; if($r.StandardErrorContent){Write-Output "stderr=$($r.StandardErrorContent)"};break} } while($true)
Remove-Item $payload -Force
