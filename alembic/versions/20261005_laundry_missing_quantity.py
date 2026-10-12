"""persist missing linen declared on laundry return slips

Revision ID: 20261005_laundry_missing
Revises: d2a7e93f4c2b
Create Date: 2026-10-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261005_laundry_missing"
down_revision: Union[str, None] = "d2a7e93f4c2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE = "laundry_remito_lines"
_OLD_CHECK = "ck_laundry_remito_lines_quantity_positive"
_NEW_CHECK = "ck_laundry_remito_lines_quantities_valid"


def upgrade() -> None:
    with op.batch_alter_table(_TABLE, recreate="auto") as batch_op:
        batch_op.add_column(
            sa.Column("missing_quantity", sa.Numeric(12, 2), server_default="0", nullable=False)
        )
        batch_op.drop_constraint(_OLD_CHECK, type_="check")
        batch_op.create_check_constraint(
            _NEW_CHECK,
            "quantity >= 0 AND missing_quantity >= 0 AND (quantity > 0 OR missing_quantity > 0)",
        )


def downgrade() -> None:
    connection = op.get_bind()
    has_claims = connection.execute(
        sa.text("SELECT 1 FROM laundry_remito_lines WHERE missing_quantity > 0 OR quantity = 0 LIMIT 1")
    ).first()
    if has_claims:
        raise RuntimeError(
            "Cannot downgrade laundry missing quantities while any remito line contains a declared loss; "
            "preserve or resolve those records first."
        )

    with op.batch_alter_table(_TABLE, recreate="auto") as batch_op:
        batch_op.drop_constraint(_NEW_CHECK, type_="check")
        batch_op.drop_column("missing_quantity")
        batch_op.create_check_constraint(_OLD_CHECK, "quantity > 0")
