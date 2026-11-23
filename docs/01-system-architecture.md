# 01 — System Architecture

## 1. Architecture summary

VISUAL EYES 360 is a layered, multi-station system:

1. **Field layer** — dispensers and their CPUs, independent pulsers, ATG probes, tank cover sensors, RFID readers, OPay POS terminals.
2. **Edge controller layer** — one ESP32-S3 FCC per nozzle; one ESP32 tank controller per tank. Each controller owns its local journal and its Wi-Fi/SIM uplink.
3. **Transport layer** — MQTT over TLS for device telemetry/commands, HTTPS REST for management clients, WebSocket for live dashboard push.
4. **Backend layer** — FastAPI services with PostgreSQL, Redis (sessions/rate limits/idempotency), and an MQTT broker. The backend is the only authority for payments, wallets, permissions and authorization.
5. **Client layer** — responsive React web app (also the future Android wrapper/Capacitor target), and a special-customer mobile experience using the same APIs.

Design rules applied throughout: database-driven multi-station model, modular drivers, no hardcoded station/pump/nozzle, no secrets in firmware or APK, and explicit separation of simulation from real integration.

## 2. Complete system block diagram

```mermaid
flowchart TB
  subgraph FIELD["FIELD / HAZARDOUS AREA — certified interfaces only"]
    DISP["Fuel dispenser<br/>Wayne (prototype)<br/>CPU + preset control<br/>RS232 / RS485 (documented)"]
    PULSE["Independent pulser<br/>per nozzle<br/>pulse output"]
    PROBE["ATG probe<br/>RS485 / Modbus RTU<br/>(address 01-10)"]
    COVER["Tank cover / access<br/>limit switch"]
    RFID["RFID reader<br/>MIFARE DESFire-class<br/>secure auth"]
    POS["OPay POS terminal<br/>assigned per nozzle"]
  end

  subgraph EDGE["STATION EDGE — one controller per nozzle / per tank"]
    FCC1["FCC-01 · ESP32-S3<br/>touchscreen · pulser input<br/>dispenser driver · RFID<br/>journal · Wi-Fi + SIM"]
    FCC2["FCC-02 · ESP32-S3<br/>(independent 2nd nozzle)"]
    TKC1["TKC-01 · ESP32<br/>RS485 Modbus master<br/>cover input · local buffer<br/>Wi-Fi + SIM"]
  end

  subgraph NET["TRANSPORT — Wi-Fi / SIM only"]
    WIFI["Wi-Fi AP<br/>(primary)"]
    CELL["SIM / cellular modem<br/>(backup)<br/>APN: configurable"]
    FAILOVER["Connectivity manager<br/>priority policy · heartbeat<br/>reconnect · buffer drain"]
  end

  subgraph CLOUD["BACKEND / CLOUD"]
    LB["TLS ingress / API gateway<br/>rate limit · WAF"]
    API["FastAPI services<br/>auth · RBAC · stations · devices<br/>payments · wallet · transactions<br/>reconciliation · alerts · reports"]
    MQTT["MQTT broker (TLS)<br/>device auth · ACL topics"]
    WS["WebSocket gateway<br/>live dashboards"]
    PG[("PostgreSQL<br/>normalized schema<br/>audit · journal mirror")]
    REDIS[("Redis<br/>sessions · idempotency<br/>rate limits · presence")]
    WORKER["Workers / schedulers<br/>reconciliation · alerts<br/>sync · reports"]
  end

  subgraph CLIENTS["CLIENTS"]
    WEB["React + TypeScript web<br/>responsive / PWA"]
    MOB["Future Android APK<br/>same backend + DB"]
    CUST["Special-customer app<br/>wallet + purchase requests"]
  end

  subgraph EXT["EXTERNAL PROVIDERS"]
    OPAY["OPay merchant API / POS<br/>(docs required)"]
    BANK["Approved transfer provider<br/>virtual account / callback"]
    NOTIFY["Email / SMS / push<br/>(approved providers)"]
  end

  DISP <-->|"documented commands"| FCC1
  PULSE --> FCC1
  FCC1 <--> RFID
  FCC1 <-->|"assigned POS only"| POS
  FCC1 <--> TKC1
  FCC2 -. "independent, no cross-auth" .- DISP
  PROBE <-->|"Modbus RTU"| TKC1
  COVER --> TKC1

  FCC1 --> WIFI
  FCC2 --> WIFI
  TKC1 --> WIFI
  FCC1 --> CELL
  FCC2 --> CELL
  TKC1 --> CELL
  WIFI --> FAILOVER
  CELL --> FAILOVER
  FAILOVER <-->|"MQTT over TLS"| MQTT
  FAILOVER <-->|"HTTPS"| LB

  LB --> API
  MQTT --> API
  API --> PG
  API --> REDIS
  API --> WS
  WORKER --> PG
  WORKER --> API
  WS --> WEB
  LB --> WEB
  LB --> MOB
  LB --> CUST
  API <--> OPAY
  API <--> BANK
  API --> NOTIFY
```

