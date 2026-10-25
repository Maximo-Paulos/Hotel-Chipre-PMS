"""SQLite migration coverage for separate cash tender, change, and tip amounts."""

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
    / "20261023_cash_tender_change.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "cash_tender_change_migration", MIGRATION_PATH
    )
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _run(migration, connection, action):
    migration.op = Operations(MigrationContext.configure(connection))
    getattr(migration, action)()


def test_cash_tender_change_migration_preserves_legacy_rows_and_validates_pairs():
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE transactions ("
                "id INTEGER PRIMARY KEY, amount NUMERIC(12,2) NOT NULL, "
                "gross_amount NUMERIC(12,2), "
                "transaction_type VARCHAR(24) NOT NULL, "
                "payment_method VARCHAR(24) NOT NULL)"
            )
            connection.exec_driver_sql(
                "CREATE TABLE reservation_group_payment_batches ("
                "id INTEGER PRIMARY KEY, received_amount NUMERIC(12,2) NOT NULL, "
                "payment_method VARCHAR(24) NOT NULL)"
            )
            connection.exec_driver_sql(
                "INSERT INTO transactions "
                "(id, amount, transaction_type, payment_method) "
                "VALUES (1, 100, 'partial_payment', 'cash')"
            )
            connection.exec_driver_sql(
                "INSERT INTO reservation_group_payment_batches "
                "(id, received_amount, payment_method) "
                "VALUES (1, 100, 'cash')"
            )

        with engine.begin() as connection:
            _run(migration, connection, "upgrade")
            for table in ("transactions", "reservation_group_payment_batches"):
                columns = {
                    column["name"]: column
                    for column in sa.inspect(connection).get_columns(table)
                }
                expected_columns = {"cash_received_amount", "cash_change_amount", "cash_tip_amount"}
                if table == "reservation_group_payment_batches":
                    expected_columns.add("gross_amount")
                assert expected_columns <= columns.keys()
                assert columns["cash_received_amount"]["nullable"] is True
                assert columns["cash_change_amount"]["nullable"] is True
                assert columns["cash_received_amount"]["type"].precision == 12
                assert columns["cash_received_amount"]["type"].scale == 2
                assert columns["cash_tip_amount"]["nullable"] is False

            assert connection.execute(
                sa.text(
                    "SELECT cash_received_amount, cash_change_amount, cash_tip_amount "
                    "FROM transactions WHERE id = 1"
                )
            ).one() == (None, None, 0)
            assert connection.execute(
                sa.text(
                    "SELECT cash_received_amount, cash_change_amount, cash_tip_amount, gross_amount "
                    "FROM reservation_group_payment_batches WHERE id = 1"
                )
            ).one() == (None, None, 0, None)

            connection.execute(
                sa.text(
                    "INSERT INTO transactions "
                    "(id, amount, transaction_type, payment_method, "
                    "cash_received_amount, cash_change_amount) "
                    "VALUES (2, 46, 'partial_payment', 'cash', 50, 4)"
                )
            )
            # SQLite NUMERIC values use floating-point arithmetic for CHECKs;
            # round the equality to the payment precision in both dialects.
            connection.execute(
                sa.text(
                    "INSERT INTO transactions "
                    "(id, amount, gross_amount, transaction_type, payment_method, "
                    "cash_received_amount, cash_change_amount) "
                    "VALUES (11, 0.10, 0.10, 'partial_payment', 'cash', 0.15, 0.05)"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO transactions "
                    "(id, amount, gross_amount, transaction_type, payment_method, "
                    "cash_received_amount, cash_change_amount, cash_tip_amount) "
                    "VALUES (12, 46, 46, 'partial_payment', 'cash', 50, 2, 2)"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO reservation_group_payment_batches "
                    "(id, received_amount, payment_method, gross_amount, "
                    "cash_received_amount, cash_change_amount, cash_tip_amount) "
                    "VALUES (2, 46, 'cash', 46, 50, 2, 2)"
                )
            )

            invalid_transactions = (
                (3, "partial_payment", "cash", None, 0),
                (4, "partial_payment", "cash", 50, -1),
                (5, "partial_payment", "cash", 50, 51),
                (6, "partial_payment", "credit_card", 50, 0),
                (7, "refund", "cash", 50, 0),
                (8, "partial_payment", "cash", 0, 0),
            )
            for (
                row_id,
                transaction_type,
                payment_method,
                received,
                change,
            ) in invalid_transactions:
                with pytest.raises(IntegrityError):
                    connection.execute(
                        sa.text(
                            "INSERT INTO transactions "
                            "(id, amount, transaction_type, payment_method, "
                            "cash_received_amount, cash_change_amount) "
                            "VALUES (:id, 1, :transaction_type, "
                            ":payment_method, :received, :change)"
                        ),
                        {
                            "id": row_id,
                            "transaction_type": transaction_type,
                            "payment_method": payment_method,
                            "received": received,
                            "change": change,
                        },
                    )

            with pytest.raises(IntegrityError):
                connection.execute(
                    sa.text(
                        "INSERT INTO transactions "
                        "(id, amount, gross_amount, transaction_type, payment_method, "
                        "cash_received_amount, cash_change_amount) "
                        "VALUES (9, 46000, 46000, 'partial_payment', 'cash', 45000, 0)"
                    )
                )
            with pytest.raises(IntegrityError):
                connection.execute(
                    sa.text(
                        "INSERT INTO transactions "
                        "(id, amount, gross_amount, transaction_type, payment_method, "
                        "cash_received_amount, cash_change_amount, cash_tip_amount) "
                        "VALUES (13, 46, 46, 'partial_payment', 'cash', 50, 0, 5)"
                    )
                )
            with pytest.raises(IntegrityError):
                connection.execute(
                    sa.text(
                        "INSERT INTO transactions "
                        "(id, amount, gross_amount, transaction_type, payment_method, "
                        "cash_received_amount, cash_change_amount) "
                        "VALUES (10, 46000, 46000, 'partial_payment', 'cash', 50000, 3000)"
                    )
                )

            invalid_batches = (
                (3, "cash", None, 0),
                (4, "cash", 50, -1),
                (5, "cash", 50, 51),
                (6, "credit_card", 50, 0),
                (7, "cash", 0, 0),
            )
            for row_id, payment_method, received, change in invalid_batches:
                with pytest.raises(IntegrityError):
                    connection.execute(
                        sa.text(
                            "INSERT INTO reservation_group_payment_batches "
                            "(id, received_amount, payment_method, "
                            "cash_received_amount, cash_change_amount) "
                            "VALUES (:id, 1, :payment_method, :received, :change)"
                        ),
                        {
                            "id": row_id,
                            "payment_method": payment_method,
                            "received": received,
                            "change": change,
                        },
                    )
            with pytest.raises(IntegrityError):
                connection.execute(
                    sa.text(
                        "INSERT INTO reservation_group_payment_batches "
                        "(id, received_amount, payment_method, gross_amount, "
                        "cash_received_amount, cash_change_amount, cash_tip_amount) "
                        "VALUES (8, 46, 'cash', 46, 50, 0, 5)"
                    )
                )

        with engine.begin() as connection:
            with pytest.raises(RuntimeError, match="erase financial history"):
                _run(migration, connection, "downgrade")
            connection.execute(
                sa.text(
                    "UPDATE transactions SET cash_received_amount = NULL, "
                    "cash_change_amount = NULL, cash_tip_amount = 0 WHERE id IN (2, 11, 12)"
                )
            )
            connection.execute(
                sa.text(
                    "UPDATE reservation_group_payment_batches "
                    "SET cash_received_amount = NULL, cash_change_amount = NULL, "
                    "cash_tip_amount = 0, gross_amount = NULL "
                    "WHERE id = 2"
                )
            )

        with engine.begin() as connection:
            _run(migration, connection, "downgrade")
            for table in ("transactions", "reservation_group_payment_batches"):
                columns = {
                    column["name"]
                    for column in sa.inspect(connection).get_columns(table)
                }
                assert not {"cash_received_amount", "cash_change_amount", "cash_tip_amount"} & columns
                if table == "reservation_group_payment_batches":
                    assert "gross_amount" not in columns

        with engine.begin() as connection:
            _run(migration, connection, "upgrade")
            for table in ("transactions", "reservation_group_payment_batches"):
                columns = {
                    column["name"]
                    for column in sa.inspect(connection).get_columns(table)
                }
                expected_columns = {"cash_received_amount", "cash_change_amount", "cash_tip_amount"}
                if table == "reservation_group_payment_batches":
                    expected_columns.add("gross_amount")
                assert expected_columns <= columns
    finally:
        engine.dispose()
