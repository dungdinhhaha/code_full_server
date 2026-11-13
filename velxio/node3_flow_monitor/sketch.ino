#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <esp_arduino_version.h>

static const char *WIFI_SSID = "Velxio-GUEST";
static const char *MQTT_HOST = "broker.hivemq.com";
static const uint16_t MQTT_PORT = 1883;
static const char *CHANNEL = "smiot-course-20261112-a91d4b";
static const char *FARM_KEY = "greenhouse_j";
static const char *DEVICE_ID = "velxio-flow-monitor-01";
static const int FLOW_PULSE_PIN = 27;
static const int FLOW_LED_PIN = 23;
static const int ALARM_LED_PIN = 22;
static const int BUZZER_PIN = 21;
static const int BUZZER_CHANNEL = 0;
static const unsigned long SAMPLE_INTERVAL_MS = 5000;
static const float PULSES_PER_LITER = 90.0f;

WiFiClient net;
PubSubClient mqtt(net);
volatile unsigned long pulseCount = 0;
volatile unsigned long lastPulseMicros = 0;
unsigned long lastSampleMs = 0;
unsigned long lastWifiAttemptMs = 0;
unsigned long lastMqttAttemptMs = 0;
unsigned long sequenceNo = 0;
float totalLiters = 0.0f;
bool pumpRequested = false;
bool alarmWasActive = false;
String profileName = "normal";
String activeScenario = "";
String activeRunId = "";
String activeIncidentId = "";
String lastCommandId = "";
unsigned long faultStartedMs = 0;
static const unsigned long AUTO_REVERT_MS = 120000UL;

String commandTopic() { return String("smiot/velxio/") + CHANNEL + "/actuator/command"; }
String flowTopic() { return String("smiot/velxio/") + CHANNEL + "/sensor/flow"; }
String ackTopic() { return String("smiot/velxio/") + CHANNEL + "/actuator/ack"; }

void setTone(unsigned int frequency) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWriteTone(BUZZER_PIN, frequency);
#else
  ledcWriteTone(BUZZER_CHANNEL, frequency);
#endif
}

// W1 evidence: one Serial line per flow-alarm state change, tied to the scenario run.
void logAlarmChange(bool alarmOn, const char *cause, const char *commandId) {
  Serial.printf("virtual_plc_safety_trip device=%s state=%s cause=%s command_id=%s "
                "scenario_code=%s scenario_run_id=%s incident_id=%s alarm_led=%d\n",
                DEVICE_ID, alarmOn ? "ALARM" : "CLEAR", cause, commandId,
                activeScenario.c_str(), activeRunId.c_str(), activeIncidentId.c_str(), alarmOn ? 1 : 0);
}

void IRAM_ATTR onFlowPulse() {
  const unsigned long now = micros();
  if (now - lastPulseMicros >= 3000) { ++pulseCount; lastPulseMicros = now; }
}

void sendProfileAck(JsonDocument &cmd, bool applied) {
  JsonDocument ack;
  ack["event"] = "virtual_device_profile_ack";
  ack["device_id"] = DEVICE_ID;
  ack["node_id"] = "flow";
  ack["farm_key"] = FARM_KEY;
  ack["command_id"] = cmd["command_id"] | "";
  ack["incident_id"] = cmd["incident_id"] | "";
  ack["scenario_run_id"] = cmd["scenario_run_id"] | "";
  ack["scenario_code"] = cmd["scenario_code"] | "";
  ack["profile"] = profileName;
  ack["dataset_id"] = profileName == "normal" ? "flow-normal-v1" : "flow-fault-v1";
  ack["applied"] = applied;
  ack["verified"] = applied && profileName == (cmd["profile"] | "normal");
  ack["safe_mode_active"] = !pumpRequested;
  ack["source"] = "velxio_synthetic";
  ack["synthetic"] = true;
  JsonObject outputs = ack["virtual_output"].to<JsonObject>();
  for (int i = 0; i < 8; ++i) outputs[String("bit") + i] = 0;
  uint8_t out[1024];
  size_t n = serializeJson(ack, out, sizeof(out));
  bool sent = mqtt.publish(ackTopic().c_str(), out, static_cast<unsigned int>(n), false);
  Serial.printf("PROFILE ACK %s -> %s applied=%d sent=%d bytes=%u\n", (const char *)(cmd["command_id"] | ""), profileName.c_str(), applied, sent, (unsigned)n);
}

