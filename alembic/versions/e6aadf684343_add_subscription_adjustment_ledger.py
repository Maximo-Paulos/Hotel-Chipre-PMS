"""add subscription adjustment ledger

Revision ID: e6aadf684343
Revises: 0f85dca5b98b
Create Date: 2026-08-20 18:26:53.850506
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e6aadf684343'
down_revision: Union[str, None] = '8b5d07cc381b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_unique(inspector, table_name: str, columns: tuple[str, ...]) -> bool:
    wanted = list(columns)
    return any(item.get("column_names") == wanted for item in inspector.get_unique_constraints(table_name)) or any(
        item.get("unique") and item.get("column_names") == wanted
        for item in inspector.get_indexes(table_name)
    )


def _ensure_subscription_composite_target(connection) -> None:
    inspector = sa.inspect(connection)
    if _has_unique(inspector, "subscriptions", ("hotel_id", "id")):
        return
    if connection.dialect.name == "sqlite":
        # The historical composite-FK migration is intentionally a PostgreSQL
        # no-op. A unique index is enough for SQLite to validate this FK while
        # avoiding a table rebuild that could disturb child tables.
        op.create_index(
            "uq_subscriptions_hotel_id_id",
            "subscriptions",
            ["hotel_id", "id"],
            unique=True,
        )
    else:
        op.create_unique_constraint(
            "uq_subscriptions_hotel_id_id",
            "subscriptions",
            ["hotel_id", "id"],
        )


def _install_rls(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    op.execute('ALTER TABLE "subscription_adjustments" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "subscription_adjustments" FORCE ROW LEVEL SECURITY')
    op.execute(
        '''CREATE POLICY "tenant_isolation_subscription_adjustments"
           ON "subscription_adjustments"
           USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
           WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )
    op.execute(
        '''CREATE POLICY "master_admin_bypass_subscription_adjustments"
           ON "subscription_adjustments"
           USING (current_setting('app.master_admin', true) = 'true')
           WITH CHECK (current_setting('app.master_admin', true) = 'true')'''
    )


def _remove_rls(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_subscription_adjustments" '
        'ON "subscription_adjustments"'
    )
    op.execute(
        'DROP POLICY IF EXISTS "master_admin_bypass_subscription_adjustments" '
        'ON "subscription_adjustments"'
    )
    op.execute('ALTER TABLE "subscription_adjustments" NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "subscription_adjustments" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    connection = op.get_bind()
    _ensure_subscription_composite_target(connection)
    op.create_table(
        "subscription_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("adjustment_type", sa.String(length=30), nullable=False),
        sa.Column("plan_code", sa.String(length=20), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_role", sa.String(length=50), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["hotel_id", "subscription_id"],
            ["subscriptions.hotel_id", "subscriptions.id"],
            name="fk_subscription_adjustments_hotel_subscription",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "adjustment_type in ('discount','credit','free_extension','override')",
            name="ck_subscription_adjustments_type",
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until >= valid_from",
            name="ck_subscription_adjustments_validity",
        ),
        sa.UniqueConstraint(
            "hotel_id",
            "idempotency_key",
            name="uq_subscription_adjustments_hotel_idempotency_key",
        ),
    )
    op.create_index(
        "ix_subscription_adjustments_hotel_created",
        "subscription_adjustments",
        ["hotel_id", "created_at"],
    )
    op.create_index(
        "ix_subscription_adjustments_subscription_id",
        "subscription_adjustments",
        ["subscription_id"],
    )
    _install_rls(connection)


def downgrade() -> None:
    connection = op.get_bind()
    _remove_rls(connection)
    op.drop_index("ix_subscription_adjustments_subscription_id", table_name="subscription_adjustments")
    op.drop_index("ix_subscription_adjustments_hotel_created", table_name="subscription_adjustments")
    op.drop_table("subscription_adjustments")
    if connection.dialect.name == "sqlite":
        inspector = sa.inspect(connection)
        if any(index.get("name") == "uq_subscriptions_hotel_id_id" for index in inspector.get_indexes("subscriptions")):
            op.drop_index("uq_subscriptions_hotel_id_id", table_name="subscriptions")
