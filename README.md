<<<<<<< HEAD
# VISUAL EYES 360

Industrial IoT fuel-station automation, cashless dispensing, independent pulser verification, tank monitoring, fleet management and multi-station control platform for the Nigerian downstream oil & gas market.

**Current status:** Phase 1 architecture complete. Phase 6/7 vertical slice implemented: working FastAPI backend + responsive React web app with login, first-admin setup, Superior Admin / Manager RBAC, station scoping and audit trail. Firmware, payments, dispenser drivers and the Android APK remain in later phases.

## Non-negotiable constraints

| # | Constraint |
|---|---|
| 1 | Controller WAN is **Wi-Fi + SIM cellular only**. No Ethernet, LAN cable, switch or Ethernet backup anywhere in the controller network. |
| 2 | **One ESP32-S3 FCC per nozzle.** No shared controller across nozzles. |
| 3 | **One ESP32 tank controller per tank.** No shared controller across tanks. |
| 4 | STM32 is optional, never the main controller. Touchscreen stays directly on the ESP32-S3. |
| 5 | **No verified payment → no dispensing.** Screenshots, receipts, messages and pending statuses never authorize fuel. |
| 6 | Dispenser CPU performs normal preset control/cutoff. The independent pulser is for measurement and investigation only — never a replacement. |
| 7 | Backend is the sole authority for identity, RBAC, station scope, wallet balances, payments and dispensing authorization. |
| 8 | Never bypass manufacturer safety interlocks or station emergency-shutdown systems. |
| 9 | Never auto-resume dispensing after unexpected power loss. |
| 10 | Never invent vendor protocols, APIs, pinouts or electrical ratings. Missing data is recorded in `docs/08-open-items.md`. |

## Repository layout

```
visual-eyes-360/
├── README.md
├── docs/
│   ├── 01-system-architecture.md
│   ├── 02-hardware-architecture.md
│   ├── 03-database.md
│   ├── 04-authentication-rbac.md
│   ├── 05-integrations.md
│   ├── 06-bom.md
│   ├── 07-roadmap.md
│   ├── 08-open-items.md
│   ├── api/            # generated API reference (Phase 6)
│   └── security/       # threat model, hardening (Phase 1+)
├── firmware/
│   ├── fcc/            # ESP32-S3 FCC firmware (Phase 4)
│   ├── tank/           # ESP32 tank controller firmware (Phase 5)
│   └── stm32/          # only if Phase 1 review approves it
├── hardware/           # schematics, pin tables, enclosure, BOM detail
├── backend/            # FastAPI service, migrations, MQTT bridge
├── web/                # React + TypeScript management PWA
├── tests/              # unit, HIL, bench, integration suites
└── deployment/         # compose/terraform/CI, secrets templates
```

## Document map

| Doc | Covers |
|---|---|
| `01-system-architecture.md` | Layered architecture, block diagrams, network, backend/web/Android, security, safety, offline recovery |
| `02-hardware-architecture.md` | One-nozzle FCC, double-nozzle dispenser, tank controller, ESP32-S3 peripherals, STM32 decision, CPU+pulser model, driver abstraction |
| `03-database.md` | ERD, normalized schema, auth tables, wallet atomicity, idempotency |
| `04-authentication-rbac.md` | Login, first-admin setup, Superior Admin vs Manager, 28-module permission matrix, station scoping, API endpoints |
| `05-integrations.md` | OPay/POS, bank transfer, RFID wallet, tank reconciliation, price management, alerts |
| `06-bom.md` | Prototype bill of materials and selection criteria |
| `07-roadmap.md` | Phase 1–12 with exit gates |
| `08-open-items.md` | External information required before implementation |

## Environment note (carried over from previous session)

The previous agent reported a background PostgreSQL 17 install and "creating the project structure." Verification at the start of this session found:

- Target folder empty — no files were persisted.
- `winget list --name PostgreSQL` → no installed package.
- No PostgreSQL service or `psql` on PATH.

Treat PostgreSQL as **not installed**. It is a Phase 6 dependency, not a Phase 1 blocker.

## Quick start (local development)

Backend:

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend, in a second terminal:

```powershell
cd web
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. API docs are at `http://127.0.0.1:8000/docs`.

On a brand-new database the first screen is `/setup`; use the one-time token `change-this-setup-token` to create the Superior Administrator. Change `SETUP_TOKEN` and `SECRET_KEY` in `.env` before any non-local use.

To seed demo data and verify the whole backend flow:

```powershell
cd backend
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe -m tests.test_smoke
```

Expected result: `TOTAL: 27/27 passed`. This seeds a local SQLite database with `SUPERADMIN001` / `Admin@1234` and `MGR001` (initial `Manager@1234`, forced to change to `Manager@5678` during the test). Delete `backend\visual_eyes_360.db` to start clean.

## Implemented in this release

- FastAPI backend with Argon2id passwords, JWT access/refresh rotation, session revocation, failed-login lockout, password reset and forced password change.
- Superior Administrator first-run setup and Manager CRUD with 28 modules / 105 granular permissions and per-station access scope.
- Station registration, station-scoped reads, audit log and dashboard counts.
- React + TypeScript responsive web app with theme toggle, route guards, permission-driven navigation, station/User/Audit screens and refresh-on-401 API client.

## Still pending

- PostgreSQL production configuration, Redis token denylist, MQTT/SSE device transport.
- Dispenser, nozzle, FCC, tank and tank-controller management screens beyond the dashboard counts.
- OPay/POS integration, wallet, transactions, reconciliation, pricing, alerts and reports.
- ESP32-S3 firmware, STM32 decision, electrical/safety design, Android APK, and all items in `docs/08-open-items.md`.
=======
# VISUAL-EYES-360
FCC CONTROL AUTOMATION SOFTWARE FOR MANAGING RECONCILIATION, PRICE CHANGE, CPU COMMUNICATION AND ETC.....
>>>>>>> 27ebb3852ae2623f58dd0950fbe533552b7b8a1c
