$ErrorActionPreference='Stop'
$profile='aws-moi'; $region='ap-southeast-2'; $instance='i-00bf2d3591d3ee0a2'
$files=@('scripts/emit_w9_w10_synthetic_metrics.py','scripts/emit_w5_dependency_metrics.py')
$parts=@()
foreach($f in $files){
  $bytes=[IO.File]::ReadAllBytes((Join-Path 'D:\IOT Trung\code_full_server' $f)); $b64=[Convert]::ToBase64String($bytes)
  $remote='/opt/smiot/'+$f.Replace('/','/')
  $parts += "echo $b64 | base64 -d > $remote"
}
$cmd=($parts -join '; ')
$tmp=Join-Path $env:TEMP ('smiot-deploy-'+[guid]::NewGuid().ToString('N')+'.json')
[IO.File]::WriteAllText($tmp, (@{commands=@($cmd)}|ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
try { $id=(aws ssm send-command --profile $profile --region $region --instance-ids $instance --document-name AWS-RunShellScript --parameters file://$tmp --comment 'SMIOT W9/W5 synthetic emitter update' --query Command.CommandId --output text).Trim(); Start-Sleep 6; aws ssm get-command-invocation --profile $profile --region $region --command-id $id --instance-id $instance --output json }
finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
