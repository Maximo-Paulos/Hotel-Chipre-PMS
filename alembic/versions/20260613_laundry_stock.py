"""laundry and stock foundations

Revision ID: 20260613_laundry_stock
Revises: 20260613_permissions
Create Date: 2026-06-13 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260613_laundry_stock"
down_revision: Union[str, None] = "20260613_permissions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "laundry_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("batch_code", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="collected", nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('collected', 'sent', 'received', 'closed')", name="ck_laundry_batches_status_valid"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_laundry_batches_created_by_user_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], name="fk_laundry_batches_hotel_id"),
        sa.PrimaryKeyConstraint("id", name="pk_laundry_batches"),
        sa.UniqueConstraint("hotel_id", "batch_code", name="uq_laundry_batches_hotel_batch_code"),
    )
    op.create_index("ix_laundry_batches_hotel_id", "laundry_batches", ["hotel_id"], unique=False)

    op.create_table(
        "stock_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("sku", sa.String(length=80), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("min_quantity", sa.Numeric(12, 2), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], name="fk_stock_items_hotel_id"),
        sa.PrimaryKeyConstraint("id", name="pk_stock_items"),
        sa.UniqueConstraint("hotel_id", "name", name="uq_stock_items_hotel_name"),
    )
    op.create_index("ix_stock_items_hotel_id", "stock_items", ["hotel_id"], unique=False)

    op.create_table(
        "stock_locations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], name="fk_stock_locations_hotel_id"),
        sa.PrimaryKeyConstraint("id", name="pk_stock_locations"),
        sa.UniqueConstraint("hotel_id", "name", name="uq_stock_locations_hotel_name"),
    )
    op.create_index("ix_stock_locations_hotel_id", "stock_locations", ["hotel_id"], unique=False)

    op.create_table(
        "laundry_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(length=100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_laundry_items_quantity_positive"),
        sa.ForeignKeyConstraint(["batch_id"], ["laundry_batches.id"], name="fk_laundry_items_batch_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], name="fk_laundry_items_hotel_id"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], name="fk_laundry_items_room_id", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_laundry_items"),
    )
    op.create_index("ix_laundry_items_hotel_id", "laundry_items", ["hotel_id"], unique=False)

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("movement_type", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reservation_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("movement_type IN ('in', 'out', 'adjustment')", name="ck_stock_movements_type_valid"),
        sa.CheckConstraint("quantity > 0", name="ck_stock_movements_quantity_positive"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_stock_movements_created_by_user_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], name="fk_stock_movements_hotel_id"),
        sa.ForeignKeyConstraint(["item_id"], ["stock_items.id"], name="fk_stock_movements_item_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["stock_locations.id"], name="fk_stock_movements_location_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], name="fk_stock_movements_reservation_id", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_stock_movements"),
    )
    op.create_index("ix_stock_movements_hotel_id", "stock_movements", ["hotel_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stock_movements_hotel_id", table_name="stock_movements")
    op.drop_table("stock_movements")

    op.drop_index("ix_laundry_items_hotel_id", table_name="laundry_items")
    op.drop_table("laundry_items")

    op.drop_index("ix_stock_locations_hotel_id", table_name="stock_locations")
    op.drop_table("stock_locations")

    op.drop_index("ix_stock_items_hotel_id", table_name="stock_items")
    op.drop_table("stock_items")

    op.drop_index("ix_laundry_batches_hotel_id", table_name="laundry_batches")
    op.drop_table("laundry_batches")
