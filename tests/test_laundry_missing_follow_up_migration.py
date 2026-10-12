"""Backfill and preserve neutral follow-up for declared laundry shortages."""

import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import insert_historical_hotel_config


PREVIOUS_REVISION = "11be7c9387c4"
REVISION = "20261017_laundry_missing_follow_up"


def _run_alembic(repository_root: str, database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "APP_ENV": "test", "DATABASE_URL": database_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=repository_root,
    )
    assert result.returncode == 0, f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
    return result


def test_missing_follow_up_migration_backfills_shorts_and_guards_downgrade(tmp_path):
    repository_root = os.path.dirname(os.path.dirname(__file__))
    database_url = f"sqlite:///{tmp_path / 'laundry-follow-up.db'}"
    _run_alembic(repository_root, database_url, "upgrade", PREVIOUS_REVISION)
    engine = create_engine(database_url)
    try:
        insert_historical_hotel_config(engine, 1)
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO linen_locations (id, hotel_id, name) VALUES (11, 1, 'Depósito')"))
            connection.execute(text("INSERT INTO linen_items (id, hotel_id, name, unit, active) VALUES (21, 1, 'Sábanas', 'unidad', 1)"))
            connection.execute(
                text(
                    "INSERT INTO laundry_vendors (id, hotel_id, name, linen_location_id, active, created_at) "
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
                    "(id, hotel_id, remito_id, linen_item_id, quantity, missing_quantity) "
                    "VALUES (14, 1, 13, 21, 5, 2), (15, 1, 13, 21, 5, 0)"
                )
            )

        _run_alembic(repository_root, database_url, "upgrade", REVISION)
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT follow_up_status FROM laundry_remito_lines WHERE id = 14")
            ).scalar_one() == "open"
            assert connection.execute(
                text("SELECT follow_up_status FROM laundry_remito_lines WHERE id = 15")
            ).scalar_one() is None
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(laundry_remito_lines)"))}
            assert {
                "follow_up_status",
                "follow_up_note",
                "supplier_reference",
                "supplier_contacted_on",
                "supplier_contact_note",
                "supplier_response_on",
                "supplier_response_note",
                "follow_up_updated_by_user_id",
                "follow_up_updated_at",
            } <= columns
            assert not {"compensation_amount", "replacement_value", "currency_code"} & columns

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO laundry_remito_lines "
                        "(id, hotel_id, remito_id, linen_item_id, quantity, missing_quantity, follow_up_status) "
                        "VALUES (16, 1, 13, 21, 5, 2, NULL)"
                    )
                )

        with engine.begin() as connection:
            connection.execute(
                text("UPDATE laundry_remito_lines SET follow_up_status = 'response_recorded' WHERE id = 14")
            )
            connection.execute(
                text(
                    "UPDATE laundry_remito_lines SET supplier_response_on = '2026-10-01', "
                    "supplier_response_note = 'Respuesta registrada' WHERE id = 14"
                )
            )

        downgrade = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", PREVIOUS_REVISION],
            capture_output=True,
            text=True,
            env={**os.environ, "APP_ENV": "test", "DATABASE_URL": database_url},
            cwd=repository_root,
        )
        assert downgrade.returncode != 0
        assert "Cannot downgrade laundry missing follow-up" in downgrade.stderr

        with engine.begin() as connection:
            connection.execute(text("DELETE FROM laundry_remito_lines WHERE id = 14"))
        _run_alembic(repository_root, database_url, "downgrade", PREVIOUS_REVISION)
        with engine.connect() as connection:
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(laundry_remito_lines)"))}
            assert "follow_up_status" not in columns
            assert connection.execute(text("SELECT missing_quantity FROM laundry_remito_lines WHERE id = 15")).scalar_one() == 0
    finally:
        engine.dispose()