void onMessage(char *topic, byte *payload, unsigned int length) {
  if (commandTopic() != topic || length == 0 || length > 1024) return;
  JsonDocument cmd;
  if (deserializeJson(cmd, payload, length)) return;
  if (String((const char *)(cmd["farm_key"] | "")) != FARM_KEY) return;
  String target = cmd["target_device_id"] | "";
  if (target.length() && target != DEVICE_ID && target != "flow") return;
  String id = cmd["command_id"] | "";
  if (!id.length() || id == lastCommandId) return;
  String action = cmd["action"] | "";
  if (action == "SET_PROFILE") {
    String requested = cmd["profile"] | "";
    if (requested != "normal" && requested != "fault") { sendProfileAck(cmd, false); return; }
    const bool wasFault = profileName == "fault";
    profileName = requested;
    activeScenario = cmd["scenario_code"] | "";
    activeRunId = cmd["scenario_run_id"] | "";
    activeIncidentId = cmd["incident_id"] | "";
    if (profileName == "normal") pumpRequested = false;
    const bool faultActive = profileName == "fault";
    digitalWrite(ALARM_LED_PIN, faultActive ? HIGH : LOW);
    alarmWasActive = faultActive;
    if (faultActive) { setTone(700); delay(180); setTone(0); }
    else { setTone(1650); delay(100); setTone(0); }
    logAlarmChange(faultActive, faultActive ? "profile_fault" : "profile_normal", id.c_str());
    if (faultActive) {
      faultStartedMs = millis();
      Serial.printf("DRILL ALERT profile=fault scenario_code=%s scenario_run_id=%s\n",
                    activeScenario.c_str(), activeRunId.c_str());
    } else if (wasFault) {
      Serial.printf("DRILL RESTORED scenario_run_id=%s\n", activeRunId.c_str());
    }
    lastCommandId = id;
    sendProfileAck(cmd, true);
    return;
  }
  bool nextPump = pumpRequested;
  if (action == "HOLD" || action == "CLEAR" || action == "SAFE_STOP" || action == "STOP_PUMPS") nextPump = false;
  else if (action == "SET_OUTPUTS" && !cmd["bit0"].isNull()) {
    int value = cmd["bit0"].as<int>(); if (value != 0 && value != 1) return; nextPump = value == 1;
  } else return;
  pumpRequested = nextPump;
  if (action == "CLEAR") {
    if (profileName == "fault") Serial.printf("DRILL RESTORED scenario_run_id=%s\n", activeRunId.c_str());
    profileName = "normal";
  }
  lastCommandId = id;
}

void maintainNetwork() {
  if (WiFi.status() != WL_CONNECTED && millis() - lastWifiAttemptMs >= 5000) {
    lastWifiAttemptMs = millis(); WiFi.mode(WIFI_STA); WiFi.begin(WIFI_SSID); Serial.println("Wi-Fi reconnect requested"); return;
  }
  if (WiFi.status() == WL_CONNECTED && !mqtt.connected() && millis() - lastMqttAttemptMs >= 2000) {
    lastMqttAttemptMs = millis();
    if (mqtt.connect(DEVICE_ID)) { mqtt.subscribe(commandTopic().c_str(), 1); Serial.println("MQTT ready"); }
    else Serial.printf("MQTT reconnect failed state=%d\n", mqtt.state());
  }
  if (mqtt.connected()) mqtt.loop();
}

void setup() {
  Serial.begin(115200);
  pinMode(FLOW_PULSE_PIN, INPUT_PULLUP); pinMode(FLOW_LED_PIN, OUTPUT); pinMode(ALARM_LED_PIN, OUTPUT);
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(BUZZER_PIN, 2000, 8);
#else
  ledcSetup(BUZZER_CHANNEL, 2000, 8); ledcAttachPin(BUZZER_PIN, BUZZER_CHANNEL);
#endif
  digitalWrite(FLOW_LED_PIN, LOW); digitalWrite(ALARM_LED_PIN, LOW);
  attachInterrupt(digitalPinToInterrupt(FLOW_PULSE_PIN), onFlowPulse, FALLING);
  mqtt.setServer(MQTT_HOST, MQTT_PORT); mqtt.setCallback(onMessage); mqtt.setBufferSize(1024);
  WiFi.mode(WIFI_STA); WiFi.begin(WIFI_SSID);
  Serial.println("Flow meter online; pulse button and synthetic fault profiles are enabled.");
}

