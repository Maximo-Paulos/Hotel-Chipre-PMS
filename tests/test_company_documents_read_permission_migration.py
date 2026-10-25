"""Regression coverage for the additive company-document read permission."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

PERMISSION = "company:documents:read"
DESCRIPTION = "Read company vouchers and signatures"


def test_migration_seeds_defaults_idempotently_and_preserves_overrides():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20261025_company_documents_read_permission.py"
    )
    spec = importlib.util.spec_from_file_location("company_documents_read_permission_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE permissions (code TEXT PRIMARY KEY, description TEXT NOT NULL, "
                    "critical BOOLEAN NOT NULL, step_up_required BOOLEAN NOT NULL, delegable BOOLEAN NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE role_permission_defaults (role TEXT NOT NULL, permission_code TEXT NOT NULL, "
                    "allowed BOOLEAN NOT NULL, UNIQUE(role, permission_code))"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE hotel_permission_overrides (hotel_id INTEGER NOT NULL, role TEXT NOT NULL, "
                    "permission_code TEXT NOT NULL, allowed BOOLEAN NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO hotel_permission_overrides "
                    "(hotel_id, role, permission_code, allowed) VALUES (1, 'receptionist', :code, true)"
                ),
                {"code": PERMISSION},
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()

            permission = connection.execute(
                text(
                    "SELECT description, critical, step_up_required, delegable "
                    "FROM permissions WHERE code = :code"
                ),
                {"code": PERMISSION},
            ).one()
            assert tuple(permission) == (DESCRIPTION, 0, 0, 1)

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
            override = connection.execute(
                text(
                    "SELECT allowed FROM hotel_permission_overrides "
                    "WHERE hotel_id = 1 AND role = 'receptionist' AND permission_code = :code"
                ),
                {"code": PERMISSION},
            ).one()
            assert bool(override.allowed) is True
    finally:
        engine.dispose()
