#include <DHTesp.h>
#include <PubSubClient.h>
#include <WiFi.h>

// Demo-only public channel. It carries synthetic telemetry and virtual
// commands only. Do not place broker credentials or private data here.
static const char *WIFI_SSID = "Wokwi-GUEST";
static const char *WIFI_PASSWORD = "";
static const char *MQTT_HOST = "broker.hivemq.com";
static const uint16_t MQTT_PORT = 1883;
static const char *CHANNEL = "greenhouse-a-7f38c2d1";
static const char *FARM_KEY = "greenhouse_a";
static const char *LOT_ID = "melon-lot-demo-001";

static const int DHT_PIN = 15;
static const int SOIL_POT_PIN = 34;
static const int NODE2_FAULT_SWITCH_PIN = 18;
static const int SAFE_HOLD_LED_PIN = 22;
static const int STAGE_EVENT_LED_PIN = 21;
static const int VIRTUAL_RELAY_LED_PIN = 23;
static const unsigned long STAGE_INTERVAL_MS = 15000;

static const char *GROWTH_STAGES[] = {
    "sowing", "seedling", "vegetative", "flowering_fruiting", "harvest"};
static const int GROWTH_STAGE_COUNT = sizeof(GROWTH_STAGES) / sizeof(GROWTH_STAGES[0]);

String telemetryTopic;
String commandTopic;
String traceabilityTopic;
String commandAckTopic;
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
DHTesp dht;
unsigned long lastPublishMs = 0;
unsigned long sampleNumber = 0;
char deviceBootId[17] = {0};
bool safeHold = false;
int growthStageIndex = -1;
unsigned long lastDailyCaptureMs = 0;
unsigned long simulatedDay = 0;

float bounded(float value, float low, float high) {
  if (value < low) return low;
  if (value > high) return high;
  return value;
}

void applyVirtualMode(bool hold) {
  safeHold = hold;
  digitalWrite(SAFE_HOLD_LED_PIN, hold ? HIGH : LOW);
  // This is only a simulated relay indicator. CLEAR shows the virtual output
  // is available again; it never controls a physical pump.
  digitalWrite(VIRTUAL_RELAY_LED_PIN, hold ? LOW : HIGH);
  Serial.printf("Virtual output: %s; no physical actuator is connected\n", hold ? "SAFE HOLD" : "READY");
}

void onMqttMessage(char *topic, byte *payload, unsigned int length) {
  if (commandTopic != topic) return;
  String body;
  body.reserve(length + 1);
  for (unsigned int i = 0; i < length; i++) body += (char)payload[i];
  Serial.printf("Received workflow command: %s\n", body.c_str());
  String commandId;
  int idStart = body.indexOf("\"command_id\":\"");
  if (idStart >= 0) {
    idStart += 13;
    int idEnd = body.indexOf('\"', idStart);
    if (idEnd > idStart) commandId = body.substring(idStart, idEnd);
  }
  String action;
  if (body.indexOf("\"action\":\"HOLD\"") >= 0) {
    applyVirtualMode(true);
    action = "HOLD";
  } else if (body.indexOf("\"action\":\"CLEAR\"") >= 0) {
    applyVirtualMode(false);
    action = "CLEAR";
  }
  if (action.length() && commandId.length()) {
    char ack[320];
    snprintf(ack, sizeof(ack),
             "{\"command_id\":\"%s\",\"action\":\"%s\",\"virtual_output\":\"%s\",\"device_id\":\"wokwi-esp32-1\",\"device_uptime_ms\":%lu,\"source\":\"wokwi_synthetic\",\"synthetic\":true}",
             commandId.c_str(), action.c_str(), safeHold ? "SAFE_HOLD" : "READY", millis());
    mqttClient.publish(commandAckTopic.c_str(), ack, false);
    Serial.printf("Virtual device ACK sent: command_id=%s output=%s\n", commandId.c_str(), safeHold ? "SAFE_HOLD" : "READY");
  }
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD, 6);
  Serial.print("Connecting to Wokwi-GUEST");
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print(".");
  }
  Serial.printf(" connected, IP=%s\n", WiFi.localIP().toString().c_str());
}

void connectMqtt() {
  while (!mqttClient.connected()) {
    String clientId = "smiot-wokwi-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    Serial.printf("Connecting to MQTT %s:%u ... ", MQTT_HOST, MQTT_PORT);
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println("connected");
      mqttClient.subscribe(commandTopic.c_str(), 1);
      // Start with outputs off until the bridge tells us the current monitor state.
      applyVirtualMode(true);
    } else {
      Serial.printf("failed, state=%d; retry in 3 seconds\n", mqttClient.state());
      delay(3000);
    }
  }
}

