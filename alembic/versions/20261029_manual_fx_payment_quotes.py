"""Persist authorized manual FX payment amounts per reservation.

Revision ID: 20261029_manual_fx_payment_quotes
Revises: 20261029_fx_rate_cache
Create Date: 2026-10-29
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261029_manual_fx_payment_quotes"
down_revision: Union[str, None] = "20261029_fx_rate_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSION_CODE = "payment:fx_manual_set"
PERMISSION_DESCRIPTION = "Set a manual FX amount for one reservation"
ROLES = ("owner", "co_owner", "manager", "receptionist", "housekeeping")
ALLOWED_ROLES = frozenset({"owner", "co_owner", "manager"})


def upgrade() -> None:
    op.create_table(
        "manual_fx_payment_quotes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("payment_method", sa.String(length=50), nullable=False),
        sa.Column("reservation_currency_code", sa.String(length=3), nullable=False),
        sa.Column("tender_currency_code", sa.String(length=3), nullable=False),
        sa.Column("reservation_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("tender_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("reason", sa.String(length=240), nullable=False),
        sa.Column("surcharge_quote_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_transaction_id", sa.Integer(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("reservation_amount > 0", name="ck_manual_fx_quote_reservation_amount_positive"),
        sa.CheckConstraint("tender_amount > 0", name="ck_manual_fx_quote_tender_amount_positive"),
        sa.CheckConstraint(
            "reservation_currency_code <> tender_currency_code",
            name="ck_manual_fx_quote_distinct_currencies",
        ),
        sa.CheckConstraint("length(trim(reason)) > 0", name="ck_manual_fx_quote_reason_nonempty"),
        sa.CheckConstraint(
            "(consumed_at IS NULL AND consumed_transaction_id IS NULL) OR "
            "(consumed_at IS NOT NULL AND consumed_transaction_id IS NOT NULL)",
            name="ck_manual_fx_quote_consumption_pair",
        ),
        sa.CheckConstraint(
            "consumed_at IS NULL OR superseded_at IS NULL",
            name="ck_manual_fx_quote_not_consumed_and_superseded",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_manual_fx_quote_hotel_id_hotel_configuration", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name="fk_manual_fx_quote_created_by_user_id_users", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "reservation_id"], ["reservations.hotel_id", "reservations.id"],
            name="fk_manual_fx_quote_hotel_reservation", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "consumed_transaction_id"], ["transactions.hotel_id", "transactions.id"],
            name="fk_manual_fx_quote_consumed_transaction", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hotel_id", "id", name="uq_manual_fx_quote_hotel_id_id"),
    )
    op.create_index(
        "uq_manual_fx_quote_active_reservation_method_currency",
        "manual_fx_payment_quotes",
        ["hotel_id", "reservation_id", "payment_method", "tender_currency_code"],
        unique=True,
        postgresql_where=sa.text("consumed_at IS NULL AND superseded_at IS NULL"),
    )
    op.create_index(
        "ix_manual_fx_quotes_hotel_reservation",
        "manual_fx_payment_quotes",
        ["hotel_id", "reservation_id", "created_at"],
    )

    connection = op.get_bind()
    if connection.execute(
        sa.text("SELECT 1 FROM permissions WHERE code = :code"), {"code": PERMISSION_CODE}
    ).first() is None:
        op.bulk_insert(
            sa.table(
                "permissions",
                sa.column("code", sa.String),
                sa.column("description", sa.String),
                sa.column("critical", sa.Boolean),
                sa.column("step_up_required", sa.Boolean),
                sa.column("delegable", sa.Boolean),
            ),
            [{
                "code": PERMISSION_CODE,
                "description": PERMISSION_DESCRIPTION,
                "critical": False,
                "step_up_required": False,
                "delegable": True,
            }],
        )

    existing = {
        (row[0], row[1])
        for row in connection.execute(
            sa.text(
                "SELECT role, permission_code FROM role_permission_defaults "
                "WHERE permission_code = :code"
            ),
            {"code": PERMISSION_CODE},
        ).all()
    }
    missing = [
        {"role": role, "permission_code": PERMISSION_CODE, "allowed": role in ALLOWED_ROLES}
        for role in ROLES
        if (role, PERMISSION_CODE) not in existing
    ]
    if missing:
        op.bulk_insert(
            sa.table(
                "role_permission_defaults",
                sa.column("role", sa.String),
                sa.column("permission_code", sa.String),
                sa.column("allowed", sa.Boolean),
            ),
            missing,
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM role_permission_defaults WHERE permission_code = :code"),
        {"code": PERMISSION_CODE},
    )
    connection.execute(
        sa.text(
            "DELETE FROM permissions WHERE code = :code "
            "AND NOT EXISTS (SELECT 1 FROM hotel_permission_overrides WHERE permission_code = :code) "
            "AND NOT EXISTS (SELECT 1 FROM user_permission_overrides WHERE permission_code = :code) "
            "AND NOT EXISTS (SELECT 1 FROM temporary_action_grants WHERE permission_code = :code) "
            "AND NOT EXISTS (SELECT 1 FROM action_step_up_ticket_uses WHERE permission_code = :code)"
        ),
        {"code": PERMISSION_CODE},
    )
    op.drop_index(
        "ix_manual_fx_quotes_hotel_reservation", table_name="manual_fx_payment_quotes"
    )
    op.drop_index(
        "uq_manual_fx_quote_active_reservation_method_currency",
        table_name="manual_fx_payment_quotes",
    )
    op.drop_table("manual_fx_payment_quotes")
