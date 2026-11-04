"""Run one end-to-end synthetic irrigation trace through local MQTT and Datadog APM.

All MQTT topics use the isolated ``smiot/demo`` namespace. The PLC and flow meter
are simulated in this script; it never publishes to the farm control topic.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import paho.mqtt.client as mqtt

from service.ai_service import AI_ENABLED, API_KEY, ask_ai
from service.observability import (
    initialize_tracing,
    inject_mqtt_trace_context,
    trace_span,
    traced_mqtt_callback,
)

initialize_tracing()

BROKER = "localhost"
PORT = 1883
SENSOR_TOPIC = "smiot/demo/irrigation/sensor"
PLC_TOPIC = "smiot/demo/irrigation/plc"
FLOW_TOPIC = "smiot/demo/irrigation/flow"

connected = threading.Event()
finished = threading.Event()
result: dict = {}


def on_connect(client, userdata, connect_flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"MQTT connection failed (code={reason_code})")
        connected.set()
        return
    for topic in (SENSOR_TOPIC, PLC_TOPIC, FLOW_TOPIC):
        client.subscribe(topic)
    connected.set()


@traced_mqtt_callback("smiot.demo.mqtt.message")
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        payload.pop("_dd_trace_context", None)
        if msg.topic == SENSOR_TOPIC:
            with trace_span("smiot.demo.gemini.irrigation_decision", resource="Gemini irrigation recommendation",
                            **{"farm.key": payload.get("farm_key"), "sensor.synthetic": True,
                               "gemini.configured": bool(API_KEY and AI_ENABLED)}):
                if API_KEY and AI_ENABLED:
                    prompt = (
                        "This is synthetic hackathon demo data, not a real sensor. "
                        f"Greenhouse {payload.get('farm_key')} Node {payload.get('node')} soil humidity is "
                        f"{payload.get('soil_humidity')}%, and the stream is deliberately marked flatline. "
                        "Give a short irrigation recommendation. Explicitly say to verify the sensor and "
                        "do not claim that any physical pump was operated."
                    )
                    recommendation = ask_ai(prompt)
                else:
                    recommendation = "Gemini chưa được gọi: hãy cấu hình GEMINI_API_KEY và AI_ENABLED=true trong .env."

            command = {
                **payload,
                "recommendation": recommendation,
                "simulated": True,
            }
            client.publish(PLC_TOPIC, json.dumps(inject_mqtt_trace_context(command)))

        elif msg.topic == PLC_TOPIC:
            with trace_span("smiot.demo.plc.simulate", resource="PLC safety gate (simulation)",
                            **{"farm.key": payload.get("farm_key"), "plc.simulated": True}):
                # A flatline reading is untrusted; the demo safety gate holds the pump.
                action = "HOLD" if payload.get("flatline") else "WOULD_WATER"
                simulated_command = {
                    "farm_key": payload.get("farm_key"),
                    "node": payload.get("node"),
                    "action": action,
                    "recommendation": payload.get("recommendation", ""),
                    "simulated": True,
                }
                client.publish(FLOW_TOPIC, json.dumps(inject_mqtt_trace_context(simulated_command)))

        elif msg.topic == FLOW_TOPIC:
            with trace_span("smiot.demo.flow_meter.confirm", resource="flow meter confirmation (simulation)",
                            **{"farm.key": payload.get("farm_key"), "flow.simulated": True}):
                result.update(payload)
                result["flow_lpm"] = 0.0 if payload.get("action") == "HOLD" else 20.5
                print("Synthetic end-to-end result:")
                print(json.dumps(result, ensure_ascii=False, indent=2))
            finished.set()
    except Exception as exc:
        print(f"Demo trace failed: {type(exc).__name__}: {exc}")
        finished.set()


def main() -> int:
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"smiot-apm-demo-{int(time.time())}",
    )
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start()
        if not connected.wait(10) or not client.is_connected():
            print("Could not connect to the local MQTT broker at localhost:1883")
            return 1

        with trace_span("smiot.demo.irrigation_cycle", resource="synthetic irrigation observability demo",
                        **{"farm.key": "greenhouse_a", "sensor.synthetic": True}):
            with trace_span("smiot.demo.sensor.publish", resource=SENSOR_TOPIC,
                            **{"mqtt.topic": SENSOR_TOPIC, "sensor.synthetic": True}):
                sensor_event = {
                    "farm_key": "greenhouse_a",
                    "node": 2,
                    "soil_humidity": 2.4,
                    "flatline": True,
                    "synthetic": True,
                }
                info = client.publish(SENSOR_TOPIC, json.dumps(inject_mqtt_trace_context(sensor_event)))
                info.wait_for_publish(timeout=10)

            if not finished.wait(90):
                print("Timed out waiting for the simulated flow meter confirmation.")
                return 1
        return 0
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
