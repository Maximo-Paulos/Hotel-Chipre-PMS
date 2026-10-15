"""Disposable PostgreSQL proof for the forward Alembic release path.

The release contract is a fresh forward install, an idempotent repeat install,
and a one-revision rollback/re-upgrade from the current head.  Full
``downgrade base`` is a known historical limitation documented in the
infrastructure runbook and is intentionally outside this test's scope.

This test is destructive. It runs only when POSTGRES_MIGRATION_TEST_URL and
independent isolation evidence are explicitly supplied and accepted by the
shared PostgreSQL isolation guard. Never set the test URL to production.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from tests.postgres_test_safety import validate_postgres_test_target


REPO_ROOT = Path(__file__).resolve().parents[2]


def _migration_dsn() -> str:
    pytest.importorskip("psycopg2")
    dsn = os.getenv("POSTGRES_MIGRATION_TEST_URL", "").strip()
    if not dsn:
        pytest.skip("POSTGRES_MIGRATION_TEST_URL must name an explicitly isolated PostgreSQL target")

    # Reuse the same fail-closed guard used by other schema-mutating tests.
    # The independent explicit URL and provider/local evidence are required;
    # a URL inherited from .env is not proof that the target is disposable.
    safety_environment = {**os.environ, "DATABASE_URL_TEST": dsn}
    return validate_postgres_test_target(dsn, safety_environment)


def _run_alembic(dsn: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "APP_ENV": "test", "DATABASE_URL": dsn}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_fresh_postgres_migrations_upgrade_is_idempotent_and_current_head_round_trips():
    dsn = _migration_dsn()
    engine = create_engine(dsn, connect_args={"connect_timeout": 2})
    try:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            pytest.skip("PostgreSQL migration target is not reachable")

        with engine.begin() as connection:
            actual_database = connection.execute(text("SELECT current_database()")).scalar_one()
            expected_database = os.getenv("POSTGRES_TEST_EXPECTED_DATABASE", "")
            if not expected_database or actual_database != expected_database:
                pytest.fail("Connected database does not match the validated disposable target")
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))

        assert inspect(engine).get_table_names() == [], "migration target must start empty"

        first = _run_alembic(dsn, "upgrade", "head")
        assert first.returncode == 0, f"first upgrade failed:\n{first.stdout}\n{first.stderr}"

        with engine.connect() as connection:
            queue_security = connection.execute(
                text(
                    "SELECT table_row_security.relrowsecurity, "
                    "table_row_security.relforcerowsecurity, "
                    "EXISTS (SELECT 1 FROM pg_policies "
                    "WHERE schemaname = 'public' "
                    "AND tablename = 'analytics_fact_refresh_jobs' "
                    "AND policyname = 'tenant_isolation_analytics_fact_refresh_jobs') "
                    "FROM pg_class AS table_row_security "
                    "JOIN pg_namespace AS table_schema ON table_schema.oid = table_row_security.relnamespace "
                    "WHERE table_schema.nspname = 'public' "
                    "AND table_row_security.relname = 'analytics_fact_refresh_jobs'"
                )
            ).one()
        assert queue_security == (True, True, True), (
            "analytics refresh queue must have forced row-level security and a hotel policy"
        )

        with engine.connect() as connection:
            company_channel = connection.execute(
                text("SELECT 'company'::fact_reservation_daily_channel_code_enum::text")
            ).scalar_one()
        assert company_channel == "company", (
            "analytics fact channel enum must accept corporate reservations"
        )

        second = _run_alembic(dsn, "upgrade", "head")
        assert second.returncode == 0, f"repeat upgrade failed:\n{second.stdout}\n{second.stderr}"

        down = _run_alembic(dsn, "downgrade", "-1")
        assert down.returncode == 0, f"one-revision downgrade failed:\n{down.stdout}\n{down.stderr}"

        round_trip = _run_alembic(dsn, "upgrade", "head")
        assert round_trip.returncode == 0, (
            f"upgrade after one-revision downgrade failed:\n"
            f"{round_trip.stdout}\n{round_trip.stderr}"
        )
    finally:
        engine.dispose()
