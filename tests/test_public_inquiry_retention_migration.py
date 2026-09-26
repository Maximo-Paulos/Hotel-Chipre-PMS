import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260925_public_inquiry_retention.py"
)
_SPEC = importlib.util.spec_from_file_location("public_inquiry_retention_migration", _MIGRATION_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MIGRATION = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MIGRATION)


def test_pg_cron_migration_skips_only_for_known_non_production_environments():
    assert _MIGRATION._pg_cron_migration_enabled(available=True, runtime_env="production") is True
    assert _MIGRATION._pg_cron_migration_enabled(available=False, runtime_env="development") is False
    assert _MIGRATION._pg_cron_migration_enabled(available=False, runtime_env="preview") is False


@pytest.mark.parametrize("runtime_env", ["production", "", "unknown"])
def test_pg_cron_migration_fails_closed_for_production_or_unknown_environment(runtime_env):
    with pytest.raises(RuntimeError, match="pg_cron is required"):
        _MIGRATION._pg_cron_migration_enabled(available=False, runtime_env=runtime_env)


def test_downgrade_guards_unschedule_when_pg_cron_was_skipped(monkeypatch):
    class FakeOp:
        def __init__(self):
            self.statements = []

        @staticmethod
        def get_bind():
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def execute(self, statement):
            self.statements.append(str(statement))

    fake_op = FakeOp()
    monkeypatch.setattr(_MIGRATION, "op", fake_op)

    _MIGRATION.downgrade()

    assert "to_regclass('cron.job') IS NOT NULL" in fake_op.statements[0]
    assert "cron.unschedule(existing_job.jobid)" in fake_op.statements[0]
    assert fake_op.statements[1] == "DROP FUNCTION IF EXISTS hotel_chipre_private.purge_public_form_data()"


def test_marketing_leads_table_and_sequence_are_closed_to_supabase_api_roles(monkeypatch):
    class FakeOp:
        def __init__(self):
            self.statements = []

        def execute(self, statement):
            self.statements.append(str(statement))

    fake_op = FakeOp()
    monkeypatch.setattr(_MIGRATION, "op", fake_op)

    _MIGRATION._secure_marketing_leads()

    sql = "\n".join(fake_op.statements)
    assert "ALTER TABLE public.marketing_leads ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL PRIVILEGES ON TABLE public.marketing_leads FROM PUBLIC" in sql
    assert "REVOKE ALL PRIVILEGES ON SEQUENCE public.marketing_leads_id_seq FROM PUBLIC" in sql
    for role in ("anon", "authenticated", "service_role"):
        assert role in sql
    assert "REVOKE ALL PRIVILEGES ON TABLE public.marketing_leads FROM %I" in sql
    assert "REVOKE ALL PRIVILEGES ON SEQUENCE public.marketing_leads_id_seq FROM %I" in sql


def test_known_nonproduction_without_pg_cron_still_hardens_marketing_leads(monkeypatch):
    class FakeResult:
        @staticmethod
        def scalar():
            return False

    class FakeBind:
        dialect = SimpleNamespace(name="postgresql")

        @staticmethod
        def execute(_statement):
            return FakeResult()

    class FakeContext:
        as_sql = False

    class FakeOp:
        def __init__(self):
            self.statements = []

        @staticmethod
        def get_bind():
            return FakeBind()

        @staticmethod
        def get_context():
            return FakeContext()

        def execute(self, statement):
            self.statements.append(str(statement))

    fake_op = FakeOp()
    monkeypatch.setattr(_MIGRATION, "op", fake_op)
    monkeypatch.setattr(_MIGRATION.os, "getenv", lambda _name, default="": "development")

    _MIGRATION.upgrade()

    sql = "\n".join(fake_op.statements)
    assert "ALTER TABLE public.marketing_leads ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL PRIVILEGES ON TABLE public.marketing_leads FROM PUBLIC" in sql
    assert "CREATE EXTENSION IF NOT EXISTS pg_cron" not in sql


def test_marketing_lead_retention_uses_creation_age_not_last_update(monkeypatch):
    class FakeResult:
        @staticmethod
        def scalar():
            return True

    class FakeBind:
        dialect = SimpleNamespace(name="postgresql")

        @staticmethod
        def execute(_statement):
            return FakeResult()

    class FakeContext:
        as_sql = False

    class FakeOp:
        def __init__(self):
            self.statements = []

        @staticmethod
        def get_bind():
            return FakeBind()

        @staticmethod
        def get_context():
            return FakeContext()

        def execute(self, statement):
            self.statements.append(str(statement))

    fake_op = FakeOp()
    monkeypatch.setattr(_MIGRATION, "op", fake_op)
    monkeypatch.setattr(_MIGRATION.os, "getenv", lambda _name, default="": "production")

    _MIGRATION.upgrade()

    retention_function = next(
        statement
        for statement in fake_op.statements
        if "DELETE FROM public.marketing_leads" in statement
    )
    assert "WHERE created_at < now_utc - INTERVAL '90 days'" in retention_function
    assert "WHERE updated_at < now_utc - INTERVAL '90 days'" not in retention_function
