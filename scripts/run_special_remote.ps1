$ErrorActionPreference='Stop'
$json=Join-Path $env:TEMP ('smiot-run-special-' + [guid]::NewGuid().ToString('N') + '.json')
$commands=@('set -e','cd /opt/smiot','export PYTHONPATH=/opt/smiot','/opt/smiot/.venv/bin/python /opt/smiot/scripts/run_correlated_w3_w5.py --case W3','/opt/smiot/.venv/bin/python /opt/smiot/scripts/run_correlated_w3_w5.py --case W5','/opt/smiot/.venv/bin/python /opt/smiot/scripts/run_w10_correlated.py')
(@{commands=$commands}|ConvertTo-Json -Compress)|Set-Content -Encoding ascii $json
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$json --comment 'SMIOT specialized W3 W5 W10 correlation drills' --query Command.CommandId --output text).Trim()
Write-Output "command=$id"
do { Start-Sleep 4; $r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json; if($r.Status -in @('Success','Failed','Cancelled','TimedOut')) { Write-Output "status=$($r.Status)"; Write-Output $r.StandardOutputContent; if($r.Status -ne 'Success'){Write-Output $r.StandardErrorContent}; break } } while($true)
Remove-Item $json -Force -ErrorAction SilentlyContinue
