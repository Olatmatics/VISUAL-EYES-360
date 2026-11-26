/*
 * VISUAL EYES 360 - BOARD 3: INDEPENDENT PULSE COUNTER (separate ESP32)
 * Bench prototype. Serial 115200. NOT intrinsically safe.
 *
 * This board only counts pump pulses and converts them to raw fuel volume.
 * It is independent of the FCC/payment board. Configure and test it all from
 * Serial Monitor — no code editing needed at the bench.
 *
 * SETUP COMMANDS (saved, survive power cycle):
 *   SET WIFI ssid|password
 *   SET BACKEND http://172.25.0.37:8000
 *   SET DEVICE PULSE-DEV-01          this board's UID
 *   SET FCC fcc-matics-001           FCC whose MATH setting to use
 *   SET NOZZLE <nozzle id>
 *   SET PPL <pulses per litre>       also saved to backend web MATH setting
 *   SET PPS <pulses per second>      expected pump pulse rate (bench math)
 *   CONFIG | JSON ON|OFF | REBOOT
 *
 * TEST / MATH COMMANDS:
 *   HELP | COUNT | RESET | STATUS | CAL FETCH | CAL SET <ppl>
 *   MATH <pulses>        convert pulses to litres
 *   MATH RATE <pps>      convert pulse rate to litres/sec and litres/min
 *   MATH PPS             measured vs configured pulse rate
 *   SEND                 post one telemetry reading now
 *
 * Formula used everywhere: litres = raw_pulse_count / pulses_per_litre
 *
 * LEDs: GPIO2 (onboard) = Wi-Fi status. Steady ON when connected, slow blink
 * while connecting. GPIO22 + 220R = backend activity, blinks very fast on
 * every telemetry send, calibration read/write and response.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <string.h>

Preferences prefs;

const char* DEF_WIFI_SSID  = "cypher";
const char* DEF_WIFI_PASS  = "12345678";
const char* DEF_BACKEND    = "http://172.25.0.37:8000";
const char* DEF_DEVICE     = "PULSE-DEV-01";
const char* DEF_FCC        = "fcc-matics-001";
const char* DEF_NOZZLE     = "YOUR_NOZZLE_ID";
const char* FIRMWARE       = "ve360-pulser-bench-1.1";

#define WIFI_LED_PIN 2      // onboard LED: Wi-Fi status
#define COMM_LED_PIN 22     // add LED + 220R to GND: backend activity
#define PULSE_PIN 27
volatile unsigned long pulses = 0;
unsigned long lastDebounce = 0;
unsigned long lastWindow = 0;
unsigned long pulsesAtWindow = 0;
unsigned long eventNo = 0;
unsigned long lastSend = 0;

String wifiSsid, wifiPass, backendUrl, deviceUid, fccUid, nozzleId;
float pulsesPerLitre = 100.0;
float expectedPps = 0;
float measuredPps = 0;
bool jsonEcho = true;

unsigned long commUntil = 0;
unsigned long commToggleAt = 0;
unsigned long wifiBlinkAt = 0;
bool commLedOn = false;
bool wifiLedOn = false;

unsigned long lastWifiRetry = 0;
unsigned long lastWifiDot = 0;
unsigned long wifiDots = 0;
bool wifiWasConnected = false;

// Explicit prototypes. Arduino IDE sometimes misses IRAM_ATTR interrupt ISRs.
void fetchCalibration();
void printNetwork();
void pingBackend();
void IRAM_ATTR onPulse();

String cfg(const char* key, const char* def) {
  String v = prefs.getString(key, "");
  return v.length() ? v : String(def);
}
void saveCfg(const char* key, const String& v) { prefs.putString(key, v); }

// ---- LED status helpers -----------------------------------------------------
void markBackendActivity(unsigned long holdMs = 700) {
  unsigned long now = millis();
  commUntil = now + holdMs;
  commToggleAt = now + 40;
  commLedOn = true;
  digitalWrite(COMM_LED_PIN, HIGH);
}

void updateLeds() {
  unsigned long now = millis();

  if (WiFi.status() == WL_CONNECTED) {
    wifiLedOn = true;
    digitalWrite(WIFI_LED_PIN, HIGH);
  } else if (now >= wifiBlinkAt) {
    wifiLedOn = !wifiLedOn;
    wifiBlinkAt = now + 500;
    digitalWrite(WIFI_LED_PIN, wifiLedOn ? HIGH : LOW);
  }

  if (now < commUntil) {
    if (now >= commToggleAt) {
      commLedOn = !commLedOn;
      digitalWrite(COMM_LED_PIN, commLedOn ? HIGH : LOW);
      commToggleAt = now + 35;
    }
  } else if (commLedOn) {
    commLedOn = false;
    digitalWrite(COMM_LED_PIN, LOW);
  }
}

void loadConfig() {
  prefs.begin("ve360-pulse", false);
  wifiSsid     = cfg("ssid", DEF_WIFI_SSID);
  wifiPass     = cfg("pass", DEF_WIFI_PASS);
  backendUrl   = cfg("backend", DEF_BACKEND);
  deviceUid    = cfg("dev", DEF_DEVICE);
  fccUid       = cfg("fcc", DEF_FCC);
  nozzleId     = cfg("nozzle", DEF_NOZZLE);
  pulsesPerLitre = prefs.getFloat("ppl", pulsesPerLitre);
  expectedPps    = prefs.getFloat("pps", 0);
  jsonEcho       = prefs.getBool("json", true);
}

void printNetwork() {
  bool up = WiFi.status() == WL_CONNECTED;
  Serial.println("---- NETWORK ----");
  Serial.printf("SSID=%s  PASS=%s\n", wifiSsid.c_str(), wifiPass.length() ? "********" : "(empty)");
  Serial.printf("STATUS=%s  IP=%s  RSSI=%d dBm\n", up ? "CONNECTED" : "OFFLINE",
                up ? WiFi.localIP().toString().c_str() : "-", WiFi.RSSI());
  Serial.printf("BACKEND=%s\n", backendUrl.c_str());
  Serial.println("-----------------");
}

void pingBackend() {
  if (WiFi.status() != WL_CONNECTED) { Serial.println("[PING] WiFi offline — type WIFI to retry"); return; }
  HTTPClient http;
  http.begin(backendUrl + "/health");
  http.setConnectTimeout(4000);
  http.setTimeout(6000);
  markBackendActivity(1000);
  int code = http.GET();
  String body = http.getString();
  http.end();
  Serial.printf("[PING] GET /health -> %d  %s\n", code, body.c_str());
}

void ensureWiFi() {
  bool up = WiFi.status() == WL_CONNECTED;
  if (up != wifiWasConnected) {
    wifiWasConnected = up;
    wifiDots = 0;
    lastWifiDot = millis();
    if (up) {
      Serial.println();
      Serial.print("[WIFI] Connected IP="); Serial.println(WiFi.localIP().toString());
      fetchCalibration();
    } else {
      Serial.println("[WIFI] Link lost — reconnecting");
    }
  }
  if (!up) {
    if (millis() - lastWifiDot >= 500) {
      lastWifiDot = millis();
      Serial.print(".");
      if (++wifiDots >= 24) {
        wifiDots = 0;
        Serial.printf(" status=%d\n", (int)WiFi.status());
      }
    }
    if (millis() - lastWifiRetry >= 10000) {
      lastWifiRetry = millis();
      Serial.print("\n[WIFI] Retry ");
      WiFi.reconnect();
      Serial.printf("status=%d\n", (int)WiFi.status());
    }
  }
}

void connectWiFi() {
  Serial.println("[WIFI] init STA");
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);
  if (wifiSsid.length() == 0 || wifiSsid == "YOUR_WIFI") {
    Serial.println("[WIFI] Not configured. Type: SET WIFI ssid|password");
    return;
  }
  Serial.printf("[WIFI] Connecting to '%s' (backend %s)\n", wifiSsid.c_str(), backendUrl.c_str());
  WiFi.begin(wifiSsid.c_str(), wifiPass.c_str());
  wifiWasConnected = false;
  lastWifiDot = millis();
  lastWifiRetry = millis();
  Serial.println("[WIFI] Started — progress dots appear while connecting. Serial stays live.");
  Serial.println("[WIFI] Check: SSID must be 2.4 GHz, password correct, router near board.");
}

void setup() {
  Serial.begin(115200);
  pinMode(WIFI_LED_PIN, OUTPUT); pinMode(COMM_LED_PIN, OUTPUT);
  pinMode(PULSE_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PULSE_PIN), onPulse, FALLING);
  Serial.println("[BOOT] pulse input ready");
  loadConfig();
  Serial.println("[BOOT] config loaded");
  connectWiFi();
  Serial.println("[BOOT] Wi-Fi started (non-blocking)");
  Serial.println("READY. Type HELP for commands.");
}

void IRAM_ATTR onPulse() {
  unsigned long now = micros();
  if (now - lastDebounce > 3000) { pulses++; lastDebounce = now; }
}

void echoJson(const char* tag, const String& body) {
  if (jsonEcho) Serial.printf("[JSON %s] %s\n", tag, body.c_str());
}

String requestJson(const char* method, const char* path, const String& body) {
  if (WiFi.status() != WL_CONNECTED) return "{\"error\":\"wifi_offline\"}";
  markBackendActivity(1200);
  HTTPClient http;
  http.begin(backendUrl + path);
  http.setConnectTimeout(4000);
  http.setTimeout(6000);
  http.addHeader("Content-Type", "application/json");
  int code = strcmp(method, "GET") == 0 ? http.GET() : http.sendRequest(method, body);
  String res = http.getString();
  http.end();
  markBackendActivity(600);
  echoJson("OUT", body.length() ? body : String("GET ") + path);
  Serial.printf("[HTTP] %s %s -> %d\n", method, path, code);
  echoJson("IN", res);
  return res;
}

void fetchCalibration() {
  String res = requestJson("GET", ("/api/v1/fcc/calibration?device_uid=" + fccUid).c_str(), "");
  DynamicJsonDocument parsed(1024);
  if (!deserializeJson(parsed, res)) {
    float ppl = parsed["pulses_per_litre"] | 0;
    if (ppl > 0) {
      pulsesPerLitre = ppl;
      markBackendActivity(1000);   // setting received from backend
      Serial.printf("[MATH] Pulses per litre loaded from web setting: %.3f\n", ppl);
    }
  }
}

void calSet(float ppl) {
  if (ppl <= 0) { Serial.println("ERR: pulses per litre must be greater than zero"); return; }
  StaticJsonDocument<256> doc;
  doc["device_uid"] = fccUid;
  doc["pulses_per_litre"] = ppl;
  String body; serializeJson(doc, body);
  Serial.println("[MATH] " + requestJson("PATCH", "/api/v1/fcc/calibration", body));
  pulsesPerLitre = ppl;
  prefs.putFloat("ppl", ppl);
}

void sendTelemetry() {
  StaticJsonDocument<512> doc;
  doc["device_uid"] = deviceUid;
  doc["kind"] = "PULSE";
  doc["event_id"] = "PULSE" + String(eventNo++);
  doc["fcc_device_uid"] = fccUid;
  doc["nozzle_id"] = nozzleId;
  JsonObject r = doc.createNestedObject("readings");
  r["raw_pulse_count"] = pulses;
  r["pulses_per_litre"] = pulsesPerLitre;
  r["pulser_volume_l"] = (float)pulses / pulsesPerLitre;
  r["pulses_per_second"] = measuredPps;
  r["configured_pulses_per_second"] = expectedPps;
  r["litres_per_second"] = expectedPps > 0 ? expectedPps / pulsesPerLitre : measuredPps / pulsesPerLitre;
  r["firmware_version"] = FIRMWARE;
  r["source"] = "INDEPENDENT_PULSER_ESP32";
  String body; serializeJson(doc, body);
  Serial.println("[PULSE] " + requestJson("POST", "/api/v1/device/prototype/telemetry", body));
}

void printConfig() {
  Serial.println("---- SAVED CONFIG ----");
  Serial.printf("WIFI=%s BACKEND=%s\n", wifiSsid.c_str(), backendUrl.c_str());
  Serial.printf("DEVICE=%s FCC=%s NOZZLE=%s\n", deviceUid.c_str(), fccUid.c_str(), nozzleId.c_str());
  Serial.printf("PPL=%.3f pulses/L  PPS=%.2f pulses/sec  JSON=%s\n",
                pulsesPerLitre, expectedPps, jsonEcho ? "ON" : "OFF");
  Serial.println("Formula: litres = pulses / PPL");
  Serial.println("----------------------");
}

void applySetting(const String& key, const String& value) {
  if (key == "WIFI") {
    int sep = value.indexOf('|');
    if (sep < 1) { Serial.println("Use: SET WIFI ssid|password"); return; }
    saveCfg("ssid", value.substring(0, sep));
    saveCfg("pass", value.substring(sep + 1));
    wifiSsid = value.substring(0, sep);
    wifiPass = value.substring(sep + 1);
    Serial.println("[SET] Wi-Fi saved. Reconnecting now...");
    WiFi.disconnect(false);
    delay(200);
    connectWiFi();
  } else if (key == "BACKEND") { saveCfg("backend", value); backendUrl = value; }
  else if (key == "DEVICE") { saveCfg("dev", value); deviceUid = value; }
  else if (key == "FCC") { saveCfg("fcc", value); fccUid = value; }
  else if (key == "NOZZLE") { saveCfg("nozzle", value); nozzleId = value; }
  else if (key == "PPL") { calSet(value.toFloat()); return; }
  else if (key == "PPS") { expectedPps = value.toFloat(); prefs.putFloat("pps", expectedPps); }
  else { Serial.println("Unknown SET key."); return; }
  Serial.println("[SET] " + key + " saved.");
}

void handleSerial(String line) {
  line.trim();
  if (line == "HELP") {
    Serial.println("SET WIFI ssid|pass | SET BACKEND url | SET DEVICE uid | SET FCC uid | SET NOZZLE id");
    Serial.println("SET PPL n | SET PPS n | CONFIG | REBOOT | JSON ON|OFF");
    Serial.println("COUNT | RESET | STATUS | CAL FETCH | CAL SET n | MATH n | MATH RATE n | MATH PPS | SEND");
    Serial.println("NETWORK | PING | WIFI (retry now) | CONFIG | FACTORY");
  } else if (line.startsWith("SET ")) {
    String rest = line.substring(4);
    int sp = rest.indexOf(' ');
    if (sp < 0) { Serial.println("Use: SET KEY value"); return; }
    applySetting(rest.substring(0, sp), rest.substring(sp + 1));
  } else if (line == "CONFIG") printConfig();
  else if (line == "REBOOT") ESP.restart();
  else if (line == "FACTORY") {
    prefs.clear();
    Serial.println("[FACTORY] Saved settings cleared — restarting with generated defaults");
    ESP.restart();
  }
  else if (line.startsWith("JSON ")) {
    jsonEcho = line.substring(5) == "ON";
    prefs.putBool("json", jsonEcho);
    Serial.printf("[JSON] %s\n", jsonEcho ? "ON" : "OFF");
  } else if (line == "COUNT") Serial.printf("[COUNT] %lu pulses = %.3f L\n", pulses, (float)pulses / pulsesPerLitre);
  else if (line == "RESET") { pulses = 0; pulsesAtWindow = 0; measuredPps = 0; Serial.println("[COUNT] reset"); }
  else if (line == "STATUS") {
    Serial.printf("UID=%s FCC=%s PULSES=%lu PPL=%.3f LITRES=%.3f MEASURED_PPS=%.2f WIFI=%s\n",
                  deviceUid.c_str(), fccUid.c_str(), pulses, pulsesPerLitre,
                  (float)pulses / pulsesPerLitre, measuredPps,
                  WiFi.status() == WL_CONNECTED ? "OK" : "OFF");
  } else if (line == "NETWORK") printNetwork();
  else if (line == "PING") pingBackend();
  else if (line == "WIFI") { WiFi.disconnect(false); delay(200); connectWiFi(); }
  else if (line == "CAL FETCH") { if (WiFi.status() == WL_CONNECTED) fetchCalibration(); else Serial.println("[MATH] WiFi offline"); }
  else if (line.startsWith("CAL SET ")) calSet(line.substring(8).toFloat());
  else if (line.startsWith("MATH RATE ")) {
    float pps = line.substring(10).toFloat();
    Serial.printf("[MATH] %.2f pulses/sec = %.4f L/sec = %.2f L/min (PPL=%.3f)\n",
                  pps, pps / pulsesPerLitre, pps / pulsesPerLitre * 60, pulsesPerLitre);
  } else if (line == "MATH PPS") {
    Serial.printf("[MATH] measured=%.2f pps configured=%.2f pps -> %.4f L/sec\n",
                  measuredPps, expectedPps, measuredPps / pulsesPerLitre);
  } else if (line.startsWith("MATH ")) {
    float p = line.substring(5).toFloat();
    Serial.printf("[MATH] %.0f pulses = %.3f L (PPL=%.3f)\n", p, p / pulsesPerLitre, pulsesPerLitre);
  } else if (line == "SEND") { if (WiFi.status() == WL_CONNECTED) sendTelemetry(); else Serial.println("[PULSE] WiFi offline"); }
  else Serial.println("Unknown command. Type HELP.");
}

void loop() {
  updateLeds();
  ensureWiFi();
  if (Serial.available()) handleSerial(Serial.readStringUntil('\n'));

  unsigned long now = millis();
  if (now - lastWindow >= 1000) {
    float elapsed = (now - lastWindow) / 1000.0;
    measuredPps = elapsed > 0 ? (pulses - pulsesAtWindow) / elapsed : 0;
    lastWindow = now;
    pulsesAtWindow = pulses;
  }
  if (WiFi.status() == WL_CONNECTED && now - lastSend > 10000) {
    lastSend = now;
    sendTelemetry();
  }
  delay(10);
}
