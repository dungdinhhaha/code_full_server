$ErrorActionPreference='Stop'
$payload=Join-Path $env:TEMP ('w6-all-normal-'+[guid]::NewGuid().ToString('N')+'.json')
$remote=@'
set -e
cd /opt/smiot
/opt/smiot/.venv/bin/python - <<'PY'
import json,time,uuid,paho.mqtt.client as mqtt
farms=[f'greenhouse_{x}' for x in 'abcdefghij']; acks=[]
try: c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='smiot-w6-normal-all-'+uuid.uuid4().hex[:8])
except AttributeError: c=mqtt.Client(client_id='smiot-w6-normal-all-'+uuid.uuid4().hex[:8])
def on_connect(cl,ud,flags,rc,props=None): cl.subscribe('farm/demo/status',qos=1)
def on_message(cl,ud,m):
 try:
  x=json.loads(m.payload.decode())
  if x.get('event')=='detector_fault_ack' and x.get('applied') is True: acks.append(x)
 except Exception: pass
c.on_connect=on_connect;c.on_message=on_message;c.connect('localhost',1883,30);c.loop_start();time.sleep(1)
for farm in farms:
 cid=str(uuid.uuid4()); c.publish('farm/demo/control',json.dumps({'demo_detector_fault':'normal','farm_key':farm,'command_id':cid,'synthetic':True},separators=(',',':')),qos=1).wait_for_publish(5); time.sleep(.25)
time.sleep(8); print(json.dumps({'farms':farms,'ack_farms':sorted({x.get('farm_key') for x in acks}),'ack_count':len(acks)})); c.disconnect();c.loop_stop()
PY
'@
[IO.File]::WriteAllText($payload,(@{commands=@($remote)}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payload --comment 'W6 normal heartbeat reset all farms' --query Command.CommandId --output text).Trim(); Write-Output "command=$id"
do {Start-Sleep 4;$r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json;if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){$r.StandardOutputContent; if($r.StandardErrorContent){$r.StandardErrorContent};break}}while($true)
Remove-Item $payload -Force
