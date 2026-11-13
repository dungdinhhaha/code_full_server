$p=Join-Path $env:TEMP 'w5-recovery-window.json'
$cmd='cd /opt/smiot; export PYTHONPATH=/opt/smiot; for i in 1 2 3 4 5 6; do /opt/smiot/.venv/bin/python scripts/emit_w5_dependency_metrics.py --mode normal --send; sleep 55; done'
[IO.File]::WriteAllText($p,(@{commands=@($cmd)}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$p --comment 'SMIOT W5 clean recovery window' --query Command.CommandId --output text).Trim()
Write-Output "command=$id"
Remove-Item $p -Force
