# Linode deployment

This deployment runs the web app, FastAPI, and PostgreSQL with Docker Compose on one Ubuntu Linode. Caddy serves the web app, routes API traffic, and obtains HTTPS certificates. PostgreSQL and FastAPI ports are not published to the public internet.

This hosts the management portal. It does **not** make real payment processing or fuel dispensing live. Those require approved provider integrations, completed device firmware, vendor protocols, and on-site safety validation.

This single-server design is an initial hosted pilot, not a high-availability or safety-certified control system. It has a single point of failure; set explicit recovery objectives and do not depend on it for unattended or safety-critical fuel control.

## Requirements

- A Linode Compute instance running Ubuntu 24.04 LTS. Use at least 2 vCPU and 4 GB RAM for an initial pilot; size it from observed production load.
- A registered domain you control, with its DNS A record pointing to the Linode's public IPv4 address. Linode is the host, not the domain name; Caddy needs a public domain to provision HTTPS automatically.
- Docker Engine with the Docker Compose plugin installed.
- Firewall rules allowing inbound TCP 80/443. Restrict SSH (TCP 22) to trusted administrative IPs. Do not open PostgreSQL port 5432 or API port 8000.

## Configure and launch

1. Connect over SSH, install Docker Engine and its Compose plugin from Docker's official Ubuntu instructions, then clone this repository onto the server.
2. In `deployment/`, copy `.env.production.example` to `.env.production`. Set `APP_DOMAIN` to the exact DNS name pointing at the server.
3. Generate four independent secrets on the server and put each value in `.env.production`:

   ```sh
   openssl rand -hex 32
   ```

   Use separate values for `POSTGRES_PASSWORD`, `SECRET_KEY`, `SETUP_TOKEN`, and `INGEST_API_KEY`. Keep `.env.production` private and never commit or send it in chat. The hexadecimal database password avoids URL-encoding issues in the Compose database URL.

4. Verify DNS has propagated and the Linode firewall allows TCP 80/443. Then validate and launch:

   ```sh
   cd deployment
   chmod 600 .env.production
   docker compose --env-file .env.production -f compose.yaml config --quiet
   docker compose --env-file .env.production -f compose.yaml up -d --build
   docker compose --env-file .env.production -f compose.yaml ps
   ```

5. Confirm `https://your-domain/health` returns `{"status":"ok",...}`. Visit `https://your-domain/setup` and create the first administrator using the `SETUP_TOKEN` from the server's environment file. Do not use demo credentials. After setup, keep the setup token private and rotate it to another random value before restarting the service.
6. Confirm the administrator can log in, then create named users with least privilege. Configure SMTP only after obtaining provider settings. Verify alert delivery and recovery before relying on alerts operationally.

The application refuses to start in production with SQLite, weak secrets, wildcard CORS, or a non-HTTPS public URL. API docs are disabled in production.

## Backups and operations

Run a local PostgreSQL dump with:

```sh
cd deployment
./backup-postgres.sh
```

The dump is stored under `deployment/backups/` on the server. This is not sufficient disaster recovery by itself: copy encrypted backups to a separate off-site destination, restrict access, set retention, and regularly test restoring into a separate database. Monitor disk space, container health, logs, certificate renewal, and Linode security updates. Never test a restore by overwriting the production database.

Schedule the backup script with the server's cron after confirming the repository path; for example, `0 3 * * * /opt/visual-eyes-360/deployment/backup-postgres.sh >> /var/log/ve360-backup.log 2>&1`.

## Still required before live station operations

- Real payment-provider account, production credentials, signed callback verification, settlement/reconciliation tests, and refund/failure handling.
- Approved dispenser/controller vendor specifications and completed, reviewed firmware.
- Per-station device enrollment and network commissioning.
- Independent field validation of payment authorization, idempotency, outage behavior, emergency stops, and manufacturer safety interlocks.
- Operational approval and a documented rollback/incident plan.

## Scaling foundation (added for 80+ stations)

The stack is unchanged in principle — FastAPI + PostgreSQL — but now has four
supporting pieces so that ~1,500 field devices cannot starve payment checks:

| Service | Role |
|---|---|
| `redis` | Ingest dedupe cache, presence, rate limits, token denylist. On the internal `data` network only. |
| `mqtt` | Mosquitto broker for future device telemetry/commands. Internal only; no ports published to the host. |
| `migrate` | One-shot schema/seed job. `api` and `ingest` wait for it to complete successfully before starting. |
| `ingest` | Separate FastAPI process (`app.ingest_main:app`, port 8001) for `/api/v1/device-ingest/*`. Caddy routes device traffic here. |

