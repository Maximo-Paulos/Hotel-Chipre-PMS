from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest


class FakeConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def exec_driver_sql(self, statement: str) -> None:
        self.statements.append(statement)


class FakeEngine:
    def __init__(self, dialect: str = "postgresql") -> None:
        self.dialect = SimpleNamespace(name=dialect)
        self.connection = FakeConnection()

    @contextmanager
    def begin(self):
        yield self.connection


def test_repair_adds_only_missing_cash_handoff_schema_objects():
    from app.scripts.repair_cash_handoff_schema import repair_cash_handoff_schema

    engine = FakeEngine()
    repair_cash_handoff_schema(engine)

    statements = "\n".join(engine.connection.statements)
    assert "ADD COLUMN IF NOT EXISTS successor_session_id" in statements
    assert "uq_cash_close_reports_successor_session" in statements
    assert "fk_cash_close_reports_hotel_successor_session" in statements


def test_repair_refuses_non_postgres_targets():
    from app.scripts.repair_cash_handoff_schema import CashHandoffSchemaRepairError, repair_cash_handoff_schema

    with pytest.raises(CashHandoffSchemaRepairError):
        repair_cash_handoff_schema(FakeEngine("sqlite"))
