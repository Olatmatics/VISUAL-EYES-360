# 07 — Phased Implementation Roadmap

Each phase has an exit gate. Do not start a later phase before the prior gate is accepted.

| Phase | Name | Deliverables | Exit gate |
|---|---|---|---|
| **1** | System Architecture | This document set: architecture, block diagrams, FCC/double-nozzle/tank designs, Wi-Fi/SIM network, ESP32-S3 selection, STM32 decision, CPU+pulser model, OPay/POS plan, RFID/wallet, tank reconciliation, ERD/schema, backend/web/Android design, offline recovery, security/safety, BOM, roadmap, auth/RBAC design | Owner reviews and approves architecture; open items owning external docs assigned |
| **2** | FCC Hardware | Component selection, pin allocation table with conflict check, wiring diagram, power/protection, PCB considerations, final BOM | Pin table verified against chosen board/modem datasheets; safety review |
| **3** | Tank Controller Hardware | ESP32 selection, Wi-Fi/SIM, RS485/Modbus, probe wiring, power, cover input, calibration config, wiring diagram | Interface specs confirmed with probe vendor |
| **4** | FCC Firmware | Boot, identity, config, Wi-Fi, SIM, failover, backend comms, touch UI, transaction state machine, payment auth, POS check, dispenser driver, preset, status, pulser, reconciliation, journal, recovery, heartbeat, watchdog, faults, OTA | Bench tests pass; simulated vs real clearly labelled |
| **5** | Tank Firmware | Boot, registration, Wi-Fi/SIM, RS485, Modbus polling, probe config, calculations, calibration, cover monitoring, alarms, buffering, sync, watchdog, diagnostics | Probe and cover tests pass |
| **6** | Backend | Modules, migrations, REST/WebSocket/MQTT, device auth, commands, security, API docs | Auth/RBAC tests pass; station scoping verified |
| **7** | Web App | All management modules connected to real APIs, responsive, themes, RBAC-driven nav | Login/RBAC flow accepted |
| **8** | Android App | Same backend reused, role-based screens, secure token storage, push | No permission divergence from web |
| **9** | Payment Integration | Official OPay + transfer provider, callbacks, idempotency, refunds, reconciliation | Sandbox verification passes before live |
| **10** | Dispenser Integration | Exact Wayne model + docs, real commands identified, validated control/preset/CPU/totalizer | Real hardware integration proven; Gilbarco/Tatsuno later |
| **11** | Testing | Hardware, electrical, pulse accuracy, protocol, payment, RFID, wallet, probe, failover, offline, power, duplicate, cybersecurity, reconciliation, multi-device/station | Documented results; no mock presented as real |
| **12** | Pilot Deployment | 1 station, 1 dispenser, 1 nozzle, 1 FCC, 1 POS, 1 pulser, 1 tank, 1 controller, 1 probe | Full lifecycle proven before scaling |

## Phase 1 detailed task list (current)

Architecture docs — completed in this package:

- [x] Technical architecture + system block diagram
- [x] One-nozzle FCC architecture
- [x] Double-nozzle dispenser architecture
- [x] Tank controller architecture
- [x] Wi-Fi/SIM network architecture
- [x] ESP32-S3 peripheral recommendation
- [x] STM32 vs pulse-counting recommendation
- [x] Dispenser CPU + pulser model and reconciliation formula
- [x] OPay/POS integration architecture + documentation needs
- [x] RFID/wallet workflow
- [x] Tank monitoring/reconciliation workflow
- [x] Database ERD/schema (incl. auth tables)
- [x] Backend/web/Android architecture
- [x] Offline/power recovery architecture
- [x] Security and industrial safety architecture
- [x] Prototype BOM
- [x] Phased roadmap
- [x] Login page design
- [x] First-admin setup workflow
- [x] Secure provisioning procedure
- [x] Auth backend architecture
- [x] Admin vs Manager dashboards
- [x] Manager creation workflow
- [x] Permission management interface + 28-module matrix
- [x] Station-based restriction design
- [x] Auth/session DB schema
- [x] Auth/account API endpoints
- [x] Password/session security design
- [x] Audit logging architecture
- [x] Responsive web + future Android architecture

Remaining Phase 1 action: resolve/assign the external information items in `08-open-items.md`, then request architecture approval before Phase 2.

## Completed vertical slice (Phase 6 + 7 foundation)

The reusable backend and responsive React web shell are implemented: PostgreSQL-ready SQLAlchemy models (SQLite for local development), FastAPI auth/RBAC/station/audit APIs, and web screens for login, first-admin setup, forced password change, dashboards, stations, user management and audit. `backend/tests/test_smoke.py` verifies the full flow with 27 assertions.

## Next build step

Continue Phase 7 with dispenser, nozzle, FCC and tank master-data screens, then OPay/POS/wallet/transaction modules behind documented vendor interfaces. Harden with PostgreSQL, Redis and MQTT before firmware work and the Android APK.
