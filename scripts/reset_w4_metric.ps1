$ErrorActionPreference = 'Stop'
$payloadPath = Join-Path $env:TEMP ('smiot-w4-reset-' + [guid]::NewGuid().ToString('N') + '.json')
$remote = @'
set -eu
for farm_node in greenhouse_a:1 greenhouse_c:1; do
  farm=${farm_node%:*}; node=${farm_node#*:}
  printf 'smiot.telemetry.status_mismatch:0|g|#farm:%s,node:%s,source:smiot_demo_stream\n' "$farm" "$node" | nc -u -w1 127.0.0.1 8125 || true
done
echo reset_sent
'@
[IO.File]::WriteAllText($payloadPath, (@{commands=@('cd /opt/smiot', $remote)} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
$id = (aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payloadPath --comment 'Reset W4 synthetic mismatch metric after stop' --query Command.CommandId --output text).Trim()
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
