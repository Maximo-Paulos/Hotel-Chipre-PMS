"""repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist

Revision ID: 890876b925a7
Revises: 795e124adaad
Create Date: 2026-07-25 21:39:47.229420

Both StockItem and StockLocation models declare a ``(hotel_id, id)`` unique
constraint (app/models/stock.py), but no prior migration ever actually
created it in the database -- only ``Base.metadata.create_all()`` (used by
the pytest harness, not by any real deploy) builds it from the model. D1's
795e124adaad migration adds composite ``(hotel_id, stock_item_id)`` /
``(hotel_id, stock_location_id)`` foreign keys from the new laundry tables to
these two, which SQLite (and Postgres) require a matching unique index on the
referenced columns for -- without this repair, every real migrated database
(this project's E2E backend included, and production) raises "foreign key
mismatch" on the very first laundry vendor/price/remito insert. Same repair
pattern as 20260626_repair_reservation_unique_constraint.py; idempotent, safe
to run even where the constraint already happens to exist.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '890876b925a7'
down_revision: Union[str, None] = '795e124adaad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("stock_items", "stock_locations")


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    for table in _TABLES:
        constraint_name = f"uq_{table}_hotel_id_id"
        if dialect == "postgresql":
            bind.execute(sa.text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {constraint_name} ON {table} (hotel_id, id)"
            ))
        else:
            inspector = sa.inspect(bind)
            existing = {uc["name"] for uc in inspector.get_unique_constraints(table)}
            if constraint_name not in existing:
                with op.batch_alter_table(table, recreate="always") as batch_op:
                    batch_op.create_unique_constraint(constraint_name, ["hotel_id", "id"])


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    for table in _TABLES:
        constraint_name = f"uq_{table}_hotel_id_id"
        if dialect == "postgresql":
            # Only drop a bare index (the broken-deploy case this repairs).
            # If some other migration later turns this into a real
            # constraint, its own downgrade owns dropping it.
            bind.execute(sa.text(
                "DO $$\n"
                "BEGIN\n"
                f"    IF NOT EXISTS (\n"
                f"        SELECT 1 FROM pg_constraint WHERE conname = '{constraint_name}'\n"
                "    ) THEN\n"
                f"        EXECUTE 'DROP INDEX IF EXISTS {constraint_name}';\n"
                "    END IF;\n"
                "END $$;"
            ))
        else:
            with op.batch_alter_table(table, recreate="always") as batch_op:
                batch_op.drop_constraint(constraint_name, type_="unique")
