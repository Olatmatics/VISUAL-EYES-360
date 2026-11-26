# 10 — Beginner guide: VISUAL EYES 360 bench hardware → software

This is the **bench/prototype build only**. It is not safe for a live forecourt,
is not intrinsically safe, and does not implement a real dispenser protocol.
Development boards are not certified for hazardous areas. Nothing here claims
that OPay sandbox references are payment proof.

Use this guide in order. You can do **every test from Serial Monitor**; the web
pages are for viewing and for the settings you do not want to type each time.

---

## 1. The five boards

| Board | Sketch folder | What it does |
|---|---|---|
| 1 | `firmware/prototype/01_fcc_pump` | FCC controller. Opens/closes two valve relays, starts POS payment, polls for approval, records completion. Has the only optional TFT. |
| 2 | `firmware/prototype/02_tank_monitor` | Ultrasonic level, DHT11 temperature/humidity, lid switch. Sends tank telemetry. |
| 3 | `firmware/prototype/03_pulser_reader` | **Separate ESP32** that only counts pump pulses and converts them to litres. This is the independent pulser for reconciliation. |
| 4 | `firmware/prototype/04_pulse_simulator` | Generates pulses so you can test board 3 without a pump. |
| 5 | `firmware/prototype/05_rfid_reader` | MFRC522 card reader. A manager places a card, sees its UID, and saves it for a station. Also funds/pays from the wallet. |

All sketches use **Serial Monitor at 115200 baud**. Type `HELP` in any board to
see its commands. Every board prints the exact JSON it sends and receives when
`JSON ON` is set (the default).

### Addresses on this bench

```text
Backend (ESP32 must use this): http://172.25.0.37:8000
Web app:                       http://127.0.0.1:5173
Login:                         SUPERADMIN001 / Admin@1234
```

`172.25.0.37` is the Wi-Fi IPv4 address of the PC running the backend. Do **not**
use `localhost` in a sketch: on an ESP32, `localhost` means the ESP32 itself.
`192.168.56.1` is a VirtualBox host-only adapter and must not be used.

Start the backend from `backend/` with:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Keep `USE_MOCK_OPAY_GATEWAY=true` for bench testing. The mock webhook fires about
3.5 seconds after payment creation.

---

## 2. Arduino IDE setup (one time)

1. Install the **ESP32 Boards** package (Espressif).
2. Install libraries: **ArduinoJson 6.x** (`StaticJsonDocument` is used),
   **MFRC522** by Miguel Balboa, and **Adafruit DHT sensor library**.
3. Select board **ESP32 Dev Module**, the correct COM port, and upload at 115200.
4. After uploading, open Serial Monitor and type `HELP` to confirm the sketch is alive.

You do not need to edit code to configure the bench. All Wi-Fi sketches now
default to SSID `cypher` and password `12345678`, so a fresh board connects
without typing `SET WIFI`. All settings are saved in ESP32 Preferences and
survive a power cycle. If a board was flashed with older settings, type
`SET WIFI cypher|12345678` and then `REBOOT`. Board 4 has no Wi-Fi — it only
generates pulses.

---

## 3. Web setup before powering boards

Do this once, in this order. It is also summarised in
`docs/11-prototype-registration-checklist.md`.

1. **Station** — register the station. Current bench station:
   `matics oil and gas`, ID `923a0b56-6e8f-4dc4-89f2-1f0dd8a93628`.
2. **Dispenser/nozzles** — register a Double dispenser and set the nozzle price.
   Current bench dispenser: `PMP-010B18`, ID `6815b668-c76b-4cf8-ba20-a8959c95c3de`.
3. **POS terminal** — Payments → **+ Register POS Terminal**. You must select the
   **nozzle** the terminal belongs to. The FCC sketch will not start a POS payment
   until this assignment exists. This is the one step people usually miss.
4. **FCC controller** — register one controller per nozzle with the exact UID used
   in the sketch. Current bench UID: `fcc-matics-001`.
5. **Pulse MATH** — Infrastructure → **Pulse MATH (Serial + Web)**. Set
   pulses per litre for that FCC. Both the FCC sketch and the separate pulser
   sketch read this same backend value.
6. **Tank + controller** — register the tank (`TK-27CCC8` or `TK-BF7475`) and its
   controller UID if board 2 is used.
7. **RFID station reader** — the RFID sketch's `SET STATION` must be the station
   where the manager is registering cards. Cards stay nationwide after that.
8. Copy IDs from **Device ID Directory**. It shows every ID with a copy button.
   If you ever reset operational data, copy the new IDs again — do not assume the
   ones in this guide still exist.

