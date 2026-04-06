# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app as fastapi_app
from app.database import Base
import app.models  # noqa
from app.models.hotel_config import HotelConfiguration
from app.dependencies.auth import AuthContext


def get_db_override_target():
    from app.database import get_db
    return get_db


def get_auth_context_target():
    from app.dependencies.auth import get_auth_context
    return get_auth_context


@pytest.fixture
def client_with_db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db_override_target()] = override_get_db
    client = TestClient(fastapi_app)
    try:
        yield client, db
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


@pytest.fixture
def ctx(client_with_db):
    client, db = client_with_db
    cfg = HotelConfiguration(id=1)
    db.add(cfg)
    db.commit()

    def override_auth_context():
        return AuthContext(hotel_id=1, user_id=1, user_email="owner@test.com", permissions=set())

    fastapi_app.dependency_overrides[get_auth_context_target()] = override_auth_context
    try:
        yield client, db
    finally:
        fastapi_app.dependency_overrides.clear()


def test_config_defaults_include_permissions(ctx):
    client, db = ctx
    r = client.get("/api/config/")
    assert r.status_code == 200
    body = r.json()
    assert body["receptionist_view_past_days"] == 0
    assert body["receptionist_view_future_days"] == 7
    assert body["allow_revenue_manager"] is True
    assert body["allow_revenue_receptionist"] is False


def test_config_update_permissions(ctx):
    client, db = ctx
    payload = {
        "receptionist_view_past_days": 2,
        "receptionist_view_future_days": 10,
        "allow_revenue_manager": False,
        "allow_revenue_receptionist": True,
    }
    r = client.patch("/api/config/", json=payload)
    assert r.status_code == 200
    body = r.json()
    for k, v in payload.items():
        assert body[k] == v
