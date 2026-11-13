$p=Join-Path $env:TEMP 'w4-stop.json'
[IO.File]::WriteAllText($p,(@{commands=@('cd /opt/smiot; export PYTHONPATH=/opt/smiot; /opt/smiot/.venv/bin/python scripts/demo_scenario.py stop --run-id 05b3c872-639b-4a97-8fa4-3a763473b3e0 --farm greenhouse_a --timeout 30')}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$p --comment 'SMIOT W4 restore normal' --query Command.CommandId --output text).Trim()
Start-Sleep 8
$r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json
$r.Status; $r.StandardOutputContent
Remove-Item $p -Force
