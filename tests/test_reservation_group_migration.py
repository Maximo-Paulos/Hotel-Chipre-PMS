"""SQLite migration round-trip for tenant-scoped reservation groups."""

import os
import subprocess
import sys
import tempfile

from sqlalchemy import create_engine, text


PREVIOUS_REVISION = "41d66acfb13a"
GROUP_REVISION = "20261001_reservation_groups"


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


def test_reservation_groups_migration_upgrade_downgrade_upgrade():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/reservation-groups.db"
        _run_alembic(cwd, db_path, "upgrade", PREVIOUS_REVISION)
        _run_alembic(cwd, db_path, "upgrade", GROUP_REVISION)

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                reservation_columns = {
                    row[1] for row in connection.execute(text("PRAGMA table_info(reservations)"))
                }
                assert "group_id" in reservation_columns
                group_columns = {
                    row[1] for row in connection.execute(text("PRAGMA table_info(reservation_groups)"))
                }
                assert {
                    "id", "hotel_id", "guest_id", "company_id", "check_in_date", "check_out_date",
                    "notes", "created_by_user_id", "created_at",
                } <= group_columns
                group_fks = connection.execute(text("PRAGMA foreign_key_list(reservation_groups)")).all()
                assert any(row[2] == "guests" and row[3] == "hotel_id" and row[4] == "hotel_id" for row in group_fks)
                assert any(row[2] == "companies" and row[3] == "hotel_id" and row[4] == "hotel_id" for row in group_fks)
                reservation_fks = connection.execute(text("PRAGMA foreign_key_list(reservations)")).all()
                assert any(row[2] == "reservation_groups" and row[3] == "hotel_id" and row[4] == "hotel_id" for row in reservation_fks)
                assert any(row[2] == "reservation_groups" and row[3] == "group_id" and row[4] == "id" for row in reservation_fks)
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "downgrade", PREVIOUS_REVISION)
        _run_alembic(cwd, db_path, "upgrade", GROUP_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                assert "group_id" in {
                    row[1] for row in connection.execute(text("PRAGMA table_info(reservations)"))
                }
                assert connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one() == GROUP_REVISION
        finally:
            engine.dispose()
