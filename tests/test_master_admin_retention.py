from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
import pyotp

from app.config import get_settings
from app.master_admin.models import MasterAdminAuditEvent, PrivacyRetentionHold
from app.models.marketing import MarketingLead
from app.models.public_inquiry import PublicInquiry
from app.models.user import User
from app.models.user_mfa import UserMfaSecret
from app.services import mfa_service
from tests.test_master_admin_panel import (
    _complete_master_login,
    _seed_platform_admin,
    master_client,
)


def _login(client, SessionLocal, monkeypatch):
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
    get_settings.cache_clear()
    with SessionLocal() as db:
        _seed_platform_admin(db)
        db.commit()
    login = _complete_master_login(client, SessionLocal)
    return {"X-CSRF-Token": login.cookies.get("master_admin_csrf")}


def _lead(SessionLocal, email="lead@example.test"):
    with SessionLocal() as db:
        lead = MarketingLead(email=email, name="Synthetic Lead", source="test")
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead.id, lead.updated_at


def _fresh_totp_code(SessionLocal):
    with SessionLocal() as db:
        user = db.query(User).filter_by(email="platform-admin@example.com").one()
        mfa_secret = db.query(UserMfaSecret).filter_by(user_id=user.id).one()
        secret = mfa_service.decrypt_totp_secret(mfa_secret.encrypted_secret)
        # Synthetic tests may perform several privileged actions in one TOTP
        # timestep; reset only this disposable fixture's replay marker.
        mfa_secret.last_used_step = None
        db.commit()
        return pyotp.TOTP(secret).now()


def test_retention_hold_endpoints_require_master_admin_and_csrf(master_client, monkeypatch):
    client, SessionLocal = master_client
    payload = {
        "resource_type": "marketing_lead",
        "record_id": 1,
        "reason_code": "litigation",
        "case_reference": "CASE-2026-41",
    }

    assert client.get("/api/master-admin/privacy-retention/holds").status_code == 401
    assert client.post("/api/master-admin/privacy-retention/holds", json=payload).status_code == 401

    headers = _login(client, SessionLocal, monkeypatch)
    no_csrf = client.post("/api/master-admin/privacy-retention/holds", json=payload)
    bad_csrf = client.post(
        "/api/master-admin/privacy-retention/holds",
        headers={"X-CSRF-Token": "wrong-token"},
        json=payload,
    )
    assert no_csrf.status_code == 403
    assert bad_csrf.status_code == 403

    db = SessionLocal()
    try:
        assert db.query(PrivacyRetentionHold).count() == 0
    finally:
        db.close()
    assert headers["X-CSRF-Token"]


