"""Alembic round-trip for the additive local business-clock table."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, text

import app.models  # noqa: F401
from app.models.business_clock import HotelBusinessClock


PREVIOUS_REVISION = "20261016_fx_direction_markets"
BUSINESS_CLOCK_REVISION = "20261017_local_business_clock"


def _run_alembic(cwd: str, db_path: str, *args: str) -> None:
    env = {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite:///{db_path}",
    }
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


def test_local_business_clock_migration_adds_and_drops_only_its_table():
    cwd = str(Path(__file__).resolve().parents[1])
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "business-clock-migration.db")
        _run_alembic(cwd, db_path, "upgrade", BUSINESS_CLOCK_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                columns = {
                    row[1]
                    for row in connection.execute(text("PRAGMA table_info(hotel_business_clock)"))
                }
                assert columns == {
                    "hotel_id",
                    "business_date",
                    "advanced_at",
                    "advanced_by_user_id",
                }
                assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == BUSINESS_CLOCK_REVISION
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "downgrade", PREVIOUS_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                tables = set(connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
                assert "hotel_business_clock" not in tables
                assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS_REVISION
        finally:
            engine.dispose()


def test_local_business_clock_migration_adopts_existing_bootstrap_table():
    cwd = str(Path(__file__).resolve().parents[1])
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "business-clock-bootstrap.db")
        _run_alembic(cwd, db_path, "upgrade", PREVIOUS_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.begin() as connection:
                HotelBusinessClock.__table__.create(connection)
                connection.execute(
                    text(
                        "INSERT INTO hotel_business_clock "
                        "(hotel_id, business_date, advanced_at, advanced_by_user_id) "
                        "VALUES (1, '2026-10-18', '2026-10-17 03:00:00', NULL)"
                    )
                )
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "upgrade", BUSINESS_CLOCK_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                assert connection.execute(
                    text("SELECT business_date FROM hotel_business_clock WHERE hotel_id = 1")
                ).scalar_one() == "2026-10-18"
                assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == BUSINESS_CLOCK_REVISION
        finally:
            engine.dispose()
