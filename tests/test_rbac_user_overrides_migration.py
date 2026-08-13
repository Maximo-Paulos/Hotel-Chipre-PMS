from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker


PRE_REVISION = "20260812_external_effects"
REVISION = "20260813_rbac_overrides"


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


def _seed_pre_revision(engine) -> None:
    from app.models.hotel_config import HotelConfiguration
    from app.models.hotel_membership import HotelMembership
    from app.models.user import User

    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as db:
        db.add_all(
            [
                HotelConfiguration(id=1, subscription_active=True),
                HotelConfiguration(id=2, subscription_active=True),
                User(id=10, email="owner-rbac@example.test", password_hash="synthetic", is_verified=True),
                User(id=20, email="staff-rbac@example.test", password_hash="synthetic", is_verified=True),
            ]
        )
        db.flush()
        db.add_all(
            [
                HotelMembership(hotel_id=1, user_id=10, role="owner", status="active"),
                HotelMembership(hotel_id=2, user_id=20, role="receptionist", status="active"),
            ]
        )
        db.commit()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO permissions (code, description) "
                "VALUES ('guest:view', 'View guest profile data')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO hotel_permission_overrides "
                "(hotel_id, role, permission_code, allowed, updated_by_user_id, updated_at) "
                "VALUES (1, 'receptionist', 'guest:view', 1, 10, CURRENT_TIMESTAMP)"
            )
        )


def test_rbac_expand_contract_round_trip_preserves_safe_legacy_decisions():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "rbac.db")
        _alembic(cwd, db_path, "upgrade", PRE_REVISION)
        engine = _engine(db_path)
        try:
            _seed_pre_revision(engine)
        finally:
            engine.dispose()

        _alembic(cwd, db_path, "upgrade", REVISION)
        engine = _engine(db_path)
        try:
            assert "user_permission_overrides" in inspect(engine).get_table_names()
            with engine.begin() as connection:
                assert bool(connection.execute(
                    text(
                        "SELECT allowed FROM hotel_permission_overrides "
                        "WHERE hotel_id=1 AND role='receptionist' AND permission_code='guest:read'"
                    )
                ).scalar()) is True
                connection.execute(
                    text(
                        "INSERT INTO user_permission_overrides "
                        "(hotel_id, user_id, permission_code, allowed, updated_by_user_id) "
                        "VALUES (1, 10, 'guest:read', 1, 10)"
                    )
                )
                connection.execute(
                    text(
                        "UPDATE hotel_permission_overrides SET allowed=0 "
                        "WHERE hotel_id=1 AND role='receptionist' AND permission_code='guest:read'"
                    )
                )
            with pytest.raises(IntegrityError):
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            "INSERT INTO user_permission_overrides "
                            "(hotel_id, user_id, permission_code, allowed) "
                            "VALUES (1, 20, 'guest:read', 1)"
                        )
                    )
        finally:
            engine.dispose()

        _alembic(cwd, db_path, "downgrade", PRE_REVISION)
        engine = _engine(db_path)
        try:
            with engine.connect() as connection:
                assert bool(connection.execute(
                    text(
                        "SELECT allowed FROM hotel_permission_overrides "
                        "WHERE hotel_id=1 AND role='receptionist' AND permission_code='guest:view'"
                    )
                ).scalar()) is False
        finally:
            engine.dispose()

        _alembic(cwd, db_path, "upgrade", REVISION)
        engine = _engine(db_path)
        try:
            with engine.connect() as connection:
                assert bool(connection.execute(
                    text(
                        "SELECT allowed FROM hotel_permission_overrides "
                        "WHERE hotel_id=1 AND role='receptionist' AND permission_code='guest:read'"
                    )
                ).scalar()) is False
        finally:
            engine.dispose()
