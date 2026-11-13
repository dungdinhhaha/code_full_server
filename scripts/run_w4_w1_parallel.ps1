$ErrorActionPreference = 'Stop'
$payloadPath = Join-Path $env:TEMP ('smiot-w4-w1-' + [guid]::NewGuid().ToString('N') + '.json')
$remote = @'
set -u
cd /opt/smiot
PY=/opt/smiot/.venv/bin/python
export PYTHONPATH=/opt/smiot
OUT4=/tmp/smiot-w4-$(date +%s).out
OUT1=/tmp/smiot-w1-$(date +%s).out
($PY scripts/demo_scenario.py start D2 --farm greenhouse_c --node 1 --seed 17 --timeout 90 > "$OUT4" 2>&1) & P4=$!
($PY scripts/demo_scenario.py start A2 --farm greenhouse_d --node 2 --seed 19 --timeout 90 > "$OUT1" 2>&1) & P1=$!
wait $P4 || true
wait $P1 || true
echo '---W4---'; cat "$OUT4"
echo '---W1---'; cat "$OUT1"
RUN4=$(grep -oE '"scenario_run_id"[[:space:]]*:[[:space:]]*"[^"]+"' "$OUT4" | head -1 | sed -E 's/.*"([^"]+)"/\1/' || true)
RUN1=$(grep -oE '"scenario_run_id"[[:space:]]*:[[:space:]]*"[^"]+"' "$OUT1" | head -1 | sed -E 's/.*"([^"]+)"/\1/' || true)
if [ -n "$RUN4" ]; then echo "---W4 STOP---"; $PY scripts/demo_scenario.py stop --run-id "$RUN4" --farm greenhouse_c --timeout 30 || true; fi
if [ -n "$RUN1" ]; then echo "---W1 STOP---"; $PY scripts/demo_scenario.py stop --run-id "$RUN1" --farm greenhouse_d --timeout 30 || true; fi
rm -f "$OUT4" "$OUT1"
'@
[IO.File]::WriteAllText($payloadPath, (@{commands=@('cd /opt/smiot', $remote)} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
$id = (aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payloadPath --comment 'SMIOT W4 W1 parallel live drill' --query Command.CommandId --output text).Trim()
Write-Output "command=$id"
do {
    Start-Sleep 10
    $result = aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json | ConvertFrom-Json
    Write-Output "status=$($result.Status)"
    if ($result.StandardOutputContent) { Write-Output $result.StandardOutputContent }
    if ($result.Status -in @('Success','Failed','Cancelled','TimedOut')) {
        if ($result.StandardErrorContent) { Write-Output "stderr=$($result.StandardErrorContent)" }
        break
    }
} while ($true)
Remove-Item $payloadPath -Force -ErrorAction SilentlyContinue
