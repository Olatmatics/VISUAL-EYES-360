"""End-to-end OPay prototype check against the running backend."""

import time
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
        fccs = c.get("/api/v1/fcc-devices", headers=h).json()
        terminals = c.get("/api/v1/payments/terminals", headers=h).json()
        nozzle = next((n for n in nozzles if n.get("price") and n.get("price") > 0), None)
        if not nozzle:
            print("NO_NOZZLE_WITH_PRICE")
            return
        fcc = next((f for f in fccs if f.get("nozzle_id") == nozzle["id"]), None)
        pos = next((p for p in terminals if p.get("nozzle_id") == nozzle["id"]), None)
        if not fcc or not pos:
            print("NO_FCC_OR_POS_FOR_NOZZLE", bool(fcc), bool(pos))
            return

        reference = f"OPAYTEST{uuid.uuid4().hex[:8].upper()}"
        initiated = c.post("/api/v1/fcc/transaction/initiate", json={
            "client_tx_ref": reference,
            "nozzle_id": nozzle["id"],
            "target_amount_ngn": 5000,
            "payment_preference": "POS",
            "device_uid": fcc["device_uid"],
        })
        print("initiate:", initiated.status_code, initiated.json().get("status"),
              initiated.json().get("authorized_liters"))

        time.sleep(5)

        status = c.get(f"/api/v1/opay/status?reference={reference}", headers=h)
        print("status:", status.status_code, status.json().get("local_status"),
              (status.json().get("gateway") or {}).get("status"))

        commands = c.get(f"/api/v1/fcc/commands/poll?device_uid={fcc['device_uid']}")
        print("commands:", commands.status_code, [x.get("type") for x in commands.json()])
        if commands.json():
            ack = c.post("/api/v1/fcc/commands/ack", json={"command_id": commands.json()[0]["id"]})
            print("ack:", ack.status_code, ack.json().get("status"))

        completed = c.post("/api/v1/fcc/transaction/complete", json={
            "client_tx_ref": reference,
            "dispenser_id": nozzle.get("dispenser_id"),
            "dispensed_liters": 4.35,
            "cpu_volume_l": 4.35,
            "pulser_volume_l": 4.34,
            "raw_pulse_count": 434,
            "unit_price_ngn": nozzle["price"],
            "total_charged_ngn": 5000,
        })
        print("complete:", completed.status_code, completed.json())


if __name__ == "__main__":
    main()
