"""Migration contract and SQLite round trip for location-specific linen minima."""

import os
import subprocess
import sys
import tempfile

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import insert_historical_hotel_config


PREVIOUS_REVISION = "20260930_housekeeping_board_permission"
PAR_LEVEL_REVISION = "41d66acfb13a"


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


def test_linen_par_level_migration_constraints_and_upgrade_downgrade_upgrade():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/linen-par-levels.db"
        _run_alembic(cwd, db_path, "upgrade", PREVIOUS_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            insert_historical_hotel_config(engine, 1)
            with engine.begin() as connection:
                connection.execute(
                    text("INSERT INTO linen_items (id, hotel_id, name, unit, active) VALUES (11, 1, 'Sabanas', 'unidad', 1)")
                )
                connection.execute(
                    text("INSERT INTO linen_locations (id, hotel_id, name) VALUES (12, 1, 'Deposito')")
                )
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "upgrade", PAR_LEVEL_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO linen_par_levels "
                        "(id, hotel_id, item_id, location_id, min_quantity, updated_at) "
                        "VALUES (1, 1, 11, 12, 0, '2026-09-30 12:00:00')"
                    )
                )
                assert connection.execute(
                    text("SELECT min_quantity FROM linen_par_levels WHERE id = 1")
                ).scalar_one() == 0
                try:
                    connection.execute(
                        text(
                            "INSERT INTO linen_par_levels "
                            "(id, hotel_id, item_id, location_id, min_quantity, updated_at) "
                            "VALUES (2, 1, 11, 12, -1, '2026-09-30 12:00:00')"
                        )
                    )
                except IntegrityError:
                    pass
                else:
                    raise AssertionError("negative linen minimum passed its database check")
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "downgrade", PREVIOUS_REVISION)
        _run_alembic(cwd, db_path, "upgrade", PAR_LEVEL_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                columns = {row[1] for row in connection.execute(text("PRAGMA table_info(linen_par_levels)"))}
                assert {"hotel_id", "item_id", "location_id", "min_quantity", "created_by_user_id", "updated_by_user_id"} <= columns
                foreign_key_pairs = connection.execute(text("PRAGMA foreign_key_list(linen_par_levels)" )).all()
                assert any(row[2] == "linen_items" and row[3] == "hotel_id" and row[4] == "hotel_id" for row in foreign_key_pairs)
                assert any(row[2] == "linen_items" and row[3] == "item_id" and row[4] == "id" for row in foreign_key_pairs)
        finally:
            engine.dispose()
