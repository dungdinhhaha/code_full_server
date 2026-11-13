$ErrorActionPreference='Stop'
$payload=Join-Path $env:TEMP ('w1-correlation-'+[guid]::NewGuid().ToString('N')+'.json')
$remote=@'
set -e
cd /opt/smiot
export PYTHONPATH=/opt/smiot
PY=/opt/smiot/.venv/bin/python
OUT=/tmp/smiot-w1-correlation.out
$PY scripts/demo_scenario.py start A2 --farm greenhouse_d --node 2 --seed 29 --timeout 90 > "$OUT" 2>&1
cat "$OUT"
RUN=$(grep -oE '"scenario_run_id"[[:space:]]*:[[:space:]]*"[^"]+"' "$OUT" | head -1 | sed -E 's/.*"([^"]+)"/\1/' || true)
if [ -z "$RUN" ]; then echo 'scenario_run_id_missing'; exit 2; fi
sleep 65
$PY scripts/demo_scenario.py stop --run-id "$RUN" --farm greenhouse_d --timeout 30
rm -f "$OUT"
'@
[IO.File]::WriteAllText($payload,(@{commands=@($remote)}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payload --comment 'SMIOT W1 isolated virtual PLC correlation drill' --query Command.CommandId --output text).Trim()
Write-Output "command=$id"
do{
  Start-Sleep 8
  $r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json
  Write-Output "status=$($r.Status)"
  if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){Write-Output $r.StandardOutputContent; if($r.StandardErrorContent){Write-Output "stderr=$($r.StandardErrorContent)"}; break}
}while($true)
Remove-Item $payload -Force
