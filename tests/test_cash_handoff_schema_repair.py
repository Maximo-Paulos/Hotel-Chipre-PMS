from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


MIGRATION_PATH = Path(__file__).parents[1] / "alembic" / "versions" / "20260725_repair_cash_handoff_schema.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("cash_handoff_schema_repair", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeInspector:
    def get_columns(self, table_name: str):
        assert table_name == "cash_close_reports"
        return [{"name": "id"}, {"name": "hotel_id"}, {"name": "session_id"}]

    def get_unique_constraints(self, table_name: str):
        if table_name == "cash_sessions":
            return [{"name": "uq_cash_sessions_hotel_id_id", "column_names": ["hotel_id", "id"]}]
        if table_name == "cash_close_reports":
            return [{"name": "uq_cash_close_reports_hotel_id_id", "column_names": ["hotel_id", "id"]}]
        return []

    def get_indexes(self, table_name: str):
        return []

    def get_foreign_keys(self, table_name: str):
        return []


def test_repair_migration_adds_missing_successor_column_and_constraints(monkeypatch):
    migration = _load_migration()
    bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    added_columns = []
    created_uniques = []
    created_foreign_keys = []

    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: FakeInspector())
    monkeypatch.setattr(migration.op, "add_column", lambda table, column: added_columns.append((table, column)))
    monkeypatch.setattr(
        migration.op,
        "create_unique_constraint",
        lambda name, table, columns: created_uniques.append((name, table, columns)),
    )
    monkeypatch.setattr(
        migration.op,
        "create_foreign_key",
        lambda name, source, target, local, remote, **kwargs: created_foreign_keys.append(
            (name, source, target, local, remote, kwargs)
        ),
    )

    migration.upgrade()

    assert added_columns[0][0] == "cash_close_reports"
    assert added_columns[0][1].name == "successor_session_id"
    assert ("uq_cash_close_reports_successor_session", "cash_close_reports", ["successor_session_id"]) in created_uniques
    assert any(item[0] == "fk_cash_close_reports_successor_session" for item in created_foreign_keys)
    assert any(item[0] == "fk_cash_close_reports_hotel_successor_session" for item in created_foreign_keys)
