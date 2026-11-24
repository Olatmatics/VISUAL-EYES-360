"""Baseline marker for the existing schema.

The schema is currently created and reconciled by ``app.db.init_db`` (additive
migration plus idempotent seeding). This revision records that baseline.
Every schema change from here on must be a new, additive Alembic revision --
never an edit to an already-applied revision.
"""

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
