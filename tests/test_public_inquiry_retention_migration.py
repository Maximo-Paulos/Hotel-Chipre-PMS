import importlib.util
from pathlib import Path

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
