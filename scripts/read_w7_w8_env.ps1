$ErrorActionPreference='Stop'
$tmp=Join-Path $env:TEMP ('w7w8-env-'+[guid]::NewGuid().ToString('N')+'.json')
[IO.File]::WriteAllText($tmp, (@{commands=@('grep -E "^(DD_AGENT_HOST|DD_DOGSTATSD_PORT|DATADOG_METRICS_ENABLED)=" /etc/smiot/app.env 2>/dev/null || true')}|ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
try {
  $id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$tmp --comment 'SMIOT read nonsecret metric settings' --query Command.CommandId --output text).Trim()
  Start-Sleep 3
  aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json
}
finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
