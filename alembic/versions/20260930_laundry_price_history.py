"""Version laundry vendor prices by effective date and restrict default edits.

Revision ID: 20260930_laundry_price_history
Revises: f595b2191009
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260930_laundry_price_history"
down_revision: Union[str, None] = "f595b2191009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("laundry_vendor_prices") as batch_op:
        batch_op.add_column(sa.Column("effective_from", sa.Date(), nullable=True))

    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        connection.execute(
            sa.text(
                "UPDATE laundry_vendor_prices "
                "SET effective_from = date(created_at) "
                "WHERE effective_from IS NULL"
            )
        )
    else:
        connection.execute(
            sa.text(
                "UPDATE laundry_vendor_prices "
                "SET effective_from = CAST(created_at AS DATE) "
                "WHERE effective_from IS NULL"
            )
        )

    with op.batch_alter_table("laundry_vendor_prices") as batch_op:
        batch_op.alter_column("effective_from", existing_type=sa.Date(), nullable=False)
        batch_op.drop_constraint("uq_laundry_vendor_prices_vendor_item", type_="unique")
        batch_op.create_unique_constraint(
            "uq_laundry_vendor_prices_vendor_item_effective",
            ["vendor_id", "linen_item_id", "effective_from"],
        )

    connection.execute(
        sa.text(
            "UPDATE role_permission_defaults SET allowed = false "
            "WHERE role = 'manager' AND permission_code = 'laundry:price_manage'"
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    duplicate = connection.execute(
        sa.text(
            "SELECT 1 FROM laundry_vendor_prices "
            "GROUP BY vendor_id, linen_item_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot downgrade laundry price history while multiple effective prices exist for a vendor item."
        )

    with op.batch_alter_table("laundry_vendor_prices") as batch_op:
        batch_op.drop_constraint("uq_laundry_vendor_prices_vendor_item_effective", type_="unique")
        batch_op.create_unique_constraint(
            "uq_laundry_vendor_prices_vendor_item", ["vendor_id", "linen_item_id"]
        )
        batch_op.drop_column("effective_from")

    connection.execute(
        sa.text(
            "UPDATE role_permission_defaults SET allowed = true "
            "WHERE role = 'manager' AND permission_code = 'laundry:price_manage'"
        )
    )
