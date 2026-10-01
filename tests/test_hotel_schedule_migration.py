"""SQLite migration round-trip for hotel-local check-in and check-out times."""

import os
import subprocess
import sys
import tempfile

from sqlalchemy import create_engine, text

from tests.migration_helpers import insert_historical_hotel_config


PREVIOUS_REVISION = "20260930_housekeeping_board_permission"
SCHEDULE_REVISION = "015f7e36b9cd"


def _run_alembic(cwd: str, db_path: str, *args: str) -> None:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )
    assert result.returncode == 0, f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"


def test_hotel_schedule_migration_preserves_existing_settings_and_round_trips():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/hotel-schedule.db"
        _run_alembic(cwd, db_path, "upgrade", PREVIOUS_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            insert_historical_hotel_config(engine, 1)
            with engine.begin() as connection:
                connection.execute(text("UPDATE hotel_configuration SET hotel_name='Hotel Mirador' WHERE id=1"))
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "upgrade", SCHEDULE_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.begin() as connection:
                columns = {row[1] for row in connection.execute(text("PRAGMA table_info(hotel_configuration)"))}
                assert {"check_in_time", "check_out_time"} <= columns
                connection.execute(
                    text("UPDATE hotel_configuration SET check_in_time='14:00', check_out_time='10:00' WHERE id=1")
                )
                assert connection.execute(
                    text("SELECT hotel_name, check_in_time, check_out_time FROM hotel_configuration WHERE id=1")
                ).one() == ("Hotel Mirador", "14:00", "10:00")
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "downgrade", PREVIOUS_REVISION)
        _run_alembic(cwd, db_path, "upgrade", SCHEDULE_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                columns = {row[1] for row in connection.execute(text("PRAGMA table_info(hotel_configuration)"))}
                assert {"check_in_time", "check_out_time"} <= columns
                assert connection.execute(
                    text("SELECT hotel_name, check_in_time, check_out_time FROM hotel_configuration WHERE id=1")
                ).one() == ("Hotel Mirador", None, None)
        finally:
            engine.dispose()
