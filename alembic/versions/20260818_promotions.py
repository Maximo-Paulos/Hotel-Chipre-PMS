"""add promotions table (versioned, typed conditions) and migrate
payment_surcharges.amount from Float to Numeric

Revision ID: 20260818_promotions
Revises: 20260813_guest_restrictions
Create Date: 2026-08-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260818_promotions"
down_revision: Union[str, None] = "20260813_guest_restrictions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BENEFIT_TYPE_ENUM = sa.Enum("fixed", "percentage", name="promotion_benefit_type_enum")
SCOPE_ENUM = sa.Enum("full_stay", "from_night_n", name="promotion_scope_enum")


def _install_rls(connection) -> None:
    """Install the PostgreSQL tenant policy for promotions; no-op elsewhere."""
    if connection.dialect.name != "postgresql":
        return
    op.execute('ALTER TABLE "promotions" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "promotions" FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS "tenant_isolation_promotions" ON "promotions"')
    op.execute(
        '''CREATE POLICY "tenant_isolation_promotions"
           ON "promotions"
           USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
           WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_rls(connection) -> None:
    """Remove the PostgreSQL tenant policy before dropping the table."""
    if connection.dialect.name != "postgresql":
        return
    op.execute('DROP POLICY IF EXISTS "tenant_isolation_promotions" ON "promotions"')
    op.execute('ALTER TABLE "promotions" NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "promotions" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    connection = op.get_bind()

    op.create_table(
        "promotions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("benefit_type", BENEFIT_TYPE_ENUM, nullable=False),
        sa.Column("benefit_value", sa.Numeric(12, 4), nullable=False),
        sa.Column("scope", SCOPE_ENUM, nullable=False, server_default="full_stay"),
        sa.Column("from_night_number", sa.Integer(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stackable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("previous_version_id", sa.Integer(), nullable=True),
        sa.Column("booking_from", sa.Date(), nullable=True),
        sa.Column("booking_to", sa.Date(), nullable=True),
        sa.Column("stay_from", sa.Date(), nullable=True),
        sa.Column("stay_to", sa.Date(), nullable=True),
        sa.Column("min_nights", sa.Integer(), nullable=True),
        sa.Column("max_nights", sa.Integer(), nullable=True),
        sa.Column("weekdays_mask", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("sales_channel_code", sa.String(length=50), nullable=True),
        sa.Column("guest_id", sa.Integer(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("guest_tag_type", sa.String(length=30), nullable=True),
        sa.Column("payment_currency", sa.String(length=3), nullable=True),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(), nullable=True),
        sa.Column("deactivated_by_user_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hotel_id", "code", "version", name="uq_promotion_hotel_code_version"),
        sa.UniqueConstraint("hotel_id", "id", name="uq_promotion_hotel_id_id"),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_promotions_hotel_id_hotel_configuration", ondelete="CASCADE",
        ),
        # Composite, not scalar: a promotion must never claim to supersede a
        # version belonging to another hotel (self-referential).
        sa.ForeignKeyConstraint(
            ["hotel_id", "previous_version_id"], ["promotions.hotel_id", "promotions.id"],
            name="fk_promotions_hotel_previous_version", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "category_id"], ["room_categories.hotel_id", "room_categories.id"],
            name="fk_promotions_hotel_category", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "room_id"], ["rooms.hotel_id", "rooms.id"],
            name="fk_promotions_hotel_room", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "guest_id"], ["guests.hotel_id", "guests.id"],
            name="fk_promotions_hotel_guest", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "company_id"], ["companies.hotel_id", "companies.id"],
            name="fk_promotions_hotel_company", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name="fk_promotions_created_by_user_id_users", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["deactivated_by_user_id"], ["users.id"],
            name="fk_promotions_deactivated_by_user_id_users", ondelete="SET NULL",
        ),
    )
    op.create_index("ix_promotion_hotel_code", "promotions", ["hotel_id", "code"])
    op.create_index("ix_promotion_hotel_active", "promotions", ["hotel_id", "is_active"])
    _install_rls(connection)

    # Decimal-safe payment adjustments: payment_surcharges.amount was Float.
    # A single batch_alter_table call is the established pattern in this repo
    # for Float->Numeric money-column migrations (see
    # 20260612_v72_gaps_phase1.py); alembic batch mode does an in-place ALTER
    # on PostgreSQL and a safe rebuild-and-copy on SQLite, so existing rows
    # are preserved (backfilled) automatically by the column type change.
    with op.batch_alter_table("payment_surcharges") as batch_op:
        batch_op.alter_column(
            "amount", type_=sa.Numeric(12, 4), existing_type=sa.Float(), existing_nullable=False,
        )


def downgrade() -> None:
    connection = op.get_bind()

    with op.batch_alter_table("payment_surcharges") as batch_op:
        batch_op.alter_column(
            "amount", type_=sa.Float(), existing_type=sa.Numeric(12, 4), existing_nullable=False,
        )

    _remove_rls(connection)
    op.drop_index("ix_promotion_hotel_active", table_name="promotions")
    op.drop_index("ix_promotion_hotel_code", table_name="promotions")
    op.drop_table("promotions")
    if connection.dialect.name == "postgresql":
        BENEFIT_TYPE_ENUM.drop(connection, checkfirst=True)
        SCOPE_ENUM.drop(connection, checkfirst=True)
