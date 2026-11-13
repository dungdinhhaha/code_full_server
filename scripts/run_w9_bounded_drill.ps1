$ErrorActionPreference = 'Stop'
$profile='aws-moi'; $region='ap-southeast-2'; $instance='i-00bf2d3591d3ee0a2'
$tmp=Join-Path $env:TEMP ('smiot-w9-'+[guid]::NewGuid().ToString('N')+'.json')
$cmd='cd /opt/smiot; export PYTHONPATH=/opt/smiot; /opt/smiot/.venv/bin/python scripts/emit_w9_w10_synthetic_metrics.py --send'
[IO.File]::WriteAllText($tmp, (@{commands=@($cmd)}|ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
try {
  $id=(aws ssm send-command --profile $profile --region $region --instance-ids $instance --document-name AWS-RunShellScript --parameters file://$tmp --comment 'SMIOT W9 bounded synthetic ACK drill' --query Command.CommandId --output text).Trim()
  Start-Sleep -Seconds 8
  aws ssm get-command-invocation --profile $profile --region $region --command-id $id --instance-id $instance --output json
} finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
