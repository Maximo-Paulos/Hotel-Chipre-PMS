"""SQLite contract test for the new manual-payment/check-in-policy migration."""

import importlib.util
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260927_manual_payments_checkin_policy.py"
)
DATA_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260927_ota_credit_backfill.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("manual_checkin_migration", MIGRATION_PATH)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _load_data_migration():
    spec = importlib.util.spec_from_file_location("ota_credit_data_migration", DATA_MIGRATION_PATH)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_migration_backfills_default_policy_and_is_idempotent(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE hotel_configuration (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO hotel_configuration (id) VALUES (7)")
            connection.exec_driver_sql(
                "CREATE TABLE transactions (id INTEGER PRIMARY KEY, hotel_id INTEGER, "
                "reservation_id INTEGER, payment_method TEXT, UNIQUE(hotel_id, id))"
            )
            connection.exec_driver_sql(
                "INSERT INTO transactions (id, hotel_id, reservation_id, payment_method) "
                "VALUES (11, 7, 8, 'credit_card')"
            )
            connection.exec_driver_sql(
                "CREATE TABLE role_permission_defaults "
                "(id INTEGER PRIMARY KEY, role TEXT NOT NULL, permission_code TEXT NOT NULL, allowed BOOLEAN NOT NULL)"
            )
            connection.exec_driver_sql(
                "INSERT INTO role_permission_defaults (role, permission_code, allowed) VALUES "
                "('manager', 'reservation:charge', 0), ('manager', 'cash:operate', 0), "
                "('owner', 'reservation:charge', 0), ('owner', 'cash:operate', 0), "
                "('housekeeping', 'whatsapp:inbox:view', 1), ('housekeeping', 'whatsapp:note:manage', 1)"
            )

            migration = _load_migration()
            data_migration = _load_data_migration()
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            monkeypatch.setattr(data_migration, "op", Operations(MigrationContext.configure(connection)))

            migration.upgrade()
            migration.upgrade()
            data_migration.upgrade()
            data_migration.upgrade()

            assert connection.execute(
                sa.text("SELECT checkin_payment_policy FROM hotel_configuration WHERE id = 7")
            ).scalar_one() == "deposit"
            assert connection.execute(
                sa.text("SELECT manual_reference FROM transactions WHERE id = 11")
            ).scalar_one() is None
            transaction_columns = {
                column["name"] for column in sa.inspect(connection).get_columns("transactions")
            }
            assert {"refund_of_transaction_id", "refund_reason"}.issubset(transaction_columns)
            # The production migration adds the self-FK on PostgreSQL. SQLite
            # uses Base.metadata in model tests; Alembic skips this FK here to
            # avoid a foreign-key failure during its required table rebuild.
            assert not any(
                fk["name"] == "fk_transactions_refund_source_same_hotel"
                for fk in sa.inspect(connection).get_foreign_keys("transactions")
            )
            with pytest.raises(sa.exc.IntegrityError):
                with connection.begin_nested():
                    connection.exec_driver_sql(
                        "INSERT INTO transactions "
                        "(id, hotel_id, reservation_id, payment_method, manual_reference) "
                        "VALUES (12, 7, 8, 'credit_card', 'POS-1')"
                    )
                    connection.exec_driver_sql(
                        "INSERT INTO transactions "
                        "(id, hotel_id, reservation_id, payment_method, manual_reference) "
                        "VALUES (13, 7, 9, 'credit_card', 'pos-1')"
                    )
            manager_defaults = connection.execute(
                sa.text(
                    "SELECT permission_code, allowed FROM role_permission_defaults "
                    "WHERE role = 'manager' ORDER BY permission_code"
                )
            ).all()
            assert manager_defaults == [("cash:operate", True), ("reservation:charge", True)]
            owner_defaults = connection.execute(
                sa.text(
                    "SELECT permission_code, allowed FROM role_permission_defaults "
                    "WHERE role = 'owner' ORDER BY permission_code"
                )
            ).all()
            assert owner_defaults == [("cash:operate", False), ("reservation:charge", False)]
            housekeeping_defaults = connection.execute(
                sa.text(
                    "SELECT permission_code, allowed FROM role_permission_defaults "
                    "WHERE role = 'housekeeping' ORDER BY permission_code"
                )
            ).all()
            assert housekeeping_defaults == [("whatsapp:inbox:view", False), ("whatsapp:note:manage", False)]
            with pytest.raises(sa.exc.IntegrityError):
                with connection.begin_nested():
                    connection.exec_driver_sql(
                        "UPDATE hotel_configuration SET checkin_payment_policy = 'unknown' WHERE id = 7"
                    )

            data_migration.downgrade()
            migration.downgrade()
            hotel_columns = {column["name"] for column in sa.inspect(connection).get_columns("hotel_configuration")}
            transaction_columns = {column["name"] for column in sa.inspect(connection).get_columns("transactions")}
            assert "checkin_payment_policy" not in hotel_columns
            assert "manual_reference" not in transaction_columns
            assert "refund_of_transaction_id" not in transaction_columns
            assert "refund_reason" not in transaction_columns
            assert connection.execute(
                sa.text(
                    "SELECT allowed FROM role_permission_defaults "
                    "WHERE role = 'manager' AND permission_code = 'cash:operate'"
                )
            ).scalar_one() == 0
            assert connection.execute(
                sa.text(
                    "SELECT allowed FROM role_permission_defaults "
                    "WHERE role = 'housekeeping' AND permission_code = 'whatsapp:inbox:view'"
                )
            ).scalar_one() == 1
    finally:
        engine.dispose()


def test_migration_separates_legacy_ota_credit_and_requires_reconfirmation(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE reservations (id INTEGER PRIMARY KEY, hotel_id INTEGER, amount_paid NUMERIC, source_provider_code TEXT, external_id TEXT)")
            connection.exec_driver_sql(
                "INSERT INTO reservations (id, hotel_id, amount_paid, source_provider_code, external_id) "
                "VALUES (8, 7, 100.00, 'booking', 'BKG-8')"
            )
            connection.exec_driver_sql(
                "CREATE TABLE transactions (id INTEGER PRIMARY KEY, hotel_id INTEGER, reservation_id INTEGER, "
                "amount NUMERIC, transaction_type TEXT, status TEXT, payment_method TEXT)"
            )
            connection.exec_driver_sql(
                "INSERT INTO transactions (id, hotel_id, reservation_id, amount, transaction_type, status, payment_method) "
                "VALUES (1, 7, 8, 25.00, 'partial_payment', 'completed', 'credit_card'), "
                "(2, 7, 8, 75.00, 'partial_payment', 'pending', 'credit_card')"
            )
            migration = _load_migration()
            data_migration = _load_data_migration()
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            monkeypatch.setattr(data_migration, "op", Operations(MigrationContext.configure(connection)))

            migration.upgrade()
            data_migration.upgrade()
            data_migration.upgrade()

            row = connection.execute(
                sa.text(
                    "SELECT amount_paid, external_paid_amount, external_paid_confirmed, "
                    "external_paid_ever_confirmed, external_paid_reference "
                    "FROM reservations WHERE id = 8"
                )
            ).one()
            assert Decimal(str(row.amount_paid)) == Decimal("25.00")
            assert Decimal(str(row.external_paid_amount)) == Decimal("75.00")
            assert not row.external_paid_confirmed
            assert not row.external_paid_ever_confirmed
            assert row.external_paid_reference is None

            with pytest.raises(RuntimeError, match="external OTA payment evidence exists"):
                data_migration.downgrade()
    finally:
        engine.dispose()


def test_ota_backfill_locks_row_before_recomputing_completed_ledger(monkeypatch):
    """A payment committed after candidate discovery must be in the backfill snapshot."""
    migration = _load_data_migration()

    class Result:
        def __init__(self, rows=(), scalar_value=None):
            self.rows = list(rows)
            self.scalar_value = scalar_value

        def all(self):
            return self.rows

        def first(self):
            return self.rows[0] if self.rows else None

        def scalar(self):
            return self.scalar_value

    class Connection:
        dialect = SimpleNamespace(name="postgresql")

        def __init__(self):
            self.statements = []
            self.update_params = None

        def execute(self, statement, params=None):
            sql = str(statement)
            self.statements.append(sql)
            if sql.startswith("SELECT id, hotel_id FROM reservations"):
                # This is only the candidate list. The payment commits after
                # discovery and before the row lock is acquired below.
                return Result(rows=[(8, 7)])
            if sql.startswith("SELECT id, hotel_id, amount_paid FROM reservations"):
                assert sql.endswith("FOR UPDATE")
                # Fresh cache now includes the concurrently completed payment.
                return Result(rows=[(8, 7, Decimal("125.00"))])
            if sql.startswith("SELECT SUM(CASE WHEN transaction_type"):
                # This per-row aggregate is queried after the lock and sees the
                # same completed payment; the old batch snapshot would be stale.
                return Result(scalar_value=Decimal("100.00"))
            if sql.startswith("UPDATE reservations SET external_paid_amount"):
                self.update_params = params
                return Result()
            raise AssertionError(f"Unexpected migration SQL: {sql}")

    connection = Connection()
    monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=lambda: connection))
    monkeypatch.setattr(migration, "_has_columns", lambda table, columns: True)

    migration._backfill_external_ota_credits()

    lock_index = next(i for i, sql in enumerate(connection.statements) if "FOR UPDATE" in sql)
    ledger_index = next(i for i, sql in enumerate(connection.statements) if sql.startswith("SELECT SUM(CASE"))
    update_index = next(i for i, sql in enumerate(connection.statements) if sql.startswith("UPDATE reservations"))
    assert lock_index < ledger_index < update_index
    assert connection.update_params["amount_paid"] == Decimal("100.00")
    assert connection.update_params["external_paid_amount"] == Decimal("25.00")