The ticker shows a device as online only when its heartbeat is inside the
**240-second** window (`DEVICE_OFFLINE_AFTER_MINUTES=4`). Board 1 sends a
heartbeat every 30 seconds automatically.

---

## 4. Board 1 — FCC pump controller

Open `01_fcc_pump/fcc_pump.ino`, upload, then type these in Serial Monitor.
Using the current bench IDs:

```text
SET WIFI your-wifi-name|your-wifi-password
SET BACKEND http://172.25.0.37:8000
SET STATION 923a0b56-6e8f-4dc4-89f2-1f0dd8a93628
SET DISPENSER 6815b668-c76b-4cf8-ba20-a8959c95c3de
SET NOZZLE_A d26a4199-393b-40fc-b4b6-45bea91a10c2
SET NOZZLE_B c802f109-0912-4968-87b2-762560ec4276
SET DEVICE_A fcc-matics-001
SET DEVICE_B FCC-DEV-B
SET POS YOUR_OPAY_POS_SN
SET PRICE 1150
REBOOT
```

Then:

```text
CONFIG              show everything saved
HEARTBEAT           force a ticker heartbeat now
CAL FETCH           read pulses/L from the web MATH page
CAL SET 100         write pulses/L from Serial (same backend field)
JSON ON             print exact request/response JSON (default)
```

### Dispensing test

```text
NOZZLE A
INIT 5000           NGN 5,000 POS payment (or INIT 5L)
POLL                collect PAYMENT_SUCCESS after the mock webhook
COMPLETE 4.35       finish with measured litres
STATUS              state, pulses, litres, authorized volume
RESET               clear the transaction and close valves
```

Automatic behaviour: while a payment is pending the board polls every 2 seconds,
opens the valve only on `PAYMENT_SUCCESS`, counts pulses, and calls `COMPLETE`
when litres reach the authorized amount. If `PAYMENT_FAILED` arrives, the valve
stays closed.

JSON examples for this board are in section 8.

---

## 5. Board 3 — independent pulser and the MATH

This board is deliberately separate from the FCC/payment board. It only counts
pulses and converts raw counts to volume. Configure it:

```text
SET WIFI your-wifi-name|your-wifi-password
SET BACKEND http://172.25.0.37:8000
SET DEVICE PULSE-DEV-01
SET FCC fcc-matics-001
SET NOZZLE d26a4199-393b-40fc-b4b6-45bea91a10c2
CONFIG
REBOOT
```

### The MATH you must know

```text
pulses_per_litre (PPL) = counted pulses ÷ known litres
litres                 = raw_pulse_count ÷ PPL
litres/sec             = pulses/sec ÷ PPL
litres/min             = (pulses/sec ÷ PPL) × 60
seconds for 5 L        = (5 × PPL) ÷ pulses/sec
```

Example: a controlled 10 L test produces 1000 pulses → `PPL = 1000 ÷ 10 = 100`.
Then 1235 pulses = `1235 ÷ 100 = 12.35 L`.

Set it from either place:

- Web: Infrastructure → **Pulse MATH (Serial + Web)** → choose FCC → save.
- Serial on board 3: `SET PPL 100` (also writes the same backend field).
- Serial on board 1: `CAL SET 100`.

Whichever you use last wins. Board 3 also runs `CAL FETCH` at boot.

### Commands

```text
COUNT               raw pulse count and litres
RESET               zero the counter
MATH 1000           convert 1000 pulses to litres
MATH RATE 10        convert 10 pulses/sec to L/sec and L/min
MATH PPS            measured vs configured pulse rate
SET PPS 10          expected pulses/sec for bench math
SEND                post one telemetry reading now
STATUS              UID, count, PPL, litres, measured pps, Wi-Fi
```

The board automatically posts telemetry every 10 seconds. Its JSON includes
`raw_pulse_count`, `pulses_per_litre`, `pulser_volume_l`, `pulses_per_second`
and `litres_per_second`. Watch it in **Hardware JSON Monitor**.

---

## 6. Boards 4 and 2 — pulse generator and tank

### Board 4 → Board 3 without a pump

Wire **GPIO 26 (board 4) → GPIO 27 (board 3)** and connect their grounds.

```text
Board 4: START          (default 1 pulse/sec)
Board 4: RATE 100       (10 pulses/sec)
Board 4: BURST 100      (exact 100 pulses)
Board 3: COUNT          (should increase)
Board 3: SEND           (see the JSON in Hardware JSON Monitor)
```

### Board 2 tank test

