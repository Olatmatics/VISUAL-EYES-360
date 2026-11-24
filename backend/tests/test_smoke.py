"""Smoke test for the VISUAL EYES 360 backend.

Runs against an isolated throwaway SQLite database so it is repeatable and
never touches the development database (visual_eyes_360_v2.db).
"""

import os
import secrets
import tempfile
from datetime import datetime, timedelta, timezone
from pydantic import ValidationError

# Must be set before app.db.base is imported so the engine binds to the temp DB.
_TEST_DB = os.path.join(tempfile.gettempdir(), "ve360_smoke_test.db")
if os.path.exists(_TEST_DB):
    os.remove(_TEST_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"

from fastapi.testclient import TestClient  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
results = []


def check(name, response, expected):
    ok = response.status_code == expected
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} {name}: {response.status_code} (expected {expected})")
    if not ok:
        print("   body:", response.text[:400])
    return response.json() if response.headers.get("content-type", "").startswith("application/json") else {}


def auth(token):
    return {"Authorization": f"Bearer {token}"}


check("health", client.get("/health"), 200)
setup = check("setup status", client.get("/api/v1/setup/status"), 200)
if setup.get("setup_required"):
    check(
        "first admin setup",
        client.post("/api/v1/setup/admin", json={
            "setup_token": "change-this-setup-token",
            "full_name": "System Owner",
            "user_id": "SUPERADMIN001",
            "password": "Admin@1234",
            "confirm_password": "Admin@1234",
            "phone": "+2348000000000",
            "email": "owner@example.com",
        }),
        201,
    )
check("setup locked", client.get("/api/v1/setup/status"), 200)
check("bad login", client.post("/api/v1/auth/login", json={"user_id": "SUPERADMIN001", "password": "wrong"}), 401)
admin_login = check("admin login", client.post("/api/v1/auth/login", json={"user_id": "SUPERADMIN001", "password": "Admin@1234"}), 200)
admin_token = admin_login["access_token"]
admin_refresh = admin_login["refresh_token"]
me = check("admin me", client.get("/api/v1/auth/me", headers=auth(admin_token)), 200)
print("   admin role:", me.get("role"), "permissions:", len(me.get("permissions", [])))

catalogue = check("permission catalogue", client.get("/api/v1/permissions/catalogue", headers=auth(admin_token)), 200)
print("   modules:", len(catalogue))

manager = check("create manager", client.post("/api/v1/users/managers", headers=auth(admin_token), json={
    "full_name": "Abuja Manager",
    "manager_id": "MGR001",
    "password": "Manager@1234",
    "confirm_password": "Manager@1234",
    "phone": "+2348011111111",
    "station_ids": [],
    "permissions": [
        {"module": "dashboard", "action": "view"},
        {"module": "stations", "action": "view"},
    ],
}), 201)
print("   manager id:", manager.get("user_id"), "permissions:", manager.get("permissions"))

