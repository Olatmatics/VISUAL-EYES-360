# 12 — Hardware ID Generator (administrator only)

This page is for non-technical installers. Log in as **SUPERIOR_ADMIN** and open
**Infrastructure → Generate Hardware IDs**. Managers cannot see or call it; the
backend enforces the same rule with `require_super_admin`.

## What it does

In one click the software creates a station, a dispenser, its nozzles, one FCC
controller per nozzle and one OPay POS terminal per nozzle. Instead of long
UUIDs such as `d26a4199-393b-40fc-b4b6-45bea91a10c2`, you get short codes:

| Item | Example | Where you use it |
|---|---|---|
| Station | `ST-6AD54C` | `SET STATION` on boards 1 and 5 |
| Dispenser / pump | `PMP-3458DA` | `SET DISPENSER` on board 1 |
| Nozzle | `NZ-832501` | `SET NOZZLE_A` / `SET NOZZLE_B` / `SET NOZZLE` |
| FCC controller | `FCC-1E9EB6` | `SET DEVICE_A` / `SET DEVICE_B` / `SET FCC` |
| POS terminal | `POS-5EBD1C` | `SET POS` and POS sn in OPay |

Every code is unique across the whole system. The long UUIDs still exist
internally, but the device endpoints accept **either** the short code or the
UUID, so old sketches keep working.

## Steps

1. Fill in the station name. The code is optional — leave it empty and the
   system creates one. Add state/LGA, address and manager details if you have
   them.
2. Set the number of nozzles, price per litre and pulses per litre.
3. Keep Wi-Fi as `cypher` / `12345678` and backend as
   `http://172.25.0.37:8000` for this bench.
4. Click **Generate IDs and ESP32 code**.
5. Click the **⧉** button on any code chip to copy it. Codes stay available
   later under **Saved IDs**.
6. For each board, either:
   - paste the whole generated code block over the `DEF_*` block at the top of
     the sketch, upload it, then send `FACTORY` and `REBOOT` in Serial Monitor;
     **or**
   - copy the commented `SET ...` lines from the block and paste them one at a
     time in Serial Monitor.

`FACTORY` clears old saved settings so the pasted defaults actually take
effect. It only clears the board's configuration — it never changes backend
data.

## Connectivity check when a board appears dead

Every network sketch (boards 1, 2, 3 and 5) now retries Wi-Fi automatically and
prints diagnostics. In Serial Monitor:

```text
NETWORK      → shows SSID, password mask, link status, IP, signal and backend URL
PING         → GET /health on the backend, prints HTTP code and JSON reply
WIFI         → force an immediate reconnect after changing the SSID/password
FACTORY      → clear saved Settings and reboot with the generated defaults
HELP         → list every available command
```

Expected boot lines:

```text
[BOOT] serial ready
[BOOT] config loaded
[WIFI] init STA
[WIFI] persistence OFF
[WIFI] Connecting to 'cypher' (backend http://172.25.0.37:8000)
[WIFI] begin called
[WIFI] auto-reconnect ON
[WIFI] Started — progress dots appear while connecting. Serial stays live.
[WIFI] Check: SSID must be 2.4 GHz, password correct, router near board.
[BOOT] Wi-Fi started (non-blocking)
[BOOT] relays safe + pulse inputs ready / sensors ready / RFID reader ready
[RELAY] outputs OFF (firmware does not energise nozzle switch)  (Board 1 only)
READY. Type HELP for commands, CONFIG to see saved IDs.
..........[WIFI] Connected IP=192.168.x.x
```

Wi-Fi connection is **non-blocking**: the board never freezes while joining, so
`HELP`, `NETWORK`, `PING` and `SET` work even before the link is up. Dots print
every half second while connecting, with a status line every 12 seconds. Once
connected, GPIO 2 goes steady ON.

### If a board freezes before `[WIFI] begin called`

Upload the tiny diagnostic sketch
`firmware/prototype/00_wifi_test/wifi_test/wifi_test.ino` **instead of** the normal
board sketch. It only joins Wi-Fi and calls `/health`.

- If the test sketch prints `[WIFI] OK IP=...` and `[PING] ... -> 200`, the
  ESP32 hardware is fine; re-upload the normal sketch (Wi-Fi now starts before
  any pins, interrupts, SPI or sensors are touched).
- If the test sketch also freezes at `WiFi.begin()`, erase the flash once
  (`python -m esptool --port COMxx erase_flash`), then upload the normal sketch
  again. Also confirm the board has a good 5 V supply, because Wi-Fi startup
  draws much more current than the relay lines.

If it stays offline, check that `cypher` is a **2.4 GHz** network, the password
is correct, and the board is near the router. On the PC, confirm the backend is
reachable at `http://172.25.0.37:8000/health`. A backend running only on
`127.0.0.1` is not reachable from an ESP32.

GPIO 2 (onboard LED) steady ON = Wi-Fi connected. GPIO 22 with an external LED
and 220 Ω resistor fast-blinks = backend send/receive activity. Board 4 has no
Wi-Fi; its GPIO 2 blinks once per pulse.

## Safety reminder

This is bench/prototype only: no intrinsic safety, no real dispenser protocol,
and payment approval does not energise the nozzle switch. The external relay
contact starts Board 4 pulses; Board 1 stops at the authorised litres.
