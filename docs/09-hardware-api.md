# 09 — Hardware API contract (firmware team)

This document is the authoritative contract for devices talking to VISUAL EYES 360.
Do not invent fields or endpoints. All examples use JSON with `Content-Type: application/json`.

## 1. Provisioning (one time, administrator only)

A controller cannot send data until it has a credential. An administrator calls:

```
POST /api/v1/device-ingest/provision/fcc/{fcc_id}
POST /api/v1/device-ingest/provision/tank/{controller_id}
Authorization: Bearer <admin access token>
```

Response:

```json
{
  "device_uid": "FCC-ABJ-001-N1",
  "authorization_scheme": "Bearer",
  "credential": "<shown once>",
  "warning": "Shown once. Store securely on the device; rotate to revoke it."
}
```

Store the credential in secure device storage. The server keeps only a SHA-256 hash.
Re-provisioning rotates the credential and immediately invalidates the old one.

## 2. FCC Controller heartbeat

```
POST /api/v1/device-ingest/fcc/{device_uid}/heartbeat
Authorization: Bearer <device credential>
```

```json
{
  "event_id": "fcc-20261124-000001",
  "observed_at": "2026-11-24T14:05:00Z",
  "firmware_version": "v1.0.4-fcc",
  "signal_strength_dbm": -72,
  "temperature_c": 41.5,
  "power_status": "MAINS_OK",
  "hardware_fault": null,
  "communication_errors": 0
}
```

Constraints:
- `event_id`: 8–96 characters, unique per device. Replay is safe.
- `observed_at`: ISO-8601 **with timezone**. Future skew ≤ 900 s; replay older than
  `DUPLICATE_WINDOW_MINUTES` (default 1440) is rejected (400).
- `signal_strength_dbm`: -150…0. `temperature_c`: -40…125.
- Unknown fields are rejected (`extra="forbid"`).

Response:

```json
{"accepted": true, "duplicate": false, "stale": false, "device_uid": "FCC-ABJ-001-N1"}
```

`duplicate: true` means the event was already stored — treat as success.
`stale: true` means the reading was older than the last heartbeat and did not
overwrite current state.

## 3. Tank reading

```
POST /api/v1/device-ingest/tank/{device_uid}/reading
Authorization: Bearer <device credential>
```

```json
{
  "event_id": "tank-20261124-000001",
  "observed_at": "2026-11-24T14:05:00Z",
  "fuel_level_mm": 1820.5,
  "fuel_volume_l": 15000.0,
  "water_level_mm": 0,
  "temperature_c": 29.4,
  "hatch_open": false
}
```

Behaviour:
- If the tank has a calibration (strapping) chart, the server **overrides** the
  device volume with chart-interpolated volume and reports `volume_source: SERVER_CALIBRATION`.
  Otherwise `DEVICE_REPORTED` is used.
- A level outside the configured calibration chart is rejected (400).
- Water ≥ 25 mm raises a HIGH alert; ≥ 50 mm raises CRITICAL.
- `hatch_open: true` raises a CRITICAL tank-security alert.

Response adds `tank_id`, `fuel_volume_l` and `volume_source`.

## 4. Errors

| Status | Meaning | Device action |
|---|---|---|
| 400 | Invalid payload, timestamp outside window, level outside chart | Fix payload; do not retry blindly |
| 401 | Missing/invalid device credential | Re-provision; do not retry with old key |
| 403 | Device not ACTIVE | Stop sending; contact administrator |
| 404 | Unknown device_uid | Stop sending; re-register |
| 409 | `event_id` reused with a different payload | Use a new event ID for changed data |

## 5. Offline buffering

Devices must journal events locally with a monotonic `event_id` and forward them
in order on reconnect. The server deduplicates by `(device_uid, event_id)`;
replays within the duplicate window are acknowledged with `duplicate: true`.

## 6. MQTT (prepared, not yet enabled for field devices)

Broker: internal only. Anonymous access is disabled and no users are provisioned.
Topic layout: `ve360/stations/{station_id}/devices/{device_uid}/...`.

Field devices must continue using the HTTPS endpoints above until TLS on 8883,
per-device credentials and ACLs are commissioned. Do not send telemetry to
MQTT yet.

## 7. Not yet supported

Dispenser CPU/pulser transaction ingestion, tamper-switch events, temperature
switch events and firmware update status have **no ingestion endpoint yet**.
Do not send them as heartbeat fields — unknown fields are rejected.

---

## 8. Bench prototype HTTP JSON transport (not the production contract)

The bench sketches in `firmware/prototype/` use plain HTTP JSON so every board
can be driven from Serial Monitor. These endpoints are **prototype-only**; do not
use them in a field deployment. The web page **Hardware JSON Monitor** records
the exact request and response for each call.

All request bodies use `Content-Type: application/json`. RFID endpoints also
accept the bench `X-API-Key` header (`INGEST_API_KEY`).

