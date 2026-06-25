import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as db_module
import app.main as main_module
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.hotel_config import HotelConfiguration
from app.models.room import RoomCategory, RoomStatusEnum


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch):
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

    monkeypatch.setattr(db_module, "get_engine", lambda database_url=None: engine)
    db_module.init_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_auth_context():
        return AuthContext(
            hotel_id=1,
            user_id=1,
            user_email="owner@test.com",
            user_role="owner",
            is_verified=True,
            permissions=set(),
        )

    main_module.app.dependency_overrides[get_db] = override_get_db
    main_module.app.dependency_overrides[get_auth_context] = override_auth_context

    with TestClient(main_module.app) as client:
        with SessionLocal() as db:
            db.add(HotelConfiguration(id=1, owner_email="owner@test.com", subscription_active=True))
            db.add(
                RoomCategory(
                    hotel_id=1,
                    name="Schema Standard",
                    code="SCHEMA_STD",
                    base_price_per_night=100.0,
                    max_occupancy=2,
                )
            )
            db.commit()
        yield client, SessionLocal

    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_room_create_and_patch_exposes_allocation_fields(api_client):
    client, SessionLocal = api_client
    with SessionLocal() as db:
        category_id = db.query(RoomCategory.id).filter(RoomCategory.hotel_id == 1).scalar()

    create = client.post(
        "/api/rooms/",
        json={
            "room_number": "701",
            "floor": 7,
            "category_id": category_id,
            "status": RoomStatusEnum.AVAILABLE.value,
            "score": 8,
            "is_accessible": True,
            "description": "Corner accessible room",
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["score"] == 8
    assert body["is_accessible"] is True
    assert body["description"] == "Corner accessible room"

    patch = client.patch(f"/api/rooms/{body['id']}", json={"score": 10})
    assert patch.status_code == 200, patch.text
    assert patch.json()["score"] == 10

    invalid = client.patch(f"/api/rooms/{body['id']}", json={"score": 11})
    assert invalid.status_code == 422, invalid.text

