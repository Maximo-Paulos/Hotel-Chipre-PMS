"""SQLite regression coverage for the reversible payment-correction migration."""

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
    / "20261024_atomic_payment_corrections.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("atomic_payment_correction_migration", MIGRATION_PATH)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _run(migration, connection, action: str) -> None:
    migration.op = Operations(MigrationContext.configure(connection))
    getattr(migration, action)()


def _create_minimal_schema(connection, *, include_manual_reference_index: bool = True) -> None:
    connection.exec_driver_sql("CREATE TABLE hotel_configuration (id INTEGER PRIMARY KEY)")
    connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
    connection.exec_driver_sql(
        "CREATE TABLE reservations (id INTEGER PRIMARY KEY, hotel_id INTEGER NOT NULL, "
        "UNIQUE (hotel_id, id))"
    )
    connection.exec_driver_sql(
        "CREATE TABLE transactions (id INTEGER PRIMARY KEY, hotel_id INTEGER NOT NULL, "
        "reservation_id INTEGER NOT NULL, payment_method VARCHAR(24) NOT NULL, "
        "status VARCHAR(24) NOT NULL, manual_reference VARCHAR(120), "
        "UNIQUE (hotel_id, id))"
    )
    if include_manual_reference_index:
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX uq_transactions_manual_reference_hotel_method "
            "ON transactions (hotel_id, payment_method, lower(manual_reference)) "
            "WHERE manual_reference IS NOT NULL"
        )
    connection.exec_driver_sql(
        "CREATE TABLE permissions (code VARCHAR(100) PRIMARY KEY, description VARCHAR(255), "
        "critical BOOLEAN NOT NULL, step_up_required BOOLEAN NOT NULL, delegable BOOLEAN NOT NULL)"
    )
    connection.exec_driver_sql(
        "CREATE TABLE role_permission_defaults (role VARCHAR(50), permission_code VARCHAR(100), "
        "allowed BOOLEAN NOT NULL, PRIMARY KEY (role, permission_code))"
    )
    for table_name in (
        "hotel_permission_overrides",
        "user_permission_overrides",
        "temporary_action_grants",
        "action_step_up_ticket_uses",
    ):
        connection.exec_driver_sql(
            f"CREATE TABLE {table_name} (permission_code VARCHAR(100) NOT NULL)"
        )


def _manual_reference_index_sql(connection) -> str | None:
    return connection.exec_driver_sql(
        "SELECT sql FROM sqlite_master "
        "WHERE type = 'index' "
        "AND name = 'uq_transactions_manual_reference_hotel_method'"
    ).scalar_one_or_none()


def test_payment_correction_migration_round_trips_when_history_is_empty():
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    try:
        with engine.begin() as connection:
            _create_minimal_schema(connection)
            _run(migration, connection, "upgrade")
            assert sa.inspect(connection).has_table("payment_corrections")
            upgraded_sql = _manual_reference_index_sql(connection)
            assert "status" in upgraded_sql.lower()

            _run(migration, connection, "downgrade")
            assert not sa.inspect(connection).has_table("payment_corrections")
            restored_sql = _manual_reference_index_sql(connection)
            assert "status" not in str(restored_sql).lower()

            _run(migration, connection, "upgrade")
            assert sa.inspect(connection).has_table("payment_corrections")
    finally:
        engine.dispose()


def test_payment_correction_upgrade_creates_target_index_when_legacy_index_is_missing():
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    try:
        with engine.begin() as connection:
            _create_minimal_schema(connection, include_manual_reference_index=False)
            _run(migration, connection, "upgrade")
            assert sa.inspect(connection).has_table("payment_corrections")
            assert "status" in _manual_reference_index_sql(connection).lower()

            _run(migration, connection, "downgrade")
            assert not sa.inspect(connection).has_table("payment_corrections")
            assert "status" not in _manual_reference_index_sql(connection).lower()
    finally:
        engine.dispose()


def test_payment_correction_upgrade_rejects_active_duplicates_before_schema_changes():
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    try:
        with engine.begin() as connection:
            _create_minimal_schema(connection, include_manual_reference_index=False)
            connection.exec_driver_sql(
                "INSERT INTO transactions "
                "(id, hotel_id, reservation_id, payment_method, status, manual_reference) "
                "VALUES (1, 1, 1, 'bank_transfer', 'completed', 'REF-1'), "
                "(2, 1, 2, 'bank_transfer', 'pending', 'ref-1')"
            )

            with pytest.raises(RuntimeError, match="duplicate hotel/payment-method/reference"):
                _run(migration, connection, "upgrade")

            assert not sa.inspect(connection).has_table("payment_corrections")
            assert _manual_reference_index_sql(connection) is None
            assert connection.exec_driver_sql("SELECT count(*) FROM transactions").scalar_one() == 2
    finally:
        engine.dispose()


def test_payment_correction_downgrade_preserves_schema_when_cancelled_duplicates_exist():
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    try:
        with engine.begin() as connection:
            _create_minimal_schema(connection)
            _run(migration, connection, "upgrade")
            connection.exec_driver_sql(
                "INSERT INTO transactions "
                "(id, hotel_id, reservation_id, payment_method, status, manual_reference) "
                "VALUES (1, 1, 1, 'bank_transfer', 'cancelled', 'REF-1'), "
                "(2, 1, 2, 'bank_transfer', 'cancelled', 'ref-1')"
            )

            with pytest.raises(RuntimeError, match="duplicate hotel/payment-method/reference"):
                _run(migration, connection, "downgrade")

            assert sa.inspect(connection).has_table("payment_corrections")
            assert "status" in _manual_reference_index_sql(connection).lower()
            assert connection.exec_driver_sql("SELECT count(*) FROM transactions").scalar_one() == 2
    finally:
        engine.dispose()


def test_payment_correction_migration_refuses_to_drop_existing_audit_history():
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    try:
        with engine.begin() as connection:
            _create_minimal_schema(connection)
            _run(migration, connection, "upgrade")
            connection.exec_driver_sql("INSERT INTO hotel_configuration (id) VALUES (1)")
            connection.exec_driver_sql("INSERT INTO users (id) VALUES (1)")
            connection.exec_driver_sql(
                "INSERT INTO reservations (id, hotel_id) VALUES (1, 1), (2, 1)"
            )
            connection.exec_driver_sql(
                "INSERT INTO transactions "
                "(id, hotel_id, reservation_id, payment_method, status, manual_reference) "
                "VALUES (1, 1, 1, 'bank_transfer', 'cancelled', 'BANK-104'), "
                "(2, 1, 2, 'bank_transfer', 'completed', 'BANK-104')"
            )
            connection.exec_driver_sql(
                "INSERT INTO payment_corrections "
                "(id, hotel_id, source_transaction_id, source_reservation_id, target_reservation_id, "
                "replacement_transaction_id, correction_type, reason, idempotency_key, actor_user_id, created_at) "
                "VALUES (1, 1, 1, 1, 2, 2, 'reassign', 'wrong reservation', "
                "'correction-key-1', 1, '2026-10-24 12:00:00')"
            )

            with pytest.raises(RuntimeError, match="correction history exists"):
                _run(migration, connection, "downgrade")

            assert sa.inspect(connection).has_table("payment_corrections")
            assert connection.exec_driver_sql(
                "SELECT count(*) FROM payment_corrections"
            ).scalar_one() == 1
    finally:
        engine.dispose()
