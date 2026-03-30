from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import app.database as db_module
import app.main as main_module
from app.database import Base, get_db


@pytest.fixture()
def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """FastAPI client backed by an isolated SQLite database."""
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


def test_seed_and_reset_blocked_by_default(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Demo endpoints must be off unless explicitly enabled."""
    monkeypatch.delenv("DEMO_MODE", raising=False)

    seed = client.post("/api/seed")
    reset = client.post("/api/reset")

    assert seed.status_code == 403
    assert reset.status_code == 403
    assert "Demo mode" in seed.json()["detail"]


def test_seed_and_reset_allowed_when_demo_enabled(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Demo utilities work once DEMO_MODE=true is set."""
    monkeypatch.setenv("DEMO_MODE", "true")

    seed = client.post("/api/seed")
    assert seed.status_code == 200
    assert seed.json()["status"] in {"seeded", "already_seeded"}

    reset = client.post("/api/reset")
    assert reset.status_code == 200
    assert reset.json()["status"] == "reset"
