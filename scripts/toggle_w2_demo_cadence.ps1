param([ValidateSet('enable','disable')][string]$Mode='enable')
$ErrorActionPreference='Stop'
$profile='aws-moi'; $region='ap-southeast-2'; $instance='i-00bf2d3591d3ee0a2'
$commands = if ($Mode -eq 'enable') {
  @('set -e','sudo cp /etc/smiot/app.env /tmp/smiot-app.env.w2.bak','if sudo grep -q "^SMIOT_W2_DEMO_MODE=" /etc/smiot/app.env; then sudo sed -i "s/^SMIOT_W2_DEMO_MODE=.*/SMIOT_W2_DEMO_MODE=true/" /etc/smiot/app.env; else echo "SMIOT_W2_DEMO_MODE=true" | sudo tee -a /etc/smiot/app.env >/dev/null; fi','sudo systemctl restart smiot.service','sleep 8','printf "mode=demo10s service=%s healthz=" "$(systemctl is-active smiot.service)"','curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 http://127.0.0.1:8080/healthz')
} else {
  @('set -e','if sudo test -f /tmp/smiot-app.env.w2.bak; then sudo cp /tmp/smiot-app.env.w2.bak /etc/smiot/app.env; sudo rm -f /tmp/smiot-app.env.w2.bak; else sudo sed -i "/^SMIOT_W2_DEMO_MODE=/d" /etc/smiot/app.env; fi','sudo systemctl restart smiot.service','sleep 8','printf "mode=normal60s service=%s healthz=" "$(systemctl is-active smiot.service)"','curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 http://127.0.0.1:8080/healthz')
}
$f=Join-Path $env:TEMP ('smiot-w2-cadence-'+[guid]::NewGuid().ToString('N')+'.json')
[IO.File]::WriteAllText($f,(@{commands=$commands}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
try {
  $id=(aws ssm send-command --profile $profile --region $region --instance-ids $instance --document-name AWS-RunShellScript --parameters file://$f --comment "SMIOT W2 cadence $Mode" --query Command.CommandId --output text).Trim()
  Start-Sleep -Seconds 12
  aws ssm get-command-invocation --profile $profile --region $region --command-id $id --instance-id $instance --output json --query '{CommandId:CommandId,Status:Status,Out:StandardOutputContent,Err:StandardErrorContent}'
} finally { Remove-Item $f -Force -ErrorAction SilentlyContinue }
