#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <ArduinoJson.h>

static const char *WIFI_SSID = "Velxio-GUEST";
static const char *MQTT_HOST = "broker.hivemq.com";
static const uint16_t MQTT_PORT = 1883;
static const char *CHANNEL = "smiot-course-20261112-a91d4b";
static const char *FARM_KEY = "greenhouse_j";
// The Velxio circuit wires DHT22 SDA to ESP32 GPIO15.
static const int DHT_PIN = 15;
static const int SOIL_PIN = 34;
static const int ALERT_LED_PIN = 23;
static const int BUZZER_PIN = 22;
static const char *DEVICE_ID = "velxio-node1";

WiFiClient net;
PubSubClient mqtt(net);
DHT dht(DHT_PIN, DHT22);
unsigned long lastSample = 0;
unsigned long sequenceNo = 0;
bool previousAlert = false;
char bootId[20] = {0};
String profileName = "normal";
String activeScenario = "";
String activeRunId = "";
String activeIncidentId = "";
String lastCommandId = "";

String topic() { return String("smiot/velxio/") + CHANNEL + "/sensor/node1"; }
String commandTopic() { return String("smiot/velxio/") + CHANNEL + "/actuator/command"; }
String ackTopic() { return String("smiot/velxio/") + CHANNEL + "/actuator/ack"; }

void sendProfileAck(JsonDocument &cmd, bool applied) {
  JsonDocument ack;
  ack["event"] = "virtual_device_profile_ack"; ack["device_id"] = DEVICE_ID;
  ack["node_id"] = "node1"; ack["farm_key"] = FARM_KEY;
  ack["command_id"] = cmd["command_id"] | ""; ack["incident_id"] = cmd["incident_id"] | "";
  ack["scenario_run_id"] = cmd["scenario_run_id"] | ""; ack["scenario_code"] = cmd["scenario_code"] | "";
  ack["profile"] = profileName; ack["dataset_id"] = profileName == "normal" ? "node1-normal-v1" : "node1-fault-v1";
  ack["applied"] = applied; ack["verified"] = applied; ack["source"] = "velxio_synthetic"; ack["synthetic"] = true;
  JsonObject outputs = ack["virtual_output"].to<JsonObject>();
  for (int i = 0; i < 8; ++i) outputs[String("bit") + i] = 0;
  uint8_t out[512]; size_t n = serializeJson(ack, out, sizeof(out));
  mqtt.publish(ackTopic().c_str(), out, static_cast<unsigned int>(n), false);
  Serial.printf("PROFILE ACK %s -> %s applied=%d\n", (const char *)(cmd["command_id"] | ""), profileName.c_str(), applied);
}

void onMessage(char *receivedTopic, byte *payload, unsigned int length) {
  if (commandTopic() != receivedTopic || !length || length > 1024) return;
  JsonDocument cmd; if (deserializeJson(cmd, payload, length)) return;
  if (String((const char *)(cmd["farm_key"] | "")) != FARM_KEY) return;
  String target = cmd["target_device_id"] | "";
  if (target.length() && target != DEVICE_ID && target != "node1") return;
  String id = cmd["command_id"] | "";
  if (!id.length() || id == lastCommandId) return;
  if (String((const char *)(cmd["action"] | "")) != "SET_PROFILE") return;
  String requested = cmd["profile"] | "";
  if (requested != "normal" && requested != "fault") { sendProfileAck(cmd, false); return; }
  profileName = requested; activeScenario = cmd["scenario_code"] | "";
  activeRunId = cmd["scenario_run_id"] | ""; activeIncidentId = cmd["incident_id"] | "";
  lastCommandId = id; sendProfileAck(cmd, true);
}

