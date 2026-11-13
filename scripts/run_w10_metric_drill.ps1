param([ValidateSet('failure','normal')][string]$Mode)
$ErrorActionPreference='Stop'
$flag = if($Mode -eq 'normal') {'--w10-normal'} else {''}
$remote="/usr/bin/python3 /opt/smiot/scripts/emit_w9_w10_synthetic_metrics.py --send $flag"
$tmp=Join-Path $env:TEMP ('w10-'+[guid]::NewGuid().ToString('N')+'.json')
[IO.File]::WriteAllText($tmp, (@{commands=@($remote)}|ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
try {
  $id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$tmp --comment "SMIOT W10 $Mode advisory drill" --query Command.CommandId --output text).Trim()
  Start-Sleep 4
  aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json
}
finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
