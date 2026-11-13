<#
.SYNOPSIS
  Local-only orchestration rehearsal for parallel W2 and W6 lanes.

.DESCRIPTION
  Generates synthetic step logs in two isolated local PowerShell jobs, each
  with its own farm, incident_id and scenario_run_id. It does not inject faults
  into a simulator or application and contains no AWS, Datadog, HTTP, MQTT or
  database calls. Evidence is written under outputs/drill_parallel_w2_w6_<utc>.json.
#>
[CmdletBinding()]
param(
    [ValidateRange(5, 600)]
    [int]$TimeoutSec = 45,
    [string]$OutputDir = ''
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $OutputDir) { $OutputDir = Join-Path $root 'outputs' }
$started = [DateTime]::UtcNow
$stamp = $started.ToString('yyyyMMddTHHmmssZ')
$evidencePath = Join-Path $OutputDir "drill_parallel_w2_w6_${stamp}_$([guid]::NewGuid().ToString('N').Substring(0,8)).json"
$lanes = @(
    [ordered]@{ workflow = 'W2'; farm_id = 'drill_w2_local'; resource_id = 'node_2' },
    [ordered]@{ workflow = 'W6'; farm_id = 'drill_w6_local'; resource_id = 'agronomic_advisory' }
)
$incidentIds = @{ W2 = 'INC-W2-' + [guid]::NewGuid().ToString('D'); W6 = 'INC-W6-' + [guid]::NewGuid().ToString('D') }
$runIds = @{ W2 = [guid]::NewGuid().ToString('D'); W6 = [guid]::NewGuid().ToString('D') }
$evidence = [ordered]@{
    schema = 'smiot.parallel_drill.w2_w6.v1'
    mode = 'local_simulation_only'
    started_at_utc = $started.ToString('o')
    finished_at_utc = $null
    timeout_seconds = $TimeoutSec
    preflight = [ordered]@{ passed = $false; checks = @(); external_io = $false; live_fault = $false; deploy = $false; datadog_write = $false }
    lanes = @()
    cleanup = [ordered]@{ attempted = $false; jobs_stopped = $false; detail = 'pending' }
    result = 'not_started'
    evidence_file = $evidencePath
}
$jobs = @()

try {
    if (-not (Test-Path -LiteralPath $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    }
    if (-not (Test-Path -LiteralPath $OutputDir -PathType Container)) { throw 'OutputDir is not a directory.' }
    if ($lanes[0].farm_id -eq $lanes[1].farm_id) { throw 'W2 and W6 farm scopes must be distinct.' }
    if ($incidentIds.W2 -eq $incidentIds.W6 -or $runIds.W2 -eq $runIds.W6) { throw 'Lane correlation IDs must be distinct.' }
    $evidence.preflight.checks = @(
        'output_directory_available', 'distinct_local_farm_scopes', 'distinct_incident_ids',
        'distinct_scenario_run_ids', 'no_external_integrations_configured'
    )
    $evidence.preflight.passed = $true

    # These jobs produce synthetic records only; they do not invoke project scripts.
    foreach ($lane in $lanes) {
        $workflow = [string]$lane.workflow
        $farmId = [string]$lane.farm_id
        $resourceId = [string]$lane.resource_id
        $incidentId = [string]$incidentIds[$workflow]
        $runId = [string]$runIds[$workflow]
        $jobs += Start-Job -Name "parallel-drill-$workflow" -ArgumentList $workflow, $farmId, $resourceId, $incidentId, $runId -ScriptBlock {
            param($Workflow, $FarmId, $ResourceId, $IncidentId, $RunId)
            function UtcNow { [DateTime]::UtcNow.ToString('o') }
            $events = @()
            $events += [ordered]@{ step = 'preflight'; status = 'pass'; at_utc = (UtcNow); detail = 'local scope and unique correlation IDs confirmed' }
            if ($Workflow -eq 'W2') {
                $events += [ordered]@{ step = 'synthetic_flatline_observed'; status = 'simulated'; at_utc = (UtcNow); detail = 'fixture event only; no sensor or simulator changed' }
                $events += [ordered]@{ step = 'synthetic_recovery_samples'; status = 'simulated'; at_utc = (UtcNow); detail = 'fixture contains increasing sequence and variation markers; no MongoDB write' }
                $events += [ordered]@{ step = 'clear_gate'; status = 'pending_external_evidence'; at_utc = (UtcNow); detail = 'live ACK, persisted samples, monitor and app verifier are not asserted by this local rehearsal' }
            } else {
                $events += [ordered]@{ step = 'evaluation_heartbeat_missing'; status = 'simulated'; at_utc = (UtcNow); detail = 'fixture event only; detector and metric stream unchanged' }
                $events += [ordered]@{ step = 'evaluation_heartbeat_restored'; status = 'simulated'; at_utc = (UtcNow); detail = 'fixture event only; no Datadog metric submitted' }
                $events += [ordered]@{ step = 'recovery_gate'; status = 'pending_external_evidence'; at_utc = (UtcNow); detail = 'live target-farm monitor OK, workflow and app CLEAR are not asserted' }
            }
            [pscustomobject]@{
                workflow = $Workflow; farm_id = $FarmId; resource_id = $ResourceId
                incident_id = $IncidentId; scenario_run_id = $RunId
                synthetic = $true; events = @($events); result = 'local_rehearsal_only'
            }
        }
    }

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSec)
    $remaining = [math]::Max(0, ($deadline - [DateTime]::UtcNow).TotalSeconds)
    $null = Wait-Job -Job $jobs -Timeout $remaining
    foreach ($job in $jobs) {
        if ($job.State -eq 'Completed') {
            $records = @(Receive-Job -Job $job -ErrorAction Stop)
            if ($records.Count -eq 1) { $evidence.lanes += $records[0] }
            else { $evidence.lanes += [ordered]@{ workflow = $job.Name; result = 'invalid_job_output'; events = @() } }
        } else {
            $evidence.lanes += [ordered]@{ workflow = $job.Name; result = 'timeout'; events = @() }
        }
    }
    if (@($evidence.lanes | Where-Object { $_.result -eq 'local_rehearsal_only' }).Count -eq 2) {
        $evidence.result = 'local_parallel_rehearsal_completed_external_acceptance_pending'
    } else {
        $evidence.result = 'local_parallel_rehearsal_timeout_or_error'
    }
}
catch {
    $evidence.result = 'aborted'
    $evidence.error = $_.Exception.Message
}
finally {
    $evidence.cleanup.attempted = $true
    $cleanupOk = $true
    foreach ($job in $jobs) {
        try {
            if ($job.State -notin @('Completed', 'Failed', 'Stopped')) { Stop-Job -Job $job -ErrorAction Stop }
            Remove-Job -Job $job -Force -ErrorAction Stop
        } catch { $cleanupOk = $false }
    }
    $evidence.cleanup.jobs_stopped = $cleanupOk
    $evidence.cleanup.detail = if ($cleanupOk) { 'all local rehearsal jobs stopped or completed and removed' } else { 'one or more local rehearsal jobs could not be confirmed removed' }
    if (-not $cleanupOk) { $evidence.result = 'cleanup_incomplete' }
    $evidence.finished_at_utc = [DateTime]::UtcNow.ToString('o')
    $json = $evidence | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($evidencePath, $json, [System.Text.UTF8Encoding]::new($false))
}

Write-Output "result=$($evidence.result)"
Write-Output "evidence=$evidencePath"
if ($evidence.result -in @('aborted','cleanup_incomplete') -or $evidence.result -like '*timeout*') { exit 1 }
