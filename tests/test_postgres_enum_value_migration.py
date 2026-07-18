"""Regression coverage for the PostgreSQL OTA/allocation enum repair."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic/versions/20260718_normalize_pg_enum_values.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("enum_value_repair", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _RecordingBind:
    def __init__(self, dialect_name: str):
        self.dialect = SimpleNamespace(name=dialect_name)
        self.statements: list[str] = []

    def execute(self, statement):
        self.statements.append(str(statement))


def test_postgres_enum_value_repair_covers_each_incompatible_model_enum(monkeypatch):
    migration = _load_migration()
    bind = _RecordingBind("postgresql")
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)

    migration.upgrade()

    expected = {
        "ota_connection_status_enum",
        "llm_policy_suggestion_status_enum",
        "ota_sync_job_status_enum",
        "allocation_run_status_enum",
        "allocation_assignment_status_enum",
        "ota_reservation_lifecycle_enum",
        "room_move_type_enum",
        "reservation_adjustment_kind_enum",
        "reservation_adjustment_status_enum",
        "billing_adjustment_type_enum",
    }
    # alembic_version.version_num is VARCHAR(32) in this project.
    assert len(migration.revision) <= 32
    assert set(migration.ENUM_VALUE_RENAMES) == expected
    assert len(bind.statements) == sum(len(values) for values in migration.ENUM_VALUE_RENAMES.values())
    assert any(
        'ALTER TYPE "ota_connection_status_enum" RENAME VALUE \'PENDING\' TO \'pending\''
        in statement
        for statement in bind.statements
    )
    assert all("pg_enum" in statement for statement in bind.statements)


def test_postgres_enum_value_repair_is_a_noop_on_sqlite(monkeypatch):
    migration = _load_migration()
    bind = _RecordingBind("sqlite")
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)

    migration.upgrade()

    assert bind.statements == []
