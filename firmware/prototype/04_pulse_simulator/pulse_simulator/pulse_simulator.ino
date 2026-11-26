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
 *
 * NOZZLE TRIGGER MODE:
 *   Board 01 drives GPIO25 HIGH when the nozzle switch relay closes.
 *   While GPIO25 is HIGH, board 04 emits pulses automatically AND turns the
 *   motor driver on GPIO27 on. When Board 01 stops the trigger at the target
 *   litres, both motor and pulses stop.
 *   Manual START still works for standalone testing.
 *
 * MOTOR OUTPUT: GPIO27, active HIGH by default.
 *   Set MOTOR_ACTIVE_LOW to 1 if your relay module turns ON when IN is LOW.
 *   GPIO27 drives a motor driver/relay input only — never power a motor from it.
 */

#define PULSE_OUT 26
#define PULSE_LED 2          // onboard LED: one blink per pulse
#define TRIGGER_IN 25        // from Board 01 GPIO32; HIGH = nozzle switch closed
#define MOTOR_OUT 27         // to motor driver/relay input
#define MOTOR_ACTIVE_LOW 0   // set to 1 for active-low relay modules
unsigned long intervalMs = 1000;
unsigned long lastPulse = 0;
unsigned long pulseLedOffAt = 0;
bool running = false;
bool triggerWasActive = false;
bool motorOn = false;
unsigned long total = 0;

void setMotor(bool on) {
  if (motorOn == on) return;
  motorOn = on;
  bool level = MOTOR_ACTIVE_LOW ? !on : on;
  digitalWrite(MOTOR_OUT, level ? HIGH : LOW);
  Serial.println(on ? "[MOTOR] ON" : "[MOTOR] OFF");
}

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
  pinMode(TRIGGER_IN, INPUT_PULLDOWN);
  pinMode(MOTOR_OUT, OUTPUT);
  digitalWrite(MOTOR_OUT, MOTOR_ACTIVE_LOW ? HIGH : LOW);
  Serial.println("READY. Type HELP for commands.");
  Serial.println("AUTO: GPIO25 HIGH from Board 01 starts motor + pulses.");
  Serial.println("MOTOR: GPIO27 output, active HIGH by default.");
}

void loop() {
  if (Serial.available()) {
    String c = Serial.readStringUntil('\n'); c.trim();
    if (c == "HELP") {
      Serial.println("START | STOP | RATE <ms> | BURST <n> | STATUS");
      Serial.println("AUTO: GPIO25 HIGH = motor + pulse, GPIO25 LOW = stop");
      Serial.println("MOTOR OUT = GPIO27");
    }
    else if (c == "START") { running = true; Serial.println("[SIM] running"); }
    else if (c == "STOP") { running = false; Serial.println("[SIM] stopped"); }
    else if (c.startsWith("RATE ")) {
      unsigned long requested = (unsigned long) c.substring(5).toInt();
      intervalMs = requested < 20UL ? 20UL : requested;
      Serial.printf("[SIM] rate %lums\n", intervalMs);
    }
    else if (c.startsWith("BURST ")) {
      int n = c.substring(6).toInt();
      setMotor(true);
      for (int i = 0; i < n; i++) { emitPulse(); delay(10); }
      setMotor(false);
    }
    else if (c == "STATUS") Serial.printf("[SIM] running=%s trigger=%s motor=%s rate=%lums total=%lu\n",
                                           running ? "YES" : "NO",
                                           digitalRead(TRIGGER_IN) == HIGH ? "ON" : "OFF",
                                           motorOn ? "ON" : "OFF",
                                           intervalMs, total);
  }

  bool triggerActive = digitalRead(TRIGGER_IN) == HIGH;
  if (triggerActive != triggerWasActive) {
    triggerWasActive = triggerActive;
    Serial.println(triggerActive ? "[TRIGGER] nozzle switch CLOSED - motor + pulses ON"
                                 : "[TRIGGER] nozzle switch OPEN - motor + pulses OFF");
  }

  bool shouldRun = running || triggerActive;
  setMotor(shouldRun);

  if (shouldRun && millis() - lastPulse >= intervalMs) {
    lastPulse = millis();
    emitPulse();
  }
  if (pulseLedOffAt > 0 && millis() >= pulseLedOffAt) {
    digitalWrite(PULSE_LED, LOW);
    pulseLedOffAt = 0;
  }
  delay(5);
}
