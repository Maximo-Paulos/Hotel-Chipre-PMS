"""stock_items.kind (supply vs linen) + soft-delete-aware name uniqueness

Revision ID: 20260727_stock_kind_fix
Revises: f3bdaadd3d15
Create Date: 2026-07-27 00:00:00.000000

Two related fixes surfaced while investigating the owner's report "no puedo
eliminar productos de stock":

1. ``uq_stock_items_hotel_name`` / ``uq_stock_locations_hotel_name`` were
   plain (not soft-delete-aware) unique constraints. Deleting an item is a
   soft delete (``deleted_at`` set, row kept for audit -- see
   app/services/stock_service.py delete_stock_item), so the name stayed
   permanently reserved. Reproduced directly: delete an item, try to create
   a new one with the same name (e.g. replacing a discontinued product) ->
   unhandled IntegrityError -> 500. From the owner's side this looks exactly
   like "I can't manage my stock products". Fixed by converting both unique
   constraints into partial unique indexes that only apply to
   ``deleted_at IS NULL`` rows.

2. Adds ``stock_items.kind`` ('supply' default vs 'linen') so StockPage
   (general supplies: bolsas, detergentes, jabon) and LaundryPage (ropa
   blanca) can each list/create their own items instead of sharing one
   undifferentiated list -- see app/api/stock.py list_items(kind=). Backfills
   'linen' for every stock item already referenced by
   laundry_vendor_prices.stock_item_id (the only existing signal that an item
   is linen, not a general supply).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260727_stock_kind_fix"
down_revision: Union[str, None] = "f3bdaadd3d15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # --- 1. kind column -----------------------------------------------
    if dialect == "sqlite":
        with op.batch_alter_table("stock_items", recreate="always") as batch_op:
            batch_op.add_column(
                sa.Column("kind", sa.String(length=20), nullable=False, server_default="supply")
            )
            batch_op.create_check_constraint(
                "ck_stock_items_kind_valid", "kind IN ('supply', 'linen')"
            )
    else:
        op.add_column(
            "stock_items",
            sa.Column("kind", sa.String(length=20), nullable=False, server_default="supply"),
        )
        op.create_check_constraint(
            "ck_stock_items_kind_valid", "stock_items", "kind IN ('supply', 'linen')"
        )
    # Data migration: anything already used as a laundry vendor price line is
    # linen, not a general supply.
    op.execute(
        sa.text(
            "UPDATE stock_items SET kind = 'linen' "
            "WHERE id IN (SELECT DISTINCT stock_item_id FROM laundry_vendor_prices)"
        )
    )

    # --- 2. soft-delete-aware uniqueness --------------------------------
    for table, column, old_constraint, new_index in (
        ("stock_items", "name", "uq_stock_items_hotel_name", "uq_stock_items_hotel_name_active"),
        ("stock_locations", "name", "uq_stock_locations_hotel_name", "uq_stock_locations_hotel_name_active"),
    ):
        if dialect == "postgresql":
            bind.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {old_constraint}"))
            bind.execute(
                sa.text(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS {new_index} ON {table} "
                    f"(hotel_id, {column}) WHERE deleted_at IS NULL"
                )
            )
        else:
            inspector = sa.inspect(bind)
            existing = {uc["name"] for uc in inspector.get_unique_constraints(table)}
            if old_constraint in existing:
                with op.batch_alter_table(table, recreate="always") as batch_op:
                    batch_op.drop_constraint(old_constraint, type_="unique")
            bind.execute(
                sa.text(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS {new_index} ON {table} "
                    f"(hotel_id, {column}) WHERE deleted_at IS NULL"
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    for table, column, old_constraint, new_index in (
        ("stock_items", "name", "uq_stock_items_hotel_name", "uq_stock_items_hotel_name_active"),
        ("stock_locations", "name", "uq_stock_locations_hotel_name", "uq_stock_locations_hotel_name_active"),
    ):
        bind.execute(sa.text(f"DROP INDEX IF EXISTS {new_index}"))
        if dialect == "postgresql":
            bind.execute(
                sa.text(f"ALTER TABLE {table} ADD CONSTRAINT {old_constraint} UNIQUE (hotel_id, {column})")
            )
        else:
            with op.batch_alter_table(table, recreate="always") as batch_op:
                batch_op.create_unique_constraint(old_constraint, ["hotel_id", column])

    if dialect == "sqlite":
        with op.batch_alter_table("stock_items", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_stock_items_kind_valid", type_="check")
            batch_op.drop_column("kind")
    else:
        op.drop_constraint("ck_stock_items_kind_valid", "stock_items", type_="check")
        op.drop_column("stock_items", "kind")
