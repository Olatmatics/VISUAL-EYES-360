/*
 * VISUAL EYES 360 - PROTOTYPE BOARD 1: FCC PUMP CONTROLLER (double nozzle)
 * Target: ESP32 DevKit v1. Serial 115200. Optional ST7735 TFT on the only screen.
 *
 * Serial commands (type in Serial Monitor):
 *   HELP                 list commands
 *   NOZZLE A|B           select active nozzle
 *   INIT 5000            start a payment for NGN amount (or "INIT 5L")
 *   POLL                 fetch queued backend commands
 *   ACK <id>             acknowledge a command
 *   COMPLETE 4.35        finish dispensing with measured litres
 *   STATUS               show current state
 *
 * Backend endpoints used (JSON over HTTP):
 *   POST /api/v1/fcc/transaction/initiate
 *   GET  /api/v1/fcc/commands/poll?device_uid=...
 *   POST /api/v1/fcc/commands/ack
 *   POST /api/v1/fcc/transaction/complete
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ---- CONFIGURE FOR YOUR BENCH -------------------------------------------
const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";
const char* BACKEND   = "http://192.168.1.100:8000";   // PC running uvicorn
const char* STATION_ID = "YOUR_STATION_ID";
const char* NOZZLE_A_ID = "YOUR_NOZZLE_A_ID";
const char* NOZZLE_B_ID = "YOUR_NOZZLE_B_ID";
const char* POS_SN      = "YOUR_OPAY_POS_SN";
const char* DEVICE_UID_A = "FCC-DEV-A";
const char* DEVICE_UID_B = "FCC-DEV-B";
float UNIT_PRICE = 1150.0;      // NGN per litre, overridden by backend response
const int PULSES_PER_LITRE = 1; // bench default - set from real pulser spec

// ---- PINS ---------------------------------------------------------------
#define RELAY_A   26
#define RELAY_B   25
#define LED_PIN   2
#define PULSE_A   27
#define PULSE_B   14

// ---- STATE --------------------------------------------------------------
enum State { IDLE, PAYMENT_PENDING, AUTHORIZED, DISPENSING, COMPLETE, ERROR_STATE };
State state = IDLE;
String activeTx = "";
String activeNozzle = "A";
float authorizedLitres = 0;
volatile unsigned long pulses = 0;
unsigned long lastPoll = 0;
unsigned long dispenseStart = 0;

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_A, OUTPUT); pinMode(RELAY_B, OUTPUT);
  pinMode(LED_PIN, OUTPUT); pinMode(PULSE_A, INPUT_PULLUP); pinMode(PULSE_B, INPUT_PULLUP);
  closeValves();
  WiFi.mode(WIFI_STA); WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nREADY. Type HELP for commands.");
  attachInterrupt(digitalPinToInterrupt(PULSE_A), onPulseA, FALLING);
  attachInterrupt(digitalPinToInterrupt(PULSE_B), onPulseB, FALLING);
}

void IRAM_ATTR onPulseA() { if (activeNozzle == "A") pulses++; }
void IRAM_ATTR onPulseB() { if (activeNozzle == "B") pulses++; }

void closeValves() {
  digitalWrite(RELAY_A, HIGH); digitalWrite(RELAY_B, HIGH); // active-low relay modules
  digitalWrite(LED_PIN, LOW);
  Serial.println("[VALVE] CLOSED (both nozzles)");
}
void openValve(char n) {
  closeValves();
  if (n == 'A') digitalWrite(RELAY_A, LOW); else digitalWrite(RELAY_B, LOW);
  digitalWrite(LED_PIN, HIGH);
  Serial.printf("[VALVE] OPEN nozzle %c\n", n);
}

String postJson(const char* path, String body) {
  if (WiFi.status() != WL_CONNECTED) return "{\"error\":\"wifi_offline\"}";
  HTTPClient http; http.begin(String(BACKEND) + path);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(body);
  String res = http.getString(); http.end();
  Serial.printf("[HTTP] POST %s -> %d\n", path, code);
  return res;
}
String getJson(String path) {
  if (WiFi.status() != WL_CONNECTED) return "[]";
  HTTPClient http; http.begin(String(BACKEND) + path);
  int code = http.GET(); String res = http.getString(); http.end();
  Serial.printf("[HTTP] GET %s -> %d\n", path.c_str(), code);
  return res;
}

void initPayment(float amount) {
  if (amount <= 0) { Serial.println("ERR: amount must be positive"); return; }
  activeTx = "FCCTX" + String(millis());
  String nozzleId = activeNozzle == "A" ? NOZZLE_A_ID : NOZZLE_B_ID;
  String deviceUid = activeNozzle == "A" ? DEVICE_UID_A : DEVICE_UID_B;
  StaticJsonDocument<512> doc;
  doc["client_tx_ref"] = activeTx;
  doc["nozzle_id"] = nozzleId;
  doc["target_amount_ngn"] = amount;
  doc["payment_preference"] = "POS";
  doc["pos_sn"] = POS_SN;
  doc["device_uid"] = deviceUid;
  String body; serializeJson(doc, body);
  String res = postJson("/api/v1/fcc/transaction/initiate", body);
  Serial.println("[INIT] " + res);
  StaticJsonDocument<1024> parsed;
  if (!deserializeJson(parsed, res)) {
    authorizedLitres = parsed["authorized_liters"] | 0;
    UNIT_PRICE = parsed["unit_price_ngn"] | UNIT_PRICE;
    state = PAYMENT_PENDING;
    Serial.printf("[INIT] Pending %.2f L at NGN %.2f/L\n", authorizedLitres, UNIT_PRICE);
  } else state = ERROR_STATE;
}

void pollCommands() {
  String uid = activeNozzle == "A" ? DEVICE_UID_A : DEVICE_UID_B;
  String res = getJson("/api/v1/fcc/commands/poll?device_uid=" + uid + "&limit=10");
  Serial.println("[POLL] " + res);
  // Minimal command extraction (avoids full array parsing on ESP32)
  int typePos = res.indexOf("\"type\":\"PAYMENT_SUCCESS\"");
  int idPos = res.indexOf("\"id\":\"");
  String cmdId = "";
  if (idPos >= 0) {
    int start = idPos + 6; int end = res.indexOf('"', start);
    cmdId = res.substring(start, end);
  }
  if (typePos >= 0) {
    state = AUTHORIZED;
    openValve(activeNozzle.charAt(0));
    pulses = 0; dispenseStart = millis(); state = DISPENSING;
    Serial.println("[PAYMENT] APPROVED - dispensing");
    if (cmdId.length()) postJson("/api/v1/fcc/commands/ack", "{\"command_id\":\"" + cmdId + "\"}");
  } else if (res.indexOf("PAYMENT_FAILED") >= 0) {
    state = ERROR_STATE; closeValves();
    if (cmdId.length()) postJson("/api/v1/fcc/commands/ack", "{\"command_id\":\"" + cmdId + "\"}");
  }
}

void complete(float litres) {
  StaticJsonDocument<512> doc;
  doc["client_tx_ref"] = activeTx;
  doc["dispenser_id"] = "DISPENSER_ID";
  doc["dispensed_liters"] = litres;
  doc["cpu_volume_l"] = litres;
  doc["pulser_volume_l"] = (float)pulses / PULSES_PER_LITRE;
  doc["raw_pulse_count"] = pulses;
  doc["unit_price_ngn"] = UNIT_PRICE;
  doc["total_charged_ngn"] = litres * UNIT_PRICE;
  String body; serializeJson(doc, body);
  Serial.println("[COMPLETE] " + postJson("/api/v1/fcc/transaction/complete", body));
  closeValves(); state = COMPLETE;
}

void loop() {
  if (Serial.available()) handleSerial(Serial.readStringUntil('\n'));
  if (state == DISPENSING && pulses >= (unsigned long)(authorizedLitres * PULSES_PER_LITRE)) {
    complete((float)pulses / PULSES_PER_LITRE);
  }
  if (millis() - lastPoll > 2000) { lastPoll = millis(); if (state == PAYMENT_PENDING) pollCommands(); }
  delay(10);
}

void handleSerial(String line) {
  line.trim();
  if (line == "HELP") {
    Serial.println("NOZZLE A|B | INIT <amount|NL> | POLL | ACK <id> | COMPLETE <L> | STATUS");
  } else if (line.startsWith("NOZZLE ")) {
    activeNozzle = line.substring(7); activeNozzle.trim();
    Serial.println("[NOZZLE] " + activeNozzle);
  } else if (line.startsWith("INIT ")) {
    String v = line.substring(5); v.trim();
    float amount = v.endsWith("L") ? v.substring(0, v.length()-1).toFloat() * UNIT_PRICE : v.toFloat();
    initPayment(amount);
  } else if (line == "POLL") pollCommands();
  else if (line.startsWith("ACK ")) {
    Serial.println(postJson("/api/v1/fcc/commands/ack", "{\"command_id\":\"" + line.substring(4) + "\"}"));
  } else if (line.startsWith("COMPLETE ")) complete(line.substring(9).toFloat());
  else if (line == "STATUS") {
    Serial.printf("STATE=%d NOZZLE=%s TX=%s PULSES=%lu LITRES=%.2f\n",
                  state, activeNozzle.c_str(), activeTx.c_str(), pulses, (float)pulses / PULSES_PER_LITRE);
  }
}