check("list users", client.get("/api/v1/users", headers=auth(admin_token)), 200)
station = check("create station", client.post("/api/v1/stations", headers=auth(admin_token), json={
    "code": "ABJ-001", "name": "Abuja Main Station", "city": "Abuja", "phone": "+2348022222222",
}), 201)
station_id = station["id"]
dispenser = check("create dispenser for telemetry", client.post(
    "/api/v1/dispensers",
    headers=auth(admin_token),
    json={"station_id": station_id, "code": "PUMP-01", "nozzle_config": "SINGLE"},
), 201)
nozzle_id = dispenser["nozzles"][0]["id"]
fcc = check("register FCC for telemetry", client.post(
    "/api/v1/fcc-devices",
    headers=auth(admin_token),
    json={"device_uid": "FCC-SMOKE-01", "nozzle_id": nozzle_id},
), 201)
fcc_key = check("provision FCC device credential", client.post(
    f"/api/v1/device-ingest/provision/fcc/{fcc['id']}",
    headers=auth(admin_token),
), 200)["credential"]
check("FCC heartbeat rejects invalid credential", client.post(
    "/api/v1/device-ingest/fcc/FCC-SMOKE-01/heartbeat",
    headers={"Authorization": "Bearer invalid-device-key"},
    json={
        "event_id": "heartbeat-invalid-01",
        "observed_at": datetime.now(timezone.utc).isoformat(),
    },
), 401)
heartbeat = {
    "event_id": "heartbeat-smoke-001",
    "observed_at": datetime.now(timezone.utc).isoformat(),
    "signal_strength_dbm": -75,
    "firmware_version": "test-fw",
}
device_auth = {"Authorization": f"Bearer {fcc_key}"}
check("FCC heartbeat accepted", client.post(
    "/api/v1/device-ingest/fcc/FCC-SMOKE-01/heartbeat",
    headers=device_auth,
    json=heartbeat,
), 200)
duplicate_heartbeat = check("FCC heartbeat idempotent", client.post(
    "/api/v1/device-ingest/fcc/FCC-SMOKE-01/heartbeat",
    headers=device_auth,
    json=heartbeat,
), 200)
print("   duplicate heartbeat:", duplicate_heartbeat.get("duplicate"))
results.append(duplicate_heartbeat.get("duplicate") is True)
conflicting_heartbeat = dict(heartbeat, signal_strength_dbm=-60)
check("FCC event ID cannot be reused with changed payload", client.post(
    "/api/v1/device-ingest/fcc/FCC-SMOKE-01/heartbeat",
    headers=device_auth,
    json=conflicting_heartbeat,
), 409)
stale_heartbeat = dict(
    heartbeat,
    event_id="heartbeat-stale-001",
    observed_at=(datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(),
)
stale_result = check("stale FCC heartbeat does not overwrite current state", client.post(
    "/api/v1/device-ingest/fcc/FCC-SMOKE-01/heartbeat",
    headers=device_auth,
    json=stale_heartbeat,
), 200)
print("   stale heartbeat:", stale_result.get("stale"))
results.append(stale_result.get("stale") is True)
tank = check("create calibrated tank controller", client.post(
    "/api/v1/tanks",
    headers=auth(admin_token),
    json={
        "station_id": station_id,
        "code": "TANK-01",
        "capacity_l": 30000,
        "initial_volume_l": 10000,
        "product_code": "PMS",
        "calibration": [
            {"height_mm": 0, "volume_l": 0},
            {"height_mm": 1000, "volume_l": 15000},
            {"height_mm": 2000, "volume_l": 30000},
        ],
        "controller": {"device_uid": "TANK-SMOKE-01"},
    },
), 201)
pos_terminal = check("register POS terminal to station nozzle", client.post(
    "/api/v1/payments/terminals",
    headers=auth(admin_token),
    json={
        "station_id": station_id,
        "terminal_id": "POS-SMOKE-01",
        "serial_number": "POS-SERIAL-SMOKE-01",
        "provider": "OPAY",
        "nozzle_id": nozzle_id,
    },
), 201)
check("reject duplicate POS terminal ID", client.post(
    "/api/v1/payments/terminals",
    headers=auth(admin_token),
    json={
        "station_id": station_id,
        "terminal_id": "POS-SMOKE-01",
        "serial_number": "POS-SERIAL-SMOKE-02",
        "provider": "OPAY",
    },
), 409)
tank_key = check("provision tank device credential", client.post(
    f"/api/v1/device-ingest/provision/tank/{tank['controller']['id']}",
    headers=auth(admin_token),
), 200)["credential"]
tank_reading = {
    "event_id": "tank-reading-smoke-001",
    "observed_at": datetime.now(timezone.utc).isoformat(),
    "fuel_level_mm": 1000,
    "fuel_volume_l": 14999,
    "water_level_mm": 2,
    "temperature_c": 25,
    "hatch_open": False,
}
tank_device_auth = {"Authorization": f"Bearer {tank_key}"}
reading_result = check("tank reading uses server calibration", client.post(
    "/api/v1/device-ingest/tank/TANK-SMOKE-01/reading",
    headers=tank_device_auth,
    json=tank_reading,
), 200)
print("   volume source:", reading_result.get("volume_source"))
results.append(
    reading_result.get("volume_source") == "SERVER_CALIBRATION"
    and reading_result.get("fuel_volume_l") == 15000
)
check("duplicate tank reading is idempotent", client.post(
    "/api/v1/device-ingest/tank/TANK-SMOKE-01/reading",
    headers=tank_device_auth,
    json=tank_reading,
), 200)
stale_tank_reading = dict(
    tank_reading,
    event_id="tank-reading-stale-001",
    observed_at=(datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(),
    fuel_level_mm=500,
    fuel_volume_l=7000,
)
stale_tank_result = check("stale tank reading retained without replacing snapshot", client.post(
    "/api/v1/device-ingest/tank/TANK-SMOKE-01/reading",
    headers=tank_device_auth,
    json=stale_tank_reading,
), 200)
print("   stale tank reading:", stale_tank_result.get("stale"))
results.append(stale_tank_result.get("stale") is True)
current_tank = check("read tank current snapshot", client.get(
    f"/api/v1/tanks?station_id={station_id}",
    headers=auth(admin_token),
), 200)
print("   current calibrated volume:", current_tank[0].get("current_volume_l"))
results.append(current_tank[0].get("current_volume_l") == 15000)
conflicting_tank_reading = dict(tank_reading, fuel_volume_l=14000)
check("tank event ID cannot be reused with changed payload", client.post(
    "/api/v1/device-ingest/tank/TANK-SMOKE-01/reading",
    headers=tank_device_auth,
    json=conflicting_tank_reading,
), 409)
check("list stations admin", client.get("/api/v1/stations", headers=auth(admin_token)), 200)
check("dashboard admin", client.get("/api/v1/dashboard/summary", headers=auth(admin_token)), 200)

mgr_login = check("manager login", client.post("/api/v1/auth/login", json={"user_id": "MGR001", "password": "Manager@1234"}), 200)
mgr_token = mgr_login["access_token"]
check("manager me", client.get("/api/v1/auth/me", headers=auth(mgr_token)), 200)
check("manager password change required", client.get("/api/v1/stations", headers=auth(mgr_token)), 403)
check("manager change password", client.post("/api/v1/auth/password/change", headers=auth(mgr_token), json={
    "current_password": "Manager@1234", "new_password": "Manager@5678",
}), 200)
mgr_stations = check("manager station scope", client.get("/api/v1/stations", headers=auth(mgr_token)), 200)
print("   visible stations:", len(mgr_stations))
check("manager dashboard scoped", client.get("/api/v1/dashboard/summary", headers=auth(mgr_token)), 200)
check("manager forbidden create station", client.post("/api/v1/stations", headers=auth(mgr_token), json={"code": "X-001", "name": "Forbidden Station"}), 403)
check("manager forbidden users", client.get("/api/v1/users", headers=auth(mgr_token)), 403)
check("manager forbidden audit", client.get("/api/v1/audit-logs", headers=auth(mgr_token)), 403)

check("audit log admin", client.get("/api/v1/audit-logs", headers=auth(admin_token)), 200)
check("refresh token", client.post("/api/v1/auth/refresh", json={"refresh_token": admin_refresh}), 200)
check("logout manager", client.post("/api/v1/auth/logout", headers=auth(mgr_token), json={"refresh_token": mgr_login["refresh_token"]}), 200)
check("token after logout", client.get("/api/v1/auth/me", headers=auth(mgr_token)), 401)
check("missing auth", client.get("/api/v1/auth/me"), 401)
customer = check("create wallet customer", client.post("/api/v1/customers", headers=auth(admin_token), json={
    "full_name": "Verified Funding Test Customer",
    "phone": "+2348099999999",
    "category": "CORPORATE",
}), 201)
check("wallet rejects unverified funding", client.post(
    f"/api/v1/customers/wallets/{customer['id']}/fund",
    headers=auth(admin_token),
    json={"amount": 5000, "payment_reference": "NOT-A-VERIFIED-PAYMENT"},
), 400)
sandbox_payment = check("payment sandbox does not verify", client.post(
    "/api/v1/payments/simulate-opay-checkout",
    headers=auth(admin_token),
    json={"amount": 5000, "payment_method": "CARD_POS"},
), 200)
print("   sandbox dispensing authorized:", sandbox_payment.get("dispensing_authorized"))
results.append(sandbox_payment.get("dispensing_authorized") is False)
check("configure nozzle price for sandbox guard test", client.patch(
    f"/api/v1/nozzles/{nozzle_id}",
    headers=auth(admin_token),
    json={"price": 1000},
), 200)
check("unverified sandbox payment cannot dispense", client.post(
    "/api/v1/transactions/simulate-dispense",
    headers=auth(admin_token),
    json={
        "nozzle_id": nozzle_id,
        "requested_amount": 5000,
        "payment_channel": "OPAY_POS",
        "payment_ref": sandbox_payment["payment_reference"],
    },
), 400)
try:
    Settings(
        _env_file=None,
        ENVIRONMENT="production",
        SECRET_KEY="dev-only-secret-change-before-production",
        SETUP_TOKEN="change-this-setup-token",
    )
    results.append(False)
    print("FAIL production config rejects development secrets")
except ValidationError:
    results.append(True)
    print("PASS production config rejects development secrets")

production_config = {
    "SECRET_KEY": secrets.token_hex(32),
    "SETUP_TOKEN": secrets.token_hex(32),
    "INGEST_API_KEY": secrets.token_hex(32),
    "DATABASE_URL": "postgresql+psycopg://ve360:password@db:5432/ve360",
    "CORS_ORIGINS": "https://visualeyes.example",
    "PUBLIC_APP_URL": "https://visualeyes.example",
}
try:
    Settings(_env_file=None, ENVIRONMENT="production", **production_config)
    results.append(True)
    print("PASS production config accepts PostgreSQL and HTTPS settings")
except ValidationError as exc:
    results.append(False)
    print("FAIL production config accepts PostgreSQL and HTTPS settings:", exc)

try:
    Settings(_env_file=None, ENVIRONMENT="production", **{
        **production_config,
        "DATABASE_URL": "sqlite:///./production.db",
    })
    results.append(False)
    print("FAIL production config rejects SQLite")
except ValidationError:
    results.append(True)
    print("PASS production config rejects SQLite")

try:
    Settings(_env_file=None, ENVIRONMENT="production", **{
        **production_config,
        "CORS_ORIGINS": "*",
    })
    results.append(False)
    print("FAIL production config rejects wildcard CORS")
except ValidationError:
    results.append(True)
    print("PASS production config rejects wildcard CORS")

print(f"\nTOTAL: {sum(results)}/{len(results)} passed")
