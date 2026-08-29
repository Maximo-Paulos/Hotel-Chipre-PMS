"""Migration coverage for the deduplication sweep."""

from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy import create_engine, text

from tests.migration_helpers import insert_historical_hotel_config


def _alembic(cwd: str, db_path: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=cwd,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_category_pricing_rows_are_folded_into_hotel_scoped_price_periods(tmp_path):
    repo_root = os.path.dirname(os.path.dirname(__file__))
    db_path = str(tmp_path / "category-pricing.db")
    _alembic(repo_root, db_path, "upgrade", "3bc5882f756d")

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        insert_historical_hotel_config(engine, 9001)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO room_categories "
                    "(id, hotel_id, name, code, description, base_price_per_night, "
                    "variable_cost_per_night, max_occupancy, amenities) "
                    "VALUES (901, 9001, 'Suite', 'STE', 'Balcon', 100, 20, 4, 'wifi')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO category_pricing "
                    "(category_id, price_cash, price_transfer, price_mercadopago, "
                    "price_paypal, price_credit_card, price_debit_card, "
                    "price_booking, price_expedia) "
                    "VALUES (901, 120, 130, 135, 140, 145, 146, 150, 155)"
                )
            )
    finally:
        engine.dispose()

    _alembic(repo_root, db_path, "upgrade", "head")
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            legacy = connection.execute(
                text("SELECT COUNT(*) FROM category_pricing_legacy")
            ).scalar_one()
            period = connection.execute(
                text(
                    "SELECT hotel_id, category_id, price_per_night, price_cash, "
                    "price_transfer, price_booking, price_expedia, priority "
                    "FROM price_periods WHERE hotel_id = 9001 AND category_id = 901"
                )
            ).mappings().one()
            assert legacy == 1
            assert period == {
                "hotel_id": 9001,
                "category_id": 901,
                "price_per_night": 120.0,
                "price_cash": 120.0,
                "price_transfer": 130.0,
                "price_booking": 150.0,
                "price_expedia": 155.0,
                "priority": -100000,
            }
    finally:
        engine.dispose()
