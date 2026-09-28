"""Regression coverage for the additive movement-group permission migration."""

import os
import subprocess
import sys

from sqlalchemy import create_engine, text


PRE_REVISION = "20260928_public_inquiry_retention_anchor"
REVISION = "20260928_movement_group_revert"
PERMISSION = "reservation:movement_group_revert"


def _alembic(cwd: str, db_path: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=cwd,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_migration_seeds_dedicated_permission_and_safe_role_defaults(tmp_path):
    cwd = os.path.dirname(os.path.dirname(__file__))
    db_path = str(tmp_path / "movement-group-revert-permission.db")

    _alembic(cwd, db_path, "upgrade", PRE_REVISION)
    _alembic(cwd, db_path, "upgrade", REVISION)

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            permission = connection.execute(
                text(
                    "SELECT description, critical, step_up_required, delegable "
                    "FROM permissions WHERE code = :code"
                ),
                {"code": PERMISSION},
            ).one()
            assert tuple(permission) == ("Revert allocation movement groups", 0, 0, 1)

            defaults = {
                role: bool(allowed)
                for role, allowed in connection.execute(
                    text(
                        "SELECT role, allowed FROM role_permission_defaults "
                        "WHERE permission_code = :code"
                    ),
                    {"code": PERMISSION},
                ).all()
            }
            assert defaults == {
                "owner": True,
                "co_owner": True,
                "manager": True,
                "receptionist": False,
                "housekeeping": False,
            }
    finally:
        engine.dispose()
