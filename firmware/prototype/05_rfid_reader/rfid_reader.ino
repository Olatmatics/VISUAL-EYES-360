/*
 * VISUAL EYES 360 - RFID CARD + WALLET PAYMENT (Serial driven)
 * Target: ESP32 DevKit v1 + MFRC522. Serial 115200.
 * Library: MFRC522 (github.com/miguelbalboa/rfid)
 *
 * Serial commands:
 *   HELP            list commands
 *   SCAN            read a card; unknown cards are registered automatically
 *   FUND 5000       add money to the scanned card's wallet (bench)
 *   PAY 5000        pay for fuel from the wallet and queue valve approval
 *   STATUS          show scanned UID, balance and link status
 *
 * MFRC522 wiring (ESP32, hardware SPI):
 *   SDA(CS) 27 | SCK 18 | MOSI 23 | MISO 19 | RST 5 | 3.3V | GND
 * DO NOT power the reader from 5V.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <SPI.h>
#include <MFRC522.h>

const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";
const char* BACKEND = "http://192.168.1.100:8000";
const char* API_KEY = "dev-ingest-key-change-me";   // match backend INGEST_API_KEY
const char* NOZZLE_ID = "YOUR_NOZZLE_ID";

#define SS_PIN 27
#define RST_PIN 5
MFRC522 rfid(SS_PIN, RST_PIN);

String currentUid = "";
float currentBalance = 0;

void setup() {
  Serial.begin(115200);
  SPI.begin(); rfid.PCD_Init();
  WiFi.mode(WIFI_STA); WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nREADY. Place a card and type SCAN. Type HELP for commands.");
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

String post(const char* path, String body) {
  if (WiFi.status() != WL_CONNECTED) return "{\"error\":\"wifi_offline\"}";
  HTTPClient http; http.begin(String(BACKEND) + path);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", API_KEY);
  int code = http.POST(body);
  String res = http.getString(); http.end();
  Serial.printf("[HTTP] %s -> %d\n", path, code);
  return res;
}

void scanCard() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    Serial.println("[RFID] No card detected. Place a card on the reader.");
    return;
  }
  currentUid = uidToString();
  StaticJsonDocument<256> doc;
  doc["uid"] = currentUid;
  String body; serializeJson(doc, body);
  String res = post("/api/v1/rfid/scan", body);
  Serial.println("[RFID] UID: " + currentUid);
  Serial.println("[RFID] " + res);
  StaticJsonDocument<512> parsed;
  if (!deserializeJson(parsed, res)) currentBalance = parsed["balance_ngn"] | 0;
  rfid.PICC_HaltA();
}

void fund(float amount) {
  if (!currentUid.length()) { Serial.println("ERR: scan a card first"); return; }
  StaticJsonDocument<256> doc;
  doc["uid"] = currentUid; doc["amount_ngn"] = amount;
  String body; serializeJson(doc, body);
  Serial.println("[FUND] " + post("/api/v1/rfid/fund", body));
}

void pay(float amount) {
  if (!currentUid.length()) { Serial.println("ERR: scan a card first"); return; }
  StaticJsonDocument<256> doc;
  doc["uid"] = currentUid; doc["amount_ngn"] = amount; doc["nozzle_id"] = NOZZLE_ID;
  String body; serializeJson(doc, body);
  String res = post("/api/v1/rfid/authorize", body);
  Serial.println("[PAY] " + res);
  StaticJsonDocument<512> parsed;
  if (!deserializeJson(parsed, res)) currentBalance = parsed["balance_ngn"] | currentBalance;
}

void loop() {
  if (Serial.available()) {
    String c = Serial.readStringUntil('\n'); c.trim();
    if (c == "HELP") Serial.println("SCAN | FUND <ngn> | PAY <ngn> | STATUS");
    else if (c == "SCAN") scanCard();
    else if (c.startsWith("FUND ")) fund(c.substring(5).toFloat());
    else if (c.startsWith("PAY ")) pay(c.substring(4).toFloat());
    else if (c == "STATUS") Serial.printf("UID=%s BALANCE=%.2f WIFI=%s\n", currentUid.c_str(), currentBalance, WiFi.status()==WL_CONNECTED?"OK":"OFF");
  }
  delay(20);
}
