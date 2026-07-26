"""v72 section 12.3 - payment_surcharges table.

Revision ID: 20260624_payment_surcharges
Revises: 20260624_daily_rates
Create Date: 2026-06-24
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260624_payment_surcharges"
down_revision: Union[str, Sequence[str], None] = "20260624_daily_rates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guarded because some production environments already created this
    # table (and its inline enum type) out-of-band via an old startup
    # self-heal pass while alembic_version stayed on an older revision --
    # see 20260612_audit_log_and_transaction_fk for the same pattern.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_postgres = bind.dialect.name == "postgresql"

    # `create_type` is not a real kwarg on generic sa.Enum (silently
    # swallowed) -- postgresql.ENUM must be used directly so create_type=False
    # actually suppresses create_table's own auto-create attempt, matching
    # the _pg_enum/_enum pattern used elsewhere (e.g.
    # 20260612_vouchers_refunds_pending_actions.py).
    if is_postgres:
        surcharge_type_col = postgresql.ENUM(
            "fixed", "percentage", name="payment_surcharge_type_enum", create_type=False,
        )
        # checkfirst=True so an enum type left over from an old self-heal
        # pass (with no matching table) doesn't collide with create_table's
        # own attempt to auto-create it.
        postgresql.ENUM(
            "fixed", "percentage", name="payment_surcharge_type_enum",
        ).create(bind, checkfirst=True)
    else:
        surcharge_type_col = sa.Enum("fixed", "percentage", name="payment_surcharge_type_enum")

    if "payment_surcharges" not in inspector.get_table_names():
        op.create_table(
            "payment_surcharges",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "hotel_id",
                sa.Integer(),
                sa.ForeignKey("hotel_configuration.id"),
                nullable=False,
            ),
            sa.Column("payment_method", sa.String(50), nullable=False),
            sa.Column("surcharge_type", surcharge_type_col, nullable=False),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("currency_code", sa.String(3), nullable=False, server_default="ARS"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint("hotel_id", "payment_method", name="uq_payment_surcharges_hotel_method"),
        )


def downgrade() -> None:
    op.drop_table("payment_surcharges")
    op.execute("DROP TYPE IF EXISTS payment_surcharge_type_enum")
