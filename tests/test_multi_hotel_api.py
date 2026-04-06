# -*- coding: utf-8 -*-
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import app as fastapi_app
from app.database import Base
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.subscription import SubscriptionPlan, HotelSubscription
from app.models.user import User
from app.models.room import RoomCategory, Room
from app.models.guest import Guest
from app.models.reservation import Reservation, ReservationStatusEnum
from app.services.security import hash_password


@pytest.fixture
def client_with_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    import app.models  # ensure all tables registered
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # seed plans
    plan = SubscriptionPlan(code="limit1", name="Plan 1", room_limit=1, price_month=0)
    plan2 = SubscriptionPlan(code="starter", name="Starter", room_limit=20, price_month=0)
    db.add_all([plan, plan2])
    db.flush()

    user = User(email="owner@test.com", password_hash=hash_password("pass"), role="owner", is_verified=True)
    db.add(user)
    db.flush()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    ctx_holder = {"hotel_id": 1, "user_id": user.id, "user_email": user.email}

    def override_get_auth_context():
        return AuthContext(hotel_id=ctx_holder["hotel_id"], user_id=ctx_holder["user_id"], user_email=ctx_holder["user_email"], permissions=set())

    fastapi_app.dependency_overrides[get_db_override_target()] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_get_auth_context

    client = TestClient(fastapi_app)
    yield client, db, ctx_holder

    fastapi_app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def get_db_override_target():
    from app.database import get_db
    return get_db


def create_hotel_with_membership(db, hotel_id, user_id, plan_code="starter", room_limit=None):
    config = HotelConfiguration(id=hotel_id, owner_email=f"owner{hotel_id}@test.com", subscription_active=True)
    db.add(config)
    db.flush()
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == plan_code).first()
    sub = HotelSubscription(hotel_id=hotel_id, plan_id=plan.id, status="active", room_limit_override=room_limit)
    db.add(sub)
    db.add(HotelMembership(hotel_id=hotel_id, user_id=user_id, role="owner", status="active"))
    db.flush()
    return config


def test_rooms_list_isolated_by_hotel(client_with_db):
    client, db, ctx = client_with_db
    create_hotel_with_membership(db, 1, ctx["user_id"])
    create_hotel_with_membership(db, 2, ctx["user_id"])

    cat1 = RoomCategory(name="Cat1", code="C1", base_price_per_night=100, max_occupancy=2, hotel_id=1)
    cat2 = RoomCategory(name="Cat2", code="C2", base_price_per_night=100, max_occupancy=2, hotel_id=2)
    db.add_all([cat1, cat2])
    db.flush()
    db.add(Room(room_number="101", floor=1, category_id=cat1.id, hotel_id=1))
    db.add(Room(room_number="201", floor=2, category_id=cat2.id, hotel_id=2))
    db.commit()

    ctx["hotel_id"] = 1
    r1 = client.get("/api/rooms/")
    assert r1.status_code == 200
    assert len(r1.json()) == 1
    assert r1.json()[0]["room_number"] == "101"

    ctx["hotel_id"] = 2
    r2 = client.get("/api/rooms/")
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.json()[0]["room_number"] == "201"


def test_reservations_list_isolated_by_hotel(client_with_db):
    client, db, ctx = client_with_db
    create_hotel_with_membership(db, 1, ctx["user_id"])
    create_hotel_with_membership(db, 2, ctx["user_id"])
    cat1 = RoomCategory(name="Cat1", code="C1", base_price_per_night=100, max_occupancy=2, hotel_id=1)
    cat2 = RoomCategory(name="Cat2", code="C2", base_price_per_night=100, max_occupancy=2, hotel_id=2)
    db.add_all([cat1, cat2]); db.flush()
    room1 = Room(room_number="101", floor=1, category_id=cat1.id, hotel_id=1)
    room2 = Room(room_number="201", floor=2, category_id=cat2.id, hotel_id=2)
    db.add_all([room1, room2]); db.flush()
    guest = Guest(first_name="A", last_name="B", hotel_id=1)
    guest2 = Guest(first_name="C", last_name="D", hotel_id=2)
    db.add_all([guest, guest2]); db.flush()
    from datetime import date
    db.add(Reservation(confirmation_code="R1", hotel_id=1, guest_id=guest.id, category_id=cat1.id, room_id=room1.id, check_in_date=date(2026, 1, 1), check_out_date=date(2026, 1, 2), total_amount=10, status=ReservationStatusEnum.PENDING))
    db.add(Reservation(confirmation_code="R2", hotel_id=2, guest_id=guest2.id, category_id=cat2.id, room_id=room2.id, check_in_date=date(2026, 1, 1), check_out_date=date(2026, 1, 2), total_amount=10, status=ReservationStatusEnum.PENDING))
    db.commit()

    ctx["hotel_id"] = 1
    r1 = client.get("/api/reservations/")
    assert r1.status_code == 200
    codes1 = [r["confirmation_code"] for r in r1.json()]
    assert codes1 == ["R1"]

    ctx["hotel_id"] = 2
    r2 = client.get("/api/reservations/")
    codes2 = [r["confirmation_code"] for r in r2.json()]
    assert codes2 == ["R2"]


def test_room_cap_enforced(client_with_db):
    client, db, ctx = client_with_db
    create_hotel_with_membership(db, 1, ctx["user_id"], plan_code="limit1", room_limit=1)
    cat1 = RoomCategory(name="Cat1", code="C1", base_price_per_night=100, max_occupancy=2, hotel_id=1)
    db.add(cat1); db.flush()

    # first room ok
    resp1 = client.post("/api/rooms/", json={"room_number": "101", "floor": 1, "category_id": cat1.id, "status": "available", "is_active": True})
    assert resp1.status_code == 201

    # second room should fail due to cap
    resp2 = client.post("/api/rooms/", json={"room_number": "102", "floor": 1, "category_id": cat1.id, "status": "available", "is_active": True})
    assert resp2.status_code == 402
    assert "límite" in resp2.json()["detail"].lower()


def test_reset_endpoint_allows_testing_env(client_with_db, monkeypatch):
    client, db, ctx = client_with_db
    # populate some data
    create_hotel_with_membership(db, 1, ctx["user_id"])
    db.add(RoomCategory(name="Cat1", code="C1", base_price_per_night=100, max_occupancy=2, hotel_id=1))
    db.commit()

    monkeypatch.setenv("TESTING", "1")
    r = client.post("/api/reset")
    assert r.status_code == 200
    assert r.json()["status"] in {"reset", "reset_empty"}
