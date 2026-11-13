$ErrorActionPreference = 'Stop'
$payloadPath = Join-Path $env:TEMP ('smiot-dd-metrics-' + [guid]::NewGuid().ToString('N') + '.json')
$remote = @'
set -eu
ENV=/etc/smiot/app.env
touch "$ENV"
if grep -q '^DATADOG_METRICS_ENABLED=' "$ENV"; then
  sudo sed -i 's/^DATADOG_METRICS_ENABLED=.*/DATADOG_METRICS_ENABLED=true/' "$ENV"
else
  echo 'DATADOG_METRICS_ENABLED=true' | sudo tee -a "$ENV" >/dev/null
fi
if grep -q '^SMIOT_DETECTOR_METRICS_ENABLED=' "$ENV"; then
  sudo sed -i 's/^SMIOT_DETECTOR_METRICS_ENABLED=.*/SMIOT_DETECTOR_METRICS_ENABLED=true/' "$ENV"
else
  echo 'SMIOT_DETECTOR_METRICS_ENABLED=true' | sudo tee -a "$ENV" >/dev/null
fi
sudo systemctl restart smiot.service
sleep 4
systemctl is-active smiot.service
curl -fsS --max-time 10 http://127.0.0.1:8080/healthz
'@
[IO.File]::WriteAllText($payloadPath, (@{commands=@('cd /opt/smiot', $remote)} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
$id = (aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payloadPath --comment 'Enable SMIOT Datadog metrics for W1 W4' --query Command.CommandId --output text).Trim()
Write-Output "command=$id"
do {
    Start-Sleep 3
    $result = aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json | ConvertFrom-Json
    if ($result.Status -in @('Success','Failed','Cancelled','TimedOut')) {
        Write-Output "status=$($result.Status)"
        Write-Output $result.StandardOutputContent
        if ($result.StandardErrorContent) { Write-Output "stderr=$($result.StandardErrorContent)" }
        break
    }
} while ($true)
Remove-Item $payloadPath -Force -ErrorAction SilentlyContinue