void connectNetwork() {
  static unsigned long lastAttempt = 0;
  if (millis() - lastAttempt < 3000) return;
  lastAttempt = millis();
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID);
    Serial.println("WiFi reconnect requested");
    return;
  }
  if (!mqtt.connected()) {
    String clientId = String("velxio-node1-") + String((uint32_t)ESP.getEfuseMac(), HEX);
    if (mqtt.connect(clientId.c_str())) { mqtt.subscribe(commandTopic().c_str(), 1); Serial.println("MQTT connected; profile commands active"); }
    else { Serial.print("MQTT connect failed, state="); Serial.println(mqtt.state()); }
  }
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  pinMode(ALERT_LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(ALERT_LED_PIN, LOW);
  snprintf(bootId, sizeof(bootId), "%08lx-%04x",
           (unsigned long)(ESP.getEfuseMac() >> 16), (unsigned int)(esp_random() & 0xffff));
  randomSeed(esp_random());
  dht.begin();
  delay(2000);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMessage);
  mqtt.setBufferSize(512);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID);
  Serial.println("Node 1 started; waiting for sensor and MQTT.");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED || !mqtt.connected()) connectNetwork();
  if (mqtt.connected()) mqtt.loop();
  if (millis() - lastSample < 10000) return;
  lastSample = millis();

  float at = dht.readTemperature();
  float ah = dht.readHumidity();
  if ((isnan(at) || isnan(ah)) && profileName != "fault") {
    digitalWrite(ALERT_LED_PIN, HIGH);
    if (!previousAlert) tone(BUZZER_PIN, 500, 300);
    previousAlert = true;
    Serial.println("DHT22 read failed; sample omitted instead of publishing fabricated values.");
    return;
  }
  if (profileName == "fault" && (isnan(at) || isnan(ah))) { at = 38.0f; ah = 82.0f; }
  float sh = (float)analogRead(SOIL_PIN) * 100.0f / 4095.0f;
  float st = 27.0f + (float)random(-5, 6) / 10.0f;
  float sec = 1.30f + (float)random(-5, 6) / 100.0f;
  if (profileName == "fault") {
    if (activeScenario == "W7" || activeScenario == "soil_spike" || activeScenario == "soil_flatline") sh = 8.0f;
    else if (activeScenario == "W8" || activeScenario == "vpd_ec_risk") { at = 39.0f; ah = 88.0f; sec = 3.8f; }
    else { at = 38.0f; ah = 82.0f; sh = 12.0f; }
  }
  bool alert = at >= 32.0f || ah >= 75.0f || sh <= 15.0f;
  digitalWrite(ALERT_LED_PIN, alert ? HIGH : LOW);
  if (alert && !previousAlert) tone(BUZZER_PIN, 1800, 180);
  previousAlert = alert;
  const unsigned long sampleSeq = ++sequenceNo;
  char payload[700];
  snprintf(payload, sizeof(payload),
    "{\"farm_key\":\"%s\",\"device_id\":\"velxio-node1\",\"node_id\":\"node1\",\"boot_id\":\"%s\",\"sequence\":%lu,\"sample_sequence\":%lu,\"device_uptime_ms\":%lu,\"at\":%.1f,\"ah\":%.1f,\"st\":%.1f,\"sh\":%.1f,\"sec\":%.2f,\"alert\":%s,\"profile\":\"%s\",\"dataset_id\":\"%s\",\"scenario_code\":\"%s\",\"scenario_run_id\":\"%s\",\"incident_id\":\"%s\",\"source\":\"velxio_synthetic\",\"synthetic\":true}",
    FARM_KEY, bootId, sampleSeq, sampleSeq, millis(), at, ah, st, sh, sec,
    alert ? "true" : "false", profileName.c_str(), profileName == "normal" ? "node1-normal-v1" : "node1-fault-v1",
    activeScenario.c_str(), activeRunId.c_str(), activeIncidentId.c_str());
  Serial.println(payload);
  if (mqtt.connected()) {
    if (mqtt.publish(topic().c_str(), payload, false)) Serial.println("MQTT publish OK");
    else Serial.println("MQTT publish failed");
  } else Serial.println("MQTT offline; sample not sent");
}