def test_marketing_lead_hold_is_audited_and_does_not_extend_the_retention_clock(
    master_client, monkeypatch
):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)
    lead_id, original_updated_at = _lead(SessionLocal)

    response = client.post(
        "/api/master-admin/privacy-retention/holds",
        headers=headers,
        json={
            "resource_type": "marketing_lead",
            "record_id": lead_id,
            "reason_code": "litigation",
            "case_reference": "CASE-2026-41",
            "hold_until": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["resource_type"] == "marketing_lead"
    assert response.json()["record_id"] == lead_id
    assert response.json()["case_reference"] == "CASE-2026-41"
    assert response.json()["released_at"] is None

    db = SessionLocal()
    try:
        lead = db.get(MarketingLead, lead_id)
        hold = db.query(PrivacyRetentionHold).one()
        event = db.query(MasterAdminAuditEvent).filter_by(action="privacy_retention_hold_place").one()
        assert lead.updated_at == original_updated_at
        assert hold.placed_by_user_id == event.actor_user_id
        assert event.target_id == f"marketing_lead:{lead_id}"
        metadata = json.loads(event.metadata_json)
        assert metadata["case_reference"] == "CASE-2026-41"
        assert "email" not in metadata
        assert "lead@example.test" not in event.metadata_json
    finally:
        db.close()

    listed = client.get("/api/master-admin/privacy-retention/holds", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_retention_hold_list_paginates_and_keeps_unreleased_holds_first(master_client, monkeypatch):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)
    hold_ids = []
    for index in range(3):
        lead_id, _ = _lead(SessionLocal, email=f"lead{index}@example.test")
        response = client.post(
            "/api/master-admin/privacy-retention/holds",
            headers=headers,
            json={
                "resource_type": "marketing_lead",
                "record_id": lead_id,
                "reason_code": "litigation",
                "case_reference": f"CASE-2026-{index + 10}",
            },
        )
        assert response.status_code == 201, response.text
        hold_ids.append(response.json()["id"])

    with SessionLocal() as db:
        released = db.get(PrivacyRetentionHold, hold_ids[0])
        released.released_at = datetime.now(timezone.utc)
        db.commit()

    first_page = client.get("/api/master-admin/privacy-retention/holds?limit=2&offset=0", headers=headers)
    second_page = client.get("/api/master-admin/privacy-retention/holds?limit=2&offset=2", headers=headers)
    assert first_page.status_code == second_page.status_code == 200
    assert len(first_page.json()) == 2
    assert all(row["released_at"] is None for row in first_page.json())
    assert [row["id"] for row in second_page.json()] == [hold_ids[0]]


def test_hold_can_protect_a_public_inquiry_without_copying_its_content(master_client, monkeypatch):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)
    inquiry_anchor = datetime(2026, 9, 26, 12, 30)
    with SessionLocal() as db:
        inquiry = PublicInquiry(
            name="Synthetic Contact",
            email="contact@example.test",
            message="Synthetic inquiry text",
            privacy_consent_at=datetime.now(timezone.utc).replace(tzinfo=None),
            created_at=inquiry_anchor,
        )
        db.add(inquiry)
        db.commit()
        inquiry_id = inquiry.id

    response = client.post(
        "/api/master-admin/privacy-retention/holds",
        headers=headers,
        json={
            "resource_type": "public_inquiry",
            "record_id": inquiry_id,
            "reason_code": "regulatory",
            "case_reference": "REG-2026-9",
            "hold_until": None,
        },
    )
    assert response.status_code == 201, response.text

    search = client.post(
        "/api/master-admin/privacy-retention/targets/search",
        headers=headers,
        json={"resource_type": "public_inquiry", "query": "contact@example.test"},
    )
    assert search.status_code == 200, search.text
    target_anchor = datetime.fromisoformat(search.json()[0]["retention_anchor_at"])
    assert target_anchor == inquiry_anchor.replace(tzinfo=timezone.utc)

    db = SessionLocal()
    try:
        event = db.query(MasterAdminAuditEvent).filter_by(action="privacy_retention_hold_place").one()
        assert "contact@example.test" not in event.metadata_json
        assert "Synthetic inquiry text" not in event.metadata_json
    finally:
        db.close()


def test_retention_target_search_masks_email_and_audits_only_search_metadata(master_client, monkeypatch):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)
    email = "lead@example.test"
    lead_id, _ = _lead(SessionLocal, email=email)
    lead_anchor = datetime(2026, 9, 26, 12, 30, tzinfo=timezone.utc)
    with SessionLocal() as db:
        db.query(MarketingLead).filter_by(id=lead_id).update(
            {MarketingLead.updated_at: lead_anchor},
            synchronize_session=False,
        )
        db.commit()

    missing_csrf = client.post(
        "/api/master-admin/privacy-retention/targets/search",
        json={"resource_type": "marketing_lead", "query": email},
    )
    assert missing_csrf.status_code == 403

    response = client.post(
        "/api/master-admin/privacy-retention/targets/search",
        headers=headers,
        json={"resource_type": "marketing_lead", "query": f"  {email}  "},
    )
    assert response.status_code == 200, response.text
    results = response.json()
    assert len(results) == 1
    assert results[0]["resource_type"] == "marketing_lead"
    assert results[0]["record_id"] == lead_id
    assert results[0]["masked_email"] == "l***@e***.test"
    assert datetime.fromisoformat(results[0]["retention_anchor_at"]) == lead_anchor
    assert email not in response.text

    by_id = client.post(
        "/api/master-admin/privacy-retention/targets/search",
        headers=headers,
        json={"resource_type": "marketing_lead", "query": str(lead_id)},
    )
    assert by_id.status_code == 200
    assert [row["record_id"] for row in by_id.json()] == [lead_id]

    db = SessionLocal()
    try:
        events = (
            db.query(MasterAdminAuditEvent)
            .filter_by(action="privacy_retention_target_search")
            .order_by(MasterAdminAuditEvent.id)
            .all()
        )
        assert len(events) == 2
        for event in events:
            assert email not in (event.metadata_json or "")
        metadata = json.loads(events[0].metadata_json)
        assert metadata == {"search_kind": "exact_email", "result_count": 1}
        assert json.loads(events[1].metadata_json) == {"search_kind": "id", "result_count": 1}
    finally:
        db.close()


