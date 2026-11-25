"""Check the one-button setup endpoint."""

import uuid

import httpx

BASE = "http://127.0.0.1:8000"


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=20.0) as c:
        token = c.post("/api/v1/auth/login", json={
            "user_id": "SUPERADMIN001", "password": "Admin@1234",
        }).json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        r = c.post("/api/v1/simple/setup", headers=h, json={
            "station_name": f"Simple {uuid.uuid4().hex[:5]}",
            "pump_count": 2,
            "nozzles_per_pump": "2",
            "price_per_litre": 1000,
            "tank_capacity_l": 30000,
            "controller_uids": f"CTRL{uuid.uuid4().hex[:6].upper()}\nCTRL{uuid.uuid4().hex[:6].upper()}",
            "card_uid": uuid.uuid4().hex[:8].upper(),
        })
        print(r.status_code, r.json().get("message"), r.json().get("summary"))
        print("station:", r.json().get("station"))
        print("status:", c.get("/api/v1/simple/status", headers=h).json())


if __name__ == "__main__":
    main()
