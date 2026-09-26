import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


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


def test_retention_uses_policy_timestamps_and_daily_schedule(monkeypatch):
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

    sql = "\n".join(fake_op.statements)
    assert "CREATE EXTENSION IF NOT EXISTS pg_cron WITH SCHEMA pg_catalog" in sql
    assert "GRANT USAGE ON SCHEMA cron TO postgres" in sql
    assert "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA cron TO postgres" in sql

    retention_function = next(
        statement
        for statement in fake_op.statements
        if "DELETE FROM public.public_inquiries" in statement
    )
    assert "WHERE created_at < utc_now - INTERVAL '90 days'" in retention_function
    assert "WHERE updated_at < now_utc - INTERVAL '90 days'" in retention_function
    assert "WHERE created_at < now_utc - INTERVAL '90 days'" not in retention_function

    scheduled_job = next(statement for statement in fake_op.statements if "cron.schedule(" in statement)
    assert f"'{_MIGRATION._JOB_NAME}'" in scheduled_job
    assert "'0 4 * * *'" in scheduled_job


_LEGAL_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260926_legal_retention_holds.py"
)
_LEGAL_SPEC = importlib.util.spec_from_file_location("legal_retention_holds_migration", _LEGAL_MIGRATION_PATH)
assert _LEGAL_SPEC is not None and _LEGAL_SPEC.loader is not None
_LEGAL_MIGRATION = importlib.util.module_from_spec(_LEGAL_SPEC)
_LEGAL_SPEC.loader.exec_module(_LEGAL_MIGRATION)


def test_legal_hold_schema_and_purge_are_a_followup_revision(monkeypatch):
    class FakeBind:
        dialect = SimpleNamespace(name="postgresql")

    class FakeOp:
        def __init__(self):
            self.statements = []

        @staticmethod
        def get_bind():
            return FakeBind()

        def execute(self, statement):
            self.statements.append(str(statement))

    fake_op = FakeOp()
    monkeypatch.setattr(_LEGAL_MIGRATION, "op", fake_op)
    _LEGAL_MIGRATION.upgrade()

    all_sql = "\n".join(fake_op.statements)
    assert _LEGAL_MIGRATION.down_revision == _MIGRATION.revision
    assert "CREATE TABLE public.privacy_retention_holds" in all_sql
    assert "ALTER TABLE public.privacy_retention_holds ENABLE ROW LEVEL SECURITY" in all_sql
    assert "CREATE INDEX ix_marketing_leads_updated_at ON public.marketing_leads (updated_at)" in all_sql
    assert "LOCK TABLE public.privacy_retention_holds IN SHARE MODE" in all_sql
    assert "inquiry.created_at < utc_now - INTERVAL '90 days'" in all_sql
    assert "lead.updated_at < now_utc - INTERVAL '90 days'" in all_sql
    assert "hold.resource_type = 'public_inquiry'" in all_sql
    assert "hold.resource_type = 'marketing_lead'" in all_sql
    assert "hold.released_at IS NULL" in all_sql
    assert "hold.hold_until IS NULL OR hold.hold_until > now_utc" in all_sql
    assert "'marketing_lead_global'" in all_sql
    assert "REVOKE ALL PRIVILEGES ON TABLE public.privacy_retention_holds FROM %I" in all_sql
    assert "cron.schedule(" in all_sql
    assert "pg_cron is required to enforce public-form retention" in all_sql


@pytest.mark.parametrize("runtime_env,required", [("production", True), ("", True), ("unknown", True), ("development", False), ("qa", False)])
def test_legal_hold_migration_requires_cron_outside_known_nonproduction(runtime_env, required, monkeypatch):
    monkeypatch.setattr(_LEGAL_MIGRATION.os, "getenv", lambda _name, default="": runtime_env)
    assert _LEGAL_MIGRATION._cron_is_required() is required


