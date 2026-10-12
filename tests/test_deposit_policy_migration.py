"""SQLite contract for conservative deposit-policy migration defaults."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "3aaf546faec7_require_hotel_deposit_policy_.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("deposit_policy_confirmation", MIGRATION_PATH)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_existing_hotels_start_unconfirmed_and_migration_is_reversible(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE hotel_configuration (id INTEGER PRIMARY KEY, deposit_percentage FLOAT NOT NULL)"
            )
            connection.exec_driver_sql(
                "INSERT INTO hotel_configuration (id, deposit_percentage) VALUES (1, 30.0)"
            )
            migration = _load_migration()
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

            migration.upgrade()
            assert connection.execute(
                sa.text("SELECT deposit_policy_configured FROM hotel_configuration WHERE id = 1")
            ).scalar_one() == 0

            migration.downgrade()
            assert "deposit_policy_configured" not in {
                column["name"] for column in sa.inspect(connection).get_columns("hotel_configuration")
            }
    finally:
        engine.dispose()
