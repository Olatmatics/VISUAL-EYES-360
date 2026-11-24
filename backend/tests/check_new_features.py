"""Live verification for manager roles, exports and alert workflow endpoints."""

import time
import uuid

import httpx

BASE = "http://127.0.0.1:8000"


def wait_health(client):
    for _ in range(50):
        try:
            if client.get("/health").status_code == 200:
                return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("backend not healthy")


def main():
    with httpx.Client(base_url=BASE, timeout=20.0) as c:
        wait_health(c)
        token = c.post("/api/v1/auth/login", json={
            "user_id": "SUPERADMIN001", "password": "Admin@1234",
        }).json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        roles = c.get("/api/v1/users/roles", headers=h)
        print("roles:", roles.status_code, len(roles.json()))

        states = c.get("/api/v1/geo/states", headers=h).json()
        state_id = states[0]["id"]
        print("states:", len(states))

        suffix = uuid.uuid4().hex[:6]
        created = c.post("/api/v1/users/managers", headers=h, json={
            "manager_id": f"ROLETEST{suffix}",
            "full_name": "Role Test Manager",
            "password": "RoleTest@1234",
            "confirm_password": "RoleTest@1234",
            "role_code": "STATE_MANAGER",
            "scope_state_id": state_id,
            "department": "Operations",
            "position": "State Manager",
            "staff_id": f"STF-{suffix}",
            "all_stations": False,
        })
        print("manager create:", created.status_code,
              created.json().get("role_code"), created.json().get("scope_state_id") == state_id)

        suffix2 = uuid.uuid4().hex[:6]
        empty_scope = c.post("/api/v1/users/managers", headers=h, json={
            "manager_id": f"EMPTY{suffix2}", "full_name": "No Scope Manager",
            "password": "RoleTest@1234", "confirm_password": "RoleTest@1234",
            "role_code": "MANAGER", "scope_state_id": None, "scope_lga_id": None,
            "department": "", "position": "", "staff_id": "",
        })
        print("manager create (no scope):", empty_scope.status_code, empty_scope.text[:200])

        datasets = c.get("/api/v1/reports/export/datasets", headers=h)
        print("export datasets:", datasets.status_code, len(datasets.json()))

        csv = c.get("/api/v1/reports/export/stations?fmt=csv", headers=h)
        print("csv export:", csv.status_code, csv.headers.get("content-type"), len(csv.content))

        xlsx = c.get("/api/v1/reports/export/stations?fmt=xlsx", headers=h)
        print("xlsx export:", xlsx.status_code, xlsx.headers.get("content-type"), len(xlsx.content))

        notes = c.get("/api/v1/alerts/notifications/list", headers=h)
        print("notification list:", notes.status_code)
        dispatch = c.post("/api/v1/alerts/notifications/dispatch", headers=h)
        print("notification dispatch:", dispatch.status_code, dispatch.json())

        alerts = c.get("/api/v1/alerts?unresolved_only=true&limit=1", headers=h).json()
        if alerts:
            aid = alerts[0]["id"]
            ack = c.post(f"/api/v1/alerts/{aid}/acknowledge", headers=h, json={})
            print("alert acknowledge:", ack.status_code, ack.json().get("status"))
        else:
            print("alert acknowledge: skipped (no alerts)")

        settings = c.get("/api/v1/system-settings", headers=h)
        print("system settings:", settings.status_code, settings.json())

        analytics = c.get("/api/v1/dashboard/analytics?days=30", headers=h)
        print("dashboard analytics:", analytics.status_code,
              sorted(analytics.json().keys())[:6])

        tanks = c.get("/api/v1/tanks?limit=1", headers=h).json()
        if tanks:
            run = c.post("/api/v1/reconciliation/tanks/run", headers=h,
                         json={"tank_id": tanks[0]["id"], "period_days": 30})
            print("tank reconciliation:", run.status_code,
                  run.json().get("status"), run.json().get("variance_l"))
        nozzles = c.get("/api/v1/nozzles?limit=1", headers=h).json()
        if nozzles:
            run = c.post("/api/v1/reconciliation/pumps/run", headers=h,
                         json={"nozzle_id": nozzles[0]["id"], "period_days": 30})
            print("pump reconciliation:", run.status_code,
                  run.json().get("status"), run.json().get("variance_l"))

        checkout = c.post("/api/v1/payments/simulate-opay-checkout", headers=h,
                          json={"amount": 1000, "payment_method": "CARD_POS"})
        if checkout.status_code == 200:
            verified = c.post("/api/v1/payments/sandbox/verify", headers=h,
                              json={"payment_reference": checkout.json()["payment_reference"]})
            print("sandbox verify:", verified.status_code, verified.json().get("status"))


if __name__ == "__main__":
    main()
