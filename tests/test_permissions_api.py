import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.api import subscription as subscription_api
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.security_audit_log import SecurityAuditLog
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.permission import HotelPermissionOverride, UserPermissionOverride
from app.models.user import User
from app.models.user_mfa import UserMfaSecret
from app.models.whatsapp_crm import (
    WhatsAppChannel,
    WhatsAppChannelStatusEnum,
    WhatsAppContact,
    WhatsAppConversation,
    WhatsAppConversationStatusEnum,
    WhatsAppMessage,
    WhatsAppMessageDirectionEnum,
    WhatsAppMessageStatusEnum,
)
from app.services.action_step_up_service import (
    create_action_step_up_ticket,
    create_permission_admin_read_step_up_ticket,
    is_permission_admin_read_action,
)
from app.services.mfa_service import encrypt_totp_secret
from app.services.permission_service import (
    _CANONICAL_DEFINITIONS,
    LEGACY_PERMISSION_ALIASES,
    PERMISSION_APIKEY_MANAGE,
    PERMISSION_CASH_APPROVE_DIFFERENCE,
    PERMISSION_CASH_CUSTODY_RECEIVE,
    PERMISSION_GUEST_CREATE,
    PERMISSION_GUEST_EDIT,
    PERMISSION_HOTEL_PROPERTY_MANAGE,
    PERMISSION_HOTEL_SECURITY_MANAGE,
    PERMISSION_GUEST_READ,
    PERMISSION_OCCUPANCY_VIEW,
    PERMISSION_RESERVATION_CREATE,
    PERMISSION_RESERVATION_MANUAL_RATE,
    PERMISSION_RESERVATION_MANUAL_RATE_POLICY_MANAGE,
    PERMISSION_RESERVATION_PAID_TOTAL_ADJUST,
    PERMISSION_PERMISSION_MANAGE,
    PERMISSION_ROOM_STATUS_UPDATE,
    PERMISSION_SETTINGS_INTEGRATIONS_VIEW,
    PERMISSION_SETTINGS_FX_MANAGE,
    PERMISSION_STOCK_ADJUST,
    PERMISSION_WHATSAPP_INBOX_VIEW,
    canonical_permission_code,
    ensure_permission_matrix_seeded,
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


def _step_up_headers(path: str, *, method: str, hotel_id: int = 1, user_id: int = 10):
    """Create an RBAC-read scope or action-bound ticket for focused API tests."""
    if is_permission_admin_read_action(method, path):
        ticket = create_permission_admin_read_step_up_ticket(
            user_id=user_id,
            hotel_id=hotel_id,
            token_version=0,
        )
        return {"X-Action-Step-Up-Ticket": ticket}
    ticket = create_action_step_up_ticket(
        user_id=user_id,
        hotel_id=hotel_id,
        token_version=0,
        permission_code=PERMISSION_PERMISSION_MANAGE,
        method=method,
        path=path,
    )
    return {"X-Action-Step-Up-Ticket": ticket}


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


def _enable_whatsapp_plan_for_api_test(monkeypatch):
    from app.api import whatsapp_crm as whatsapp_crm_api

    monkeypatch.setattr(
        whatsapp_crm_api, "get_subscription_snapshot", lambda *_args: {"plan": "pro"}
    )
    monkeypatch.setattr(
        whatsapp_crm_api, "plan_has_feature", lambda *_args: True
    )


def test_permissions_matrix_available_to_permission_manager_only():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
    try:
        path = "/api/permissions/matrix"
        response = client.get(path, headers=_step_up_headers(path, method="GET"))
        assert response.status_code == 200
        assert response.json()["matrix"]["manager"][PERMISSION_RESERVATION_CREATE]["allowed"] is True

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "co_owner")
        co_owner_response = client.get(path, headers=_step_up_headers(path, method="GET"))
        assert co_owner_response.status_code == 200
        assert co_owner_response.json()["matrix"]["co_owner"][PERMISSION_PERMISSION_MANAGE]["allowed"] is True

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
        path = "/api/permissions/matrix"
        response = client.get(path, headers=_step_up_headers(path, method="GET"))

        assert response.status_code == 200
        matrix = response.json()["matrix"]
        canonical_codes = set(_CANONICAL_DEFINITIONS)
        legacy_codes = set(LEGACY_PERMISSION_ALIASES)

        # New role-only business actions are named capabilities in the catalog.
        assert len(canonical_codes) == 111
        assert {"payment:proof:view", "payment:proof:review"} <= canonical_codes
        assert {"payment:refund", "reservation:cancel_paid"} <= canonical_codes
        assert {"reservation:manual_rate_limited", "reservation:manual_rate_policy_manage"} <= canonical_codes
        assert "reservation:rate_adjust" in canonical_codes
        assert "cash:expense" in canonical_codes
        assert "payment:ota_confirm" in canonical_codes
        assert "reservation:ota_record" in canonical_codes
        assert "company:night_rate_manage" in canonical_codes
        assert {code for code in canonical_codes if code.startswith("whatsapp:")} == {
            "whatsapp:inbox:view", "whatsapp:inbox:all", "whatsapp:message:send",
            "whatsapp:note:manage", "whatsapp:conversation:assign", "whatsapp:conversation:close",
            "whatsapp:context:guest", "whatsapp:context:reservation", "whatsapp:action:quote",
            "whatsapp:action:payment", "whatsapp:settings:manage",
        }
        for cells in matrix.values():
            assert len(cells) == len(canonical_codes)
            assert set(cells) == canonical_codes
            assert set(cells).isdisjoint(legacy_codes)
            for code, cell in cells.items():
                assert cell["module"] == _CANONICAL_DEFINITIONS[code][0]
                assert cell["help_es"] == _CANONICAL_DEFINITIONS[code][2]
        for role in ("owner", "co_owner", "manager"):
            assert matrix[role]["payment:proof:review"]["allowed"] is True
        assert matrix["owner"][PERMISSION_SETTINGS_FX_MANAGE]["allowed"] is True
        assert matrix["co_owner"][PERMISSION_SETTINGS_FX_MANAGE]["allowed"] is True
        assert matrix["co_owner"][PERMISSION_SETTINGS_FX_MANAGE]["source"] == "invariant"
        assert matrix["manager"][PERMISSION_SETTINGS_FX_MANAGE]["allowed"] is False
        assert matrix["manager"]["reservation:charge"]["allowed"] is True
        assert matrix["manager"]["cash:operate"]["allowed"] is True
        assert matrix["manager"]["payment:refund"]["allowed"] is True
        assert matrix["manager"]["reservation:cancel_paid"]["allowed"] is True
        assert matrix["manager"]["cash:expense"]["allowed"] is True
        assert matrix["co_owner"]["cash:expense"]["allowed"] is True
        assert matrix["manager"]["reservation:manual_rate_limited"]["allowed"] is True
        assert matrix["co_owner"]["reservation:manual_rate_limited"]["allowed"] is True
        assert matrix["owner"]["reservation:rate_adjust"]["allowed"] is False
        assert matrix["manager"]["reservation:rate_adjust"]["allowed"] is True
        assert matrix["co_owner"]["reservation:rate_adjust"]["allowed"] is False
        assert matrix["receptionist"]["reservation:rate_adjust"]["allowed"] is False
        assert matrix["manager"]["reservation:rate_adjust"]["help_es"]
        assert matrix["owner"][PERMISSION_RESERVATION_MANUAL_RATE]["allowed"] is True
        assert matrix["co_owner"][PERMISSION_RESERVATION_MANUAL_RATE]["allowed"] is True
        assert matrix["manager"][PERMISSION_RESERVATION_MANUAL_RATE]["allowed"] is False
        assert matrix["owner"][PERMISSION_RESERVATION_MANUAL_RATE_POLICY_MANAGE]["allowed"] is True
        assert matrix["co_owner"][PERMISSION_RESERVATION_MANUAL_RATE_POLICY_MANAGE]["allowed"] is True
        assert matrix["manager"][PERMISSION_RESERVATION_MANUAL_RATE_POLICY_MANAGE]["allowed"] is False
        assert matrix["owner"][PERMISSION_RESERVATION_PAID_TOTAL_ADJUST]["allowed"] is True
        assert matrix["co_owner"][PERMISSION_RESERVATION_PAID_TOTAL_ADJUST]["allowed"] is True
        assert matrix["manager"][PERMISSION_RESERVATION_PAID_TOTAL_ADJUST]["allowed"] is False
        assert matrix["owner"][PERMISSION_APIKEY_MANAGE]["allowed"] is True
        assert matrix["co_owner"][PERMISSION_APIKEY_MANAGE]["allowed"] is True
        assert matrix["manager"][PERMISSION_APIKEY_MANAGE]["allowed"] is False
        assert matrix["owner"][PERMISSION_HOTEL_SECURITY_MANAGE]["allowed"] is True
        assert matrix["co_owner"][PERMISSION_HOTEL_SECURITY_MANAGE]["allowed"] is True
        assert matrix["manager"][PERMISSION_HOTEL_SECURITY_MANAGE]["allowed"] is False
        assert matrix["owner"][PERMISSION_HOTEL_PROPERTY_MANAGE]["allowed"] is True
        assert matrix["co_owner"][PERMISSION_HOTEL_PROPERTY_MANAGE]["allowed"] is False
        assert matrix["manager"][PERMISSION_HOTEL_PROPERTY_MANAGE]["allowed"] is False
        assert matrix["owner"]["company:night_rate_manage"]["allowed"] is True
        assert matrix["co_owner"]["company:night_rate_manage"]["allowed"] is True
        assert matrix["manager"]["company:night_rate_manage"]["allowed"] is True
        assert matrix["receptionist"]["company:night_rate_manage"]["allowed"] is False
        assert matrix["manager"]["payment:ota_confirm"]["allowed"] is True
        assert matrix["co_owner"]["payment:ota_confirm"]["allowed"] is True
        for role in ("owner", "co_owner", "manager", "receptionist"):
            assert matrix[role]["reservation:ota_record"]["allowed"] is True
        assert matrix["housekeeping"]["reservation:ota_record"]["allowed"] is False
        for role in ("receptionist", "housekeeping"):
            assert matrix[role]["payment:proof:review"]["allowed"] is False
            assert matrix[role]["payment:refund"]["allowed"] is False
            assert matrix[role]["reservation:cancel_paid"]["allowed"] is False
            assert matrix[role]["payment:ota_confirm"]["allowed"] is False
            assert matrix[role]["reservation:manual_rate_limited"]["allowed"] is False
        assert matrix["housekeeping"]["whatsapp:inbox:view"]["allowed"] is False
        assert matrix["housekeeping"]["whatsapp:note:manage"]["allowed"] is False
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
        ("settings:notifications:daily_report:view", "/api/notifications/daily-report-schedule", None),
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


