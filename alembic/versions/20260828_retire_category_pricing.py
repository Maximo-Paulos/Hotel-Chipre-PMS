"""Fold legacy category pricing into seasonal price periods."""
from __future__ import annotations

from datetime import date, datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "20260828_retire_category_pricing"
down_revision = "20260828_config_authority_dedup"
branch_labels = None
depends_on = None

LEGACY_NAME = "Migrated legacy category pricing"
METHOD_COLUMNS = (
    "price_cash",
    "price_transfer",
    "price_mercadopago",
    "price_paypal",
    "price_credit_card",
    "price_debit_card",
    "price_booking",
    "price_expedia",
)


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, name: str) -> bool:
    return name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table("price_periods"):
        for name in METHOD_COLUMNS:
            if not _has_column("price_periods", name):
                op.add_column("price_periods", sa.Column(name, sa.Float(), nullable=True))

    if _has_table("category_pricing") and not _has_table("category_pricing_legacy"):
        op.rename_table("category_pricing", "category_pricing_legacy")

    if not _has_table("category_pricing_legacy") or not _has_table("price_periods"):
        return

    legacy = sa.table(
        "category_pricing_legacy",
        sa.column("category_id", sa.Integer()),
        *[sa.column(name, sa.Float()) for name in METHOD_COLUMNS],
    )
    categories = sa.table(
        "room_categories",
        sa.column("id", sa.Integer()),
        sa.column("hotel_id", sa.Integer()),
    )
    periods = sa.table(
        "price_periods",
        sa.column("id", sa.Integer()),
        sa.column("hotel_id", sa.Integer()),
        sa.column("category_id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("start_date", sa.Date()),
        sa.column("end_date", sa.Date()),
        sa.column("price_per_night", sa.Float()),
        sa.column("priority", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime()),
        *[sa.column(name, sa.Float()) for name in METHOD_COLUMNS],
    )
    rows = bind.execute(
        sa.select(legacy, categories.c.hotel_id)
        .select_from(legacy.join(categories, categories.c.id == legacy.c.category_id))
    )
    for row in rows:
        if bind.execute(
            sa.select(periods.c.id).where(
                periods.c.hotel_id == row.hotel_id,
                periods.c.category_id == row.category_id,
                periods.c.name == LEGACY_NAME,
                periods.c.priority == -100000,
            )
        ).first():
            continue
        values = {name: getattr(row, name) for name in METHOD_COLUMNS}
        base = next((value for value in values.values() if value is not None), 0.0)
        bind.execute(
            periods.insert().values(
                hotel_id=row.hotel_id,
                category_id=row.category_id,
                name=LEGACY_NAME,
                start_date=date(1970, 1, 1),
                end_date=date(9999, 12, 31),
                price_per_night=base,
                priority=-100000,
                is_active=True,
                created_at=datetime.now(timezone.utc),
                **values,
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table("price_periods") and _has_table("category_pricing_legacy"):
        periods = sa.table(
            "price_periods",
            sa.column("id", sa.Integer()),
            sa.column("hotel_id", sa.Integer()),
            sa.column("category_id", sa.Integer()),
            sa.column("name", sa.String()),
            sa.column("priority", sa.Integer()),
        )
        bind.execute(
            periods.delete().where(periods.c.name == LEGACY_NAME, periods.c.priority == -100000)
        )
    if _has_table("category_pricing_legacy") and not _has_table("category_pricing"):
        op.rename_table("category_pricing_legacy", "category_pricing")
    if _has_table("price_periods"):
        with op.batch_alter_table("price_periods", recreate="auto") as batch:
            for name in reversed(METHOD_COLUMNS):
                if _has_column("price_periods", name):
                    batch.drop_column(name)
