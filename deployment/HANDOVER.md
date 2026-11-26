# VISUAL EYES 360 — handover

## Chosen stack

FastAPI + PostgreSQL 17 as the system of record, one Python codebase deployed
as four roles: `api`, `ingest`, `worker`, and a one-shot `migrate` job.
Redis handles idempotency/presence; Mosquitto is prepared for device MQTT but
is not yet exposed. `redis`, `mqtt`, `db` and `worker` live on an internal-only
network. Alembic manages future schema changes; `0001_baseline` is a no-op
marker and `0002_telemetry_partitions` creates monthly telemetry partitions.

## What still needs a human

1. **A Linux server** with Docker Engine + Compose plugin (the current Windows
   machine has no Docker). All commands below run there, in `deployment/`.
2. **Real secrets** in `.env.production`: unique 32+ char values for
   `POSTGRES_PASSWORD`, `SECRET_KEY`, `SETUP_TOKEN`, `INGEST_API_KEY`; set
   `APP_DOMAIN` and `PUBLIC_APP_URL` to the HTTPS domain.
3. **MQTT TLS certificates** and per-device credentials before any field device
   uses MQTT. Until then devices must use the HTTPS ingest endpoints.

## First deployment

```sh
cp .env.production.example .env.production
chmod 600 .env.production
# edit APP_DOMAIN, PUBLIC_APP_URL and the four secrets
docker compose --env-file .env.production -f compose.yaml config --quiet
docker compose --env-file .env.production -f compose.yaml up -d --build
docker compose --env-file .env.production -f compose.yaml ps
```

Health: `curl -fsS https://$APP_DOMAIN/health`. First login at
`https://$APP_DOMAIN/setup` with `SETUP_TOKEN`, then rotate that token.

## Routine operations

```sh
S="docker compose --env-file .env.production -f compose.yaml"
$S ps
$S restart api
$S restart ingest
$S restart worker
$S logs --tail=100 worker
$S run --rm migrate                 # after a backend upgrade
$S down                             # stop everything
```

## Tests

On a development machine from `backend/`:

```sh
.venv/Scripts/python.exe -m tests.test_smoke          # Windows
.venv/bin/python -m tests.test_smoke                  # Linux
.venv/bin/python -m tests.test_maintenance
.venv/bin/python -m tests.load_local --events 100 --concurrency 10
```

## Changing configuration later

| Change | Where |
|---|---|
| Default/fast coding model for AI tools | LLM config files (separate task, still paused) |
| API key for device ingest | `INGEST_API_KEY` in `.env.production`; rotate via `/device-ingest/provision/...` |
| New schema change | New Alembic revision under `backend/migrations/versions/`; run `$S run --rm migrate` |
| Telemetry retention | `TELEMETRY_RETENTION_MONTHS` in `.env.production` (default 12) |
| Offline alert threshold | `DEVICE_OFFLINE_AFTER_MINUTES` (default 4 = 240 s ticker window) |
| New MQTT device | `deployment/mosquitto/provision_device.py`, then restart `mqtt` |

## Backups

Original files before modification:
`C:\Users\Administrator\ai-config-backup-20261124-145651\visual-eyes-360-20261124-150000`

Database dumps: `deployment/backup-postgres.sh` → copy encrypted dumps off-site
and test restores regularly.