def test_hold_rejects_missing_targets_expired_dates_and_duplicate_active_holds(master_client, monkeypatch):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)
    lead_id, _ = _lead(SessionLocal)
    base_payload = {
        "resource_type": "marketing_lead",
        "record_id": lead_id,
        "reason_code": "contractual",
        "case_reference": "CONTRACT-2026-12",
    }

    missing = client.post(
        "/api/master-admin/privacy-retention/holds",
        headers=headers,
        json={**base_payload, "record_id": lead_id + 1000},
    )
    assert missing.status_code == 404

    expired = client.post(
        "/api/master-admin/privacy-retention/holds",
        headers=headers,
        json={**base_payload, "hold_until": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()},
    )
    assert expired.status_code == 422

    placed = client.post("/api/master-admin/privacy-retention/holds", headers=headers, json=base_payload)
    duplicate = client.post("/api/master-admin/privacy-retention/holds", headers=headers, json=base_payload)
    assert placed.status_code == 201, placed.text
    assert duplicate.status_code == 409

    db = SessionLocal()
    try:
        assert db.query(PrivacyRetentionHold).count() == 1
    finally:
        db.close()


def test_releasing_a_hold_requires_a_reason_and_writes_a_second_audit_event(master_client, monkeypatch):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)
    lead_id, _ = _lead(SessionLocal)
    placed = client.post(
        "/api/master-admin/privacy-retention/holds",
        headers=headers,
        json={
            "resource_type": "marketing_lead",
            "record_id": lead_id,
            "reason_code": "litigation",
            "case_reference": "CASE-2026-77",
        },
    )
    hold_id = placed.json()["id"]

    missing_reason = client.post(
        f"/api/master-admin/privacy-retention/holds/{hold_id}/release",
        headers=headers,
        json={"reason_code": "entered_in_error"},
    )
    assert missing_reason.status_code == 422

    released = client.post(
        f"/api/master-admin/privacy-retention/holds/{hold_id}/release",
        headers=headers,
        json={
            "reason_code": "obligation_ended",
            "case_reference": "CASE-2026-77-1",
            "password": "Master123!",
            "mfa_code": _fresh_totp_code(SessionLocal),
        },
    )
    assert released.status_code == 200, released.text
    assert released.json()["released_by_user_id"] is not None
    assert released.json()["release_reason_code"] == "obligation_ended"

    again = client.post(
        f"/api/master-admin/privacy-retention/holds/{hold_id}/release",
        headers=headers,
        json={
            "reason_code": "obligation_ended",
            "case_reference": "CASE-2026-77-1",
            "password": "Master123!",
            "mfa_code": _fresh_totp_code(SessionLocal),
        },
    )
    assert again.status_code == 409

    db = SessionLocal()
    try:
        actions = [event.action for event in db.query(MasterAdminAuditEvent).all()]
        assert actions.count("privacy_retention_hold_place") == 1
        assert actions.count("privacy_retention_hold_release") == 2
        assert db.query(PrivacyRetentionHold).one().released_at is not None
    finally:
        db.close()


def test_release_requires_password_and_fresh_mfa_and_audits_denials(master_client, monkeypatch):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)
    lead_id, _ = _lead(SessionLocal)
    placed = client.post(
        "/api/master-admin/privacy-retention/holds",
        headers=headers,
        json={
            "resource_type": "marketing_lead",
            "record_id": lead_id,
            "reason_code": "litigation",
            "case_reference": "CASE-2026-88",
        },
    )
    assert placed.status_code == 201, placed.text
    hold_id = placed.json()["id"]

    payload = {
        "reason_code": "obligation_ended",
        "case_reference": "CASE-2026-88-1",
        "password": "wrong-password",
        "mfa_code": "000000",
    }
    wrong_password = client.post(
        f"/api/master-admin/privacy-retention/holds/{hold_id}/release",
        headers=headers,
        json=payload,
    )
    assert wrong_password.status_code == 401

    payload["password"] = "Master123!"
    current_code = _fresh_totp_code(SessionLocal)
    invalid_code = "000000" if current_code != "000000" else "000001"
    payload["mfa_code"] = invalid_code
    rejected_code = client.post(
        f"/api/master-admin/privacy-retention/holds/{hold_id}/release",
        headers=headers,
        json=payload,
    )
    assert rejected_code.status_code == 401

    payload["mfa_code"] = _fresh_totp_code(SessionLocal)
    accepted = client.post(
        f"/api/master-admin/privacy-retention/holds/{hold_id}/release",
        headers=headers,
        json=payload,
    )
    assert accepted.status_code == 200, accepted.text
    replayed = client.post(
        f"/api/master-admin/privacy-retention/holds/{hold_id}/release",
        headers=headers,
        json=payload,
    )
    assert replayed.status_code == 401

    db = SessionLocal()
    try:
        assert db.query(PrivacyRetentionHold).one().released_at is not None
        events = (
            db.query(MasterAdminAuditEvent)
            .filter_by(action="privacy_retention_hold_release")
            .order_by(MasterAdminAuditEvent.id)
            .all()
        )
        assert [event.outcome for event in events] == ["failure", "failure", "success", "failure"]
        assert all("Master123!" not in (event.metadata_json or "") for event in events)
        assert all("000000" not in (event.metadata_json or "") for event in events)
    finally:
        db.close()


