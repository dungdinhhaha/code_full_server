$ErrorActionPreference = 'Stop'
$tmp = Join-Path $env:TEMP ('smiot-w6-correlated-' + [guid]::NewGuid().ToString('N') + '.json')
$remote = @'
set -e
cd /opt/smiot
PY=/opt/smiot/.venv/bin/python
[ -x "$PY" ] || PY=python3
"$PY" - <<'PYCODE'
import json, threading, time, uuid
import paho.mqtt.client as mqtt
farm = "greenhouse_b"
incident = "INC-SMIOT-W6-DRILL-" + uuid.uuid4().hex[:10].upper()
acks = []
ready = threading.Event()
try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="smiot-w6-correlated-" + uuid.uuid4().hex[:8])
except AttributeError:
    client = mqtt.Client(client_id="smiot-w6-correlated-" + uuid.uuid4().hex[:8])
def on_connect(cl, userdata, flags, reason_code, properties=None):
    if reason_code in (None, 0):
        cl.subscribe("farm/demo/status", qos=1)
        ready.set()
def on_message(cl, userdata, msg):
    try: data = json.loads(msg.payload.decode())
    except Exception: return
    if data.get("event") == "detector_fault_ack": acks.append(data)
client.on_connect = on_connect; client.on_message = on_message
client.connect("localhost", 1883, keepalive=30); client.loop_start()
if not ready.wait(8): raise SystemExit("mqtt_connect_timeout")
def send(mode):
    command_id = str(uuid.uuid4())
    body = {"demo_detector_fault": mode, "farm_key": farm, "command_id": command_id,
            "incident_id": incident, "synthetic": True}
    client.publish("farm/demo/control", json.dumps(body, separators=(",", ":")), qos=1).wait_for_publish(5)
    deadline = time.time() + 15
    while time.time() < deadline and not any(x.get("command_id") == command_id for x in acks): time.sleep(.2)
    ack = next((x for x in acks if x.get("command_id") == command_id), None)
    print(json.dumps({"mode": mode, "incident_id": incident, "ack": ack}, separators=(",", ":")), flush=True)
    if not ack or ack.get("applied") is not True: raise SystemExit("missing_or_failed_ack_" + mode)
send("stalled")
print(json.dumps({"phase":"w6_stalled","incident_id":incident,"farm_key":farm}, separators=(",", ":")), flush=True)
time.sleep(330)
send("normal")
print(json.dumps({"phase":"w6_normal_sent","incident_id":incident,"farm_key":farm}, separators=(",", ":")), flush=True)
client.disconnect(); client.loop_stop()
PYCODE
'@
[IO.File]::WriteAllText($tmp, (@{commands=@('cd /opt/smiot', $remote)} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
try {
  $id = (aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$tmp --comment 'SMIOT W6 correlated detector drill' --query Command.CommandId --output text).Trim()
  Write-Output "command=$id"
  do {
    Start-Sleep 10
    $r = aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json | ConvertFrom-Json
    Write-Output "status=$($r.Status)"
    if ($r.StandardOutputContent) { Write-Output $r.StandardOutputContent }
    if ($r.Status -in @('Success','Failed','Cancelled','TimedOut')) { if ($r.StandardErrorContent) { Write-Output "stderr=$($r.StandardErrorContent)" }; break }
  } while ($true)
} finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
