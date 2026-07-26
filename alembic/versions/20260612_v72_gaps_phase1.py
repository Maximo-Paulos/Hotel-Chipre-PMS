"""v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+rating+tags,
reservation mobility_restriction, cash register, waitlist, surcharges, hotel API keys.

Revision ID: 20260612_v72_gaps_phase1
Revises: 20260612_vouchers_refunds_pending_actions
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260612_v72_gaps_phase1"
down_revision = "20260612_vouchers_refunds_pending_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    is_postgres = conn.dialect.name == "postgresql"
    inspector = sa.inspect(conn)

    # ── 1. guest_rating_enum (PostgreSQL only) ──────────────────────────────
    # Guarded (checkfirst=True instead of raw CREATE TYPE) because some
    # production environments created these enum types out-of-band via an
    # old startup self-heal pass while alembic_version stayed on an older
    # revision -- see 20260612_audit_log_and_transaction_fk for the same
    # pattern applied to tables.
    if is_postgres:
        postgresql.ENUM("normal", "excelente", "complicado", name="guest_rating_enum").create(conn, checkfirst=True)
        postgresql.ENUM("no_pago", "robo", "conflictivo", "vip", "alergias", "otro", name="guest_tag_type_enum").create(conn, checkfirst=True)
        postgresql.ENUM("open", "closed", "pending_approval", name="cash_session_status_enum").create(conn, checkfirst=True)
        postgresql.ENUM("income", "expense", "adjustment", name="cash_movement_type_enum").create(conn, checkfirst=True)
        postgresql.ENUM("waiting", "promoted", "cancelled", "expired", name="waitlist_status_enum").create(conn, checkfirst=True)
        postgresql.ENUM("whatsapp_bot", "web_engine", "channel_manager", "reporting", "other", name="api_key_purpose_enum").create(conn, checkfirst=True)

    # ── 2. guests: add rating, dedup constraint ──────────────────────────────
    guests_columns = {c["name"] for c in inspector.get_columns("guests")}
    guests_indexes = {ix["name"] for ix in inspector.get_indexes("guests")}
    guests_unique = {uc["name"] for uc in inspector.get_unique_constraints("guests")}
    with op.batch_alter_table("guests") as batch_op:
        rating_type = (
            postgresql.ENUM("normal", "excelente", "complicado", name="guest_rating_enum", create_type=False)
            if is_postgres
            else sa.String(20)
        )
        if "rating" not in guests_columns:
            batch_op.add_column(sa.Column("rating", rating_type, nullable=False, server_default="normal"))
        if "ix_guest_hotel_id" not in guests_indexes:
            batch_op.create_index("ix_guest_hotel_id", ["hotel_id"])
        if "uq_guest_document_per_hotel" not in guests_unique:
            batch_op.create_unique_constraint(
                "uq_guest_document_per_hotel",
                ["hotel_id", "document_type", "document_number"],
            )

    # ── 3. rooms: add score, is_accessible ──────────────────────────────────
    rooms_columns = {c["name"] for c in inspector.get_columns("rooms")}
    rooms_checks = {ck["name"] for ck in inspector.get_check_constraints("rooms")}
    with op.batch_alter_table("rooms") as batch_op:
        if "score" not in rooms_columns:
            batch_op.add_column(sa.Column("score", sa.Integer, nullable=True))
        if "is_accessible" not in rooms_columns:
            batch_op.add_column(sa.Column("is_accessible", sa.Boolean, nullable=False, server_default="0"))
        if "ck_room_score_range" not in rooms_checks:
            batch_op.create_check_constraint(
                "ck_room_score_range",
                "score IS NULL OR (score >= 1 AND score <= 10)",
            )

    # ── 4. room_categories: base_price_per_night Float → Numeric(12,2) ──────
    with op.batch_alter_table("room_categories") as batch_op:
        batch_op.alter_column(
            "base_price_per_night",
            type_=sa.Numeric(12, 2),
            existing_type=sa.Float,
        )

    # ── 5. reservations: Float → Numeric(12,2), add mobility_restriction ────
    reservations_columns = {c["name"] for c in inspector.get_columns("reservations")}
    with op.batch_alter_table("reservations") as batch_op:
        for col in ("total_amount", "amount_paid", "deposit_amount", "subtotal_amount",
                    "tax_amount", "fee_amount", "commission_amount", "net_amount"):
            batch_op.alter_column(col, type_=sa.Numeric(12, 2), existing_type=sa.Float)
        if "mobility_restriction" not in reservations_columns:
            batch_op.add_column(sa.Column("mobility_restriction", sa.Boolean, nullable=False, server_default="0"))

    # ── 6. transactions: Float → Numeric(12,2) ──────────────────────────────
    with op.batch_alter_table("transactions") as batch_op:
        for col in ("amount", "gross_amount", "tax_amount", "fee_amount", "net_amount"):
            batch_op.alter_column(col, type_=sa.Numeric(12, 2), existing_type=sa.Float,
                                  existing_nullable=(col != "amount"))

    # ── 7. hotel_vouchers: Float → Numeric(12,2) ────────────────────────────
    with op.batch_alter_table("hotel_vouchers") as batch_op:
        batch_op.alter_column("original_amount", type_=sa.Numeric(12, 2), existing_type=sa.Float)
        batch_op.alter_column("remaining_amount", type_=sa.Numeric(12, 2), existing_type=sa.Float)

    with op.batch_alter_table("voucher_redemptions") as batch_op:
        batch_op.alter_column("amount_used", type_=sa.Numeric(12, 2), existing_type=sa.Float)

    # ── 8. refund_requests: Float → Numeric(12,2) ───────────────────────────
    with op.batch_alter_table("refund_requests") as batch_op:
        batch_op.alter_column("amount", type_=sa.Numeric(12, 2), existing_type=sa.Float)

    # ── 9. guest_tags ────────────────────────────────────────────────────────
    tag_type_col = (
        postgresql.ENUM("no_pago", "robo", "conflictivo", "vip", "alergias", "otro",
                        name="guest_tag_type_enum", create_type=False)
        if is_postgres
        else sa.String(30)
    )
    if "guest_tags" not in inspector.get_table_names():
        op.create_table(
            "guest_tags",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer, sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False),
            sa.Column("guest_id", sa.Integer, sa.ForeignKey("guests.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tag_type", tag_type_col, nullable=False),
            sa.Column("note", sa.Text, nullable=True),
            sa.Column("expires_at", sa.DateTime, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
    if "ix_guest_tags_hotel_guest" not in ({ix["name"] for ix in inspector.get_indexes("guest_tags")} if inspector.has_table("guest_tags") else set()):
        op.create_index("ix_guest_tags_hotel_guest", "guest_tags", ["hotel_id", "guest_id"])

    # ── 10. cash_sessions ────────────────────────────────────────────────────
    session_status_col = (
        postgresql.ENUM("open", "closed", "pending_approval",
                        name="cash_session_status_enum", create_type=False)
        if is_postgres
        else sa.String(20)
    )
    if "cash_sessions" not in inspector.get_table_names():
        op.create_table(
            "cash_sessions",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer, sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False),
            sa.Column("opened_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("closed_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", session_status_col, nullable=False, server_default="open"),
            sa.Column("opening_balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("currency_code", sa.String(3), nullable=False, server_default="ARS"),
            sa.Column("opened_at", sa.DateTime, nullable=False),
            sa.Column("closed_at", sa.DateTime, nullable=True),
            sa.Column("notes", sa.Text, nullable=True),
            sa.CheckConstraint("opening_balance >= 0", name="ck_cash_sessions_opening_nonneg"),
        )
    if "ix_cash_sessions_hotel_status" not in ({ix["name"] for ix in inspector.get_indexes("cash_sessions")} if inspector.has_table("cash_sessions") else set()):
        op.create_index("ix_cash_sessions_hotel_status", "cash_sessions", ["hotel_id", "status"])

    # ── 11. cash_movements ───────────────────────────────────────────────────
    movement_type_col = (
        postgresql.ENUM("income", "expense", "adjustment",
                        name="cash_movement_type_enum", create_type=False)
        if is_postgres
        else sa.String(20)
    )
    if "cash_movements" not in inspector.get_table_names():
        op.create_table(
            "cash_movements",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer, sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False),
            sa.Column("session_id", sa.Integer, sa.ForeignKey("cash_sessions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reservation_id", sa.Integer, sa.ForeignKey("reservations.id", ondelete="SET NULL"), nullable=True),
            sa.Column("transaction_id", sa.Integer, sa.ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("recorded_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("movement_type", movement_type_col, nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("description", sa.String(300), nullable=True),
            sa.Column("recorded_at", sa.DateTime, nullable=False),
            sa.CheckConstraint("amount > 0", name="ck_cash_movements_amount_positive"),
        )
    cash_movements_indexes = {ix["name"] for ix in inspector.get_indexes("cash_movements")} if inspector.has_table("cash_movements") else set()
    if "ix_cash_movements_session_id" not in cash_movements_indexes:
        op.create_index("ix_cash_movements_session_id", "cash_movements", ["session_id"])
    if "ix_cash_movements_hotel_id" not in cash_movements_indexes:
        op.create_index("ix_cash_movements_hotel_id", "cash_movements", ["hotel_id"])

    # ── 12. cash_close_reports ───────────────────────────────────────────────
    if "cash_close_reports" not in inspector.get_table_names():
        op.create_table(
            "cash_close_reports",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer, sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False),
            sa.Column("session_id", sa.Integer, sa.ForeignKey("cash_sessions.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("closed_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("approved_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("expected_balance", sa.Numeric(12, 2), nullable=False),
            sa.Column("declared_balance", sa.Numeric(12, 2), nullable=False),
            sa.Column("difference", sa.Numeric(12, 2), nullable=False),
            sa.Column("difference_approved", sa.Boolean, nullable=False, server_default="0"),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("closed_at", sa.DateTime, nullable=False),
        )
    if "ix_cash_close_reports_hotel_id" not in ({ix["name"] for ix in inspector.get_indexes("cash_close_reports")} if inspector.has_table("cash_close_reports") else set()):
        op.create_index("ix_cash_close_reports_hotel_id", "cash_close_reports", ["hotel_id"])

    # ── 13. waitlist_entries ─────────────────────────────────────────────────
    waitlist_status_col = (
        postgresql.ENUM("waiting", "promoted", "cancelled", "expired",
                        name="waitlist_status_enum", create_type=False)
        if is_postgres
        else sa.String(20)
    )
    if "waitlist_entries" not in inspector.get_table_names():
        op.create_table(
            "waitlist_entries",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer, sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False),
            sa.Column("guest_id", sa.Integer, sa.ForeignKey("guests.id", ondelete="CASCADE"), nullable=False),
            sa.Column("category_id", sa.Integer, sa.ForeignKey("room_categories.id", ondelete="CASCADE"), nullable=False),
            sa.Column("promoted_reservation_id", sa.Integer, sa.ForeignKey("reservations.id", ondelete="SET NULL"), nullable=True),
            sa.Column("check_in_date", sa.Date, nullable=False),
            sa.Column("check_out_date", sa.Date, nullable=False),
            sa.Column("num_adults", sa.Integer, nullable=False, server_default="1"),
            sa.Column("num_children", sa.Integer, nullable=False, server_default="0"),
            sa.Column("status", waitlist_status_col, nullable=False, server_default="waiting"),
            sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("contact_phone", sa.String(50), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("promoted_at", sa.DateTime, nullable=True),
            sa.Column("expired_at", sa.DateTime, nullable=True),
            sa.CheckConstraint("check_out_date > check_in_date", name="ck_waitlist_dates"),
            sa.CheckConstraint("num_adults > 0", name="ck_waitlist_adults_positive"),
            sa.CheckConstraint("priority >= 0", name="ck_waitlist_priority_nonneg"),
        )
    waitlist_indexes = {ix["name"] for ix in inspector.get_indexes("waitlist_entries")} if inspector.has_table("waitlist_entries") else set()
    if "ix_waitlist_hotel_status" not in waitlist_indexes:
        op.create_index("ix_waitlist_hotel_status", "waitlist_entries", ["hotel_id", "status"])
    if "ix_waitlist_hotel_category_dates" not in waitlist_indexes:
        op.create_index("ix_waitlist_hotel_category_dates", "waitlist_entries",
                        ["hotel_id", "category_id", "check_in_date", "check_out_date"])

    # ── 14. payment_surcharge_configs ────────────────────────────────────────
    if "payment_surcharge_configs" not in inspector.get_table_names():
        op.create_table(
            "payment_surcharge_configs",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer, sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False),
            sa.Column("payment_method", sa.String(30), nullable=False),
            sa.Column("surcharge_pct", sa.Numeric(5, 4), nullable=True),
            sa.Column("surcharge_fixed", sa.Numeric(12, 2), nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("updated_at", sa.DateTime, nullable=False),
            sa.CheckConstraint(
                "surcharge_pct IS NULL OR (surcharge_pct >= 0 AND surcharge_pct < 1)",
                name="ck_surcharge_pct_range",
            ),
            sa.CheckConstraint("surcharge_fixed IS NULL OR surcharge_fixed >= 0", name="ck_surcharge_fixed_nonneg"),
            sa.UniqueConstraint("hotel_id", "payment_method", name="uq_surcharge_hotel_method"),
        )
    if "ix_surcharge_hotel_id" not in ({ix["name"] for ix in inspector.get_indexes("payment_surcharge_configs")} if inspector.has_table("payment_surcharge_configs") else set()):
        op.create_index("ix_surcharge_hotel_id", "payment_surcharge_configs", ["hotel_id"])

    # ── 15. hotel_api_keys ───────────────────────────────────────────────────
    api_purpose_col = (
        postgresql.ENUM("whatsapp_bot", "web_engine", "channel_manager", "reporting", "other",
                        name="api_key_purpose_enum", create_type=False)
        if is_postgres
        else sa.String(30)
    )
    if "hotel_api_keys" not in inspector.get_table_names():
        op.create_table(
            "hotel_api_keys",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer, sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("revoked_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("purpose", api_purpose_col, nullable=False, server_default="other"),
            sa.Column("key_prefix", sa.String(8), nullable=False),
            sa.Column("key_hash", sa.String(128), nullable=False),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
            sa.Column("last_used_at", sa.DateTime, nullable=True),
            sa.Column("expires_at", sa.DateTime, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("revoked_at", sa.DateTime, nullable=True),
            sa.UniqueConstraint("hotel_id", "name", name="uq_hotel_api_key_name"),
        )
    if "ix_hotel_api_keys_hotel_id" not in ({ix["name"] for ix in inspector.get_indexes("hotel_api_keys")} if inspector.has_table("hotel_api_keys") else set()):
        op.create_index("ix_hotel_api_keys_hotel_id", "hotel_api_keys", ["hotel_id"])


def downgrade() -> None:
    op.drop_table("hotel_api_keys")
    op.drop_table("payment_surcharge_configs")
    op.drop_table("waitlist_entries")
    op.drop_table("cash_close_reports")
    op.drop_table("cash_movements")
    op.drop_table("cash_sessions")
    op.drop_table("guest_tags")

    with op.batch_alter_table("refund_requests") as batch_op:
        batch_op.alter_column("amount", type_=sa.Float, existing_type=sa.Numeric(12, 2))

    with op.batch_alter_table("voucher_redemptions") as batch_op:
        batch_op.alter_column("amount_used", type_=sa.Float, existing_type=sa.Numeric(12, 2))

    with op.batch_alter_table("hotel_vouchers") as batch_op:
        batch_op.alter_column("original_amount", type_=sa.Float, existing_type=sa.Numeric(12, 2))
        batch_op.alter_column("remaining_amount", type_=sa.Float, existing_type=sa.Numeric(12, 2))

    with op.batch_alter_table("transactions") as batch_op:
        for col in ("amount", "gross_amount", "tax_amount", "fee_amount", "net_amount"):
            batch_op.alter_column(col, type_=sa.Float, existing_type=sa.Numeric(12, 2))

    with op.batch_alter_table("reservations") as batch_op:
        batch_op.drop_column("mobility_restriction")
        for col in ("total_amount", "amount_paid", "deposit_amount", "subtotal_amount",
                    "tax_amount", "fee_amount", "commission_amount", "net_amount"):
            batch_op.alter_column(col, type_=sa.Float, existing_type=sa.Numeric(12, 2))

    with op.batch_alter_table("room_categories") as batch_op:
        batch_op.alter_column("base_price_per_night", type_=sa.Float, existing_type=sa.Numeric(12, 2))

    with op.batch_alter_table("rooms") as batch_op:
        batch_op.drop_constraint("ck_room_score_range", type_="check")
        batch_op.drop_column("is_accessible")
        batch_op.drop_column("score")

    with op.batch_alter_table("guests") as batch_op:
        batch_op.drop_constraint("uq_guest_document_per_hotel", type_="unique")
        batch_op.drop_index("ix_guest_hotel_id")
        batch_op.drop_column("rating")

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS api_key_purpose_enum")
        op.execute("DROP TYPE IF EXISTS waitlist_status_enum")
        op.execute("DROP TYPE IF EXISTS cash_movement_type_enum")
        op.execute("DROP TYPE IF EXISTS cash_session_status_enum")
        op.execute("DROP TYPE IF EXISTS guest_tag_type_enum")
        op.execute("DROP TYPE IF EXISTS guest_rating_enum")
