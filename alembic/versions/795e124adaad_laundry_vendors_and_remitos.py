"""laundry vendors and remitos

Revision ID: 795e124adaad
Revises: 62fddec52b79
Create Date: 2026-07-25 21:04:40.394220
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '795e124adaad'
down_revision: Union[str, None] = '62fddec52b79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guarded because some production environments already created these
    # tables out-of-band via an old startup self-heal pass while
    # alembic_version stayed on an older revision -- see
    # 20260612_audit_log_and_transaction_fk for the same pattern.
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "laundry_vendors" not in inspector.get_table_names():
        op.create_table(
            "laundry_vendors",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("stock_location_id", sa.Integer(), nullable=False),
            sa.Column("contact_phone", sa.String(length=40), nullable=True),
            sa.Column("contact_email", sa.String(length=150), nullable=True),
            sa.Column("active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], name="fk_laundry_vendors_hotel_id"),
            sa.ForeignKeyConstraint(
                ["hotel_id", "stock_location_id"],
                ["stock_locations.hotel_id", "stock_locations.id"],
                name="fk_laundry_vendors_hotel_stock_location",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_laundry_vendors"),
            sa.UniqueConstraint("hotel_id", "name", name="uq_laundry_vendors_hotel_name"),
            sa.UniqueConstraint("hotel_id", "id", name="uq_laundry_vendors_hotel_id_id"),
        )
    if "ix_laundry_vendors_hotel_id" not in ({ix["name"] for ix in inspector.get_indexes("laundry_vendors")} if inspector.has_table("laundry_vendors") else set()):
        op.create_index("ix_laundry_vendors_hotel_id", "laundry_vendors", ["hotel_id"], unique=False)

    if "laundry_vendor_prices" not in inspector.get_table_names():
        op.create_table(
            "laundry_vendor_prices",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("vendor_id", sa.Integer(), nullable=False),
            sa.Column("stock_item_id", sa.Integer(), nullable=False),
            sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency_code", sa.String(length=3), server_default="ARS", nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("unit_price >= 0", name="ck_laundry_vendor_prices_unit_price_non_negative"),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], name="fk_laundry_vendor_prices_hotel_id"),
            sa.ForeignKeyConstraint(
                ["hotel_id", "vendor_id"],
                ["laundry_vendors.hotel_id", "laundry_vendors.id"],
                name="fk_laundry_vendor_prices_hotel_vendor",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["hotel_id", "stock_item_id"],
                ["stock_items.hotel_id", "stock_items.id"],
                name="fk_laundry_vendor_prices_hotel_stock_item",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_laundry_vendor_prices"),
            sa.UniqueConstraint("vendor_id", "stock_item_id", name="uq_laundry_vendor_prices_vendor_item"),
        )
    if "ix_laundry_vendor_prices_hotel_id" not in ({ix["name"] for ix in inspector.get_indexes("laundry_vendor_prices")} if inspector.has_table("laundry_vendor_prices") else set()):
        op.create_index("ix_laundry_vendor_prices_hotel_id", "laundry_vendor_prices", ["hotel_id"], unique=False)

    if "laundry_remitos" not in inspector.get_table_names():
        op.create_table(
            "laundry_remitos",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("vendor_id", sa.Integer(), nullable=False),
            sa.Column("direction", sa.String(length=10), nullable=False),
            sa.Column("remito_number", sa.String(length=60), nullable=False),
            sa.Column("remito_date", sa.DateTime(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("direction IN ('outbound', 'inbound')", name="ck_laundry_remitos_direction_valid"),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], name="fk_laundry_remitos_hotel_id"),
            sa.ForeignKeyConstraint(
                ["hotel_id", "vendor_id"],
                ["laundry_vendors.hotel_id", "laundry_vendors.id"],
                name="fk_laundry_remitos_hotel_vendor",
            ),
            sa.ForeignKeyConstraint(
                ["created_by_user_id"], ["users.id"], name="fk_laundry_remitos_created_by_user_id", ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id", name="pk_laundry_remitos"),
            sa.UniqueConstraint("hotel_id", "id", name="uq_laundry_remitos_hotel_id_id"),
        )
    laundry_remitos_indexes = {ix["name"] for ix in inspector.get_indexes("laundry_remitos")} if inspector.has_table("laundry_remitos") else set()
    if "ix_laundry_remitos_hotel_id" not in laundry_remitos_indexes:
        op.create_index("ix_laundry_remitos_hotel_id", "laundry_remitos", ["hotel_id"], unique=False)
    if "ix_laundry_remitos_vendor_id" not in laundry_remitos_indexes:
        op.create_index("ix_laundry_remitos_vendor_id", "laundry_remitos", ["vendor_id"], unique=False)

    if "laundry_remito_lines" not in inspector.get_table_names():
        op.create_table(
            "laundry_remito_lines",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("remito_id", sa.Integer(), nullable=False),
            sa.Column("stock_item_id", sa.Integer(), nullable=False),
            sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
            sa.Column("unit_price_snapshot", sa.Numeric(12, 2), nullable=True),
            sa.CheckConstraint("quantity > 0", name="ck_laundry_remito_lines_quantity_positive"),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], name="fk_laundry_remito_lines_hotel_id"),
            sa.ForeignKeyConstraint(
                ["hotel_id", "remito_id"],
                ["laundry_remitos.hotel_id", "laundry_remitos.id"],
                name="fk_laundry_remito_lines_hotel_remito",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["hotel_id", "stock_item_id"],
                ["stock_items.hotel_id", "stock_items.id"],
                name="fk_laundry_remito_lines_hotel_stock_item",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_laundry_remito_lines"),
        )
    laundry_remito_lines_indexes = {ix["name"] for ix in inspector.get_indexes("laundry_remito_lines")} if inspector.has_table("laundry_remito_lines") else set()
    if "ix_laundry_remito_lines_hotel_id" not in laundry_remito_lines_indexes:
        op.create_index("ix_laundry_remito_lines_hotel_id", "laundry_remito_lines", ["hotel_id"], unique=False)
    if "ix_laundry_remito_lines_remito_id" not in laundry_remito_lines_indexes:
        op.create_index("ix_laundry_remito_lines_remito_id", "laundry_remito_lines", ["remito_id"], unique=False)

    # This migration runs after the RLS baseline (20260724_tenant_rls_context),
    # so these new tables own their own policy -- same pattern as
    # 20260724_payment_proof_blobs.py. ENABLE/FORCE ROW LEVEL SECURITY are
    # idempotent (safe to re-run); CREATE POLICY is not, so guard it against
    # pg_policies.
    if bind.dialect.name == "postgresql":
        for table_name in ("laundry_vendors", "laundry_vendor_prices", "laundry_remitos", "laundry_remito_lines"):
            op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
            policy_exists = bind.execute(sa.text(
                "SELECT 1 FROM pg_policies WHERE tablename = :table_name "
                "AND policyname = :policy_name"
            ), {"table_name": table_name, "policy_name": f"tenant_isolation_{table_name}"}).first()
            if not policy_exists:
                op.execute(f'''CREATE POLICY "tenant_isolation_{table_name}" ON "{table_name}"
                    USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
                    WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)''')


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table_name in ("laundry_remito_lines", "laundry_remitos", "laundry_vendor_prices", "laundry_vendors"):
            op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{table_name}" ON "{table_name}"')
            op.execute(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY')

    op.drop_index("ix_laundry_remito_lines_remito_id", table_name="laundry_remito_lines")
    op.drop_index("ix_laundry_remito_lines_hotel_id", table_name="laundry_remito_lines")
    op.drop_table("laundry_remito_lines")

    op.drop_index("ix_laundry_remitos_vendor_id", table_name="laundry_remitos")
    op.drop_index("ix_laundry_remitos_hotel_id", table_name="laundry_remitos")
    op.drop_table("laundry_remitos")

    op.drop_index("ix_laundry_vendor_prices_hotel_id", table_name="laundry_vendor_prices")
    op.drop_table("laundry_vendor_prices")

    op.drop_index("ix_laundry_vendors_hotel_id", table_name="laundry_vendors")
    op.drop_table("laundry_vendors")
