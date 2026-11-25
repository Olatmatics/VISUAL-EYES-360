"""End-to-end check for minimal setup and RFID wallet dispensing."""

import uuid

import httpx

BASE = "http://127.0.0.1:8000"


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=20.0) as c:
        token = c.post("/api/v1/auth/login", json={
            "user_id": "SUPERADMIN001", "password": "Admin@1234",
        }).json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        key = {"X-API-Key": "dev-ingest-key-change-me"}

        station = c.post("/api/v1/quick/station", headers=h,
                         json={"name": f"Quick {uuid.uuid4().hex[:5]}"}).json()
        print("station:", station["code"])

        pump = c.post("/api/v1/quick/pump", headers=h, json={
            "station_id": station["id"], "nozzle_config": "DOUBLE", "price": 1000,
        }).json()
        print("pump:", pump["code"], "nozzles:", len(pump["nozzles"]))

        tank = c.post("/api/v1/quick/tank", headers=h, json={
            "station_id": station["id"], "capacity_l": 30000,
        }).json()
        print("tank:", tank["code"])

        uid = f"FCC{uuid.uuid4().hex[:8].upper()}"
        fcc = c.post("/api/v1/quick/fcc", headers=h, json={
            "device_uid": uid, "station_id": station["id"],
        })
        print("fcc:", fcc.status_code, fcc.json().get("device_uid"))

        card_uid = uuid.uuid4().hex[:8].upper()
        scanned = c.post("/api/v1/rfid/scan", headers=key, json={"uid": card_uid, "name": "Test Driver"})
        print("scan:", scanned.status_code, scanned.json().get("message"))

        funded = c.post("/api/v1/rfid/fund", headers=key, json={"uid": card_uid, "amount_ngn": 10000})
        print("fund:", funded.status_code, funded.json().get("balance_ngn"))

        authorized = c.post("/api/v1/rfid/authorize", headers=key, json={
            "uid": card_uid, "amount_ngn": 5000, "nozzle_id": pump["nozzles"][0]["id"],
        })
        print("authorize:", authorized.status_code, authorized.json().get("status"),
              authorized.json().get("balance_ngn"))

        commands = c.get(f"/api/v1/fcc/commands/poll?device_uid={uid}").json()
        print("commands:", [x.get("type") for x in commands])

        if commands:
            completed = c.post("/api/v1/fcc/transaction/complete", json={
                "client_tx_ref": authorized.json()["reference"],
                "dispenser_id": pump["id"], "dispensed_liters": 5,
                "cpu_volume_l": 5, "pulser_volume_l": 5, "raw_pulse_count": 5,
                "unit_price_ngn": 1000, "total_charged_ngn": 5000,
            })
            print("complete:", completed.status_code, completed.json().get("discrepancy"))


if __name__ == "__main__":
    main()
