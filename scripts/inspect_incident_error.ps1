$ErrorActionPreference='Stop'
$payload=Join-Path $env:TEMP 'journal-incident.json'
$remote="journalctl -u smiot.service --since '15 minutes ago' --no-pager | tail -260"
[IO.File]::WriteAllText($payload,(@{commands=@($remote)}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payload --comment 'Inspect incident page traceback' --query Command.CommandId --output text).Trim()
do {Start-Sleep 3;$r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json;if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){$r.StandardOutputContent; $r.StandardErrorContent;break}}while($true)
Remove-Item $payload -Force