void loop() {
  maintainNetwork();
  // Auto-revert: a fault profile with no SET_PROFILE normal for AUTO_REVERT_MS returns to normal.
  if (profileName == "fault" && millis() - faultStartedMs >= AUTO_REVERT_MS) {
    profileName = "normal";
    pumpRequested = false;
    alarmWasActive = false;
    digitalWrite(ALARM_LED_PIN, LOW);
    Serial.printf("DRILL AUTO_REVERT scenario_run_id=%s\n", activeRunId.c_str());
  }
  if (millis() - lastSampleMs < SAMPLE_INTERVAL_MS) return;
  unsigned long now = millis();
  float intervalSeconds = lastSampleMs ? (now - lastSampleMs) / 1000.0f : 5.0f;
  lastSampleMs = now;
  noInterrupts(); unsigned long pulses = pulseCount; pulseCount = 0; interrupts();

  float flowLpm = (pulses / PULSES_PER_LITER) * 60.0f / max(1.0f, intervalSeconds);
  float pressure = pumpRequested && flowLpm >= 0.15f ? 1.6f : 0.0f;
  const char *fault = "none";
  if (profileName == "fault") {
    if (activeScenario == "A1" || activeScenario == "a1_water_overrun" || activeScenario == "water_overrun") {
      flowLpm = 12.0f; pressure = 0.2f; fault = "high_flow_leak";
    } else if (activeScenario == "C10" || activeScenario == "pipe_leak") {
      flowLpm = 12.0f; pressure = 0.2f; fault = "pipe_leak";
    } else if (activeScenario == "A2" || activeScenario == "a2_pump_pressure_zero") {
      flowLpm = 0.0f; pressure = 0.0f; fault = "pump_on_pressure_zero";
    } else if (activeScenario == "A3" || activeScenario == "a3_low_flow") {
      // Very low flow only while the pump is commanded to run.
      flowLpm = pumpRequested ? 0.1f : 0.0f; pressure = pumpRequested ? 0.3f : 0.0f; fault = "low_flow";
    } else { flowLpm = 0.0f; pressure = 0.0f; fault = "scenario_fault"; }
  }
  totalLiters += flowLpm * intervalSeconds / 60.0f;
  bool alarm = profileName == "fault" || flowLpm > 2.0f;
  digitalWrite(FLOW_LED_PIN, flowLpm >= 0.15f && !alarm ? HIGH : LOW);
  digitalWrite(ALARM_LED_PIN, alarm ? HIGH : LOW);
  if (alarm && !alarmWasActive) { setTone(1100); delay(250); setTone(0); }
  if (alarm != alarmWasActive) {
    const char *cause = !alarm ? "flow_recovered" : (profileName == "fault" ? fault : "flow_above_2_lpm");
    logAlarmChange(alarm, cause, lastCommandId.c_str());
  }
  alarmWasActive = alarm;

  JsonDocument doc;
  doc["farm_key"] = FARM_KEY; doc["device_id"] = DEVICE_ID; doc["device_type"] = "flow_sensor";
  doc["node_id"] = "flow"; doc["sequence"] = ++sequenceNo;
  doc["f1"] = flowLpm; doc["f2"] = 0.0; doc["pressure_bar"] = pressure;
  doc["pump_line1_on"] = pumpRequested; doc["pump_line2_on"] = false;
  doc["valve_open"] = pumpRequested && profileName != "fault"; doc["safe_mode_active"] = !pumpRequested;
  doc["fault"] = fault; doc["t1"] = totalLiters; doc["t2"] = 0.0;
  doc["flow_pulses"] = pulses; doc["profile"] = profileName;
  doc["dataset_id"] = profileName == "normal" ? "flow-normal-v1" : "flow-fault-v1";
  doc["scenario_code"] = activeScenario; doc["scenario_run_id"] = activeRunId;
  doc["incident_id"] = activeIncidentId; doc["source"] = "velxio_synthetic"; doc["synthetic"] = true;
  uint8_t out[800]; size_t n = serializeJson(doc, out, sizeof(out));
  if (mqtt.connected()) mqtt.publish(flowTopic().c_str(), out, static_cast<unsigned int>(n), false);
  Serial.printf("sample #%lu profile=%s flow=%.2f pressure=%.2f fault=%s\n", sequenceNo, profileName.c_str(), flowLpm, pressure, fault);
}
