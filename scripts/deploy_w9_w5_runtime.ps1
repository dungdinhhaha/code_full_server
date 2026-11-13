$ErrorActionPreference='Stop'
$root='D:\IOT Trung\code_full_server'
$tmp=Join-Path $env:TEMP ('smiot-w9-w5-src-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $tmp 'service'),(Join-Path $tmp 'scripts') | Out-Null
Copy-Item (Join-Path $root 'service/mqtt.py') (Join-Path $tmp 'service/mqtt.py')
Copy-Item (Join-Path $root 'scripts/probe_w5_dependencies.py') (Join-Path $tmp 'scripts/probe_w5_dependencies.py')
$archive=$tmp+'.tgz'; tar -czf $archive -C $tmp service scripts
$b64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($archive))
$commands=@('set -e','cd /opt/smiot',"echo $b64 | base64 -d > /tmp/smiot-w9-w5.tgz",'sudo tar -xzf /tmp/smiot-w9-w5.tgz -C /opt/smiot')
$commands += @(
  'sudo chown root:root /opt/smiot/service/mqtt.py /opt/smiot/scripts/probe_w5_dependencies.py',
  'sudo systemctl restart smiot.service',
  'sleep 8',
  'printf "service=%s\n" "$(systemctl is-active smiot.service)"',
  'printf "healthz=%s\n" "$(curl -s -o /dev/null -w ''%{http_code}'' --max-time 5 http://127.0.0.1:8080/healthz)"'
)
$json=Join-Path $env:TEMP ('smiot-w9-w5-'+[guid]::NewGuid().ToString('N')+'.json')
[IO.File]::WriteAllText($json,(@{commands=$commands}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$json --comment 'SMIOT W9 late ACK and W5 dependency probe deploy' --query Command.CommandId --output text).Trim()
Write-Output "command=$id"
do {
  Start-Sleep 5
  $r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json
  Write-Output "status=$($r.Status)"
  if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){
    Write-Output $r.StandardOutputContent
    if($r.StandardErrorContent){Write-Output "stderr=$($r.StandardErrorContent)"}
    break
  }
} while($true)
Remove-Item $json -Force
Remove-Item $tmp,$archive -Recurse -Force -ErrorAction SilentlyContinue
