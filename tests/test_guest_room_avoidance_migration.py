from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


PRE_REVISION = "20260830_room_move_tiers"
REVISION = "20260830_guest_room_avoidance"
PERMISSION = "guest:room_avoidance_resolve"


def _alembic(cwd: str, db_path: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=cwd,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _load_migration():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "20260830_guest_room_avoidance.py"
    spec = importlib.util.spec_from_file_location("guest_room_avoidance_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_guest_room_avoidance_migration_is_reversible_on_sqlite_and_seeds_defaults(tmp_path):
    cwd = os.path.dirname(os.path.dirname(__file__))
    db_path = str(tmp_path / "guest-room-avoidance.db")

    _alembic(cwd, db_path, "upgrade", PRE_REVISION)
    _alembic(cwd, db_path, "upgrade", REVISION)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        inspector = inspect(engine)
        assert "guest_room_avoidance" in inspector.get_table_names()
        assert {index["name"] for index in inspector.get_indexes("guest_room_avoidance")} >= {
            "ix_guest_room_avoidance_hotel_guest_status"
        }
        uniques = {tuple(item["column_names"]) for item in inspector.get_unique_constraints("guest_room_avoidance")}
        assert ("hotel_id", "guest_id", "room_id") in uniques
        source_fk = next(
            item
            for item in inspector.get_foreign_keys("guest_room_avoidance")
            if item["constrained_columns"] == ["source_move_event_id"]
        )
        assert source_fk["referred_table"] == "room_move_events"
        assert source_fk["options"].get("ondelete") == "SET NULL"
        with engine.connect() as connection:
            rows = dict(
                connection.execute(
                    text(
                        "SELECT role, allowed FROM role_permission_defaults "
                        "WHERE permission_code = :permission ORDER BY role"
                    ),
                    {"permission": PERMISSION},
                ).all()
            )
        assert rows == {
            "co_owner": 1,
            "housekeeping": 0,
            "manager": 1,
            "owner": 1,
            "receptionist": 0,
        }
    finally:
        engine.dispose()

    _alembic(cwd, db_path, "downgrade", PRE_REVISION)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        assert "guest_room_avoidance" not in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT COUNT(*) FROM role_permission_defaults WHERE permission_code = :permission"),
                {"permission": PERMISSION},
            ).scalar_one() == 0
    finally:
        engine.dispose()


def test_guest_room_avoidance_migration_owns_reversible_postgresql_rls(monkeypatch):
    migration = _load_migration()
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", lambda statement: statements.append(str(statement)))

    connection = type("Connection", (), {"dialect": type("Dialect", (), {"name": "postgresql"})()})()
    migration._install_rls(connection)
    migration._remove_rls(connection)

    ddl = "\n".join(statements)
    assert 'ALTER TABLE "guest_room_avoidance" ENABLE ROW LEVEL SECURITY' in ddl
    assert 'ALTER TABLE "guest_room_avoidance" FORCE ROW LEVEL SECURITY' in ddl
    assert 'CREATE POLICY "tenant_isolation_guest_room_avoidance"' in ddl
    assert "current_setting('app.hotel_id', true)" in ddl
    assert "WITH CHECK" in ddl
    assert 'DROP POLICY IF EXISTS "tenant_isolation_guest_room_avoidance"' in ddl
    assert 'ALTER TABLE "guest_room_avoidance" DISABLE ROW LEVEL SECURITY' in ddl
