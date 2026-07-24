from __future__ import annotations

import pytest
from sqlalchemy import inspect

import app.database as database_module
from app.config import Settings


@pytest.mark.parametrize("app_env", ["production", "preview", "qa", "staging"])
def test_managed_environments_reject_sqlite_schema_bootstrap(monkeypatch, app_env: str) -> None:
    monkeypatch.setattr(
        database_module,
        "get_settings",
        lambda: Settings(APP_ENV=app_env),
    )

    with pytest.raises(RuntimeError, match="automatic schema creation is disabled"):
        database_module.init_db("sqlite:///:memory:")


def test_development_sqlite_bootstrap_remains_available(monkeypatch) -> None:
    monkeypatch.setattr(
        database_module,
        "get_settings",
        lambda: Settings(APP_ENV="development"),
    )

    engine = database_module.init_db("sqlite:///:memory:")

    assert engine.dialect.name == "sqlite"
    assert inspect(engine).has_table("users")
