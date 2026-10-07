"""allow pre-check-in reservation facts

The reservation status enum already includes ``pre_check_in``, but the
separate analytics-fact enum was created before that state existed. This
keeps PostgreSQL's enum and SQLite's CHECK constraint aligned with the model.

Downgrade is intentionally a no-op: PostgreSQL cannot safely remove an enum
label, and historical analytics facts may already use this valid status.

Revision ID: db9b84864700
Revises: 20261017_laundry_missing_follow_up
Create Date: 2026-10-06 19:28:00.980426
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'db9b84864700'
down_revision: Union[str, None] = '20261017_laundry_missing_follow_up'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            "ALTER TYPE fact_reservation_daily_status_enum "
            "ADD VALUE IF NOT EXISTS 'pre_check_in'"
        )
    elif dialect == "sqlite":
        values = (
            "pending",
            "deposit_paid",
            "fully_paid",
            "pre_check_in",
            "checked_in",
            "checked_out",
            "cancelled",
            "no_show",
        )
        constraint = "status IN ({})".format(", ".join(repr(value) for value in values))
        with op.batch_alter_table("fact_reservation_daily", recreate="always") as batch:
            batch.drop_constraint("fact_reservation_daily_status_enum", type_="check")
            batch.create_check_constraint("fact_reservation_daily_status_enum", constraint)


def downgrade() -> None:
    # Removing this value would either fail on PostgreSQL or invalidate stored
    # historical facts. Keep the expanded enum contract on downgrade.
    return None
