$ErrorActionPreference = 'Stop'
$remote = @'
set -u
cd /opt/smiot
export PYTHONPATH=/opt/smiot
PY=/opt/smiot/.venv/bin/python
BASE=/tmp/smiot-nine-cases-$(date -u +%Y%m%dT%H%M%SZ)
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
run_case W1 A2 greenhouse_d 2 101 &
run_case W2 soil_flatline greenhouse_a 2 102 &
run_case W3 H1 greenhouse_c 1 103 &
run_case W5 H2 greenhouse_e 1 105 &
run_case W6 H4 greenhouse_b 1 106 &
run_case W7 soil_spike greenhouse_f 2 107 &
run_case W8 soil_out_of_range greenhouse_g 1 108 &
run_case W9 A4 greenhouse_j 1 109 &
run_case W10 H6 greenhouse_h 1 110 &
wait
for f in "$BASE"/*.out; do echo "===== $(basename "$f") ====="; cat "$f"; done
'@
$payload = Join-Path $env:TEMP ('smiot-nine-' + [guid]::NewGuid().ToString('N') + '.json')
[IO.File]::WriteAllText($payload, (@{commands=@($remote)} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
try {
  $id = (aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payload --comment 'SMIOT nine isolated scenario correlation runs' --query Command.CommandId --output text).Trim()
  Write-Output "command=$id"
} finally { Remove-Item $payload -Force -ErrorAction SilentlyContinue }
