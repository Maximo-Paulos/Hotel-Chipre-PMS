from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import app.api.bookings as bookings_module
import app.config as config_module
import app.database as db_module
import app.main as main_module
from app.config import Settings, get_settings
from app.database import Base, get_db


@pytest.fixture()
def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """FastAPI client backed by an isolated SQLite database."""
    monkeypatch.setenv("APP_ENV", "development")
    db_file = tmp_path / "demo.sqlite"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def fake_get_engine(database_url: str | None = None):
        return engine

    monkeypatch.setattr(db_module, "get_engine", fake_get_engine)
    db_module.init_db(db_url)
    monkeypatch.setattr(main_module, "init_db", lambda: db_module.init_db(db_url))

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[get_db] = override_get_db

    with TestClient(main_module.app) as test_client:
        yield test_client

    main_module.app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_seed_and_reset_blocked_by_default(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Demo endpoints must be off unless explicitly enabled."""
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    seed = client.post("/api/seed")
    reset = client.post("/api/reset")

    assert seed.status_code == 403
    assert reset.status_code == 403
    assert "Demo mode" in seed.json()["detail"]


@pytest.mark.parametrize("environment_key", ["APP_ENV", "ENVIRONMENT"])
def test_seed_and_reset_allowed_when_demo_enabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, environment_key: str
):
    """Explicit development environments retain the DEMO_MODE workflow."""
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv(environment_key, "development")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TESTING", "false")
    get_settings.cache_clear()

    seed = client.post("/api/seed")
    assert seed.status_code == 200
    assert seed.json()["status"] in {"seeded", "already_seeded"}

    reset = client.post("/api/reset")
    assert reset.status_code == 200
    assert reset.json()["status"] == "reset_empty"


@pytest.mark.parametrize("testing_value", ["false", "0", "no", "off", "False"])
def test_false_testing_values_do_not_bypass_demo_guard(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, testing_value: str
):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.setenv("TESTING", testing_value)

    response = client.post("/api/reset")

    assert response.status_code == 403, response.text


def test_demo_reset_is_unavailable_in_production_even_if_flags_are_enabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TESTING", "true")
    get_settings.cache_clear()

    response = client.post("/api/reset")

    assert response.status_code == 404, response.text


def test_demo_utilities_are_unavailable_in_preview_even_if_test_flags_are_enabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("APP_ENV", "qa")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TESTING", "true")
    get_settings.cache_clear()

    for endpoint in ("/api/seed", "/api/reset"):
        response = client.post(endpoint)
        assert response.status_code == 404, response.text


@pytest.mark.parametrize(
    ("environment_key", "environment_value"),
    [("APP_ENV", "live"), ("ENVIRONMENT", "live"), ("APP_ENV", "test")],
)
def test_demo_utilities_fail_closed_for_unknown_environment_even_with_flags_enabled(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    environment_key: str,
    environment_value: str,
):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv(environment_key, environment_value)
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TESTING", "true")
    get_settings.cache_clear()

    import app.scripts.seed_demo as seed_demo_module

    def unexpected_side_effect(*args, **kwargs):
        pytest.fail("A denied demo request reached a data mutation.")

    monkeypatch.setattr(seed_demo_module, "seed", unexpected_side_effect)
    monkeypatch.setattr(Base.metadata, "drop_all", unexpected_side_effect)
    monkeypatch.setattr(Base.metadata, "create_all", unexpected_side_effect)

    for endpoint in ("/api/seed", "/api/reset"):
        response = client.post(endpoint)
        assert response.status_code == 404, response.text


@pytest.mark.parametrize(
    ("app_env", "environment"),
    [("development", "production"), ("production", "development")],
)
def test_demo_utilities_fail_closed_when_environment_sources_conflict(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, app_env: str, environment: str
):
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TESTING", "true")
    get_settings.cache_clear()

    for endpoint in ("/api/seed", "/api/reset"):
        response = client.post(endpoint)
        assert response.status_code == 404, response.text


def test_demo_guard_rejects_implicit_development_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TESTING", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(config_module, "get_settings", lambda: Settings(_env_file=None))

    with pytest.raises(HTTPException) as exc_info:
        bookings_module._require_demo_mode()

    assert exc_info.value.status_code == 404


def test_demo_guard_accepts_explicit_settings_development_fallback(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setattr(
        config_module,
        "get_settings",
        lambda: Settings(_env_file=None, APP_ENV="development"),
    )

    assert config_module.is_demo_environment_allowed()


def test_demo_guard_rejects_conflicting_settings_fallback(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setattr(
        config_module,
        "get_settings",
        lambda: Settings(_env_file=None, APP_ENV="production"),
    )

    assert not config_module.is_demo_environment_allowed()


@pytest.mark.parametrize("environment_key", ["APP_ENV", "ENVIRONMENT"])
def test_booking_demo_seed_guard_fails_closed_for_unknown_environment(
    monkeypatch: pytest.MonkeyPatch, environment_key: str
):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv(environment_key, "live")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TESTING", "true")
    get_settings.cache_clear()

    with pytest.raises(HTTPException) as exc_info:
        bookings_module._require_demo_mode()

    assert exc_info.value.status_code == 404


def test_demo_routes_hidden_from_openapi_by_default(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    paths = client.app.openapi()["paths"]
    assert "/api/seed" not in paths
    assert "/api/reset" not in paths
