from __future__ import annotations

import importlib.util
from pathlib import Path

import app.models  # noqa: F401
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.services.tenant_context import set_tenant_context, set_tenant_hotel_context


def _load_rls_migration():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "20260724_tenant_rls_context.py"
    spec = importlib.util.spec_from_file_location("tenant_rls_context_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rls_migration_covers_every_hotel_scoped_model_table():
    migration = _load_rls_migration()
    model_tables = {
        table.name
        for table in Base.metadata.sorted_tables
        if "hotel_id" in table.c
    }
    expected = model_tables - {"hotel_api_keys", "hotel_memberships"}
    assert set(migration.TENANT_TABLES) == expected
    assert "hotel_memberships" not in migration.TENANT_TABLES


def test_rls_migration_keeps_api_key_bootstrap_exception_explicit():
    migration = _load_rls_migration()
    source = Path(migration.__file__).read_text(encoding="utf-8")
    assert "hotel_api_keys is intentionally" in source
    assert "current_setting('app.hotel_id', true)" in source
    assert "FORCE ROW LEVEL SECURITY" in source


def test_tenant_context_is_safe_for_local_sqlite_sessions():
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as db:
        set_tenant_context(db, user_id=7, hotel_id=42)
        set_tenant_hotel_context(db, None)


@pytest.mark.parametrize("user_id,hotel_id", [(0, 1), (1, 0), (-1, 1), (1, -1)])
def test_tenant_context_rejects_invalid_principals(user_id: int, hotel_id: int):
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as db:
        with pytest.raises(ValueError):
            set_tenant_context(db, user_id=user_id, hotel_id=hotel_id)
