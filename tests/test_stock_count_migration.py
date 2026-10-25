"""SQLite migration round-trip for audited, hotel-scoped stock count sessions."""

import os
import subprocess
import sys

from sqlalchemy import MetaData, Table, create_engine, inspect, text

from tests.migration_helpers import insert_historical_hotel_config

PRE_REVISION = "20261025_reservation_cancellation_review"
REVISION = "20261025_stock_count_sessions"


def _alembic(cwd: str, db_path: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=cwd,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
    )


def _assert_revision_schema(db_path: str, *, present: bool) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        stock_columns = {
            column["name"] for column in inspector.get_columns("stock_items")
        }
        hotel_columns = {
            column["name"] for column in inspector.get_columns("hotel_configuration")
        }
        assert ("stock_count_sessions" in tables) is present
        assert ("stock_count_lines" in tables) is present
        assert ("movement_version" in stock_columns) is present
        assert ("allow_stock_count_self_approval" in hotel_columns) is present
        if present:
            assert {
                index["name"] for index in inspector.get_indexes("stock_count_lines")
            } >= {
                "uq_stock_count_line_unlocated",
                "ix_stock_count_lines_hotel_session",
            }
    finally:
        engine.dispose()


def test_stock_count_migration_backfills_safe_defaults_and_round_trips(tmp_path):
    cwd = os.path.dirname(os.path.dirname(__file__))
    db_path = str(tmp_path / "stock-count-sessions.db")
    _alembic(cwd, db_path, "upgrade", PRE_REVISION)

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        insert_historical_hotel_config(engine, 1)
        with engine.begin() as connection:
            stock_items = Table("stock_items", MetaData(), autoload_with=connection)
            connection.execute(
                stock_items.insert().values(
                    hotel_id=1, name="Soap", unit="unit", active=True
                )
            )
    finally:
        engine.dispose()

    _alembic(cwd, db_path, "upgrade", REVISION)
    _assert_revision_schema(db_path, present=True)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT movement_version FROM stock_items WHERE hotel_id = 1")
                ).scalar_one()
                == 0
            )
            assert connection.execute(
                text(
                    "SELECT allow_stock_count_self_approval FROM hotel_configuration WHERE id = 1"
                )
            ).scalar_one() in (0, False)
            for role in ("owner", "co_owner", "manager"):
                assert connection.execute(
                    text(
                        "SELECT allowed FROM role_permission_defaults "
                        "WHERE role = :role AND permission_code = 'stock:count_confirm'"
                    ),
                    {"role": role},
                ).scalar_one() in (1, True)
            for role in ("receptionist", "housekeeping"):
                assert connection.execute(
                    text(
                        "SELECT allowed FROM role_permission_defaults "
                        "WHERE role = :role AND permission_code = 'stock:count_confirm'"
                    ),
                    {"role": role},
                ).scalar_one() in (0, False)
    finally:
        engine.dispose()

    _alembic(cwd, db_path, "downgrade", PRE_REVISION)
    _assert_revision_schema(db_path, present=False)
    _alembic(cwd, db_path, "upgrade", REVISION)
    _assert_revision_schema(db_path, present=True)
