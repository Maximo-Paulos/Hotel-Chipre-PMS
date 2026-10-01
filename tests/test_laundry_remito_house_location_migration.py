"""Add a nullable hotel-side location to new laundry remitos safely."""

import os
import subprocess
import sys
import tempfile

from sqlalchemy import create_engine, text

from tests.migration_helpers import insert_historical_hotel_config


PREVIOUS_REVISION = "20261003_manual_rate_policy"
REVISION = "6259a93c6205"


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


def test_house_location_migration_preserves_old_remitos_and_round_trips():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/laundry-remito-location.db"
        _run_alembic(cwd, db_path, "upgrade", PREVIOUS_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            insert_historical_hotel_config(engine, 1)
            with engine.begin() as connection:
                connection.execute(
                    text("INSERT INTO linen_locations (id, hotel_id, name) VALUES (11, 1, 'Deposito')")
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
                        "VALUES (13, 1, 12, 'outbound', 'R-OLD', '2026-09-30 12:00:00', '2026-09-30 12:00:00')"
                    )
                )
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "upgrade", REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                row = connection.execute(
                    text("SELECT house_location_id FROM laundry_remitos WHERE id = 13")
                ).one()
                assert row.house_location_id is None
                foreign_keys = connection.execute(text("PRAGMA foreign_key_list(laundry_remitos)")).all()
                assert any(
                    row[2] == "linen_locations" and row[3] == "hotel_id" and row[4] == "hotel_id"
                    for row in foreign_keys
                )
                assert any(
                    row[2] == "linen_locations" and row[3] == "house_location_id" and row[4] == "id"
                    for row in foreign_keys
                )
                linen_columns = {
                    row[1] for row in connection.execute(text("PRAGMA table_info(linen_movements)"))
                }
                assert "transfer_reference" in linen_columns
                transfer_indexes = {
                    row[1] for row in connection.execute(text("PRAGMA index_list(linen_movements)"))
                }
                assert "uq_linen_movement_transfer_direction" in transfer_indexes
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "downgrade", PREVIOUS_REVISION)
        _run_alembic(cwd, db_path, "upgrade", REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                assert connection.execute(
                    text("SELECT id, remito_number FROM laundry_remitos WHERE id = 13")
                ).one() == (13, "R-OLD")
                columns = {row[1] for row in connection.execute(text("PRAGMA table_info(laundry_remitos)"))}
                assert "house_location_id" in columns
                linen_columns = {
                    row[1] for row in connection.execute(text("PRAGMA table_info(linen_movements)"))
                }
                assert "transfer_reference" in linen_columns
        finally:
            engine.dispose()
