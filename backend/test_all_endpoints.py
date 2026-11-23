import sys
from fastapi.testclient import TestClient
from app.main import app

def run_tests():
    client = TestClient(app)
    print("=" * 60)
    print("VISUAL EYES 360 - Comprehensive Backend Test Suite")
    print("=" * 60)

    # 1. Test Setup Status
    r = client.get("/api/v1/setup/status")
    assert r.status_code == 200, f"/setup/status failed: {r.status_code} {r.text}"
    print(f"[OK] GET /api/v1/setup/status -> 200 (setup_required: {r.json().get('setup_required')})")

    # 2. Test Admin Login
    login_admin = client.post("/api/v1/auth/login", json={"user_id": "SUPERADMIN001", "password": "Admin@1234"})
    assert login_admin.status_code == 200, f"Admin login failed: {login_admin.status_code} {login_admin.text}"
    admin_token = login_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print(f"[OK] POST /api/v1/auth/login (SUPERADMIN001) -> 200 (Token issued)")

    # 3. Test Manager Login
    login_mgr = client.post("/api/v1/auth/login", json={"user_id": "MGR001", "password": "Manager@5678"})
    assert login_mgr.status_code == 200, f"Manager login failed: {login_mgr.status_code} {login_mgr.text}"
    mgr_token = login_mgr.json()["access_token"]
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
    print(f"[OK] POST /api/v1/auth/login (MGR001) -> 200 (Token issued)")

    # Test Endpoints as Admin
    endpoints = [
        ("GET", "/api/v1/dashboard/summary"),
        ("GET", "/api/v1/stations"),
        ("GET", "/api/v1/dispensers"),
        ("GET", "/api/v1/nozzles"),
        ("GET", "/api/v1/fcc-devices"),
        ("GET", "/api/v1/tanks"),
        ("GET", "/api/v1/transactions"),
        ("GET", "/api/v1/reconciliation/pulser"),
        ("GET", "/api/v1/reconciliation/tank"),
        ("GET", "/api/v1/payments/terminals"),
        ("GET", "/api/v1/customers"),
        ("GET", "/api/v1/customers/fleets"),
        ("GET", "/api/v1/prices"),
        ("GET", "/api/v1/prices/history"),
        ("GET", "/api/v1/alerts"),
        ("GET", "/api/v1/reports/financial"),
        ("GET", "/api/v1/reports/inventory"),
        ("GET", "/api/v1/users"),
        ("GET", "/api/v1/users/roles"),
        ("GET", "/api/v1/users/audit-logs"),
    ]

    failed = 0
    for method, path in endpoints:
        if method == "GET":
            res = client.get(path, headers=admin_headers)
        if res.status_code == 200:
            count = len(res.json()) if isinstance(res.json(), list) else len(res.json().keys())
            print(f"[OK] {method:4} {path:<32} -> 200 OK (items/keys: {count})")
        else:
            print(f"[FAIL] {method:4} {path:<32} -> {res.status_code} {res.text}")
            failed += 1

    # Test Operational Endpoints: Dispense Simulation & Pulser Verification
    print("\nTesting Forecourt Operational Workflows...")
    
    # Simulate Dispense with 0.750L discrepancy (triggers discrepancy_alert)
    disp_sim = client.post(
        "/api/v1/transactions/simulate-dispense",
        headers=admin_headers,
        json={
            "station_code": "ABJ-001",
            "dispenser_code": "DISP-01",
            "nozzle_number": 1,
            "requested_volume": 30.0,
            "cpu_delivered_volume": 30.0,
            "pulser_measured_volume": 29.2,  # 0.8L discrepancy > 0.49L threshold
            "unit_price": 850.0,
            "payment_channel": "OPAY_POS",
            "payment_ref": "TEST-OPAY-REF-001",
        }
    )
    if disp_sim.status_code in [200, 201]:
        data = disp_sim.json()
        print(f"[OK] POST /api/v1/transactions/simulate-dispense -> {disp_sim.status_code} (Discrepancy: {data.get('volume_difference')}L, Alert: {data.get('discrepancy_alert')})")
    else:
        print(f"[FAIL] POST /api/v1/transactions/simulate-dispense -> {disp_sim.status_code} {disp_sim.text}")
        failed += 1

    # Test OPay Payment Verification
    opay_sim = client.post(
        "/api/v1/payments/verify-opay",
        headers=admin_headers,
        json={
            "terminal_id": "OPAY-POS-ABJ-N1",
            "amount": 25500.0,
            "rrn": "RRN-20261123-998811",
        }
    )
    if opay_sim.status_code == 200:
        print(f"[OK] POST /api/v1/payments/verify-opay -> 200 (Verified: {opay_sim.json().get('payment_status')})")
    else:
        print(f"[FAIL] POST /api/v1/payments/verify-opay -> {opay_sim.status_code} {opay_sim.text}")
        failed += 1

    print("=" * 60)
    if failed == 0:
        print("ALL BACKEND ENDPOINTS & WORKFLOWS VERIFIED SUCCESSFULLY (100% PASS)")
    else:
        print(f"FAILED {failed} ENDPOINTS")
    print("=" * 60)
    return failed

if __name__ == "__main__":
    sys.exit(run_tests())
