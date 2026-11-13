$ErrorActionPreference = 'Stop'
$payloadPath = Join-Path $env:TEMP ('smiot-w2-w6-parallel-' + [guid]::NewGuid().ToString('N') + '.json')
$remote = @'
set -e
cd /opt/smiot
PY=/opt/smiot/.venv/bin/python
[ -x "$PY" ] || PY=python3
"$PY" - <<'PYCODE'
import json, threading, time, uuid
import paho.mqtt.client as mqtt
acks = []
samples = []
ready = threading.Event()
try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="smiot-w2-w6-parallel-" + uuid.uuid4().hex[:8])
except AttributeError:
    client = mqtt.Client(client_id="smiot-w2-w6-parallel-" + uuid.uuid4().hex[:8])
def on_connect(cl, userdata, flags, reason_code, properties=None):
    if reason_code in (None, 0):
        cl.subscribe([("farm/demo/status", 1), ("farm/sensor", 1)])
        ready.set()
def on_message(cl, userdata, msg):
    try: data = json.loads(msg.payload.decode())
    except Exception: return
    if msg.topic == "farm/demo/status": acks.append(data)
    elif msg.topic == "farm/sensor": samples.append(data)
client.on_connect = on_connect
client.on_message = on_message
client.connect("localhost", 1883, keepalive=30)
client.loop_start()
if not ready.wait(8): raise SystemExit("mqtt_connect_timeout")
w2run = str(uuid.uuid4())
w2cmd = str(uuid.uuid4())
w6cmd = str(uuid.uuid4())
client.publish("farm/demo/control", json.dumps({"action":"START_SCENARIO","scenario_type":"soil_flatline","scenario_run_id":w2run,"command_id":w2cmd,"farm_key":"greenhouse_a","node_id":2,"seed":42}, separators=(",", ":")), qos=1).wait_for_publish(5)
client.publish("farm/demo/control", json.dumps({"demo_detector_fault":"stalled","farm_key":"greenhouse_b","command_id":w6cmd,"synthetic":True}, separators=(",", ":")), qos=1).wait_for_publish(5)
deadline = time.time() + 45
while time.time() < deadline and not any(x.get("command_id") == w2cmd for x in acks): time.sleep(.2)
print(json.dumps({"phase":"started","w2_run_id":w2run,"w2_ack":next((x for x in acks if x.get("command_id") == w2cmd),None),"w6_ack":next((x for x in acks if x.get("command_id") == w6cmd),None)}, separators=(",", ":")), flush=True)
print(json.dumps({"phase":"w2_correlated_samples","count":sum(1 for x in samples if x.get("scenario_run_id") == w2run)}, separators=(",", ":")), flush=True)
time.sleep(330)
w2stop = str(uuid.uuid4())
w6normal = str(uuid.uuid4())
client.publish("farm/demo/control", json.dumps({"action":"STOP_SCENARIO","scenario_run_id":w2run,"command_id":w2stop,"farm_key":"greenhouse_a"}, separators=(",", ":")), qos=1).wait_for_publish(5)
client.publish("farm/demo/control", json.dumps({"demo_detector_fault":"normal","farm_key":"greenhouse_b","command_id":w6normal,"synthetic":True}, separators=(",", ":")), qos=1).wait_for_publish(5)
time.sleep(20)
print(json.dumps({"phase":"restored","w2_stop_id":w2stop,"w6_normal_id":w6normal,"w2_stop_ack":next((x for x in acks if x.get("command_id") == w2stop),None),"w6_normal_ack":next((x for x in acks if x.get("command_id") == w6normal),None)}, separators=(",", ":")), flush=True)
client.disconnect()
client.loop_stop()
PYCODE
'@
[IO.File]::WriteAllText($payloadPath, (@{commands=@('cd /opt/smiot', $remote)} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
$id = (aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payloadPath --comment 'SMIOT W2 W6 parallel live drill after fixes' --query Command.CommandId --output text).Trim()
Write-Output "command=$id"
do {
    Start-Sleep 10
    $result = aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json | ConvertFrom-Json
    Write-Output "status=$($result.Status)"
    if ($result.StandardOutputContent) { Write-Output $result.StandardOutputContent }
    if ($result.Status -in @('Success','Failed','Cancelled','TimedOut')) {
        if ($result.StandardErrorContent) { Write-Output "stderr=$($result.StandardErrorContent)" }
        break
    }
} while ($true)
Remove-Item $payloadPath -Force -ErrorAction SilentlyContinue
