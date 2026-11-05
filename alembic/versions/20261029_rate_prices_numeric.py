"""Store active nightly and seasonal rate prices as exact cents.

Revision ID: 20261029_rate_prices_numeric
Revises: 20261029_manual_fx_payment_quotes
Create Date: 2026-10-29
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261029_rate_prices_numeric"
down_revision: str | Sequence[str] | None = "20261029_manual_fx_payment_quotes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RATE_PRICE_COLUMNS: dict[str, tuple[str, ...]] = {
    "daily_rates": (
        "price",
        "price_cash",
        "price_transfer",
        "price_mercadopago",
        "price_paypal",
        "price_credit_card",
    ),
    "price_periods": (
        "price_per_night",
        "price_cash",
        "price_transfer",
        "price_mercadopago",
        "price_paypal",
        "price_credit_card",
        "price_debit_card",
        "price_booking",
        "price_expedia",
    ),
}

_CENT_TOLERANCE = "0.000001"
_MAX_PRICE = "9999999999.99"  # Numeric(12, 2)


def _columns_to_change(table_name: str, *, target: str) -> list[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return []

    reflected = {column["name"]: column["type"] for column in inspector.get_columns(table_name)}
    result: list[str] = []
    for name in RATE_PRICE_COLUMNS[table_name]:
        column_type = reflected.get(name)
        if column_type is None:
            continue
        is_float = isinstance(column_type, sa.Float)
        is_numeric = isinstance(column_type, sa.Numeric) and not is_float
        if target == "numeric" and is_float or target == "float" and is_numeric:
            result.append(name)
    return result


def _assert_prices_fit_cents(table_name: str, column_names: list[str]) -> None:
    """Refuse silent rounding or overflow before converting existing prices."""
    if not column_names:
        return

    bind = op.get_bind()
    preparer = bind.dialect.identifier_preparer
    table_sql = preparer.quote(table_name)
    invalid_conditions: list[str] = []
    for name in column_names:
        column_sql = preparer.quote(name)
        numeric_value = f"CAST({column_sql} AS NUMERIC)"
        invalid_conditions.append(
            f"({column_sql} IS NOT NULL AND ("
            f"CAST({column_sql} AS TEXT) IN ('NaN', 'Infinity', '-Infinity') "
            f"OR ABS({numeric_value}) > {_MAX_PRICE} "
            f"OR ABS({numeric_value} - ROUND({numeric_value}, 2)) > {_CENT_TOLERANCE}"
            "))"
        )
    invalid_where = " OR ".join(invalid_conditions)
    has_invalid = bind.execute(
        sa.text(f"SELECT EXISTS (SELECT 1 FROM {table_sql} WHERE {invalid_where} LIMIT 1)")
    ).scalar_one()
    if has_invalid:
        raise RuntimeError(
            f"{table_name} contains a rate outside the supported Numeric(12, 2) range "
            "or with sub-cent precision; reconcile it before retrying this migration."
        )


def _change_column_types(*, source: str, target: str) -> None:
    bind = op.get_bind()
    source_type = sa.Float() if source == "float" else sa.Numeric(12, 2)
    target_type = sa.Float() if target == "float" else sa.Numeric(12, 2)

    changes = {
        table_name: _columns_to_change(table_name, target=target)
        for table_name in RATE_PRICE_COLUMNS
    }
    if target == "numeric":
        # Validate every affected table before altering any of them. This keeps
        # a failed preflight from leaving earlier tables converted when the
        # migration is invoked outside Alembic's normal transaction wrapper.
        for table_name, column_names in changes.items():
            _assert_prices_fit_cents(table_name, column_names)

    for table_name, column_names in changes.items():
        if not column_names:
            continue

        with op.batch_alter_table(table_name) as batch:
            for name in column_names:
                using = (
                    f"{bind.dialect.identifier_preparer.quote(name)}::double precision"
                    if target == "float"
                    else f"{bind.dialect.identifier_preparer.quote(name)}::numeric(12, 2)"
                )
                batch.alter_column(
                    name,
                    existing_type=source_type,
                    type_=target_type,
                    postgresql_using=using,
                )


def upgrade() -> None:
    _change_column_types(source="float", target="numeric")


def downgrade() -> None:
    _change_column_types(source="numeric", target="float")
