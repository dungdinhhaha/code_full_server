param([ValidateSet('before','after')][string]$Phase='before')
$ErrorActionPreference='Stop'
$p=Join-Path $env:TEMP ('w5-probe-'+$Phase+'-'+[guid]::NewGuid().ToString('N')+'.json')
$cmd="sudo bash -lc 'cd /opt/smiot; set -a; source /etc/smiot/app.env 2>/dev/null || true; source /etc/smiot/probe.env 2>/dev/null || true; set +a; export PYTHONPATH=/opt/smiot; /opt/smiot/.venv/bin/python scripts/probe_w5_dependencies.py --phase $Phase'"
[IO.File]::WriteAllText($p,(@{commands=@($cmd)}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$p --comment "SMIOT W5 $Phase read-only dependency probe" --query Command.CommandId --output text).Trim()
Start-Sleep 8
$r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json
$r.Status; $r.StandardOutputContent; if($r.StandardErrorContent){$r.StandardErrorContent}
Remove-Item $p -Force
