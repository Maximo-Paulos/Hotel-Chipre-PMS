from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.fx_rates as fx_rates_module
import app.database as db_module
import app.main as main_module
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.hotel_config import HotelConfiguration
from app.models.fx_rate_snapshot import FxRateSnapshot
from app.models.user import User


@pytest.fixture
def fx_client(monkeypatch: pytest.MonkeyPatch):
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

    async def fake_snapshot():
        return {
            "oficial": {"moneda": "USD", "compra": 900.0, "venta": 920.0},
            "blue": {"moneda": "USD", "compra": 1000.0, "venta": 1020.0},
        }

    monkeypatch.setattr(db_module, "get_engine", fake_get_engine)
    monkeypatch.setattr(fx_rates_module, "get_all_rates_snapshot", fake_snapshot)
    db_module.init_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    auth_state = {"hotel_id": 1, "user_id": 21, "role": "manager"}

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_auth_context():
        return AuthContext(
            hotel_id=auth_state["hotel_id"],
            user_id=auth_state["user_id"],
            user_email="manager-fx@example.com",
            user_role=auth_state["role"],
            is_verified=True,
            permissions=set(),
        )

    main_module.app.dependency_overrides[get_db] = override_get_db
    main_module.app.dependency_overrides[get_auth_context] = override_auth_context

    with SessionLocal() as db:
        db.add_all(
            [
                HotelConfiguration(id=1, owner_email="owner1@example.com", subscription_active=True),
                HotelConfiguration(id=2, owner_email="owner2@example.com", subscription_active=True),
                User(id=21, email="manager-fx@example.com", password_hash="test", is_active=True, is_verified=True),
            ]
        )
        db.commit()

    with TestClient(main_module.app) as client:
        yield client, SessionLocal, auth_state

    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_create_fx_snapshot(fx_client):
    client, SessionLocal, _ = fx_client

    response = client.post("/fx/snapshot")

    assert response.status_code == 201, response.text
    assert response.json()["stored"] == 2
    with SessionLocal() as db:
        rows = db.query(FxRateSnapshot).filter(FxRateSnapshot.hotel_id == 1).all()
        assert {row.rate_type for row in rows} == {"oficial", "blue"}


def test_get_rate_snapshot_by_date(fx_client):
    client, _, _ = fx_client
    create = client.post("/fx/snapshot")
    assert create.status_code == 201, create.text

    all_snapshots = client.get("/fx/snapshots", params={"rate_type": "oficial"})
    assert all_snapshots.status_code == 200, all_snapshots.text
    fetched_date = datetime.fromisoformat(all_snapshots.json()[0]["fetched_at"]).date().isoformat()

    response = client.get(
        "/fx/snapshots",
        params={"from": fetched_date, "to": fetched_date, "rate_type": "oficial"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["rate_type"] == "oficial"
    assert payload[0]["venta"] == 920.0


def test_fx_snapshots_are_hotel_scoped(fx_client):
    client, SessionLocal, auth_state = fx_client
    create = client.post("/fx/snapshot")
    assert create.status_code == 201, create.text

    auth_state["hotel_id"] = 2
    response = client.get("/fx/snapshots")

    assert response.status_code == 200, response.text
    assert response.json() == []

    with SessionLocal() as db:
        db.add(
            FxRateSnapshot(
                hotel_id=None,
                rate_type="oficial",
                moneda="USD",
                compra=910.0,
                venta=930.0,
                source="dolarapi.com",
            )
        )
        db.commit()

    platform_response = client.get("/fx/snapshots", params={"rate_type": "oficial"})
    assert platform_response.status_code == 200, platform_response.text
    assert [row["hotel_id"] for row in platform_response.json()] == [None]
