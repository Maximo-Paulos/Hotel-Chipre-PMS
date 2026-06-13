from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.security_audit_log import SecurityAuditLog
from app.models.hotel_config import HotelConfiguration
from app.services.permission_service import (
    PERMISSION_GUEST_EDIT,
    PERMISSION_RESERVATION_CREATE,
)


def _override_auth(hotel_id: int, role: str, user_id: int = 10):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=user_id,
            user_email=f"{role}@test.com",
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    return dependency


def _client_with_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add_all(
        [
            HotelConfiguration(id=1, subscription_active=True),
            HotelConfiguration(id=2, subscription_active=True),
        ]
    )
    db.flush()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    from app.database import get_db

    fastapi_app.dependency_overrides[get_db] = override_get_db
    client = TestClient(fastapi_app)
    return client, db, engine


def test_permissions_matrix_available_to_authenticated_hotel_member():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")
    try:
        response = client.get("/api/permissions/matrix")
        assert response.status_code == 200
        assert response.json()["matrix"]["manager"][PERMISSION_RESERVATION_CREATE]["allowed"] is True
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_permission_override_allows_receptionist_guest_edit():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=99)
    try:
        response = client.put(
            "/api/permissions/override",
            json={"role": "receptionist", "permission_code": PERMISSION_GUEST_EDIT, "allowed": True},
        )
        assert response.status_code == 200
        assert response.json()["allowed"] is True

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")
        matrix = client.get("/api/permissions/matrix")
        assert matrix.json()["matrix"]["receptionist"][PERMISSION_GUEST_EDIT]["allowed"] is True
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_permission_denied_is_audited():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "housekeeping", user_id=42)
    try:
        response = client.post(
            "/api/reservations/",
            json={
                "guest_id": 1,
                "category_id": 1,
                "check_in_date": "2026-07-01",
                "check_out_date": "2026-07-03",
                "num_adults": 1,
            },
        )
        assert response.status_code == 403
        audit = db.query(SecurityAuditLog).filter(SecurityAuditLog.action == "permission.denied").one()
        assert audit.hotel_id == 1
        assert audit.user_id == 42
        assert PERMISSION_RESERVATION_CREATE in (audit.details or "")
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_override_in_hotel_a_does_not_affect_hotel_b():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
    try:
        response = client.put(
            "/api/permissions/override",
            json={"role": "receptionist", "permission_code": PERMISSION_GUEST_EDIT, "allowed": True},
        )
        assert response.status_code == 200

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")
        hotel_a = client.get("/api/permissions/matrix")
        assert hotel_a.json()["matrix"]["receptionist"][PERMISSION_GUEST_EDIT]["allowed"] is True

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(2, "receptionist")
        hotel_b = client.get("/api/permissions/matrix")
        assert hotel_b.json()["matrix"]["receptionist"][PERMISSION_GUEST_EDIT]["allowed"] is False
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()