def test_subscription_status_does_not_claim_active_when_source_is_unavailable(monkeypatch):
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")

    def fail_status(*_args, **_kwargs):
        raise RuntimeError("synthetic subscription store failure")

    monkeypatch.setattr(subscription_api, "_serialize_status_payload", fail_status)
    try:
        response = client.get("/api/subscription/status")
        assert response.status_code == 503
        assert "estado real" in response.json()["detail"].lower()
        assert response.json().get("status") is None
        assert response.json().get("source") is None
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_permission_catalog_exposes_administrator_and_owner_only_metadata_and_help_text():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
    try:
        catalog_path = "/api/permissions/catalog"
        read_headers = _step_up_headers(catalog_path, method="GET")
        response = client.get(catalog_path, headers=read_headers)
        assert response.status_code == 200
        catalog = {row["code"]: row for row in response.json()["permissions"]}
        assert catalog
        assert all(isinstance(row["help_es"], str) and row["help_es"].strip() for row in catalog.values())

        for code in (
            PERMISSION_PERMISSION_MANAGE,
            PERMISSION_HOTEL_PROPERTY_MANAGE,
            PERMISSION_HOTEL_SECURITY_MANAGE,
            PERMISSION_APIKEY_MANAGE,
            PERMISSION_RESERVATION_MANUAL_RATE_POLICY_MANAGE,
        ):
            assert catalog[code]["critical"] is True
            assert catalog[code]["step_up_required"] is True
            assert catalog[code]["delegable"] is False

        assert catalog[PERMISSION_PERMISSION_MANAGE]["locked"] is True
        assert catalog[PERMISSION_PERMISSION_MANAGE]["lock_reason"] == "role_scope"
        assert catalog[PERMISSION_SETTINGS_FX_MANAGE]["critical"] is True
        assert catalog[PERMISSION_SETTINGS_FX_MANAGE]["step_up_required"] is True
        assert catalog[PERMISSION_SETTINGS_FX_MANAGE]["delegable"] is False
        assert catalog[PERMISSION_SETTINGS_FX_MANAGE]["locked"] is True
        assert catalog[PERMISSION_SETTINGS_FX_MANAGE]["lock_reason"] == "role_scope"

        assert catalog["settings:users:manage"]["step_up_required"] is True
        assert catalog["settings:subscription:manage"]["step_up_required"] is True
        assert catalog["company:night_rate_manage"]["critical"] is False
        assert catalog["company:night_rate_manage"]["step_up_required"] is False
        assert catalog["company:night_rate_manage"]["delegable"] is True

        assert catalog[PERMISSION_CASH_APPROVE_DIFFERENCE]["critical"] is False
        assert catalog[PERMISSION_CASH_APPROVE_DIFFERENCE]["step_up_required"] is True
        assert catalog[PERMISSION_CASH_APPROVE_DIFFERENCE]["delegable"] is True
        assert catalog[PERMISSION_CASH_CUSTODY_RECEIVE]["critical"] is False
        assert catalog[PERMISSION_CASH_CUSTODY_RECEIVE]["step_up_required"] is True
        assert catalog[PERMISSION_CASH_CUSTODY_RECEIVE]["delegable"] is True
        assert catalog["cash:expense"]["step_up_required"] is True
        assert catalog["payment:ota_confirm"]["step_up_required"] is True

        for code in (PERMISSION_GUEST_CREATE, PERMISSION_RESERVATION_CREATE, PERMISSION_ROOM_STATUS_UPDATE):
            assert catalog[code]["critical"] is False
            assert catalog[code]["step_up_required"] is False
            assert catalog[code]["delegable"] is True
            assert catalog[code]["help_es"]

        matrix_path = "/api/permissions/matrix"
        matrix = client.get(matrix_path, headers=_step_up_headers(matrix_path, method="GET"))
        assert matrix.status_code == 200
        assert matrix.json()["matrix"]["manager"][PERMISSION_RESERVATION_CREATE]["help_es"]

        profiles_path = "/api/permissions/role-overrides"
        profiles = client.get(profiles_path, headers=_step_up_headers(profiles_path, method="GET"))
        assert profiles.status_code == 200
        assert profiles.json()["matrix"]["manager"][PERMISSION_RESERVATION_CREATE]["help_es"]
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_permission_administration_reads_require_mfa_and_share_a_read_only_ticket():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
    db.add(User(id=20, email="employee@test.com", password_hash="synthetic", is_verified=True))
    db.flush()
    db.add(HotelMembership(hotel_id=1, user_id=20, role="receptionist", status="active"))
    db.commit()
    try:
        paths = (
            "/api/permissions/catalog",
            "/api/permissions/matrix",
            "/api/permissions/role-overrides",
            "/api/permissions/visibility-windows",
            "/api/permissions/user-overrides/20",
            "/api/permissions/effective/preview?user_id=20",
        )
        assert client.get(paths[0]).status_code == 428
        headers = _step_up_headers("/api/permissions/catalog", method="GET")
        for path in paths:
            response = client.get(path, headers=headers)
            assert response.status_code == 200, f"{path}: {response.text}"

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")
        denied = client.get("/api/permissions/catalog", headers=headers)
        assert denied.status_code == 403

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        write_with_read_ticket = client.put(
            "/api/permissions/visibility-windows",
            json={"role": "manager", "past_hours": 24, "future_hours": 48},
            headers=headers,
        )
        assert write_with_read_ticket.status_code == 428
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
            headers=_step_up_headers("/api/permissions/override", method="PUT", user_id=99),
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


