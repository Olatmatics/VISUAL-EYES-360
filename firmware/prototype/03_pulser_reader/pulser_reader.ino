/*
 * VISUAL EYES 360 - PROTOTYPE BOARD 3: PULSER READER
 * Counts pulses on GPIO 27 (from board 4 simulator or the optocoupler circuit)
 * and posts them to the backend. Serial 115200.
 *
 * Serial commands: HELP | COUNT | RESET | RATE <n> | SEND | STATUS
 * RATE = pulses per litre (bench default 1; set from real pulser datasheet).
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";
const char* BACKEND   = "http://192.168.1.100:8000";
const char* DEVICE_UID = "PULSE-DEV-01";

#define PULSE_PIN 27
volatile unsigned long pulses = 0;
unsigned long lastDebounce = 0;
unsigned long eventNo = 0;
unsigned long lastSend = 0;
float pulsesPerLitre = 1.0;

void IRAM_ATTR onPulse() {
  unsigned long now = micros();
  if (now - lastDebounce > 3000) {   // 3ms debounce
    pulses++; lastDebounce = now;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PULSE_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PULSE_PIN), onPulse, FALLING);
  WiFi.mode(WIFI_STA); WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nREADY. Type HELP for commands.");
}

void sendPulses() {
  if (WiFi.status() != WL_CONNECTED) { Serial.println("[HTTP] wifi offline"); return; }
  StaticJsonDocument<512> doc;
  doc["device_uid"] = DEVICE_UID;
  doc["kind"] = "PULSE";
  doc["event_id"] = "PULSE" + String(eventNo++);
  JsonObject r = doc.createNestedObject("readings");
  r["raw_pulse_count"] = pulses;
  r["pulses_per_litre"] = pulsesPerLitre;
  r["pulser_volume_l"] = (float)pulses / pulsesPerLitre;
  String body; serializeJson(doc, body);
  HTTPClient http; http.begin(String(BACKEND) + "/api/v1/device/prototype/telemetry");
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(body);
  Serial.printf("[HTTP] pulses -> %d : %s\n", code, http.getString().c_str());
  http.end();
}

void loop() {
  if (Serial.available()) {
    String c = Serial.readStringUntil('\n'); c.trim();
    if (c == "HELP") Serial.println("COUNT | RESET | RATE <n> | SEND | STATUS");
    else if (c == "COUNT") Serial.printf("[COUNT] %lu pulses = %.2f L\n", pulses, (float)pulses / pulsesPerLitre);
    else if (c == "RESET") { pulses = 0; Serial.println("[COUNT] reset"); }
    else if (c.startsWith("RATE ")) { pulsesPerLitre = c.substring(5).toFloat(); Serial.printf("[RATE] %.2f pulses/L\n", pulsesPerLitre); }
    else if (c == "SEND") sendPulses();
    else if (c == "STATUS") Serial.printf("UID=%s PPL=%.2f WIFI=%s\n", DEVICE_UID, pulsesPerLitre, WiFi.status()==WL_CONNECTED?"OK":"OFF");
  }
  if (millis() - lastSend > 10000) { lastSend = millis(); sendPulses(); }
  delay(20);
}
