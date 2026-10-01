"""hotel check-in checkout times

Revision ID: 015f7e36b9cd
Revises: 20260930_housekeeping_board_permission
Create Date: 2026-09-30 00:10:32.843916
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '015f7e36b9cd'
down_revision: Union[str, None] = '20260930_housekeeping_board_permission'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("hotel_configuration")}
    if "check_in_time" not in columns:
        op.add_column("hotel_configuration", sa.Column("check_in_time", sa.String(length=5), nullable=True))
    if "check_out_time" not in columns:
        op.add_column("hotel_configuration", sa.Column("check_out_time", sa.String(length=5), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("hotel_configuration")}
    if "check_out_time" in columns:
        op.drop_column("hotel_configuration", "check_out_time")
    if "check_in_time" in columns:
        op.drop_column("hotel_configuration", "check_in_time")
