/*
 * VISUAL EYES 360 - BOARD 1: FCC PUMP CONTROLLER (two nozzles)
 * Bench prototype. ESP32 DevKit v1, Serial 115200. NOT intrinsically safe.
 *
 * Everything can be typed in Serial Monitor — no code editing needed at the bench.
 *
 * SETUP COMMANDS (saved in ESP32 Preferences, survive power cycle):
 *   SET WIFI ssid|password       Wi-Fi credentials
 *   SET BACKEND http://172.25.0.37:8000
 *   SET STATION <station id>
 *   SET NOZZLE_A <nozzle id>     SET NOZZLE_B <nozzle id>
 *   SET DEVICE_A <fcc uid>       SET DEVICE_B <fcc uid>
 *   SET POS <opay pos serial>
 *   SET DISPENSER <dispenser id>
 *   SET PRICE <ngn per litre>
 *   CONFIG                       show all saved values
 *   REBOOT                       restart to apply Wi-Fi change
 *
 * TEST COMMANDS:
 *   HELP | NOZZLE A|B | INIT 5000 (or INIT 5L) | POLL | ACK <id>
 *   COMPLETE <litres> | STATUS | RESET | HEARTBEAT | JSON ON|OFF
 *   CAL FETCH | CAL SET <pulses per litre>
 *   NETWORK (show Wi-Fi + backend) | PING (test backend) | WIFI (retry now)
 *
 * The automatic heartbeat makes the web ticker show this controller online.
 * All request and response JSON is printed to Serial when JSON is ON.
 *
 * LEDs: GPIO2 (onboard) = Wi-Fi status. Steady ON when connected, slow blink
 * while connecting. GPIO22 + 220R = backend activity, blinks very fast on
 * every request, response and queued command.
 *
 * NOZZLE-SWITCH MODE:
 *   Payment approval does NOT energise the nozzle switch.
 *   GPIO13 (nozzle A) / GPIO12 (nozzle B) are INPUT_PULLUP sense inputs.
 *   Your external relay contact closes the sensed pin to GND.
 *   When the switch closes, GPIO32 goes HIGH to tell Board 04 to pulse.
 *   When authorised litres is reached, GPIO32 goes LOW and pulses stop.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <string.h>

Preferences prefs;

// ---- Factory defaults. Change these from Serial with SET ... ---------------
const char* DEF_WIFI_SSID   = "cypher";
const char* DEF_WIFI_PASS   = "12345678";
const char* DEF_BACKEND     = "http://172.25.0.37:8000";
const char* DEF_STATION     = "YOUR_STATION_ID";
const char* DEF_NOZZLE_A    = "YOUR_NOZZLE_A_ID";
const char* DEF_NOZZLE_B    = "YOUR_NOZZLE_B_ID";
const char* DEF_DEVICE_A    = "fcc-matics-001";
const char* DEF_DEVICE_B    = "FCC-DEV-B";
const char* DEF_POS         = "YOUR_OPAY_POS_SN";
const char* DEF_DISPENSER   = "YOUR_DISPENSER_ID";
const char* FIRMWARE        = "ve360-fcc-bench-1.1";

#define RELAY_A   26
#define RELAY_B   25
#define WIFI_LED_PIN 2      // onboard LED: Wi-Fi status
#define COMM_LED_PIN 22     // add LED + 220R to GND: backend activity
#define PULSE_A   27
#define PULSE_B   14
#define NOZZLE_SENSE_A 13   // external nozzle relay contact -> GND = CLOSED
#define NOZZLE_SENSE_B 12   // external nozzle relay contact -> GND = CLOSED
#define PULSE_TRIGGER 32    // HIGH tells Board 04 GPIO25 to emit pulses

enum State { IDLE, PAYMENT_PENDING, AUTHORIZED, DISPENSING, COMPLETE, ERROR_STATE };
State state = IDLE;

String wifiSsid, wifiPass, backendUrl, stationId, nozzleAId, nozzleBId;
String posSn, deviceUidA, deviceUidB, dispenserId;
String activeTx = "";
String activeNozzle = "A";
volatile char activeNozzleChar = 'A';
volatile unsigned long pulses = 0;
float unitPrice = 1150.0;
float pulsesPerLitre = 1.0;
float authorizedLitres = 0;
bool jsonEcho = true;

unsigned long commUntil = 0;
unsigned long commToggleAt = 0;
unsigned long wifiBlinkAt = 0;
bool commLedOn = false;
bool wifiLedOn = false;
bool senseAWasActive = false;
bool senseBWasActive = false;
bool pulseTriggerOn = false;

unsigned long lastPoll = 0;
unsigned long lastHeartbeat = 0;
unsigned long lastCalFetch = 0;
unsigned long dispenseStart = 0;
unsigned long lastWifiRetry = 0;
bool wifiWasConnected = false;

// Explicit prototypes. Arduino IDE sometimes misses IRAM_ATTR interrupt ISRs.
void closeValves();
void sendHeartbeat();
void fetchCalibration();
void printNetwork();
void pingBackend();
void IRAM_ATTR onPulseA();
void IRAM_ATTR onPulseB();

String cfg(const char* key, const char* def) {
  String value = prefs.getString(key, "");
  return value.length() ? value : String(def);
}
void saveCfg(const char* key, const String& value) { prefs.putString(key, value); }

String currentDeviceUid() { return activeNozzleChar == 'A' ? deviceUidA : deviceUidB; }
String currentNozzleId()  { return activeNozzleChar == 'A' ? nozzleAId : nozzleBId; }

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

// ---- Network diagnostics -----------------------------------------------------
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
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[PING] WiFi offline — type WIFI to retry");
    return;
  }
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
    if (up) {
      Serial.print("[WIFI] Connected IP="); Serial.println(WiFi.localIP().toString());
      sendHeartbeat();
    } else {
      Serial.println("[WIFI] Link lost — reconnecting");
    }
  }
  if (!up && millis() - lastWifiRetry > 10000) {
    lastWifiRetry = millis();
    Serial.print("[WIFI] Retry ");
    WiFi.reconnect();
    delay(50);
    Serial.printf("status=%d\n", (int)WiFi.status());
  }
}

// ---- Nozzle switch and pulse trigger helpers --------------------------------
bool nozzleSwitchActive() {
  return activeNozzleChar == 'A'
    ? digitalRead(NOZZLE_SENSE_A) == LOW
    : digitalRead(NOZZLE_SENSE_B) == LOW;
}

void setPulseTrigger(bool on) {
  if (pulseTriggerOn == on) return;
  pulseTriggerOn = on;
  digitalWrite(PULSE_TRIGGER, on ? HIGH : LOW);
  Serial.println(on ? "[TRIGGER] telling Board 04: PULSE"
                    : "[TRIGGER] telling Board 04: STOP");
}

void loadConfig() {
  prefs.begin("ve360-fcc", false);
  wifiSsid     = cfg("ssid", DEF_WIFI_SSID);
  wifiPass     = cfg("pass", DEF_WIFI_PASS);
  backendUrl   = cfg("backend", DEF_BACKEND);
  stationId    = cfg("station", DEF_STATION);
  nozzleAId    = cfg("nozA", DEF_NOZZLE_A);
  nozzleBId    = cfg("nozB", DEF_NOZZLE_B);
  deviceUidA   = cfg("devA", DEF_DEVICE_A);
  deviceUidB   = cfg("devB", DEF_DEVICE_B);
  posSn        = cfg("pos", DEF_POS);
  dispenserId  = cfg("disp", DEF_DISPENSER);
  unitPrice    = prefs.getFloat("price", unitPrice);
  pulsesPerLitre = prefs.getFloat("ppl", pulsesPerLitre);
  jsonEcho     = prefs.getBool("json", true);
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);
  if (wifiSsid.length() == 0 || wifiSsid == "YOUR_WIFI") {
    Serial.println("[WIFI] Not configured. Type: SET WIFI your-ssid|your-password");
    return;
  }
  Serial.printf("[WIFI] Connecting to '%s' (backend %s)\n", wifiSsid.c_str(), backendUrl.c_str());
  WiFi.begin(wifiSsid.c_str(), wifiPass.c_str());
  unsigned long started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 12000) {
    updateLeds();
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  wifiWasConnected = WiFi.status() == WL_CONNECTED;
  if (wifiWasConnected) {
    Serial.print("[WIFI] OK IP=");
    Serial.println(WiFi.localIP().toString());
  } else {
    Serial.println("[WIFI] Offline — it will retry automatically. Serial still works.");
    Serial.println("[WIFI] Check: SSID must be 2.4 GHz, password correct, router near board.");
  }
  printNetwork();
}

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_A, OUTPUT); pinMode(RELAY_B, OUTPUT);
  pinMode(WIFI_LED_PIN, OUTPUT); pinMode(COMM_LED_PIN, OUTPUT);
  pinMode(PULSE_A, INPUT_PULLUP); pinMode(PULSE_B, INPUT_PULLUP);
  pinMode(NOZZLE_SENSE_A, INPUT_PULLUP); pinMode(NOZZLE_SENSE_B, INPUT_PULLUP);
  pinMode(PULSE_TRIGGER, OUTPUT); digitalWrite(PULSE_TRIGGER, LOW);
  closeValves();
  loadConfig();
  attachInterrupt(digitalPinToInterrupt(PULSE_A), onPulseA, FALLING);
  attachInterrupt(digitalPinToInterrupt(PULSE_B), onPulseB, FALLING);
  connectWiFi();
  Serial.println("READY. Type HELP for commands, CONFIG to see saved IDs.");
  if (WiFi.status() == WL_CONNECTED) {
    sendHeartbeat();
    fetchCalibration();
  }
}

void IRAM_ATTR onPulseA() { if (activeNozzleChar == 'A') pulses++; }
void IRAM_ATTR onPulseB() { if (activeNozzleChar == 'B') pulses++; }

void closeValves() {
  digitalWrite(RELAY_A, HIGH); digitalWrite(RELAY_B, HIGH); // active-low relay modules
  Serial.println("[RELAY] outputs OFF (firmware does not energise nozzle switch)");
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
  int code;
  if (strcmp(method, "GET") == 0)       code = http.GET();
  else if (strcmp(method, "PATCH") == 0) code = http.sendRequest("PATCH", body);
  else                                   code = http.POST(body);
  String res = http.getString();
  http.end();
  markBackendActivity(600);
  echoJson("OUT", body.length() ? body : String("GET ") + path);
  Serial.printf("[HTTP] %s %s -> %d\n", method, path, code);
  echoJson("IN", res);
  return res;
}

String postJson(const char* path, const String& body) { return requestJson("POST", path, body); }
String getJson(const String& path) { return requestJson("GET", path.c_str(), ""); }

void sendHeartbeat() {
  StaticJsonDocument<256> doc;
  doc["device_uid"] = currentDeviceUid();
  doc["firmware_version"] = FIRMWARE;
  doc["signal_strength_dbm"] = WiFi.RSSI();
  String body; serializeJson(doc, body);
  Serial.println("[HEARTBEAT] " + postJson("/api/v1/fcc/prototype/heartbeat", body));
}

void fetchCalibration() {
  String res = getJson("/api/v1/fcc/calibration?device_uid=" + currentDeviceUid());
  DynamicJsonDocument parsed(1024);
  if (!deserializeJson(parsed, res)) {
    float ppl = parsed["pulses_per_litre"] | 0;
    if (ppl > 0) {
      pulsesPerLitre = ppl;
      Serial.printf("[CAL] pulses/litre = %.3f (from web MATH setting)\n", pulsesPerLitre);
    }
  }
}

void calSet(float ppl) {
  if (ppl <= 0) { Serial.println("ERR: pulses per litre must be greater than zero"); return; }
  StaticJsonDocument<256> doc;
  doc["device_uid"] = currentDeviceUid();
  doc["pulses_per_litre"] = ppl;
  String body; serializeJson(doc, body);
  Serial.println("[CAL] " + requestJson("PATCH", "/api/v1/fcc/calibration", body));
  pulsesPerLitre = ppl;
  prefs.putFloat("ppl", ppl);
}

void initPayment(float amount) {
  if (amount <= 0) { Serial.println("ERR: amount must be positive"); return; }
  activeTx = "FCCTX" + String(millis());
  StaticJsonDocument<512> doc;
  doc["client_tx_ref"] = activeTx;
  doc["nozzle_id"] = currentNozzleId();
  doc["target_amount_ngn"] = amount;
  doc["payment_preference"] = "POS";
  doc["pos_sn"] = posSn;
  doc["device_uid"] = currentDeviceUid();
  String body; serializeJson(doc, body);
  String res = postJson("/api/v1/fcc/transaction/initiate", body);
  DynamicJsonDocument parsed(2048);
  if (!deserializeJson(parsed, res)) {
    authorizedLitres = parsed["authorized_liters"] | 0;
    unitPrice = parsed["unit_price_ngn"] | unitPrice;
    state = PAYMENT_PENDING;
    Serial.printf("[INIT] Pending %.2f L at NGN %.2f/L. POS SN=%s\n",
                  authorizedLitres, unitPrice, parsed["opay_pos_sn"] | "");
  } else {
    state = ERROR_STATE;
    Serial.println("[INIT] Failed. See JSON above (POS terminal may not be assigned).");
  }
}

void pollCommands() {
  String res = getJson("/api/v1/fcc/commands/poll?device_uid=" + currentDeviceUid() + "&limit=10");
  int typePos = res.indexOf("\"type\":\"PAYMENT_SUCCESS\"");
  int idPos = res.indexOf("\"id\":\"");
  String cmdId = "";
  if (idPos >= 0) {
    int start = idPos + 6;
    int end = res.indexOf('"', start);
    if (end > start) cmdId = res.substring(start, end);
  }
  if (typePos >= 0) {
    markBackendActivity(1200);   // command arrived from backend
    state = AUTHORIZED;
    pulses = 0;
    dispenseStart = millis();
    setPulseTrigger(false);
    Serial.println("[PAYMENT] APPROVED - waiting for nozzle switch relay");
    if (cmdId.length() > 0) {
      StaticJsonDocument<128> ack;
      ack["command_id"] = cmdId;
      String ackBody; serializeJson(ack, ackBody);
      postJson("/api/v1/fcc/commands/ack", ackBody);
    }
  } else if (res.indexOf("PAYMENT_FAILED") >= 0) {
    markBackendActivity(1200);   // command arrived from backend
    state = ERROR_STATE;
    setPulseTrigger(false);
    closeValves();
    Serial.println("[PAYMENT] DECLINED - no pulse trigger, nozzle stays off");
    if (cmdId.length() > 0) {
      StaticJsonDocument<128> ack;
      ack["command_id"] = cmdId;
      String ackBody; serializeJson(ack, ackBody);
      postJson("/api/v1/fcc/commands/ack", ackBody);
    }
  }
}

void complete(float litres) {
  if (litres <= 0) litres = (float)pulses / pulsesPerLitre;
  StaticJsonDocument<512> doc;
  doc["client_tx_ref"] = activeTx;
  doc["device_uid"] = currentDeviceUid();
  doc["dispenser_id"] = dispenserId;
  doc["dispensed_liters"] = litres;
  doc["cpu_volume_l"] = litres;
  doc["pulser_volume_l"] = (float)pulses / pulsesPerLitre;
  doc["raw_pulse_count"] = pulses;
  doc["pulses_per_litre"] = pulsesPerLitre;
  doc["unit_price_ngn"] = unitPrice;
  doc["total_charged_ngn"] = litres * unitPrice;
  String body; serializeJson(doc, body);
  Serial.println("[COMPLETE] " + postJson("/api/v1/fcc/transaction/complete", body));
  setPulseTrigger(false);
  closeValves();
  state = COMPLETE;
  Serial.println("[TRANSACTION] target reached - pulses stopped");
}

void printConfig() {
  Serial.println("---- SAVED CONFIG ----");
  Serial.printf("WIFI=%s BACKEND=%s\n", wifiSsid.c_str(), backendUrl.c_str());
  Serial.printf("STATION=%s DISPENSER=%s\n", stationId.c_str(), dispenserId.c_str());
  Serial.printf("NOZZLE_A=%s\nNOZZLE_B=%s\n", nozzleAId.c_str(), nozzleBId.c_str());
  Serial.printf("DEVICE_A=%s\nDEVICE_B=%s\n", deviceUidA.c_str(), deviceUidB.c_str());
  Serial.printf("POS=%s PRICE=%.2f PPL=%.3f JSON=%s\n",
                posSn.c_str(), unitPrice, pulsesPerLitre, jsonEcho ? "ON" : "OFF");
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
  else if (key == "STATION") { saveCfg("station", value); stationId = value; }
  else if (key == "NOZZLE_A") { saveCfg("nozA", value); nozzleAId = value; }
  else if (key == "NOZZLE_B") { saveCfg("nozB", value); nozzleBId = value; }
  else if (key == "DEVICE_A") { saveCfg("devA", value); deviceUidA = value; }
  else if (key == "DEVICE_B") { saveCfg("devB", value); deviceUidB = value; }
  else if (key == "POS") { saveCfg("pos", value); posSn = value; }
  else if (key == "DISPENSER") { saveCfg("disp", value); dispenserId = value; }
  else if (key == "PRICE") { unitPrice = value.toFloat(); prefs.putFloat("price", unitPrice); }
  else if (key == "PPL") { pulsesPerLitre = value.toFloat(); prefs.putFloat("ppl", pulsesPerLitre); }
  else { Serial.println("Unknown SET key. Type CONFIG to see keys."); return; }
  Serial.println("[SET] " + key + " saved.");
}

void handleSerial(String line) {
  line.trim();
  if (line == "HELP") {
    Serial.println("SET WIFI ssid|pass | SET BACKEND url | SET STATION id | SET NOZZLE_A id | SET NOZZLE_B id");
    Serial.println("SET DEVICE_A uid | SET DEVICE_B uid | SET POS sn | SET DISPENSER id | SET PRICE n | SET PPL n");
    Serial.println("CONFIG | REBOOT | NOZZLE A|B | INIT 5000 | INIT 5L | POLL | ACK id | COMPLETE L");
    Serial.println("STATUS | RESET | HEARTBEAT | JSON ON|OFF | CAL FETCH | CAL SET n");
    Serial.println("NETWORK | PING | WIFI (retry now) | CONFIG");
    Serial.println("NOZZLE SWITCH: GPIO13(A)/GPIO12(B) to GND, Board 04 trigger on GPIO32");
  } else if (line.startsWith("SET ")) {
    String rest = line.substring(4);
    int sp = rest.indexOf(' ');
    if (sp < 0) { Serial.println("Use: SET KEY value"); return; }
    applySetting(rest.substring(0, sp), rest.substring(sp + 1));
  } else if (line == "CONFIG") printConfig();
  else if (line == "REBOOT") ESP.restart();
  else if (line.startsWith("NOZZLE ")) {
    String n = line.substring(7); n.trim();
    activeNozzle = n;
    activeNozzleChar = (n.length() && (n.charAt(0) == 'B' || n.charAt(0) == 'b')) ? 'B' : 'A';
    Serial.println("[NOZZLE] " + activeNozzle);
  } else if (line.startsWith("INIT ")) {
    String v = line.substring(5); v.trim();
    float amount = v.endsWith("L") || v.endsWith("l")
      ? v.substring(0, v.length() - 1).toFloat() * unitPrice
      : v.toFloat();
    initPayment(amount);
  } else if (line == "POLL") pollCommands();
  else if (line.startsWith("ACK ")) {
    StaticJsonDocument<128> ack;
    ack["command_id"] = line.substring(4);
    String body; serializeJson(ack, body);
    Serial.println(postJson("/api/v1/fcc/commands/ack", body));
  } else if (line.startsWith("COMPLETE")) {
    String v = line.substring(8); v.trim();
    complete(v.length() ? v.toFloat() : 0);
  } else if (line == "STATUS") {
    Serial.printf("STATE=%d NOZZLE=%s TX=%s PULSES=%lu LITRES=%.3f PPL=%.3f AUTHORIZED=%.2f\n",
                  state, activeNozzle.c_str(), activeTx.c_str(), pulses,
                  (float)pulses / pulsesPerLitre, pulsesPerLitre, authorizedLitres);
    Serial.printf("UID=%s WIFI=%s RSSI=%d\n", currentDeviceUid().c_str(),
                  WiFi.status() == WL_CONNECTED ? "OK" : "OFF", WiFi.RSSI());
    Serial.printf("NOZZLE_SWITCH=%s TRIGGER_TO_04=%s\n",
                  nozzleSwitchActive() ? "CLOSED" : "OPEN",
                  pulseTriggerOn ? "ON" : "OFF");
  } else if (line == "RESET") {
    pulses = 0; activeTx = ""; state = IDLE;
    setPulseTrigger(false);
    closeValves();
    Serial.println("[RESET] pulses and transaction cleared");
  }
  else if (line == "HEARTBEAT") { if (WiFi.status() == WL_CONNECTED) sendHeartbeat(); else Serial.println("[HEARTBEAT] WiFi offline"); }
  else if (line == "NETWORK") printNetwork();
  else if (line == "PING") pingBackend();
  else if (line == "WIFI") { WiFi.disconnect(false); delay(200); connectWiFi(); }
  else if (line.startsWith("JSON ")) {
    jsonEcho = line.substring(5) == "ON";
    prefs.putBool("json", jsonEcho);
    Serial.printf("[JSON] %s\n", jsonEcho ? "ON" : "OFF");
  } else if (line == "CAL FETCH") { if (WiFi.status() == WL_CONNECTED) fetchCalibration(); else Serial.println("[CAL] WiFi offline"); }
  else if (line.startsWith("CAL SET ")) calSet(line.substring(8).toFloat());
  else Serial.println("Unknown command. Type HELP.");
}

void loop() {
  updateLeds();
  ensureWiFi();
  if (Serial.available()) handleSerial(Serial.readStringUntil('\n'));

  // Sense the external nozzle-switch relay. Contact to GND = CLOSED/energised.
  bool senseA = digitalRead(NOZZLE_SENSE_A) == LOW;
  if (senseA != senseAWasActive) {
    senseAWasActive = senseA;
    Serial.printf("[NOZZLE A] switch %s\n", senseA ? "CLOSED" : "OPEN");
  }
  bool senseB = digitalRead(NOZZLE_SENSE_B) == LOW;
  if (senseB != senseBWasActive) {
    senseBWasActive = senseB;
    Serial.printf("[NOZZLE B] switch %s\n", senseB ? "CLOSED" : "OPEN");
  }

  if (WiFi.status() == WL_CONNECTED) {
    if (millis() - lastHeartbeat > 30000) { lastHeartbeat = millis(); sendHeartbeat(); }
    if (millis() - lastCalFetch > 300000) { lastCalFetch = millis(); fetchCalibration(); }
    if (state == PAYMENT_PENDING && millis() - lastPoll > 2000) { lastPoll = millis(); pollCommands(); }
  }

  // Approval arms the transaction; the nozzle switch is the actual start.
  if ((state == AUTHORIZED || state == DISPENSING) && nozzleSwitchActive()) {
    if (state == AUTHORIZED) {
      state = DISPENSING;
      dispenseStart = millis();
      setPulseTrigger(true);
      Serial.println("[NOZZLE] switch closed - Board 04 told to pulse");
    }
  }

  // If the switch opens early, stop pulses but keep the approval armed.
  if (state == DISPENSING && !nozzleSwitchActive()) {
    setPulseTrigger(false);
    state = AUTHORIZED;
    Serial.println("[NOZZLE] switch opened - dispensing paused");
  }

  // Stop at the authorised litres/naira worth of fuel.
  if (state == DISPENSING && authorizedLitres > 0 &&
      pulses >= (unsigned long)(authorizedLitres * pulsesPerLitre)) {
    complete((float)pulses / pulsesPerLitre);
  }
  delay(10);
}
