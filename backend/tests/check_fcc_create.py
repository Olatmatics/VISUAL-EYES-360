"""Diagnose FCC registration against a free nozzle."""

import uuid

import httpx

BASE = "http://127.0.0.1:8000"


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=20.0) as c:
        token = c.post("/api/v1/auth/login", json={
            "user_id": "SUPERADMIN001", "password": "Admin@1234",
        }).json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        nozzles = c.get("/api/v1/nozzles", headers=h).json()
        free = next((n for n in nozzles if not n.get("fcc")), None)
        print("free nozzle:", free and (free["id"], free.get("dispenser_code"), free.get("number")))
        if not free:
            return

        payloads = {
            "minimal": {"device_uid": f"FCC{uuid.uuid4().hex[:6].upper()}", "nozzle_id": free["id"]},
            "with_station": {"device_uid": f"FCC{uuid.uuid4().hex[:6].upper()}", "nozzle_id": free["id"],
                             "station_id": free.get("station_id")},
            "full": {"device_uid": f"FCC{uuid.uuid4().hex[:6].upper()}", "nozzle_id": free["id"],
                     "station_id": free.get("station_id"), "connection_mode": "WIFI",
                     "calibration_factor": 100, "firmware_version": "v1.0.0"},
        }
        for name, payload in payloads.items():
            r = c.post("/api/v1/fcc-devices", headers=h, json=payload)
            print(name, r.status_code, r.text[:300])


if __name__ == "__main__":
    main()
