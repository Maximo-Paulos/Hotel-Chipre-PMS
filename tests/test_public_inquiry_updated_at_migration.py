import importlib.util
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


_VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _VERSIONS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SCHEMA = _load("public_inquiry_updated_at_schema", "20260928_public_inquiry_updated_at.py")
_ANCHOR = _load("public_inquiry_retention_anchor", "20260928_public_inquiry_retention_anchor.py")


def test_schema_and_backfill_migrations_make_last_update_the_retention_anchor(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    created_at = datetime(2026, 6, 1, 12, 30)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE public_inquiries ("
                "id INTEGER PRIMARY KEY, created_at DATETIME NOT NULL, email VARCHAR(320) NOT NULL)"
            )
            connection.execute(
                sa.text("INSERT INTO public_inquiries (id, created_at, email) VALUES (1, :created_at, :email)"),
                {"created_at": created_at, "email": "synthetic@example.test"},
            )
            operations = Operations(MigrationContext.configure(connection))
            monkeypatch.setattr(_SCHEMA, "op", operations)
            monkeypatch.setattr(_ANCHOR, "op", operations)

            _SCHEMA.upgrade()
            _ANCHOR.upgrade()

            row = connection.execute(
                sa.text("SELECT created_at, updated_at FROM public_inquiries WHERE id = 1")
            ).one()
            assert row.created_at == row.updated_at
            column = next(
                item for item in sa.inspect(connection).get_columns("public_inquiries")
                if item["name"] == "updated_at"
            )
            assert column["nullable"] is False
            assert "ix_public_inquiries_updated_at" in {
                item["name"] for item in sa.inspect(connection).get_indexes("public_inquiries")
            }
    finally:
        engine.dispose()


def test_postgresql_expand_column_has_database_default_for_older_writers(monkeypatch):
    class FakeInspector:
        @staticmethod
        def has_table(name, schema=None):
            return True

        @staticmethod
        def get_columns(name, schema=None):
            return [{"name": "id"}, {"name": "created_at"}]

        @staticmethod
        def get_indexes(name, schema=None):
            return []

    class FakeOp:
        def __init__(self):
            self.added_column = None

        @staticmethod
        def get_bind():
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def add_column(self, table, column, schema=None):
            self.added_column = column

        def create_index(self, *args, **kwargs):
            pass

    fake = FakeOp()
    monkeypatch.setattr(_SCHEMA, "op", fake)
    monkeypatch.setattr(_SCHEMA.sa, "inspect", lambda _bind: FakeInspector())

    _SCHEMA.upgrade()

    assert fake.added_column.name == "updated_at"
    assert str(fake.added_column.server_default.arg) == "CURRENT_TIMESTAMP"


def test_retention_function_uses_last_update_and_keeps_legal_hold_checks(monkeypatch):
    class FakeOp:
        def __init__(self):
            self.statements = []

        @staticmethod
        def get_bind():
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def execute(self, statement):
            self.statements.append(str(statement))

    fake = FakeOp()
    monkeypatch.setattr(_ANCHOR, "op", fake)

    _ANCHOR._install_purge_function("updated_at")

    sql = "\n".join(fake.statements)
    assert "inquiry.updated_at < utc_now - INTERVAL '90 days'" in sql
    assert "lead.updated_at < now_utc - INTERVAL '90 days'" in sql
    assert "hold.resource_type = 'public_inquiry'" in sql
    assert "hold.resource_type = 'marketing_lead'" in sql
    assert "LOCK TABLE public.privacy_retention_holds IN SHARE MODE" in sql
    assert "REVOKE ALL PRIVILEGES ON FUNCTION" in sql


def test_retention_anchor_downgrade_refuses_to_discard_legal_hold_history(monkeypatch):
    class FakeOp:
        def __init__(self):
            self.statements = []

        @staticmethod
        def get_bind():
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def execute(self, statement):
            self.statements.append(str(statement))

    fake = FakeOp()
    monkeypatch.setattr(_ANCHOR, "op", fake)

    _ANCHOR.downgrade()

    assert "Cannot downgrade privacy retention while legal hold audit records exist" in fake.statements[0]
