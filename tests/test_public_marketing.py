"""The two endpoints the public website calls, and the ways an anonymous
caller could abuse the write one."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.adapters.rate_limiter import lead_capture_limiter
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models.marketing import MarketingLead, MarketingPricingPlan
from app.services.subscription_entitlements import TRIAL_DURATION_DAYS


@pytest.fixture
def client_with_db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    def override_get_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = override_get_db
    original_limit = lead_capture_limiter.limit
    try:
        yield TestClient(fastapi_app), db
    finally:
        fastapi_app.dependency_overrides.clear()
        lead_capture_limiter.limit = original_limit
        db.close()
        engine.dispose()


def _plan(db, code, **kwargs):
    plan = MarketingPricingPlan(code=code, name=kwargs.pop("name", code.title()), **kwargs)
    db.add(plan)
    db.commit()
    return plan


class TestPublicPricing:
    def test_falls_back_to_real_plan_caps_when_unseeded(self, client_with_db):
        client, _ = client_with_db
        body = client.get("/api/public/pricing").json()

        assert [plan["code"] for plan in body["plans"]] == ["starter", "pro", "ultra"]
        # The caps are the ones actually enforced, so they are safe to publish.
        assert [plan["room_limit"] for plan in body["plans"]] == [15, 40, 80]
        # And no price is invented.
        assert all(plan["price_amount"] is None for plan in body["plans"])
        assert body["trial_days"] == TRIAL_DURATION_DAYS

    def test_serves_configured_plans_in_sort_order(self, client_with_db):
        client, db = client_with_db
        _plan(db, "ultra", sort_order=30, price_amount=Decimal("99.00"), currency="USD")
        _plan(db, "starter", sort_order=10)

        plans = client.get("/api/public/pricing").json()["plans"]

        assert [plan["code"] for plan in plans] == ["starter", "ultra"]
        assert plans[0]["price_amount"] is None
        assert plans[1]["price_amount"] == "99.00"
        assert plans[1]["currency"] == "USD"

    def test_hides_non_public_plans(self, client_with_db):
        client, db = client_with_db
        _plan(db, "starter", sort_order=10)
        _plan(db, "internal", sort_order=20, is_public=False)

        plans = client.get("/api/public/pricing").json()["plans"]

        assert [plan["code"] for plan in plans] == ["starter"]

    def test_survives_a_missing_table(self, client_with_db):
        """A deploy that has not run the migration yet must not 500 the page."""
        client, db = client_with_db
        db.execute(text("DROP TABLE marketing_pricing_plans"))
        db.commit()

        body = client.get("/api/public/pricing").json()

        assert [plan["code"] for plan in body["plans"]] == ["starter", "pro", "ultra"]
        assert all(plan["price_amount"] is None for plan in body["plans"])

    def test_decodes_features(self, client_with_db):
        client, db = client_with_db
        _plan(db, "pro", sort_order=10, features_json='["Caja y arqueo", "Tarifas"]')

        assert client.get("/api/public/pricing").json()["plans"][0]["features"] == [
            "Caja y arqueo",
            "Tarifas",
        ]


class TestLeadCapture:
    def test_records_a_lead(self, client_with_db):
        client, db = client_with_db

        response = client.post(
            "/api/public/leads",
            json={"email": "Dueno@Hotel.COM", "hotel_name": "Hotel Río", "rooms_estimate": 22},
        )

        assert response.status_code == 200
        lead = db.query(MarketingLead).one()
        assert lead.email == "dueno@hotel.com"
        assert lead.hotel_name == "Hotel Río"
        assert lead.rooms_estimate == 22

    def test_never_stores_the_raw_ip(self, client_with_db):
        client, db = client_with_db
        client.post("/api/public/leads", json={"email": "a@b.com"})

        lead = db.query(MarketingLead).one()
        assert lead.ip_hash and len(lead.ip_hash) == 64
        assert "testclient" not in lead.ip_hash

    def test_repeat_email_is_idempotent_and_enriches(self, client_with_db):
        client, db = client_with_db
        client.post(
            "/api/public/leads",
            json={"email": "a@b.com", "hotel_name": "Hotel Río", "source": "hero"},
        )
        second = client.post(
            "/api/public/leads", json={"email": "a@b.com", "city": "Bariloche", "source": "final"}
        )

        # Same answer either way: an anonymous caller must not learn whether an
        # address is already on the list.
        assert second.status_code == 200
        lead = db.query(MarketingLead).one()
        assert lead.city == "Bariloche"
        # The earlier answer survives a later submission that omitted it.
        assert lead.hotel_name == "Hotel Río"
        # First touch wins, so attribution is not rewritten by a later visit.
        assert lead.source == "hero"

    def test_honeypot_is_silently_dropped(self, client_with_db):
        client, db = client_with_db

        response = client.post(
            "/api/public/leads",
            json={"email": "bot@spam.com", "company_website": "http://spam"},
        )

        assert response.status_code == 200
        assert db.query(MarketingLead).count() == 0

    def test_rejects_invalid_email(self, client_with_db):
        client, db = client_with_db

        assert client.post("/api/public/leads", json={"email": "not-an-email"}).status_code == 422
        assert db.query(MarketingLead).count() == 0

    def test_rate_limits_a_flood_from_one_source(self, client_with_db):
        client, db = client_with_db
        lead_capture_limiter.limit = 3

        codes = [
            client.post("/api/public/leads", json={"email": f"a{i}@b.com"}).status_code
            for i in range(5)
        ]

        assert codes == [200, 200, 200, 429, 429]
        assert db.query(MarketingLead).count() == 3

    def test_caps_utm_payload(self, client_with_db):
        client, db = client_with_db
        client.post(
            "/api/public/leads",
            json={"email": "a@b.com", "utm": {f"k{i}": "x" * 500 for i in range(30)}},
        )

        lead = db.query(MarketingLead).one()
        assert len(lead.utm_json) < 4000
