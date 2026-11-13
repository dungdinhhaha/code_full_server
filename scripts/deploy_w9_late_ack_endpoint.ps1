$ErrorActionPreference='Stop'
$root='D:\IOT Trung\code_full_server'
$tmp=Join-Path $env:TEMP ('w9-late-src-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $tmp 'service') | Out-Null
Copy-Item (Join-Path $root 'main.py') (Join-Path $tmp 'main.py')
Copy-Item (Join-Path $root 'service/demo_mode.py') (Join-Path $tmp 'service/demo_mode.py')
Copy-Item (Join-Path $root 'service/operational_evidence.py') (Join-Path $tmp 'service/operational_evidence.py')
$archive=$tmp+'.tgz'; tar -czf $archive -C $tmp main.py service
$b64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($archive))
$cmds=@('set -e',"echo $b64 | base64 -d > /tmp/smiot-w9-late.tgz",'sudo tar -xzf /tmp/smiot-w9-late.tgz -C /opt/smiot','sudo chown root:root /opt/smiot/main.py /opt/smiot/service/demo_mode.py','sudo systemctl restart smiot.service','sleep 8','printf "service=%s\n" "$(systemctl is-active smiot.service)"','printf "healthz=%s\n" "$(curl -s -o /dev/null -w ''%{http_code}'' --max-time 5 http://127.0.0.1:8080/healthz)"')
$p=Join-Path $env:TEMP 'w9-late-deploy.json'; [IO.File]::WriteAllText($p,(@{commands=$cmds}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$p --comment 'SMIOT W9 admin late ACK endpoint deploy' --query Command.CommandId --output text).Trim(); Write-Output "command=$id"
do { Start-Sleep 5; $r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json; Write-Output "status=$($r.Status)"; if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){Write-Output $r.StandardOutputContent; if($r.StandardErrorContent){Write-Output "stderr=$($r.StandardErrorContent)"}; break} } while($true)
Remove-Item $p,$tmp,$archive -Recurse -Force -ErrorAction SilentlyContinue
