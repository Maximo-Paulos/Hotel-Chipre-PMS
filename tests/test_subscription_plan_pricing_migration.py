from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy import create_engine, text


def _run_alembic(repository_root: str, database_url: str, *args: str) -> None:
    env = {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_URL": database_url,
        "JWT_SECRET": "local-pricing-migration-test-secret-0123456789",
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=repository_root,
    )
    assert result.returncode == 0, f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"


def _plan_values(engine, query: str):
    with engine.connect() as connection:
        return {
            row.code: (row.price_amount, row.currency, row.billing_period)
            for row in connection.execute(text(query))
        }


def test_publishes_approved_prices_without_overwriting_admin_values(tmp_path):
    repository_root = os.path.dirname(os.path.dirname(__file__))
    database_url = f"sqlite:///{tmp_path / 'pricing.db'}"
    _run_alembic(repository_root, database_url, "upgrade", "4f3c177c4ba4")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE marketing_pricing_plans "
                    "SET price_amount = 123, currency = 'EUR' WHERE code = 'pro'"
                )
            )

        _run_alembic(repository_root, database_url, "upgrade", "head")
        assert _plan_values(
            engine,
            "SELECT code, price_amount, currency, billing_period FROM marketing_pricing_plans",
        ) == {
            "starter": (20, "USD", "month"),
            "pro": (123, "EUR", "month"),
            "ultra": (200, "USD", "month"),
        }

        _run_alembic(repository_root, database_url, "downgrade", "4f3c177c4ba4")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE marketing_pricing_plans "
                    "SET price_amount = 99, currency = 'ARS' WHERE code = 'pro'"
                )
            )
        assert _plan_values(
            engine,
            "SELECT code, price_amount, currency, billing_period FROM marketing_pricing_plans",
        ) == {
            "starter": (None, None, "month"),
            "pro": (99, "ARS", "month"),
            "ultra": (None, None, "month"),
        }
    finally:
        engine.dispose()


def test_price_migration_downgrade_preserves_admin_edit_with_same_published_price(tmp_path):
    repository_root = os.path.dirname(os.path.dirname(__file__))
    database_url = f"sqlite:///{tmp_path / 'pricing-same-value-edit.db'}"
    _run_alembic(repository_root, database_url, "upgrade", "4f3c177c4ba4")
    engine = create_engine(database_url)
    try:
        _run_alembic(repository_root, database_url, "upgrade", "head")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE marketing_pricing_plans "
                    "SET headline = 'Edited by admin', updated_at = '2099-01-01 00:00:00.000000' "
                    "WHERE code = 'starter'"
                )
            )

        _run_alembic(repository_root, database_url, "downgrade", "4f3c177c4ba4")
        assert _plan_values(
            engine,
            "SELECT code, price_amount, currency, billing_period "
            "FROM marketing_pricing_plans WHERE code = 'starter'",
        ) == {"starter": (20, "USD", "month")}
    finally:
        engine.dispose()


def test_price_migration_downgrade_restores_preexisting_currency_and_period(tmp_path):
    repository_root = os.path.dirname(os.path.dirname(__file__))
    database_url = f"sqlite:///{tmp_path / 'pricing-restore.db'}"
    _run_alembic(repository_root, database_url, "upgrade", "4f3c177c4ba4")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE marketing_pricing_plans "
                    "SET price_amount = NULL, currency = 'EUR', billing_period = 'year' "
                    "WHERE code = 'pro'"
                )
            )

        _run_alembic(repository_root, database_url, "upgrade", "head")
        assert _plan_values(
            engine,
            "SELECT code, price_amount, currency, billing_period "
            "FROM marketing_pricing_plans WHERE code = 'pro'",
        ) == {"pro": (100, "USD", "month")}

        _run_alembic(repository_root, database_url, "downgrade", "4f3c177c4ba4")
        assert _plan_values(
            engine,
            "SELECT code, price_amount, currency, billing_period "
            "FROM marketing_pricing_plans WHERE code = 'pro'",
        ) == {"pro": (None, "EUR", "year")}
    finally:
        engine.dispose()
