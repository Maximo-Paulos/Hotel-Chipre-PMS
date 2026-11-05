"""PostgreSQL behavior checks for exact money in active nightly rate tables."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Float, Numeric, inspect, text

from app.models.daily_rate import DailyRate, PricePeriod
from app.models.hotel_config import HotelConfiguration
from app.models.room import RoomCategory
from app.services.pricing_service import get_price_for_date, resolve_rate_calendar
from app.services.tenant_context import set_tenant_hotel_context


def _rate_price_migration():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20261029_rate_prices_numeric.py"
    spec = spec_from_file_location("rate_prices_numeric_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_postgres_rate_resolution_preserves_cents_for_daily_and_season_rates(pg_session):
    suffix = uuid4().hex[:10].upper()
    hotel_id = 1_200_000_000 + uuid4().int % 20_000_000
    target_date = date.today() + timedelta(days=30)
    next_date = target_date + timedelta(days=1)
    set_tenant_hotel_context(pg_session, hotel_id)

    hotel = HotelConfiguration(
        id=hotel_id,
        hotel_name=f"Synthetic exact-rate hotel {suffix}",
        subscription_active=True,
        default_currency="ARS",
    )
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Synthetic exact-rate category {suffix}",
        code=f"ER{suffix}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    pg_session.add_all([hotel, category])
    pg_session.flush()

    period = PricePeriod(
        hotel_id=hotel_id,
        category_id=category.id,
        name=f"Synthetic exact-rate period {suffix}",
        start_date=target_date,
        end_date=next_date,
        price_per_night=Decimal("120.00"),
        price_cash=Decimal("121.45"),
        priority=0,
        is_active=True,
    )
    daily_rate = DailyRate(
        hotel_id=hotel_id,
        category_id=category.id,
        date=target_date,
        price=Decimal("100.00"),
        price_cash=Decimal("99.95"),
    )
    pg_session.add_all([period, daily_rate])
    pg_session.flush()
    pg_session.expire_all()

    stored_daily = pg_session.query(DailyRate).filter_by(hotel_id=hotel_id, date=target_date).one()
    stored_period = pg_session.query(PricePeriod).filter_by(hotel_id=hotel_id, name=period.name).one()
    assert stored_daily.price == Decimal("100.00")
    assert stored_daily.price_cash == Decimal("99.95")
    assert stored_period.price_per_night == Decimal("120.00")
    assert stored_period.price_cash == Decimal("121.45")

    assert get_price_for_date(pg_session, hotel_id, category.id, target_date, "cash") == 99.95
    assert get_price_for_date(pg_session, hotel_id, category.id, next_date, "cash") == 121.45

    calendar = resolve_rate_calendar(
        pg_session,
        hotel_id,
        category.id,
        target_date,
        next_date,
        payment_method="cash",
        category=category,
    )
    assert [row["price"] for row in calendar] == [99.95, 121.45]


def test_postgres_rate_price_migration_refuses_rounding_and_reverses(pg_session):
    migration = _rate_price_migration()
    suffix = uuid4().hex[:10]
    schema = f"rate_money_migration_{suffix}"
    connection = pg_session.connection()

    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
    connection.execute(text("""
        CREATE TABLE daily_rates (
            id INTEGER PRIMARY KEY,
            price DOUBLE PRECISION NOT NULL,
            price_cash DOUBLE PRECISION,
            price_transfer DOUBLE PRECISION,
            price_mercadopago DOUBLE PRECISION,
            price_paypal DOUBLE PRECISION,
            price_credit_card DOUBLE PRECISION
        )
    """))
    connection.execute(text("""
        CREATE TABLE price_periods (
            id INTEGER PRIMARY KEY,
            price_per_night DOUBLE PRECISION NOT NULL,
            price_cash DOUBLE PRECISION,
            price_transfer DOUBLE PRECISION,
            price_mercadopago DOUBLE PRECISION,
            price_paypal DOUBLE PRECISION,
            price_credit_card DOUBLE PRECISION,
            price_debit_card DOUBLE PRECISION,
            price_booking DOUBLE PRECISION,
            price_expedia DOUBLE PRECISION
        )
    """))
    connection.execute(text("""
        INSERT INTO daily_rates
            (id, price, price_cash, price_transfer, price_mercadopago, price_paypal, price_credit_card)
        VALUES (1, 55000.00, 55000.10, NULL, 56000.25, 58000.50, 57000.75)
    """))
    connection.execute(text("""
        INSERT INTO price_periods
            (id, price_per_night, price_cash, price_transfer, price_mercadopago, price_paypal,
             price_credit_card, price_debit_card, price_booking, price_expedia)
        VALUES (1, 72000.00, 72000.10, 72100.20, 72200.30, 72300.40,
                72400.50, 72500.60, 72600.70, 72700.80)
    """))
    connection.execute(text("""
        INSERT INTO price_periods (id, price_per_night, price_cash)
        VALUES (2, 1000.00, 1000.001)
    """))

    with (
        pytest.raises(RuntimeError, match="sub-cent precision"),
        pg_session.begin_nested(),
        Operations.context(MigrationContext.configure(connection)),
    ):
        migration.upgrade()

    daily_columns = {column["name"]: column["type"] for column in inspect(connection).get_columns("daily_rates", schema=schema)}
    assert isinstance(daily_columns["price"], Float)
    period_columns = {column["name"]: column["type"] for column in inspect(connection).get_columns("price_periods", schema=schema)}
    assert isinstance(period_columns["price_per_night"], Float)
    connection.execute(text('DELETE FROM "price_periods" WHERE id = 2'))

    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()

    for table_name, expected_columns in migration.RATE_PRICE_COLUMNS.items():
        columns = {column["name"]: column["type"] for column in inspect(connection).get_columns(table_name, schema=schema)}
        for name in expected_columns:
            assert isinstance(columns[name], Numeric)
            assert columns[name].scale == 2
    stored = connection.execute(text('SELECT price::text, price_cash::text FROM "daily_rates" WHERE id = 1')).one()
    assert Decimal(stored[0]) == Decimal("55000.00")
    assert Decimal(stored[1]) == Decimal("55000.10")

    with Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
    downgraded = inspect(connection).get_columns("price_periods", schema=schema)
    assert isinstance(next(column["type"] for column in downgraded if column["name"] == "price_per_night"), Float)

    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
    reupgraded = inspect(connection).get_columns("price_periods", schema=schema)
    assert isinstance(next(column["type"] for column in reupgraded if column["name"] == "price_per_night"), Numeric)
