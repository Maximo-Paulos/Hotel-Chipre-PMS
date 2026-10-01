"""Add effective-dated company extra-person rates and audited charge corrections.

Existing legacy company rates are seeded from the migration cutover date only.
We cannot infer their historical effective dates, so no past nights are priced
from the current legacy value.
"""
from alembic import op
import sqlalchemy as sa


revision = "20261015_company_nightly_rate_history"
down_revision = "20261014_payment_fx_currency"
branch_labels = None
depends_on = None


RATE_TABLE = "company_nightly_surcharge_rates"
ADJUSTMENT_TABLE = "company_night_charge_amount_adjustments"


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


def _disable_tenant_rls(table_name: str) -> None:
    quoted = f'"{table_name}"'
    policy = f'"tenant_isolation_{table_name}"'
    op.execute(f"DROP POLICY IF EXISTS {policy} ON {quoted}")
    op.execute(f"ALTER TABLE {quoted} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {quoted} DISABLE ROW LEVEL SECURITY")


def _disable_silent_rls_filtering(bind) -> None:
    """Make destructive downgrade guards fail if PostgreSQL would hide rows."""
    if bind.dialect.name == "postgresql":
        # FORCE ROW LEVEL SECURITY can make an unscoped SELECT look empty to
        # a non-BYPASSRLS migration role. Fail closed instead of allowing a
        # downgrade guard to miss history and drop user data.
        bind.execute(sa.text("SET LOCAL row_security = off"))


