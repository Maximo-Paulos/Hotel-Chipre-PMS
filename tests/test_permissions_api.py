import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.security_audit_log import SecurityAuditLog
from app.models.hotel_config import HotelConfiguration
from app.models.permission import HotelPermissionOverride
from app.services.permission_service import (
    _CANONICAL_DEFINITIONS,
    LEGACY_PERMISSION_ALIASES,
    PERMISSION_APIKEY_MANAGE,
    PERMISSION_GUEST_CREATE,
    PERMISSION_GUEST_EDIT,
    PERMISSION_HOTEL_PROPERTY_MANAGE,
    PERMISSION_HOTEL_SECURITY_MANAGE,
    PERMISSION_OCCUPANCY_VIEW,
    PERMISSION_RESERVATION_CREATE,
    PERMISSION_PERMISSION_MANAGE,
    PERMISSION_ROOM_STATUS_UPDATE,
    PERMISSION_STOCK_ADJUST,
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


def test_permissions_matrix_available_to_permission_manager_only():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
    try:
        response = client.get("/api/permissions/matrix")
        assert response.status_code == 200
        assert response.json()["matrix"]["manager"][PERMISSION_RESERVATION_CREATE]["allowed"] is True

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")
        assert client.get("/api/permissions/matrix").status_code == 403

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "housekeeping")
        assert client.get("/api/permissions/matrix").status_code == 403
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_permissions_matrix_exposes_only_canonical_rows_with_ui_metadata():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
    try:
        response = client.get("/api/permissions/matrix")

        assert response.status_code == 200
        matrix = response.json()["matrix"]
        canonical_codes = set(_CANONICAL_DEFINITIONS)
        legacy_codes = set(LEGACY_PERMISSION_ALIASES)

        assert len(canonical_codes) == 68
        for cells in matrix.values():
            assert len(cells) == len(canonical_codes)
            assert set(cells) == canonical_codes
            assert set(cells).isdisjoint(legacy_codes)
            for code, cell in cells.items():
                assert cell["module"] == _CANONICAL_DEFINITIONS[code][0]
                assert cell["help_es"] == _CANONICAL_DEFINITIONS[code][2]
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


@pytest.mark.parametrize(
    ("permission_code", "path", "params"),
    [
        ("analytics:view", "/api/analytics/starter-summary", None),
        ("analytics:advanced:view", "/api/analytics/rooms", None),
        ("analytics:ai:view", "/api/analytics/ai-config", None),
        ("occupancy:view", "/api/reservations/occupancy-grid", {"date_from": "2027-01-01", "date_to": "2027-01-02"}),
        ("waitlist:view", "/api/waitlist/", None),
        ("cash:view", "/api/cash-register/sessions", None),
        ("company:view", "/api/companies", None),
        ("company:view", "/api/company-documents/company/1", None),
        ("settings:users:view", "/api/users/", None),
        ("settings:integrations:view", "/api/integrations", None),
        ("settings:subscription:view", "/api/subscription/status", None),
        ("settings:security:view", "/api/settings/security/overview", None),
        ("settings:notifications:view", "/api/notifications/daily-report-schedule", None),
        ("settings:assistant:view", "/api/gemma/chat/history", None),
        ("settings:tests:view", "/api/payment-link-tests", None),
    ],
)
def test_revoking_each_section_view_permission_blocks_its_read_endpoint(
    permission_code, path, params
):
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
    try:
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
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_permission_catalog_exposes_owner_only_normal_metadata_and_help_text():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
    try:
        response = client.get("/api/permissions/catalog")
        assert response.status_code == 200
        catalog = {row["code"]: row for row in response.json()["permissions"]}
        assert catalog
        assert all(isinstance(row["help_es"], str) and row["help_es"].strip() for row in catalog.values())

        for code in (
            PERMISSION_PERMISSION_MANAGE,
            PERMISSION_HOTEL_PROPERTY_MANAGE,
            PERMISSION_HOTEL_SECURITY_MANAGE,
            PERMISSION_APIKEY_MANAGE,
        ):
            assert catalog[code]["critical"] is True
            assert catalog[code]["step_up_required"] is True
            assert catalog[code]["delegable"] is False

        for code in (PERMISSION_GUEST_CREATE, PERMISSION_RESERVATION_CREATE, PERMISSION_ROOM_STATUS_UPDATE):
            assert catalog[code]["critical"] is False
            assert catalog[code]["step_up_required"] is False
            assert catalog[code]["delegable"] is True
            assert catalog[code]["help_es"]

        matrix = client.get("/api/permissions/matrix")
        assert matrix.status_code == 200
        assert matrix.json()["matrix"]["manager"][PERMISSION_RESERVATION_CREATE]["help_es"]

        profiles = client.get("/api/permissions/role-overrides")
        assert profiles.status_code == 200
        assert profiles.json()["matrix"]["manager"][PERMISSION_RESERVATION_CREATE]["help_es"]
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_effective_permissions_returns_only_current_role_capabilities():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")
    try:
        response = client.get("/api/permissions/effective")

        assert response.status_code == 200
        assert response.json()["hotel_id"] == 1
        assert response.json()["role"] == "receptionist"
        assert PERMISSION_GUEST_CREATE in response.json()["permissions"]
        assert PERMISSION_GUEST_EDIT in response.json()["permissions"]
        assert PERMISSION_STOCK_ADJUST not in response.json()["permissions"]
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_permission_override_can_deny_receptionist_guest_edit():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=99)
    try:
        response = client.put(
            "/api/permissions/override",
            json={"role": "receptionist", "permission_code": PERMISSION_GUEST_EDIT, "allowed": False},
        )
        assert response.status_code == 200
        assert response.json()["allowed"] is False
        assert response.json()["version"] == 1

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")
        effective = client.get("/api/permissions/effective")
        assert effective.status_code == 200
        assert PERMISSION_GUEST_EDIT not in effective.json()["permissions"]
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_stale_expected_version_is_rejected_for_role_override():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=99)
    try:
        created = client.put(
            "/api/permissions/override",
            json={"role": "receptionist", "permission_code": PERMISSION_GUEST_EDIT, "allowed": False},
        )
        assert created.status_code == 200
        assert created.json()["version"] == 1

        first_update = client.put(
            "/api/permissions/override",
            json={
                "role": "receptionist",
                "permission_code": PERMISSION_GUEST_EDIT,
                "allowed": True,
                "expected_version": 1,
            },
        )
        assert first_update.status_code == 200
        assert first_update.json()["version"] == 2

        stale_update = client.put(
            "/api/permissions/override",
            json={
                "role": "receptionist",
                "permission_code": PERMISSION_GUEST_EDIT,
                "allowed": False,
                "expected_version": 1,
            },
        )
        assert stale_update.status_code == 409
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


