"""SQLite migration round-trip for linked stock transfer movements."""

import os
import subprocess
import sys
import tempfile

from sqlalchemy import create_engine, text


PREVIOUS_REVISION = "20261001_reservation_groups"
TRANSFER_REVISION = "20261002_stock_transfers"


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


def _assert_transfer_schema(db_path: str, present: bool) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(stock_movements)"))}
            indexes = {row[1] for row in connection.execute(text("PRAGMA index_list(stock_movements)"))}
            assert ("transfer_reference" in columns) is present
            assert ("uq_stock_movement_transfer_direction" in indexes) is present
            if present:
                table_sql = connection.execute(
                    text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'stock_movements'")
                ).scalar_one()
                assert "ck_stock_movements_transfer_direction_valid" in table_sql
                index_sql = connection.execute(
                    text("SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'uq_stock_movement_transfer_direction'")
                ).scalar_one()
                assert "WHERE transfer_reference IS NOT NULL" in index_sql
    finally:
        engine.dispose()


def test_stock_transfer_migration_upgrade_downgrade_upgrade():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/stock-transfers.db"
        _run_alembic(cwd, db_path, "upgrade", PREVIOUS_REVISION)
        _run_alembic(cwd, db_path, "upgrade", TRANSFER_REVISION)
        _assert_transfer_schema(db_path, present=True)

        _run_alembic(cwd, db_path, "downgrade", PREVIOUS_REVISION)
        _assert_transfer_schema(db_path, present=False)

        _run_alembic(cwd, db_path, "upgrade", TRANSFER_REVISION)
        _assert_transfer_schema(db_path, present=True)
