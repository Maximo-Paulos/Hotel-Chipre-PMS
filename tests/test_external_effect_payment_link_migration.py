"""Data-contract regression for the payment-link execution-mode migration."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError


PRE_REVISION = "ebd2db08c7d0"
REVISION = "20260812_external_effects"


def _alembic(cwd: str, db_path: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=cwd,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _seed_legacy_links(engine) -> None:
    statement = text(
        """
        INSERT INTO payment_links
            (id, hotel_id, reservation_id, link_code, requested_amount,
             collected_amount, currency, provider, status, recipient_email,
             sent_via_email, sent_via_whatsapp, external_checkout_url, title,
             allow_partial_payments, require_exact_amount)
        VALUES
            (:id, 1, 1, :code, 10, 0, 'ARS', 'mercado_pago', :status,
             :email, 0, 0, :url, 'Legacy', 1, 0)
        """
    )
    with engine.begin() as conn:
        conn.execute(
            statement,
            {
                "id": 9001,
                "code": "legacy-no-url",
                "status": "pending",
                "email": "a@example.com",
                "url": None,
            },
        )
        conn.execute(
            statement,
            {
                "id": 9002,
                "code": "legacy-url",
                "status": "pending",
                "email": "b@example.com",
                "url": "https://provider.example/pay",
            },
        )


def _assert_migrated(engine) -> None:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT link_code, execution_mode, payable FROM payment_links "
                "WHERE id IN (9001, 9002) ORDER BY id"
            )
        ).all()
        assert rows == [
            ("legacy-no-url", "provider", False),
            ("legacy-url", "provider", True),
        ]
        defaults = {
            row[1]: row[4]
            for row in conn.execute(text("PRAGMA table_info(payment_links)"))
        }
        assert defaults["execution_mode"].strip("'") == "local_only"


def test_payment_link_migration_backfills_provider_history_and_reupgrades():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "migration.db")
        _alembic(cwd, db_path, "upgrade", PRE_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            _seed_legacy_links(engine)
        finally:
            engine.dispose()

        _alembic(cwd, db_path, "upgrade", REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            _assert_migrated(engine)
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO payment_links "
                        "(id, hotel_id, reservation_id, link_code, requested_amount, "
                        "recipient_email, title) VALUES "
                        "(9003, 1, 1, 'new-local', 10, 'c@example.com', 'New')"
                    )
                )
            with pytest.raises(IntegrityError):
                with engine.begin() as conn:
                    conn.execute(text("UPDATE payment_links SET payable = 1 WHERE id = 9003"))
        finally:
            engine.dispose()

        _alembic(cwd, db_path, "downgrade", PRE_REVISION)
        _alembic(cwd, db_path, "upgrade", REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            _assert_migrated(engine)
        finally:
            engine.dispose()