| Method | Endpoint | Direction | Purpose |
|---|---|---|---|
| POST | `/api/v1/fcc/prototype/heartbeat` | IN | FCC board → backend ticker heartbeat |
| GET | `/api/v1/fcc/calibration?device_uid=…` | OUT | Pulser/FCC board → backend reads pulses/L |
| PATCH | `/api/v1/fcc/calibration` | IN | Web MATH or Serial writes pulses/L |
| POST | `/api/v1/fcc/transaction/initiate` | IN | Starts POS/bank payment through OPay |
| GET | `/api/v1/fcc/commands/poll?device_uid=…` | OUT | Backend → FCC queued commands |
| POST | `/api/v1/fcc/commands/ack` | IN | FCC confirms command received |
| POST | `/api/v1/fcc/transaction/complete` | IN | Final litres, pulses and discrepancy |
| POST | `/api/v1/device/prototype/telemetry` | IN | Tank or separate pulser readings |
| POST | `/api/v1/rfid/prototype/register` | IN | Manager enrols card UID for a station |
| POST | `/api/v1/rfid/scan` | IN | Recognise card / show balance |
| POST | `/api/v1/rfid/fund` | IN | Bench wallet funding |
| POST | `/api/v1/rfid/authorize` | IN + OUT | Debit wallet and queue `PAYMENT_SUCCESS` |
| POST | `/api/v1/opay/webhook` | IN | OPay → backend signed payment result |
| GET | `/api/v1/hardware/exchanges` | OUT | Web reads the JSON log (`hardware:view`) |

### Prototype heartbeat

```json
POST /api/v1/fcc/prototype/heartbeat
{"device_uid":"fcc-matics-001","firmware_version":"ve360-fcc-bench-1.1","signal_strength_dbm":-55}
```

```json
{"accepted":true,"device_uid":"fcc-matics-001","is_online":true,"last_seen":"2026-11-26T07:23:01.204706"}
```

A device is shown online only if `last_heartbeat` is inside the 240-second
window (`DEVICE_OFFLINE_AFTER_MINUTES=4`). A stale device is also marked offline
by the worker's `check_offline_devices` job.

### Pulse calibration and telemetry

```json
PATCH /api/v1/fcc/calibration
{"device_uid":"fcc-matics-001","pulses_per_litre":100.0}
```

```json
{"device_uid":"fcc-matics-001","pulses_per_litre":100.0,"formula":"litres = raw_pulse_count / pulses_per_litre"}
```

```json
POST /api/v1/device/prototype/telemetry
{
  "device_uid":"PULSE-DEV-01",
  "kind":"PULSE",
  "event_id":"PULSE0007",
  "fcc_device_uid":"fcc-matics-001",
  "readings":{
    "raw_pulse_count":1235,
    "pulses_per_litre":100.0,
    "pulser_volume_l":12.35,
    "pulses_per_second":10.0,
    "litres_per_second":0.1
  }
}
```

```json
{"accepted":true,"duplicate":false,"device_uid":"PULSE-DEV-01"}
```

### RFID registration and wallet authorization

```json
POST /api/v1/rfid/prototype/register
{"uid":"A1B2C3D4","owner":"Alu Ada","station_id":"923a0b56-6e8f-4dc4-89f2-1f0dd8a93628"}
```

```json
{"registered":true,"uid":"A1B2C3D4","owner":"Alu Ada","home_station_id":"923a0b56-6e8f-4dc4-89f2-1f0dd8a93628","home_station":"matics oil and gas","balance_ngn":0.0,"nationwide":true,"message":"NEW CARD SAVED"}
```

`home_station_id` is only the registration station. The card is valid nationwide.
For stations and nozzles generated by the admin ID generator, either the short
code (for example `NZ-832501`) or the UUID is accepted in every device-facing
`*_id` field.

```json
POST /api/v1/rfid/authorize
{"uid":"A1B2C3D4","amount_ngn":5000,"nozzle_id":"d26a4199-393b-40fc-b4b6-45bea91a10c2"}
```

```json
{"reference":"RFID-4936685E68","status":"APPROVED","amount_ngn":5000.0,"balance_ngn":0.0,"authorized_liters":4.35,"device_uid":"fcc-matics-001"}
```

The OUT log row for the queued command:

```json
{
  "type":"PAYMENT_SUCCESS",
  "payload":{"reference":"RFID-4936685E68","status":"APPROVED","amount_ngn":5000.0,"payment_method":"RFID_WALLET","authorized_liters":4.35}
}
```

`GET /api/v1/fcc/commands/poll?device_uid=fcc-matics-001` returns that command.
The FCC acknowledges it with `POST /api/v1/fcc/commands/ack` using the command `id`.

Full step-by-step instructions, including POS explanation and wiring, are in
`docs/10-prototype-hardware-guide.md`.