```text
SET WIFI your-wifi-name|your-wifi-password
SET BACKEND http://172.25.0.37:8000
SET DEVICE TANK-DEV-01
SET TANK 4d29b187-3ee7-473d-b434-558adf344d65
SET HEIGHT 200
SET CAPACITY 30000
REBOOT
READ
SEND
```

Board 2 also saves all values in Preferences; no code edit is needed.

HC-SR04 ECHO is 5 V and must go through a **2k2 + 3k3 divider** to GPIO 18.
Never put 12 V on an ESP32 GPIO.

---

## 7. Board 5 — RFID card registration and wallet

MFRC522 wiring (hardware SPI): `SDA/CS 27 | SCK 18 | MOSI 23 | MISO 19 | RST 5 |
3.3 V | GND`. Do not power the reader from 5 V.

Configure:

```text
SET WIFI your-wifi-name|your-wifi-password
SET BACKEND http://172.25.0.37:8000
SET APIKEY dev-ingest-key-change-me
SET STATION 923a0b56-6e8f-4dc4-89f2-1f0dd8a93628
SET NOZZLE d26a4199-393b-40fc-b4b6-45bea91a10c2
CONFIG
REBOOT
```

### Manager enrolment flow (this is the requested flow)

```text
REGISTER               Serial prints: "Place the NEW customer card (30s)"
[place card on reader]
                       Serial prints the UID, e.g. "UID READ: A1B2C3D4"
NAME Alu Ada           optional owner name
SAVE                   sends UID + station to the backend
```

Serial then prints the UID, owner, home station, balance, and `NATIONWIDE: YES`.
The exact JSON is printed too and can be opened in **Hardware JSON Monitor**.

**A card is nationwide.** `home_station_id` records where it was first registered;
it does *not* restrict use. The same UID works at any station in any state. The
backend, not the card, owns identity, balance and authorization. A card by itself
is never proof of payment. This is a UID-only bench reader; real secure keys are
still an open item in `docs/08-open-items.md`.

Every time a card is placed on the reader, its UID is printed. For an existing
card:

```text
SCAN                recognise card and show balance
FUND 5000           bench funding after a verified external payment
PAY 5000            debit wallet + queue PAYMENT_SUCCESS for the nozzle FCC
CARD                show the current UID
STATUS              UID, balance, Wi-Fi, pending registration
CANCEL              abort a pending registration
```

`PAY` uses the same command path as OPay: the approval appears when board 1 runs
`POLL`, then `ACK`. The wallet payment creates a verified `PaymentRecord`, so the
later `COMPLETE` call works exactly like the POS flow.

---

## 8. POS / OPay explanation (important)

The tested Sunbeth build worked like this:

1. Software creates an OPay POS payment (`create_pos_payment`) with the POS serial
   number that is registered in the OPay merchant dashboard.
2. OPay sends a signed webhook to the software.
3. Software verifies the signature, marks the payment `VERIFIED`, and queues a
   hardware command.
4. Their device receives that command over WebSocket and opens the valve.

Our bench build follows the same business rule but uses simpler transport:

1. Board 1 `INIT 5000` → `POST /api/v1/fcc/transaction/initiate`.
2. Backend finds the active POS terminal assigned to that nozzle and calls OPay.
3. Mock OPay (or real OPay in sandbox) posts `/api/v1/opay/webhook`.
4. Backend verifies and queues `PAYMENT_SUCCESS` in `device_commands`.
5. Board 1 `POLL` collects it, `ACK` confirms it, and only then does the valve open.
6. Board 1 `COMPLETE` records litres, pulses and any CPU/pulser discrepancy.

Why the nozzle assignment matters: a payment must know which pump/nozzle and
which POS serial to use. If `INIT` replies `400 No POS terminal assigned to this
nozzle`, go to Payments and assign the terminal to the nozzle. The mock's
sandbox references are not payment proof; live credentials belong in `.env`,
never in a sketch or in git.

OPay signing (already implemented) is: recursively sort JSON keys → compact JSON
(no spaces) → HMAC-SHA512 with the private key → `Authorization: Bearer <signature>`
with `MerchantId` header.

---

## 9. Exact JSON exchanged (visible in the web)

Open **Infrastructure → Hardware JSON Monitor**. It shows IN
(hardware → software) and OUT (software → hardware) rows with both the request
and response JSON. Set `JSON ON` on a board to see the same text in Serial.

### 9.1 FCC heartbeat (IN)

```json
POST /api/v1/fcc/prototype/heartbeat
{
  "device_uid": "fcc-matics-001",
  "firmware_version": "ve360-fcc-bench-1.1",
  "signal_strength_dbm": -55
}
```

