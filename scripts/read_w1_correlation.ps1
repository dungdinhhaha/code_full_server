$ErrorActionPreference='Stop'
$run='565ab740-e2a7-4ad2-abc5-e69dc677c509'
$cmd="sudo bash -lc 'source /etc/smiot/app.env; curl -sS --max-time 8 -H \"Authorization: Bearer `$SMIOT_DEMO_CONTROL_TOKEN\" http://127.0.0.1:8080/api/demo/scenarios/$run'"
$payload=Join-Path $env:TEMP ('w1-read-'+[guid]::NewGuid().ToString('N')+'.json')
[IO.File]::WriteAllText($payload,(@{commands=@($cmd)}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payload --comment 'SMIOT W1 read scenario incident correlation' --query Command.CommandId --output text).Trim()
Start-Sleep 6
$r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json
Write-Output $r.StandardOutputContent
if($r.StandardErrorContent){Write-Output $r.StandardErrorContent}
Remove-Item $payload -Force
