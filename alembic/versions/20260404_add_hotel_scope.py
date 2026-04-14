"""add hotel scope to core tables

Revision ID: 20260404_add_hotel_scope
Revises: cb9001557529
Create Date: 2026-04-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260404_add_hotel_scope"
down_revision: Union[str, None] = "cb9001557529"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


legacy_metadata = sa.MetaData()

room_categories_with_hotel = sa.Table(
    "room_categories",
    legacy_metadata,
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("name", sa.String(length=100), nullable=False),
    sa.Column("code", sa.String(length=20), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("base_price_per_night", sa.Float(), nullable=False),
    sa.Column("max_occupancy", sa.Integer(), nullable=False),
    sa.Column("amenities", sa.Text(), nullable=True),
    sa.Column("hotel_id", sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint("id"),
    sa.CheckConstraint("base_price_per_night > 0", name="ck_category_price_positive"),
    sa.CheckConstraint("max_occupancy > 0", name="ck_category_max_occ_positive"),
    sa.UniqueConstraint("code", name="room_categories_code_key"),
    sa.UniqueConstraint("name", name="room_categories_name_key"),
)

rooms_with_hotel = sa.Table(
    "rooms",
    legacy_metadata,
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("room_number", sa.String(length=10), nullable=False),
    sa.Column("floor", sa.Integer(), nullable=False),
    sa.Column("category_id", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(length=20), nullable=False),
    sa.Column("is_active", sa.Boolean(), nullable=False),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column("hotel_id", sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint("id"),
    sa.CheckConstraint("floor >= 0", name="ck_room_floor_positive"),
    sa.ForeignKeyConstraint(["category_id"], ["room_categories.id"]),
    sa.UniqueConstraint("room_number", name="rooms_room_number_key"),
)

reservations_with_hotel = sa.Table(
    "reservations",
    legacy_metadata,
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("confirmation_code", sa.String(length=30), nullable=False),
    sa.Column("guest_id", sa.Integer(), nullable=False),
    sa.Column("room_id", sa.Integer(), nullable=True),
    sa.Column("category_id", sa.Integer(), nullable=False),
    sa.Column("check_in_date", sa.Date(), nullable=False),
    sa.Column("check_out_date", sa.Date(), nullable=False),
    sa.Column("actual_check_in", sa.DateTime(), nullable=True),
    sa.Column("actual_check_out", sa.DateTime(), nullable=True),
    sa.Column("total_amount", sa.Float(), nullable=False),
    sa.Column("amount_paid", sa.Float(), nullable=False),
    sa.Column("deposit_amount", sa.Float(), nullable=False),
    sa.Column("status", sa.String(length=30), nullable=False),
    sa.Column("source", sa.String(length=30), nullable=False),
    sa.Column("external_id", sa.String(length=100), nullable=True),
    sa.Column("num_adults", sa.Integer(), nullable=False),
    sa.Column("num_children", sa.Integer(), nullable=False),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(), nullable=False),
    sa.Column("updated_at", sa.DateTime(), nullable=False),
    sa.Column("hotel_id", sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint("id"),
    sa.CheckConstraint("amount_paid >= 0", name="ck_reservation_paid_positive"),
    sa.CheckConstraint("check_out_date > check_in_date", name="ck_reservation_dates"),
    sa.CheckConstraint("num_adults > 0", name="ck_reservation_adults_positive"),
    sa.CheckConstraint("num_children >= 0", name="ck_reservation_children_positive"),
    sa.CheckConstraint("total_amount >= 0", name="ck_reservation_total_positive"),
    sa.ForeignKeyConstraint(["category_id"], ["room_categories.id"]),
    sa.ForeignKeyConstraint(["guest_id"], ["guests.id"]),
    sa.ForeignKeyConstraint(["room_id"], ["rooms.id"]),
)


def upgrade() -> None:
    op.add_column("room_categories", sa.Column("hotel_id", sa.Integer(), nullable=True))
    op.add_column("rooms", sa.Column("hotel_id", sa.Integer(), nullable=True))
    op.add_column("reservations", sa.Column("hotel_id", sa.Integer(), nullable=True))

    op.execute("UPDATE room_categories SET hotel_id = 1 WHERE hotel_id IS NULL")
    op.execute("UPDATE rooms SET hotel_id = 1 WHERE hotel_id IS NULL")
    op.execute("UPDATE reservations SET hotel_id = 1 WHERE hotel_id IS NULL")

    with op.batch_alter_table("room_categories", recreate="always", copy_from=room_categories_with_hotel) as batch_op:
        batch_op.alter_column("hotel_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_constraint("room_categories_code_key", type_="unique")
        batch_op.drop_constraint("room_categories_name_key", type_="unique")
        batch_op.create_foreign_key(
            "fk_room_categories_hotel_configuration",
            "hotel_configuration",
            ["hotel_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_room_category_code_hotel",
            ["hotel_id", "code"],
        )
        batch_op.create_unique_constraint(
            "uq_room_category_name_hotel",
            ["hotel_id", "name"],
        )
        batch_op.create_index("ix_room_category_hotel_id", ["hotel_id"], unique=False)

    with op.batch_alter_table("rooms", recreate="always", copy_from=rooms_with_hotel) as batch_op:
        batch_op.alter_column("hotel_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_constraint("rooms_room_number_key", type_="unique")
        batch_op.create_foreign_key(
            "fk_rooms_hotel_configuration",
            "hotel_configuration",
            ["hotel_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_room_number_hotel",
            ["hotel_id", "room_number"],
        )
        batch_op.create_index("ix_room_hotel_id", ["hotel_id"], unique=False)

    with op.batch_alter_table("reservations", recreate="always", copy_from=reservations_with_hotel) as batch_op:
        batch_op.alter_column("hotel_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_reservations_hotel_configuration",
            "hotel_configuration",
            ["hotel_id"],
            ["id"],
        )
        batch_op.create_index("ix_reservations_hotel_id", ["hotel_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("reservations", recreate="always", copy_from=reservations_with_hotel) as batch_op:
        batch_op.drop_index("ix_reservations_hotel_id")
        batch_op.drop_constraint("fk_reservations_hotel_configuration", type_="foreignkey")
        batch_op.alter_column("hotel_id", existing_type=sa.Integer(), nullable=True)

    with op.batch_alter_table("rooms", recreate="always", copy_from=rooms_with_hotel) as batch_op:
        batch_op.drop_index("ix_room_hotel_id")
        batch_op.drop_constraint("uq_room_number_hotel", type_="unique")
        batch_op.drop_constraint("fk_rooms_hotel_configuration", type_="foreignkey")
        batch_op.alter_column("hotel_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_unique_constraint("rooms_room_number_key", ["room_number"])

    with op.batch_alter_table("room_categories", recreate="always", copy_from=room_categories_with_hotel) as batch_op:
        batch_op.drop_index("ix_room_category_hotel_id")
        batch_op.drop_constraint("uq_room_category_name_hotel", type_="unique")
        batch_op.drop_constraint("uq_room_category_code_hotel", type_="unique")
        batch_op.drop_constraint("fk_room_categories_hotel_configuration", type_="foreignkey")
        batch_op.alter_column("hotel_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_unique_constraint("room_categories_name_key", ["name"])
        batch_op.create_unique_constraint("room_categories_code_key", ["code"])

    op.drop_column("reservations", "hotel_id")
    op.drop_column("rooms", "hotel_id")
    op.drop_column("room_categories", "hotel_id")
