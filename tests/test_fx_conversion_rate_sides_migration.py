"""SQLite migration coverage for configurable USD conversion sides."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20261016_fx_conversion_rate_sides.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("fx_conversion_rate_sides_migration", MIGRATION_PATH)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _side_columns(connection):
    return {
        column["name"]
        for column in sa.inspect(connection).get_columns("hotel_configuration")
        if column["name"].endswith("_rate_side")
    }


def test_fx_conversion_side_migration_backfills_defaults_and_round_trips_safely(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    expected_columns = {"fx_usd_to_ars_rate_side", "fx_ars_to_usd_rate_side"}
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE hotel_configuration ("
                "id INTEGER PRIMARY KEY, fx_conversion_rate_type VARCHAR(20) NOT NULL)"
            )
            connection.exec_driver_sql(
                "INSERT INTO hotel_configuration (id, fx_conversion_rate_type) VALUES (1, 'oficial')"
            )

        with engine.begin() as connection:
            monkeypatch.setattr(
                migration,
                "op",
                Operations(MigrationContext.configure(connection)),
            )
            migration.upgrade()
            assert _side_columns(connection) == expected_columns
            assert connection.execute(
                sa.text(
                    "SELECT fx_usd_to_ars_rate_side, fx_ars_to_usd_rate_side "
                    "FROM hotel_configuration WHERE id = 1"
                )
            ).one() == ("venta", "venta")
            connection.execute(
                sa.text("INSERT INTO hotel_configuration (id, fx_conversion_rate_type) VALUES (2, 'blue')")
            )
            assert connection.execute(
                sa.text(
                    "SELECT fx_usd_to_ars_rate_side, fx_ars_to_usd_rate_side "
                    "FROM hotel_configuration WHERE id = 2"
                )
            ).one() == ("venta", "venta")
            with pytest.raises(IntegrityError):
                connection.execute(
                    sa.text(
                        "UPDATE hotel_configuration SET fx_usd_to_ars_rate_side = 'medio' WHERE id = 2"
                    )
                )
            connection.execute(
                sa.text("UPDATE hotel_configuration SET fx_usd_to_ars_rate_side = 'compra' WHERE id = 2")
            )

        with engine.begin() as connection:
            monkeypatch.setattr(
                migration,
                "op",
                Operations(MigrationContext.configure(connection)),
            )
            with pytest.raises(RuntimeError, match="non-default selection"):
                migration.downgrade()

        with engine.begin() as connection:
            connection.execute(
                sa.text("UPDATE hotel_configuration SET fx_usd_to_ars_rate_side = 'venta' WHERE id = 2")
            )
            monkeypatch.setattr(
                migration,
                "op",
                Operations(MigrationContext.configure(connection)),
            )
            migration.downgrade()
            assert _side_columns(connection) == set()
            assert connection.execute(
                sa.text("SELECT COUNT(*) FROM hotel_configuration")
            ).scalar_one() == 2

        with engine.begin() as connection:
            monkeypatch.setattr(
                migration,
                "op",
                Operations(MigrationContext.configure(connection)),
            )
            migration.upgrade()
            assert _side_columns(connection) == expected_columns
            assert connection.execute(
                sa.text(
                    "SELECT fx_usd_to_ars_rate_side, fx_ars_to_usd_rate_side "
                    "FROM hotel_configuration WHERE id = 1"
                )
            ).one() == ("venta", "venta")
    finally:
        engine.dispose()
