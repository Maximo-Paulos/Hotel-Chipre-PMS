"""A5: GET /api/guests/ already paginated (app/api/guests.py::list_guests) --
skip/limit were live server-side the whole time, only the frontend never sent
them (frontend/src/api/guests.ts). This locks the contract the UI now relies
on: default caps at 50, skip/limit page through results, a `le=200` ceiling
keeps a runaway limit from turning into an unbounded scan, and pagination
never leaks another hotel's guests -- the exact bug class the plan calls out
for every other tenant-scoped list.
"""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration

HOTEL_A = 7501
HOTEL_B = 7502


def _auth_for(hotel_id: int):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=1,
            user_email="owner@test.com",
            user_role="owner",
            is_verified=True,
            permissions=set(),
        )

    return dependency


def _seed_guests(db, hotel_id: int, count: int, prefix: str):
    for i in range(count):
        db.add(Guest(hotel_id=hotel_id, first_name=f"{prefix}{i:03d}", last_name="Sintetico"))
    db.flush()


def test_list_guests_defaults_to_50_and_pages_through_the_rest():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = _auth_for(HOTEL_A)
    client = TestClient(fastapi_app)
    try:
        db.add(HotelConfiguration(id=HOTEL_A, hotel_name="Hotel A", subscription_active=True))
        _seed_guests(db, HOTEL_A, 70, prefix="Huesped")
        db.commit()

        default_page = client.get("/api/guests/")
        assert default_page.status_code == 200
        assert len(default_page.json()) == 50

        page1 = client.get("/api/guests/", params={"skip": 0, "limit": 20})
        page2 = client.get("/api/guests/", params={"skip": 20, "limit": 20})
        assert len(page1.json()) == 20
        assert len(page2.json()) == 20
        page1_ids = {g["id"] for g in page1.json()}
        page2_ids = {g["id"] for g in page2.json()}
        assert page1_ids.isdisjoint(page2_ids)

        last_page = client.get("/api/guests/", params={"skip": 60, "limit": 20})
        assert len(last_page.json()) == 10

        capped = client.get("/api/guests/", params={"limit": 999})
        assert capped.status_code == 422
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_list_guests_pagination_stays_scoped_to_hotel_id():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    client = TestClient(fastapi_app)
    try:
        db.add(HotelConfiguration(id=HOTEL_A, hotel_name="Hotel A", subscription_active=True))
        db.add(HotelConfiguration(id=HOTEL_B, hotel_name="Hotel B", subscription_active=True))
        _seed_guests(db, HOTEL_A, 55, prefix="HotelA")
        _seed_guests(db, HOTEL_B, 5, prefix="HotelB")
        db.commit()

        fastapi_app.dependency_overrides[get_auth_context] = _auth_for(HOTEL_A)
        hotel_a_second_page = client.get("/api/guests/", params={"skip": 50, "limit": 50})
        assert hotel_a_second_page.status_code == 200
        names = {g["first_name"] for g in hotel_a_second_page.json()}
        assert names.issubset({f"HotelA{i:03d}" for i in range(55)})
        assert not any(name.startswith("HotelB") for name in names)

        fastapi_app.dependency_overrides[get_auth_context] = _auth_for(HOTEL_B)
        hotel_b_page = client.get("/api/guests/", params={"skip": 0, "limit": 50})
        assert hotel_b_page.status_code == 200
        assert len(hotel_b_page.json()) == 5
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_guest_search_is_partial_ranked_and_searches_phone_without_cross_tenant_leak():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    client = TestClient(fastapi_app)
    try:
        db.add(HotelConfiguration(id=HOTEL_A, hotel_name="Hotel A", subscription_active=True))
        db.add(HotelConfiguration(id=HOTEL_B, hotel_name="Hotel B", subscription_active=True))
        exact = Guest(
            hotel_id=HOTEL_A,
            first_name="5551234",
            last_name="Exacto",
            phone="+549115551234",
        )
        partial = Guest(
            hotel_id=HOTEL_A,
            first_name="Marina",
            last_name="5551234sson",
            phone="+549110000000",
        )
        other_hotel = Guest(
            hotel_id=HOTEL_B,
            first_name="Hotel B",
            last_name="5551234",
            phone="+549115551234",
        )
        db.add_all([exact, partial, other_hotel])
        db.commit()

        fastapi_app.dependency_overrides[get_auth_context] = _auth_for(HOTEL_A)
        response = client.get("/api/guests/", params={"search": "5551234", "limit": 1})
        assert response.status_code == 200
        assert [guest["id"] for guest in response.json()] == [exact.id]

        response = client.get("/api/guests/", params={"search": "115551234", "limit": 20})
        assert response.status_code == 200
        ids = [guest["id"] for guest in response.json()]
        assert ids == [exact.id]
        assert other_hotel.id not in ids

        search_response = client.get(
            "/api/guests/search",
            params={"q": "5551234", "skip": 1, "limit": 1},
        )
        assert search_response.status_code == 200
        assert [guest["id"] for guest in search_response.json()] == [partial.id]

        assert client.get("/api/guests/search", params={"q": "5551234", "limit": -1}).status_code == 422
        assert client.get("/api/guests/search", params={"q": "5551234", "limit": 201}).status_code == 422
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()
