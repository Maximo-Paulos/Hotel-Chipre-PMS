"""SQLite round-trip for the configurable reservation price permission."""

import os
import subprocess
import sys
import tempfile

from sqlalchemy import create_engine, text


PREVIOUS_REVISION = "20261006_company_night_surcharges"
RATE_ADJUST_REVISION = "20261007_reservation_rate_adjust_permission"
OWNER_DEFAULT_REVISION = "20261008_owner_rate_adjust_default"
LATEST_REVISION = "20261011_co_owner_manual_rate_default"


def _run_alembic(cwd: str, db_path: str, *args: str) -> None:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )
    assert result.returncode == 0, (
        f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
    )


def _assert_permission_defaults(
    db_path: str,
    present: bool,
    *,
    owner_allowed: bool = True,
    co_owner_manual_rate_allowed: bool = True,
) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            permission = connection.execute(
                text(
                    "SELECT critical, step_up_required, delegable FROM permissions "
                    "WHERE code = 'reservation:rate_adjust'"
                )
            ).first()
            if not present:
                assert permission is None
                co_owner_manual_rate = connection.execute(
                    text(
                        "SELECT allowed FROM role_permission_defaults "
                        "WHERE role = 'co_owner' AND permission_code = 'reservation:manual_rate_limited'"
                    )
                ).scalar_one()
                assert bool(co_owner_manual_rate) is co_owner_manual_rate_allowed
                return

            assert permission == (False, False, True)
            defaults = {
                row[0]: row[1]
                for row in connection.execute(
                    text(
                        "SELECT role, allowed FROM role_permission_defaults "
                        "WHERE permission_code = 'reservation:rate_adjust'"
                    )
                )
            }
            assert defaults == {
                "owner": owner_allowed,
                "co_owner": False,
                "manager": True,
                "receptionist": False,
                "housekeeping": False,
            }
            co_owner_manual_rate = connection.execute(
                text(
                    "SELECT allowed FROM role_permission_defaults "
                    "WHERE role = 'co_owner' AND permission_code = 'reservation:manual_rate_limited'"
                )
            ).scalar_one()
            assert bool(co_owner_manual_rate) is co_owner_manual_rate_allowed
    finally:
        engine.dispose()


def test_reservation_rate_adjust_permission_migration_upgrade_downgrade_upgrade():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/reservation-rate-adjust.db"
        _run_alembic(cwd, db_path, "upgrade", PREVIOUS_REVISION)
        _assert_permission_defaults(db_path, present=False)

        _run_alembic(cwd, db_path, "upgrade", RATE_ADJUST_REVISION)
        _assert_permission_defaults(
            db_path,
            present=True,
            co_owner_manual_rate_allowed=False,
        )

        _run_alembic(cwd, db_path, "upgrade", OWNER_DEFAULT_REVISION)
        _assert_permission_defaults(
            db_path,
            present=True,
            owner_allowed=False,
            co_owner_manual_rate_allowed=False,
        )

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
                connection.execute(
                    text(
                        "INSERT INTO hotel_permission_overrides "
                        "(hotel_id, role, permission_code, allowed, version, updated_at) "
                        "VALUES (1, 'co_owner', 'reservation:manual_rate_limited', 0, 1, CURRENT_TIMESTAMP)"
                    )
                )
                connection.execute(
                    text(
                        "INSERT INTO user_permission_overrides "
                        "(hotel_id, user_id, permission_code, allowed, version, updated_at) "
                        "VALUES (1, 2, 'reservation:manual_rate_limited', 1, 1, CURRENT_TIMESTAMP)"
                    )
                )
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "upgrade", LATEST_REVISION)
        _assert_permission_defaults(
            db_path,
            present=True,
            owner_allowed=False,
            co_owner_manual_rate_allowed=True,
        )
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                assert bool(connection.execute(
                    text(
                        "SELECT allowed FROM hotel_permission_overrides "
                        "WHERE hotel_id = 1 AND role = 'co_owner' "
                        "AND permission_code = 'reservation:manual_rate_limited'"
                    )
                ).scalar_one()) is False
                assert bool(connection.execute(
                    text(
                        "SELECT allowed FROM user_permission_overrides "
                        "WHERE hotel_id = 1 AND user_id = 2 "
                        "AND permission_code = 'reservation:manual_rate_limited'"
                    )
                ).scalar_one()) is True
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "downgrade", RATE_ADJUST_REVISION)
        _assert_permission_defaults(
            db_path,
            present=True,
            co_owner_manual_rate_allowed=False,
        )

        _run_alembic(cwd, db_path, "downgrade", PREVIOUS_REVISION)
        _assert_permission_defaults(db_path, present=False)

        _run_alembic(cwd, db_path, "upgrade", OWNER_DEFAULT_REVISION)
        _assert_permission_defaults(
            db_path,
            present=True,
            owner_allowed=False,
            co_owner_manual_rate_allowed=False,
        )

        _run_alembic(cwd, db_path, "upgrade", LATEST_REVISION)
        _assert_permission_defaults(
            db_path,
            present=True,
            owner_allowed=False,
            co_owner_manual_rate_allowed=True,
        )
