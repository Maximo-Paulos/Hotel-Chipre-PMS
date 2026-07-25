"""repair sqlite reservation status enum pre_check_in

PostgreSQL got `pre_check_in` added to reservation_status_enum via
`ALTER TYPE ... ADD VALUE` back in 20260612_v72_gaps_phase4, but that
migration only runs on the postgresql dialect -- SQLite's CHECK constraint
(baked in at CREATE TABLE time) never got the equivalent repair, so
`pre_check_in` was dead on SQLite: PRE_CHECK_IN existed in the Python enum
but writing it raised a CHECK constraint violation (B3.1 is the first place
that actually writes it). Same repair pattern as
20260724_allocation_enum_values.py.

Revision ID: 62fddec52b79
Revises: 17f1689785f3
Create Date: 2026-07-25 18:57:06.801185
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '62fddec52b79'
down_revision: Union[str, None] = '17f1689785f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WITH_PRE_CHECK_IN = (
    "pending", "deposit_paid", "fully_paid", "pre_check_in",
    "checked_in", "checked_out", "cancelled", "no_show",
)
_WITHOUT_PRE_CHECK_IN = (
    "pending", "deposit_paid", "fully_paid",
    "checked_in", "checked_out", "cancelled", "no_show",
)


def _check_clause(values: tuple[str, ...]) -> str:
    return "status IN ({})".format(", ".join(repr(value) for value in values))


def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    with op.batch_alter_table("reservations", recreate="always") as batch:
        batch.drop_constraint("reservation_status_enum", type_="check")
        batch.create_check_constraint("reservation_status_enum", _check_clause(_WITH_PRE_CHECK_IN))


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    with op.batch_alter_table("reservations", recreate="always") as batch:
        batch.drop_constraint("reservation_status_enum", type_="check")
        batch.create_check_constraint("reservation_status_enum", _check_clause(_WITHOUT_PRE_CHECK_IN))
