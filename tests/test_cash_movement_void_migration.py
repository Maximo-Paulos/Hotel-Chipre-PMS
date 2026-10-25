"""SQLite regression coverage for auditable cash-movement voids."""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20261024_cash_movement_voids.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("cash_movement_void_migration", MIGRATION_PATH)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _run(migration, connection, action: str) -> None:
    migration.op = Operations(MigrationContext.configure(connection))
    getattr(migration, action)()


def _create_minimal_schema(connection) -> None:
    connection.exec_driver_sql(
        "CREATE TABLE payment_corrections (id INTEGER NOT NULL, hotel_id INTEGER NOT NULL, "
        "UNIQUE (hotel_id, id))"
    )
    connection.exec_driver_sql(
        "CREATE TABLE cash_movements (id INTEGER PRIMARY KEY, hotel_id INTEGER NOT NULL, "
        "session_id INTEGER NOT NULL, transaction_id INTEGER, amount NUMERIC(12, 2) NOT NULL)"
    )


def test_cash_movement_void_migration_round_trips_without_history():
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    try:
        with engine.begin() as connection:
            _create_minimal_schema(connection)
            _run(migration, connection, "upgrade")
            columns = {column["name"] for column in sa.inspect(connection).get_columns("cash_movements")}
            assert "voided_at" in columns
            assert "voided_by_payment_correction_id" in columns

            _run(migration, connection, "downgrade")
            columns = {column["name"] for column in sa.inspect(connection).get_columns("cash_movements")}
            assert "voided_at" not in columns
            assert "voided_by_payment_correction_id" not in columns
    finally:
        engine.dispose()


def test_cash_movement_void_migration_refuses_to_drop_void_history():
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    try:
        with engine.begin() as connection:
            _create_minimal_schema(connection)
            _run(migration, connection, "upgrade")
            connection.exec_driver_sql("INSERT INTO payment_corrections (id, hotel_id) VALUES (1, 1)")
            connection.exec_driver_sql(
                "INSERT INTO cash_movements "
                "(id, hotel_id, session_id, amount, voided_at, voided_by_payment_correction_id) "
                "VALUES (1, 1, 1, 50, '2026-10-24 12:00:00', 1)"
            )

            with pytest.raises(RuntimeError, match="voided movements exist"):
                _run(migration, connection, "downgrade")

            columns = {column["name"] for column in sa.inspect(connection).get_columns("cash_movements")}
            assert "voided_at" in columns
    finally:
        engine.dispose()
