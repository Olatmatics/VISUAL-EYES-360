"""Check transaction filtering by state/LGA/station."""

import httpx

BASE = "http://127.0.0.1:8000"


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=20.0) as c:
        token = c.post("/api/v1/auth/login", json={
            "user_id": "SUPERADMIN001", "password": "Admin@1234",
        }).json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        states = c.get("/api/v1/geo/states", headers=h).json()
        for s in states:
            rr = c.get(f"/api/v1/transactions?state_id={s['id']}&limit=100", headers=h)
            if rr.json():
                print("state with transactions:", s["name"], "->", len(rr.json()))
                print("sample location:", rr.json()[0].get("state_name"), "/", rr.json()[0].get("lga_name"))
        kano = next((s for s in states if "kano" in s["name"].lower()), None)
        print("Kano state:", kano and kano["id"])
        if not kano:
            return
        lgas = c.get(f"/api/v1/geo/states/{kano['id']}/lgas", headers=h).json()
        print("Kano LGAs:", len(lgas))
        r = c.get(f"/api/v1/transactions?state_id={kano['id']}&limit=100", headers=h)
        print("Kano transactions:", r.status_code, len(r.json()))
        if r.json():
            print("sample:", r.json()[0].get("state_name"), "/", r.json()[0].get("lga_name"))
        if lgas:
            r2 = c.get(f"/api/v1/transactions?state_id={kano['id']}&lga_id={lgas[0]['id']}", headers=h)
            print("First LGA transactions:", r2.status_code, len(r2.json()))


if __name__ == "__main__":
    main()
