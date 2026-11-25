# 10 — Prototype hardware guide (4 × ESP32)

This is the **bench build** only. It is not safe for a live forecourt, not
intrinsically safe, and does not replace certified interfaces. The backend
protocol is documented in `docs/09-hardware-api.md`.

## 1. Board roles

| Board | Sketch | Role | Inputs | Outputs |
|---|---|---|---|---|
| 1 | `firmware/prototype/01_fcc_pump` | FCC pump controller, double nozzle, the only TFT screen | Serial commands, pulse inputs GPIO 27/14 | Relay GPIO 26/25, HTTP to backend, Serial |
| 2 | `firmware/prototype/02_tank_monitor` | Tank level + environment | HC-SR04, DHT11, lid limit switch | HTTP telemetry, Serial |
| 3 | `firmware/prototype/03_pulser_reader` | Pulse counting | Pulse on GPIO 27 (from board 4 or optocoupler) | HTTP telemetry, Serial |
| 4 | `firmware/prototype/04_pulse_simulator` | Bench pulse generator | Serial commands | Pulses on GPIO 26 |

All boards print structured lines to Serial Monitor at **115200 baud** and accept
commands typed into Serial Monitor. That is the prototype "input and output" link
you asked for.

## 2. Configuring each sketch

In every sketch set at the top:
- `WIFI_SSID` / `WIFI_PASS` — your bench Wi-Fi
- `BACKEND` — `http://<PC-IP>:8000` (the IP of the machine running uvicorn)
- IDs copied from the web app (station, nozzle, tank, POS SN, device UID)

`BACKEND` must be an IP, not `localhost`, because `localhost` on the ESP32 is the
ESP32 itself.

## 3. Building a pulser input from the pump's 12 V pulse

**Never connect 12 V to an ESP32 GPIO.** The pin tolerates 0–3.3 V only.

### 3.1 Recommended: optocoupler (isolated)

```
PUMP PULSE 12V  ──[ 1kΩ ]──> PC817 pin 1 (anode)
PUMP GROUND    ─────────────> PC817 pin 2 (cathode)

ESP32 3.3V     ──[ 10kΩ ]──> PC817 pin 4 (collector) ──> GPIO 27
ESP32 GND      ─────────────> PC817 pin 3 (emitter)
```

- No common ground between pump and ESP32 — this is the safe part.
- When the pump pulse goes high, the optocoupler LED lights, the transistor
  conducts and pulls GPIO 27 low. The sketch counts FALLING edges.
- Add a 100 nF capacitor across the 1 kΩ resistor if the pulse is noisy.
- Software debounce is already 3 ms in `03_pulser_reader`.

### 3.2 Alternative: NPN transistor (non-isolated, bench only)

```
PUMP PULSE 12V ──[ 10kΩ ]──> BC547 BASE
PUMP GROUND   ─────────────> BC547 EMITTER ──> ESP32 GND   (common ground!)
ESP32 3.3V    ──[ 10kΩ ]──> BC547 COLLECTOR ──> GPIO 27
```

This requires the pump ground and ESP32 ground to be tied together. Use it only
on an isolated bench supply. For anything near a real dispenser, use the
optocoupler.

### 3.3 No real pulser? Use board 4

Wire **GPIO 26 (board 4) → GPIO 27 (board 3)** and common the grounds. Open both
Serial Monitors:

```
Board 4: START        (or RATE 500 for faster pulses, BURST 10 for exact counts)
Board 3: COUNT        (shows pulses and litres)
Board 3: RATE 1       (1 pulse = 1 litre for the bench)
Board 3: SEND         (posts the count to the backend)
```

## 4. Other wiring

| Device | ESP32 pin | Note |
|---|---|---|
| HC-SR04 TRIG | GPIO 5 | direct |
| HC-SR04 ECHO | GPIO 18 | **5 V → 3.3 V via 2k2 series + 3k3 to GND divider** |
| DHT11 data | GPIO 4 | 4k7 pull-up to 3.3 V |
| Lid limit switch | GPIO 19 | `INPUT_PULLUP`; switch closes to GND = OPEN |
| Relay (valve) A / B | GPIO 26 / 25 | active-low relay module; check your module |
| TFT (optional) | CS 15, DC 4, RST 14, MOSI 23, SCLK 18 | the one screen goes on board 1 |

Add a flyback diode across any solenoid coil and a fuse on the 12 V supply.

## 5. Serial command reference

| Board | Commands |
|---|---|
| 1 FCC | `HELP`, `NOZZLE A|B`, `INIT 5000` or `INIT 5L`, `POLL`, `ACK <id>`, `COMPLETE 4.35`, `STATUS` |
| 2 Tank | `HELP`, `READ`, `SEND`, `STATUS`, `LID` |
| 3 Pulser | `HELP`, `COUNT`, `RESET`, `RATE <n>`, `SEND`, `STATUS` |
| 4 Simulator | `HELP`, `START`, `STOP`, `RATE <ms>`, `BURST <n>`, `STATUS` |

## 6. Backend endpoints the sketches call

| Endpoint | Used by | Purpose |
|---|---|---|
| `POST /api/v1/fcc/transaction/initiate` | Board 1 | Create payment, push order to OPay POS |
| `GET /api/v1/fcc/commands/poll?device_uid=…` | Board 1 | Fetch `PAYMENT_SUCCESS` / `PAYMENT_FAILED` |
| `POST /api/v1/fcc/commands/ack` | Board 1 | Acknowledge a command |
| `POST /api/v1/fcc/transaction/complete` | Board 1 | Record CPU/pulser volumes and discrepancy |
| `POST /api/v1/device/prototype/telemetry` | Boards 2, 3 | Store tank/pulse readings |

The local OPay simulator runs inside the same backend at `/mock-opay`. With
`USE_MOCK_OPAY_GATEWAY=true` it fires a signed webhook about 3.5 s after payment
creation, so you can watch the whole flow without a physical POS terminal.

## 7. Bench workflow

1. Register a station, dispenser, nozzle, tank, POS terminal and FCC in the web
   app; set the nozzle price. Copy their IDs into the sketches.
2. Start the backend with `USE_MOCK_OPAY_GATEWAY=true`.
3. Flash all four boards; open Serial Monitors.
4. Board 4: `START`. Board 3: `COUNT` — pulses should increase; `SEND`.
5. Board 2: `READ`, then `SEND` — check the tank reading in the web app.
6. Board 1: `NOZZLE A`, `INIT 5000` — watch the backend log for the OPay create
   and webhook. After ~4 s, `POLL` — you should get `PAYMENT_SUCCESS`.
7. Board 1 then opens the relay, counts pulses, and on reaching the target calls
   `COMPLETE 4.35`. Check the transaction, discrepancy and alert screens.

## 8. Safety rules (non-negotiable)

- No 12 V on GPIO. Use the optocoupler or divider.
- No Ethernet anywhere on the controller network.
- The dispenser CPU retains normal control; the FCC only requests presets through
  a documented interface. Never bypass interlocks or E-stop.
- No payment verification → no valve open. No auto-resume after power loss.
- Dev boards are not intrinsically safe. This guide is bench-only.
