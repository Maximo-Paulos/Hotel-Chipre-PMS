"""Add the corporate channel to the analytics fact enum.

Reservation.channel_code already accepts ``company``.  PostgreSQL stores the
fact table's channel in a separate native enum, so analytics fact refreshes for
corporate reservations otherwise fail when persisting that value.

Revision ID: 20261018_fact_company_channel_enum
Revises: 20261018_stay_metrics_deposit_rules
"""
from alembic import op


revision = "20261018_fact_company_channel_enum"
down_revision = "20261018_stay_metrics_deposit_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        # Keep compatibility with PostgreSQL versions that require ALTER TYPE
        # ADD VALUE outside a transaction block.
        op.execute("COMMIT")
        op.execute(
            "ALTER TYPE fact_reservation_daily_channel_code_enum "
            "ADD VALUE IF NOT EXISTS 'company'"
        )


def downgrade() -> None:
    # PostgreSQL cannot remove an enum value safely without rebuilding the
    # type and every dependent column. Keeping the extra value is harmless.
    pass
