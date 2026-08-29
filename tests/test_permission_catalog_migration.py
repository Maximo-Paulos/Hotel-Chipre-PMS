"""Regression coverage for the additive permission-catalog migration."""

import os
import subprocess
import sys

from sqlalchemy import bindparam, create_engine, text
from tests.migration_helpers import insert_historical_hotel_config


PRE_REVISION = "20260821_apple_sign_in"
REVISION = "20260828_permission_catalog"
NEW_CODES = (
    "analytics:view",
    "analytics:advanced:view",
    "analytics:ai:view",
    "dashboard:view",
    "occupancy:view",
    "waitlist:view",
    "waitlist:manage",
    "cash:view",
    "company:view",
    "settings:users:view",
    "settings:users:manage",
    "settings:integrations:view",
    "settings:integrations:manage",
    "settings:subscription:view",
    "settings:security:view",
    "settings:sessions:view",
    "settings:notifications:view",
    "settings:assistant:view",
    "settings:tests:view",
)


def _alembic(cwd: str, db_path: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=cwd,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_permission_catalog_migration_is_additive_and_reversible(tmp_path):
    cwd = os.path.dirname(os.path.dirname(__file__))
    db_path = str(tmp_path / "permission-catalog.db")

    _alembic(cwd, db_path, "upgrade", PRE_REVISION)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        insert_historical_hotel_config(engine, 1)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO permissions (code, description) "
                    "VALUES ('dashboard:view', 'operator override')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO role_permission_defaults (role, permission_code, allowed) "
                    "VALUES ('manager', 'dashboard:view', 0)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO hotel_permission_overrides "
                    "(hotel_id, role, permission_code, allowed) "
                    "VALUES (1, 'manager', 'dashboard:view', 1)"
                )
            )
    finally:
        engine.dispose()

    _alembic(cwd, db_path, "upgrade", REVISION)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT COUNT(*) FROM permissions WHERE code IN :codes")
                .bindparams(bindparam("codes", expanding=True)),
                {"codes": NEW_CODES},
            ).scalar() == len(NEW_CODES)
            assert connection.execute(
                text(
                    "SELECT description FROM permissions WHERE code = 'dashboard:view'"
                )
            ).scalar() == "operator override"
            assert connection.execute(
                text(
                    "SELECT allowed FROM role_permission_defaults "
                    "WHERE role = 'manager' AND permission_code = 'dashboard:view'"
                )
            ).scalar() == 0
            assert connection.execute(
                text(
                    "SELECT allowed FROM hotel_permission_overrides "
                    "WHERE hotel_id = 1 AND role = 'manager' "
                    "AND permission_code = 'dashboard:view'"
                )
            ).scalar() == 1
            assert connection.execute(
                text(
                    "SELECT COUNT(*) FROM role_permission_defaults "
                    "WHERE permission_code = 'analytics:view'"
                )
            ).scalar() == 5
    finally:
        engine.dispose()

    _alembic(cwd, db_path, "downgrade", PRE_REVISION)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT COUNT(*) FROM role_permission_defaults "
                    "WHERE permission_code = 'analytics:view'"
                )
            ).scalar() == 0
            assert connection.execute(
                text(
                    "SELECT allowed FROM hotel_permission_overrides "
                    "WHERE hotel_id = 1 AND role = 'manager' "
                    "AND permission_code = 'dashboard:view'"
                )
            ).scalar() == 1
    finally:
        engine.dispose()
