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


def test_housekeeping_occupancy_default_migration_tightens_without_touching_grant(tmp_path):
    cwd = os.path.dirname(os.path.dirname(__file__))
    db_path = str(tmp_path / "housekeeping-occupancy-default.db")
    previous_head = "20260829_permission_enforcement"
    new_head = "20260830_hk_occupancy_default"

    _alembic(cwd, db_path, "upgrade", PRE_REVISION)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        insert_historical_hotel_config(engine, 1)
    finally:
        engine.dispose()

    _alembic(cwd, db_path, "upgrade", previous_head)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO hotel_permission_overrides "
                    "(hotel_id, role, permission_code, allowed) "
                    "VALUES (1, 'housekeeping', 'occupancy:view', 1)"
                )
            )
    finally:
        engine.dispose()

    _alembic(cwd, db_path, "upgrade", new_head)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT allowed FROM role_permission_defaults "
                    "WHERE role = 'housekeeping' AND permission_code = 'occupancy:view'"
                )
            ).scalar() == 0
            assert connection.execute(
                text(
                    "SELECT allowed FROM hotel_permission_overrides "
                    "WHERE hotel_id = 1 AND role = 'housekeeping' "
                    "AND permission_code = 'occupancy:view'"
                )
            ).scalar() == 1
            assert connection.execute(
                text(
                    "SELECT COUNT(*) FROM role_permission_defaults "
                    "WHERE role = 'housekeeping' AND permission_code = 'occupancy:view'"
                )
            ).scalar() == 1
    finally:
        engine.dispose()

    _alembic(cwd, db_path, "downgrade", previous_head)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT allowed FROM role_permission_defaults "
                    "WHERE role = 'housekeeping' AND permission_code = 'occupancy:view'"
                )
            ).scalar() == 1
            assert connection.execute(
                text(
                    "SELECT allowed FROM hotel_permission_overrides "
                    "WHERE hotel_id = 1 AND role = 'housekeeping' "
                    "AND permission_code = 'occupancy:view'"
                )
            ).scalar() == 1
    finally:
        engine.dispose()


def test_room_move_tier_migration_is_additive_idempotent_and_preserves_overrides(tmp_path):
    cwd = os.path.dirname(os.path.dirname(__file__))
    db_path = str(tmp_path / "room-move-tiers.db")
    previous_head = "20260830_hk_occupancy_default"
    new_head = "20260830_room_move_tiers"
    category_permission = "reservation:move_category"
    capacity_permission = "reservation:move_capacity"

    _alembic(cwd, db_path, "upgrade", previous_head)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        insert_historical_hotel_config(engine, 1)
        with engine.begin() as connection:
            # Simulate a partially pre-seeded catalog plus an explicit
            # operator choice. The migration must only fill missing rows.
            connection.execute(
                text(
                    "INSERT INTO permissions (code, description) "
                    "VALUES (:code, 'operator description')"
                ),
                {"code": category_permission},
            )
            connection.execute(
                text(
                    "INSERT INTO role_permission_defaults (role, permission_code, allowed) "
                    "VALUES ('manager', :code, 0)"
                ),
                {"code": category_permission},
            )
            connection.execute(
                text(
                    "INSERT INTO hotel_permission_overrides "
                    "(hotel_id, role, permission_code, allowed) "
                    "VALUES (1, 'manager', :code, 0)"
                ),
                {"code": category_permission},
            )
    finally:
        engine.dispose()

    _alembic(cwd, db_path, "upgrade", new_head)
    _alembic(cwd, db_path, "upgrade", new_head)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT description FROM permissions WHERE code = :code"),
                {"code": category_permission},
            ).scalar() == "operator description"
            assert connection.execute(
                text(
                    "SELECT allowed FROM role_permission_defaults "
                    "WHERE role = 'manager' AND permission_code = :code"
                ),
                {"code": category_permission},
            ).scalar() == 0
            assert connection.execute(
                text(
                    "SELECT allowed FROM hotel_permission_overrides "
                    "WHERE hotel_id = 1 AND role = 'manager' AND permission_code = :code"
                ),
                {"code": category_permission},
            ).scalar() == 0
            assert connection.execute(
                text("SELECT COUNT(*) FROM role_permission_defaults WHERE permission_code = :code"),
                {"code": category_permission},
            ).scalar() == 5
            assert connection.execute(
                text("SELECT COUNT(*) FROM role_permission_defaults WHERE permission_code = :code"),
                {"code": capacity_permission},
            ).scalar() == 5
            assert connection.execute(
                text(
                    "SELECT allowed FROM role_permission_defaults "
                    "WHERE role = 'manager' AND permission_code = :code"
                ),
                {"code": capacity_permission},
            ).scalar() == 1
    finally:
        engine.dispose()

    _alembic(cwd, db_path, "downgrade", previous_head)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT COUNT(*) FROM role_permission_defaults WHERE permission_code IN (:category, :capacity)"),
                {"category": category_permission, "capacity": capacity_permission},
            ).scalar() == 0
            assert connection.execute(
                text("SELECT COUNT(*) FROM permissions WHERE code = :code"),
                {"code": category_permission},
            ).scalar() == 1
            assert connection.execute(
                text("SELECT COUNT(*) FROM permissions WHERE code = :code"),
                {"code": capacity_permission},
            ).scalar() == 0
    finally:
        engine.dispose()

