$ErrorActionPreference = 'Stop'
$payloadPath = Join-Path $env:TEMP ('smiot-w1-monitor-' + [guid]::NewGuid().ToString('N') + '.json')
$remote = @'
set -e
cd /opt/smiot
echo 'W1 monitor API patch is applied locally by the deployment runner; no EC2 action required.'
'@
# This file documents the intended Terraform/API change; live Datadog update is performed by the local Python helper.
Remove-Item $payloadPath -Force -ErrorAction SilentlyContinue
