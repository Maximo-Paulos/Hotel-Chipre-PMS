"""Disposable live PostgreSQL proof for the forward Alembic release path.

The release contract is a fresh forward install, an idempotent repeat install,
and a one-revision rollback/re-upgrade from the current head.  Full
``downgrade base`` is a known historical limitation documented in the
infrastructure runbook and is intentionally outside this test's scope.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DSN = "postgresql+psycopg2://pms:pms@127.0.0.1:5432/fresh_check"


def _migration_dsn() -> str:
    pytest.importorskip("psycopg2")
    dsn = os.getenv("POSTGRES_MIGRATION_TEST_URL", DEFAULT_DSN)
    if not dsn.startswith("postgresql"):
        pytest.skip("POSTGRES_MIGRATION_TEST_URL must be a PostgreSQL DSN")
    return dsn


def _run_alembic(dsn: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": dsn}
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
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))

        assert inspect(engine).get_table_names() == [], "migration target must start empty"

        first = _run_alembic(dsn, "upgrade", "head")
        assert first.returncode == 0, f"first upgrade failed:\n{first.stdout}\n{first.stderr}"

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
