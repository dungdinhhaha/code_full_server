param(
  [string]$Profile = 'aws-moi',
  [string]$Region = 'ap-southeast-2',
  [string]$InstanceId = 'i-00bf2d3591d3ee0a2'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tmp = Join-Path $env:TEMP ('smiot-w2-' + [guid]::NewGuid().ToString('N'))
$archive = Join-Path $env:TEMP ('smiot-w2-' + [guid]::NewGuid().ToString('N') + '.tgz')
$json = Join-Path $env:TEMP ('smiot-w2-' + [guid]::NewGuid().ToString('N') + '.json')
New-Item -ItemType Directory -Path (Join-Path $tmp 'scripts'),(Join-Path $tmp 'service') | Out-Null
Copy-Item (Join-Path $root 'scripts/verify_and_clear_demo_safe_mode.py') (Join-Path $tmp 'scripts')
Copy-Item (Join-Path $root 'scripts/set_demo_sensor_fault.py') (Join-Path $tmp 'scripts')
Copy-Item (Join-Path $root 'service/telemetry_health.py') (Join-Path $tmp 'service')
Copy-Item (Join-Path $root 'service/demo_mode.py') (Join-Path $tmp 'service')
tar -czf $archive -C $tmp scripts service
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($archive))
$commands = @(
  'set -e',
  "printf '%s' '$b64' | base64 -d > /tmp/smiot-w2-patch.tgz",
  'sudo tar -xzf /tmp/smiot-w2-patch.tgz -C /opt/smiot',
  'sudo chown root:root /opt/smiot/scripts/verify_and_clear_demo_safe_mode.py /opt/smiot/scripts/set_demo_sensor_fault.py /opt/smiot/service/telemetry_health.py /opt/smiot/service/demo_mode.py',
  'sudo systemctl restart smiot.service',
  'sleep 5',
  'printf "service=%s\n" "$(systemctl is-active smiot.service)"',
  'printf "healthz=%s\n" "$(curl -s -o /dev/null -w ''%{http_code}'' --max-time 5 http://127.0.0.1:8080/healthz)"',
  'rm -f /tmp/smiot-w2-patch.tgz'
)
 [IO.File]::WriteAllText($json, (@{commands=$commands} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
$cmd = (aws ssm send-command --profile $Profile --region $Region --instance-ids $InstanceId --document-name AWS-RunShellScript --parameters file://$json --comment 'SMIOT W2 cadence-aware verifier patch' --query Command.CommandId --output text).Trim()
Write-Output "command=$cmd"
$deadline = (Get-Date).AddMinutes(3)
do {
  Start-Sleep -Seconds 3
  $raw = aws ssm get-command-invocation --profile $Profile --region $Region --command-id $cmd --instance-id $InstanceId --output json | ConvertFrom-Json
  Write-Output "status=$($raw.Status)"
  if ($raw.Status -in @('Success','Failed','Cancelled','TimedOut')) {
    Write-Output $raw.StandardOutputContent
    if ($raw.StandardErrorContent) { Write-Output 'stderr_present=1' }
    break
  }
} while ((Get-Date) -lt $deadline)
Remove-Item $tmp,$archive,$json -Recurse -Force -ErrorAction SilentlyContinue
