$ErrorActionPreference = 'Stop'
$payloadPath = Join-Path $env:TEMP ('smiot-w6-py-' + [guid]::NewGuid().ToString('N') + '.json')
$remote = @'
set -e
cd /opt/smiot
PY=/opt/smiot/.venv/bin/python
[ -x "$PY" ] || PY=python3
"$PY" - <<'PYCODE'
import json, threading, time, uuid
import paho.mqtt.client as mqtt
farm = "greenhouse_b"
acks = []
ready = threading.Event()
try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="smiot-w6-inject-" + uuid.uuid4().hex[:8])
except AttributeError:
    client = mqtt.Client(client_id="smiot-w6-inject-" + uuid.uuid4().hex[:8])
def on_connect(cl, userdata, flags, reason_code, properties=None):
    if reason_code in (None, 0):
        cl.subscribe("farm/demo/status", qos=1)
        ready.set()
def on_message(cl, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except Exception:
        return
    if data.get("event") == "detector_fault_ack":
        acks.append(data)
client.on_connect = on_connect
client.on_message = on_message
client.connect("localhost", 1883, keepalive=30)
client.loop_start()
if not ready.wait(8):
    raise SystemExit("mqtt_connect_timeout")
for mode in ("stalled", "normal"):
    command_id = str(uuid.uuid4())
    message = {"demo_detector_fault": mode, "farm_key": farm, "command_id": command_id, "synthetic": True}
    client.publish("farm/demo/control", json.dumps(message, separators=(",", ":")), qos=1).wait_for_publish(5)
    deadline = time.time() + 12
    while time.time() < deadline and not any(item.get("command_id") == command_id for item in acks):
        time.sleep(0.2)
    ack = next((item for item in acks if item.get("command_id") == command_id), None)
    print(json.dumps({"mode": mode, "ack": ack}, separators=(",", ":")))
    if not ack or ack.get("applied") is not True or ack.get("mode_applied") is not True:
        raise SystemExit("missing_or_failed_ack_" + mode)
client.disconnect()
client.loop_stop()
PYCODE
'@
[IO.File]::WriteAllText($payloadPath, (@{commands=@('cd /opt/smiot', $remote)} | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
$id = (aws ssm send-command --profile aws-moi --region ap-southeast-2 --instance-ids i-00bf2d3591d3ee0a2 --document-name AWS-RunShellScript --parameters file://$payloadPath --comment 'SMIOT W6 scoped synthetic injector ACK test' --query Command.CommandId --output text).Trim()
Write-Output "command=$id"
do {
    Start-Sleep 3
    $result = aws ssm get-command-invocation --profile aws-moi --region ap-southeast-2 --command-id $id --instance-id i-00bf2d3591d3ee0a2 --output json | ConvertFrom-Json
    if ($result.Status -in @('Success','Failed','Cancelled','TimedOut')) {
        Write-Output "status=$($result.Status)"
        Write-Output $result.StandardOutputContent
        if ($result.StandardErrorContent) { Write-Output "stderr=$($result.StandardErrorContent)" }
        break
    }
} while ($true)
Remove-Item $payloadPath -Force -ErrorAction SilentlyContinue
