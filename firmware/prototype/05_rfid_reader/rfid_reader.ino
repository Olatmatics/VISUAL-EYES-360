/*
 * VISUAL EYES 360 - BOARD 5: RFID CARD REGISTRAR + WALLET
 * Bench prototype. ESP32 DevKit v1 + MFRC522, Serial 115200. NOT intrinsically safe.
 *
 * A manager registers a customer's card by placing it on this reader. The UID is
 * shown on Serial, then saved to the backend with the manager's home station.
 * Cards are NATIONWIDE: the home station is only where it was first registered;
 * the same card works at any station in any state.
 *
 * MFRC522 wiring (ESP32 hardware SPI):
 *   SDA(CS) 27 | SCK 18 | MOSI 23 | MISO 19 | RST 5 | 3.3V | GND
 *   Never power the reader from 5 V.
 *
 * SETUP COMMANDS (saved, survive power cycle):
 *   SET WIFI ssid|password
 *   SET BACKEND http://172.25.0.37:8000
 *   SET APIKEY dev-ingest-key-change-me
 *   SET STATION <station id where this reader is located>
 *   SET NOZZLE <nozzle id used for PAY test>
 *   CONFIG | JSON ON|OFF | REBOOT
 *
 * CARD COMMANDS:
 *   REGISTER         arm registration, then place a NEW card on the reader
 *   NAME <full name> optional owner name for the pending card
 *   SAVE             save pending UID to backend (nationwide card)
 *   CANCEL           abort pending registration
 *   SCAN             read a card and recognise an existing card
 *   FUND 5000        bench funding after verified external payment
 *   PAY 5000         debit wallet and queue PAYMENT_SUCCESS for the nozzle FCC
 *   CARD | STATUS | HELP
 *
 * Simply placing a card on the reader always prints its UID.
 * All request/response JSON is printed when JSON is ON.
 *
 * LEDs: GPIO2 (onboard) = Wi-Fi status. Steady ON when connected, slow blink
 * while connecting. GPIO22 + 220R = backend activity, blinks very fast on
 * every card register/scan/fund/pay request and response.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <SPI.h>
#include <MFRC522.h>
#include <string.h>

Preferences prefs;

// Defaults match the current bench database. Change from Serial if you reset data.
const char* DEF_WIFI_SSID = "cypher";
const char* DEF_WIFI_PASS = "12345678";
const char* DEF_BACKEND   = "http://172.25.0.37:8000";
const char* DEF_APIKEY    = "dev-ingest-key-change-me";
const char* DEF_STATION   = "923a0b56-6e8f-4dc4-89f2-1f0dd8a93628";
const char* DEF_NOZZLE    = "d26a4199-393b-40fc-b4b6-45bea91a10c2";

#define WIFI_LED_PIN 2      // onboard LED: Wi-Fi status
#define COMM_LED_PIN 22     // add LED + 220R to GND: backend activity
#define SS_PIN 27
#define RST_PIN 5
MFRC522 rfid(SS_PIN, RST_PIN);

String wifiSsid, wifiPass, backendUrl, apiKey, stationId, nozzleId;
String currentUid = "", pendingUid = "", pendingOwner = "";
float currentBalance = 0;
bool jsonEcho = true;
bool waitingForCard = false;

unsigned long commUntil = 0;
unsigned long commToggleAt = 0;
unsigned long wifiBlinkAt = 0;
bool commLedOn = false;
bool wifiLedOn = false;

unsigned long registerStarted = 0;

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
  prefs.begin("ve360-rfid", false);
  wifiSsid   = cfg("ssid", DEF_WIFI_SSID);
  wifiPass   = cfg("pass", DEF_WIFI_PASS);
  backendUrl = cfg("backend", DEF_BACKEND);
  apiKey     = cfg("apikey", DEF_APIKEY);
  stationId  = cfg("station", DEF_STATION);
  nozzleId   = cfg("nozzle", DEF_NOZZLE);
  jsonEcho   = prefs.getBool("json", true);
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  if (wifiSsid == "YOUR_WIFI" || wifiSsid.length() == 0) {
    Serial.println("[WIFI] Not configured. Type: SET WIFI ssid|password  then REBOOT");
    return;
  }
  WiFi.begin(wifiSsid.c_str(), wifiPass.c_str());
  Serial.print("[WIFI] Connecting");
  unsigned long started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 15000) {
    updateLeds();
    delay(500); Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("[WIFI] OK IP="); Serial.println(WiFi.localIP().toString());
  } else {
    Serial.println("[WIFI] Offline — card UID still prints locally.");
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(WIFI_LED_PIN, OUTPUT); pinMode(COMM_LED_PIN, OUTPUT);
  SPI.begin();
  rfid.PCD_Init();
  loadConfig();
  connectWiFi();
  Serial.println("READY. Type REGISTER and place a new card. Type HELP for commands.");
}

String uidToString() {
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  return uid;
}

void echoJson(const char* tag, const String& body) {
  if (jsonEcho) Serial.printf("[JSON %s] %s\n", tag, body.c_str());
}

String post(const char* path, const String& body) {
  if (WiFi.status() != WL_CONNECTED) return "{\"error\":\"wifi_offline\"}";
  markBackendActivity(1200);
  HTTPClient http;
  http.begin(backendUrl + path);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", apiKey);
  int code = http.POST(body);
  String res = http.getString();
  http.end();
  markBackendActivity(600);
  echoJson("OUT", body);
  Serial.printf("[HTTP] %s -> %d\n", path, code);
  echoJson("IN", res);
  return res;
}

void armRegister() {
  waitingForCard = true;
  registerStarted = millis();
  Serial.println("[REGISTER] Place the NEW customer card on the reader (30s)...");
}

void savePendingCard() {
  if (pendingUid.length() == 0) {
    Serial.println("ERR: type REGISTER and place a new card first");
    return;
  }
  if (pendingOwner.length() == 0) pendingOwner = "Card " + pendingUid;

  StaticJsonDocument<512> doc;
  doc["uid"] = pendingUid;
  doc["owner"] = pendingOwner;
  doc["station_id"] = stationId;
  String body; serializeJson(doc, body);
  String res = post("/api/v1/rfid/prototype/register", body);

  DynamicJsonDocument parsed(2048);
  if (!deserializeJson(parsed, res)) {
    currentUid = pendingUid;
    currentBalance = parsed["balance_ngn"] | 0;
    String owner = parsed["owner"] | pendingOwner;
    String home = parsed["home_station"] | "";
    bool nationwide = parsed["nationwide"] | false;
    Serial.println("---- CARD SAVED ----");
    Serial.println("UID: " + String(parsed["uid"] | currentUid));
    Serial.println("OWNER: " + owner);
    Serial.println("HOME STATION: " + (home.length() ? home : String("not set")));
    Serial.printf("BALANCE: NGN %.2f   NATIONWIDE: %s\n", currentBalance, nationwide ? "YES" : "NO");
    Serial.println("--------------------");
    pendingUid = "";
    pendingOwner = "";
  } else {
    Serial.println("[REGISTER] Save failed. See JSON above.");
  }
}

void scanCard() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    Serial.println("[RFID] No card detected. Place a card on the reader.");
    return;
  }
  currentUid = uidToString();
  rfid.PICC_HaltA();
  Serial.println("[RFID] UID: " + currentUid);
  StaticJsonDocument<256> doc;
  doc["uid"] = currentUid;
  String body; serializeJson(doc, body);
  String res = post("/api/v1/rfid/scan", body);
  DynamicJsonDocument parsed(2048);
  if (!deserializeJson(parsed, res)) currentBalance = parsed["balance_ngn"] | 0;
}

void fund(float amount) {
  if (currentUid.length() == 0) { Serial.println("ERR: place a card on the reader first"); return; }
  if (amount <= 0) { Serial.println("ERR: amount must be positive"); return; }
  StaticJsonDocument<256> doc;
  doc["uid"] = currentUid;
  doc["amount_ngn"] = amount;
  String body; serializeJson(doc, body);
  String res = post("/api/v1/rfid/fund", body);
  DynamicJsonDocument parsed(1024);
  if (!deserializeJson(parsed, res)) currentBalance = parsed["balance_ngn"] | currentBalance;
  Serial.printf("[FUND] Balance now NGN %.2f\n", currentBalance);
}

void pay(float amount) {
  if (currentUid.length() == 0) { Serial.println("ERR: place a card on the reader first"); return; }
  if (amount <= 0) { Serial.println("ERR: amount must be positive"); return; }
  StaticJsonDocument<512> doc;
  doc["uid"] = currentUid;
  doc["amount_ngn"] = amount;
  doc["nozzle_id"] = nozzleId;
  String body; serializeJson(doc, body);
  String res = post("/api/v1/rfid/authorize", body);
  DynamicJsonDocument parsed(2048);
  if (!deserializeJson(parsed, res)) {
    currentBalance = parsed["balance_ngn"] | currentBalance;
    Serial.printf("[PAY] APPROVED ref=%s liters=%.2f FCC=%s balance=NGN %.2f\n",
                  String(parsed["reference"] | "").c_str(),
                  (float)(parsed["authorized_liters"] | 0),
                  String(parsed["device_uid"] | "").c_str(), currentBalance);
  } else {
    Serial.println("[PAY] Declined. See JSON above.");
  }
}

void printConfig() {
  Serial.println("---- SAVED CONFIG ----");
  Serial.printf("WIFI=%s BACKEND=%s\n", wifiSsid.c_str(), backendUrl.c_str());
  Serial.printf("STATION=%s\nNOZZLE=%s\n", stationId.c_str(), nozzleId.c_str());
  Serial.printf("JSON=%s  Cards are NATIONWIDE\n", jsonEcho ? "ON" : "OFF");
  Serial.println("----------------------");
}

void applySetting(const String& key, const String& value) {
  if (key == "WIFI") {
    int sep = value.indexOf('|');
    if (sep < 1) { Serial.println("Use: SET WIFI ssid|password"); return; }
    saveCfg("ssid", value.substring(0, sep));
    saveCfg("pass", value.substring(sep + 1));
    Serial.println("[SET] Wi-Fi saved. Type REBOOT to connect.");
  } else if (key == "BACKEND") { saveCfg("backend", value); backendUrl = value; }
  else if (key == "APIKEY") { saveCfg("apikey", value); apiKey = value; }
  else if (key == "STATION") { saveCfg("station", value); stationId = value; }
  else if (key == "NOZZLE") { saveCfg("nozzle", value); nozzleId = value; }
  else { Serial.println("Unknown SET key."); return; }
  Serial.println("[SET] " + key + " saved.");
}

void handleSerial(String line) {
  line.trim();
  if (line == "HELP") {
    Serial.println("SET WIFI ssid|pass | SET BACKEND url | SET APIKEY key | SET STATION id | SET NOZZLE id");
    Serial.println("CONFIG | JSON ON|OFF | REBOOT | REGISTER | NAME <owner> | SAVE | CANCEL");
    Serial.println("SCAN | FUND 5000 | PAY 5000 | CARD | STATUS");
  } else if (line.startsWith("SET ")) {
    String rest = line.substring(4);
    int sp = rest.indexOf(' ');
    if (sp < 0) { Serial.println("Use: SET KEY value"); return; }
    applySetting(rest.substring(0, sp), rest.substring(sp + 1));
  } else if (line == "CONFIG") printConfig();
  else if (line == "REBOOT") ESP.restart();
  else if (line.startsWith("JSON ")) {
    jsonEcho = line.substring(5) == "ON";
    prefs.putBool("json", jsonEcho);
    Serial.printf("[JSON] %s\n", jsonEcho ? "ON" : "OFF");
  } else if (line == "REGISTER") armRegister();
  else if (line.startsWith("NAME ")) {
    pendingOwner = line.substring(5);
    Serial.println("[REGISTER] Owner set to: " + pendingOwner);
  } else if (line == "SAVE") savePendingCard();
  else if (line == "CANCEL") { waitingForCard = false; pendingUid = ""; pendingOwner = ""; Serial.println("[REGISTER] cancelled"); }
  else if (line == "SCAN") scanCard();
  else if (line.startsWith("FUND ")) fund(line.substring(5).toFloat());
  else if (line.startsWith("PAY ")) pay(line.substring(4).toFloat());
  else if (line == "CARD") Serial.println("UID=" + (currentUid.length() ? currentUid : String("none")));
  else if (line == "STATUS") {
    Serial.printf("UID=%s BALANCE=NGN %.2f WIFI=%s PENDING=%s\n",
                  currentUid.length() ? currentUid.c_str() : "none", currentBalance,
                  WiFi.status() == WL_CONNECTED ? "OK" : "OFF",
                  pendingUid.length() ? pendingUid.c_str() : "none");
  } else Serial.println("Unknown command. Type HELP.");
}

void loop() {
  updateLeds();
  if (Serial.available()) handleSerial(Serial.readStringUntil('\n'));

  if (waitingForCard && millis() - registerStarted > 30000) {
    waitingForCard = false;
    Serial.println("[REGISTER] Timed out. Type REGISTER and place the card again.");
  }

  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    String uid = uidToString();
    rfid.PICC_HaltA();
    if (waitingForCard) {
      waitingForCard = false;
      pendingUid = uid;
      pendingOwner = "Card " + uid.substring(uid.length() > 6 ? uid.length() - 6 : 0);
      Serial.println("[REGISTER] UID READ: " + uid);
      Serial.println("[REGISTER] Optional: NAME <full name>  then  SAVE");
      Serial.println("[REGISTER] Or just type SAVE to accept the default owner.");
    } else {
      currentUid = uid;
      Serial.println("[CARD] UID: " + uid);
    }
    delay(300);
  }
  delay(10);
}
