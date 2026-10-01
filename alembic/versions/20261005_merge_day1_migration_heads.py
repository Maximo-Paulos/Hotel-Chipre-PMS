"""Merge the parallel day 0 and day 1 schema branches."""
from alembic import op  # noqa: F401


revision = "20261005_merge_day1_migration_heads"
down_revision = (
    "20261004_checkin_full_payment_default",
    "20260930_laundry_price_history",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
