/*
 * VISUAL EYES 360 - PROTOTYPE BOARD 4: PULSE SIMULATOR
 * Generates pulses so you can test the pulser reader without a real pump.
 * Wire GPIO 26 of this board to GPIO 27 of board 3 (common GND).
 * No Wi-Fi is needed on this board. Serial 115200.
 *
 * Serial commands: HELP | START | STOP | RATE <ms> | BURST <n> | STATUS
 * Default rate 1000ms = 1 pulse/second. With PULSES_PER_LITRE=1 that is 1 L/s.
 *
 * LED: onboard GPIO2 blinks once for every generated pulse.
 */

#define PULSE_OUT 26
#define PULSE_LED 2          // onboard LED: one blink per pulse
unsigned long intervalMs = 1000;
unsigned long lastPulse = 0;
unsigned long pulseLedOffAt = 0;
bool running = false;
unsigned long total = 0;

void blinkPulseLed() {
  unsigned long onMs = intervalMs >= 100UL ? 40UL : 12UL;
  digitalWrite(PULSE_LED, HIGH);
  pulseLedOffAt = millis() + onMs;
}

void emitPulse() {
  digitalWrite(PULSE_OUT, HIGH);
  delayMicroseconds(200);
  digitalWrite(PULSE_OUT, LOW);
  blinkPulseLed();
  total++;
  Serial.printf("[PULSE] %lu  (%.1f L if 1 pulse/L)\n", total, (float)total);
}

void setup() {
  Serial.begin(115200);
  pinMode(PULSE_OUT, OUTPUT); digitalWrite(PULSE_OUT, LOW);
  pinMode(PULSE_LED, OUTPUT); digitalWrite(PULSE_LED, LOW);
  Serial.println("READY. Type HELP for commands.");
}

void loop() {
  if (Serial.available()) {
    String c = Serial.readStringUntil('\n'); c.trim();
    if (c == "HELP") Serial.println("START | STOP | RATE <ms> | BURST <n> | STATUS");
    else if (c == "START") { running = true; Serial.println("[SIM] running"); }
    else if (c == "STOP") { running = false; Serial.println("[SIM] stopped"); }
    else if (c.startsWith("RATE ")) {
      unsigned long requested = (unsigned long) c.substring(5).toInt();
      intervalMs = requested < 20UL ? 20UL : requested;
      Serial.printf("[SIM] rate %lums\n", intervalMs);
    }
    else if (c.startsWith("BURST ")) {
      int n = c.substring(6).toInt();
      for (int i = 0; i < n; i++) { emitPulse(); delay(10); }
    }
    else if (c == "STATUS") Serial.printf("[SIM] running=%s rate=%lums total=%lu\n", running?"YES":"NO", intervalMs, total);
  }
  if (running && millis() - lastPulse >= intervalMs) { lastPulse = millis(); emitPulse(); }
  if (pulseLedOffAt > 0 && millis() >= pulseLedOffAt) {
    digitalWrite(PULSE_LED, LOW);
    pulseLedOffAt = 0;
  }
  delay(5);
}
