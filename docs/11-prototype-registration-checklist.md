# 11 — Prototype registration checklist

Do these **in order**. Each record must exist before the next one. The backend
rejects assignments to nonexistent or cross-station equipment.

## 0. Log in as the Superior Administrator

`SUPERADMIN001` / `Admin@1234`. A manager without `dispensers:create` will not
even see the **+ Register Dispenser** button.

**Faster path:** Infrastructure → **Generate Hardware IDs** is available only to
the Superior Administrator. It creates steps 1, 3, 5 and 6 together with short
copyable codes and ESP32 code blocks. See `docs/12-hardware-id-generator.md`.
The manual steps below still work and are useful when adding equipment to an
existing station.

## 1. Station — required first

Stations → **Register station**. Minimum: code, name, country, state, LGA, city,
address, GPS latitude/longitude, manager name + phone, supervisor name + phone.
A station must exist before a dispenser, tank, FCC or POS terminal.

## 2. Pump type (optional but recommended)

Dispensers → **Pump Type Management** → add e.g. `WAYNE_IGEM` / `Wayne iGEM`.
These become available in the dispenser dropdown.

## 3. Dispenser / pump

Dispensers → **+ Register Dispenser**:

| Field | Rule |
|---|---|
| Assigned station | must already exist; dropdown is populated from `/stations` |
| Dispenser code | required, unique within the station |
| Name / serial | optional, serial unique if supplied |
| Manufacturer | Wayne, Veeder-Root, Gilbarco, Tatsuno, Tokheim, Bennett or Other |
| Pump type | from step 2 |
| Nozzle configuration | **Single** = 1 record, **Double** = 2 records, **Other** = your count (1–12) |
| Nozzle 1 / 2 price | ₦/L, becomes the nozzle's selling price |

Creating a **Double** configuration automatically creates Nozzle 1 and Nozzle 2
with separate IDs, prices, FCC mappings and reconciliation history.

If this fails, the error banner shows the backend reason. The usual causes are:
- no station registered / no station selected
- duplicate dispenser code at that station
- duplicate serial number
- logged in as a user without `dispensers:create`
- "Other" manufacturer selected without a custom name

## 4. Tank

Tanks → register with station, code, capacity, product, and (for the bench)
calibration rows. Add the tank controller UID here if you have one.

## 5. POS terminal (must be assigned to a nozzle)

Payments → **+ Register POS Terminal** → select station **and the nozzle the
terminal serves**. The nozzle selector is required for the FCC sketch: without
it, `INIT 5000` returns `400 No POS terminal assigned to this nozzle`. The
terminal ID / serial is used by the OPay `sn` mapping.

## 6. FCC Controller — one per nozzle

FCC Controllers → **+ Register FCC**:

1. Select station
2. Select a dispenser **of that station**
3. Select a nozzle **of that dispenser**
4. Select the POS terminal **of that station**
5. Enter the unique `device_uid` used in the ESP32 sketch
6. Set calibration (pulses/L) and connection mode

The backend validates the whole hierarchy. Cross-station or cross-dispenser
assignments are rejected with 400/403.

## 6b. Pulse MATH (pulses per litre)

Infrastructure → **Pulse MATH (Serial + Web)** → choose the FCC and save the
pulses-per-litre value. Measure it with a known volume: `PPL = pulses ÷ litres`.
The FCC board and the separate pulser ESP32 both read this same backend value.
It can also be set from Serial with `CAL SET <ppl>` or `SET PPL <ppl>`.

## 6c. RFID card enrolment (Serial Monitor)

On board 5 type `REGISTER`, place the new card, optionally type `NAME <owner>`,
then `SAVE`. Serial prints the UID, owner, home station and `NATIONWIDE: YES`.
The home station is only where it was first registered; the card works at any
station in any state. Use `FUND 5000` then `PAY <amount>` for a bench wallet test.

## 7. Provision the device credential

After registration, call the provisioning endpoint (admin token):

```
POST /api/v1/device-ingest/provision/fcc/{fcc_id}
```

Store the returned one-time credential in the ESP32 sketch. Do not paste it in
chat or commit it.

## 8. Verify the chain

```powershell
cd backend
.\.venv\Scripts\python.exe -m tests.check_dispenser_create
.\.venv\Scripts\python.exe -m tests.check_opay_flow
```

`check_opay_flow` proves: initiate → OPay webhook → VERIFIED → device command →
completion. `check_dispenser_create` proves station → dispenser → nozzles.

For the live bench, open **Hardware JSON Monitor** before powering the boards.
Then type `HEARTBEAT` on board 1 and `SEND` on board 3. You should see both the
IN request and the backend response. The device ticker treats a controller as
online only while its heartbeat is inside the **240-second** window.

Common failures:

| Symptom | Cause |
|---|---|
| `400 No POS terminal assigned to this nozzle` | POS terminal was registered without selecting the nozzle |
| Card enrolment fails | `SET STATION` or `SET APIKEY` on board 5 is wrong |
| Ticker goes offline after 4 minutes | ESP32 heartbeat stopped or Wi-Fi dropped |
| Pulse volume is wrong | Pulse MATH `PPL` was not measured from a known volume |

## Common failures

| Symptom | Cause |
|---|---|
| "+ Register Dispenser" button missing | user lacks `dispensers:create` |
| Station dropdown empty | no station registered, or scope excludes all stations |
| `400 Dispenser code is required` | code left blank |
| `409 Dispenser code already exists` | duplicate code at the same station |
| `409 serial number already registered` | duplicate serial |
| `400 nozzle_config must be SINGLE, DOUBLE or OTHER` | old client sending bad config |
| FCC registration 400/403 | station/dispenser/nozzle hierarchy mismatch |
| No `PAYMENT_SUCCESS` command | device UID in sketch differs from registered FCC UID |
