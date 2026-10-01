"""SQLite round-trip for company extension request fields."""

import os
import subprocess
import sys
import tempfile

from sqlalchemy import create_engine, inspect, text


PREVIOUS_REVISION = "20261008_owner_rate_adjust_default"
EXTENSION_REQUEST_REVISION = "20261009_company_extension_request"


def _run_alembic(cwd: str, db_path: str, *args: str) -> None:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )
    assert result.returncode == 0, (
        f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
    )


def _assert_columns(db_path: str, present: bool) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        names = {column["name"] for column in inspect(engine).get_columns("reservations")}
        expected = {"company_extension_request_pending", "company_extension_request_note"}
        assert expected <= names if present else expected.isdisjoint(names)
        if present:
            with engine.connect() as connection:
                pending = connection.execute(
                    text("SELECT company_extension_request_pending FROM reservations LIMIT 1")
                ).first()
                assert pending is None
    finally:
        engine.dispose()


def test_company_extension_request_migration_upgrade_downgrade_upgrade():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/company-extension-request.db"
        _run_alembic(cwd, db_path, "upgrade", PREVIOUS_REVISION)
        _assert_columns(db_path, present=False)

        _run_alembic(cwd, db_path, "upgrade", EXTENSION_REQUEST_REVISION)
        _assert_columns(db_path, present=True)

        _run_alembic(cwd, db_path, "downgrade", PREVIOUS_REVISION)
        _assert_columns(db_path, present=False)

        _run_alembic(cwd, db_path, "upgrade", EXTENSION_REQUEST_REVISION)
        _assert_columns(db_path, present=True)