def test_permission_enforcement_migration_backfills_defaults_and_removes_sessions(tmp_path):
    cwd = os.path.dirname(os.path.dirname(__file__))
    db_path = str(tmp_path / "permission-enforcement.db")
    previous_head = "20260828_query_shape_indexes"
    new_head = "20260829_permission_enforcement"

    _alembic(cwd, db_path, "upgrade", PRE_REVISION)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        insert_historical_hotel_config(engine, 1)
    finally:
        engine.dispose()


    _alembic(cwd, db_path, "upgrade", previous_head)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE role_permission_defaults SET allowed = 0 "
                    "WHERE (role = 'housekeeping' AND permission_code = 'occupancy:view') "
                    "OR (role = 'manager' AND permission_code = 'company:view')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO hotel_permission_overrides "
                    "(hotel_id, role, permission_code, allowed) VALUES "
                    "(1, 'housekeeping', 'occupancy:view', 0), "
                    "(1, 'manager', 'company:view', 0)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, email, password_hash, is_active, is_verified, role, created_at, updated_at) "
                    "VALUES (10, 'migration@example.test', 'not-a-password', 1, 1, 'owner', "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO hotel_memberships (hotel_id, user_id, role, status) "
                    "VALUES (1, 10, 'owner', 'active')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO hotel_permission_overrides "
                    "(hotel_id, role, permission_code, allowed) "
                    "VALUES (1, 'manager', 'settings:sessions:view', 0)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO user_permission_overrides "
                    "(hotel_id, user_id, permission_code, allowed) "
                    "VALUES (1, 10, 'settings:sessions:view', 1)"
                )
            )
    finally:
        engine.dispose()

    _alembic(cwd, db_path, "upgrade", new_head)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT allowed FROM role_permission_defaults "
                    "WHERE role = 'housekeeping' AND permission_code = 'occupancy:view'"
                )
            ).scalar() == 1
            assert connection.execute(
                text(
                    "SELECT allowed FROM role_permission_defaults "
                    "WHERE role = 'manager' AND permission_code = 'company:view'"
                )
            ).scalar() == 1
            assert connection.execute(
                text(
                    "SELECT allowed FROM hotel_permission_overrides "
                    "WHERE hotel_id = 1 AND role = 'housekeeping' AND permission_code = 'occupancy:view'"
                )
            ).scalar() == 0
            assert connection.execute(
                text(
                    "SELECT allowed FROM hotel_permission_overrides "
                    "WHERE hotel_id = 1 AND role = 'manager' AND permission_code = 'company:view'"
                )
            ).scalar() == 0
            assert connection.execute(
                text("SELECT COUNT(*) FROM permissions WHERE code = 'settings:sessions:view'")
            ).scalar() == 0
            for table in (
                "role_permission_defaults",
                "hotel_permission_overrides",
                "user_permission_overrides",
            ):
                assert connection.execute(
                    text(f"SELECT COUNT(*) FROM {table} WHERE permission_code = 'settings:sessions:view'")
                ).scalar() == 0
    finally:
        engine.dispose()

    _alembic(cwd, db_path, "downgrade", previous_head)
    _alembic(cwd, db_path, "upgrade", new_head)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT COUNT(*) FROM permissions WHERE code = 'settings:sessions:view'")
            ).scalar() == 0
            assert connection.execute(
                text(
                    "SELECT allowed FROM role_permission_defaults "
                    "WHERE role = 'housekeeping' AND permission_code = 'occupancy:view'"
                )
            ).scalar() == 1
    finally:
        engine.dispose()


def test_migrated_defaults_match_the_code_default_matrix(tmp_path):
    """role_permission_defaults must agree with DEFAULT_MATRIX after migrating.

    Runtime authorization reads the table, not the dict. When a permission's
    default changes in code, the change is invisible on every pre-existing
    database unless a migration updates the row too -- and the rest of the
    suite cannot see the gap, because it builds permissions from the dict.

    reservation:move is why this test exists: it was flipped on for
    receptionists in code while the migrated row stayed False.
    """
    from app.services.permission_service import DEFAULT_MATRIX

    cwd = os.path.dirname(os.path.dirname(__file__))
    db_path = str(tmp_path / "defaults-parity.db")
    _alembic(cwd, db_path, "upgrade", "head")

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as connection:
            migrated = {
                (row[0], row[1]): bool(row[2])
                for row in connection.execute(
                    text("SELECT role, permission_code, allowed FROM role_permission_defaults")
                ).all()
            }
    finally:
        engine.dispose()

    mismatches = sorted(
        f"{role}/{code}: code={expected} migrated={migrated[(role, code)]}"
        for role, permissions in DEFAULT_MATRIX.items()
        for code, expected in permissions.items()
        if (role, code) in migrated and migrated[(role, code)] is not bool(expected)
    )
    assert not mismatches, "DEFAULT_MATRIX and role_permission_defaults disagree: " + "; ".join(mismatches)
