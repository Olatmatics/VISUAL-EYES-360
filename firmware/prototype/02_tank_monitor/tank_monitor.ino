/*
 * VISUAL EYES 360 - PROTOTYPE BOARD 2: TANK MONITOR
 * Ultrasonic level + DHT11 temperature/humidity + lid limit switch.
 * Serial 115200. Libraries: DHT sensor library (Adafruit).
 *
 * Serial commands: HELP | READ | SEND | STATUS | LID
 *
 * HC-SR04 ECHO is 5V -> use a 2k2/3k3 divider to ESP32 GPIO (see wiring guide).
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";
const char* BACKEND   = "http://172.25.0.37:8000";   // change to your PC IP if different
const char* DEVICE_UID = "TANK-DEV-01";
const char* TANK_ID    = "YOUR_TANK_ID";

#define TRIG_PIN 5
#define ECHO_PIN 18
#define DHT_PIN  4
#define LIMIT_PIN 19
#define DHTTYPE DHT11
DHT dht(DHT_PIN, DHTTYPE);

const float TANK_HEIGHT_CM = 200.0;   // calibrate to your tank
const float TANK_CAPACITY_L = 30000.0;
unsigned long lastSend = 0;
unsigned long eventNo = 0;

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT); pinMode(ECHO_PIN, INPUT); pinMode(LIMIT_PIN, INPUT_PULLUP);
  dht.begin();
  WiFi.mode(WIFI_STA); WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nREADY. Type HELP for commands.");
}

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW); delayMicroseconds(4);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(12); digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) return -1;
  return duration * 0.0343 / 2.0;
}

String telemetryJson(float level, float volume, float temp, float hum, bool lidOpen) {
  StaticJsonDocument<512> doc;
  doc["device_uid"] = DEVICE_UID;
  doc["kind"] = "TANK";
  doc["event_id"] = "TANK" + String(eventNo++);
  doc["tank_id"] = TANK_ID;
  JsonObject r = doc.createNestedObject("readings");
  r["fuel_level_cm"] = level;
  r["fuel_volume_l"] = volume;
  r["temperature_c"] = temp;
  r["humidity_pct"] = hum;
  r["lid_open"] = lidOpen;
  String out; serializeJson(doc, out); return out;
}

void sendTelemetry(float level, float volume, float temp, float hum, bool lidOpen) {
  if (WiFi.status() != WL_CONNECTED) { Serial.println("[HTTP] wifi offline"); return; }
  HTTPClient http; http.begin(String(BACKEND) + "/api/v1/device/prototype/telemetry");
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(telemetryJson(level, volume, temp, hum, lidOpen));
  Serial.printf("[HTTP] telemetry -> %d : %s\n", code, http.getString().c_str());
  http.end();
}

void readAndPrint() {
  float dist = readDistanceCm();
  float level = (dist < 0) ? 0 : constrain(TANK_HEIGHT_CM - dist, 0, TANK_HEIGHT_CM);
  float volume = level / TANK_HEIGHT_CM * TANK_CAPACITY_L;
  float temp = dht.readTemperature();
  float hum = dht.readHumidity();
  bool lid = digitalRead(LIMIT_PIN) == LOW;
  Serial.printf("[TANK] distance=%.1fcm level=%.1fcm volume=%.0fL temp=%.1fC hum=%.0f%% lid=%s\n",
                dist, level, volume, temp, hum, lid ? "OPEN" : "CLOSED");
}

void loop() {
  if (Serial.available()) {
    String c = Serial.readStringUntil('\n'); c.trim();
    if (c == "HELP") Serial.println("READ | SEND | STATUS | LID");
    else if (c == "READ") readAndPrint();
    else if (c == "SEND") { readAndPrint(); sendTelemetry(
      constrain(TANK_HEIGHT_CM - readDistanceCm(), 0, TANK_HEIGHT_CM),
      (constrain(TANK_HEIGHT_CM - readDistanceCm(), 0, TANK_HEIGHT_CM) / TANK_HEIGHT_CM) * TANK_CAPACITY_L,
      dht.readTemperature(), dht.readHumidity(), digitalRead(LIMIT_PIN) == LOW); }
    else if (c == "STATUS") Serial.printf("UID=%s TANK=%s WIFI=%s\n", DEVICE_UID, TANK_ID, WiFi.status()==WL_CONNECTED?"OK":"OFF");
    else if (c == "LID") Serial.println(digitalRead(LIMIT_PIN) == LOW ? "LID OPEN" : "LID CLOSED");
  }
  if (millis() - lastSend > 15000) {
    lastSend = millis();
    float dist = readDistanceCm();
    float level = (dist < 0) ? 0 : constrain(TANK_HEIGHT_CM - dist, 0, TANK_HEIGHT_CM);
    sendTelemetry(level, level / TANK_HEIGHT_CM * TANK_CAPACITY_L,
                  dht.readTemperature(), dht.readHumidity(), digitalRead(LIMIT_PIN) == LOW);
  }
  delay(100);
}