def test_owner_rate_adjust_is_denied_by_default_and_can_be_explicitly_granted():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=99)
    try:
        matrix_path = "/api/permissions/matrix"
        default_matrix = client.get(
            matrix_path,
            headers=_step_up_headers(matrix_path, method="GET", user_id=99),
        )
        assert default_matrix.status_code == 200, default_matrix.text
        assert default_matrix.json()["matrix"]["owner"]["reservation:rate_adjust"]["allowed"] is False
        assert default_matrix.json()["matrix"]["manager"]["reservation:rate_adjust"]["allowed"] is True

        override_path = "/api/permissions/override"
        granted = client.put(
            override_path,
            json={
                "role": "owner",
                "permission_code": "reservation:rate_adjust",
                "allowed": True,
                "expected_version": 0,
            },
            headers=_step_up_headers(override_path, method="PUT", user_id=99),
        )
        assert granted.status_code == 200, granted.text
        assert granted.json()["allowed"] is True
        assert granted.json()["source"] == "role_override"

        effective = client.get("/api/permissions/effective")
        assert effective.status_code == 200, effective.text
        assert "reservation:rate_adjust" in effective.json()["permissions"]
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_co_owner_cannot_mutate_or_reset_owner_role_profile():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "co_owner")
    try:
        headers = _step_up_headers("/api/permissions/override", method="PUT")
        blocked = client.put(
            "/api/permissions/override",
            json={"role": "owner", "permission_code": PERMISSION_GUEST_READ, "allowed": False},
            headers=headers,
        )
        assert blocked.status_code == 403

        blocked_rate_adjust = client.put(
            "/api/permissions/override",
            json={"role": "owner", "permission_code": "reservation:rate_adjust", "allowed": True},
            headers=_step_up_headers("/api/permissions/override", method="PUT"),
        )
        assert blocked_rate_adjust.status_code == 403

        blocked_critical_reset = client.delete(
            f"/api/permissions/overrides/role/owner/{PERMISSION_PERMISSION_MANAGE}",
            params={"expected_version": 1},
            headers=_step_up_headers(
                f"/api/permissions/overrides/role/owner/{PERMISSION_PERMISSION_MANAGE}",
                method="DELETE",
            ),
        )
        assert blocked_critical_reset.status_code == 403

        reset_headers = _step_up_headers("/api/permissions/role-overrides/owner", method="DELETE")
        blocked_reset = client.delete("/api/permissions/role-overrides/owner", headers=reset_headers)
        assert blocked_reset.status_code == 403

        visibility_headers = _step_up_headers("/api/permissions/visibility-windows", method="PUT")
        blocked_visibility = client.put(
            "/api/permissions/visibility-windows",
            json={"role": "owner", "past_hours": 24, "future_hours": 24},
            headers=visibility_headers,
        )
        assert blocked_visibility.status_code == 403
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_permission_override_reads_include_current_versions():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=10)
    db.add(User(id=20, email="employee@test.com", password_hash="synthetic", is_verified=True))
    db.flush()
    db.add(HotelMembership(hotel_id=1, user_id=20, role="receptionist", status="active"))
    db.commit()
    try:
        role_path = "/api/permissions/override"
        for allowed, expected_version in ((False, 0), (True, 1)):
            updated = client.put(
                role_path,
                json={
                    "role": "receptionist",
                    "permission_code": PERMISSION_GUEST_EDIT,
                    "allowed": allowed,
                    "expected_version": expected_version,
                },
                headers=_step_up_headers(role_path, method="PUT"),
            )
            assert updated.status_code == 200, updated.text

        role_profiles_path = "/api/permissions/role-overrides"
        role_profiles = client.get(
            role_profiles_path,
            headers=_step_up_headers(role_profiles_path, method="GET"),
        )
        assert role_profiles.status_code == 200, role_profiles.text
        permission_code = canonical_permission_code(PERMISSION_GUEST_EDIT)
        role_detail = role_profiles.json()["matrix"]["receptionist"][permission_code]
        assert role_detail["source"] == "role_override"
        assert role_detail["version"] == 2

        user_path = "/api/permissions/user-overrides/20"
        for allowed, expected_version in ((False, 0), (True, 1)):
            updated = client.put(
                user_path,
                json={
                    "permission_code": PERMISSION_GUEST_EDIT,
                    "allowed": allowed,
                    "expected_version": expected_version,
                },
                headers=_step_up_headers(user_path, method="PUT"),
            )
            assert updated.status_code == 200, updated.text

        read_path = "/api/permissions/user-overrides/20"
        user_overrides = client.get(
            read_path,
            headers=_step_up_headers(read_path, method="GET"),
        )
        assert user_overrides.status_code == 200, user_overrides.text
        user_detail = user_overrides.json()["details"][permission_code]
        assert user_detail["source"] == "user_override"
        assert user_detail["version"] == 2
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
            headers=_step_up_headers("/api/permissions/override", method="PUT", user_id=99),
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
            headers=_step_up_headers("/api/permissions/override", method="PUT", user_id=99),
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
            headers=_step_up_headers("/api/permissions/override", method="PUT", user_id=99),
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
            headers=_step_up_headers("/api/permissions/override", method="PUT", user_id=99),
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
            headers=_step_up_headers("/api/permissions/override", method="PUT", user_id=99),
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
            headers=_step_up_headers("/api/permissions/override", method="PUT"),
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


