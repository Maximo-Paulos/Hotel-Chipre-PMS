"""SQLite migration coverage for the fixed housekeeping checklist schema."""
from __future__ import annotations

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
    / "20261023_housekeeping_checklists.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("housekeeping_checklists_migration", MIGRATION_PATH)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _run(migration, connection, action):
    migration.op = Operations(MigrationContext.configure(connection))
    getattr(migration, action)()


def _create_referenced_tables(connection):
    connection.exec_driver_sql("CREATE TABLE hotel_configuration (id INTEGER PRIMARY KEY)")
    connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
    connection.exec_driver_sql(
        "CREATE TABLE rooms (id INTEGER PRIMARY KEY, hotel_id INTEGER NOT NULL, UNIQUE(hotel_id, id))"
    )
    connection.exec_driver_sql(
        "CREATE TABLE reservations (id INTEGER PRIMARY KEY, hotel_id INTEGER NOT NULL, UNIQUE(hotel_id, id))"
    )
    connection.exec_driver_sql("INSERT INTO hotel_configuration (id) VALUES (1)")
    connection.exec_driver_sql("INSERT INTO rooms (id, hotel_id) VALUES (10, 1)")
    connection.exec_driver_sql("INSERT INTO reservations (id, hotel_id) VALUES (20, 1)")


def test_housekeeping_checklist_migration_creates_constrained_tenant_tables_and_guards_downgrade():
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    try:
        with engine.begin() as connection:
            _create_referenced_tables(connection)
            _run(migration, connection, "upgrade")
            assert {"housekeeping_checklists", "housekeeping_checklist_items"} <= {
                table_name for table_name in sa.inspect(connection).get_table_names()
            }
            assert {"hotel_id", "room_id", "reservation_id", "version"} <= {
                column["name"]
                for column in sa.inspect(connection).get_columns("housekeeping_checklists")
            }

        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO housekeeping_checklists "
                    "(id, hotel_id, room_id, reservation_id, status, version) "
                    "VALUES (1, 1, 10, 20, 'open', 1)"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO housekeeping_checklist_items "
                    "(hotel_id, checklist_id, code, label, completed) "
                    "VALUES (1, 1, 'change_sheets', 'Cambiar sábanas', false)"
                )
            )

        with engine.begin() as connection, pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO housekeeping_checklist_items "
                    "(hotel_id, checklist_id, code, label, completed) "
                    "VALUES (1, 1, 'unknown', 'Texto inválido', false)"
                )
            )

        with engine.begin() as connection, pytest.raises(
            RuntimeError, match="checklist history exists"
        ):
            _run(migration, connection, "downgrade")

        with engine.begin() as connection:
            connection.execute(sa.text("DELETE FROM housekeeping_checklist_items"))
            connection.execute(sa.text("DELETE FROM housekeeping_checklists"))
        with engine.begin() as connection:
            _run(migration, connection, "downgrade")
            table_names = sa.inspect(connection).get_table_names()
            assert "housekeeping_checklists" not in table_names
            assert "housekeeping_checklist_items" not in table_names
    finally:
        engine.dispose()
