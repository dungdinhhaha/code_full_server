#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <esp_arduino_version.h>

static const char *WIFI_SSID = "Velxio-GUEST";
static const char *MQTT_HOST = "broker.hivemq.com";
static const uint16_t MQTT_PORT = 1883;
static const char *CHANNEL = "smiot-course-20261112-a91d4b";
static const char *FARM_KEY = "greenhouse_j";
static const int OUTPUT_PINS[7] = {23, 22, 21, 19, 18, 17, 16};
static const int HOLD_LED = 25;
static const int BUZZER_PIN = 26;
static const int BUZZER_CHANNEL = 0;
static const unsigned long WIFI_RETRY_MS = 5000;
static const unsigned long MQTT_RETRY_MS = 2000;

WiFiClient net;
PubSubClient mqtt(net);
bool safeHold = false;
int outputBits[8] = {0};
String lastCommandId;
String profileName = "normal";
String activeScenario = "";
String activeRunId = "";
String activeIncidentId = "";
unsigned long lastWifiAttemptMs = 0;
unsigned long lastMqttAttemptMs = 0;
unsigned long faultStartedMs = 0;
static const unsigned long AUTO_REVERT_MS = 120000UL;
String commandTopic() { return String("smiot/velxio/") + CHANNEL + "/actuator/command"; }
String ackTopic() { return String("smiot/velxio/") + CHANNEL + "/actuator/ack"; }

void applyOutputs() {
  if (safeHold) for (int i = 0; i < 8; ++i) outputBits[i] = 0;
  for (int i = 0; i < 7; ++i) digitalWrite(OUTPUT_PINS[i], outputBits[i] ? HIGH : LOW);
  digitalWrite(HOLD_LED, safeHold ? HIGH : LOW);
}

int pumpsOn() {
  int n = 0;
  for (int i = 0; i < 7; ++i) n += outputBits[i] ? 1 : 0;
  return n;
}

// W1 evidence: one Serial line per safety-state change (HOLD red LED follows safeHold).
void logSafetyChange(const char *state, const char *cause, const char *commandId) {
  Serial.printf("virtual_plc_safety_trip device=velxio-virtual-pump-01 state=%s cause=%s command_id=%s "
                "scenario_code=%s scenario_run_id=%s incident_id=%s hold_led=%d pumps_on=%d\n",
                state, cause, commandId, activeScenario.c_str(), activeRunId.c_str(),
                activeIncidentId.c_str(), safeHold ? 1 : 0, pumpsOn());
}

// W9 (A4) drill: during a fault run tagged A4, commands are still applied but the
// pump withholds its command ACK and the confirmation beep (simulated no-ACK).
bool isA4Scenario() {
  return activeScenario == "A4" || activeScenario == "a4_command_no_ack";
}

bool ackSuppressedForScenario() {
  return profileName == "fault" && isA4Scenario();
}

void setBuzzerTone(unsigned int frequency) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWriteTone(BUZZER_PIN, frequency);
#else
  ledcWriteTone(BUZZER_CHANNEL, frequency);
#endif
}

void playBeep(unsigned int frequency, unsigned long durationMs) {
  setBuzzerTone(frequency);
  delay(durationMs);
  setBuzzerTone(0);
}

void sendAck(const char *commandId, const char *action, bool verified, bool beep) {
  if (ackSuppressedForScenario()) {
    Serial.printf("ACK_SUPPRESSED command_id=%s action=%s scenario_code=%s scenario_run_id=%s pumps_on=%d safe_hold=%d\n",
                  commandId, action, activeScenario.c_str(), activeRunId.c_str(), pumpsOn(), safeHold ? 1 : 0);
    return;
  }
  JsonDocument doc;
  doc["event"] = "virtual_plc_command_ack";
  doc["command_id"] = commandId;
  doc["action"] = action;
  doc["farm_key"] = FARM_KEY;
  doc["device_id"] = "velxio-virtual-pump-01";
  doc["source"] = "velxio_synthetic";
  doc["synthetic"] = true;
  doc["applied"] = verified;
  doc["verified"] = verified;
  doc["safe_mode_active"] = safeHold;
  JsonObject observed = doc["virtual_output"].to<JsonObject>();
  for (int i = 0; i < 8; ++i) observed[String("bit") + i] = outputBits[i];
  uint8_t out[512];
  size_t n = serializeJson(doc, out, sizeof(out));
  if (!mqtt.publish(ackTopic().c_str(), out, static_cast<unsigned int>(n), false)) {
    Serial.printf("ACK publish failed for command_id=%s\n", commandId);
  }
  if (beep) {
    // Make command feedback audible in a live demo; failed verification gets a longer low tone.
    playBeep(verified ? 1650 : 500, verified ? 380 : 650);
  }
  Serial.printf("ACK %s; virtual pumps on=%d/7, safe_hold=%d\n", commandId,
                outputBits[0] + outputBits[1] + outputBits[2] + outputBits[3] +
                outputBits[4] + outputBits[5] + outputBits[6], safeHold ? 1 : 0);
}

