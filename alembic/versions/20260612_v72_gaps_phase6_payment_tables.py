"""v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_events)

Revision ID: 20260612_v72_gaps_phase6_payment_tables
Revises: 20260612_v72_gaps_phase5
Create Date: 2026-06-12

Brings payment gateway tables from main branch into the worktree chain.
Source of truth rule (architecture-hybrid.md §transactions-vs-payments):
  - transactions: the canonical financial ledger (one row per payment event, double-entry)
  - payments: gateway-specific tracking (provider, external_payment_id, webhook state)
  - payment_links: pre-payment objects sent to guest (MercadoPago/PayPal/Stripe)
  - Relationship: Payment.completed → writes Transaction (via payment_service.py)
"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "20260612_v72_gaps_phase6_payment_tables"
down_revision: Union[str, None] = "20260612_v72_gaps_phase5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    inspector = sa.inspect(bind)

    # Every object below is guarded because some production environments
    # already have this schema out-of-band via an old startup self-heal pass
    # (Base.metadata.create_all()) while alembic_version stayed on an older
    # revision -- see 20260612_audit_log_and_transaction_fk for the same
    # pattern.

    # Unique constraint on reservations so FK (hotel_id, id) works in payment tables.
    # Some environments got this via 20260626_repair_reservation_unique_constraint's
    # Postgres path, which creates it as a plain `CREATE UNIQUE INDEX` rather than a
    # named constraint -- inspector.get_unique_constraints() only sees pg_constraint
    # rows (contype='u'), not unique indexes, so that path is invisible to it. Check
    # both, or a same-named ADD CONSTRAINT fails with DuplicateTable (confirmed
    # against a real drifted PostgreSQL instance).
    reservations_unique = {uc["name"] for uc in inspector.get_unique_constraints("reservations")}
    reservations_indexes = {ix["name"] for ix in inspector.get_indexes("reservations")}
    if "uq_reservation_hotel_id_id" not in reservations_unique | reservations_indexes:
        if dialect_name == "sqlite":
            with op.batch_alter_table("reservations", recreate="always") as batch_op:
                batch_op.create_unique_constraint("uq_reservation_hotel_id_id", ["hotel_id", "id"])
        else:
            op.create_unique_constraint(
                "uq_reservation_hotel_id_id", "reservations", ["hotel_id", "id"]
            )

    if "payment_links" not in inspector.get_table_names():
        op.create_table(
            "payment_links",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotel_configuration.id"), nullable=False),
            sa.Column("reservation_id", sa.Integer(), nullable=False),
            sa.Column("link_code", sa.String(64), nullable=False),
            sa.Column("requested_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("collected_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("currency", sa.String(3), nullable=False, server_default="ARS"),
            sa.Column("provider", sa.String(30), nullable=False, server_default="mercado_pago"),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("recipient_email", sa.String(255), nullable=False),
            sa.Column("recipient_name", sa.String(255), nullable=True),
            sa.Column("recipient_phone", sa.String(20), nullable=True),
            sa.Column("sent_via_email", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("sent_via_whatsapp", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("external_reference", sa.String(120), nullable=True),
            sa.Column("external_checkout_url", sa.Text(), nullable=True),
            sa.Column("external_qr_code", sa.Text(), nullable=True),
            sa.Column("title", sa.String(255), nullable=False, server_default="Pago de Reserva"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("allow_partial_payments", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("require_exact_amount", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_by", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
            sa.Column("first_payment_at", sa.DateTime(), nullable=True),
            sa.Column("last_payment_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("gateway_response", sa.JSON(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.CheckConstraint("requested_amount > 0", name="ck_payment_link_amount_positive"),
            sa.CheckConstraint("collected_amount >= 0", name="ck_payment_link_collected_nonnegative"),
            sa.ForeignKeyConstraint(
                ["hotel_id", "reservation_id"],
                ["reservations.hotel_id", "reservations.id"],
                name="fk_payment_link_hotel_reservation",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint("hotel_id", "id", name="uq_payment_link_hotel_id_id"),
            sa.UniqueConstraint("link_code", name="uq_payment_link_code"),
            sa.UniqueConstraint(
                "hotel_id", "provider", "external_reference",
                name="uq_payment_link_external_per_hotel_provider",
            ),
        )
    payment_links_indexes = {ix["name"] for ix in inspector.get_indexes("payment_links")} if inspector.has_table("payment_links") else set()
    if "ix_payment_links_hotel_id" not in payment_links_indexes:
        op.create_index("ix_payment_links_hotel_id", "payment_links", ["hotel_id"])
    if "ix_payment_links_reservation_id" not in payment_links_indexes:
        op.create_index("ix_payment_links_reservation_id", "payment_links", ["reservation_id"])
    if "ix_payment_links_link_code" not in payment_links_indexes:
        op.create_index("ix_payment_links_link_code", "payment_links", ["link_code"])
    if "ix_payment_links_status" not in payment_links_indexes:
        op.create_index("ix_payment_links_status", "payment_links", ["status"])
    if "ix_payment_links_external_reference" not in payment_links_indexes:
        op.create_index("ix_payment_links_external_reference", "payment_links", ["external_reference"])
    if "idx_hotel_reservation_link_status" not in payment_links_indexes:
        op.create_index(
            "idx_hotel_reservation_link_status", "payment_links",
            ["hotel_id", "reservation_id", "status"],
        )

    if "payments" not in inspector.get_table_names():
        op.create_table(
            "payments",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotel_configuration.id"), nullable=False),
            sa.Column("reservation_id", sa.Integer(), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="ARS"),
            sa.Column("provider", sa.String(30), nullable=False, server_default="cash"),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("external_payment_id", sa.String(200), nullable=True),
            sa.Column("external_status", sa.String(100), nullable=True),
            sa.Column("payment_link_id", sa.Integer(), sa.ForeignKey("payment_links.id", ondelete="SET NULL"), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("gateway_response", sa.JSON(), nullable=True),
            sa.Column("fee_amount", sa.Numeric(12, 2), nullable=True),
            sa.Column("net_amount", sa.Numeric(12, 2), nullable=True),
            sa.Column("fx_rate", sa.Float(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
            sa.ForeignKeyConstraint(
                ["hotel_id", "reservation_id"],
                ["reservations.hotel_id", "reservations.id"],
                name="fk_payment_hotel_reservation",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint("hotel_id", "id", name="uq_payment_hotel_id_id"),
            sa.UniqueConstraint(
                "hotel_id", "provider", "external_payment_id",
                name="uq_payment_external_per_hotel_provider",
            ),
        )
    payments_indexes = {ix["name"] for ix in inspector.get_indexes("payments")} if inspector.has_table("payments") else set()
    if "ix_payments_hotel_id" not in payments_indexes:
        op.create_index("ix_payments_hotel_id", "payments", ["hotel_id"])
    if "ix_payments_reservation_id" not in payments_indexes:
        op.create_index("ix_payments_reservation_id", "payments", ["reservation_id"])
    if "ix_payments_status" not in payments_indexes:
        op.create_index("ix_payments_status", "payments", ["status"])
    if "ix_payments_external_payment_id" not in payments_indexes:
        op.create_index("ix_payments_external_payment_id", "payments", ["external_payment_id"])
    if "ix_payments_created_at" not in payments_indexes:
        op.create_index("ix_payments_created_at", "payments", ["created_at"])
    if "idx_hotel_reservation_status" not in payments_indexes:
        op.create_index("idx_hotel_reservation_status", "payments", ["hotel_id", "reservation_id", "status"])
    if "idx_external_payment_id_hotel" not in payments_indexes:
        op.create_index("idx_external_payment_id_hotel", "payments", ["external_payment_id", "hotel_id"])

    if "payment_webhook_events" not in inspector.get_table_names():
        op.create_table(
            "payment_webhook_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), sa.ForeignKey("hotel_configuration.id"), nullable=False),
            sa.Column("payment_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(30), nullable=False),
            sa.Column("webhook_id", sa.String(200), nullable=True),
            sa.Column("event_type", sa.String(100), nullable=False),
            sa.Column("raw_payload", sa.JSON(), nullable=False),
            sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("processing_error", sa.Text(), nullable=True),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.Column("received_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ["hotel_id", "payment_id"],
                ["payments.hotel_id", "payments.id"],
                name="fk_webhook_event_hotel_payment",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "hotel_id", "provider", "webhook_id",
                name="uq_webhook_event_provider_id_per_hotel",
            ),
        )
    payment_webhook_events_indexes = {ix["name"] for ix in inspector.get_indexes("payment_webhook_events")} if inspector.has_table("payment_webhook_events") else set()
    if "ix_payment_webhook_events_hotel_id" not in payment_webhook_events_indexes:
        op.create_index("ix_payment_webhook_events_hotel_id", "payment_webhook_events", ["hotel_id"])
    if "ix_payment_webhook_events_payment_id" not in payment_webhook_events_indexes:
        op.create_index("ix_payment_webhook_events_payment_id", "payment_webhook_events", ["payment_id"])
    if "ix_payment_webhook_events_webhook_id" not in payment_webhook_events_indexes:
        op.create_index("ix_payment_webhook_events_webhook_id", "payment_webhook_events", ["webhook_id"])
    if "ix_payment_webhook_events_processed" not in payment_webhook_events_indexes:
        op.create_index("ix_payment_webhook_events_processed", "payment_webhook_events", ["processed"])
    if "ix_payment_webhook_events_received_at" not in payment_webhook_events_indexes:
        op.create_index("ix_payment_webhook_events_received_at", "payment_webhook_events", ["received_at"])
    if "idx_hotel_provider_event_type" not in payment_webhook_events_indexes:
        op.create_index(
            "idx_hotel_provider_event_type", "payment_webhook_events",
            ["hotel_id", "provider", "event_type"],
        )
    if "idx_unprocessed_webhooks" not in payment_webhook_events_indexes:
        op.create_index(
            "idx_unprocessed_webhooks", "payment_webhook_events",
            ["hotel_id", "processed", "received_at"],
        )

    # Performance indexes (from main's 20260612_query_performance_indexes)
    reservations_indexes = {ix["name"] for ix in inspector.get_indexes("reservations")}
    if "ix_reservation_hotel_status_checkin" not in reservations_indexes:
        op.create_index(
            "ix_reservation_hotel_status_checkin", "reservations",
            ["hotel_id", "status", "check_in_date"],
        )
    if "ix_reservation_hotel_room_status_dates" not in reservations_indexes:
        op.create_index(
            "ix_reservation_hotel_room_status_dates", "reservations",
            ["hotel_id", "room_id", "status", "check_in_date", "check_out_date"],
        )
    transactions_indexes = {ix["name"] for ix in inspector.get_indexes("transactions")}
    if "ix_transactions_hotel_reservation_created" not in transactions_indexes:
        op.create_index(
            "ix_transactions_hotel_reservation_created", "transactions",
            ["hotel_id", "reservation_id", "created_at"],
        )
    if "ix_transactions_hotel_status_created" not in transactions_indexes:
        op.create_index(
            "ix_transactions_hotel_status_created", "transactions",
            ["hotel_id", "status", "created_at"],
        )
    if "ix_transactions_external_payment_id" not in transactions_indexes:
        op.create_index(
            "ix_transactions_external_payment_id", "transactions", ["external_payment_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    op.drop_index("ix_transactions_external_payment_id", table_name="transactions")
    op.drop_index("ix_transactions_hotel_status_created", table_name="transactions")
    op.drop_index("ix_transactions_hotel_reservation_created", table_name="transactions")
    op.drop_index("ix_reservation_hotel_room_status_dates", table_name="reservations")
    op.drop_index("ix_reservation_hotel_status_checkin", table_name="reservations")

    op.drop_index("idx_unprocessed_webhooks", table_name="payment_webhook_events")
    op.drop_index("idx_hotel_provider_event_type", table_name="payment_webhook_events")
    op.drop_index("ix_payment_webhook_events_received_at", table_name="payment_webhook_events")
    op.drop_index("ix_payment_webhook_events_processed", table_name="payment_webhook_events")
    op.drop_index("ix_payment_webhook_events_webhook_id", table_name="payment_webhook_events")
    op.drop_index("ix_payment_webhook_events_payment_id", table_name="payment_webhook_events")
    op.drop_index("ix_payment_webhook_events_hotel_id", table_name="payment_webhook_events")
    op.drop_table("payment_webhook_events")

    op.drop_index("idx_external_payment_id_hotel", table_name="payments")
    op.drop_index("idx_hotel_reservation_status", table_name="payments")
    op.drop_index("ix_payments_created_at", table_name="payments")
    op.drop_index("ix_payments_external_payment_id", table_name="payments")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_reservation_id", table_name="payments")
    op.drop_index("ix_payments_hotel_id", table_name="payments")
    op.drop_table("payments")

    op.drop_index("idx_hotel_reservation_link_status", table_name="payment_links")
    op.drop_index("ix_payment_links_external_reference", table_name="payment_links")
    op.drop_index("ix_payment_links_status", table_name="payment_links")
    op.drop_index("ix_payment_links_link_code", table_name="payment_links")
    op.drop_index("ix_payment_links_reservation_id", table_name="payment_links")
    op.drop_index("ix_payment_links_hotel_id", table_name="payment_links")
    op.drop_table("payment_links")

    if dialect_name == "sqlite":
        with op.batch_alter_table("reservations", recreate="always") as batch_op:
            batch_op.drop_constraint("uq_reservation_hotel_id_id", type_="unique")
    else:
        op.drop_constraint("uq_reservation_hotel_id_id", "reservations", type_="unique")