```json
{
  "accepted": true,
  "device_uid": "fcc-matics-001",
  "is_online": true,
  "last_seen": "2026-11-26T07:23:01.204706"
}
```

### 9.2 Pulse MATH calibration (IN)

```json
PATCH /api/v1/fcc/calibration
{
  "device_uid": "fcc-matics-001",
  "pulses_per_litre": 100.0
}
```

```json
{
  "device_uid": "fcc-matics-001",
  "pulses_per_litre": 100.0,
  "formula": "litres = raw_pulse_count / pulses_per_litre"
}
```

`GET /api/v1/fcc/calibration?device_uid=fcc-matics-001` returns the same value
plus station, nozzle and dispenser IDs.

### 9.3 Separate pulser telemetry (IN)

```json
POST /api/v1/device/prototype/telemetry
{
  "device_uid": "PULSE-DEV-01",
  "kind": "PULSE",
  "event_id": "PULSE0007",
  "fcc_device_uid": "fcc-matics-001",
  "nozzle_id": "d26a4199-393b-40fc-b4b6-45bea91a10c2",
  "readings": {
    "raw_pulse_count": 1235,
    "pulses_per_litre": 100.0,
    "pulser_volume_l": 12.35,
    "pulses_per_second": 10.0,
    "litres_per_second": 0.1,
    "source": "INDEPENDENT_PULSER_ESP32"
  }
}
```

```json
{"accepted": true, "duplicate": false, "device_uid": "PULSE-DEV-01"}
```

### 9.4 RFID registration (IN)

```json
POST /api/v1/rfid/prototype/register
X-API-Key: dev-ingest-key-change-me
{
  "uid": "A1B2C3D4",
  "owner": "Alu Ada",
  "station_id": "923a0b56-6e8f-4dc4-89f2-1f0dd8a93628"
}
```

```json
{
  "registered": true,
  "uid": "A1B2C3D4",
  "owner": "Alu Ada",
  "home_station_id": "923a0b56-6e8f-4dc4-89f2-1f0dd8a93628",
  "home_station": "matics oil and gas",
  "balance_ngn": 0.0,
  "nationwide": true,
  "message": "NEW CARD SAVED"
}
```

### 9.5 Wallet payment and queued command (IN + OUT)

```json
POST /api/v1/rfid/authorize
{
  "uid": "A1B2C3D4",
  "amount_ngn": 5000,
  "nozzle_id": "d26a4199-393b-40fc-b4b6-45bea91a10c2"
}
```

```json
{
  "reference": "RFID-4936685E68",
  "status": "APPROVED",
  "amount_ngn": 5000.0,
  "balance_ngn": 0.0,
  "authorized_liters": 4.35,
  "device_uid": "fcc-matics-001"
}
```

OUT row (queued for the FCC to collect with `POLL`):

```json
GET /api/v1/fcc/commands/poll?device_uid=fcc-matics-001
[
  {
    "id": "4fac9d47-d054-41e9-98b6-1873d22bdf88",
    "type": "PAYMENT_SUCCESS",
    "payload": {
      "reference": "RFID-4936685E68",
      "status": "APPROVED",
      "amount_ngn": 5000.0,
      "payment_method": "RFID_WALLET",
      "authorized_liters": 4.35
    }
  }
]
```

### 9.6 FCC initiate and completion (IN)

```json
POST /api/v1/fcc/transaction/initiate
{
  "client_tx_ref": "FCCTX12345",
  "nozzle_id": "d26a4199-393b-40fc-b4b6-45bea91a10c2",
  "target_amount_ngn": 5000,
  "payment_preference": "POS",
  "pos_sn": "YOUR_OPAY_POS_SN",
  "device_uid": "fcc-matics-001"
}
```

```json
{
  "reference": "FCCTX12345",
  "order_no": "<opay order number>",
  "status": "PENDING",
  "authorized_liters": 4.35,
  "unit_price_ngn": 1150.0,
  "opay_pos_sn": "YOUR_OPAY_POS_SN",
  "amount_ngn": 5000.0
}
```

After `POLL`, `ACK` and dispensing:

```json
POST /api/v1/fcc/transaction/complete
{
  "client_tx_ref": "FCCTX12345",
  "device_uid": "fcc-matics-001",
  "dispenser_id": "6815b668-c76b-4cf8-ba20-a8959c95c3de",
  "dispensed_liters": 4.35,
  "cpu_volume_l": 4.35,
  "pulser_volume_l": 4.34,
  "raw_pulse_count": 434,
  "pulses_per_litre": 100.0,
  "unit_price_ngn": 1150.0,
  "total_charged_ngn": 5000.0
}
```

