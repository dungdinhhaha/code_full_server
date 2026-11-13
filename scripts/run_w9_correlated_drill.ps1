$ErrorActionPreference = 'Stop'
$tmp = Join-Path $env:TEMP ('smiot-w9-correlated-' + [guid]::NewGuid().ToString('N') + '.json')
$remote = @'
set -e
cd /opt/smiot
PY=/opt/smiot/.venv/bin/python
[ -x "$PY" ] || PY=python3
"$PY" - <<'PYCODE'
import json, threading, time, uuid
import paho.mqtt.client as mqtt
farm = "greenhouse_j"
incident = "INC-SMIOT-W9-DRILL-" + uuid.uuid4().hex[:10].upper()
ready = threading.Event()
try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="smiot-w9-correlated-" + uuid.uuid4().hex[:8])
except AttributeError:
    client = mqtt.Client(client_id="smiot-w9-correlated-" + uuid.uuid4().hex[:8])
def on_connect(cl, userdata, flags, reason_code, properties=None):
    if reason_code in (None, 0): ready.set()
client.on_connect = on_connect
client.connect("localhost", 1883, keepalive=30); client.loop_start()
if not ready.wait(8): raise SystemExit("mqtt_connect_timeout")
command_id = "w9-" + uuid.uuid4().hex
body = {"action":"SET_OUTPUTS", "farm_key":farm, "command_id":command_id,
        "incident_id":incident, "monitor_id":"342734743",
        "workflow_id":"47e95b24-db40-4cd5-b667-5b90e170b667",
        "bit0":0, "w9_late_ack_drill":True, "synthetic":True}
client.publish("farm/demo/control", json.dumps(body, separators=(",", ":")), qos=1).wait_for_publish(5)
print(json.dumps({"phase":"w9_command_sent","incident_id":incident,"command_id":command_id,"farm_key":farm}, separators=(",", ":")), flush=True)
time.sleep(12)
ack = {"event":"virtual_plc_command_ack", "command_id":command_id, "farm_key":farm,
       "incident_id":incident, "action":"SET_OUTPUTS", "target":"smiot_virtual_plc",
       "source":"smiot_w9_late_ack_drill", "synthetic":True, "verified":True,
       "virtual_output":{"bit0":0}, "bit0":0}
client.publish("farm/command/ack", json.dumps(ack, separators=(",", ":")), qos=1).wait_for_publish(5)
print(json.dumps({"phase":"w9_late_ack_sent","incident_id":incident,"command_id":command_id,"farm_key":farm}, separators=(",", ":")), flush=True)
time.sleep(3)
client.disconnect(); client.loop_stop()
PYCODE
'@
[IO.File]::WriteAllText($tmp, (@{commands=@('cd /opt/smiot', $remote)} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
try {
  $id = (aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$tmp --comment 'SMIOT W9 correlated late ACK drill' --query Command.CommandId --output text).Trim()
  Write-Output "command=$id"
  do {
    Start-Sleep 5
    $r = aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json | ConvertFrom-Json
    Write-Output "status=$($r.Status)"
    if ($r.StandardOutputContent) { Write-Output $r.StandardOutputContent }
    if ($r.Status -in @('Success','Failed','Cancelled','TimedOut')) { if ($r.StandardErrorContent) { Write-Output "stderr=$($r.StandardErrorContent)" }; break }
  } while ($true)
} finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
