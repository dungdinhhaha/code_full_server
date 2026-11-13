<#
.SYNOPSIS
  Drill for Case 3 (smiot.service stopped, dependencies healthy), run from the operator machine.

.DESCRIPTION
  DEFAULT = dry run: only READ-ONLY checks (STS identity, SSM status, EC2/EBS snapshot age,
  systemctl is-active, HTTP status, newest MongoDB sample age through the root-owned readback helper).
  smiot.service is STOPPED only when -Confirm is given AND -DryRun is not given.
  After the stop the script polls (read-only) until the guarded recovery (Datadog workflow or an operator
  running the guarded SSM document) brings the app back, or until -MaxWaitSec expires.
  It never restarts EC2, MongoDB, Mosquitto or the Datadog Agent. It never reads secrets.
  Evidence (timestamps, step results, observations; no secrets) is written to outputs\drill_ca3_<utc>.json.

  The data is synthetic demo telemetry. A passing drill proves the guarded path worked for that run only.
  It does not prove any SLO.

.PARAMETER Confirm
  Required to actually stop smiot.service.
.PARAMETER DryRun
  Force dry run even when -Confirm is present.
.PARAMETER MonitorsOkAttested
  Operator attests that monitor 340356283 (and the others) are OK in Datadog. Required for a live run.
.PARAMETER MuteNoted
  Operator attests that the drill was announced / the right monitor was muted or annotated. Required for a live run.
.PARAMETER StartViaGuardIfNoRecovery
  Live only. If nothing restored the app within -MaxWaitSec, run the guarded script
  /usr/local/sbin/smiot-recover-guarded through SSM once (it keeps all of its own guards).

.EXAMPLE
  .\scripts\drill_ca3_service_down.ps1                       # dry run, read-only
.EXAMPLE
  .\scripts\drill_ca3_service_down.ps1 -Confirm -MonitorsOkAttested -MuteNoted -MaxWaitSec 420
#>
param(
    [switch]$Confirm,
    [switch]$DryRun,
    [switch]$MonitorsOkAttested,
    [switch]$MuteNoted,
    [switch]$StartViaGuardIfNoRecovery,
    [string]$Profile = "aws-moi",
    [string]$Region = "ap-southeast-2",
    [string]$InstanceId = "i-00bf2d3591d3ee0a2",
    [string]$ExpectedAccountId = "920235987407",
    [string]$Service = "smiot.service",
    [int]$MaxSnapshotAgeHours = 24,
    [int]$PollIntervalSec = 10,
    [int]$MaxWaitSec = 360,
    [int]$FreshSampleMaxAgeSec = 180,
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$ict = [TimeSpan]::FromHours(7)
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $OutputDir) { $OutputDir = Join-Path $projectRoot "outputs" }
$live = [bool]($Confirm -and -not $DryRun)
$drillStart = [DateTime]::UtcNow
$drillId = "DRILL-CA3-" + $drillStart.ToString("yyyyMMddTHHmmssZ")

function Get-Stamp {
    $u = [DateTime]::UtcNow
    $i = $u + $ict
    return [ordered]@{ utc = $u.ToString("yyyy-MM-ddTHH:mm:ss.fffZ"); ict = $i.ToString("yyyy-MM-ddTHH:mm:ss.fff") + "+07:00" }
}
function Write-Mark([string]$text) {
    $s = Get-Stamp
    Write-Output ("[{0} UTC | {1} ICT] {2}" -f $s.utc.Substring(0, 19), $s.ict.Substring(0, 19), $text)
}

