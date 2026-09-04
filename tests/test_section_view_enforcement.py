"""API regression coverage for section visibility permissions."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.models.permission import HotelPermissionOverride
from app.services.permission_service import (
    PERMISSION_LAUNDRY_PRICE_MANAGE,
    seed_default_permissions,
)


@pytest.fixture
def section_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)
    db = session_factory()
    db.add(HotelConfiguration(id=1, hotel_name="Section Hotel", subscription_active=True))
    db.flush()
    seed_default_permissions(db)
    db.commit()

    def override_db():
        yield db

    def override_auth():
        return AuthContext(
            hotel_id=1,
            user_id=10,
            user_email="owner@example.test",
            user_role="owner",
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_db] = override_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    try:
        yield TestClient(fastapi_app), db
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


@pytest.mark.parametrize(
    ("permission_code", "path", "params"),
    (
        ("analytics:view", "/api/analytics/home", {}),
        ("analytics:advanced:view", "/api/analytics/rooms", {}),
        ("analytics:ai:view", "/api/analytics/insights/status", {}),
        (
            "occupancy:view",
            "/api/reservations/occupancy-grid",
            {"date_from": date.today().isoformat(), "date_to": date.today().isoformat()},
        ),
        ("waitlist:view", "/api/waitlist/", {}),
        ("cash:view", "/api/cash-register/sessions", {}),
        ("operations:audit:view", "/api/operations/audit", {}),
        ("company:view", "/api/companies", {}),
        ("settings:users:view", "/api/users/", {}),
        ("settings:integrations:view", "/api/integrations", {}),
        ("settings:subscription:view", "/api/subscription/plans", {}),
        ("settings:security:view", "/api/settings/security/overview", {}),
        ("settings:notifications:view", "/api/notifications/daily-report-schedule", {}),
        ("settings:assistant:view", "/api/gemma/chat/history", {}),
        ("settings:tests:view", "/api/payment-link-tests", {}),
    ),
)
def test_revoking_section_view_permission_blocks_read_endpoint(section_client, permission_code, path, params):
    client, db = section_client
    db.add(
        HotelPermissionOverride(
            hotel_id=1,
            role="owner",
            permission_code=permission_code,
            allowed=False,
        )
    )
    db.commit()

    response = client.get(path, params=params)

    assert response.status_code == 403, response.text


def test_revoking_laundry_price_permission_blocks_price_write(section_client):
    client, db = section_client
    db.add(
        HotelPermissionOverride(
            hotel_id=1,
            role="owner",
            permission_code=PERMISSION_LAUNDRY_PRICE_MANAGE,
            allowed=False,
        )
    )
    db.commit()

    response = client.post(
        "/api/laundry/vendors/1/prices",
        json={"linen_item_id": 1, "unit_price": "100.00"},
    )

    assert response.status_code == 403, response.text
