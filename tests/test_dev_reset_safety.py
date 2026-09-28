from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.engine import make_url

import app.api.demo as demo_api
import app.scripts.dev_reset as dev_reset
import app.scripts.seed_demo as seed_demo
from app.config import get_settings
from app.database import Base
from app.services.demo_reset_safety import DemoResetSafetyError, assert_demo_reset_is_safe


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_dev_reset_rejects_live_before_database_initialization(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("APP_ENV", "live")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TESTING", "true")

    def unexpected_database_access(*_args, **_kwargs):
        pytest.fail("A denied reset must not initialize or mutate the database.")

    monkeypatch.setattr(dev_reset, "init_db", unexpected_database_access)
    monkeypatch.setattr(Base.metadata, "drop_all", unexpected_database_access)
    monkeypatch.setattr(Base.metadata, "create_all", unexpected_database_access)

    with pytest.raises(DemoResetSafetyError, match="unavailable in this environment"):
        dev_reset.reset()


def test_demo_seed_cli_rejects_live_before_database_initialization(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "live")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setattr(
        seed_demo,
        "init_db",
        lambda *_args, **_kwargs: pytest.fail("A denied demo seed must not initialize the database."),
    )

    with pytest.raises(DemoResetSafetyError, match="unavailable in this environment"):
        seed_demo.main()


def test_demo_seed_helper_rejects_live_before_database_query(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "live")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TESTING", "true")

    class LiveTargetSession:
        def get_bind(self):
            return SimpleNamespace(url=make_url("sqlite:///./dev.db"))

        def get(self, *_args, **_kwargs):
            pytest.fail("A live seed must be rejected before reading application data.")

    with pytest.raises(DemoResetSafetyError, match="unavailable in this environment"):
        seed_demo.seed(LiveTargetSession())


def test_dev_reset_keeps_explicit_development_workflow(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("TESTING", "false")
    engine = object()
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(dev_reset, "init_db", lambda _db_url: engine)
    monkeypatch.setattr(
        Base.metadata,
        "drop_all",
        lambda *, bind: calls.append(("drop", bind)),
    )
    monkeypatch.setattr(
        Base.metadata,
        "create_all",
        lambda *, bind: calls.append(("create", bind)),
    )

    dev_reset.reset("sqlite:///./dev.db")

    assert calls == [("drop", engine), ("create", engine)]


def test_dev_reset_rejects_hosted_database_when_environment_says_development(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setattr(
        dev_reset,
        "init_db",
        lambda *_args, **_kwargs: pytest.fail("A hosted target must be rejected before initialization."),
    )

    with pytest.raises(DemoResetSafetyError, match="approved local database"):
        dev_reset.reset("postgresql+psycopg2://pms@db.example.invalid/hotel_pms")


def test_demo_reset_api_rejects_hosted_database_before_commit_or_ddl(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TESTING", "false")
    calls: list[str] = []

    class RemoteTargetSession:
        def get_bind(self):
            return SimpleNamespace(url=make_url("postgresql://pms@db.example.invalid/hotel_pms"))

        def rollback(self):
            calls.append("rollback")

        def commit(self):
            calls.append("commit")

    def unexpected_ddl(*_args, **_kwargs):
        pytest.fail("A hosted target must never reach table DDL.")

    monkeypatch.setattr(Base.metadata, "drop_all", unexpected_ddl)
    monkeypatch.setattr(Base.metadata, "create_all", unexpected_ddl)

    with pytest.raises(HTTPException) as exc_info:
        demo_api.reset_demo(db=RemoteTargetSession())

    assert exc_info.value.status_code == 404
    assert calls == ["rollback"]


def test_demo_seed_api_rejects_hosted_database_before_query_or_seed(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TESTING", "false")

    class RemoteTargetSession:
        def get_bind(self):
            return SimpleNamespace(url=make_url("postgresql://pms@db.example.invalid/hotel_pms"))

        def rollback(self):
            return None

        def query(self, *_args, **_kwargs):
            pytest.fail("A hosted demo target must be rejected before querying or seeding.")

    monkeypatch.setattr(
        "app.scripts.seed_demo.seed",
        lambda *_args, **_kwargs: pytest.fail("A hosted target must never be seeded."),
    )

    with pytest.raises(HTTPException) as exc_info:
        demo_api.seed_demo(db=RemoteTargetSession())

    assert exc_info.value.status_code == 404


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite:///./dev.db",
        "postgresql+psycopg2://pms@localhost:5432/hotel_pms",
        "postgresql+psycopg2://pms@db:5432/hotel_pms",
    ],
)
def test_demo_reset_target_allowlist_keeps_local_development_databases(
    monkeypatch: pytest.MonkeyPatch, database_url: str
):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    assert_demo_reset_is_safe(database_url)


def test_demo_reset_target_rejects_postgres_connection_overrides(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    with pytest.raises(DemoResetSafetyError, match="approved local database"):
        assert_demo_reset_is_safe(
            "postgresql+psycopg2://pms@localhost:5432/hotel_pms?hostaddr=198.51.100.10"
        )