def _seed_permission_restore_state(db, restore_kind: str) -> str:
    ensure_permission_matrix_seeded(db)
    secret = pyotp.random_base32()
    permission_code = canonical_permission_code(PERMISSION_GUEST_EDIT)
    db.add_all(
        [
            User(
                id=10,
                email="owner@test.com",
                password_hash="unused-test-hash",
                is_active=True,
                is_verified=True,
                role="owner",
            ),
            UserMfaSecret(
                user_id=10,
                encrypted_secret=encrypt_totp_secret(secret),
                status="active",
            ),
        ]
    )
    if restore_kind == "role":
        db.add(
            HotelPermissionOverride(
                hotel_id=1,
                role="receptionist",
                permission_code=permission_code,
                allowed=False,
                version=1,
            )
        )
    else:
        db.add_all(
            [
                User(
                    id=20,
                    email="employee@test.com",
                    password_hash="unused-test-hash",
                    is_active=True,
                    is_verified=True,
                    role="owner",
                ),
                HotelMembership(
                    hotel_id=1,
                    user_id=20,
                    role="receptionist",
                    status="active",
                ),
                UserPermissionOverride(
                    hotel_id=1,
                    user_id=20,
                    permission_code=permission_code,
                    allowed=False,
                    version=1,
                ),
            ]
        )
    db.commit()
    return secret


