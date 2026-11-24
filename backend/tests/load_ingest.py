"""Load / reconnect-storm test for the device-ingest endpoint.

Run against a live server (local uvicorn or the Compose stack):

  VE360_URL=https://your-domain \
  VE360_DEVICE_UID=FCC-XXXX \
  VE360_INGEST_TOKEN=<one-time token from the provision endpoint> \
  python -m tests.load_ingest --events 500 --concurrency 20

Add ``--storm`` to replay the same event IDs a second time and verify that
idempotency holds during a simulated reconnect. The token is read from the
environment and is never printed.
"""

import argparse
import asyncio
import os
import statistics
import time
import uuid

import httpx


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--storm", action="store_true")
    args = parser.parse_args()

    base_url = os.environ.get("VE360_URL", "http://127.0.0.1:8000").rstrip("/")
    device_uid = os.environ.get("VE360_DEVICE_UID", "")
    token = os.environ.get("VE360_INGEST_TOKEN", "")
    if not device_uid or not token:
        print("Set VE360_DEVICE_UID and VE360_INGEST_TOKEN first.")
        return 2

    run_id = uuid.uuid4().hex[:8]
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    events = [
        {
            "event_id": f"load-{run_id}-{i:06d}",
            "observed_at": stamp,
            "signal_strength_dbm": -70,
        }
        for i in range(args.events)
    ]
    endpoint = f"{base_url}/api/v1/device-ingest/fcc/{device_uid}/heartbeat"
    headers = {"Authorization": f"Bearer {token}"}
    latencies: list[float] = []
    failures: list[str] = []
    duplicates = 0
    semaphore = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient(timeout=30.0) as client:
        async def send(event: dict) -> None:
            nonlocal duplicates
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.post(endpoint, json=event, headers=headers)
                    latencies.append(time.perf_counter() - started)
                    if response.status_code == 200:
                        if response.json().get("duplicate"):
                            duplicates += 1
                    else:
                        failures.append(f"{event['event_id']}: HTTP {response.status_code}")
                except Exception as exc:  # noqa: BLE001
                    latencies.append(time.perf_counter() - started)
                    failures.append(f"{event['event_id']}: {type(exc).__name__}")

        started_all = time.perf_counter()
        await asyncio.gather(*(send(e) for e in events))
        elapsed = time.perf_counter() - started_all

        if args.storm:
            await asyncio.gather(*(send(e) for e in events[: args.events // 2]))

    if latencies:
        ordered = sorted(latencies)
        p50 = ordered[len(ordered) // 2]
        p95 = ordered[int(len(ordered) * 0.95) - 1] if len(ordered) > 1 else p50
    else:
        p50 = p95 = 0.0

    print(f"events={len(events)} elapsed={elapsed:.2f}s rate={len(events) / max(elapsed, 0.001):.1f}/s")
    print(f"duplicates={duplicates} failures={len(failures)} p50={p50 * 1000:.1f}ms p95={p95 * 1000:.1f}ms")
    if failures:
        for item in failures[:10]:
            print("  FAIL", item)
        return 1
    if args.storm and duplicates < args.events // 2:
        print("Reconnect replay was not fully deduplicated.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
