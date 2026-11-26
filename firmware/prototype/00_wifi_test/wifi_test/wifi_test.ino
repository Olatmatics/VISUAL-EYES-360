/*
 * VISUAL EYES 360 - MINIMAL Wi-Fi TEST (diagnostic only)
 * ESP32 DevKit v1, Serial 115200. NOT part of the normal bench firmware.
 *
 * Upload this INSTEAD of a board sketch only while diagnosing a board that
 * freezes at WiFi.begin(). It does nothing except join Wi-Fi and call /health.
 * If this sketch works but the board sketch does not, the problem is in the
 * board sketch setup order. If this sketch also freezes, erase the ESP32 flash.
 */

#include <WiFi.h>
#include <HTTPClient.h>

static const char* WIFI_SSID = "cypher";
static const char* WIFI_PASS = "12345678";
static const char* BACKEND  = "http://172.25.0.37:8000";

unsigned long lastDot = 0;
unsigned long lastPing = 0;
unsigned long dots = 0;

void pingBackend() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[PING] Wi-Fi offline");
    return;
  }
  HTTPClient http;
  http.begin(String(BACKEND) + "/health");
  http.setConnectTimeout(4000);
  http.setTimeout(6000);
  int code = http.GET();
  String body = http.getString();
  http.end();
  Serial.printf("[PING] GET /health -> %d  %s\n", code, body.c_str());
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("---- VISUAL EYES 360 MINIMAL WIFI TEST ----");
  Serial.printf("SSID=%s  BACKEND=%s\n", WIFI_SSID, BACKEND);
  Serial.println("[BOOT] serial ready");
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.println("[WIFI] begin called");
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    if (lastPing == 0 || millis() - lastPing >= 5000) {
      lastPing = millis();
      Serial.print("[WIFI] OK IP=");
      Serial.println(WiFi.localIP().toString());
      pingBackend();
    }
  } else {
    if (millis() - lastDot >= 500) {
      lastDot = millis();
      Serial.print(".");
      if (++dots >= 24) {
        dots = 0;
        Serial.printf(" status=%d\n", (int)WiFi.status());
      }
    }
  }

  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    line.toUpperCase();
    if (line == "PING") pingBackend();
    else if (line == "STATUS") {
      Serial.printf("[STATUS] WiFi=%s IP=%s RSSI=%d dBm\n",
                    WiFi.status() == WL_CONNECTED ? "OK" : "OFFLINE",
                    WiFi.localIP().toString().c_str(),
                    WiFi.RSSI());
    } else if (line == "REBOOT") {
      ESP.restart();
    } else if (line == "HELP") {
      Serial.println("HELP | STATUS | PING | REBOOT");
    }
  }
}
