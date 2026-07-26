"""v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields,
company_documents table, reservations.pre_check_in_at.

Revision ID: 20260612_v72_gaps_phase4
Revises: 20260612_v72_gaps_phase3
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260612_v72_gaps_phase4"
down_revision = "20260612_v72_gaps_phase3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    is_postgres = conn.dialect.name == "postgresql"
    inspector = sa.inspect(conn)

    # ── 1. reservation_status_enum: add pre_check_in value ───────────────────
    if is_postgres:
        op.execute("ALTER TYPE reservation_status_enum ADD VALUE IF NOT EXISTS 'pre_check_in'")
        # Guarded (checkfirst=True instead of raw CREATE TYPE) because some
        # production environments created these enums out-of-band via an old
        # startup self-heal pass while alembic_version stayed on an older
        # revision -- see 20260612_audit_log_and_transaction_fk.
        postgresql.ENUM(
            "voucher_pdf", "signature_required", "authorization", "extension", "other",
            name="company_document_type_enum",
        ).create(conn, checkfirst=True)
        postgresql.ENUM(
            "pending", "signed", "waived", "rejected",
            name="company_document_status_enum",
        ).create(conn, checkfirst=True)

    # ── 2. reservations: add pre_check_in_at ─────────────────────────────────
    reservations_columns = {c["name"] for c in inspector.get_columns("reservations")}
    with op.batch_alter_table("reservations") as batch_op:
        if "pre_check_in_at" not in reservations_columns:
            batch_op.add_column(sa.Column("pre_check_in_at", sa.DateTime, nullable=True))

    # ── 3. room_move_events: add audit fields (v72 §5.5) ─────────────────────
    room_move_events_columns = {c["name"] for c in inspector.get_columns("room_move_events")}
    with op.batch_alter_table("room_move_events") as batch_op:
        if "reason_note" not in room_move_events_columns:
            batch_op.add_column(sa.Column("reason_note", sa.Text, nullable=True))
        if "trigger_event" not in room_move_events_columns:
            batch_op.add_column(sa.Column("trigger_event", sa.String(100), nullable=True))
        if "state_before" not in room_move_events_columns:
            batch_op.add_column(sa.Column("state_before", sa.String(50), nullable=True))
        if "state_after" not in room_move_events_columns:
            batch_op.add_column(sa.Column("state_after", sa.String(50), nullable=True))

    # ── 4. company_documents (v72 §3.6) ──────────────────────────────────────
    doc_type_col = (
        postgresql.ENUM(
            "voucher_pdf", "signature_required", "authorization", "extension", "other",
            name="company_document_type_enum", create_type=False,
        )
        if is_postgres
        else sa.String(30)
    )
    doc_status_col = (
        postgresql.ENUM(
            "pending", "signed", "waived", "rejected",
            name="company_document_status_enum", create_type=False,
        )
        if is_postgres
        else sa.String(20)
    )
    if "company_documents" not in inspector.get_table_names():
        op.create_table(
            "company_documents",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer, sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reservation_id", sa.Integer, sa.ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
            sa.Column("doc_type", doc_type_col, nullable=False, server_default="other"),
            sa.Column("status", doc_status_col, nullable=False, server_default="pending"),
            sa.Column("file_name", sa.String(300), nullable=True),
            sa.Column("file_url", sa.String(1000), nullable=True),
            sa.Column("requires_signature", sa.Boolean, nullable=False, server_default="0"),
            sa.Column("signed_at", sa.DateTime, nullable=True),
            sa.Column("signed_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("updated_at", sa.DateTime, nullable=False),
            sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
    company_documents_indexes = {ix["name"] for ix in inspector.get_indexes("company_documents")} if inspector.has_table("company_documents") else set()
    if "ix_company_documents_hotel_reservation" not in company_documents_indexes:
        op.create_index("ix_company_documents_hotel_reservation", "company_documents",
                        ["hotel_id", "reservation_id"])
    if "ix_company_documents_hotel_company" not in company_documents_indexes:
        op.create_index("ix_company_documents_hotel_company", "company_documents",
                        ["hotel_id", "company_id"])


def downgrade() -> None:
    op.drop_index("ix_company_documents_hotel_company", table_name="company_documents")
    op.drop_index("ix_company_documents_hotel_reservation", table_name="company_documents")
    op.drop_table("company_documents")

    with op.batch_alter_table("room_move_events") as batch_op:
        batch_op.drop_column("state_after")
        batch_op.drop_column("state_before")
        batch_op.drop_column("trigger_event")
        batch_op.drop_column("reason_note")

    with op.batch_alter_table("reservations") as batch_op:
        batch_op.drop_column("pre_check_in_at")

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS company_document_status_enum")
        op.execute("DROP TYPE IF EXISTS company_document_type_enum")
        # Note: cannot remove 'pre_check_in' from reservation_status_enum in PostgreSQL