Dev and tests are unaffected: `VE360_SKIP_INIT` is set only in the Docker image,
so local runs still initialise the database on import.

### Verification

```sh
cd deployment
docker compose --env-file .env.production -f compose.yaml config --quiet
docker compose --env-file .env.production -f compose.yaml up -d --build
docker compose --env-file .env.production -f compose.yaml ps
curl -fsS https://your-domain/health
```

The ingest endpoint is reachable at `https://your-domain/api/v1/device-ingest/...`
and its own health check is internal (`ingest:8001/health`).

### Database migrations

`migrate` runs `python -m app.db.init_db`, which applies the existing additive
schema reconciliation and idempotent seeding. Alembic is wired for **future**
changes:

```sh
cd deployment
docker compose --env-file .env.production -f compose.yaml run --rm migrate \
  alembic revision --autogenerate -m "describe change"
docker compose --env-file .env.production -f compose.yaml run --rm migrate \
  alembic upgrade head
```

`0001_baseline` is an intentional no-op marker: the current schema is still
owned by `init_db`. Add new revisions; never edit an applied one. After any
backend upgrade, re-run the one-shot job explicitly with
`docker compose --env-file .env.production -f compose.yaml run --rm migrate`
before restarting `api` and `ingest`.

### MQTT status and next step

The broker is intentionally locked down: `allow_anonymous false` with an empty
`passwd` file means **no client can connect yet**. This is deliberate — field
devices still use the HTTPS ingest endpoints. Before enabling MQTT:

1. Provision each device through `/api/v1/device-ingest/provision/fcc/{id}` or
   `/provision/tank/{id}` and store the returned one-time credential on the device.
2. Add the device user from the one-time credential (never printed or passed
   on the command line):

   ```sh
   cd deployment/mosquitto
   VE360_DEVICE_UID=FCC-XXXX VE360_MQTT_TOKEN=<token> python provision_device.py
   cd ..
   docker compose --env-file .env.production -f compose.yaml restart mqtt
   ```

3. For TLS, copy `mosquitto/mosquitto-tls.conf.template` into `mosquitto.conf`,
   place certificates in `mosquitto/certs/`, uncomment the cert volume and the
   `8883` port in `compose.yaml`, and apply the topic ACL in `mosquitto/acl`.
4. Only then point devices at MQTT. Do not expose 1883 publicly.

A concise operational runbook is in [`HANDOVER.md`](./HANDOVER.md).

### Operations

```sh
# Stop everything
docker compose --env-file .env.production -f compose.yaml down

# Restart one service
docker compose --env-file .env.production -f compose.yaml restart ingest

# Health
docker compose --env-file .env.production -f compose.yaml ps
```

Redis is optional for local development; if it is unreachable the ingest code
falls back to database deduplication and logs a warning.

### Worker service and telemetry partitioning

`worker` runs scheduled ARQ jobs from `app/worker/main.py`:

| Job | Cadence | Purpose |
|---|---|---|
| `offline_check` | every 15 min | Raise a deduplicated HIGH alert for FCC/tank controllers with no heartbeat |
| `notifications` | every 2 min | Deliver queued email via the existing `process_pending` |
| `discrepancies` | every 30 min | Flag CPU/pulser mismatches for review and alert |
| `token_cleanup` | 03:00 daily | Delete expired refresh/reset/login tokens |
| `partitions` | 02:00 daily | Create monthly telemetry partitions and drop those past retention |

`device_events` and `tank_readings` are range-partitioned by month on
PostgreSQL. `ensure_partitions()` creates three months ahead plus a default
partition, so an offline device replay can never fail because a partition is
missing. Retention is `TELEMETRY_RETENTION_MONTHS` (default 12) — dropping a
partition permanently deletes that month's telemetry, so set it deliberately.

`alembic` revision `0002_telemetry_partitions` applies the partition setup.
SQLite development databases are unaffected by all of this.

### Load / reconnect-storm test

Against a running stack, with a device UID and its one-time ingest token:

```sh
cd backend
VE360_URL=https://your-domain \
VE360_DEVICE_UID=FCC-XXXX \
VE360_INGEST_TOKEN=<token> \
.venv/bin/python -m tests.load_ingest --events 500 --concurrency 20 --storm
```

`--storm` replays half the events to confirm deduplication. The token is read
from the environment and is never printed.