## 3. Trust boundaries

| Boundary | Rule |
|---|---|
| Field → FCC | Manufacturer-approved interface only. Safety interlocks untouched. Pulse input is isolated/protected. |
| FCC → Backend | Device certificate/token, mutual TLS where broker supports it, signed commands, replay protection. |
| Client → Backend | JWT access + rotating refresh token, RBAC + station scope enforced server-side on every request. |
| Backend → Provider | Provider secrets live only in backend secret store; callbacks verified (signature + amount + reference + merchant). |
| Manager → System | Permissions delivered by backend; UI hides controls but backend rejects unauthorized calls independently. |

## 4. Wi-Fi and SIM-only communication architecture

```mermaid
flowchart LR
  A["Controller boot"] --> B{"Wi-Fi configured<br/>and available?"}
  B -->|yes| C["Connect Wi-Fi<br/>DHCP · time sync"]
  B -->|no| D["Init SIM modem<br/>APN · registration · PDP"]
  C --> E{"Heartbeat to<br/>backend OK?"}
  E -->|yes| F["Active link = Wi-Fi"]
  E -->|no| D
  D --> G{"Cellular data<br/>established?"}
  G -->|yes| H["Active link = Cellular"]
  G -->|no| I["Offline mode<br/>journal locally · alert queued"]
  F --> J["Policy: WiFi-preferred<br/>or cellular-preferred<br/>(admin configurable)"]
  H --> J
  J --> K["Publish heartbeat + telemetry<br/>drain append-only journal in order"]
  I --> L["Retry with backoff<br/>no record loss · no auto-dispense"]
  L --> B
```

Requirements implemented by this layer:

- Wi-Fi provisioning, reconnection and signal reporting.
- Modem init, SIM presence, network registration, APN/PDP activation, signal strength (RSRP/CSQ where supported).
- Configurable priority policy (default Wi-Fi preferred, SIM backup).
- Heartbeat, timeouts, backoff, link-quality reporting to backend.
- Offline journaling and ordered replay after reconnect, exactly-once semantics via transaction/sync IDs.
- **No Ethernet path exists** in the design — not primary, not failover.

> Modem model, Nigerian band support, APN values and AT command set are unresolved — see `08-open-items.md`.

## 5. Backend architecture (Phase 6)

