"""Harden company nightly charge tenant keys and row level security."""
from alembic import op
import sqlalchemy as sa


revision = "20261010_company_night_charge_tenant_keys"
down_revision = "20261009_company_extension_request"
branch_labels = None
depends_on = None


TENANT_TABLES = (
    "company_night_charges",
    "company_night_charge_payment_allocations",
)
UNIQUE_TARGETS = (
    ("transactions", "uq_transaction_hotel_id_id", ("hotel_id", "id")),
    ("billing_adjustments", "uq_billing_adjustments_hotel_id_id", ("hotel_id", "id")),
)
COMPOSITE_FKS = (
    (
        "company_night_charges",
        "fk_company_night_charges_hotel_billing_adjustment",
        ("hotel_id", "billing_adjustment_id"),
        "billing_adjustments",
        ("hotel_id", "id"),
        "CASCADE",
    ),
)


def _has_unique(table_name: str, columns: tuple[str, ...]) -> bool:
    inspector = sa.inspect(op.get_bind())
    wanted = list(columns)
    return any(
        row.get("column_names") == wanted
        for row in inspector.get_unique_constraints(table_name)
    ) or any(
        row.get("unique") and row.get("column_names") == wanted
        for row in inspector.get_indexes(table_name)
    )


def _has_fk(table_name: str, columns: tuple[str, ...], parent: str, parent_columns: tuple[str, ...]) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(
        row.get("constrained_columns") == list(columns)
        and row.get("referred_table") == parent
        and row.get("referred_columns") == list(parent_columns)
        for row in inspector.get_foreign_keys(table_name)
    )


def _enable_tenant_rls(table_name: str) -> None:
    quoted = f'"{table_name}"'
    policy = f'"tenant_isolation_{table_name}"'
    op.execute(f"ALTER TABLE {quoted} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {quoted} FORCE ROW LEVEL SECURITY")
    op.execute(f"DROP POLICY IF EXISTS {policy} ON {quoted}")
    op.execute(
        f"CREATE POLICY {policy} ON {quoted} "
        "USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer) "
        "WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)"
    )


def upgrade() -> None:
    # The historical core tenant-key migration is PostgreSQL-only. Add the
    # candidate keys here too so SQLite's migrated schema can validate its
    # composite allocation foreign key.
    for table_name, constraint_name, columns in UNIQUE_TARGETS:
        if not _has_unique(table_name, columns):
            with op.batch_alter_table(table_name, recreate="auto") as batch_op:
                batch_op.create_unique_constraint(constraint_name, list(columns))

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table_name, constraint_name, columns, parent, parent_columns, ondelete in COMPOSITE_FKS:
            if not _has_fk(table_name, columns, parent, parent_columns):
                op.create_foreign_key(
                    constraint_name,
                    table_name,
                    parent,
                    list(columns),
                    list(parent_columns),
                    ondelete=ondelete,
                )
        for table_name in TENANT_TABLES:
            _enable_tenant_rls(table_name)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    inspector = sa.inspect(bind)
    for table_name, constraint_name, columns, parent, parent_columns, _ondelete in reversed(COMPOSITE_FKS):
        if any(
            item.get("name") == constraint_name
            and item.get("constrained_columns") == list(columns)
            and item.get("referred_table") == parent
            and item.get("referred_columns") == list(parent_columns)
            for item in inspector.get_foreign_keys(table_name)
        ):
            op.drop_constraint(constraint_name, table_name, type_="foreignkey")

    for table_name in TENANT_TABLES:
        quoted = f'"{table_name}"'
        policy = f'"tenant_isolation_{table_name}"'
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {quoted}")
        op.execute(f"ALTER TABLE {quoted} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {quoted} DISABLE ROW LEVEL SECURITY")
