"""Persist declared laundry losses without changing historical remito lines."""

import os
import subprocess
import sys
import tempfile

import pytest
from sqlalchemy import create_engine, text

from tests.migration_helpers import insert_historical_hotel_config


PREVIOUS_REVISION = "d2a7e93f4c2b"
REVISION = "20261005_laundry_missing"


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


def test_missing_quantity_migration_defaults_existing_lines_and_round_trips():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/laundry-missing.db"
        _run_alembic(cwd, db_path, "upgrade", PREVIOUS_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            insert_historical_hotel_config(engine, 1)
            with engine.begin() as connection:
                connection.execute(
                    text("INSERT INTO linen_locations (id, hotel_id, name) VALUES (11, 1, 'Depósito')")
                )
                connection.execute(
                    text(
                        "INSERT INTO linen_items (id, hotel_id, name, unit, active) "
                        "VALUES (21, 1, 'Sábanas', 'unidad', 1)"
                    )
                )
                connection.execute(
                    text(
                        "INSERT INTO laundry_vendors "
                        "(id, hotel_id, name, linen_location_id, active, created_at) "
                        "VALUES (12, 1, 'Lavadero', 11, 1, '2026-09-30 12:00:00')"
                    )
                )
                connection.execute(
                    text(
                        "INSERT INTO laundry_remitos "
                        "(id, hotel_id, vendor_id, direction, remito_number, remito_date, created_at) "
                        "VALUES (13, 1, 12, 'inbound', 'R-OLD', '2026-09-30 12:00:00', '2026-09-30 12:00:00')"
                    )
                )
                connection.execute(
                    text(
                        "INSERT INTO laundry_remito_lines "
                        "(id, hotel_id, remito_id, linen_item_id, quantity) VALUES (14, 1, 13, 21, 5)"
                    )
                )
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "upgrade", REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                assert connection.execute(
                    text("SELECT quantity, missing_quantity FROM laundry_remito_lines WHERE id = 14")
                ).one() == (5, 0)
                columns = {row[1] for row in connection.execute(text("PRAGMA table_info(laundry_remito_lines)"))}
                assert "missing_quantity" in columns
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO laundry_remito_lines "
                        "(id, hotel_id, remito_id, linen_item_id, quantity, missing_quantity) "
                        "VALUES (15, 1, 13, 21, 0, 5)"
                    )
                )
        finally:
            engine.dispose()

        env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
        blocked_downgrade = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", PREVIOUS_REVISION],
            capture_output=True,
            text=True,
            env=env,
            cwd=cwd,
        )
        assert blocked_downgrade.returncode != 0
        assert "Cannot downgrade laundry missing quantities" in blocked_downgrade.stderr

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM laundry_remito_lines WHERE id = 15"))
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "downgrade", PREVIOUS_REVISION)
        _run_alembic(cwd, db_path, "upgrade", REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                assert connection.execute(
                    text("SELECT id, quantity, missing_quantity FROM laundry_remito_lines WHERE id = 14")
                ).one() == (14, 5, 0)
        finally:
            engine.dispose()
