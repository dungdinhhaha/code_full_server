$ErrorActionPreference='Stop'
$file='D:\IOT Trung\code_full_server\scripts\verify_six_step_demo.py'
$b64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($file))
$cmd="echo $b64 | base64 -d > /tmp/verify_six_step_demo.py; set -a; . /etc/smiot/app.env; set +a; cd /opt/smiot; sudo -E -u smiot env PYTHONPATH=/opt/smiot /opt/smiot/.venv/bin/python /tmp/verify_six_step_demo.py"
$p=Join-Path $env:TEMP 'verify-six-step-demo.json'
[IO.File]::WriteAllText($p,(@{commands=@($cmd)}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
try { $id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$p --comment 'Verify SMIOT six-step incident pack' --query Command.CommandId --output text).Trim(); Write-Output "command=$id"; do { Start-Sleep 4; $r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json; if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){Write-Output "status=$($r.Status)";Write-Output $r.StandardOutputContent;if($r.StandardErrorContent){Write-Output "stderr=$($r.StandardErrorContent)"};break} } while($true) } finally { Remove-Item $p -Force -ErrorAction SilentlyContinue }
