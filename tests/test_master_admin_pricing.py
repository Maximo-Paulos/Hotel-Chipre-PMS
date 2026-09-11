"""Public pricing is owner-editable from the master-admin console.

Reuses the master_client harness from test_master_admin_panel so the auth,
MFA and CSRF path under test is the real one.
"""
from decimal import Decimal

import pytest

from app.config import get_settings
from app.master_admin.models import MasterAdminAuditEvent
from app.models.marketing import MarketingLead, MarketingPricingPlan

from tests.test_master_admin_panel import (  # noqa: F401  (fixtures)
    _complete_master_login,
    _enable_mocked_master_providers,
    _seed_platform_admin,
    master_client,
)


def _login(client, SessionLocal, monkeypatch):
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
    get_settings.cache_clear()
    db = SessionLocal()
    try:
        _seed_platform_admin(db)
        db.commit()
    finally:
        db.close()
    login = _complete_master_login(client, SessionLocal)
    return {"X-CSRF-Token": login.cookies.get("master_admin_csrf")}


def test_pricing_requires_master_admin(master_client):
    client, _ = master_client
    assert client.get("/api/master-admin/pricing/plans").status_code in (401, 403)
    assert client.put("/api/master-admin/pricing/plans", json={"plans": []}).status_code in (401, 403)


def test_leads_require_master_admin(master_client):
    client, _ = master_client
    assert client.get("/api/master-admin/leads").status_code in (401, 403)


def test_owner_sets_a_price_and_the_public_endpoint_serves_it(master_client, monkeypatch):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)

    # Nothing published yet: the site shows caps, no number.
    assert client.get("/api/public/pricing").json()["plans"][0]["price_amount"] is None

    saved = client.put(
        "/api/master-admin/pricing/plans",
        headers=headers,
        json={
            "plans": [
                {
                    "code": "starter",
                    "name": "Starter",
                    "sort_order": 10,
                    "room_limit": 15,
                    "features": ["Reservas", "Caja"],
                },
                {
                    "code": "pro",
                    "name": "Pro",
                    "sort_order": 20,
                    "price_amount": "38900.00",
                    "currency": "ars",
                    "room_limit": 40,
                    "highlight": True,
                },
            ]
        },
    )
    assert saved.status_code == 200, saved.text

    plans = client.get("/api/public/pricing").json()["plans"]
    assert [plan["code"] for plan in plans] == ["starter", "pro"]
    assert plans[0]["price_amount"] is None
    assert plans[0]["features"] == ["Reservas", "Caja"]
    assert plans[1]["price_amount"] == "38900.00"
    assert plans[1]["currency"] == "ARS"
    assert plans[1]["highlight"] is True


def test_saving_pricing_writes_an_audit_event(master_client, monkeypatch):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)

    client.put(
        "/api/master-admin/pricing/plans",
        headers=headers,
        json={"plans": [{"code": "starter", "name": "Starter"}]},
    )

    db = SessionLocal()
    try:
        actions = [event.action for event in db.query(MasterAdminAuditEvent).all()]
    finally:
        db.close()
    assert "master_admin_update_pricing_plans" in actions


def test_a_plan_dropped_from_the_payload_disappears(master_client, monkeypatch):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)

    client.put(
        "/api/master-admin/pricing/plans",
        headers=headers,
        json={
            "plans": [
                {"code": "starter", "name": "Starter", "sort_order": 10},
                {"code": "legacy", "name": "Legacy", "sort_order": 20},
            ]
        },
    )
    client.put(
        "/api/master-admin/pricing/plans",
        headers=headers,
        json={"plans": [{"code": "starter", "name": "Starter", "sort_order": 10}]},
    )

    db = SessionLocal()
    try:
        assert [plan.code for plan in db.query(MarketingPricingPlan).all()] == ["starter"]
    finally:
        db.close()


def test_negative_price_is_rejected(master_client, monkeypatch):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)

    response = client.put(
        "/api/master-admin/pricing/plans",
        headers=headers,
        json={"plans": [{"code": "starter", "name": "Starter", "price_amount": "-1.00"}]},
    )

    assert response.status_code == 422


def test_owner_can_read_captured_leads(master_client, monkeypatch):
    client, SessionLocal = master_client
    headers = _login(client, SessionLocal, monkeypatch)
    client.post("/api/public/leads", json={"email": "dueno@hotel.com", "hotel_name": "Hotel Río"})

    body = client.get("/api/master-admin/leads", headers=headers).json()

    assert body["total"] == 1
    assert body["items"][0]["email"] == "dueno@hotel.com"
    assert body["items"][0]["hotel_name"] == "Hotel Río"
    # The stored IP hash is never handed back out.
    assert "ip_hash" not in body["items"][0]