$evidence = [ordered]@{
    schema         = "smiot.drill.ca3.v1"
    drill_id       = $drillId
    data_label     = "synthetic_demo_telemetry"
    mode           = $(if ($live) { "live" } else { "dry_run" })
    instance_id    = $InstanceId
    region         = $Region
    service        = $Service
    started        = Get-Stamp
    attestations   = [ordered]@{ monitors_ok = [bool]$MonitorsOkAttested; mute_or_annotation_noted = [bool]$MuteNoted; source = "operator_flag_not_verified_by_script" }
    steps          = @()
    observations   = @()
    marks          = [ordered]@{}
    datadog_fields_to_fill_manually = [ordered]@{ monitor_alert_time_utc = $null; workflow_execution_id = $null; bits_investigation_id = $null }
    result         = "not_finished"
    notes          = @("Script does not read Datadog; fill datadog_fields_to_fill_manually from the UI.", "No secret, URI or key is read or stored.")
}
function Add-Step([string]$name, [string]$status, [string]$detail) {
    $script:evidence.steps += [ordered]@{ name = $name; status = $status; detail = $detail; at = (Get-Stamp).utc }
    Write-Mark ("{0}: {1} - {2}" -f $name, $status, $detail)
}
function Save-Evidence {
    $script:evidence.finished = Get-Stamp
    if (-not (Test-Path -LiteralPath $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir | Out-Null }
    $path = Join-Path $OutputDir ("drill_ca3_" + $drillStart.ToString("yyyyMMddTHHmmssZ") + ".json")
    $json = $script:evidence | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($path, $json, [System.Text.UTF8Encoding]::new($false))
    Write-Mark "Evidence written: $path"
}

function Invoke-Aws {
    param([string[]]$CliArgs)
    $out = & aws --profile $Profile --region $Region @CliArgs
    if ($LASTEXITCODE -ne 0) { throw "aws $($CliArgs[0..1] -join ' ') failed (exit $LASTEXITCODE)" }
    return $out
}

# Run a shell command on the instance through SSM Run Command and return stdout (trimmed).
function Invoke-Ssm {
    param([string]$Command, [int]$TimeoutSec = 90)
    $tmp = Join-Path $env:TEMP ("smiot-drill-" + [guid]::NewGuid().ToString("N") + ".json")
    $payload = @{ commands = @($Command) } | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText($tmp, $payload, [System.Text.UTF8Encoding]::new($false))
    try {
        $id = (Invoke-Aws @("ssm", "send-command", "--instance-ids", $InstanceId,
                "--document-name", "AWS-RunShellScript", "--parameters", "file://$tmp",
                "--query", "Command.CommandId", "--output", "text")).Trim()
    } finally { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSec)
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Seconds 2
        $raw = & aws --profile $Profile --region $Region ssm get-command-invocation --command-id $id --instance-id $InstanceId --output json 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $raw) { continue }
        $inv = ($raw -join "`n") | ConvertFrom-Json
        if ($inv.Status -in @("Success", "Failed", "Cancelled", "TimedOut")) {
            return [pscustomobject]@{ Status = $inv.Status; Code = $inv.ResponseCode; Out = ([string]$inv.StandardOutputContent).Trim(); CommandId = $id }
        }
    }
    return [pscustomobject]@{ Status = "PollTimeout"; Code = -1; Out = ""; CommandId = $id }
}

# One read-only observation: unit states, HTTP code, newest sample age. No Environment/secret is printed.
$observeCmd = @'
echo "unit=$(systemctl is-active smiot.service 2>/dev/null)"
echo "mongod=$(systemctl is-active mongod.service 2>/dev/null)"
echo "mosquitto=$(systemctl is-active mosquitto.service 2>/dev/null)"
echo "http=$(curl -s -o /dev/null -m 4 -w '%{http_code}' http://127.0.0.1:8080/login 2>/dev/null)"
echo "latest_ms=$(sudo -n /usr/local/sbin/smiot-recovery-mongo-readback 2>/dev/null || /usr/local/sbin/smiot-recovery-mongo-readback 2>/dev/null)"
echo "now_ms=$(date +%s%3N)"
'@

function Get-Observation {
    $r = Invoke-Ssm -Command $observeCmd
    $o = [ordered]@{ at = (Get-Stamp).utc; ssm_status = $r.Status; unit = $null; mongod = $null; mosquitto = $null; http = $null; sample_age_sec = $null }
    foreach ($line in ($r.Out -split "`n")) {
        if ($line -match '^(unit|mongod|mosquitto|http)=(.*)$') { $o[$Matches[1]] = $Matches[2].Trim() }
    }
    $lat = $null; $now = $null
    foreach ($line in ($r.Out -split "`n")) {
        if ($line -match '^latest_ms=(\d+)') { $lat = [int64]$Matches[1] }
        if ($line -match '^now_ms=(\d+)') { $now = [int64]$Matches[1] }
    }
    if ($lat -and $now -and $lat -gt 0) { $o.sample_age_sec = [math]::Round(($now - $lat) / 1000.0, 1); $o.latest_sample_epoch_ms = $lat }
    return [pscustomobject]$o
}

