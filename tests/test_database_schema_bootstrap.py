from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text

import app.database as database_module
from app.config import Settings
from app.models.analytics import AnalyticsFactRefreshJob


@pytest.mark.parametrize("app_env", ["production", "live", "preview", "qa", "staging"])
def test_managed_environments_reject_sqlite_schema_bootstrap(monkeypatch, app_env: str) -> None:
    monkeypatch.setattr(
        database_module,
        "get_settings",
        lambda: Settings(APP_ENV=app_env),
    )

    with pytest.raises(RuntimeError, match="automatic schema creation is disabled"):
        database_module.init_db("sqlite:///:memory:")


def test_environment_production_alias_rejects_sqlite_schema_bootstrap(monkeypatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(
        database_module,
        "get_settings",
        lambda: Settings(_env_file=None),
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


def test_callable_timestamp_defaults_are_not_bound_as_backfill_values() -> None:
    column = AnalyticsFactRefreshJob.__table__.c.available_at

    assert database_module._column_fill_value(column) is None


def test_schema_backfill_only_updates_nullable_drift_columns() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE analytics_fact_refresh_jobs (attempts INTEGER NULL)")
            )
            connection.execute(
                text("INSERT INTO analytics_fact_refresh_jobs (attempts) VALUES (NULL)")
            )

        database_module._backfill_not_null_nulls(engine)

        with engine.connect() as connection:
            attempts = connection.execute(
                text("SELECT attempts FROM analytics_fact_refresh_jobs")
            ).scalar_one()
        assert attempts == 0
    finally:
        engine.dispose()
