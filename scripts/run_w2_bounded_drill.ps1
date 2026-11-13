param([int]$HoldSeconds = 720)
$ErrorActionPreference = 'Stop'
$profile = 'aws-moi'; $region = 'ap-southeast-2'; $instance = 'i-00bf2d3591d3ee0a2'
function Invoke-Ssm([string]$command, [int]$wait = 180) {
  $p = Join-Path $env:TEMP ('smiot-w2-drill-' + [guid]::NewGuid().ToString('N') + '.json')
  [IO.File]::WriteAllText($p, (@{commands=@($command)} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
  try {
    $id = (aws ssm send-command --profile $profile --region $region --instance-ids $instance --document-name AWS-RunShellScript --parameters file://$p --comment 'SMIOT bounded W2 drill' --query Command.CommandId --output text).Trim()
    $deadline = (Get-Date).AddSeconds($wait)
    do {
      Start-Sleep -Seconds 3
      $r = aws ssm get-command-invocation --profile $profile --region $region --command-id $id --instance-id $instance --output json | ConvertFrom-Json
      if ($r.Status -in @('Success','Failed','Cancelled','TimedOut')) { return [pscustomobject]@{Id=$id;Status=$r.Status;Out=[string]$r.StandardOutputContent;Err=[string]$r.StandardErrorContent} }
    } while ((Get-Date) -lt $deadline)
    return [pscustomobject]@{Id=$id;Status='PollTimeout';Out='';Err=''}
  } finally { Remove-Item $p -Force -ErrorAction SilentlyContinue }
}
if ($HoldSeconds -lt 330) { throw 'HoldSeconds must exceed the five-minute monitor window and allow flatline detection.' }
$start = @'
set -u
cd /opt/smiot
export PYTHONPATH=/opt/smiot
/opt/smiot/.venv/bin/python /opt/smiot/scripts/demo_scenario.py start soil_flatline --farm greenhouse_a --node 2 --seed 42 --timeout 90
'@
$s = Invoke-Ssm $start 150
Write-Output "start_command=$($s.Id) status=$($s.Status)"
Write-Output $s.Out
$runId = $null
if ($s.Out -match '"scenario_run_id"\s*:\s*"([^"]+)"') { $runId = $Matches[1] }
if ($s.Status -ne 'Success' -or -not $runId) {
  throw 'W2 scenario did not return a successful start ACK and scenario_run_id; refusing to claim a live drill.'
}
try {
  Write-Output "hold_started_utc=$([DateTime]::UtcNow.ToString('o')) hold_seconds=$HoldSeconds scenario_run_id=$runId"
  Start-Sleep -Seconds $HoldSeconds
} finally {
  $stop = Invoke-Ssm "cd /opt/smiot && export PYTHONPATH=/opt/smiot && /opt/smiot/.venv/bin/python /opt/smiot/scripts/demo_scenario.py stop --run-id $runId --farm greenhouse_a --timeout 30" 60
  Write-Output "stop_command=$($stop.Id) status=$($stop.Status) scenario_run_id=$runId"
  Write-Output $stop.Out
  if ($stop.Status -ne 'Success') { throw 'W2 cleanup stop did not succeed; inspect the scenario state before proceeding.' }
}
