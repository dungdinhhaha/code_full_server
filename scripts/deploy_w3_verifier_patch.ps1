$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tmp = Join-Path $env:TEMP ('smiot-w3-' + [guid]::NewGuid().ToString('N'))
$archive = Join-Path $env:TEMP ('smiot-w3-' + [guid]::NewGuid().ToString('N') + '.tgz')
$json = Join-Path $env:TEMP ('smiot-w3-' + [guid]::NewGuid().ToString('N') + '.json')
New-Item -ItemType Directory -Path $tmp | Out-Null
Copy-Item (Join-Path $root 'main.py') (Join-Path $tmp 'main.py')
tar -czf $archive -C $tmp main.py
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($archive))
$commands = @(
  'set -e',
  "printf '%s' '$b64' | base64 -d > /tmp/smiot-w3-patch.tgz",
  'sudo tar -xzf /tmp/smiot-w3-patch.tgz -C /opt/smiot',
  'sudo chown root:root /opt/smiot/main.py',
  'sudo systemctl restart smiot.service',
  'sleep 8',
  'printf "service=%s\n" "$(systemctl is-active smiot.service)"',
  'printf "healthz=%s\n" "$(curl -s -o /dev/null -w ''%{http_code}'' --max-time 5 http://127.0.0.1:8080/healthz)"',
  'rm -f /tmp/smiot-w3-patch.tgz'
)
[IO.File]::WriteAllText($json, (@{commands=$commands} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
$cmd = (aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$json --comment 'SMIOT W3 verifier wait for SSM terminal state' --query Command.CommandId --output text).Trim()
Write-Output "command=$cmd"
$deadline=(Get-Date).AddMinutes(2)
do {
  Start-Sleep -Seconds 3
  $r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $cmd --instance-id i-00bf2d3591d3ee0a2 --output json | ConvertFrom-Json
  if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){ Write-Output "status=$($r.Status)"; Write-Output $r.StandardOutputContent; break }
} while((Get-Date)-lt $deadline)
Remove-Item $tmp,$archive,$json -Recurse -Force -ErrorAction SilentlyContinue
