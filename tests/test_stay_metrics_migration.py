"""SQLite contract test for persisted stay counts and deposit rule backfill."""
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20261018_operational_stay_metrics_and_deposit_rules.py"
)


def test_migration_backfills_nights_and_legacy_deposit_rules(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE hotel_configuration ("
                "id INTEGER PRIMARY KEY, deposit_percentage FLOAT NOT NULL, "
                "checkin_payment_policy TEXT NOT NULL)"
            )
            connection.exec_driver_sql(
                "INSERT INTO hotel_configuration VALUES (1, 25.0, 'free')"
            )
            connection.exec_driver_sql(
                "CREATE TABLE reservations (id INTEGER PRIMARY KEY, check_in_date DATE, check_out_date DATE)"
            )
            connection.exec_driver_sql(
                "INSERT INTO reservations VALUES (1, '2026-10-01', '2026-10-04')"
            )
            spec = importlib.util.spec_from_file_location("stay_metrics_migration", MIGRATION_PATH)
            assert spec and spec.loader
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

            migration.upgrade()
            assert connection.execute(
                sa.text("SELECT reserved_nights FROM reservations WHERE id=1")
            ).scalar_one() == 3
            rules = connection.execute(
                sa.text("SELECT deposit_policy_rules FROM hotel_configuration WHERE id=1")
            ).scalar_one()
            assert '"value": 25.0' in rules
            assert connection.execute(
                sa.text("SELECT checkin_payment_policy FROM hotel_configuration WHERE id=1")
            ).scalar_one() == "total"
            assert connection.execute(
                sa.text("SELECT used_nights FROM reservations WHERE id=1")
            ).scalar_one() is None

            migration.downgrade()
            assert "reserved_nights" not in {
                column["name"] for column in sa.inspect(connection).get_columns("reservations")
            }
            assert "deposit_policy_rules" not in {
                column["name"] for column in sa.inspect(connection).get_columns("hotel_configuration")
            }
    finally:
        engine.dispose()
