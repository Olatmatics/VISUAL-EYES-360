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
