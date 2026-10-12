"""SQLite upgrade/downgrade coverage for durable receipt delivery outcomes."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from sqlalchemy import create_engine, inspect, text


def test_receipt_email_migration_round_trips_and_preserves_delivery_ledger():
    repository_root = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = f"{temp_dir}/receipt-email-migration.db"
        database_url = f"sqlite:///{db_path}"
        env = {
            **os.environ,
            "APP_ENV": "test",
            "DATABASE_URL": database_url,
            "JWT_SECRET": "local-migration-test-secret-0123456789",
        }

        def run_alembic(*args: str, expected_success: bool = True) -> subprocess.CompletedProcess[str]:
            result = subprocess.run(
                [sys.executable, "-m", "alembic", *args],
                capture_output=True,
                text=True,
                env=env,
                cwd=repository_root,
            )
            assert (result.returncode == 0) is expected_success, (
                f"alembic {' '.join(args)} returned {result.returncode}:\n"
                f"{result.stdout}\n{result.stderr}"
            )
            return result

        run_alembic("upgrade", "head")
        engine = create_engine(database_url)
        try:
            assert "payment_receipt_email_deliveries" in inspect(engine).get_table_names()
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO payment_receipt_email_deliveries "
                        "(hotel_id, transaction_id, idempotency_key_hash, recipient_fingerprint, status) "
                        "VALUES (1, 1, :key_hash, :recipient_hash, 'sent')"
                    ),
                    {"key_hash": "a" * 64, "recipient_hash": "b" * 64},
                )
        finally:
            engine.dispose()

        # The current schema head is an Alembic merge revision. Target the
        # receipt table's parent so this checks its downgrade and unwinds the
        # sibling outbox branch, instead of asking Alembic for an ambiguous
        # single-step walk.
        receipt_parent_revision = "20261005_laundry_missing"
        run_alembic("downgrade", receipt_parent_revision, expected_success=False)
        engine = create_engine(database_url)
        try:
            with engine.begin() as connection:
                assert connection.execute(
                    text("SELECT status FROM payment_receipt_email_deliveries")
                ).scalar_one() == "sent"
                connection.execute(text("DELETE FROM payment_receipt_email_deliveries"))
        finally:
            engine.dispose()

        run_alembic("downgrade", receipt_parent_revision)
        engine = create_engine(database_url)
        try:
            assert "payment_receipt_email_deliveries" not in inspect(engine).get_table_names()
        finally:
            engine.dispose()

        run_alembic("upgrade", "head")
        engine = create_engine(database_url)
        try:
            assert "payment_receipt_email_deliveries" in inspect(engine).get_table_names()
        finally:
            engine.dispose()
