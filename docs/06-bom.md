# 06 — Prototype Bill of Materials

Selection principle: choose by **verified datasheet fit**, not by assumption. Values below are selection criteria and example families, not final ratings or pin assignments. Confirm each against the actual datasheet before ordering (see `08-open-items.md`).

## A. FCC prototype (one nozzle) — Phase 2

| # | Item | Selection criteria / example family | Qty | Verify |
|---|---|---|---|---|
| 1 | Main MCU module | ESP32-S3 module with PSRAM (ESP32-S3-WROOM class) on carrier exposing needed GPIO/USB | 1 | Flash/PSRAM size, GPIO count, UART/RMT availability |
| 2 | Touchscreen | SPI LCD + capacitive/resistive touch controller, size suitable for HMI | 1 | Interface, voltage, driver support, CS/IRQ pins |
| 3 | Cellular modem | LTE Cat-1/Cat-M module supporting Nigerian operator bands, UART AT interface, SIM holder | 1 | Bands for MTN/Airtel/Glo/9mobile, APN, AT command set, peak current |
| 4 | Wi-Fi | On-module ESP32-S3 2.4 GHz | — | Regulatory/wi-fi mode support |
| 5 | SIM holder + ESD | SIM socket with protection | 1 | SIM form factor (mini/micro/nano) |
| 6 | Dispenser interface | Isolated RS232 or RS485 transceiver module per dispenser docs | 1 | Exact interface from Wayne documentation |
| 7 | Pulser input | Isolated/digital input with debounce and protection | 1 | Pulse voltage/frequency from actual pulser |
| 8 | RFID reader | NFC/HF reader supporting secure card auth (e.g., DESFire-class) | 1 | Card technology and auth method |
| 9 | Local storage | Internal flash journal partition; microSD module-ready | 1 | Endurance, wear levelling |
| 10 | Power | Industrial PSU, regulation, surge/transient protection, fuse | 1 | Input range, modem TX burst current, isolation |
| 11 | Protection | TVS/ESD, opto/isolation, surge on external lines | as needed | Hazardous-area installation design |
| 12 | Enclosure | Suitable industrial enclosure for the installation zone | 1 | Certification requirements |
| 13 | Debug | USB/JTAG + log UART header | 1 | Board support |
| 14 | RTC / brownout / watchdog | RTC source, brownout detection (MCU feature + supervisor) | 1 | Time recovery accuracy |

## B. Tank controller prototype (one tank) — Phase 3

| # | Item | Selection criteria / example family | Qty | Verify |
|---|---|---|---|---|
| 1 | MCU | ESP32 (Wi-Fi) module/board with UART for modem + RS485 | 1 | UART count, GPIO |
| 2 | Cellular modem | Same selection process as FCC | 1 | Bands/APN/power |
| 3 | RS485 interface | Isolated/protected RS485 transceiver | 1 | Probe electrical spec |
| 4 | ATG probe | Supported Modbus RTU probe, address 01–10 | 1–n | Register map, baud, wiring |
| 5 | Cover sensor | Industrial limit/access switch with protected input | 1 | Output type, hazardous-area suitability |
| 6 | Local buffer | Flash/FRAM ring buffer | 1 | Retention |
| 7 | Power/protection | Regulated PSU, surge, isolation, grounding | 1 | Field wiring spec |
| 8 | Enclosure | Industrial/certified enclosure | 1 | Installation zone |

## C. Shared / bench

- Bench power supply, isolated USB-UART adapter, logic analyser (pulse validation), RS232/RS485 adapters, SIM cards with data plans, test dispenser simulator (clearly labelled simulation), test ATG probe or Modbus simulator.
- Tools: ESP-IDF, Python/FastAPI, PostgreSQL client, MQTT client, Git.

## D. Explicitly NOT included

- Ethernet controllers, switches, cables or ports — prohibited by requirement.
- STM32 in the first prototype (deferred pending pulse-accuracy evidence).
- Intrinsically-safe certification claims for dev boards — not permitted.

> Cost figures are intentionally omitted until specific part numbers and supplier quotes are confirmed.
