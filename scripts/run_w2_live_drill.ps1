param(
  [string]$Profile = 'aws-moi',
  [string]$Region = 'ap-southeast-2',
  [string]$InstanceId = 'i-00bf2d3591d3ee0a2',
  [ValidateRange(330,1800)][int]$HoldSeconds = 420,
  [ValidateRange(330,1800)][int]$RecoveryWaitSeconds = 420,
  [string]$EvidencePath = ''
)

# Live W2 drill runner. It is intentionally not invoked by this implementation
# task. The app creates the canonical incident ID; every mode ACK and matching
# sample must carry that ID. Cleanup always attempts to return the publisher to
# normal, even when the SSM call, wait, or evidence parsing fails.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$faultHelper = Join-Path $PSScriptRoot 'set_demo_sensor_fault.py'
if (-not $EvidencePath) {
  $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
  $EvidencePath = Join-Path $root "outputs/evidence/w2_live_drill_$stamp.json"
}
$drillRunId = [guid]::NewGuid().ToString('D')
$startedAtUtc = [DateTime]::UtcNow
$incidentId = $null
$flatlineResult = $null
$normalResult = $null
$normalApplied = $false
$flatlineCommandId = $null
$normalCommandId = $null

function Invoke-Ssm([string]$Command, [int]$WaitSeconds = 120) {
  $requestFile = Join-Path $env:TEMP ('smiot-w2-live-' + [guid]::NewGuid().ToString('N') + '.json')
  [IO.File]::WriteAllText($requestFile, (@{commands=@($Command)} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
  try {
    $commandId = (aws ssm send-command --profile $Profile --region $Region --instance-ids $InstanceId `
      --document-name AWS-RunShellScript --parameters "file://$requestFile" `
      --comment "SMIOT W2 bounded drill $drillRunId" --query Command.CommandId --output text).Trim()
    if (-not $commandId -or $commandId -eq 'None') { throw 'SSM did not return a command ID.' }
    $deadline = [DateTime]::UtcNow.AddSeconds($WaitSeconds)
    do {
      Start-Sleep -Seconds 3
      $result = aws ssm get-command-invocation --profile $Profile --region $Region --command-id $commandId `
        --instance-id $InstanceId --output json | ConvertFrom-Json
      if ($result.Status -in @('Success','Failed','Cancelled','TimedOut')) {
        if ($result.Status -ne 'Success') {
          throw "SSM command $commandId ended $($result.Status). stderr_present=$([bool]$result.StandardErrorContent)"
        }
        return [pscustomobject]@{ CommandId=$commandId; Status=$result.Status; Output=[string]$result.StandardOutputContent }
      }
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "SSM command $commandId did not finish within $WaitSeconds seconds."
  } finally {
    Remove-Item -LiteralPath $requestFile -Force -ErrorAction SilentlyContinue
  }
}

function Read-ModeResult([string]$Output) {
  $jsonLine = @($Output -split "`r?`n" | Where-Object { $_.Trim().StartsWith('{') -and $_.Trim().EndsWith('}') } | Select-Object -Last 1)
  if (-not $jsonLine) { throw 'Mode helper did not return its correlated JSON result.' }
  return ($jsonLine[0] | ConvertFrom-Json)
}

function Invoke-Mode([ValidateSet('flatline','normal')][string]$Mode, [string]$CorrelatedIncidentId = '') {
  if ($CorrelatedIncidentId -and $CorrelatedIncidentId -notmatch '^INC-SMIOT-[A-Za-z0-9-]+$') {
    throw 'Incident ID format is invalid; refusing to send the mode command.'
  }
  $archive = Join-Path $env:TEMP ('smiot-w2-helper-' + [guid]::NewGuid().ToString('N') + '.tgz')
  $stageDir = Join-Path $env:TEMP ('smiot-w2-helper-' + [guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Path $stageDir | Out-Null
  try {
    Copy-Item -LiteralPath $faultHelper -Destination (Join-Path $stageDir 'set_demo_sensor_fault.py')
    tar -czf $archive -C $stageDir set_demo_sensor_fault.py
    if ($LASTEXITCODE -ne 0) { throw 'Could not package the W2 mode helper.' }
    $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($archive))
    $incidentArg = if ($CorrelatedIncidentId) { "--incident-id $CorrelatedIncidentId" } else { '' }
    $remote = @(
      'set -e',
      "printf '%s' '$b64' | base64 -d > /tmp/smiot-w2-helper.tgz",
      'tar -xzf /tmp/smiot-w2-helper.tgz -C /tmp',
      'cd /opt/smiot',
      'export PYTHONPATH=/opt/smiot',
      "/opt/smiot/.venv/bin/python /tmp/set_demo_sensor_fault.py $Mode --host 127.0.0.1 --port 1883 $incidentArg",
      'rm -f /tmp/smiot-w2-helper.tgz /tmp/set_demo_sensor_fault.py'
    ) -join '; '
    $response = Invoke-Ssm $remote 120
    return [pscustomobject]@{ CommandId=$response.CommandId; Status=$response.Status; Result=(Read-ModeResult $response.Output) }
  } finally {
    Remove-Item -LiteralPath $archive,$stageDir -Recurse -Force -ErrorAction SilentlyContinue
  }
}

try {
  $identity = aws sts get-caller-identity --profile $Profile --region $Region --output json | ConvertFrom-Json
  if (-not $identity.Account) { throw 'AWS identity preflight returned no account.' }
  $monitorBefore = python (Join-Path $PSScriptRoot 'read_w2_datadog_state.py') | ConvertFrom-Json
  if ($monitorBefore.overall_state -ne 'OK') { throw "W2 monitor baseline is $($monitorBefore.overall_state), not OK." }

  $flatlineResult = Invoke-Mode 'flatline'
  $flatlineCommandId = $flatlineResult.CommandId
  if ($flatlineResult.Result.mode -ne 'flatline' -or $flatlineResult.Result.ack.applied -ne $true) {
    throw 'Publisher did not ACK the requested flatline mode.'
  }
  $incidentId = [string]$flatlineResult.Result.incident_id
  if (-not $incidentId -or [string]$flatlineResult.Result.first_sample.incident_id -ne $incidentId) {
    throw 'Flatline ACK and first sample do not share the canonical incident ID.'
  }

  Start-Sleep -Seconds $HoldSeconds
  $monitorAlert = python (Join-Path $PSScriptRoot 'read_w2_datadog_state.py') | ConvertFrom-Json
  if ($monitorAlert.overall_state -ne 'Alert') { throw "W2 monitor did not Alert during the held fault; state=$($monitorAlert.overall_state)." }

  $normalResult = Invoke-Mode 'normal' $incidentId
  $normalCommandId = $normalResult.CommandId
  if (($normalResult.Result.mode -ne 'normal') -or
      ($normalResult.Result.ack.applied -ne $true) -or
      ([string]$normalResult.Result.incident_id -ne $incidentId) -or
      ([string]$normalResult.Result.first_sample.incident_id -ne $incidentId)) {
    throw 'Normal ACK/sample is not correlated to the W2 incident.'
  }
  $normalApplied = $true
  Start-Sleep -Seconds $RecoveryWaitSeconds

  $monitorRead = python (Join-Path $PSScriptRoot 'read_w2_datadog_state.py') | ConvertFrom-Json
  if ($monitorRead.overall_state -ne 'OK') { throw "W2 monitor did not return to OK; state=$($monitorRead.overall_state)." }
  $record = [ordered]@{
    schema_version = 1
    workflow = 'W2'
    drill_run_id = $drillRunId
    incident_id = $incidentId
    farm = 'greenhouse_a'
    node = 2
    synthetic = $true
    started_at_utc = $startedAtUtc.ToString('o')
    completed_at_utc = [DateTime]::UtcNow.ToString('o')
    hold_seconds = $HoldSeconds
    recovery_wait_seconds = $RecoveryWaitSeconds
    region = $Region
    instance_id = $InstanceId
    flatline = [ordered]@{
      ssm_command_id = $flatlineCommandId
      status = $flatlineResult.Status
      mode_ack = $flatlineResult.Result.ack
      first_sample = $flatlineResult.Result.first_sample
    }
    normal = [ordered]@{
      ssm_command_id = $normalCommandId
      status = $normalResult.Status
      mode_ack = $normalResult.Result.ack
      first_sample = $normalResult.Result.first_sample
    }
    monitor_before = $monitorBefore
    monitor_during_fault = $monitorAlert
    monitor_readback = $monitorRead
    workflow_run_readback = 'must be added by the operator/reviewer from the exact monitor-triggered instance'
    mongo_persistence_readback = 'must be added from incident verifier/evidence; mode ACK alone does not prove Mongo persistence or CLEAR'
    actuator_called = $false
  }
  $parent = Split-Path -Parent $EvidencePath
  New-Item -ItemType Directory -Path $parent -Force | Out-Null
  [IO.File]::WriteAllText($EvidencePath, ($record | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
  Write-Output "evidence=$EvidencePath"
  Write-Output "incident_id=$incidentId"
  Write-Output "monitor_state=$($monitorRead.overall_state)"
} finally {
  if (-not $normalApplied) {
    try {
      $cleanup = Invoke-Mode 'normal' $incidentId
      Write-Warning "Safety cleanup reset publisher to normal; command=$($cleanup.CommandId)"
    } catch {
      Write-Error "CRITICAL: unable to confirm W2 publisher reset. Error type: $($_.Exception.GetType().Name)"
    }
  }
}