def test_permission_override_can_grant_permission_missing_from_role_default():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=99)
    try:
        response = client.put(
            "/api/permissions/override",
            json={
                "role": "housekeeping",
                "permission_code": PERMISSION_GUEST_EDIT,
                "allowed": True,
            },
        )

        assert response.status_code == 200, response.text
        assert response.json()["allowed"] is True
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_owner_can_grant_housekeeping_occupancy_planner():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=99)
    try:
        grant = client.put(
            "/api/permissions/override",
            json={
                "role": "housekeeping",
                "permission_code": PERMISSION_OCCUPANCY_VIEW,
                "allowed": True,
            },
        )

        assert grant.status_code == 200, grant.text
        assert grant.json()["allowed"] is True

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "housekeeping")
        effective = client.get("/api/permissions/effective")
        assert effective.status_code == 200, effective.text
        assert PERMISSION_OCCUPANCY_VIEW in effective.json()["permissions"]

        occupancy = client.get(
            "/api/reservations/occupancy-grid",
            params={"date_from": "2027-01-01", "date_to": "2027-01-02"},
        )
        assert occupancy.status_code == 200, occupancy.text
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
            json={"role": "receptionist", "permission_code": PERMISSION_GUEST_EDIT, "allowed": False},
        )
        assert response.status_code == 200

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")
        hotel_a = client.get("/api/permissions/effective")
        assert hotel_a.status_code == 200
        assert PERMISSION_GUEST_EDIT not in hotel_a.json()["permissions"]

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(2, "receptionist")
        hotel_b = client.get("/api/permissions/effective")
        assert hotel_b.status_code == 200
        assert PERMISSION_GUEST_EDIT in hotel_b.json()["permissions"]
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_stock_operator_cannot_adjust_without_explicit_adjust_permission():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")
    try:
        item_response = client.post(
            "/api/stock/items",
            json={"name": "Toallas", "unit": "unidad", "min_quantity": 2},
        )
        assert item_response.status_code == 201
        item_id = item_response.json()["id"]

        denied = client.post(
            "/api/stock/movements",
            json={"item_id": item_id, "movement_type": "adjustment", "quantity": "1", "reason": "Conteo"},
        )
        assert denied.status_code == 403
        assert "stock:adjust" in (db.query(SecurityAuditLog).filter(SecurityAuditLog.action == "permission.denied").one().details or "")

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=11)
        allowed = client.post(
            "/api/stock/movements",
            json={"item_id": item_id, "movement_type": "adjustment", "quantity": "1", "reason": "Conteo autorizado"},
        )
        assert allowed.status_code == 201
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_stock_operator_cannot_adjust_downward_without_explicit_adjust_permission():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=11)
    try:
        item_response = client.post(
            "/api/stock/items",
            json={"name": "Sabanas", "unit": "unidad", "min_quantity": 2},
        )
        assert item_response.status_code == 201
        item_id = item_response.json()["id"]
        seed = client.post(
            "/api/stock/movements",
            json={"item_id": item_id, "movement_type": "in", "quantity": "10", "reason": "Stock inicial"},
        )
        assert seed.status_code == 201

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")
        denied = client.post(
            "/api/stock/movements",
            json={"item_id": item_id, "movement_type": "adjustment_out", "quantity": "1", "reason": "Conteo"},
        )
        assert denied.status_code == 403
        assert "stock:adjust" in (
            db.query(SecurityAuditLog)
            .filter(SecurityAuditLog.action == "permission.denied")
            .order_by(SecurityAuditLog.id.desc())
            .first()
            .details
            or ""
        )

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=11)
        allowed = client.post(
            "/api/stock/movements",
            json={"item_id": item_id, "movement_type": "adjustment_out", "quantity": "1", "reason": "Conteo autorizado"},
        )
        assert allowed.status_code == 201
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_stock_history_api_is_hotel_scoped_and_limited():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=11)
    try:
        item = client.post("/api/stock/items", json={"name": "Amenities", "unit": "unidad"})
        assert item.status_code == 201
        item_id = item.json()["id"]

        first = client.post(
            "/api/stock/movements",
            json={"item_id": item_id, "movement_type": "in", "quantity": "5", "reason": "Ingreso"},
        )
        latest = client.post(
            "/api/stock/movements",
            json={"item_id": item_id, "movement_type": "out", "quantity": "2", "reason": "Consumo"},
        )
        assert first.status_code == latest.status_code == 201

        limited = client.get(f"/api/stock/movements?item_id={item_id}&limit=1")
        assert limited.status_code == 200
        assert [row["id"] for row in limited.json()] == [latest.json()["id"]]

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(2, "owner", user_id=12)
        assert client.get(f"/api/stock/movements?item_id={item_id}").json() == []
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()