def upgrade() -> None:
    op.create_table(
        RATE_TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_migration_seed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("amount >= 0", name="ck_company_nightly_surcharge_rates_amount_nonnegative"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["hotel_id", "company_id"],
            ["companies.hotel_id", "companies.id"],
            name="fk_company_nightly_surcharge_rates_hotel_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hotel_id", "company_id", "id", name="uq_company_nightly_surcharge_rates_hotel_company_id"
        ),
    )
    op.create_index(
        "ix_company_nightly_surcharge_rates_hotel_company_date",
        RATE_TABLE,
        ["hotel_id", "company_id", "effective_from", "id"],
    )

    op.create_table(
        ADJUSTMENT_TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("company_night_charge_id", sa.Integer(), nullable=False),
        sa.Column("previous_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("new_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("delta_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint(
            "previous_amount > 0",
            name="ck_company_night_charge_amount_adjustments_previous_positive",
        ),
        sa.CheckConstraint(
            "new_amount > 0",
            name="ck_company_night_charge_amount_adjustments_new_positive",
        ),
        sa.CheckConstraint(
            "delta_amount = new_amount - previous_amount",
            name="ck_company_night_charge_amount_adjustments_delta_consistent",
        ),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["hotel_id", "company_night_charge_id"],
            ["company_night_charges.hotel_id", "company_night_charges.id"],
            name="fk_company_night_charge_amount_adjustments_hotel_charge",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_night_charge_amount_adjustments_hotel_charge",
        ADJUSTMENT_TABLE,
        ["hotel_id", "company_night_charge_id", "created_at", "id"],
    )

    # Keep old charge snapshots as-is, but make their original one-person
    # meaning explicit for the new response and correction UI.
    op.add_column("company_night_charges", sa.Column("unit_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column(
        "company_night_charges",
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("company_night_charges", sa.Column("rate_id", sa.Integer(), nullable=True))
    op.add_column("company_night_charges", sa.Column("rate_effective_from", sa.Date(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE company_night_charges "
            "SET unit_amount = amount, quantity = 1 "
            "WHERE unit_amount IS NULL"
        )
    )
    with op.batch_alter_table("company_night_charges") as batch_op:
        batch_op.create_check_constraint("ck_company_night_charges_quantity_positive", "quantity > 0")
        batch_op.create_foreign_key(
            "fk_company_night_charges_hotel_rate",
            RATE_TABLE,
            ["hotel_id", "company_id", "rate_id"],
            ["hotel_id", "company_id", "id"],
            ondelete="RESTRICT",
        )

    # This cutover seed applies the old configured amount only on or after
    # migration day. Historical dates are intentionally left without an
    # inferred rate because the old schema had no effective-date history.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Match the request path's hotel-local calendar date (Render/database
        # clocks are UTC, and can already be on tomorrow for an AR hotel).
        cutover_date = (
            "(CURRENT_TIMESTAMP AT TIME ZONE "
            "COALESCE(NULLIF(hotel_configuration.hotel_timezone, ''), 'UTC'))::date"
        )
        op.execute(
            sa.text(
                "INSERT INTO company_nightly_surcharge_rates "
                "(hotel_id, company_id, effective_from, amount, is_migration_seed, created_by_user_id, created_at) "
                f"SELECT companies.hotel_id, companies.id, {cutover_date}, "
                "companies.extra_person_nightly_surcharge, TRUE, NULL, CURRENT_TIMESTAMP "
                "FROM companies JOIN hotel_configuration ON hotel_configuration.id = companies.hotel_id "
                "WHERE companies.extra_person_nightly_surcharge IS NOT NULL"
            )
        )
    else:
        # SQLite does not provide PostgreSQL's IANA timezone conversion. Test
        # databases use the DB date; production cutover above uses hotel-local.
        op.execute(
            sa.text(
                "INSERT INTO company_nightly_surcharge_rates "
                "(hotel_id, company_id, effective_from, amount, is_migration_seed, created_by_user_id, created_at) "
                "SELECT hotel_id, id, CURRENT_DATE, extra_person_nightly_surcharge, TRUE, NULL, CURRENT_TIMESTAMP "
                "FROM companies WHERE extra_person_nightly_surcharge IS NOT NULL"
            )
        )

    if bind.dialect.name == "postgresql":
        _enable_tenant_rls(RATE_TABLE)
        _enable_tenant_rls(ADJUSTMENT_TABLE)

    # Ship the rate-management capability and its defaults with the tables.
    # Insert-only behavior preserves any rows already seeded by application
    # startup while covering existing databases upgraded before app startup.
    op.execute(
        sa.text(
            "INSERT INTO permissions (code, description, critical, step_up_required, delegable) "
            "VALUES ('company:night_rate_manage', 'Manage company extra-person nightly rates', false, false, true) "
            "ON CONFLICT (code) DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permission_defaults (role, permission_code, allowed) "
            "VALUES "
            "('owner', 'company:night_rate_manage', true), "
            "('co_owner', 'company:night_rate_manage', true), "
            "('manager', 'company:night_rate_manage', true), "
            "('receptionist', 'company:night_rate_manage', false), "
            "('housekeeping', 'company:night_rate_manage', false) "
            "ON CONFLICT (role, permission_code) DO NOTHING"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    _disable_silent_rls_filtering(bind)
    custom_rates = bind.execute(
        sa.text(f"SELECT COUNT(*) FROM {RATE_TABLE} WHERE is_migration_seed = false")
    ).scalar_one()
    amount_adjustments = bind.execute(sa.text(f"SELECT COUNT(*) FROM {ADJUSTMENT_TABLE}")).scalar_one()
    charge_snapshots = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM company_night_charges "
            "WHERE rate_id IS NOT NULL OR quantity <> 1"
        )
    ).scalar_one()
    if custom_rates or amount_adjustments or charge_snapshots:
        raise RuntimeError(
            "Refusing to downgrade company nightly pricing after user rates, per-person charge snapshots, "
            "or audited corrections exist; export or preserve this operational history before rollback."
        )

    if bind.dialect.name == "postgresql":
        _disable_tenant_rls(ADJUSTMENT_TABLE)
        _disable_tenant_rls(RATE_TABLE)

    with op.batch_alter_table("company_night_charges") as batch_op:
        batch_op.drop_constraint("fk_company_night_charges_hotel_rate", type_="foreignkey")
        batch_op.drop_constraint("ck_company_night_charges_quantity_positive", type_="check")
        batch_op.drop_column("rate_effective_from")
        batch_op.drop_column("rate_id")
        batch_op.drop_column("quantity")
        batch_op.drop_column("unit_amount")

    op.drop_index(
        "ix_company_night_charge_amount_adjustments_hotel_charge",
        table_name=ADJUSTMENT_TABLE,
    )
    op.drop_table(ADJUSTMENT_TABLE)
    op.drop_index("ix_company_nightly_surcharge_rates_hotel_company_date", table_name=RATE_TABLE)
    op.drop_table(RATE_TABLE)
