"""linen (ropa blanca) split into its own physical tables

Revision ID: 20260727_linen_split
Revises: 513720cf2551
Create Date: 2026-07-27 21:00:00.000000

The owner explicitly rejected a previous loop's ``StockItem.kind`` flag
('supply' vs 'linen') on the shared stock_items/stock_locations/
stock_movements tables: "no son lo mismo, son totalmente separados...
dos tablas separadas, dos datos distintos." This migration:

1. Creates linen_items / linen_locations / linen_movements -- same shape as
   their stock_* counterparts (see app/models/linen.py), but physically
   separate tables.
2. Migrates data: every stock_items row with kind='linen' (and its
   movements) moves to the new tables, reusing the same id so every
   downstream FK rewrite below is a simple lookup. Any StockLocation used by
   a migrated linen movement (or a LaundryVendor's own location) is copied
   into linen_locations too -- reusing its id when the location is
   exclusive to linen (and then deleting it from stock_locations, since
   nothing else needs it there), or getting an independent new id when the
   same physical location is still used by a general-supply movement (kept
   in stock_locations for that -- see the ``shared_location_ids`` guard).
3. Repoints laundry_vendors.stock_location_id -> linen_location_id,
   laundry_vendor_prices.stock_item_id -> linen_item_id and
   laundry_remito_lines.stock_item_id -> linen_item_id to the new ids.
4. Deletes the migrated rows from stock_items/stock_locations/
   stock_movements (already copied above) inside the same transaction.
5. Drops stock_items.kind: everything left in stock_items is 'supply' by
   definition once every 'linen' row has moved out.

Also adds StockItem.unit_cost (owner: "quiero que se pueda poner en las
cosas de stock... el costo por unidad") -- unrelated to the split itself,
but a cheap single-column addition bundled here since it touches the same
table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260727_linen_split"
down_revision: Union[str, None] = "513720cf2551"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    _create_linen_tables(dialect)
    op.add_column("stock_items", sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True))

    # New FK columns start nullable so the data migration below can populate
    # them before they are tightened to NOT NULL and get their real
    # constraints in _finalize_laundry_vendor_columns.
    op.add_column("laundry_vendors", sa.Column("linen_location_id", sa.Integer(), nullable=True))
    op.add_column("laundry_vendor_prices", sa.Column("linen_item_id", sa.Integer(), nullable=True))
    op.add_column("laundry_remito_lines", sa.Column("linen_item_id", sa.Integer(), nullable=True))

    _migrate_linen_data(bind, dialect)

    _drop_kind_column(dialect)

    if dialect == "postgresql":
        for table_name in ("linen_items", "linen_locations", "linen_movements"):
            op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
            policy_exists = bind.execute(
                sa.text(
                    "SELECT 1 FROM pg_policies WHERE tablename = :table_name AND policyname = :policy_name"
                ),
                {"table_name": table_name, "policy_name": f"tenant_isolation_{table_name}"},
            ).first()
            if not policy_exists:
                op.execute(
                    f'''CREATE POLICY "tenant_isolation_{table_name}" ON "{table_name}"
                        USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
                        WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
                )


def _create_linen_tables(dialect: str) -> None:
    op.create_table(
        "linen_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("min_quantity", sa.Numeric(12, 2), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], name="fk_linen_items_hotel_id"),
        sa.ForeignKeyConstraint(
            ["deleted_by_user_id"], ["users.id"], name="fk_linen_items_deleted_by_user_id", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_linen_items"),
        sa.UniqueConstraint("hotel_id", "id", name="uq_linen_items_hotel_id_id"),
    )
    op.create_index("ix_linen_items_hotel_id", "linen_items", ["hotel_id"], unique=False)
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_linen_items_hotel_name_active ON linen_items (hotel_id, name) "
            "WHERE deleted_at IS NULL"
        )
    )

    op.create_table(
        "linen_locations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], name="fk_linen_locations_hotel_id"),
        sa.ForeignKeyConstraint(
            ["deleted_by_user_id"], ["users.id"], name="fk_linen_locations_deleted_by_user_id", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_linen_locations"),
        sa.UniqueConstraint("hotel_id", "id", name="uq_linen_locations_hotel_id_id"),
    )
    op.create_index("ix_linen_locations_hotel_id", "linen_locations", ["hotel_id"], unique=False)
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_linen_locations_hotel_name_active ON linen_locations (hotel_id, name) "
            "WHERE deleted_at IS NULL"
        )
    )

    op.create_table(
        "linen_movements",
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
        sa.CheckConstraint(
            "movement_type IN ('in', 'out', 'adjustment', 'adjustment_out')", name="ck_linen_movements_type_valid"
        ),
        sa.CheckConstraint("quantity > 0", name="ck_linen_movements_quantity_positive"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], name="fk_linen_movements_hotel_id"),
        sa.ForeignKeyConstraint(
            ["hotel_id", "item_id"], ["linen_items.hotel_id", "linen_items.id"],
            name="fk_linen_movements_hotel_item", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "location_id"], ["linen_locations.hotel_id", "linen_locations.id"],
            name="fk_linen_movements_hotel_location",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "reservation_id"], ["reservations.hotel_id", "reservations.id"],
            name="fk_linen_movements_hotel_reservation",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name="fk_linen_movements_created_by_user_id", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_linen_movements"),
    )
    op.create_index("ix_linen_movements_hotel_id", "linen_movements", ["hotel_id"], unique=False)


def _migrate_linen_data(bind, dialect: str) -> None:
    metadata = sa.MetaData()
    stock_items_t = sa.Table("stock_items", metadata, autoload_with=bind)
    stock_locations_t = sa.Table("stock_locations", metadata, autoload_with=bind)
    stock_movements_t = sa.Table("stock_movements", metadata, autoload_with=bind)
    laundry_vendors_t = sa.Table("laundry_vendors", metadata, autoload_with=bind)
    laundry_vendor_prices_t = sa.Table("laundry_vendor_prices", metadata, autoload_with=bind)
    laundry_remito_lines_t = sa.Table("laundry_remito_lines", metadata, autoload_with=bind)
    linen_items_t = sa.Table("linen_items", metadata, autoload_with=bind)
    linen_locations_t = sa.Table("linen_locations", metadata, autoload_with=bind)
    linen_movements_t = sa.Table("linen_movements", metadata, autoload_with=bind)

    linen_item_rows = bind.execute(
        sa.select(stock_items_t).where(stock_items_t.c.kind == "linen")
    ).mappings().all()

    # Even with no linen items, laundry_vendors.linen_location_id must still
    # end up NOT NULL -- but with zero rows in the table the UPDATE below is
    # a no-op either way, so the "nothing to migrate" fast path is safe.
    if linen_item_rows:
        # --- 1. Items: reuse the same id so every FK rewrite below is a
        # plain identity lookup. --------------------------------------------
        bind.execute(
            linen_items_t.insert(),
            [
                {
                    "id": row["id"],
                    "hotel_id": row["hotel_id"],
                    "name": row["name"],
                    "unit": row["unit"],
                    "min_quantity": row["min_quantity"],
                    "active": row["active"],
                    "deleted_at": row["deleted_at"],
                    "deleted_by_user_id": row["deleted_by_user_id"],
                }
                for row in linen_item_rows
            ],
        )
        linen_item_ids = {row["id"] for row in linen_item_rows}

        # --- 2. Locations referenced by a migrated item's movements, or by
        # a LaundryVendor's own location. -------------------------------
        vendor_location_ids = {
            row[0] for row in bind.execute(sa.select(laundry_vendors_t.c.stock_location_id))
        }
        movement_location_ids = {
            row[0]
            for row in bind.execute(
                sa.select(stock_movements_t.c.location_id)
                .where(stock_movements_t.c.item_id.in_(linen_item_ids))
                .where(stock_movements_t.c.location_id.isnot(None))
                .distinct()
            )
        }
        all_location_ids = vendor_location_ids | movement_location_ids

        shared_location_ids: set[int] = set()
        location_id_map: dict[int, int] = {}
        if all_location_ids:
            # A location is "shared" if a *non*-linen item's movement also
            # uses it -- that row must stay in stock_locations (general
            # stock still needs it), so linen gets an independent copy
            # instead of taking over the same id.
            shared_location_ids = {
                row[0]
                for row in bind.execute(
                    sa.select(stock_movements_t.c.location_id)
                    .select_from(
                        stock_movements_t.join(stock_items_t, stock_items_t.c.id == stock_movements_t.c.item_id)
                    )
                    .where(stock_movements_t.c.location_id.in_(all_location_ids))
                    .where(stock_items_t.c.kind != "linen")
                    .distinct()
                )
            }

            location_rows = bind.execute(
                sa.select(stock_locations_t).where(stock_locations_t.c.id.in_(all_location_ids))
            ).mappings().all()
            for row in location_rows:
                old_id = row["id"]
                payload = {
                    "hotel_id": row["hotel_id"],
                    "name": row["name"],
                    "deleted_at": row["deleted_at"],
                    "deleted_by_user_id": row["deleted_by_user_id"],
                }
                if old_id in shared_location_ids:
                    result = bind.execute(linen_locations_t.insert(), payload)
                    location_id_map[old_id] = result.inserted_primary_key[0]
                else:
                    bind.execute(linen_locations_t.insert(), {"id": old_id, **payload})
                    location_id_map[old_id] = old_id

        # --- 3. Movements: every StockMovement belonging to a migrated
        # linen item. ------------------------------------------------------
        movement_rows = bind.execute(
            sa.select(stock_movements_t).where(stock_movements_t.c.item_id.in_(linen_item_ids))
        ).mappings().all()
        if movement_rows:
            bind.execute(
                linen_movements_t.insert(),
                [
                    {
                        "hotel_id": row["hotel_id"],
                        "item_id": row["item_id"],
                        "location_id": (
                            location_id_map.get(row["location_id"]) if row["location_id"] is not None else None
                        ),
                        "movement_type": row["movement_type"],
                        "quantity": row["quantity"],
                        "reason": row["reason"],
                        "reservation_id": row["reservation_id"],
                        "created_by_user_id": row["created_by_user_id"],
                        "created_at": row["created_at"],
                    }
                    for row in movement_rows
                ],
            )

        # --- 4. Repoint laundry_vendors/laundry_vendor_prices/
        # laundry_remito_lines at the new ids. -------------------------------
        for row in bind.execute(
            sa.select(laundry_vendors_t.c.id, laundry_vendors_t.c.stock_location_id)
        ).mappings().all():
            new_location_id = location_id_map.get(row["stock_location_id"], row["stock_location_id"])
            bind.execute(
                laundry_vendors_t.update()
                .where(laundry_vendors_t.c.id == row["id"])
                .values(linen_location_id=new_location_id)
            )
        bind.execute(
            laundry_vendor_prices_t.update().values(linen_item_id=laundry_vendor_prices_t.c.stock_item_id)
        )
        bind.execute(
            laundry_remito_lines_t.update().values(linen_item_id=laundry_remito_lines_t.c.stock_item_id)
        )

        # --- 4b. Finalize laundry_vendors/laundry_vendor_prices/
        # laundry_remito_lines BEFORE deleting anything below: production
        # incident 2026-07-28 -- this used to run after step 5, so the *old*
        # stock_location_id/stock_item_id FK constraints (still pointing at
        # stock_locations/stock_items) were still live when step 5 tried to
        # delete a row a real laundry_vendors/laundry_vendor_prices row still
        # referenced, and Postgres correctly rejected it with
        # ForeignKeyViolation. Finalizing here drops those old columns (and
        # their FKs) together with the data copy, so by the time step 5 runs
        # nothing old-side references the rows being deleted. SQLite doesn't
        # enforce FKs by default, which is why this never failed locally.
        _finalize_laundry_vendor_columns(dialect)

        # --- 5. Delete migrated rows: movements first (FK), then
        # linen-exclusive locations, then the items. Shared locations and
        # non-linen items/movements are left untouched in stock_*. ----------
        bind.execute(stock_movements_t.delete().where(stock_movements_t.c.item_id.in_(linen_item_ids)))
        exclusive_location_ids = all_location_ids - shared_location_ids
        if exclusive_location_ids:
            bind.execute(stock_locations_t.delete().where(stock_locations_t.c.id.in_(exclusive_location_ids)))
        bind.execute(stock_items_t.delete().where(stock_items_t.c.id.in_(linen_item_ids)))
    else:
        # No linen rows to migrate, but a hotel may still have laundry
        # vendors already pointing at a (non-linen) StockLocation from an
        # earlier loop -- keep the identity mapping consistent so the
        # NOT NULL tightening below never trips on a real row.
        for row in bind.execute(
            sa.select(laundry_vendors_t.c.id, laundry_vendors_t.c.stock_location_id)
        ).mappings().all():
            bind.execute(
                laundry_vendors_t.update()
                .where(laundry_vendors_t.c.id == row["id"])
                .values(linen_location_id=row["stock_location_id"])
            )
        bind.execute(
            laundry_vendor_prices_t.update().values(linen_item_id=laundry_vendor_prices_t.c.stock_item_id)
        )
        bind.execute(
            laundry_remito_lines_t.update().values(linen_item_id=laundry_remito_lines_t.c.stock_item_id)
        )
        _finalize_laundry_vendor_columns(dialect)


def _finalize_laundry_vendor_columns(dialect: str) -> None:
    if dialect == "postgresql":
        op.execute('ALTER TABLE "laundry_vendors" DROP CONSTRAINT IF EXISTS fk_laundry_vendors_hotel_stock_location')
        op.execute('ALTER TABLE "laundry_vendors" ALTER COLUMN linen_location_id SET NOT NULL')
        op.execute('ALTER TABLE "laundry_vendors" DROP COLUMN stock_location_id')
        op.create_foreign_key(
            "fk_laundry_vendors_hotel_linen_location", "laundry_vendors", "linen_locations",
            ["hotel_id", "linen_location_id"], ["hotel_id", "id"],
        )

        op.execute(
            'ALTER TABLE "laundry_vendor_prices" DROP CONSTRAINT IF EXISTS fk_laundry_vendor_prices_hotel_stock_item'
        )
        op.execute('ALTER TABLE "laundry_vendor_prices" DROP CONSTRAINT IF EXISTS uq_laundry_vendor_prices_vendor_item')
        op.execute('ALTER TABLE "laundry_vendor_prices" ALTER COLUMN linen_item_id SET NOT NULL')
        op.execute('ALTER TABLE "laundry_vendor_prices" DROP COLUMN stock_item_id')
        op.create_foreign_key(
            "fk_laundry_vendor_prices_hotel_linen_item", "laundry_vendor_prices", "linen_items",
            ["hotel_id", "linen_item_id"], ["hotel_id", "id"],
        )
        op.create_unique_constraint(
            "uq_laundry_vendor_prices_vendor_item", "laundry_vendor_prices", ["vendor_id", "linen_item_id"]
        )

        op.execute(
            'ALTER TABLE "laundry_remito_lines" DROP CONSTRAINT IF EXISTS fk_laundry_remito_lines_hotel_stock_item'
        )
        op.execute('ALTER TABLE "laundry_remito_lines" ALTER COLUMN linen_item_id SET NOT NULL')
        op.execute('ALTER TABLE "laundry_remito_lines" DROP COLUMN stock_item_id')
        op.create_foreign_key(
            "fk_laundry_remito_lines_hotel_linen_item", "laundry_remito_lines", "linen_items",
            ["hotel_id", "linen_item_id"], ["hotel_id", "id"],
        )
        return

    # SQLite: batch_alter_table (table rebuild) is required to drop a
    # column or a named constraint -- same pattern used throughout this
    # repo's other SQLite-targeting migrations (see 20260727_stock_kind_fix).
    with op.batch_alter_table("laundry_vendors", recreate="always") as batch_op:
        batch_op.drop_column("stock_location_id")
        batch_op.alter_column("linen_location_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_laundry_vendors_hotel_linen_location", "linen_locations",
            ["hotel_id", "linen_location_id"], ["hotel_id", "id"],
        )

    with op.batch_alter_table("laundry_vendor_prices", recreate="always") as batch_op:
        batch_op.drop_column("stock_item_id")
        batch_op.alter_column("linen_item_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_laundry_vendor_prices_hotel_linen_item", "linen_items",
            ["hotel_id", "linen_item_id"], ["hotel_id", "id"],
        )
        batch_op.create_unique_constraint("uq_laundry_vendor_prices_vendor_item", ["vendor_id", "linen_item_id"])

    with op.batch_alter_table("laundry_remito_lines", recreate="always") as batch_op:
        batch_op.drop_column("stock_item_id")
        batch_op.alter_column("linen_item_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_laundry_remito_lines_hotel_linen_item", "linen_items",
            ["hotel_id", "linen_item_id"], ["hotel_id", "id"],
        )


def _drop_kind_column(dialect: str) -> None:
    if dialect == "postgresql":
        op.execute('ALTER TABLE "stock_items" DROP CONSTRAINT IF EXISTS ck_stock_items_kind_valid')
        op.drop_column("stock_items", "kind")
        return

    with op.batch_alter_table("stock_items", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_stock_items_kind_valid", type_="check")
        batch_op.drop_column("kind")


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        for table_name in ("linen_movements", "linen_locations", "linen_items"):
            op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{table_name}" ON "{table_name}"')
            op.execute(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY')

    if dialect == "sqlite":
        with op.batch_alter_table("stock_items", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("kind", sa.String(length=20), nullable=False, server_default="supply"))
            batch_op.create_check_constraint("ck_stock_items_kind_valid", "kind IN ('supply', 'linen')")
    else:
        op.add_column(
            "stock_items", sa.Column("kind", sa.String(length=20), nullable=False, server_default="supply")
        )
        op.create_check_constraint("ck_stock_items_kind_valid", "stock_items", "kind IN ('supply', 'linen')")

    # Restore the old stock_item_id/stock_location_id columns (nullable
    # first, so the reverse data copy below can populate them) before moving
    # linen data back into stock_items/stock_locations/stock_movements.
    op.add_column("laundry_vendors", sa.Column("stock_location_id", sa.Integer(), nullable=True))
    op.add_column("laundry_vendor_prices", sa.Column("stock_item_id", sa.Integer(), nullable=True))
    op.add_column("laundry_remito_lines", sa.Column("stock_item_id", sa.Integer(), nullable=True))

    _migrate_linen_data_back(bind)

    if dialect == "postgresql":
        op.execute('ALTER TABLE "laundry_vendors" DROP CONSTRAINT IF EXISTS fk_laundry_vendors_hotel_linen_location')
        op.execute('ALTER TABLE "laundry_vendors" ALTER COLUMN stock_location_id SET NOT NULL')
        op.execute('ALTER TABLE "laundry_vendors" DROP COLUMN linen_location_id')
        op.create_foreign_key(
            "fk_laundry_vendors_hotel_stock_location", "laundry_vendors", "stock_locations",
            ["hotel_id", "stock_location_id"], ["hotel_id", "id"],
        )

        op.execute(
            'ALTER TABLE "laundry_vendor_prices" DROP CONSTRAINT IF EXISTS fk_laundry_vendor_prices_hotel_linen_item'
        )
        op.execute('ALTER TABLE "laundry_vendor_prices" DROP CONSTRAINT IF EXISTS uq_laundry_vendor_prices_vendor_item')
        op.execute('ALTER TABLE "laundry_vendor_prices" ALTER COLUMN stock_item_id SET NOT NULL')
        op.execute('ALTER TABLE "laundry_vendor_prices" DROP COLUMN linen_item_id')
        op.create_foreign_key(
            "fk_laundry_vendor_prices_hotel_stock_item", "laundry_vendor_prices", "stock_items",
            ["hotel_id", "stock_item_id"], ["hotel_id", "id"],
        )
        op.create_unique_constraint(
            "uq_laundry_vendor_prices_vendor_item", "laundry_vendor_prices", ["vendor_id", "stock_item_id"]
        )

        op.execute(
            'ALTER TABLE "laundry_remito_lines" DROP CONSTRAINT IF EXISTS fk_laundry_remito_lines_hotel_linen_item'
        )
        op.execute('ALTER TABLE "laundry_remito_lines" ALTER COLUMN stock_item_id SET NOT NULL')
        op.execute('ALTER TABLE "laundry_remito_lines" DROP COLUMN linen_item_id')
        op.create_foreign_key(
            "fk_laundry_remito_lines_hotel_stock_item", "laundry_remito_lines", "stock_items",
            ["hotel_id", "stock_item_id"], ["hotel_id", "id"],
        )
    else:
        with op.batch_alter_table("laundry_vendors", recreate="always") as batch_op:
            batch_op.drop_column("linen_location_id")
            batch_op.alter_column("stock_location_id", nullable=False)
            batch_op.create_foreign_key(
                "fk_laundry_vendors_hotel_stock_location", "stock_locations",
                ["hotel_id", "stock_location_id"], ["hotel_id", "id"],
            )

        with op.batch_alter_table("laundry_vendor_prices", recreate="always") as batch_op:
            batch_op.drop_column("linen_item_id")
            batch_op.alter_column("stock_item_id", nullable=False)
            batch_op.create_foreign_key(
                "fk_laundry_vendor_prices_hotel_stock_item", "stock_items",
                ["hotel_id", "stock_item_id"], ["hotel_id", "id"],
            )
            batch_op.create_unique_constraint("uq_laundry_vendor_prices_vendor_item", ["vendor_id", "stock_item_id"])

        with op.batch_alter_table("laundry_remito_lines", recreate="always") as batch_op:
            batch_op.drop_column("linen_item_id")
            batch_op.alter_column("stock_item_id", nullable=False)
            batch_op.create_foreign_key(
                "fk_laundry_remito_lines_hotel_stock_item", "stock_items",
                ["hotel_id", "stock_item_id"], ["hotel_id", "id"],
            )

    op.drop_column("stock_items", "unit_cost")

    op.drop_index("ix_linen_movements_hotel_id", table_name="linen_movements")
    op.drop_table("linen_movements")

    op.drop_index("ix_linen_locations_hotel_id", table_name="linen_locations")
    op.execute(sa.text("DROP INDEX IF EXISTS uq_linen_locations_hotel_name_active"))
    op.drop_table("linen_locations")

    op.drop_index("ix_linen_items_hotel_id", table_name="linen_items")
    op.execute(sa.text("DROP INDEX IF EXISTS uq_linen_items_hotel_name_active"))
    op.drop_table("linen_items")


def _migrate_linen_data_back(bind) -> None:
    """Reverse of _migrate_linen_data: every linen_items row moves back into
    stock_items with kind='linen', same id, along with its locations and
    movements -- the mirror image, used by the downgrade path."""
    metadata = sa.MetaData()
    stock_items_t = sa.Table("stock_items", metadata, autoload_with=bind)
    stock_locations_t = sa.Table("stock_locations", metadata, autoload_with=bind)
    stock_movements_t = sa.Table("stock_movements", metadata, autoload_with=bind)
    laundry_vendors_t = sa.Table("laundry_vendors", metadata, autoload_with=bind)
    laundry_vendor_prices_t = sa.Table("laundry_vendor_prices", metadata, autoload_with=bind)
    laundry_remito_lines_t = sa.Table("laundry_remito_lines", metadata, autoload_with=bind)
    linen_items_t = sa.Table("linen_items", metadata, autoload_with=bind)
    linen_locations_t = sa.Table("linen_locations", metadata, autoload_with=bind)
    linen_movements_t = sa.Table("linen_movements", metadata, autoload_with=bind)

    linen_item_rows = bind.execute(sa.select(linen_items_t)).mappings().all()
    if linen_item_rows:
        bind.execute(
            stock_items_t.insert(),
            [
                {
                    "id": row["id"],
                    "hotel_id": row["hotel_id"],
                    "name": row["name"],
                    "sku": None,
                    "unit": row["unit"],
                    "min_quantity": row["min_quantity"],
                    "active": row["active"],
                    "unit_cost": None,
                    "kind": "linen",
                    "deleted_at": row["deleted_at"],
                    "deleted_by_user_id": row["deleted_by_user_id"],
                }
                for row in linen_item_rows
            ],
        )

        location_rows = bind.execute(sa.select(linen_locations_t)).mappings().all()
        location_id_map: dict[int, int] = {}
        for row in location_rows:
            old_id = row["id"]
            # A "shared" location's stock_locations row was never deleted by
            # the upgrade (a general-supply movement still used it) -- reuse
            # that live row instead of violating the soft-delete-aware
            # per-hotel name uniqueness by inserting a duplicate.
            existing_shared = bind.execute(
                sa.select(stock_locations_t.c.id)
                .where(stock_locations_t.c.hotel_id == row["hotel_id"])
                .where(stock_locations_t.c.name == row["name"])
                .where(stock_locations_t.c.deleted_at.is_(None))
            ).first()
            if existing_shared is not None:
                location_id_map[old_id] = existing_shared[0]
                continue
            payload = {
                "hotel_id": row["hotel_id"],
                "name": row["name"],
                "deleted_at": row["deleted_at"],
                "deleted_by_user_id": row["deleted_by_user_id"],
            }
            result = bind.execute(stock_locations_t.insert(), payload)
            location_id_map[old_id] = result.inserted_primary_key[0]

        movement_rows = bind.execute(sa.select(linen_movements_t)).mappings().all()
        if movement_rows:
            bind.execute(
                stock_movements_t.insert(),
                [
                    {
                        "hotel_id": row["hotel_id"],
                        "item_id": row["item_id"],
                        "location_id": (
                            location_id_map.get(row["location_id"]) if row["location_id"] is not None else None
                        ),
                        "movement_type": row["movement_type"],
                        "quantity": row["quantity"],
                        "reason": row["reason"],
                        "reservation_id": row["reservation_id"],
                        "created_by_user_id": row["created_by_user_id"],
                        "created_at": row["created_at"],
                    }
                    for row in movement_rows
                ],
            )

        for row in bind.execute(
            sa.select(laundry_vendors_t.c.id, laundry_vendors_t.c.linen_location_id)
        ).mappings().all():
            new_location_id = location_id_map.get(row["linen_location_id"], row["linen_location_id"])
            bind.execute(
                laundry_vendors_t.update()
                .where(laundry_vendors_t.c.id == row["id"])
                .values(stock_location_id=new_location_id)
            )
    else:
        for row in bind.execute(
            sa.select(laundry_vendors_t.c.id, laundry_vendors_t.c.linen_location_id)
        ).mappings().all():
            bind.execute(
                laundry_vendors_t.update()
                .where(laundry_vendors_t.c.id == row["id"])
                .values(stock_location_id=row["linen_location_id"])
            )

    bind.execute(
        laundry_vendor_prices_t.update().values(stock_item_id=laundry_vendor_prices_t.c.linen_item_id)
    )
    bind.execute(
        laundry_remito_lines_t.update().values(stock_item_id=laundry_remito_lines_t.c.linen_item_id)
    )
