import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260918_member_alias_auth.py"
)


def _load_migration():
    assert MIGRATION_PATH.is_file(), "the account and membership migration must exist"
    spec = importlib.util.spec_from_file_location("member_alias_auth_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _run_migration(connection, operation):
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        operation()


def test_migration_backfills_existing_accounts_and_retains_alias_on_rollback():
    migration = _load_migration()
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    users = sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
    )
    memberships = sa.Table(
        "hotel_memberships",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("hotel_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(users.insert().values(id=1, email="existing@example.test", password_hash="hash"))
        connection.execute(memberships.insert().values(id=1, hotel_id=7, user_id=1, role="manager", status="active"))

        _run_migration(connection, migration.upgrade)
        user_columns = {item["name"] for item in sa.inspect(connection).get_columns("users")}
        membership_columns = {item["name"] for item in sa.inspect(connection).get_columns("hotel_memberships")}
        assert "password_login_enabled" in user_columns
        assert {"alias", "alias_key"}.issubset(membership_columns)
        assert connection.execute(sa.text("SELECT password_login_enabled FROM users WHERE id = 1")).scalar_one() in (1, True)

        connection.execute(
            sa.text("UPDATE hotel_memberships SET alias = :alias, alias_key = :key WHERE id = 1"),
            {"alias": "Recepción mañana", "key": "recepción mañana"},
        )
        _run_migration(connection, migration.downgrade)

        assert connection.execute(sa.text("SELECT alias FROM hotel_memberships WHERE id = 1")).scalar_one() == "Recepción mañana"
        assert connection.execute(sa.text("SELECT password_login_enabled FROM users WHERE id = 1")).scalar_one() in (1, True)

        # Downgrade/re-upgrade must be safe because schema and operator data remain.
        _run_migration(connection, migration.upgrade)
        duplicate_alias = sa.text(
            "INSERT INTO hotel_memberships (id, hotel_id, user_id, role, status, alias, alias_key) "
            "VALUES (2, 7, 2, 'manager', 'active', 'OTRA', 'recepción mañana')"
        )
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(duplicate_alias)

    engine.dispose()