void sendProfileAck(JsonDocument &cmd, bool applied) {
  JsonDocument ack;
  ack["event"] = "virtual_device_profile_ack";
  ack["command_id"] = cmd["command_id"] | "";
  ack["action"] = "SET_PROFILE";
  ack["farm_key"] = FARM_KEY;
  ack["device_id"] = "velxio-virtual-pump-01";
  ack["node_id"] = "node2";
  ack["incident_id"] = cmd["incident_id"] | "";
  ack["scenario_run_id"] = cmd["scenario_run_id"] | "";
  ack["scenario_code"] = cmd["scenario_code"] | "";
  ack["profile"] = profileName;
  ack["dataset_id"] = profileName == "normal" ? "node2-normal-v1" : "node2-fault-v1";
  ack["applied"] = applied; ack["verified"] = applied;
  ack["safe_mode_active"] = safeHold; ack["source"] = "velxio_synthetic"; ack["synthetic"] = true;
  JsonObject observed = ack["virtual_output"].to<JsonObject>();
  for (int i = 0; i < 8; ++i) observed[String("bit") + i] = i < 7 ? outputBits[i] : 0;
  uint8_t out[1024]; size_t n = serializeJson(ack, out, sizeof(out));
  bool sent = mqtt.publish(ackTopic().c_str(), out, static_cast<unsigned int>(n), false);
  // Make the scenario change visible and audible as soon as it is applied.
  // Fault profile: red SAFE HOLD LED + two low alarm beeps. Normal profile:
  // outputs stay OFF, red LED clears, and one short high confirmation beep.
  if (applied) {
    if (profileName == "fault") {
      playBeep(700, 130);
      delay(90);
      playBeep(700, 130);
    } else {
      playBeep(1650, 110);
    }
  }
  Serial.printf("PROFILE ACK %s -> %s applied=%d sent=%d bytes=%u; pumps remain OFF\n",
                (const char *)(cmd["command_id"] | ""), profileName.c_str(), applied, sent, (unsigned)n);
}

