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


def upgrade() -> None:
    # Add hotel_id columns (nullable during migration)
    op.add_column("room_categories", sa.Column("hotel_id", sa.Integer(), nullable=True))
    op.add_column("rooms", sa.Column("hotel_id", sa.Integer(), nullable=True))
    op.add_column("reservations", sa.Column("hotel_id", sa.Integer(), nullable=True))

    # Populate legacy data with hotel_id = 1
    op.execute("UPDATE room_categories SET hotel_id = 1 WHERE hotel_id IS NULL")
    op.execute("UPDATE rooms SET hotel_id = 1 WHERE hotel_id IS NULL")
    op.execute("UPDATE reservations SET hotel_id = 1 WHERE hotel_id IS NULL")

    # Drop old unique constraints to recreate scoped by hotel
    op.drop_constraint("room_categories_code_key", "room_categories", type_="unique")
    op.drop_constraint("room_categories_name_key", "room_categories", type_="unique")
    op.drop_constraint("rooms_room_number_key", "rooms", type_="unique")

    # Make columns NOT NULL and add FKs
    op.alter_column("room_categories", "hotel_id", nullable=False)
    op.alter_column("rooms", "hotel_id", nullable=False)
    op.alter_column("reservations", "hotel_id", nullable=False)

    op.create_foreign_key(None, "room_categories", "hotel_configuration", ["hotel_id"], ["id"])
    op.create_foreign_key(None, "rooms", "hotel_configuration", ["hotel_id"], ["id"])
    op.create_foreign_key(None, "reservations", "hotel_configuration", ["hotel_id"], ["id"])

    # Scoped unique constraints
    op.create_unique_constraint(
        "uq_room_category_code_hotel", "room_categories", ["hotel_id", "code"]
    )
    op.create_unique_constraint(
        "uq_room_category_name_hotel", "room_categories", ["hotel_id", "name"]
    )
    op.create_unique_constraint("uq_room_number_hotel", "rooms", ["hotel_id", "room_number"])

    # Index for reservation filtering by hotel
    op.create_index("ix_reservations_hotel_id", "reservations", ["hotel_id"])
    op.create_index("ix_room_hotel_id", "rooms", ["hotel_id"])
    op.create_index("ix_room_category_hotel_id", "room_categories", ["hotel_id"])


def downgrade() -> None:
    op.drop_index("ix_room_category_hotel_id", table_name="room_categories")
    op.drop_index("ix_room_hotel_id", table_name="rooms")
    op.drop_index("ix_reservations_hotel_id", table_name="reservations")
    op.drop_constraint("uq_room_number_hotel", "rooms", type_="unique")
    op.drop_constraint("uq_room_category_name_hotel", "room_categories", type_="unique")
    op.drop_constraint("uq_room_category_code_hotel", "room_categories", type_="unique")

    op.drop_constraint(None, "reservations", type_="foreignkey")
    op.drop_constraint(None, "rooms", type_="foreignkey")
    op.drop_constraint(None, "room_categories", type_="foreignkey")

    op.alter_column("reservations", "hotel_id", nullable=True)
    op.alter_column("rooms", "hotel_id", nullable=True)
    op.alter_column("room_categories", "hotel_id", nullable=True)

    op.drop_column("reservations", "hotel_id")
    op.drop_column("rooms", "hotel_id")
    op.drop_column("room_categories", "hotel_id")

    # Restore old uniques
    op.create_unique_constraint("rooms_room_number_key", "rooms", ["room_number"])
    op.create_unique_constraint("room_categories_name_key", "room_categories", ["name"])
    op.create_unique_constraint("room_categories_code_key", "room_categories", ["code"])
