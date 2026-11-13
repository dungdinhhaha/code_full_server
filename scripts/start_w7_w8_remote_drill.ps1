param(
  [ValidateSet('w7','w8','normal')][string]$Mode,
  [int]$Seconds = 180,
  [string]$Farm = 'greenhouse_j',
  [int]$Node = 1
)
$ErrorActionPreference='Stop'
$profile='aws-moi'; $region='ap-southeast-2'; $instance='i-00bf2d3591d3ee0a2'
$remote="nohup /usr/bin/python3 /opt/smiot/scripts/emit_w7_w8_advisory_metrics.py --mode $Mode --farm $Farm --node $Node --seconds $Seconds --interval 10 >/tmp/smiot-$Mode-demo.log 2>&1 & echo started"
$tmp=Join-Path $env:TEMP ('w7w8-start-'+[guid]::NewGuid().ToString('N')+'.json')
[IO.File]::WriteAllText($tmp, (@{commands=@($remote)}|ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
try { aws ssm send-command --profile $profile --region $region --instance-ids $instance --document-name AWS-RunShellScript --parameters file://$tmp --comment "SMIOT $Mode bounded advisory drill" --output json }
finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
