$ErrorActionPreference='Stop'
$root='D:\IOT Trung\code_full_server'
$file=Join-Path $root 'scripts/backfill_datadog_workflow_incidents.py'
$b64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($file))
$cmd="set -e; echo $b64 | base64 -d > /tmp/backfill_datadog_workflow_incidents.py; set -a; . /etc/smiot/app.env; set +a; cd /opt/smiot; sudo -E -u smiot env PYTHONPATH=/opt/smiot /opt/smiot/.venv/bin/python /tmp/backfill_datadog_workflow_incidents.py"
$p=Join-Path $env:TEMP 'backfill-workflow.json'; [IO.File]::WriteAllText($p,(@{commands=@($cmd)}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$p --comment 'Backfill Datadog workflow evidence headers' --query Command.CommandId --output text).Trim(); Write-Output "command=$id"
do { Start-Sleep 4; $r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json; Write-Output "status=$($r.Status)"; if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){Write-Output $r.StandardOutputContent; if($r.StandardErrorContent){Write-Output "stderr=$($r.StandardErrorContent)"}; break} } while($true)
Remove-Item $p -Force -ErrorAction SilentlyContinue
