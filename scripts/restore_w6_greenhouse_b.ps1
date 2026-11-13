$ErrorActionPreference='Stop'
$payload=Join-Path $env:TEMP ('w6-normal-'+[guid]::NewGuid().ToString('N')+'.json')
$remote=@'
set -e
cd /opt/smiot
/opt/smiot/.venv/bin/python - <<'PY'
import json,threading,time,uuid
import paho.mqtt.client as mqtt
farm='greenhouse_b'; cid=str(uuid.uuid4()); got=[]; ready=threading.Event()
try: c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='smiot-w6-normal-'+uuid.uuid4().hex[:8])
except AttributeError: c=mqtt.Client(client_id='smiot-w6-normal-'+uuid.uuid4().hex[:8])
def conn(cl,ud,flags,rc,props=None):
 if rc in (None,0): cl.subscribe('farm/demo/status',qos=1); ready.set()
def msg(cl,ud,m):
 try:
  x=json.loads(m.payload.decode())
  if x.get('event')=='detector_fault_ack' and x.get('command_id')==cid: got.append(x)
 except Exception: pass
c.on_connect=conn;c.on_message=msg;c.connect('localhost',1883,30);c.loop_start()
if not ready.wait(8): raise SystemExit('mqtt_connect_timeout')
c.publish('farm/demo/control',json.dumps({'demo_detector_fault':'normal','farm_key':farm,'command_id':cid,'synthetic':True},separators=(',',':')),qos=1).wait_for_publish(5)
until=time.time()+15
while time.time()<until and not got: time.sleep(.2)
print(json.dumps({'farm':farm,'command_id':cid,'ack':got[0] if got else None}),flush=True)
c.disconnect();c.loop_stop()
if not got or got[0].get('applied') is not True or got[0].get('mode_applied') is not True: raise SystemExit('normal_ack_failed')
PY
'@
[IO.File]::WriteAllText($payload,(@{commands=@($remote)}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
$id=(aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payload --comment 'SMIOT W6 greenhouse_b normal cleanup' --query Command.CommandId --output text).Trim()
Write-Output "command=$id"
do { Start-Sleep 5; $r=aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json|ConvertFrom-Json; if($r.Status -in @('Success','Failed','Cancelled','TimedOut')){Write-Output "status=$($r.Status)"; Write-Output $r.StandardOutputContent; if($r.StandardErrorContent){Write-Output $r.StandardErrorContent}; break} } while($true)
Remove-Item $payload -Force