void onMessage(char *topic, byte *payload, unsigned int length) {
  if (commandTopic() != topic || length == 0 || length > 1024) return;
  JsonDocument doc;
  if (deserializeJson(doc, payload, length)) return;
  if (String((const char *)(doc["farm_key"] | "")) != FARM_KEY) return;
  String target = doc["target_device_id"] | "";
  if (target.length() && target != "velxio-virtual-pump-01" && target != "node2") return;
  String commandId = doc["command_id"] | "";
  if (commandId.length() == 0 || commandId.length() > 128) return;
  String action = doc["action"] | "SET_OUTPUTS";
  if (action == "SET_PROFILE") {
    String requested = doc["profile"] | "";
    if (requested != "normal" && requested != "fault") { sendProfileAck(doc, false); return; }
    const bool wasFault = profileName == "fault";
    profileName = requested;
    activeScenario = doc["scenario_code"] | "";
    activeRunId = doc["scenario_run_id"] | "";
    activeIncidentId = doc["incident_id"] | "";
    // A2 holds outputs at zero (HOLD LED). A4 keeps applying commands, only the ACK is withheld.
    safeHold = requested == "fault" && !isA4Scenario();
    for (int i = 0; i < 8; ++i) outputBits[i] = 0;
    applyOutputs();
    logSafetyChange(safeHold ? "HOLD" : "CLEAR", requested == "fault" ? "profile_fault" : "profile_normal", commandId.c_str());
    if (requested == "fault") {
      faultStartedMs = millis();
      Serial.printf("DRILL ALERT profile=fault scenario_code=%s scenario_run_id=%s\n",
                    activeScenario.c_str(), activeRunId.c_str());
    } else if (wasFault) {
      Serial.printf("DRILL RESTORED scenario_run_id=%s\n", activeRunId.c_str());
    }
    lastCommandId = commandId;
    sendProfileAck(doc, true);
    return;
  }
  if (action != "SET_OUTPUTS" && action != "HOLD" && action != "CLEAR") return;

  bool hasBit = false;
  for (int i = 0; i < 8; ++i) {
    String key = String("bit") + i;
    if (!doc[key].isNull()) {
      hasBit = true;
      if (!doc[key].is<int>() && !doc[key].is<bool>()) return;
      int requested = doc[key].as<int>();
      if (requested != 0 && requested != 1) return;
    }
  }
  if (action == "SET_OUTPUTS" && !hasBit) return;

  if (action == "HOLD") {
    safeHold = true;
    for (int i = 0; i < 8; ++i) outputBits[i] = 0;
    logSafetyChange("HOLD", "hold_command", commandId.c_str());
  } else if (action == "CLEAR") {
    safeHold = false;
    for (int i = 0; i < 8; ++i) outputBits[i] = 0;
    logSafetyChange("CLEAR", "clear_command", commandId.c_str());
  } else if (!safeHold) {
    for (int i = 0; i < 8; ++i) {
      String key = String("bit") + i;
      if (!doc[key].isNull()) outputBits[i] = doc[key].as<int>();
    }
  }
  applyOutputs();

  bool verified = true;
  for (int i = 0; i < 8; ++i) {
    String key = String("bit") + i;
    if (!doc[key].isNull() && outputBits[i] != doc[key].as<int>()) verified = false;
    if (safeHold && !doc[key].isNull() && doc[key].as<int>() == 1) verified = false;
  }
  if (action == "HOLD") verified = safeHold;
  if (action == "CLEAR") verified = !safeHold;

  bool duplicate = commandId == lastCommandId;
  sendAck(commandId.c_str(), action.c_str(), verified, !duplicate);
  lastCommandId = commandId;
}

void maintainNetwork() {
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - lastWifiAttemptMs >= WIFI_RETRY_MS) {
      lastWifiAttemptMs = millis();
      WiFi.mode(WIFI_STA);
      WiFi.begin(WIFI_SSID);
      Serial.println("Wi-Fi reconnect requested; command loop remains responsive.");
    }
    return;
  }
  if (!mqtt.connected() && millis() - lastMqttAttemptMs >= MQTT_RETRY_MS) {
    lastMqttAttemptMs = millis();
    if (mqtt.connect("velxio-virtual-pump-01")) {
      mqtt.subscribe(commandTopic().c_str(), 1);
      Serial.println("MQTT connected; actuator command subscription active.");
    } else {
      Serial.printf("MQTT reconnect failed, state=%d; retrying.\n", mqtt.state());
    }
  }
  if (mqtt.connected()) mqtt.loop();
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 7; ++i) pinMode(OUTPUT_PINS[i], OUTPUT);
  pinMode(HOLD_LED, OUTPUT);
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  if (!ledcAttach(BUZZER_PIN, 2000, 8)) {
    Serial.println("LEDC buzzer attach failed; visual LED indicators remain available.");
  }
#else
  ledcSetup(BUZZER_CHANNEL, 2000, 8);
  ledcAttachPin(BUZZER_PIN, BUZZER_CHANNEL);
#endif
  applyOutputs();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMessage);
  mqtt.setBufferSize(1024);
  Serial.println("Virtual pump controller starting; all outputs are LEDs, no physical pump.");
}

void loop() {
  maintainNetwork();
  // Auto-revert: a fault profile with no SET_PROFILE normal for AUTO_REVERT_MS returns to normal.
  if (profileName == "fault" && millis() - faultStartedMs >= AUTO_REVERT_MS) {
    profileName = "normal";
    safeHold = false;
    for (int i = 0; i < 8; ++i) outputBits[i] = 0;
    applyOutputs();
    logSafetyChange("CLEAR", "auto_revert", lastCommandId.c_str());
    Serial.printf("DRILL AUTO_REVERT scenario_run_id=%s\n", activeRunId.c_str());
  }
}
