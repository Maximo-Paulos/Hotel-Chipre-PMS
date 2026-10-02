"""Store external OTA payment amounts in their source currency.

Revision ID: 20261017_manual_ota_paid_currency
Revises: 20261016_co_owner_security_access
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261017_manual_ota_paid_currency"
down_revision: Union[str, None] = "20261016_co_owner_security_access"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    reservation_columns = {column["name"] for column in sa.inspect(bind).get_columns("reservations")}
    if "external_paid_currency" not in reservation_columns:
        op.add_column(
            "reservations",
            sa.Column("external_paid_currency", sa.String(length=3), nullable=True),
        )

    # Before this field existed, confirmed OTA credits were interpreted in the
    # reservation currency. Preserve that historical meaning; never infer FX.
    op.execute(
        sa.text(
            "UPDATE reservations "
            "SET external_paid_currency = COALESCE(NULLIF(UPPER(TRIM(currency_code)), ''), 'ARS') "
            "WHERE external_paid_amount > 0 AND external_paid_currency IS NULL"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("reservations")}
    if "external_paid_currency" not in columns:
        return
    mismatch = bind.execute(
        sa.text(
            "SELECT id FROM reservations "
            "WHERE external_paid_amount > 0 "
            "AND external_paid_currency IS NOT NULL "
            "AND UPPER(external_paid_currency) <> UPPER(COALESCE(NULLIF(TRIM(currency_code), ''), 'ARS')) "
            "LIMIT 1"
        )
    ).first()
    if mismatch is not None:
        raise RuntimeError(
            "Cannot downgrade OTA paid-currency migration while external payments use a different currency"
        )
    op.drop_column("reservations", "external_paid_currency")
