"""Data migration guard for separating housekeeping state from room status."""
import os
import subprocess
import sys
import tempfile

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import insert_historical_hotel_config


PREVIOUS_REVISION = "20260929_cash_prior_receipts"
HOUSEKEEPING_REVISION = "20260930_housekeeping_status"
HOUSEKEEPING_BOARD_PERMISSION_REVISION = "20260930_housekeeping_board_permission"


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


def _assert_backfill(engine) -> None:
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, status, housekeeping_status FROM rooms ORDER BY id")
        ).all()
    assert rows == [(1, "cleaning", "in_progress"), (2, "available", "clean")]


def test_housekeeping_status_migration_backfills_and_reverses_cleanly():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/housekeeping.db"
        _run_alembic(cwd, db_path, "upgrade", PREVIOUS_REVISION)

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            insert_historical_hotel_config(engine, 1)
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO room_categories "
                        "(id, hotel_id, name, code, base_price_per_night, max_occupancy) "
                        "VALUES (1, 1, 'Estándar', 'STD', 85000, 2)"
                    )
                )
                connection.execute(
                    text(
                        "INSERT INTO rooms (id, hotel_id, room_number, floor, category_id, status, is_active) "
                        "VALUES (1, 1, '101', 1, 1, 'cleaning', 1), "
                        "(2, 1, '102', 1, 1, 'available', 1)"
                    )
                )
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "upgrade", HOUSEKEEPING_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            _assert_backfill(engine)
            with engine.connect() as connection:
                try:
                    connection.execute(
                        text("UPDATE rooms SET housekeeping_status = 'unknown' WHERE id = 1")
                    )
                    connection.commit()
                except IntegrityError:
                    connection.rollback()
                else:
                    raise AssertionError("invalid housekeeping status passed its database constraint")
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "downgrade", PREVIOUS_REVISION)
        _run_alembic(cwd, db_path, "upgrade", HOUSEKEEPING_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            _assert_backfill(engine)
        finally:
            engine.dispose()


def test_housekeeping_board_permission_migration_seeds_only_intended_roles():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/housekeeping-permissions.db"
        _run_alembic(cwd, db_path, "upgrade", HOUSEKEEPING_BOARD_PERMISSION_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                permission = connection.execute(
                    text("SELECT code, description FROM permissions WHERE code = 'housekeeping:board_view'")
                ).one()
                defaults = dict(
                    connection.execute(
                        text(
                            "SELECT role, allowed FROM role_permission_defaults "
                            "WHERE permission_code = 'housekeeping:board_view'"
                        )
                    ).all()
                )
            assert permission[0] == "housekeeping:board_view"
            assert defaults == {
                "owner": 1,
                "co_owner": 1,
                "manager": 1,
                "receptionist": 0,
                "housekeeping": 1,
            }
        finally:
            engine.dispose()
