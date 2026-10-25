"""SQLite coverage for the persisted foreign-payment FX rounding policy."""
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
    / "20261022_fx_rounding_policy.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("fx_rounding_policy_migration", MIGRATION_PATH)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_fx_rounding_policy_migration_defaults_existing_hotels_and_checks_allowed_policies(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE hotel_configuration (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO hotel_configuration (id) VALUES (1)")

        with engine.begin() as connection:
            monkeypatch.setattr(
                migration,
                "op",
                Operations(MigrationContext.configure(connection)),
            )
            migration.upgrade()
            assert "fx_rounding_policy" in {
                column["name"] for column in sa.inspect(connection).get_columns("hotel_configuration")
            }
            assert connection.execute(
                sa.text("SELECT fx_rounding_policy FROM hotel_configuration WHERE id = 1")
            ).scalar_one() == "keep_remainder"

            connection.execute(sa.text("INSERT INTO hotel_configuration (id) VALUES (2)"))
            assert connection.execute(
                sa.text("SELECT fx_rounding_policy FROM hotel_configuration WHERE id = 2")
            ).scalar_one() == "keep_remainder"
            for policy in ("round_up", "round_down", "nearest_ten", "exact", "keep_remainder"):
                connection.execute(
                    sa.text("UPDATE hotel_configuration SET fx_rounding_policy = :policy WHERE id = 2"),
                    {"policy": policy},
                )
            with pytest.raises(IntegrityError):
                connection.execute(
                    sa.text("UPDATE hotel_configuration SET fx_rounding_policy = 'nearest_hundred' WHERE id = 2")
                )

        with engine.begin() as connection:
            monkeypatch.setattr(
                migration,
                "op",
                Operations(MigrationContext.configure(connection)),
            )
            migration.downgrade()
            assert "fx_rounding_policy" not in {
                column["name"] for column in sa.inspect(connection).get_columns("hotel_configuration")
            }
            assert connection.execute(sa.text("SELECT COUNT(*) FROM hotel_configuration")).scalar_one() == 2
    finally:
        engine.dispose()
