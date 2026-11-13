$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tmp = Join-Path $env:TEMP ('smiot-special-' + [guid]::NewGuid().ToString('N'))
$archive = Join-Path $env:TEMP ('smiot-special-' + [guid]::NewGuid().ToString('N') + '.tgz')
$json = Join-Path $env:TEMP ('smiot-special-' + [guid]::NewGuid().ToString('N') + '.json')
New-Item -ItemType Directory -Path (Join-Path $tmp 'service') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tmp 'scripts') -Force | Out-Null
Copy-Item (Join-Path $root 'service/special_incident_correlation.py') (Join-Path $tmp 'service')
Copy-Item (Join-Path $root 'service/demo_mode.py') (Join-Path $tmp 'service')
Copy-Item (Join-Path $root 'service/mqtt.py') (Join-Path $tmp 'service')
Copy-Item (Join-Path $root 'service/detector_heartbeat.py') (Join-Path $tmp 'service')
Copy-Item (Join-Path $root 'service/scenario_evidence.py') (Join-Path $tmp 'service')
Copy-Item (Join-Path $root 'scripts/run_correlated_w3_w5.py') (Join-Path $tmp 'scripts')
Copy-Item (Join-Path $root 'scripts/run_w10_correlated.py') (Join-Path $tmp 'scripts')
Copy-Item (Join-Path $root 'scripts/run_w6_correlated_drill.ps1') (Join-Path $tmp 'scripts')
Copy-Item (Join-Path $root 'scripts/run_w9_correlated_drill.ps1') (Join-Path $tmp 'scripts')
tar -czf $archive -C $tmp service scripts
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($archive))
$commands = @(
  'set -e',
  "sudo mkdir -p /opt/smiot-rollback/$(date -u +%Y%m%dT%H%M%SZ)",
  "sudo cp /opt/smiot/service/special_incident_correlation.py /opt/smiot-rollback/$(date -u +%Y%m%dT%H%M%SZ)/special_incident_correlation.py 2>/dev/null || true",
  "printf '%s' '$b64' | base64 -d > /tmp/smiot-special.tgz",
  'sudo tar -xzf /tmp/smiot-special.tgz -C /opt/smiot',
  'sudo chown root:root /opt/smiot/service/special_incident_correlation.py /opt/smiot/service/demo_mode.py /opt/smiot/service/mqtt.py /opt/smiot/service/detector_heartbeat.py /opt/smiot/service/scenario_evidence.py /opt/smiot/scripts/run_correlated_w3_w5.py /opt/smiot/scripts/run_w10_correlated.py /opt/smiot/scripts/run_w6_correlated_drill.ps1 /opt/smiot/scripts/run_w9_correlated_drill.ps1',
  'sudo systemctl restart smiot.service',
  'sleep 8',
  'printf "service=%s\n" "$(systemctl is-active smiot.service)"',
  'printf "healthz=%s\n" "$(curl -s -o /dev/null -w %{http_code} --max-time 5 http://127.0.0.1:8080/healthz)"',
  'rm -f /tmp/smiot-special.tgz'
)
[IO.File]::WriteAllText($json, (@{commands=$commands} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
$cmd = (aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$json --comment 'SMIOT specialized incident correlation deploy' --query Command.CommandId --output text).Trim()
Write-Output "command=$cmd"
$deadline=(Get-Date).AddMinutes(3)
do {
  Start-Sleep -Seconds 3
  $r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $cmd --instance-id i-00bf2d3591d3ee0a2 --output json | ConvertFrom-Json
  if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){ Write-Output "status=$($r.Status)"; Write-Output $r.StandardOutputContent; if($r.Status -ne 'Success'){Write-Output $r.StandardErrorContent}; break }
} while((Get-Date)-lt $deadline)
Remove-Item $tmp,$archive,$json -Recurse -Force -ErrorAction SilentlyContinue
