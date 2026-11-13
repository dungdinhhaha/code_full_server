$ErrorActionPreference = 'Stop'
$root = 'D:\IOT Trung\code_full_server'
$files = @('pages\incident.py', 'service\incident_blackbox.py', 'service\mqtt.py')
$parts = foreach ($relative in $files) {
    $local = Join-Path $root $relative
    $remote = '/opt/smiot/' + ($relative -replace '\\','/')
    $input = [IO.File]::ReadAllBytes($local)
    $inStream = [IO.MemoryStream]::new($input)
    $outStream = [IO.MemoryStream]::new()
    $gzip = [IO.Compression.GzipStream]::new($outStream, [IO.Compression.CompressionMode]::Compress)
    $inStream.CopyTo($gzip); $gzip.Dispose(); $inStream.Dispose()
    $b64 = [Convert]::ToBase64String($outStream.ToArray()); $outStream.Dispose()
    "echo $b64 | base64 -d | gzip -d > $remote"
}
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$cmd = @(
    "set -e",
    "mkdir -p /opt/smiot-rollback/evidence-labels-$stamp",
    "cp /opt/smiot/pages/incident.py /opt/smiot-rollback/evidence-labels-$stamp/incident.py",
    "cp /opt/smiot/service/incident_blackbox.py /opt/smiot-rollback/evidence-labels-$stamp/incident_blackbox.py",
    "cp /opt/smiot/service/mqtt.py /opt/smiot-rollback/evidence-labels-$stamp/mqtt.py"
) + $parts + @(
    "chown smiot:smiot /opt/smiot/pages/incident.py /opt/smiot/service/incident_blackbox.py",
    "systemctl restart smiot.service",
    "sleep 3",
    "systemctl is-active --quiet smiot.service",
    "curl -fsS http://127.0.0.1:8080/healthz"
)
$payload = Join-Path $env:TEMP 'deploy-incident-evidence-labels.json'
[IO.File]::WriteAllText($payload, (@{commands=$cmd} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
try {
    $id = (aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payload --comment 'SMIOT exact incident evidence display and node normalization' --query Command.CommandId --output text).Trim()
    Write-Output "command=$id"
    do {
        Start-Sleep 4
        $r = aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json | ConvertFrom-Json
        if ($r.Status -in @('Success','Failed','Cancelled','TimedOut')) {
            Write-Output "status=$($r.Status)"
            if ($r.StandardOutputContent) { Write-Output $r.StandardOutputContent }
            if ($r.StandardErrorContent) { Write-Output "stderr=$($r.StandardErrorContent)" }
            if ($r.Status -ne 'Success') { throw "SSM deployment failed: $($r.Status)" }
            break
        }
    } while ($true)
} finally {
    Remove-Item $payload -Force -ErrorAction SilentlyContinue
}
