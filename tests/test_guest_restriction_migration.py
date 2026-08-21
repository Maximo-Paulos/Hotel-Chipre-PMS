from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker


PRE_REVISION = "20260813_rbac_overrides"
REVISION = "20260813_guest_restrictions"


def _alembic(cwd: str, db_path: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=cwd,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _engine(db_path: str):
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def _seed_legacy_tags(engine) -> None:
    from app.models.guest import Guest, GuestRatingEnum, GuestTag, GuestTagTypeEnum
    from app.models.hotel_config import HotelConfiguration

    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as db:
        db.add_all(
            [
                HotelConfiguration(id=7301, subscription_active=True),
                HotelConfiguration(id=7302, subscription_active=True),
            ]
        )
        db.flush()
        # This fixture intentionally seeds the schema before the migration
        # under test. Do not use current ORM ``add()`` for User or Guest here:
        # their mappers include columns that do not exist at this historical
        # revision (including TECH-0110's later soft-delete columns).
        db.execute(
            text(
                "INSERT INTO users "
                "(id, email, password_hash, is_active, is_verified, role, token_version, created_at, updated_at) "
                "VALUES (301, 'migration@example.test', 'synthetic', 1, 1, 'owner', 0, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        guest_table = Guest.__table__
        guest_a_id = db.execute(
            guest_table.insert().values(
                hotel_id=7301,
                first_name="Legacy",
                last_name="Active",
                rating=GuestRatingEnum.NORMAL,
                terms_accepted=False,
            )
        ).inserted_primary_key[0]
        guest_b_id = db.execute(
            guest_table.insert().values(
                hotel_id=7302,
                first_name="Legacy",
                last_name="Other hotel",
                rating=GuestRatingEnum.NORMAL,
                terms_accepted=False,
            )
        ).inserted_primary_key[0]
        db.add_all(
            [
                GuestTag(
                    hotel_id=7301,
                    guest_id=guest_a_id,
                    tag_type=GuestTagTypeEnum.PROHIBIDO_ALOJAR,
                    note="Legacy detail",
                    created_by_user_id=301,
                ),
                    GuestTag(
                        hotel_id=7301,
                        guest_id=guest_a_id,
                    tag_type=GuestTagTypeEnum.PROHIBIDO_ALOJAR,
                    note="Expired legacy detail",
                    expires_at="2020-01-01 00:00:00",
                    created_by_user_id=301,
                ),
            ]
        )
        db.commit()
        return guest_a_id, guest_b_id


def _load_migration():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "20260813_guest_restrictions.py"
    spec = importlib.util.spec_from_file_location("guest_restrictions_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_guest_restriction_upgrade_downgrade_upgrade_backfills_without_touching_tags():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "guest-restrictions.db")
        _alembic(cwd, db_path, "upgrade", PRE_REVISION)
        engine = _engine(db_path)
        try:
            guest_a_id, guest_b_id = _seed_legacy_tags(engine)
        finally:
            engine.dispose()

        _alembic(cwd, db_path, "upgrade", REVISION)
        engine = _engine(db_path)
        try:
            assert "guest_restrictions" in inspect(engine).get_table_names()
            with engine.connect() as connection:
                assert connection.execute(text("SELECT COUNT(*) FROM guest_tags")).scalar_one() == 2
                row = connection.execute(
                    text(
                        "SELECT hotel_id, guest_id, status, reason, detail, legacy_guest_tag_id "
                        "FROM guest_restrictions"
                    )
                ).mappings().one()
                assert row["hotel_id"] == 7301
                assert row["guest_id"] == guest_a_id
                assert row["status"] == "active"
                assert row["reason"] == "legacy_prohibido_alojar"
                assert row["detail"] == "Legacy detail"

            with pytest.raises(IntegrityError):
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            "INSERT INTO guest_restrictions "
                            "(hotel_id, guest_id, status, reason, created_at, updated_at) "
                            "VALUES (7301, :guest_b_id, 'active', 'cross_hotel', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                        ),
                        {"guest_b_id": guest_b_id},
                    )
        finally:
            engine.dispose()

        _alembic(cwd, db_path, "downgrade", PRE_REVISION)
        engine = _engine(db_path)
        try:
            assert "guest_restrictions" not in inspect(engine).get_table_names()
            with engine.connect() as connection:
                assert connection.execute(text("SELECT COUNT(*) FROM guest_tags")).scalar_one() == 2
        finally:
            engine.dispose()

        _alembic(cwd, db_path, "upgrade", REVISION)
        engine = _engine(db_path)
        try:
            assert "guest_restrictions" in inspect(engine).get_table_names()
            with engine.connect() as connection:
                assert connection.execute(text("SELECT COUNT(*) FROM guest_restrictions")).scalar_one() == 1
                assert connection.execute(text("SELECT COUNT(*) FROM guest_tags")).scalar_one() == 2
        finally:
            engine.dispose()


def test_guest_restriction_migration_owns_reversible_postgresql_rls(monkeypatch):
    migration = _load_migration()
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", lambda statement: statements.append(str(statement)))

    migration._install_rls(type("Connection", (), {"dialect": type("Dialect", (), {"name": "postgresql"})()})())
    migration._remove_rls(type("Connection", (), {"dialect": type("Dialect", (), {"name": "postgresql"})()})())

    ddl = "\n".join(statements)
    assert 'ALTER TABLE "guest_restrictions" ENABLE ROW LEVEL SECURITY' in ddl
    assert 'ALTER TABLE "guest_restrictions" FORCE ROW LEVEL SECURITY' in ddl
    assert 'CREATE POLICY "tenant_isolation_guest_restrictions"' in ddl
    assert "current_setting('app.hotel_id', true)" in ddl
    assert "WITH CHECK" in ddl
    assert 'DROP POLICY IF EXISTS "tenant_isolation_guest_restrictions"' in ddl
    assert 'ALTER TABLE "guest_restrictions" DISABLE ROW LEVEL SECURITY' in ddl
