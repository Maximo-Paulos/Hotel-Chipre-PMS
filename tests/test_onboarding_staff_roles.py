from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.invitation import StaffInvitation
from app.models.user import User
from app.services.security import hash_password


def test_co_owner_cannot_create_an_owner_invitation_from_onboarding():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    owner = User(email="primary@example.test", password_hash=hash_password("test-password"), role="owner")
    co_owner = User(email="co-owner@example.test", password_hash=hash_password("test-password"), role="co_owner")
    db.add_all([owner, co_owner, HotelConfiguration(id=91, hotel_name="Hotel de prueba", owner_email=owner.email)])
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=91, user_id=owner.id, role="owner", status="active", is_primary_owner=True),
            HotelMembership(hotel_id=91, user_id=co_owner.id, role="co_owner", status="active"),
        ]
    )
    db.commit()
    context = AuthContext(
        hotel_id=91,
        user_id=co_owner.id,
        user_email=co_owner.email,
        user_role="co_owner",
        is_verified=True,
        permissions=set(),
    )

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_auth_context] = lambda: context
    client = TestClient(app)
    try:
        response = client.post(
            "/api/onboarding/staff",
            json={"staff": [{"name": "Laura", "role": "Owner", "email": "laura@example.test"}]},
        )

        assert response.status_code == 400, response.text
        assert db.query(StaffInvitation).filter_by(hotel_id=91, email="laura@example.test").count() == 0
        assert db.query(User).filter_by(email="laura@example.test").count() == 0
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_onboarding_invitation_reports_mocked_email_delivery(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    owner = User(email="owner-delivery@example.test", password_hash=hash_password("test-password"), role="owner")
    db.add_all([owner, HotelConfiguration(id=92, hotel_name="Hotel de prueba", owner_email=owner.email)])
    db.flush()
    db.add(HotelMembership(hotel_id=92, user_id=owner.id, role="owner", status="active", is_primary_owner=True))
    db.commit()
    context = AuthContext(
        hotel_id=92,
        user_id=owner.id,
        user_email=owner.email,
        user_role="owner",
        is_verified=True,
        permissions=set(),
    )
    sent: list[tuple[str, str, str]] = []

    class MockMailer:
        configured = True

        def send(self, email: str, subject: str, body: str) -> bool:
            sent.append((email, subject, body))
            return True

    monkeypatch.setattr("app.api.onboarding.mailer", MockMailer())
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_auth_context] = lambda: context
    client = TestClient(app)
    try:
        response = client.post(
            "/api/onboarding/staff",
            json={"staff": [{"name": "Rosa", "role": "Limpieza", "email": "rosa@example.test"}]},
        )

        assert response.status_code == 200, response.text
        deliveries = response.json()["staff_invitations"]
        assert deliveries[0]["email_delivery"] == "sent"
        assert deliveries[0]["role"] == "housekeeping"
        assert sent and sent[0][0] == "rosa@example.test"
        assert "con el rol Limpieza" in sent[0][2]
        assert "/login" in sent[0][2]
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
