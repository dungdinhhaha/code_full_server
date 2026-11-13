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
String commandTopic() { return String("smiot/velxio/") + CHANNEL + "/actuator/command"; }
String ackTopic() { return String("smiot/velxio/") + CHANNEL + "/actuator/ack"; }

void applyOutputs() {
  if (safeHold) for (int i = 0; i < 8; ++i) outputBits[i] = 0;
  for (int i = 0; i < 7; ++i) digitalWrite(OUTPUT_PINS[i], outputBits[i] ? HIGH : LOW);
  digitalWrite(HOLD_LED, safeHold ? HIGH : LOW);
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
  uint8_t out[512]; size_t n = serializeJson(ack, out, sizeof(out));
  mqtt.publish(ackTopic().c_str(), out, static_cast<unsigned int>(n), false);
  Serial.printf("PROFILE ACK %s -> %s applied=%d; pumps remain OFF\n",
                (const char *)(cmd["command_id"] | ""), profileName.c_str(), applied);
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
    profileName = requested;
    activeScenario = doc["scenario_code"] | "";
    activeRunId = doc["scenario_run_id"] | "";
    activeIncidentId = doc["incident_id"] | "";
    safeHold = requested == "fault";
    for (int i = 0; i < 8; ++i) outputBits[i] = 0;
    applyOutputs();
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
  } else if (action == "CLEAR") {
    safeHold = false;
    for (int i = 0; i < 8; ++i) outputBits[i] = 0;
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
}