def _issue_permission_restore_ticket(client, secret: str, path: str) -> str:
    response = client.post(
        "/api/auth/step-up",
        json={
            "code": pyotp.TOTP(secret).now(),
            "permission_code": PERMISSION_PERMISSION_MANAGE,
            "method": "DELETE",
            "path": path,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["ticket"]


@pytest.mark.parametrize(
    ("restore_kind", "path"),
    [
        (
            "role",
            "/api/permissions/overrides/role/receptionist/guest:edit",
        ),
        (
            "role",
            "/api/permissions/role-overrides/receptionist/guest:edit",
        ),
        (
            "user",
            "/api/permissions/overrides/user/20/guest:edit",
        ),
        (
            "user",
            "/api/permissions/user-overrides/20/guest:edit",
        ),
    ],
)
@pytest.mark.parametrize("ticket_mode", ["missing", "invalid", "valid"])
def test_permission_override_restore_requires_action_bound_step_up(
    restore_kind, path, ticket_mode
):
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=10)
    try:
        secret = _seed_permission_restore_state(db, restore_kind)
        headers = {}
        if ticket_mode == "invalid":
            headers["X-Action-Step-Up-Ticket"] = "not-a-valid-signed-ticket"
        elif ticket_mode == "valid":
            headers["X-Action-Step-Up-Ticket"] = _issue_permission_restore_ticket(
                client, secret, path
            )

        response = client.delete(
            path,
            params={"expected_version": 1},
            headers=headers,
        )

        if ticket_mode == "valid":
            assert response.status_code == 200, response.text
            assert response.json()["restored"] is True
        else:
            assert response.status_code == 428, response.text
            detail = response.json()["detail"]
            assert detail == {
                "code": "STEP_UP_REQUIRED",
                "permission_code": PERMISSION_PERMISSION_MANAGE,
                "method": "DELETE",
                "path": path,
            }

        db.expire_all()
        if restore_kind == "role":
            row = db.query(HotelPermissionOverride).filter_by(
                hotel_id=1,
                role="receptionist",
                permission_code=canonical_permission_code(PERMISSION_GUEST_EDIT),
            ).one_or_none()
        else:
            row = db.query(UserPermissionOverride).filter_by(
                hotel_id=1,
                user_id=20,
                permission_code=canonical_permission_code(PERMISSION_GUEST_EDIT),
            ).one_or_none()

        if ticket_mode == "valid":
            assert row is None
        else:
            assert row is not None
            assert row.allowed is False
            assert row.version == 1
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_whatsapp_channel_status_requires_inbox_or_integration_view_permission(monkeypatch):
    client, db, engine = _client_with_db()
    _enable_whatsapp_plan_for_api_test(monkeypatch)
    try:
        db.add_all(
            [
                HotelPermissionOverride(
                    hotel_id=1,
                    role="manager",
                    permission_code=PERMISSION_WHATSAPP_INBOX_VIEW,
                    allowed=False,
                ),
                HotelPermissionOverride(
                    hotel_id=1,
                    role="manager",
                    permission_code=PERMISSION_SETTINGS_INTEGRATIONS_VIEW,
                    allowed=False,
                ),
            ]
        )
        db.commit()

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")
        denied = client.get("/api/whatsapp/channel")
        assert denied.status_code == 403

        # The inbox and settings pages both use this endpoint, but have distinct
        # read permissions. Either one should preserve the shared status view.
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")
        inbox_reader = client.get("/api/whatsapp/channel")
        assert inbox_reader.status_code == 200, inbox_reader.text
        assert inbox_reader.json() == {"status": "ready", "channel": None}

        db.add(
            HotelPermissionOverride(
                hotel_id=1,
                role="owner",
                permission_code=PERMISSION_WHATSAPP_INBOX_VIEW,
                allowed=False,
            )
        )
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        integration_reader = client.get("/api/whatsapp/channel")
        assert integration_reader.status_code == 200, integration_reader.text
        assert integration_reader.json() == {"status": "ready", "channel": None}
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_whatsapp_channel_status_serializes_only_the_ui_summary(monkeypatch):
    client, db, engine = _client_with_db()
    _enable_whatsapp_plan_for_api_test(monkeypatch)
    try:
        channel = WhatsAppChannel(
            hotel_id=1,
            waba_id="synthetic-waba-id",
            phone_number_id="synthetic-phone-id",
            display_phone_number="+5491100000000",
            display_name="Synthetic Channel",
            status=WhatsAppChannelStatusEnum.ACTIVE,
            last_error_code="SYNTHETIC_ERR",
            last_error="Synthetic integration diagnostic",
        )
        db.add(channel)
        db.flush()
        contact = WhatsAppContact(
            hotel_id=1,
            channel_id=channel.id,
            normalized_phone="5491100000001",
            display_name="Synthetic Guest",
        )
        db.add(contact)
        db.flush()
        conversation = WhatsAppConversation(
            hotel_id=1,
            channel_id=channel.id,
            contact_id=contact.id,
            status=WhatsAppConversationStatusEnum.NEW,
        )
        db.add(conversation)
        db.flush()
        db.add(
            WhatsAppMessage(
                hotel_id=1,
                conversation_id=conversation.id,
                direction=WhatsAppMessageDirectionEnum.INBOUND,
                status=WhatsAppMessageStatusEnum.RECEIVED,
                message_type="text",
                text="SYNTHETIC_PRIVATE_MESSAGE",
            )
        )
        db.commit()

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")
        response = client.get("/api/whatsapp/channel")

        assert response.status_code == 200, response.text
        assert response.json() == {
            "status": "active",
            "channel": {
                "id": channel.id,
                "status": "active",
                "display_phone_number": "+5491100000000",
                "display_name": "Synthetic Channel",
            },
        }
        assert "synthetic-waba-id" not in response.text
        assert "synthetic-phone-id" not in response.text
        assert "Synthetic integration diagnostic" not in response.text
        assert "SYNTHETIC_PRIVATE_MESSAGE" not in response.text
        assert "Synthetic Guest" not in response.text
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()
