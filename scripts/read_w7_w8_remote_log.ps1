$ErrorActionPreference='Stop'
$tmp=Join-Path $env:TEMP ('w7w8-log-'+[guid]::NewGuid().ToString('N')+'.json')
[IO.File]::WriteAllText($tmp, (@{commands=@('ps -ef | grep emit_w7_w8 | grep -v grep || true; tail -n 20 /tmp/smiot-w7-demo.log 2>/dev/null || true')}|ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
try {
  $id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$tmp --comment 'SMIOT read W7 W8 drill log' --query Command.CommandId --output text).Trim()
  Start-Sleep 3
  aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json
}
finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
