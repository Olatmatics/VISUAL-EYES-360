from fastapi.testclient import TestClient
from app.main import app

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
check("manager forbidden create station", client.post("/api/v1/stations", headers=auth(mgr_token), json={"code": "X", "name": "X"}), 403)
check("manager forbidden users", client.get("/api/v1/users", headers=auth(mgr_token)), 403)
check("manager forbidden audit", client.get("/api/v1/audit-logs", headers=auth(mgr_token)), 403)

check("audit log admin", client.get("/api/v1/audit-logs", headers=auth(admin_token)), 200)
check("refresh token", client.post("/api/v1/auth/refresh", json={"refresh_token": admin_refresh}), 200)
check("logout manager", client.post("/api/v1/auth/logout", headers=auth(mgr_token), json={"refresh_token": mgr_login["refresh_token"]}), 200)
check("token after logout", client.get("/api/v1/auth/me", headers=auth(mgr_token)), 401)
check("missing auth", client.get("/api/v1/auth/me"), 401)

print(f"\nTOTAL: {sum(results)}/{len(results)} passed")
