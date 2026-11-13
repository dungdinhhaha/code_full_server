$ErrorActionPreference='Stop'
$p=Join-Path $env:TEMP ('w6-notice-'+[guid]::NewGuid().ToString('N')+'.json')
$remote=@'
sudo bash -lc 'cd /opt/smiot; set -a; source /etc/smiot/app.env; set +a; /opt/smiot/.venv/bin/python - <<"PY"
import os,json
from pymongo import MongoClient
ids=["010ee0e9-61a1-4bcd-92d1-a110282a346b"]
c=MongoClient(os.environ["MONGODB_URI"],serverSelectionTimeoutMS=5000)
col=c[os.getenv("MONGODB_DATABASE","smiot")]["notifications"]
for x in col.find({"workflow_run_id":{"$in":ids}},{"_id":0,"event_id":1,"workflow_run_id":1,"workflow_id":1,"monitor_id":1,"farm_key":1,"workflow_status":1,"verification_status":1,"created_at":1,"message":1}): print(json.dumps(x,default=str))
c.close()
PY'
'@
[IO.File]::WriteAllText($p,(@{commands=@($remote)}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$p --comment 'SMIOT read-only W6 app notification check' --query Command.CommandId --output text).Trim()
Start-Sleep 8
$r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json
$r.Status; $r.StandardOutputContent; if($r.StandardErrorContent){$r.StandardErrorContent}
Remove-Item $p -Force
