$ErrorActionPreference='Stop'
$profile='aws-moi'; $region='ap-southeast-2'; $instance='i-00bf2d3591d3ee0a2'
$files=@('service/datadog_metrics.py','scripts/emit_w7_w8_advisory_metrics.py')
$parts=@()
foreach($f in $files){
  $bytes=[IO.File]::ReadAllBytes((Join-Path 'D:\IOT Trung\code_full_server' $f)); $b64=[Convert]::ToBase64String($bytes)
  $remote='/opt/smiot/'+$f
  $dir=Split-Path $remote
  $parts += "install -d -m 0755 $dir; echo $b64 | base64 -d > $remote; chmod 0644 $remote"
}
$parts += "systemctl is-active --quiet smiot.service"
$cmd=($parts -join '; ')
$tmp=Join-Path $env:TEMP ('smiot-w7-w8-'+[guid]::NewGuid().ToString('N')+'.json')
[IO.File]::WriteAllText($tmp, (@{commands=@($cmd)}|ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
try {
  $id=(aws ssm send-command --profile $profile --region $region --instance-ids $instance --document-name AWS-RunShellScript --parameters file://$tmp --comment 'SMIOT W7/W8 advisory metrics update' --query Command.CommandId --output text).Trim()
  Start-Sleep 5
  aws ssm get-command-invocation --profile $profile --region $region --command-id $id --instance-id $instance --output json
}
finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
