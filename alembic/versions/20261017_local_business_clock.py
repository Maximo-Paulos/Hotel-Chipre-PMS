"""Persist the local synthetic hotel business date.

Revision ID: 20261017_local_business_clock
Revises: 20261016_fx_direction_markets
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261017_local_business_clock"
down_revision: Union[str, None] = "20261016_fx_direction_markets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "hotel_business_clock"
EXPECTED_COLUMNS = {
    "hotel_id",
    "business_date",
    "advanced_at",
    "advanced_by_user_id",
}


def _existing_table_matches(bind) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(TABLE):
        return False

    columns = {column["name"] for column in inspector.get_columns(TABLE)}
    primary_key = inspector.get_pk_constraint(TABLE).get("constrained_columns") or []
    if not EXPECTED_COLUMNS.issubset(columns) or primary_key != ["hotel_id"]:
        raise RuntimeError(
            "Existing hotel_business_clock table does not match the expected schema; "
            "reconcile it before applying this migration."
        )

    foreign_keys = {
        (
            tuple(foreign_key["constrained_columns"]),
            foreign_key["referred_table"],
            tuple(foreign_key["referred_columns"]),
        )
        for foreign_key in inspector.get_foreign_keys(TABLE)
    }
    expected_foreign_keys = {
        (("hotel_id",), "hotel_configuration", ("id",)),
        (("advanced_by_user_id",), "users", ("id",)),
    }
    if not expected_foreign_keys.issubset(foreign_keys):
        raise RuntimeError(
            "Existing hotel_business_clock table is missing a required foreign key; "
            "reconcile it before applying this migration."
        )
    return True


def _install_tenant_rls(bind) -> None:
    if bind.dialect.name != "postgresql":
        return

    quoted = f'"{TABLE}"'
    policy = f'"tenant_isolation_{TABLE}"'
    op.execute(f"ALTER TABLE {quoted} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {quoted} FORCE ROW LEVEL SECURITY")
    op.execute(f"DROP POLICY IF EXISTS {policy} ON {quoted}")
    op.execute(
        f"CREATE POLICY {policy} ON {quoted} "
        "USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer) "
        "WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)"
    )


def upgrade() -> None:
    bind = op.get_bind()
    # Local development bootstraps missing model tables with Base.metadata.create_all
    # before Alembic runs. Adopt that table after validating its shape instead of
    # failing on an already-created table or replacing simulation state.
    if not _existing_table_matches(bind):
        op.create_table(
            TABLE,
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("business_date", sa.Date(), nullable=False),
            sa.Column("advanced_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("advanced_by_user_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["hotel_id"], ["hotel_configuration.id"],
                name="fk_hotel_business_clock_hotel_id_hotel_configuration",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["advanced_by_user_id"], ["users.id"],
                name="fk_hotel_business_clock_advanced_by_user_id_users",
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("hotel_id", name="pk_hotel_business_clock"),
        )

    # The local app may have created the table before Alembic reaches this
    # revision, so RLS must be installed whether we create or adopt it.
    _install_tenant_rls(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(TABLE):
        return
    if bind.dialect.name == "postgresql":
        quoted = f'"{TABLE}"'
        policy = f'"tenant_isolation_{TABLE}"'
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {quoted}")
        op.execute(f"ALTER TABLE {quoted} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {quoted} DISABLE ROW LEVEL SECURITY")
    if bind.execute(sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")).first() is not None:
        raise RuntimeError(
            "Cannot downgrade the local business clock while simulation state exists; "
            "preserve or explicitly clear that state first."
        )
    op.drop_table(TABLE)
