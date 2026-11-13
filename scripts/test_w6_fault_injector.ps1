$ErrorActionPreference='Stop'
$p=Join-Path $env:TEMP ('smiot-w6-inject-' + [guid]::NewGuid().ToString('N') + '.json')
$cmd=@'
set -e
farm=greenhouse_b
for mode in stalled normal; do
  cid=$(uuidgen)
  out=/tmp/smiot-w6-ack-$cid
  (timeout 12 mosquitto_sub -h localhost -t farm/demo/status -C 1 > "$out" 2>/dev/null || true) &
  sub=$!
  sleep 1
  mosquitto_pub -h localhost -t farm/demo/control -q 1 -m "{\"demo_detector_fault\":\"$mode\",\"farm_key\":\"$farm\",\"command_id\":\"$cid\",\"synthetic\":true}"
  wait $sub || true
  echo "mode=$mode"
  grep -F 'detector_fault_ack' "$out" || cat "$out"
  rm -f "$out"
done
'@
[IO.File]::WriteAllText($p, (@{commands=@('cd /opt/smiot', $cmd)} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$p --comment 'SMIOT W6 scoped synthetic injector ACK test' --query Command.CommandId --output text).Trim()
Write-Output "command=$id"
$deadline=(Get-Date).AddMinutes(2)
do { Start-Sleep 3; $r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json; if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){Write-Output "status=$($r.Status)"; Write-Output $r.StandardOutputContent; break} } while((Get-Date)-lt $deadline)
Remove-Item $p -Force -ErrorAction SilentlyContinue
