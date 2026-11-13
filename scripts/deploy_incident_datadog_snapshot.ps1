$ErrorActionPreference='Stop'
$root='D:\IOT Trung\code_full_server'
$tmp=Join-Path $env:TEMP ('incident-dd-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $tmp 'pages') | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tmp 'service') | Out-Null
Copy-Item (Join-Path $root 'pages/incident.py') (Join-Path $tmp 'pages/incident.py')
Copy-Item (Join-Path $root 'service/datadog_reader.py') (Join-Path $tmp 'service/datadog_reader.py')
Copy-Item (Join-Path $root 'service/incident_blackbox.py') (Join-Path $tmp 'service/incident_blackbox.py')
$archive=$tmp+'.tgz'; tar -czf $archive -C $tmp pages service
$b64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($archive))
$cmds=@('set -e',"echo $b64 | base64 -d > /tmp/smiot-incident-dd.tgz",'sudo tar -xzf /tmp/smiot-incident-dd.tgz -C /opt/smiot','sudo chown root:root /opt/smiot/pages/incident.py /opt/smiot/service/datadog_reader.py /opt/smiot/service/incident_blackbox.py','sudo systemctl restart smiot.service','sleep 8','systemctl is-active smiot.service','curl -sS --max-time 5 http://127.0.0.1:8080/healthz | head -c 200')
$p=Join-Path $env:TEMP 'smiot-incident-dd.json'; [IO.File]::WriteAllText($p,(@{commands=$cmds}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$p --comment 'SMIOT incident Datadog read-only snapshot' --query Command.CommandId --output text).Trim(); Write-Output "command=$id"
do { Start-Sleep 5; $r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json; Write-Output "status=$($r.Status)"; if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){Write-Output $r.StandardOutputContent; if($r.StandardErrorContent){Write-Output "stderr=$($r.StandardErrorContent)"}; break} } while($true)
Remove-Item $p,$tmp,$archive -Recurse -Force -ErrorAction SilentlyContinue
