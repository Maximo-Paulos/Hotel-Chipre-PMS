"""linen location par levels

Revision ID: 41d66acfb13a
Revises: 015f7e36b9cd
Create Date: 2026-09-30 00:19:57.538959
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '41d66acfb13a'
down_revision: Union[str, None] = '015f7e36b9cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "linen_par_levels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("min_quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("min_quantity >= 0", name="ck_linen_par_levels_min_quantity_nonnegative"),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_linen_par_levels_hotel_id", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name="fk_linen_par_levels_created_by_user_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"],
            name="fk_linen_par_levels_updated_by_user_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "item_id"], ["linen_items.hotel_id", "linen_items.id"],
            name="fk_linen_par_levels_hotel_item", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "location_id"], ["linen_locations.hotel_id", "linen_locations.id"],
            name="fk_linen_par_levels_hotel_location", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hotel_id", "item_id", "location_id",
            name="uq_linen_par_levels_hotel_item_location",
        ),
    )
    op.create_index(
        "ix_linen_par_levels_hotel_location", "linen_par_levels", ["hotel_id", "location_id"]
    )
    _install_rls()


def downgrade() -> None:
    _remove_rls()
    op.drop_index("ix_linen_par_levels_hotel_location", table_name="linen_par_levels")
    op.drop_table("linen_par_levels")


def _install_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute('ALTER TABLE "linen_par_levels" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "linen_par_levels" FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS "tenant_isolation_linen_par_levels" ON "linen_par_levels"')
    op.execute(
        '''CREATE POLICY "tenant_isolation_linen_par_levels" ON "linen_par_levels"
            USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
            WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute('DROP POLICY IF EXISTS "tenant_isolation_linen_par_levels" ON "linen_par_levels"')
    op.execute('ALTER TABLE "linen_par_levels" NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "linen_par_levels" DISABLE ROW LEVEL SECURITY')
