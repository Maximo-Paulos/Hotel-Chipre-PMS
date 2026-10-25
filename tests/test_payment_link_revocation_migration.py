"""SQLite coverage for the legacy payment-link revocation backfill."""
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20261022_payment_link_provider_revocation.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("payment_link_revocation_migration", MIGRATION_PATH)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_migration_queues_only_legacy_open_mp_links_for_cancelled_reservations(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE TABLE reservations (
                    id INTEGER NOT NULL,
                    hotel_id INTEGER NOT NULL,
                    status VARCHAR(30) NOT NULL,
                    PRIMARY KEY (hotel_id, id)
                )
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE payment_links (
                    id INTEGER PRIMARY KEY,
                    hotel_id INTEGER NOT NULL,
                    reservation_id INTEGER NOT NULL,
                    status VARCHAR(30) NOT NULL,
                    payable BOOLEAN NOT NULL,
                    execution_mode VARCHAR(20) NOT NULL,
                    provider VARCHAR(30) NOT NULL,
                    external_checkout_url VARCHAR(500),
                    cancelled_at DATETIME
                )
                """
            )
            connection.exec_driver_sql(
                "INSERT INTO reservations (id, hotel_id, status) VALUES (1, 1, 'cancelled'), (2, 1, 'pending')"
            )
            connection.exec_driver_sql(
                """
                INSERT INTO payment_links
                    (id, hotel_id, reservation_id, status, payable, execution_mode, provider, external_checkout_url, cancelled_at)
                VALUES
                    (1, 1, 1, 'pending', 1, 'provider', 'mercado_pago', 'https://checkout.test/1', NULL),
                    (2, 1, 1, 'cancelled', 0, 'provider', 'mercadopago', 'https://checkout.test/2', '2026-10-20 12:00:00'),
                    (3, 1, 2, 'pending', 1, 'provider', 'mercado_pago', 'https://checkout.test/3', NULL),
                    (4, 1, 1, 'completed', 0, 'provider', 'mercado_pago', 'https://checkout.test/4', NULL),
                    (5, 1, 1, 'pending', 0, 'local_only', 'mercado_pago', NULL, NULL),
                    (6, 1, 1, 'expired', 0, 'provider', 'mercado_pago', 'https://checkout.test/6', NULL),
                    (7, 1, 1, 'pending', 0, 'provider', 'mercado_pago', 'https://checkout.test/7', NULL)
                """
            )

        with engine.begin() as connection:
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.upgrade()
            rows = connection.execute(
                sa.text(
                    "SELECT id, status, payable, provider_revocation_status, cancelled_at "
                    "FROM payment_links ORDER BY id"
                )
            ).mappings().all()

        by_id = {row["id"]: row for row in rows}
        for link_id in (1, 2):
            assert by_id[link_id]["status"] == "cancelled"
            assert by_id[link_id]["payable"] in (False, 0)
            assert by_id[link_id]["provider_revocation_status"] == "pending"
            assert by_id[link_id]["cancelled_at"] is not None
        assert by_id[2]["cancelled_at"] == "2026-10-20 12:00:00"
        for link_id in (3, 4, 5, 6, 7):
            assert by_id[link_id]["provider_revocation_status"] == "not_required"
        assert by_id[3]["status"] == "pending"
        assert by_id[4]["status"] == "completed"
        assert by_id[5]["status"] == "pending"
        assert by_id[6]["status"] == "expired"
        assert by_id[7]["status"] == "pending"
    finally:
        engine.dispose()
