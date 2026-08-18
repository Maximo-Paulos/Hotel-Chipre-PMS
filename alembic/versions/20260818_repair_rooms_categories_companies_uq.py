"""repair: ensure (hotel_id, id) unique constraints exist on rooms/room_categories/companies

Revision ID: 20260818_repair_room_company_uq
Revises: 20260818_promotions
Create Date: 2026-08-18

app/models/room.py, room.py (RoomCategory) and company.py all declare a
``(hotel_id, id)`` unique constraint, and 20260724_core_tenant_composite_fks
lists them in UNIQUE_TARGETS -- but that migration is intentionally
PostgreSQL-only ("SQLite remains a local test dialect whose schema is
created from the ORM metadata"). That assumption doesn't hold for this
repo's own local-dev tooling: scripts/seed_e2e_backend.py and the documented
dev-up flow both run `alembic upgrade head` against a real SQLite file, not
metadata.create_all(). Task 3's promotions table (20260818_promotions) is
the first migration to add real composite FKs to rooms/room_categories/
companies, which SQLite enforces at DML time via PRAGMA foreign_keys=ON --
exposing "foreign key mismatch" on the very first real insert. Same repair
pattern as 890876b925a7 (stock_items/stock_locations); idempotent, safe to
run even where the constraint already exists (e.g. real Postgres deploys).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260818_repair_room_company_uq"
down_revision: Union[str, None] = "20260818_promotions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TARGETS = (
    ("rooms", "uq_room_hotel_id_id"),
    ("room_categories", "uq_room_category_hotel_id_id"),
    ("companies", "uq_companies_hotel_id_id"),
)


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    for table, constraint_name in _TARGETS:
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

    for table, constraint_name in _TARGETS:
        if dialect == "postgresql":
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
