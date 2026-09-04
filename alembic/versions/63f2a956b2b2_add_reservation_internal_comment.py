"""add reservation internal comment

Revision ID: 63f2a956b2b2
Revises: 20260904_operational_audit_cash_daily
Create Date: 2026-09-04 15:59:51.455011
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '63f2a956b2b2'
down_revision: Union[str, None] = '20260904_operational_audit_cash_daily'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("reservations")}
    if "reservation_comment" not in columns:
        op.add_column(
            "reservations",
            sa.Column("reservation_comment", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("reservations")}
    if "reservation_comment" in columns:
        op.drop_column("reservations", "reservation_comment")
