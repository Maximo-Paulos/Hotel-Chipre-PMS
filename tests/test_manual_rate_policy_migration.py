"""SQLite migration round-trip for bounded manual reservation rates."""

import os
import subprocess
import sys
import tempfile

from sqlalchemy import create_engine, text


PREVIOUS_REVISION = "20261002_stock_transfers"
MANUAL_RATE_REVISION = "20261003_manual_rate_policy"


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


def _assert_schema(db_path: str, present: bool) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            hotel_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(hotel_configuration)"))
            }
            reservation_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(reservations)"))
            }
            assert ("manual_rate_min_adjustment_pct" in hotel_columns) is present
            assert ("manual_rate_max_adjustment_pct" in hotel_columns) is present
            assert ("manual_rate_reason" in reservation_columns) is present
            assert ("manual_rate_scope" in reservation_columns) is present
            if present:
                permissions = {
                    row[0]: (row[1], row[2])
                    for row in connection.execute(
                        text(
                            "SELECT code, step_up_required, delegable FROM permissions "
                            "WHERE code IN ('reservation:manual_rate_limited', "
                            "'reservation:manual_rate_policy_manage')"
                        )
                    )
                }
                assert permissions == {
                    "reservation:manual_rate_limited": (0, 1),
                    "reservation:manual_rate_policy_manage": (1, 0),
                }
                defaults = {
                    (row[0], row[1]): row[2]
                    for row in connection.execute(
                        text(
                            "SELECT role, permission_code, allowed FROM role_permission_defaults "
                            "WHERE permission_code IN ('reservation:manual_rate_limited', "
                            "'reservation:manual_rate_policy_manage')"
                        )
                    )
                }
                assert defaults[("manager", "reservation:manual_rate_limited")] == 1
                assert defaults[("co_owner", "reservation:manual_rate_limited")] == 1
                assert defaults[("receptionist", "reservation:manual_rate_limited")] == 0
                assert defaults[("owner", "reservation:manual_rate_policy_manage")] == 1
                assert defaults[("manager", "reservation:manual_rate_policy_manage")] == 0
    finally:
        engine.dispose()


def test_manual_rate_policy_migration_upgrade_downgrade_upgrade():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/manual-rate-policy.db"
        _run_alembic(cwd, db_path, "upgrade", PREVIOUS_REVISION)
        _run_alembic(cwd, db_path, "upgrade", MANUAL_RATE_REVISION)
        _assert_schema(db_path, present=True)

        _run_alembic(cwd, db_path, "downgrade", PREVIOUS_REVISION)
        _assert_schema(db_path, present=False)

        _run_alembic(cwd, db_path, "upgrade", MANUAL_RATE_REVISION)
        _assert_schema(db_path, present=True)