void publishTelemetry() {
  TempAndHumidity climate = dht.getTempAndHumidity();
  float airTemp = isnan(climate.temperature) ? 29.0f : climate.temperature;
  float airHumidity = isnan(climate.humidity) ? 78.0f : climate.humidity;

  int rawSoil = analogRead(SOIL_POT_PIN);
  float node1Soil = bounded((float)rawSoil * 100.0f / 4095.0f, 0.0f, 100.0f);
  // Slide switch defaults left (pin 1 connected to 2 = GND): inject the
  // flatline by default. Move right to connect pin 2 to 3V3 and recover.
  bool node2Fault = digitalRead(NODE2_FAULT_SWITCH_PIN) == LOW;
  float node2Soil = node2Fault ? 2.4f : bounded(node1Soil + random(-10, 11) / 10.0f, 0.0f, 100.0f);

  float node1SoilTemp = 27.0f + random(-5, 6) / 10.0f;
  float node2SoilTemp = 26.5f + random(-5, 6) / 10.0f;
  float node1Ec = 1.30f + random(-5, 6) / 100.0f;
  float node2Ec = 1.20f + random(-5, 6) / 100.0f;
  float node2AirTemp = airTemp + 0.5f;
  float node2AirHumidity = bounded(airHumidity + 2.0f, 0.0f, 100.0f);

  char payload[600];
  snprintf(
      payload, sizeof(payload),
      "{\"device_name\":\"Wokwi SMIOT Demo\",\"device_id\":\"wokwi-esp32-1\",\"boot_id\":\"%s\",\"sample_sequence\":%lu,\"device_uptime_ms\":%lu,\"farm_key\":\"%s\",\"id6\":{" 
      "\"node1\":{\"at\":%.1f,\"ah\":%.1f,\"st\":%.1f,\"sh\":%.1f,\"sec\":%.2f},"
      "\"node2\":{\"at\":%.1f,\"ah\":%.1f,\"st\":%.1f,\"sh\":%.1f,\"sec\":%.2f}}}",
      deviceBootId, sampleNumber + 1, millis(), FARM_KEY, airTemp, airHumidity, node1SoilTemp, node1Soil, node1Ec,
      node2AirTemp, node2AirHumidity, node2SoilTemp, node2Soil, node2Ec);

  if (mqttClient.publish(telemetryTopic.c_str(), payload, false)) {
    sampleNumber++;
    Serial.printf("sample=%lu; node1 soil=%.1f%%; node2 soil=%.1f%% (%s); mode=%s\n",
                  sampleNumber, node1Soil, node2Soil, node2Fault ? "FAULT INJECTED" : "normal",
                  safeHold ? "SAFE HOLD" : "READY");
  } else {
    Serial.println("MQTT telemetry publish failed");
  }
}

bool publishDailyPhotoEvent() {
  if (!mqttClient.connected()) return false;
  const unsigned long nextDay = simulatedDay + 1;
  const int stageIndex = min((int)nextDay - 1, GROWTH_STAGE_COUNT - 1);
  const char *stage = GROWTH_STAGES[stageIndex];
  char payload[512];
  snprintf(payload, sizeof(payload),
           "{\"event\":\"daily_photo_capture_simulated\",\"farm_key\":\"%s\",\"lot_id\":\"%s\","
           "\"simulated_day\":%lu,\"stage\":\"%s\",\"stage_index\":%d,"
           "\"simulated\":true,\"image_captured\":false,\"capture_kind\":\"synthetic_asset\","
           "\"image_asset_id\":\"smiot_melon_growth_contact_sheet_v1\",\"image_panel\":%d,"
           "\"uptime_ms\":%lu}",
           FARM_KEY, LOT_ID, nextDay, stage, stageIndex + 1, stageIndex + 1, millis());

  bool sent = mqttClient.publish(traceabilityTopic.c_str(), payload, false);
  if (!sent) {
    Serial.printf("Daily photo event publish failed; will retry for day %lu\n", nextDay);
    return false;
  }
  simulatedDay = nextDay;
  growthStageIndex = stageIndex;
  lastDailyCaptureMs = millis();
  digitalWrite(STAGE_EVENT_LED_PIN, HIGH);
  Serial.printf("Daily photo event sent: simulated day=%lu lot=%s stage=%s; bridge attaches synthetic JPEG; event=%s\n",
                simulatedDay, LOT_ID, stage, payload);
  delay(120);
  digitalWrite(STAGE_EVENT_LED_PIN, LOW);
  return true;
}

void setup() {
  snprintf(deviceBootId, sizeof(deviceBootId), "%08lx", (unsigned long)esp_random());
  Serial.begin(115200);
  pinMode(NODE2_FAULT_SWITCH_PIN, INPUT);
  pinMode(SAFE_HOLD_LED_PIN, OUTPUT);
  pinMode(STAGE_EVENT_LED_PIN, OUTPUT);
  pinMode(VIRTUAL_RELAY_LED_PIN, OUTPUT);
  pinMode(SOIL_POT_PIN, INPUT);
  applyVirtualMode(true);
  dht.setup(DHT_PIN, DHTesp::DHT22);
  analogReadResolution(12);
  randomSeed(esp_random());

  telemetryTopic = String("smiot/wokwi/") + CHANNEL + "/telemetry";
  commandTopic = String("smiot/wokwi/") + CHANNEL + "/command";
  commandAckTopic = String("smiot/wokwi/") + CHANNEL + "/command/ack";
  traceabilityTopic = String("smiot/wokwi/") + CHANNEL + "/traceability";
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  mqttClient.setCallback(onMqttMessage);
  mqttClient.setBufferSize(768);
  connectWifi();
  connectMqtt();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWifi();
  if (!mqttClient.connected()) connectMqtt();
  mqttClient.loop();

  // Wokwi time is accelerated: every 15 seconds represents one simulated day.
  if (simulatedDay == 0 || millis() - lastDailyCaptureMs >= STAGE_INTERVAL_MS) {
    publishDailyPhotoEvent();
  }

  if (millis() - lastPublishMs >= 10000) {
    lastPublishMs = millis();
    publishTelemetry();
  }
}
