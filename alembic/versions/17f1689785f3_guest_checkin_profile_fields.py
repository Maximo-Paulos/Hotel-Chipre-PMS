"""guest checkin profile fields

Revision ID: 17f1689785f3
Revises: 20260725_res_hotel_room_dates_idx
Create Date: 2026-07-25 18:33:01.539176
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '17f1689785f3'
down_revision: Union[str, None] = '20260725_res_hotel_room_dates_idx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("guests") as batch_op:
        batch_op.add_column(sa.Column("birth_place", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("birth_country", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("marital_status", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("occupation", sa.String(length=120), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("guests") as batch_op:
        batch_op.drop_column("occupation")
        batch_op.drop_column("marital_status")
        batch_op.drop_column("birth_country")
        batch_op.drop_column("birth_place")