def test_release_password_guesses_consume_the_persistent_mfa_attempt_budget(master_client, monkeypatch):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)
    lead_id, _ = _lead(SessionLocal)
    placed = client.post(
        "/api/master-admin/privacy-retention/holds",
        headers=headers,
        json={
            "resource_type": "marketing_lead",
            "record_id": lead_id,
            "reason_code": "litigation",
            "case_reference": "CASE-2026-89",
        },
    )
    assert placed.status_code == 201, placed.text
    hold_id = placed.json()["id"]

    import app.adapters.rate_limiter as rate_limiter_module

    monkeypatch.setattr(rate_limiter_module.mfa_code_guess_limiter, "limit", 1)
    payload = {
        "reason_code": "obligation_ended",
        "case_reference": "CASE-2026-89-1",
        "password": "wrong-password",
        "mfa_code": "000000",
    }
    first_guess = client.post(
        f"/api/master-admin/privacy-retention/holds/{hold_id}/release",
        headers=headers,
        json=payload,
    )
    blocked_guess = client.post(
        f"/api/master-admin/privacy-retention/holds/{hold_id}/release",
        headers=headers,
        json=payload,
    )

    assert first_guess.status_code == 401
    assert blocked_guess.status_code == 429
    with SessionLocal() as db:
        hold = db.query(PrivacyRetentionHold).one()
        assert hold.released_at is None


def test_hold_and_audit_are_one_transaction(master_client, monkeypatch):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)
    lead_id, _ = _lead(SessionLocal)

    import app.master_admin.privacy_retention as retention_module

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(retention_module, "audit_master_action", fail_audit)
    # The application's exception middleware logs the internal failure and
    # returns a generic 500 instead of exposing it through TestClient.
    response = client.post(
        "/api/master-admin/privacy-retention/holds",
        headers=headers,
        json={
            "resource_type": "marketing_lead",
            "record_id": lead_id,
            "reason_code": "litigation",
            "case_reference": "CASE-2026-1",
        },
    )
    assert response.status_code == 500

    db = SessionLocal()
    try:
        assert db.query(PrivacyRetentionHold).count() == 0
        assert db.query(MasterAdminAuditEvent).filter_by(action="privacy_retention_hold_place").count() == 0
    finally:
        db.close()


@pytest.mark.parametrize("resource_type", ["hotel", "user", "public_inquiry ; DROP TABLE users"])
def test_hold_rejects_unsupported_resource_types(master_client, monkeypatch, resource_type):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)
    response = client.post(
        "/api/master-admin/privacy-retention/holds",
        headers=headers,
        json={
            "resource_type": resource_type,
            "record_id": 1,
            "reason_code": "other",
            "case_reference": "CASE-2026-1",
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "case_reference",
    [
        "person@example.com",
        "+5491123456789",
        "CASE-2026 with spaces",
        "Juan-Perez",
        "DNI-30123456",
        "Tel-1155551234",
        "CASE-2026-1155551234",
        "CASE-2026-30123456",
        "CASE-2026-123456-78901",
    ],
)
def test_retention_hold_rejects_contact_details_as_legal_reference(master_client, monkeypatch, case_reference):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)
    lead_id, _ = _lead(SessionLocal)
    response = client.post(
        "/api/master-admin/privacy-retention/holds",
        headers=headers,
        json={
            "resource_type": "marketing_lead",
            "record_id": lead_id,
            "reason_code": "litigation",
            "case_reference": case_reference,
        },
    )
    assert response.status_code == 422


def test_release_of_missing_hold_is_audited(master_client, monkeypatch):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)
    response = client.post(
        "/api/master-admin/privacy-retention/holds/999999/release",
        headers=headers,
        json={
            "reason_code": "other",
            "case_reference": "CASE-2026-404",
            "password": "Master123!",
            "mfa_code": _fresh_totp_code(SessionLocal),
        },
    )
    assert response.status_code == 404
    db = SessionLocal()
    try:
        event = db.query(MasterAdminAuditEvent).filter_by(action="privacy_retention_hold_release").one()
        assert event.outcome == "not_found"
        assert "CASE-2026-404" in (event.metadata_json or "")
    finally:
        db.close()
