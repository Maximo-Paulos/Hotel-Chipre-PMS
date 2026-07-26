"""v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjustment Float→Numeric.

Revision ID: 20260612_v72_gaps_phase3
Revises: 20260612_v72_gaps_phase2
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa

revision = "20260612_v72_gaps_phase3"
down_revision = "20260612_v72_gaps_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    # ── 1. room_movement_groups (v72 §5.4) ───────────────────────────────────
    if "room_movement_groups" not in inspector.get_table_names():
        op.create_table(
            "room_movement_groups",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer, sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False),
            sa.Column("trigger_reason", sa.String(100), nullable=False),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("is_reverted", sa.Boolean, nullable=False, server_default="0"),
            sa.Column("reverted_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("reverted_at", sa.DateTime, nullable=True),
            sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )
    if "ix_room_movement_groups_hotel_id" not in ({ix["name"] for ix in inspector.get_indexes("room_movement_groups")} if inspector.has_table("room_movement_groups") else set()):
        op.create_index("ix_room_movement_groups_hotel_id", "room_movement_groups", ["hotel_id"])

    # ── 2. room_move_events: add movement_group_id FK ────────────────────────
    room_move_events_columns = {c["name"] for c in inspector.get_columns("room_move_events")}
    room_move_events_fks = {fk["name"] for fk in inspector.get_foreign_keys("room_move_events")}
    room_move_events_indexes = {ix["name"] for ix in inspector.get_indexes("room_move_events")}
    with op.batch_alter_table("room_move_events") as batch_op:
        if "movement_group_id" not in room_move_events_columns:
            batch_op.add_column(
                sa.Column("movement_group_id", sa.Integer, nullable=True)
            )
        if "fk_room_move_events_movement_group_id" not in room_move_events_fks:
            batch_op.create_foreign_key(
                "fk_room_move_events_movement_group_id",
                "room_movement_groups",
                ["movement_group_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "ix_room_move_events_group_id" not in room_move_events_indexes:
            batch_op.create_index("ix_room_move_events_group_id", ["movement_group_id"])

    # ── 3. billing_adjustments: Float → Numeric(12,2) ────────────────────────
    with op.batch_alter_table("billing_adjustments") as batch_op:
        batch_op.alter_column("amount", type_=sa.Numeric(12, 2), existing_type=sa.Float)
        batch_op.alter_column("tax_amount", type_=sa.Numeric(12, 2), existing_type=sa.Float,
                              existing_nullable=True)
        batch_op.alter_column("total_amount", type_=sa.Numeric(12, 2), existing_type=sa.Float)

    # ── 4. reservation_adjustments: amount_delta Float → Numeric(12,2) ───────
    with op.batch_alter_table("reservation_adjustments") as batch_op:
        batch_op.alter_column("amount_delta", type_=sa.Numeric(12, 2), existing_type=sa.Float,
                              existing_nullable=True)

    # ── 5. rooms: add description field (v72 §4.6) ───────────────────────────
    rooms_columns = {c["name"] for c in inspector.get_columns("rooms")}
    with op.batch_alter_table("rooms") as batch_op:
        if "description" not in rooms_columns:
            batch_op.add_column(sa.Column("description", sa.Text, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("rooms") as batch_op:
        batch_op.drop_column("description")

    with op.batch_alter_table("reservation_adjustments") as batch_op:
        batch_op.alter_column("amount_delta", type_=sa.Float, existing_type=sa.Numeric(12, 2),
                              existing_nullable=True)

    with op.batch_alter_table("billing_adjustments") as batch_op:
        batch_op.alter_column("total_amount", type_=sa.Float, existing_type=sa.Numeric(12, 2))
        batch_op.alter_column("tax_amount", type_=sa.Float, existing_type=sa.Numeric(12, 2),
                              existing_nullable=True)
        batch_op.alter_column("amount", type_=sa.Float, existing_type=sa.Numeric(12, 2))

    with op.batch_alter_table("room_move_events") as batch_op:
        batch_op.drop_index("ix_room_move_events_group_id")
        batch_op.drop_constraint("fk_room_move_events_movement_group_id", type_="foreignkey")
        batch_op.drop_column("movement_group_id")

    op.drop_index("ix_room_movement_groups_hotel_id", table_name="room_movement_groups")
    op.drop_table("room_movement_groups")
