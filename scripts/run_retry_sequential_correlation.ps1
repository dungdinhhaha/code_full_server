$ErrorActionPreference = 'Stop'
$remote = @'
set -u
cd /opt/smiot
export PYTHONPATH=/opt/smiot
PY=/opt/smiot/.venv/bin/python
BASE=/tmp/smiot-retry-cases-$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$BASE"
run_case(){
  local name="$1" scenario="$2" farm="$3" node="$4" seed="$5"
  local out="$BASE/$name.out"
  echo "[$name] start" > "$out"
  timeout 150 "$PY" scripts/demo_scenario.py start "$scenario" --farm "$farm" --node "$node" --seed "$seed" --timeout 90 >> "$out" 2>&1 || true
  local run
  run=$(grep -oE '"scenario_run_id"[[:space:]]*:[[:space:]]*"[^"]+"' "$out" | head -1 | sed -E 's/.*"([^"]+)"/\1/' || true)
  if [ -n "$run" ]; then
    echo "[$name] run=$run" >> "$out"
    "$PY" scripts/demo_scenario.py stop --run-id "$run" --farm "$farm" --timeout 30 >> "$out" 2>&1 || true
  else
    echo "[$name] run_missing" >> "$out"
  fi
  echo "[$name] end" >> "$out"
}
run_case W3 H1 greenhouse_c 1 203
run_case W5 H2 greenhouse_e 1 205
run_case W6 H4 greenhouse_b 1 206
run_case W9 A4 greenhouse_j 1 209
run_case W10 H6 greenhouse_h 1 210
for f in "$BASE"/*.out; do echo "===== $(basename "$f") ====="; cat "$f"; done
'@
$payload = Join-Path $env:TEMP ('smiot-retry-' + [guid]::NewGuid().ToString('N') + '.json')
[IO.File]::WriteAllText($payload, (@{commands=@($remote)} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
try {
  $id = (aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payload --comment 'SMIOT retry sequential correlation cases' --query Command.CommandId --output text).Trim()
  Write-Output "command=$id"
} finally { Remove-Item $payload -Force -ErrorAction SilentlyContinue }
