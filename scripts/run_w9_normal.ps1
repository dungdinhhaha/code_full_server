$ErrorActionPreference='Stop'
$profile='aws-moi'; $region='ap-southeast-2'; $instance='i-00bf2d3591d3ee0a2'
$cmd='cd /opt/smiot; export PYTHONPATH=/opt/smiot; /opt/smiot/.venv/bin/python scripts/emit_w9_w10_synthetic_metrics.py --send --w9-normal'
$tmp=Join-Path $env:TEMP ('smiot-w9-normal-'+[guid]::NewGuid().ToString('N')+'.json')
[IO.File]::WriteAllText($tmp, (@{commands=@($cmd)}|ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
try { $id=(aws ssm send-command --profile $profile --region $region --instance-ids $instance --document-name AWS-RunShellScript --parameters file://$tmp --comment 'SMIOT W9 normal recovery' --query Command.CommandId --output text).Trim(); Start-Sleep 8; aws ssm get-command-invocation --profile $profile --region $region --command-id $id --instance-id $instance --output json }
finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