def test_legal_hold_migration_creates_and_drops_sqlite_support_tables(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(sa.text("CREATE TABLE marketing_leads (id INTEGER PRIMARY KEY, updated_at DATETIME)"))
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(_LEGAL_MIGRATION, "op", operations)

        _LEGAL_MIGRATION._upgrade_sqlite()
        inspector = sa.inspect(connection)
        assert inspector.has_table("privacy_retention_holds")
        assert "ix_privacy_retention_holds_lookup" in {
            index["name"] for index in inspector.get_indexes("privacy_retention_holds")
        }
        assert "ix_marketing_leads_updated_at" in {
            index["name"] for index in inspector.get_indexes("marketing_leads")
        }

        _LEGAL_MIGRATION._downgrade_sqlite()
        inspector = sa.inspect(connection)
        assert not inspector.has_table("privacy_retention_holds")
        assert "ix_marketing_leads_updated_at" not in {
            index["name"] for index in inspector.get_indexes("marketing_leads")
        }


def test_legal_hold_downgrade_blocks_effective_holds_and_restores_base_purge(monkeypatch):
    class FakeBind:
        dialect = SimpleNamespace(name="postgresql")

    class FakeOp:
        def __init__(self):
            self.statements = []

        @staticmethod
        def get_bind():
            return FakeBind()

        def execute(self, statement):
            self.statements.append(str(statement))

    fake_op = FakeOp()
    monkeypatch.setattr(_LEGAL_MIGRATION, "op", fake_op)
    _LEGAL_MIGRATION.downgrade()

    all_sql = "\n".join(fake_op.statements)
    assert "LOCK TABLE public.privacy_retention_holds IN ACCESS EXCLUSIVE MODE" in all_sql
    assert "Cannot downgrade while effective privacy retention holds exist" in all_sql
    assert "DROP TABLE public.privacy_retention_holds" in all_sql
    assert "DROP INDEX IF EXISTS public.ix_marketing_leads_updated_at" in all_sql
    # With the legal-hold table removed, the downgraded function cannot keep a
    # stale reference to it and scheduled deletion continues normally.
    assert "LOCK TABLE public.privacy_retention_holds IN SHARE MODE" not in all_sql


_PERMISSION_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260927_payment_proof_capabilities.py"
)
_PERMISSION_SPEC = importlib.util.spec_from_file_location(
    "payment_proof_capabilities_migration", _PERMISSION_MIGRATION_PATH
)
assert _PERMISSION_SPEC is not None and _PERMISSION_SPEC.loader is not None
_PERMISSION_MIGRATION = importlib.util.module_from_spec(_PERMISSION_SPEC)
_PERMISSION_SPEC.loader.exec_module(_PERMISSION_MIGRATION)


def test_payment_proof_migration_preserves_existing_explicit_financial_overrides(monkeypatch):
    class FakeConnection:
        dialect = SimpleNamespace(name="postgresql")

        def __init__(self):
            self.statements = []

        def execute(self, statement, params):
            self.statements.append((str(statement), dict(params)))

    connection = FakeConnection()
    class FakeOp:
        @staticmethod
        def get_bind():
            return connection

    monkeypatch.setattr(_PERMISSION_MIGRATION, "op", FakeOp())
    _PERMISSION_MIGRATION.upgrade()

    sql = "\n".join(statement for statement, _params in connection.statements)
    assert _PERMISSION_MIGRATION.down_revision == _LEGAL_MIGRATION.revision
    assert "INSERT INTO permissions" in sql
    assert "INSERT INTO role_permission_defaults" in sql
    assert "INSERT INTO hotel_permission_overrides" in sql
    assert "INSERT INTO user_permission_overrides" in sql
    assert "NOT EXISTS" in sql
    assert "ON CONFLICT" in sql
    assert "old.updated_by_user_id" in sql
    assert "old.updated_at" in sql
    assert any(params.get("legacy_code") == _PERMISSION_MIGRATION._LEGACY for _statement, params in connection.statements)