```
backend/
├── app/
│   ├── main.py                 # app factory, middleware
│   ├── core/                   # config, security, hashing, errors
│   ├── db/                     # session, base, migrations
│   ├── modules/
│   │   ├── auth/               # login, tokens, first-admin setup
│   │   ├── users/              # admin/manager accounts, permissions
│   │   ├── stations/           # stations, states/LGAs
│   │   ├── devices/            # FCC/tank registration, provisioning
│   │   ├── dispensers/         # pumps, nozzles, drivers
│   │   ├── payments/           # OPay, transfer, callbacks, idempotency
│   │   ├── rfid/ wallets/ customers/ fleets/
│   │   ├── transactions/       # sessions, CPU+pulser records
│   │   ├── reconciliation/     # fuel + tank engines
│   │   ├── prices/ alerts/ reports/ audit/
│   │   └── iot/                # MQTT client, commands, telemetry ingest
│   ├── schemas/                # Pydantic request/response models
│   └── ws/                     # WebSocket channels
├── migrations/                 # Alembic
└── tests/
```

Key patterns: service layer + repository layer, Pydantic validation on all inputs, dependency-injected permission and station-scope guards, outbox pattern for device commands, and idempotency keys on every externally-triggered mutation.

## 6. Web and Android architecture (Phases 7–8)

- **Web:** React + TypeScript, Vite, component library, React Query for server state, WebSocket for live views, responsive layout with light/dark themes. Route guards consume backend-provided permissions; direct URL access to an unauthorized module renders an access-denied state and the backend still rejects the API calls.
- **Android:** same REST/WebSocket APIs and same database. Preferred path is a thin native/Capacitor shell around the responsive app, with native plugins for secure token storage and push notifications. No second business database, no hardcoded credentials, no role escalation on mobile.
- **Customer app:** dedicated role (`SPECIAL_CUSTOMER`) with wallet, purchase requests, card status and notifications; it never authorizes dispensing directly.

## 7. Security architecture (Section 20)

- Argon2id password hashing; unique User ID login; generic failure message.
- JWT access tokens (short TTL) + rotating refresh tokens with revocation on logout/deactivation.
- Login throttling/lockout, rate limiting at gateway and app layer.
- RBAC with per-module actions plus per-station row scope enforced in SQL queries.
- Device identity: per-device credentials/certificates, provisioning approval, revocation list; no shared permanent password.
- TLS everywhere; MQTT authenticated with topic ACLs; signed commands with expiry and nonce; replay protection.
- Idempotency keys for payments, authorizations, wallet reservations and journal sync.
- Secrets in backend secret manager only; never in ESP32 firmware or APK.
- Tamper-evident audit log; managers cannot delete or edit it.
- Signed firmware updates where the chosen platform supports them.

## 8. Industrial safety architecture (Section 21)

- Field wiring uses certified interfaces, barriers, surge/transient protection, isolation, grounding/bonding and approved enclosures.
- ESP32/STM32 dev boards are **not** intrinsically safe — no uncertified board in a classified area.
- No bypass of dispenser safety interlocks or station ESD.
- Preset control goes through the manufacturer-approved enable/control path.
- Any independent shutdown is a separate, safety-rated, qualified-engineer design.
- Fail-safe defaults: on comms fault, sensor fault or power loss, no new authorization is issued.

## 9. Offline and power-failure recovery (Section 14)

```mermaid
stateDiagram-v2
  [*] --> Boot
  Boot --> BrownoutCheck
  BrownoutCheck --> JournalScan: power event logged
  JournalScan --> IdentifyUnfinished: find open session
  IdentifyUnfinished --> QueryDispenser: read status/totalizer (if supported)
  QueryDispenser --> CompareReadings: CPU vs pulser
  CompareReadings --> Classify: completed / interrupted / investigate
  Classify --> StoreRecoveryResult
  StoreRecoveryResult --> SyncWhenOnline
  SyncWhenOnline --> [*]
  Classify --> NoAutoResume: never re-enable pump automatically
  NoAutoResume --> AwaitVerifiedAuth: new tx needs fresh verified payment
```

Guarantees: append-only journal, atomic record writes with integrity checks, RTC/time recovery, brownout detection, watchdog, duplicate-sync protection, and no authorization without fresh verified payment. Ambiguous outcomes are marked for investigation, never silently "successful."
