"""Self-contained local load test.

Starts a real uvicorn server against a throwaway SQLite database, provisions
one FCC device, then sends concurrent heartbeats and replays half of them to
verify deduplication. No secrets are printed.

Run from backend/:  python -m tests.load_local --events 100 --concurrency 10
"""

import argparse
import asyncio
import os
import tempfile
import threading
import time
import uuid

import httpx
import uvicorn

HOST = "127.0.0.1"
PORT = 8123


def _wait_for_health(base: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    with httpx.Client(timeout=2.0) as client:
        while time.monotonic() < deadline:
            try:
                if client.get(f"{base}/health").status_code == 200:
                    return
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
    raise RuntimeError("Server did not become healthy")


def _bootstrap(base: str, device_uid: str) -> str:
    with httpx.Client(base_url=base, timeout=10.0) as client:
        setup = client.post("/api/v1/setup/admin", json={
            "setup_token": "change-this-setup-token",
            "full_name": "Load Test Owner",
            "user_id": "LOADADMIN",
            "password": "LoadTest@1234",
            "confirm_password": "LoadTest@1234",
            "phone": "+2348000000001",
            "email": "load@example.com",
        })
        assert setup.status_code == 201, setup.text
        token = client.post("/api/v1/auth/login", json={
            "user_id": "LOADADMIN", "password": "LoadTest@1234",
        }).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        station = client.post("/api/v1/stations", headers=headers, json={
            "code": "LOAD-001", "name": "Load Test Station", "city": "Abuja",
        }).json()
        dispenser = client.post("/api/v1/dispensers", headers=headers, json={
            "station_id": station["id"], "code": "LOAD-PUMP-01", "nozzle_config": "SINGLE",
        }).json()
        fcc = client.post("/api/v1/fcc-devices", headers=headers, json={
            "device_uid": device_uid, "nozzle_id": dispenser["nozzles"][0]["id"],
        }).json()
        credential = client.post(
            f"/api/v1/device-ingest/provision/fcc/{fcc['id']}", headers=headers
        ).json()["credential"]
        return credential


async def _send(base: str, device_uid: str, token: str, events: list[dict], concurrency: int):
    endpoint = f"{base}/api/v1/device-ingest/fcc/{device_uid}/heartbeat"
    headers = {"Authorization": f"Bearer {token}"}
    latencies: list[float] = []
    failures: list[str] = []
    duplicates = 0
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=30.0) as client:
        async def post(event: dict) -> None:
            nonlocal duplicates
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.post(endpoint, headers=headers, json=event)
                    latencies.append(time.perf_counter() - started)
                    if response.status_code == 200:
                        duplicates += int(bool(response.json().get("duplicate")))
                    else:
                        failures.append(f"{event['event_id']}: HTTP {response.status_code}")
                except Exception as exc:  # noqa: BLE001
                    latencies.append(time.perf_counter() - started)
                    failures.append(f"{event['event_id']}: {type(exc).__name__}")

        started_all = time.perf_counter()
        await asyncio.gather(*(post(e) for e in events))
        elapsed = time.perf_counter() - started_all
    return elapsed, latencies, failures, duplicates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args()

    db_path = os.path.join(tempfile.gettempdir(), f"ve360_load_{uuid.uuid4().hex[:8]}.db")
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    base = f"http://{HOST}:{PORT}"

    config = uvicorn.Config("app.main:app", host=HOST, port=PORT, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        _wait_for_health(base)
        device_uid = f"FCC-LOAD-{uuid.uuid4().hex[:6].upper()}"
        token = _bootstrap(base, device_uid)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        events = [
            {
                "event_id": f"load-{uuid.uuid4().hex[:8]}-{i:06d}",
                "observed_at": stamp,
                "signal_strength_dbm": -70,
            }
            for i in range(args.events)
        ]
        elapsed, latencies, failures, duplicates = asyncio.run(
            _send(base, device_uid, token, events, args.concurrency)
        )
        replay_elapsed, replay_latencies, replay_failures, replay_duplicates = asyncio.run(
            _send(base, device_uid, token, events[: args.events // 2], args.concurrency)
        )
    finally:
        server.should_exit = True
        thread.join(timeout=10)

    all_latencies = sorted(latencies + replay_latencies)
    p50 = all_latencies[len(all_latencies) // 2] if all_latencies else 0.0
    p95 = all_latencies[int(len(all_latencies) * 0.95) - 1] if len(all_latencies) > 2 else p50
    print(f"events={args.events} concurrency={args.concurrency} elapsed={elapsed:.2f}s "
          f"rate={args.events / max(elapsed, 0.001):.1f}/s")
    print(f"storm_replay_duplicates={replay_duplicates}/{args.events // 2} "
          f"storm_elapsed={replay_elapsed:.2f}s")
    print(f"p50={p50 * 1000:.1f}ms p95={p95 * 1000:.1f}ms "
          f"failures={len(failures) + len(replay_failures)}")
    return 1 if failures or replay_failures or replay_duplicates < args.events // 2 else 0


if __name__ == "__main__":
    raise SystemExit(main())
