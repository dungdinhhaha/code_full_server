$p=Join-Path $env:TEMP 'envnames.json'
$cmd='sudo bash -lc ''for f in /etc/smiot/app.env /etc/smiot/probe.env; do [ -f "$f" ] && grep -E "^[A-Za-z_][A-Za-z0-9_]*=" "$f" | sed -E "s/=.*//"; done | grep -E "MONGO|MQTT" | sort'''
[IO.File]::WriteAllText($p,(@{commands=@($cmd)}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$p --comment 'SMIOT inspect dependency env names' --query Command.CommandId --output text).Trim()
Start-Sleep 6
$r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json
$r.StandardOutputContent; if($r.StandardErrorContent){$r.StandardErrorContent}
Remove-Item $p -Force
