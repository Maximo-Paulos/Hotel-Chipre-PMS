"""SQLite migration coverage for separate FX rounding-credit ledger fields."""
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
    / "20261022_fx_credit_ledger.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("fx_rounding_credit_ledger_migration", MIGRATION_PATH)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_credit_ledger_migration_preserves_old_rows_and_constrains_credit_refunds(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE transactions ("
                "id INTEGER PRIMARY KEY, amount NUMERIC(12,2) NOT NULL, "
                "transaction_type VARCHAR(24) NOT NULL, tender_amount NUMERIC(12,2), "
                "CONSTRAINT ck_transaction_amount_nonzero CHECK (amount != 0))"
            )
            connection.exec_driver_sql(
                "INSERT INTO transactions (id, amount, transaction_type, tender_amount) "
                "VALUES (1, 100, 'partial_payment', 100)"
            )

        with engine.begin() as connection:
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.upgrade()
            columns = {column["name"] for column in sa.inspect(connection).get_columns("transactions")}
            assert {"rounding_credit_amount", "credit_refund_amount", "refund_component"} <= columns
            old_row = connection.execute(
                sa.text(
                    "SELECT amount, rounding_credit_amount, credit_refund_amount, refund_component "
                    "FROM transactions WHERE id = 1"
                )
            ).one()
            assert tuple(old_row) == (100, 0, 0, "payment")

            connection.execute(
                sa.text(
                    "INSERT INTO transactions "
                    "(id, amount, transaction_type, tender_amount, refund_component, credit_refund_amount) "
                    "VALUES (2, 0, 'refund', 0.10, 'rounding_credit', 0.10)"
                )
            )
            with pytest.raises(IntegrityError):
                connection.execute(
                    sa.text(
                        "INSERT INTO transactions "
                        "(id, amount, transaction_type, tender_amount) VALUES (3, 0, 'refund', 0.10)"
                    )
                )
            with pytest.raises(IntegrityError):
                connection.execute(
                    sa.text(
                        "INSERT INTO transactions "
                        "(id, amount, transaction_type, tender_amount, refund_component, credit_refund_amount) "
                        "VALUES (4, 0, 'refund', 0.11, 'rounding_credit', 0.10)"
                    )
                )

        with engine.begin() as connection:
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            with pytest.raises(RuntimeError, match="erase financial history"):
                migration.downgrade()
            connection.execute(sa.text("DELETE FROM transactions WHERE id = 2"))

        with engine.begin() as connection:
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.downgrade()
            columns = {column["name"] for column in sa.inspect(connection).get_columns("transactions")}
            assert not {"rounding_credit_amount", "credit_refund_amount", "refund_component"} & columns
            with pytest.raises(IntegrityError):
                connection.execute(
                    sa.text("INSERT INTO transactions (id, amount, transaction_type) VALUES (5, 0, 'refund')")
                )
    finally:
        engine.dispose()
