"""Monthly range partitions for the two high-volume telemetry tables.

PostgreSQL only. SQLite development/test databases are untouched.
Partitions are created a few months ahead so an upstream clock error or a
long offline replay cannot cause an insert to fail.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import text

logger = logging.getLogger("ve360.partitioning")

# table -> partition key column
PARTITIONED_TABLES = {
    "device_events": "received_at",
    "tank_readings": "recorded_at",
}


def _add_months(value: datetime, months: int) -> datetime:
    index = value.month - 1 + months
    year = value.year + index // 12
    month = index % 12 + 1
    return value.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


def _dialect_name(bind) -> str:
    return getattr(getattr(bind, "dialect", None), "name", "")


def ensure_partitions(bind, months_back: int = 3, months_forward: int = 3) -> list[str]:
    """Create missing monthly partitions and a default partition."""
    if _dialect_name(bind) != "postgresql":
        return []

    created: list[str] = []
    now = datetime.utcnow()
    start = _add_months(now, -months_back)
    end = _add_months(now, months_forward + 1)

    cursor = start
    while cursor < end:
        nxt = _add_months(cursor, 1)
        for table, column in PARTITIONED_TABLES.items():
            name = f"{table}_{cursor:%Y%m}"
            ddl = text(
                f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF {table} "
                f"FOR VALUES FROM ('{cursor:%Y-%m-%d}') TO ('{nxt:%Y-%m-%d}')"
            )
            bind.execute(ddl)
            created.append(name)
        cursor = nxt

    for table in PARTITIONED_TABLES:
        name = f"{table}_default"
        bind.execute(text(f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF {table} DEFAULT"))
        created.append(name)

    if created:
        logger.info("Verified %d telemetry partitions", len(created))
    return created


def drop_old_partitions(bind, months_to_keep: int) -> list[str]:
    """Drop monthly partitions older than the retention window.

    The default partition is never dropped. This deletes historical telemetry
    by design; set TELEMETRY_RETENTION_MONTHS deliberately.
    """
    if _dialect_name(bind) != "postgresql" or months_to_keep <= 0:
        return []

    cutoff = _add_months(datetime.utcnow(), -months_to_keep)
    rows = bind.execute(text(
        "SELECT child.relname FROM pg_inherits "
        "JOIN pg_class parent ON pg_inherits.inhparent = parent.oid "
        "JOIN pg_class child ON pg_inherits.inhrelid = child.oid "
        "WHERE parent.relname IN ('device_events', 'tank_readings')"
    )).scalars().all()

    dropped: list[str] = []
    for name in rows:
        suffix = name.rsplit("_", 1)[-1]
        if len(suffix) != 6 or not suffix.isdigit():
            continue
        if datetime(int(suffix[:4]), int(suffix[4:]), 1) >= cutoff:
            continue
        bind.execute(text(f"DROP TABLE IF EXISTS {name}"))
        dropped.append(name)
    if dropped:
        logger.warning("Dropped %d expired telemetry partitions: %s", len(dropped), ", ".join(dropped))
    return dropped
