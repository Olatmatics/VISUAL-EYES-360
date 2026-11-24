"""Ensure monthly telemetry partitions exist.

PostgreSQL creates range partitions for device_events and tank_readings.
SQLite is a no-op, so local development and tests are unaffected.
"""

from alembic import op

revision = "0002_telemetry_partitions"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db.partitioning import ensure_partitions

    ensure_partitions(op.get_bind())


def downgrade() -> None:
    # Partitions hold telemetry data; they are retired by retention, not by
    # rolling back a migration. Intentionally left empty.
    pass
