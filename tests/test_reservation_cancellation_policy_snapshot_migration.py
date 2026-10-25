"""SQLite coverage for the reversible cancellation-policy snapshot column."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "ebaf9d3d2baa_reservation_cancellation_policy_snapshot.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "reservation_cancellation_policy_snapshot_migration", MIGRATION_PATH
    )
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _run(migration, connection, action):
    migration.op = Operations(MigrationContext.configure(connection))
    getattr(migration, action)()


def test_cancellation_policy_snapshot_migration_is_nullable_reversible_and_does_not_backfill():
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE reservations (id INTEGER PRIMARY KEY, hotel_id INTEGER NOT NULL)"
            )
            connection.exec_driver_sql("INSERT INTO reservations (id, hotel_id) VALUES (1, 7)")
            _run(migration, connection, "upgrade")

            snapshot_column = next(
                column
                for column in sa.inspect(connection).get_columns("reservations")
                if column["name"] == "cancellation_policy_snapshot"
            )
            assert snapshot_column["nullable"] is True
            assert isinstance(snapshot_column["type"], sa.JSON)
            assert connection.execute(
                sa.text("SELECT cancellation_policy_snapshot FROM reservations WHERE id = 1")
            ).scalar_one() is None

        with engine.begin() as connection:
            _run(migration, connection, "downgrade")
            assert "cancellation_policy_snapshot" not in {
                column["name"] for column in sa.inspect(connection).get_columns("reservations")
            }
            assert connection.execute(sa.text("SELECT hotel_id FROM reservations WHERE id = 1")).scalar_one() == 7
    finally:
        engine.dispose()
