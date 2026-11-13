param([ValidateSet('failure','normal')][string]$Mode='failure')
$ErrorActionPreference='Stop'
$py = if($Mode -eq 'failure'){
  "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.sendto(b'smiot.ai.provider_failure:1|g|#status:provider_error,action:HOLD,source:smiot_w10_clean_drill\nsmiot.ai.ask_latency_ms:6000|g|#status:provider_error,source:smiot_w10_clean_drill\nsmiot.ai.provider_success:0|g|#status:provider_error,action:HOLD,source:smiot_w10_clean_drill',('127.0.0.1',8125)); print('W10 synthetic failure metrics sent')"
} else {
  "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.sendto(b'smiot.ai.provider_failure:0|g|#status:provider_error,action:HOLD,source:smiot_w10_clean_drill\nsmiot.ai.ask_latency_ms:250|g|#status:provider_error,source:smiot_w10_clean_drill\nsmiot.ai.provider_success:1|g|#status:ok,action:NONE,source:smiot_w10_clean_drill',('127.0.0.1',8125)); print('W10 synthetic normal metrics sent')"
}
$encoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($py))
$remote="echo $encoded | base64 -d > /tmp/smiot-w10-metric.py; python3 /tmp/smiot-w10-metric.py; rm -f /tmp/smiot-w10-metric.py"
$payload=Join-Path $env:TEMP ('w10-clean-'+[guid]::NewGuid().ToString('N')+'.json')
[IO.File]::WriteAllText($payload,(@{commands=@($remote)}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payload --comment "SMIOT W10 clean $Mode synthetic drill" --query Command.CommandId --output text).Trim()
Start-Sleep 6
$r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json
Write-Output "command=$id status=$($r.Status)"
Write-Output $r.StandardOutputContent
if($r.StandardErrorContent){Write-Output $r.StandardErrorContent}
Remove-Item $payload -Force
