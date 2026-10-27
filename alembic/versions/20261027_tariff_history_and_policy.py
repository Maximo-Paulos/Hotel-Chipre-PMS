"""Store comparable published-rate history and pilot recommendation settings.

Revision ID: 20261027_tariff_history_and_policy
Revises: 20261025_wa_msg_cursor_idx
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "20261027_tariff_history_and_policy"
down_revision: str | None = "20261025_wa_msg_cursor_idx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_HISTORY_TABLE = "published_rate_history"


def _install_history_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f'ALTER TABLE "{_HISTORY_TABLE}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{_HISTORY_TABLE}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'''CREATE POLICY "tenant_isolation_{_HISTORY_TABLE}" ON "{_HISTORY_TABLE}"
        USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
        WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_history_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{_HISTORY_TABLE}" ON "{_HISTORY_TABLE}"')
    op.execute(f'ALTER TABLE "{_HISTORY_TABLE}" NO FORCE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{_HISTORY_TABLE}" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    bind = op.get_bind()
    period_columns = {column["name"] for column in sa.inspect(bind).get_columns("price_periods")}
    with op.batch_alter_table("price_periods") as batch:
        if "comparable_season_key" not in period_columns:
            batch.add_column(sa.Column("comparable_season_key", sa.String(80), nullable=True))
        if "is_high_demand_event" not in period_columns:
            batch.add_column(
                sa.Column(
                    "is_high_demand_event",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )

    hotel_columns = {column["name"] for column in sa.inspect(bind).get_columns("hotel_configuration")}
    with op.batch_alter_table("hotel_configuration") as batch:
        new_columns = (
            ("tariff_recommendations_enabled", sa.Boolean(), sa.false()),
            ("tariff_high_occupancy_pct", sa.Numeric(5, 2), sa.text("80")),
            ("tariff_low_occupancy_pct", sa.Numeric(5, 2), sa.text("40")),
            ("tariff_pickup_change_pct", sa.Numeric(6, 2), sa.text("20")),
            ("tariff_max_step_pct", sa.Numeric(5, 2), sa.text("5")),
        )
        for name, type_, default in new_columns:
            if name not in hotel_columns:
                batch.add_column(
                    sa.Column(name, type_, nullable=False, server_default=default)
                )
        existing_checks = {
            check.get("name") for check in sa.inspect(bind).get_check_constraints("hotel_configuration")
        }
        if "ck_hotel_configuration_tariff_occupancy_thresholds" not in existing_checks:
            batch.create_check_constraint(
                "ck_hotel_configuration_tariff_occupancy_thresholds",
                "tariff_low_occupancy_pct >= 0 AND "
                "tariff_low_occupancy_pct < tariff_high_occupancy_pct AND "
                "tariff_high_occupancy_pct <= 100",
            )
        if "ck_hotel_configuration_tariff_recommendation_bounds" not in existing_checks:
            batch.create_check_constraint(
                "ck_hotel_configuration_tariff_recommendation_bounds",
                "tariff_pickup_change_pct > 0 AND tariff_max_step_pct > 0 "
                "AND tariff_max_step_pct <= 5",
            )

    if _HISTORY_TABLE not in sa.inspect(bind).get_table_names():
        op.create_table(
            _HISTORY_TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("category_id", sa.Integer(), nullable=False),
            sa.Column("source_draft_id", sa.Integer(), nullable=False),
            sa.Column("rate_date", sa.Date(), nullable=False),
            sa.Column("comparable_season_key", sa.String(length=80), nullable=True),
            sa.Column("published_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency_code", sa.String(length=3), nullable=False),
            sa.Column("usd_amount", sa.Numeric(12, 4), nullable=True),
            sa.Column("fx_snapshot_id", sa.Integer(), nullable=True),
            sa.Column("fx_market", sa.String(length=20), nullable=True),
            sa.Column("fx_side", sa.String(length=10), nullable=True),
            sa.Column("ars_per_usd", sa.Numeric(20, 8), nullable=True),
            sa.Column("rate_source", sa.String(length=16), nullable=False),
            sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "currency_code = upper(currency_code)",
                name="ck_published_rate_history_currency_upper",
            ),
            sa.CheckConstraint(
                "rate_source IN ('daily_rates', 'price_period')",
                name="ck_published_rate_history_source",
            ),
            sa.CheckConstraint(
                "published_amount >= 0",
                name="ck_published_rate_history_amount_nonnegative",
            ),
            sa.CheckConstraint(
                "usd_amount IS NULL OR usd_amount >= 0",
                name="ck_published_rate_history_usd_nonnegative",
            ),
            sa.ForeignKeyConstraint(
                ["hotel_id"], ["hotel_configuration.id"],
                name="fk_published_rate_history_hotel_id", ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["hotel_id", "category_id"],
                ["room_categories.hotel_id", "room_categories.id"],
                name="fk_published_rate_history_hotel_category", ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_published_rate_history"),
            sa.UniqueConstraint(
                "hotel_id", "source_draft_id", "rate_date",
                name="uq_published_rate_history_source_date",
            ),
        )
        op.create_index(
            "ix_published_rate_history_comparable",
            _HISTORY_TABLE,
            ["hotel_id", "category_id", "comparable_season_key", "rate_date"],
        )
    _install_history_rls()


def downgrade() -> None:
    bind = op.get_bind()
    if _HISTORY_TABLE in sa.inspect(bind).get_table_names():
        _remove_history_rls()
        op.drop_index("ix_published_rate_history_comparable", table_name=_HISTORY_TABLE)
        op.drop_table(_HISTORY_TABLE)

    hotel_columns = {column["name"] for column in sa.inspect(bind).get_columns("hotel_configuration")}
    with op.batch_alter_table("hotel_configuration") as batch:
        existing_checks = {
            check.get("name") for check in sa.inspect(bind).get_check_constraints("hotel_configuration")
        }
        if "ck_hotel_configuration_tariff_occupancy_thresholds" in existing_checks:
            batch.drop_constraint("ck_hotel_configuration_tariff_occupancy_thresholds", type_="check")
        if "ck_hotel_configuration_tariff_recommendation_bounds" in existing_checks:
            batch.drop_constraint("ck_hotel_configuration_tariff_recommendation_bounds", type_="check")
        for name in (
            "tariff_max_step_pct",
            "tariff_pickup_change_pct",
            "tariff_low_occupancy_pct",
            "tariff_high_occupancy_pct",
            "tariff_recommendations_enabled",
        ):
            if name in hotel_columns:
                batch.drop_column(name)

    period_columns = {column["name"] for column in sa.inspect(bind).get_columns("price_periods")}
    with op.batch_alter_table("price_periods") as batch:
        if "is_high_demand_event" in period_columns:
            batch.drop_column("is_high_demand_event")
        if "comparable_season_key" in period_columns:
            batch.drop_column("comparable_season_key")
