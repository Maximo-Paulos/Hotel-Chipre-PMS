from pathlib import Path
import importlib.util

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20261016_fx_direction_markets.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("fx_direction_markets_migration", MIGRATION_PATH)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _market_columns(connection):
    return {
        column["name"]
        for column in sa.inspect(connection).get_columns("hotel_configuration")
        if column["name"].endswith("_rate_type")
    } - {"fx_conversion_rate_type"}


def test_fx_direction_market_migration_preserves_global_market_and_guards_downgrade(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    expected_columns = {"fx_usd_to_ars_rate_type", "fx_ars_to_usd_rate_type"}
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE hotel_configuration ("
                "id INTEGER PRIMARY KEY, fx_conversion_rate_type VARCHAR(20) NOT NULL)"
            )
            connection.exec_driver_sql(
                "INSERT INTO hotel_configuration (id, fx_conversion_rate_type) "
                "VALUES (1, 'oficial'), (2, 'blue')"
            )

        with engine.begin() as connection:
            monkeypatch.setattr(
                migration,
                "op",
                Operations(MigrationContext.configure(connection)),
            )
            migration.upgrade()
            assert _market_columns(connection) == expected_columns
            assert connection.execute(
                sa.text(
                    "SELECT fx_usd_to_ars_rate_type, fx_ars_to_usd_rate_type "
                    "FROM hotel_configuration ORDER BY id"
                )
            ).all() == [("oficial", "oficial"), ("blue", "blue")]

            with pytest.raises(IntegrityError):
                connection.execute(
                    sa.text(
                        "UPDATE hotel_configuration SET fx_usd_to_ars_rate_type = 'tarjeta' WHERE id = 1"
                    )
                )
            connection.execute(
                sa.text(
                    "UPDATE hotel_configuration SET fx_usd_to_ars_rate_type = 'oficial' "
                    "WHERE id = 2"
                )
            )

        with engine.begin() as connection:
            monkeypatch.setattr(
                migration,
                "op",
                Operations(MigrationContext.configure(connection)),
            )
            with pytest.raises(RuntimeError, match="different from its global reference"):
                migration.downgrade()

        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE hotel_configuration SET fx_usd_to_ars_rate_type = 'blue' "
                    "WHERE id = 2"
                )
            )
            monkeypatch.setattr(
                migration,
                "op",
                Operations(MigrationContext.configure(connection)),
            )
            migration.downgrade()
            assert _market_columns(connection) == set()
            assert connection.execute(
                sa.text("SELECT COUNT(*) FROM hotel_configuration")
            ).scalar_one() == 2
    finally:
        engine.dispose()
