# VISUAL EYES 360

Industrial IoT fuel-station automation, cashless dispensing, independent pulser verification, tank monitoring, fleet management and multi-station control platform for the Nigerian downstream oil & gas market.

**Current status:** Phase 1 architecture complete. Phase 6/7 vertical slice implemented: working FastAPI backend + responsive React web app with login, first-admin setup, Superior Admin / Manager RBAC, station scoping and audit trail. Firmware, payments, dispenser drivers and the Android APK remain in later phases.

## Non-negotiable constraints

| # | Constraint |
|---|---|
| 1 | Controller WAN is **Wi-Fi + SIM cellular only**. No Ethernet, LAN cable, switch or Ethernet backup anywhere in the controller network. |
| 2 | **One FCC Controller per nozzle.** No shared controller across nozzles. |
| 3 | **One FCC tank controller per tank.** No shared controller across tanks. |
| 4 | The touchscreen stays directly on the FCC Controller; no separate main controller is used. |
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
│   ├── fcc/            # FCC Controller firmware (Phase 4)
│   ├── tank/           # FCC tank controller firmware (Phase 5)
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

To run the backend smoke suite:

```powershell
cd backend
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe -m tests.test_smoke
```

The smoke test uses an isolated throwaway SQLite database and exercises authentication, station scope, wallet funding rejection, payment sandbox safety, and device telemetry ingestion. It does not seed the development database.

## Production deployment

The initial Linode Docker Compose deployment, PostgreSQL, HTTPS reverse proxy, secret template, and backup script are documented in [`deployment/README.md`](./deployment/README.md). Production startup rejects SQLite, weak/default secrets, wildcard CORS, and non-HTTPS public URLs. This deployment hosts the management portal only; real payment processing and fuel dispensing still require completed vendor integrations, firmware, and on-site safety validation.

## Implemented in this release

- FastAPI backend with Argon2id passwords, JWT access/refresh rotation, session revocation, failed-login lockout, password reset and forced password change.
- Superior Administrator first-run setup and Manager CRUD with 28 modules / 105 granular permissions and per-station access scope.
- Station registration, station-scoped reads, audit log and dashboard counts.
- Per-device FCC/tank-controller bearer credentials, authenticated telemetry ingestion, event idempotency, and append-only tank readings.
- Wallet funding requires a verified, customer-bound funding payment; sandbox payment references remain unverified and cannot authorize fuel.
- React + TypeScript responsive web app with theme toggle, route guards, permission-driven navigation and a refresh-on-401 API client.
- Full management screens: dashboard, forecourt/dispensers/nozzles, FCC Controllers, ATG tanks, fuel transactions, pulser reconciliation, tank reconciliation, OPay/POS payments, RFID wallets, fleets, price management, alerts, reports, users and audit log.
- **App-entry splash animation** — jQuery-driven fuel nozzle gliding left→right with a three-dot loader and the AUTOMATION brand mark (`web/src/components/Splash.tsx`).
- **PWA manifest + icons** — installable to home screen / app-like standalone window.
- One-click launcher: `start.ps1` starts backend (8000) and web (5173) together.

## Verification

```powershell
# Backend API smoke test (isolated throwaway DB, safe to re-run)
cd backend
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe -m tests.test_smoke

# Frontend type-check + production build
cd ..\web
npm run build                                       # -> tsc --noEmit && vite build
```

## Still pending

- PostgreSQL production configuration, Redis token denylist, MQTT/SSE device transport.
- OPay/POS live credentials and callbacks (sandbox mock is implemented), verified bank-transfer provider.
- FCC Controller firmware, electrical/safety design, native Android APK, and all items in `docs/08-open-items.md`.

## Backend recommendation

The backend is **FastAPI (Python) + SQLAlchemy**, which is the right long-term choice for this product:

- **Why keep it:** async-friendly, typed, auto-generates the `/docs` OpenAPI reference the firmware and Android teams will consume, and SQLAlchemy lets you run SQLite today and switch to PostgreSQL for production by changing one `DATABASE_URL`.
- **Production path:** PostgreSQL 17 + Redis (JWT denylist, rate limiting) + MQTT broker for FCC Controller device transport. Same code, no rewrite.
- **When to reconsider:** only if you need heavy real-time WebSocket fan-out at massive scale — then add a Node/Go gateway in front, but keep FastAPI as the system of record for RBAC, wallet and dispensing authorization.

Do **not** move the authority for identity, RBAC, wallet balances or dispensing authorization off this backend — that is a non-negotiable constraint (README #7).

## Product tagline

**VISUAL-EYES-360** — FCC control automation software for managing reconciliation, price change, CPU communication and more.
