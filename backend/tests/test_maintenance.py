"""Verification for maintenance worker tasks on an isolated SQLite database."""

import os
import tempfile

_TEST_DB = os.path.join(tempfile.gettempdir(), "ve360_maintenance_test.db")
if os.path.exists(_TEST_DB):
    os.remove(_TEST_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"

from app.db.init_db import init_db  # noqa: E402

init_db()

from app.worker.tasks import (  # noqa: E402
    check_offline_devices,
    cleanup_expired_tokens,
    partition_maintenance,
    process_notifications,
    reconcile_discrepancies,
)

results = [
    ("offline devices", check_offline_devices()),
    ("discrepancies", reconcile_discrepancies()),
    ("notifications", process_notifications()),
    ("token cleanup", cleanup_expired_tokens()),
    ("partitions", partition_maintenance()),
]
for name, result in results:
    print(f"PASS {name}: {result}")
print(f"TOTAL: {len(results)}/{len(results)} maintenance tasks passed")
