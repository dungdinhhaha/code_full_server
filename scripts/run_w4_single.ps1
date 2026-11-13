$ErrorActionPreference='Stop'
$payload=Join-Path $env:TEMP ('w4-'+[guid]::NewGuid().ToString('N')+'.json')
$remote='cd /opt/smiot; export PYTHONPATH=/opt/smiot; PY=/opt/smiot/.venv/bin/python; $PY scripts/demo_scenario.py start D2 --farm greenhouse_a --node 1 --seed 17 --timeout 90; sleep 35'
[IO.File]::WriteAllText($payload,(@{commands=@($remote)}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payload --comment 'SMIOT W4 status mismatch drill' --query Command.CommandId --output text).Trim()
Write-Output "command=$id"
do{
  Start-Sleep 8
  $r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json
  Write-Output "status=$($r.Status)"
  if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){Write-Output $r.StandardOutputContent; if($r.StandardErrorContent){Write-Output "stderr=$($r.StandardErrorContent)"};break}
}while($true)
Remove-Item $payload -Force
