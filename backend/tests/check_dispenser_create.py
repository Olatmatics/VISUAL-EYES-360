"""Diagnose dispenser creation from the frontend payload."""

import uuid

import httpx

BASE = "http://127.0.0.1:8000"


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=20.0) as c:
        token = c.post("/api/v1/auth/login", json={
            "user_id": "SUPERADMIN001", "password": "Admin@1234",
        }).json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        stations = c.get("/api/v1/stations", headers=h).json()
        print("stations:", len(stations), [s.get("code") for s in stations[:5]])
        if not stations:
            print("NO_STATIONS")
            return
        station = stations[0]

        frontend_payload = {
            "station_id": station["id"],
            "code": f"TEST{uuid.uuid4().hex[:6].upper()}",
            "manufacturer": "Wayne",
            "model": "iGEM 2-Hose",
            "protocol": "Wayne_Dart",
            "interface": "RS485_CurrentLoop",
        }
        r = c.post("/api/v1/dispensers", headers=h, json=frontend_payload)
        print("frontend-style create:", r.status_code, r.text[:500])

        full_payload = dict(frontend_payload)
        full_payload["code"] = f"TEST{uuid.uuid4().hex[:6].upper()}"
        full_payload["nozzle_config"] = "DOUBLE"
        full_payload["nozzle_count"] = 2
        full_payload["pump_type_id"] = None
        full_payload["nozzles"] = [
            {"number": 1, "name": "Nozzle 1", "price": 1150},
            {"number": 2, "name": "Nozzle 2", "price": 890},
        ]
        r2 = c.post("/api/v1/dispensers", headers=h, json=full_payload)
        print("double-nozzle create:", r2.status_code, r2.text[:500])
        if r2.status_code == 201:
            print("nozzles:", len(r2.json().get("nozzles", [])))


if __name__ == "__main__":
    main()
