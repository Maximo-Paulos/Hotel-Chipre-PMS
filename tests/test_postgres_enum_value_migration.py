"""Unit coverage for the guarded PostgreSQL enum-label migration."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic/versions/20260924_pg_enum_values.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("remaining_pg_enum_values", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Result:
    def __init__(self, rows=()):
        self._rows = list(rows)

    def all(self):
        return self._rows


class _RecordingBind:
    def __init__(self, dialect_name: str, labels_by_type: dict[str, set[str]] | None = None):
        self.dialect = SimpleNamespace(name=dialect_name)
        self.labels_by_type = labels_by_type or {}
        self.statements: list[str] = []

    def execute(self, statement, parameters=None):
        sql = str(statement)
        self.statements.append(sql)
        if sql.startswith("SELECT n.nspname"):
            labels = self.labels_by_type.get(parameters["type_name"], set())
            return _Result(("public", label) for label in sorted(labels))

        if sql.startswith('ALTER TYPE "public".'):
            import re

            match = re.fullmatch(
                r'ALTER TYPE "public"\."([^\"]+)" RENAME VALUE \'([^\']+)\' TO \'([^\']+)\'',
                sql,
            )
            assert match is not None, sql
            type_name, old_value, new_value = match.groups()
            labels = self.labels_by_type[type_name]
            assert old_value in labels
            assert new_value not in labels
            labels.remove(old_value)
            labels.add(new_value)
            return _Result()

        raise AssertionError(f"Unexpected SQL: {sql}")


def _uppercase_catalog(migration):
    return {
        type_name: {old for old, _new in pairs}
        for type_name, pairs in migration.ENUM_VALUE_RENAMES.items()
    }


def test_upgrade_normalizes_only_remaining_enum_labels_and_is_idempotent(monkeypatch):
    migration = _load_migration()
    bind = _RecordingBind("postgresql", _uppercase_catalog(migration))
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)

    migration.upgrade()

    expected = {
        type_name: {new for _old, new in pairs}
        for type_name, pairs in migration.ENUM_VALUE_RENAMES.items()
    }
    assert bind.labels_by_type == expected
    alter_count = sum(statement.startswith("ALTER TYPE") for statement in bind.statements)
    assert alter_count == sum(len(pairs) for pairs in migration.ENUM_VALUE_RENAMES.values())

    migration.upgrade()
    assert sum(statement.startswith("ALTER TYPE") for statement in bind.statements) == alter_count


def test_downgrade_reverses_only_the_new_migration(monkeypatch):
    migration = _load_migration()
    bind = _RecordingBind(
        "postgresql",
        {type_name: {new for _old, new in pairs} for type_name, pairs in migration.ENUM_VALUE_RENAMES.items()},
    )
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)

    migration.downgrade()

    assert bind.labels_by_type == _uppercase_catalog(migration)


def test_upgrade_fails_closed_if_both_enum_labels_exist(monkeypatch):
    migration = _load_migration()
    labels = _uppercase_catalog(migration)
    labels["ota_connection_status_enum"].add("pending")
    bind = _RecordingBind("postgresql", labels)
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)

    with pytest.raises(RuntimeError, match="contiene ambas etiquetas"):
        migration.upgrade()

    assert "PENDING" in bind.labels_by_type["ota_connection_status_enum"]
    assert "pending" in bind.labels_by_type["ota_connection_status_enum"]


def test_upgrade_fails_closed_when_an_expected_label_is_missing(monkeypatch):
    migration = _load_migration()
    labels = _uppercase_catalog(migration)
    labels["ota_connection_status_enum"].remove("PENDING")
    bind = _RecordingBind("postgresql", labels)
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)

    with pytest.raises(RuntimeError, match="no contiene ni"):
        migration.upgrade()


def test_sqlite_skips_postgresql_enum_ddl(monkeypatch):
    migration = _load_migration()
    bind = _RecordingBind("sqlite")
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)

    migration.upgrade()

    assert bind.statements == []


def test_revision_fits_alembic_version_column():
    migration = _load_migration()

    assert len(migration.revision) <= 32
    assert migration.down_revision == "20260924_custom_hotel_roles"
