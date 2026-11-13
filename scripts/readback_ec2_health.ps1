$ErrorActionPreference = 'Stop'
$p = Join-Path $env:TEMP ('smiot-readback-' + [guid]::NewGuid().ToString('N') + '.json')
$payload = @{commands=@(
  'systemctl is-active smiot.service',
  'systemctl is-active mongod.service',
  'systemctl is-active mosquitto.service',
  'curl -s -o /dev/null -w ''healthz=%{http_code}\n'' --max-time 5 http://127.0.0.1:8080/healthz',
  'sudo -n /usr/local/sbin/smiot-recovery-mongo-readback 2>/dev/null || true',
  'systemctl show smiot.service -p WorkingDirectory --value',
  'pwd; ls -ld /opt/smiot /opt/smiot/service 2>/dev/null || true'
)} | ConvertTo-Json -Compress
[IO.File]::WriteAllText($p, $payload, [Text.UTF8Encoding]::new($false))
$id = (aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$p --query Command.CommandId --output text).Trim()
Start-Sleep -Seconds 6
$o = aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json | ConvertFrom-Json
Write-Output "command=$id"
Write-Output "status=$($o.Status)"
Write-Output $o.StandardOutputContent
Remove-Item $p -Force -ErrorAction SilentlyContinue
