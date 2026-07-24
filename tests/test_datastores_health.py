import builtins
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

import app.database as db_module
from app.config import get_settings
from app.database import Base
from app.db.cassandra import cassandra_healthcheck, get_cassandra_session
from app.db.mongo import get_mongo_db, mongo_healthcheck
from app.db.neo4j import get_neo4j_driver, neo4j_healthcheck


@pytest.fixture(autouse=True)
def datastores_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("READ_MODEL_CACHE_ENABLED", "false")
    monkeypatch.setenv("DISTRIBUTED_LOCK_ENABLED", "false")
    monkeypatch.setenv("MONGO_ENABLED", "false")
    monkeypatch.setenv("CASSANDRA_ENABLED", "false")
    monkeypatch.setenv("NEO4J_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_disabled_clients_return_none_and_healthchecks_are_disabled():
    assert get_mongo_db() is None
    assert get_cassandra_session() is None
    assert get_neo4j_driver() is None

    for payload in (mongo_healthcheck(), cassandra_healthcheck(), neo4j_healthcheck()):
        assert payload["status"] == "disabled"
        assert payload["enabled"] is False
        assert payload["connected"] is False
        assert payload["error"] is None


def test_datastores_health_endpoint_reports_postgres_and_disabled_nosql(monkeypatch: pytest.MonkeyPatch):
    import app.main as main_module

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def fake_get_engine(database_url: str | None = None):
        return engine

    monkeypatch.setattr(db_module, "get_engine", fake_get_engine)
    db_module.init_db()
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_module._SessionLocal = session_local

    with TestClient(main_module.app) as client:
        response = client.get("/health/datastores")

    assert response.status_code == 200
    payload = response.json()
    assert payload["postgres"]["status"] == "ok"
    assert payload["postgres"]["connected"] is True

    for store in ("redis", "mongo", "cassandra", "neo4j"):
        assert payload[store]["status"] == "disabled"
        assert payload[store]["enabled"] is False
        assert payload[store]["connected"] is False
        assert payload[store]["error"] is None

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_redis_health_is_active_for_distributed_locks_when_cache_is_off(monkeypatch: pytest.MonkeyPatch):
    import app.api.health as health_module

    class FakeRedis:
        def ping(self):
            return True

    monkeypatch.setenv("DISTRIBUTED_LOCK_ENABLED", "true")
    monkeypatch.setattr("redis.Redis.from_url", lambda *args, **kwargs: FakeRedis())
    get_settings.cache_clear()

    payload = health_module._redis_healthcheck()

    assert payload["status"] == "ok"
    assert payload["enabled"] is True
    assert payload["connected"] is True
    assert payload["cache_enabled"] is False
    assert payload["distributed_locks_enabled"] is True


def test_import_app_main_succeeds_when_optional_drivers_are_missing():
    script = r"""
import builtins

blocked = ("pymongo", "cassandra", "neo4j")
original_import = builtins.__import__

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name in blocked or name.startswith(tuple(prefix + "." for prefix in blocked)):
        raise ImportError(f"blocked optional driver import: {name}")
    return original_import(name, globals, locals, fromlist, level)

builtins.__import__ = guarded_import
import app.main
print("import ok")
"""
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "import ok" in result.stdout
