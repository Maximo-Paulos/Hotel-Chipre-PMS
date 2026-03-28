from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import app.database as db_module
import app.main as main_module
from app.database import Base, get_db


@pytest.fixture(scope="function")
def db_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    db_dir = tmp_path_factory.mktemp("smoke-db")
    return f"sqlite:///{(db_dir / 'smoke.sqlite').as_posix()}"


@pytest.fixture(scope="function")
def engine(db_url: str):
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def client(engine, db_url: str, monkeypatch: pytest.MonkeyPatch):
    # Route all DB access through the ephemeral SQLite engine
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