try {
    Write-Mark ("{0} | mode={1} | synthetic demo data" -f $drillId, $evidence.mode)
    if (-not $live) { Write-Mark "DRY RUN: nothing will be stopped. Use -Confirm -MonitorsOkAttested -MuteNoted for the live drill." }

    # ---- Pre-checks (all read-only) ----
    $acct = (Invoke-Aws @("sts", "get-caller-identity", "--query", "Account", "--output", "text")).Trim()
    if ($acct -ne $ExpectedAccountId) { throw "AWS profile '$Profile' is not the expected account." }
    Add-Step "precheck.aws_identity" "pass" "account matches expected"

    $ssmState = (Invoke-Aws @("ssm", "describe-instance-information", "--filters", "Key=InstanceIds,Values=$InstanceId",
            "--query", "InstanceInformationList[0].PingStatus", "--output", "text")).Trim()
    if ($ssmState -ne "Online") { throw "SSM PingStatus is '$ssmState', expected Online." }
    Add-Step "precheck.ssm_online" "pass" "PingStatus=Online"

    $volId = (Invoke-Aws @("ec2", "describe-volumes", "--filters", "Name=attachment.instance-id,Values=$InstanceId",
            "--query", "Volumes[0].VolumeId", "--output", "text")).Trim()
    $snapRaw = (Invoke-Aws @("ec2", "describe-snapshots", "--owner-ids", "self", "--filters", "Name=volume-id,Values=$volId", "Name=status,Values=completed",
            "--query", "max_by(Snapshots,&StartTime).StartTime", "--output", "text")).Trim()
    $snapAgeH = $null
    if ($snapRaw -and $snapRaw -ne "None") {
        $snapAgeH = [math]::Round(([DateTime]::UtcNow - [DateTime]::Parse($snapRaw).ToUniversalTime()).TotalHours, 1)
    }
    $evidence.snapshot = [ordered]@{ volume_id = $volId; latest_completed_start = $snapRaw; age_hours = $snapAgeH; max_age_hours = $MaxSnapshotAgeHours }
    if ($null -eq $snapAgeH -or $snapAgeH -gt $MaxSnapshotAgeHours) {
        Add-Step "precheck.snapshot_fresh" "fail" "no completed snapshot within $MaxSnapshotAgeHours h (age=$snapAgeH). Take a snapshot first."
        if ($live) { throw "Snapshot too old; refusing live drill." }
    } else { Add-Step "precheck.snapshot_fresh" "pass" "age_hours=$snapAgeH" }

    $base = Get-Observation
    $evidence.baseline_observation = $base
    $okBase = ($base.unit -eq "active") -and ($base.http -eq "200") -and ($base.mongod -eq "active") -and ($base.mosquitto -eq "active")
    $freshBase = ($null -ne $base.sample_age_sec) -and ($base.sample_age_sec -le $FreshSampleMaxAgeSec)
    Add-Step "precheck.app_and_dependencies" $(if ($okBase) { "pass" } else { "fail" }) ("unit={0} mongod={1} mosquitto={2} http={3}" -f $base.unit, $base.mongod, $base.mosquitto, $base.http)
    Add-Step "precheck.fresh_mongo_sample" $(if ($freshBase) { "pass" } else { "fail" }) ("sample_age_sec={0}" -f $base.sample_age_sec)
    if ($live -and -not ($okBase -and $freshBase)) { throw "Baseline is not healthy; refusing live drill." }

    Add-Step "precheck.monitor_status" $(if ($MonitorsOkAttested) { "attested" } else { "not_attested" }) "Datadog monitor state is NOT read by this script; operator must confirm monitors are OK."
    if ($live -and -not ($MonitorsOkAttested -and $MuteNoted)) { throw "Live run needs -MonitorsOkAttested and -MuteNoted." }

    if (-not $live) {
        $evidence.result = "dry_run_completed"
        Add-Step "stop_service" "skipped" "dry run (no -Confirm, or -DryRun given)"
        Save-Evidence
        return
    }

    # ---- Live: stop only the app service ----
    $evidence.marks.t0_precheck_done = Get-Stamp
    Write-Mark "T0: about to stop $Service. Emergency stop of the drill: run 'systemctl start $Service' via the guarded SSM document or sudo on the host."
    $stop = Invoke-Ssm -Command "systemctl stop $Service; echo stopped_rc=`$?"
    $evidence.marks.t1_stop_issued = Get-Stamp
    Add-Step "stop_service" $(if ($stop.Status -eq "Success") { "done" } else { "error" }) ("ssm_status={0} command_id={1}" -f $stop.Status, $stop.CommandId)

    # ---- Poll (read-only) until recovery or timeout ----
    $deadline = [DateTime]::UtcNow.AddSeconds($MaxWaitSec)
    $downSeen = $false; $recovered = $false
    $baselineMs = $base.latest_sample_epoch_ms
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Seconds $PollIntervalSec
        $ob = Get-Observation
        $evidence.observations += $ob
        Write-Mark ("poll unit={0} http={1} sample_age_sec={2}" -f $ob.unit, $ob.http, $ob.sample_age_sec)
        if ($ob.unit -ne "active" -and -not $downSeen) { $downSeen = $true; $evidence.marks.t2_down_observed = Get-Stamp }
        $newer = ($null -ne $ob.latest_sample_epoch_ms) -and ($null -ne $baselineMs) -and ($ob.latest_sample_epoch_ms -gt $baselineMs)
        $fresh = ($null -ne $ob.sample_age_sec) -and ($ob.sample_age_sec -le $FreshSampleMaxAgeSec)
        if ($downSeen -and $ob.unit -eq "active" -and $ob.http -eq "200" -and $newer -and $fresh) {
            $recovered = $true
            $evidence.marks.t3_recovery_verified = Get-Stamp
            break
        }
    }

    if (-not $recovered -and $StartViaGuardIfNoRecovery) {
        Write-Mark "No recovery within $MaxWaitSec s; running the guarded script once (it keeps its own guards)."
        $g = Invoke-Ssm -Command "/usr/local/sbin/smiot-recover-guarded" -TimeoutSec 240
        $evidence.marks.t_guard_manual_run = Get-Stamp
        $lastLine = ($g.Out -split "`n" | Select-Object -Last 1)
        Add-Step "manual_guarded_start" $g.Status ("exit={0} last_record={1}" -f $g.Code, $lastLine)
        $ob = Get-Observation
        $evidence.observations += $ob
        $newer = ($null -ne $ob.latest_sample_epoch_ms) -and ($null -ne $baselineMs) -and ($ob.latest_sample_epoch_ms -gt $baselineMs)
        if ($ob.unit -eq "active" -and $ob.http -eq "200" -and $newer) { $recovered = $true; $evidence.marks.t3_recovery_verified = Get-Stamp }
    }

    if ($recovered) {
        $evidence.result = "recovered_verified_http_and_new_mongo_sample"
        Add-Step "recovery_check" "pass" "unit active, HTTP 200, newer Mongo sample within $FreshSampleMaxAgeSec s"
    } else {
        $evidence.result = "not_recovered_within_wait"
        Add-Step "recovery_check" "fail" "not verified within $MaxWaitSec s. Do NOT assume recovery; start the guarded SSM document or check manually."
    }
    if ($evidence.marks.Contains("t1_stop_issued") -and $evidence.marks.Contains("t3_recovery_verified")) {
        $t1 = [DateTime]::Parse($evidence.marks.t1_stop_issued.utc).ToUniversalTime()
        $t3 = [DateTime]::Parse($evidence.marks.t3_recovery_verified.utc).ToUniversalTime()
        $evidence.stop_to_verified_seconds = [math]::Round(($t3 - $t1).TotalSeconds, 0)
    }
    Save-Evidence
}
catch {
    $evidence.result = "aborted"
    Add-Step "abort" "error" $_.Exception.Message
    Save-Evidence
    throw
}