```json
{
  "transaction_ref": "FCCTX12345",
  "dispensed_liters": 4.35,
  "difference_l": 0.01,
  "discrepancy": false
}
```

---

## 10. Full bench run (copy/paste order)

1. Start backend. Confirm `http://127.0.0.1:8000/health` returns OK.
2. Web: check station, dispenser, nozzle price, POS→nozzle assignment, FCC UID,
   Pulse MATH value. Open **Hardware JSON Monitor** and leave it open.
3. Board 4: `START`. Board 3: `COUNT` (pulses rise), `MATH 1000`, `SEND`.
   Confirm the IN row appears in the JSON monitor.
4. Board 1: `CONFIG`, `HEARTBEAT`, `CAL FETCH`. Confirm the ticker shows
   `fcc-matics-001` online, and the JSON monitor shows the heartbeat.
5. Board 5: `REGISTER`, place new card, `NAME ...`, `SAVE`. Confirm UID and
   `NATIONWIDE: YES`; then `FUND 5000`, `PAY 1000`.
6. Board 1: `NOZZLE A`, `POLL` (you should see the RFID `PAYMENT_SUCCESS`), `ACK`.
   The valve opens. For a POS test instead, use `INIT 5000` and wait ~4 s before
   `POLL`.
7. Board 1: `COMPLETE <litres>` or let it complete automatically from pulses.
8. Web: check Fuel Transactions, Pulser Verification, Alerts, and the JSON monitor.

To stop: board 1 `RESET` closes both valves; board 4 `STOP`.

---

## 11. Wiring summary

| Device | ESP32 pin | Note |
|---|---|---|
| Pulser input (board 3) | GPIO 27 | FALLING edge, 3 ms debounce, `INPUT_PULLUP` |
| Pulse simulator output (board 4) | GPIO 26 | wire to board 3 GPIO 27, common ground |
| Valve relay A / B (board 1) | GPIO 26 / 25 | active-low relay modules |
| Board 1 pulse inputs | GPIO 27 / 14 | optional local counting |
| HC-SR04 TRIG / ECHO | GPIO 5 / 18 | ECHO needs 2k2 + 3k3 divider |
| DHT11 data | GPIO 4 | 4k7 pull-up to 3.3 V |
| Lid limit switch | GPIO 19 | closes to GND = OPEN |
| MFRC522 SDA/SCK/MOSI/MISO/RST | 27 / 18 / 23 / 19 / 5 | 3.3 V only |
| Optional TFT | CS 15, DC 4, RST 14, MOSI 23, SCLK 18 | one screen on board 1 |

Pulser input from a pump: use an optocoupler (PC817) so there is **no common
ground**. A non-isolated transistor divider is bench-only. Add a flyback diode
across solenoid coils and a fuse on the 12 V supply.

---

## 12. Safety and scope (non-negotiable)

- Never connect 12 V to an ESP32 GPIO. GPIO is 0–3.3 V only.
- Dev boards are not intrinsically safe. Keep this on the bench.
- Do not bypass dispenser interlocks, E-stop, or the physical nozzle control.
- No verified payment → no valve open. No automatic resume after power loss.
- No claim of real Wayne/Gilbarco/Tatsuno protocol support; the CPU model remains
  the authority in a real installation.
- OPay secrets stay in `.env`. Never commit them or paste them into sketches.

## 13. Common failures

| Symptom | Fix |
|---|---|
| ESP32 cannot reach backend | Use `http://172.25.0.37:8000`, not localhost; backend must bind `0.0.0.0`. |
| Ticker shows device offline after 4 min | Send `HEARTBEAT`; check Wi-Fi and the UID registered in the web app. |
| `400 No POS terminal assigned to this nozzle` | Payments page → register/assign POS terminal to that nozzle. |
| `404 FCC controller not found` | Device UID in sketch must exactly match the registered FCC UID. |
| Card save fails | Check `SET STATION` and `SET APIKEY` on board 5. |
| `PAY` says insufficient balance | Run `FUND` first (bench only, after a verified external payment). |
| Pulser litres look wrong | Run a known-volume test and set `PPL = pulses ÷ litres` from Pulse MATH or Serial. |
| JSON monitor is empty | Type `HEARTBEAT`, `SEND`, `CAL FETCH` or `REGISTER` on a board; check `JSON ON`. |
| Frontend build warning about chunk size | Non-blocking; the app still builds and runs. |
