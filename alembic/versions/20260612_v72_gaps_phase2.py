"""v72 gaps phase 2: guest search indexes, OTA dedup constraint, updated guest_tag_type_enum,
room_blocks table, company commercial fields.

Revision ID: 20260612_v72_gaps_phase2
Revises: 20260612_v72_gaps_phase1
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260612_v72_gaps_phase2"
down_revision = "20260612_v72_gaps_phase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    is_postgres = conn.dialect.name == "postgresql"

    # ── 1. guest_tag_type_enum: add 3 new values (PostgreSQL ALTER TYPE) ──────
    if is_postgres:
        op.execute("ALTER TYPE guest_tag_type_enum ADD VALUE IF NOT EXISTS 'robo_cosas'")
        op.execute("ALTER TYPE guest_tag_type_enum ADD VALUE IF NOT EXISTS 'prohibido_alojar'")
        op.execute("ALTER TYPE guest_tag_type_enum ADD VALUE IF NOT EXISTS 'requiere_deposito'")
        op.execute("CREATE TYPE room_block_reason_enum AS ENUM ("
                   "'maintenance', 'deep_cleaning', 'owner_use', "
                   "'vip_hold', 'overbooking_buffer', 'other')")

    # ── 2. guests: search indexes (v72 §2.4) ─────────────────────────────────
    with op.batch_alter_table("guests") as batch_op:
        batch_op.create_index("ix_guest_hotel_last_name", ["hotel_id", "last_name"])
        batch_op.create_index("ix_guest_hotel_email", ["hotel_id", "email"])
        batch_op.create_index("ix_guest_hotel_phone", ["hotel_id", "phone"])
        batch_op.create_index("ix_guest_hotel_document_number", ["hotel_id", "document_number"])

    # ── 3. reservations: OTA dedup constraint (v72 §10.1) ────────────────────
    with op.batch_alter_table("reservations") as batch_op:
        batch_op.create_unique_constraint(
            "uq_reservation_ota_external_id",
            ["hotel_id", "source_provider_code", "external_id"],
        )

    # ── 4. companies: commercial fields (v72 §3.3-3.5) ───────────────────────
    with op.batch_alter_table("companies") as batch_op:
        batch_op.add_column(sa.Column("contact_name", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("contact_email", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("contact_phone", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("administrative_contact", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("base_price", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("payment_deferred", sa.Boolean, nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("deferred_days", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("requires_voucher", sa.Boolean, nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("requires_signature", sa.Boolean, nullable=False, server_default="0"))

    # ── 5. room_blocks (v72 §14) ──────────────────────────────────────────────
    reason_col = (
        postgresql.ENUM(
            "maintenance", "deep_cleaning", "owner_use",
            "vip_hold", "overbooking_buffer", "other",
            name="room_block_reason_enum", create_type=False,
        )
        if is_postgres
        else sa.String(30)
    )
    op.create_table(
        "room_blocks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("hotel_id", sa.Integer, sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_id", sa.Integer, sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason_code", reason_col, nullable=False, server_default="other"),
        sa.Column("reason_note", sa.String(500), nullable=True),
        sa.Column("starts_at", sa.Date, nullable=False),
        sa.Column("ends_at", sa.Date, nullable=True),
        sa.Column("is_indefinite", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="ck_room_block_dates"),
        sa.CheckConstraint(
            "(is_indefinite = 1 AND ends_at IS NULL) OR (is_indefinite = 0)",
            name="ck_room_block_indefinite_consistency",
        ),
    )
    op.create_index("ix_room_blocks_hotel_room", "room_blocks", ["hotel_id", "room_id"])
    op.create_index("ix_room_blocks_hotel_dates", "room_blocks", ["hotel_id", "starts_at", "ends_at"])


def downgrade() -> None:
    op.drop_index("ix_room_blocks_hotel_dates", table_name="room_blocks")
    op.drop_index("ix_room_blocks_hotel_room", table_name="room_blocks")
    op.drop_table("room_blocks")

    with op.batch_alter_table("companies") as batch_op:
        for col in ("requires_signature", "requires_voucher", "deferred_days",
                    "payment_deferred", "base_price", "administrative_contact",
                    "contact_phone", "contact_email", "contact_name"):
            batch_op.drop_column(col)

    with op.batch_alter_table("reservations") as batch_op:
        batch_op.drop_constraint("uq_reservation_ota_external_id", type_="unique")

    with op.batch_alter_table("guests") as batch_op:
        batch_op.drop_index("ix_guest_hotel_document_number")
        batch_op.drop_index("ix_guest_hotel_phone")
        batch_op.drop_index("ix_guest_hotel_email")
        batch_op.drop_index("ix_guest_hotel_last_name")

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS room_block_reason_enum")
        # Note: cannot remove values from PostgreSQL enums; robo_cosas/prohibido_alojar/requiere_deposito remain
