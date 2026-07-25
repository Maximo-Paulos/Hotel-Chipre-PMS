"""Regression guard for a real bug B3.2 uncovered: POST /api/guests/ dumps
every GuestBase field (including unset ones, as None) into GuestCreatePayload,
a hand-mirrored dataclass in app/services/guest_service.py that has to be
kept in sync with GuestBase or the endpoint 500s on the very first request
after adding a field there -- as it did here for birth_place/birth_country/
marital_status/occupation until guest_service.py was updated to match."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration

HOTEL_ID = 7401


def _override_auth():
    def dependency():
        return AuthContext(
            hotel_id=HOTEL_ID,
            user_id=1,
            user_email="owner@test.com",
            user_role="owner",
            is_verified=True,
            permissions=set(),
        )

    return dependency


def test_create_guest_via_api_accepts_new_checkin_profile_fields():
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
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth()
    client = TestClient(fastapi_app)
    try:
        db.add(HotelConfiguration(id=HOTEL_ID, hotel_name="Hotel Create", subscription_active=True))
        db.flush()

        response = client.post(
            "/api/guests/",
            json={
                "first_name": "Noelia",
                "last_name": "Fernandez",
                "birth_place": "La Plata",
                "birth_country": "Argentina",
                "marital_status": "married",
                "occupation": "Docente",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["birth_place"] == "La Plata"
        assert body["occupation"] == "Docente"
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()
