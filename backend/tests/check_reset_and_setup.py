"""Verify reset wipes operational data and setup auto-names pumps/tanks/controllers."""

import uuid

import httpx

BASE = "http://127.0.0.1:8000"


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=20.0) as c:
        token = c.post("/api/v1/auth/login", json={
            "user_id": "SUPERADMIN001", "password": "Admin@1234",
        }).json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        before = c.get("/api/v1/simple/status", headers=h).json()
        print("before:", before)

        r = c.post("/api/v1/simple/reset", headers=h)
        print("reset:", r.status_code, r.json())
        token = c.post("/api/v1/auth/login", json={
            "user_id": "SUPERADMIN001", "password": "Admin@1234",
        }).json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        after = c.get("/api/v1/simple/status", headers=h).json()
        print("after:", after)

        s = c.post("/api/v1/simple/setup", headers=h, json={
            "station_name": f"Fresh {uuid.uuid4().hex[:5]}",
            "pump_count": 3,
            "nozzles_per_pump": "2",
            "price_per_litre": 1000,
            "tank_capacity_l": 30000,
            "controller_uids": "CTRL1\nCTRL2\nCTRL3",
            "card_uid": "1234ABCD",
        })
        print("setup:", s.status_code, s.json().get("summary"))
        for p in s.json().get("pumps", []):
            print("  pump:", p.get("name"), p.get("code"), "nozzles:", len(p.get("nozzles", [])))
        for ctrl in s.json().get("controllers", []):
            print("  controller:", ctrl.get("uid"), ctrl.get("pump"), "nozzle", ctrl.get("nozzle"))


if __name__ == "__main__":
    main()
