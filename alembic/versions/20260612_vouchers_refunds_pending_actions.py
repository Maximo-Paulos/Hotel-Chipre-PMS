"""vouchers, refund_requests, and pending_operational_actions

Implements the three missing business-requirement tables:

  1. hotel_vouchers + voucher_redemptions
     — Hotel credit lifecycle (refund §8.7 path 2).

  2. refund_requests
     — Tracks refund routing: gateway / voucher / manual_review (§8.7 all paths).

  3. pending_operational_actions
     — Follow-up items the system creates when auto-resolution is unsafe
       (master-plan §A1-A2 "pending_actions").

Revision ID: 20260612_vouchers_refunds_pending_actions
Revises: 20260612_audit_log_and_transaction_fk
Create Date: 2026-06-12 12:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg


revision: str = "20260612_vouchers_refunds_pending_actions"
down_revision: Union[str, Sequence[str], None] = "20260612_audit_log_and_transaction_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pg_enum(*values: str, name: str) -> sa.Enum:
    return pg.ENUM(*values, name=name, create_type=True)


def _generic_enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, create_constraint=True)


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ---- 1. Enum types (PostgreSQL only) ----
    if dialect == "postgresql":
        _pg_enum("active", "partially_redeemed", "fully_redeemed", "expired", "cancelled",
                 name="voucher_status_enum").create(op.get_bind(), checkfirst=True)
        _pg_enum("gateway", "voucher", "manual_review",
                 name="refund_path_enum").create(op.get_bind(), checkfirst=True)
        _pg_enum("pending", "approved", "processing", "completed", "failed", "cancelled",
                 name="refund_status_enum").create(op.get_bind(), checkfirst=True)
        _pg_enum(
            "manual_review_required", "ota_conflict", "room_move_needed",
            "refund_pending", "settlement_review", "allocation_conflict",
            "payment_discrepancy", "other",
            name="pending_action_type_enum",
        ).create(op.get_bind(), checkfirst=True)
        _pg_enum("open", "in_progress", "resolved", "dismissed",
                 name="pending_action_status_enum").create(op.get_bind(), checkfirst=True)
        _pg_enum("low", "medium", "high", "critical",
                 name="pending_action_priority_enum").create(op.get_bind(), checkfirst=True)

    def _enum(*values: str, name: str) -> sa.Enum:
        if dialect == "postgresql":
            return pg.ENUM(*values, name=name, create_type=False)
        return sa.Enum(*values, name=name, create_constraint=True)

    # ---- 2. hotel_vouchers ----
    # Guarded because some production environments created these tables
    # out-of-band via an old startup self-heal pass (Base.metadata.create_all())
    # while alembic_version stayed on an older revision -- see
    # 20260612_audit_log_and_transaction_fk for the same pattern.
    if "hotel_vouchers" not in inspector.get_table_names():
        op.create_table(
            "hotel_vouchers",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(),
                      sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False),
            sa.Column("guest_id", sa.Integer(),
                      sa.ForeignKey("guests.id", ondelete="SET NULL"), nullable=True),
            sa.Column("source_reservation_id", sa.Integer(),
                      sa.ForeignKey("reservations.id", ondelete="SET NULL"), nullable=True),
            sa.Column("voucher_code", sa.String(50), nullable=False),
            sa.Column("original_amount", sa.Float(), nullable=False),
            sa.Column("remaining_amount", sa.Float(), nullable=False),
            sa.Column("currency_code", sa.String(3), nullable=False, server_default="ARS"),
            sa.Column("status",
                      _enum("active", "partially_redeemed", "fully_redeemed", "expired", "cancelled",
                            name="voucher_status_enum"),
                      nullable=False),
            sa.Column("is_transferable", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("issued_at", sa.DateTime(), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("issued_by_user_id", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.CheckConstraint("remaining_amount >= 0", name="ck_hotel_vouchers_remaining_nonneg"),
            sa.CheckConstraint("original_amount > 0", name="ck_hotel_vouchers_original_positive"),
            sa.UniqueConstraint("hotel_id", "voucher_code", name="uq_hotel_vouchers_code_per_hotel"),
        )
    existing_indexes = {ix["name"] for ix in inspector.get_indexes("hotel_vouchers")} if inspector.has_table("hotel_vouchers") else set()
    if "ix_hotel_vouchers_hotel_guest" not in existing_indexes:
        op.create_index("ix_hotel_vouchers_hotel_guest", "hotel_vouchers", ["hotel_id", "guest_id"])
    if "ix_hotel_vouchers_hotel_status" not in existing_indexes:
        op.create_index("ix_hotel_vouchers_hotel_status", "hotel_vouchers", ["hotel_id", "status"])

    # ---- 3. voucher_redemptions ----
    if "voucher_redemptions" not in inspector.get_table_names():
        op.create_table(
            "voucher_redemptions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(),
                      sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False),
            sa.Column("voucher_id", sa.Integer(),
                      sa.ForeignKey("hotel_vouchers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reservation_id", sa.Integer(),
                      sa.ForeignKey("reservations.id", ondelete="SET NULL"), nullable=True),
            sa.Column("amount_used", sa.Float(), nullable=False),
            sa.Column("redeemed_at", sa.DateTime(), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("redeemed_by_user_id", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.CheckConstraint("amount_used > 0", name="ck_voucher_redemptions_amount_positive"),
        )
    existing_indexes = {ix["name"] for ix in inspector.get_indexes("voucher_redemptions")} if inspector.has_table("voucher_redemptions") else set()
    if "ix_voucher_redemptions_voucher_id" not in existing_indexes:
        op.create_index("ix_voucher_redemptions_voucher_id", "voucher_redemptions", ["voucher_id"])
    if "ix_voucher_redemptions_hotel_reservation" not in existing_indexes:
        op.create_index("ix_voucher_redemptions_hotel_reservation",
                        "voucher_redemptions", ["hotel_id", "reservation_id"])

    # ---- 4. refund_requests ----
    if "refund_requests" not in inspector.get_table_names():
        op.create_table(
            "refund_requests",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(),
                      sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reservation_id", sa.Integer(),
                      sa.ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("original_transaction_id", sa.Integer(),
                      sa.ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("currency_code", sa.String(3), nullable=False, server_default="ARS"),
            sa.Column("path",
                      _enum("gateway", "voucher", "manual_review", name="refund_path_enum"),
                      nullable=False),
            sa.Column("status",
                      _enum("pending", "approved", "processing", "completed", "failed", "cancelled",
                            name="refund_status_enum"),
                      nullable=False),
            sa.Column("gateway_refund_id", sa.String(200), nullable=True),
            sa.Column("gateway_response", sa.Text(), nullable=True),
            sa.Column("voucher_id", sa.Integer(),
                      sa.ForeignKey("hotel_vouchers.id", ondelete="SET NULL"), nullable=True),
            sa.Column("reason_code", sa.String(50), nullable=True),
            sa.Column("reason_note", sa.Text(), nullable=True),
            sa.Column("requested_by_user_id", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("authorized_by_user_id", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("requested_at", sa.DateTime(), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint("amount > 0", name="ck_refund_requests_amount_positive"),
        )
    existing_indexes = {ix["name"] for ix in inspector.get_indexes("refund_requests")} if inspector.has_table("refund_requests") else set()
    if "ix_refund_requests_hotel_reservation" not in existing_indexes:
        op.create_index("ix_refund_requests_hotel_reservation",
                        "refund_requests", ["hotel_id", "reservation_id"])
    if "ix_refund_requests_hotel_status" not in existing_indexes:
        op.create_index("ix_refund_requests_hotel_status",
                        "refund_requests", ["hotel_id", "status"])

    # ---- 5. pending_operational_actions ----
    if "pending_operational_actions" not in inspector.get_table_names():
        op.create_table(
            "pending_operational_actions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(),
                      sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reservation_id", sa.Integer(),
                      sa.ForeignKey("reservations.id", ondelete="SET NULL"), nullable=True),
            sa.Column("action_type",
                      _enum("manual_review_required", "ota_conflict", "room_move_needed",
                            "refund_pending", "settlement_review", "allocation_conflict",
                            "payment_discrepancy", "other",
                            name="pending_action_type_enum"),
                      nullable=False),
            sa.Column("status",
                      _enum("open", "in_progress", "resolved", "dismissed",
                            name="pending_action_status_enum"),
                      nullable=False),
            sa.Column("priority",
                      _enum("low", "medium", "high", "critical",
                            name="pending_action_priority_enum"),
                      nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("source_entity_type", sa.String(100), nullable=True),
            sa.Column("source_entity_id", sa.Integer(), nullable=True),
            sa.Column("is_system_generated", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("assigned_to_user_id", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("resolved_by_user_id", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("resolution_note", sa.Text(), nullable=True),
        )
    existing_indexes = {ix["name"] for ix in inspector.get_indexes("pending_operational_actions")} if inspector.has_table("pending_operational_actions") else set()
    if "ix_pending_actions_hotel_status" not in existing_indexes:
        op.create_index("ix_pending_actions_hotel_status",
                        "pending_operational_actions", ["hotel_id", "status"])
    if "ix_pending_actions_hotel_reservation" not in existing_indexes:
        op.create_index("ix_pending_actions_hotel_reservation",
                        "pending_operational_actions", ["hotel_id", "reservation_id"])
    if "ix_pending_actions_hotel_type_status" not in existing_indexes:
        op.create_index("ix_pending_actions_hotel_type_status",
                        "pending_operational_actions", ["hotel_id", "action_type", "status"])


def downgrade() -> None:
    dialect = op.get_context().dialect.name

    op.drop_index("ix_pending_actions_hotel_type_status", "pending_operational_actions")
    op.drop_index("ix_pending_actions_hotel_reservation", "pending_operational_actions")
    op.drop_index("ix_pending_actions_hotel_status", "pending_operational_actions")
    op.drop_table("pending_operational_actions")

    op.drop_index("ix_refund_requests_hotel_status", "refund_requests")
    op.drop_index("ix_refund_requests_hotel_reservation", "refund_requests")
    op.drop_table("refund_requests")

    op.drop_index("ix_voucher_redemptions_hotel_reservation", "voucher_redemptions")
    op.drop_index("ix_voucher_redemptions_voucher_id", "voucher_redemptions")
    op.drop_table("voucher_redemptions")

    op.drop_index("ix_hotel_vouchers_hotel_status", "hotel_vouchers")
    op.drop_index("ix_hotel_vouchers_hotel_guest", "hotel_vouchers")
    op.drop_table("hotel_vouchers")

    if dialect == "postgresql":
        for enum_name in [
            "pending_action_priority_enum", "pending_action_status_enum",
            "pending_action_type_enum", "refund_status_enum",
            "refund_path_enum", "voucher_status_enum",
        ]:
            sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
