from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api import rate_change_drafts
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
import app.models  # noqa: F401
from app.models.audit_log import AuditLog
from app.models.daily_rate import DailyRate
from app.models.daily_rate import PricePeriod
from app.models.guest import DocumentTypeEnum, Guest
from app.models.hotel_config import HotelConfiguration
from app.models.rate_change_draft import RateChangeDraft
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.user import User


@pytest.fixture
def rate_client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'rate_change_drafts.db'}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_local()
    app = FastAPI()
    app.include_router(rate_change_drafts.router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        hotel_id=1,
        user_id=123,
        user_email="owner@example.com",
        user_role="owner",
        is_verified=True,
    )
    with TestClient(app) as client:
        yield client, db
    app.dependency_overrides.clear()
    db.rollback()
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def seed_rate_context(db):
    db.add(HotelConfiguration(id=1, subscription_active=True))
    db.add(User(id=123, email="owner@example.com", password_hash="test", is_active=True, is_verified=True))
    db.flush()
    category = RoomCategory(
        hotel_id=1,
        name="Doble",
        code="DBL",
        base_price_per_night=100,
        variable_cost_per_night=0,
        max_occupancy=2,
    )
    db.add(category)
    guest = Guest(
        hotel_id=1,
        first_name="Test",
        last_name="Guest",
        document_type=DocumentTypeEnum.DNI,
        document_number="RATE-DRAFT-001",
        terms_accepted=True,
    )
    db.add(guest)
    db.flush()
    reservation = Reservation(
        hotel_id=1,
        confirmation_code="RATE-DRAFT-RES-001",
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 7, 10),
        check_out_date=date(2026, 7, 12),
        status=ReservationStatusEnum.PENDING,
        total_amount=200,
    )
    db.add(reservation)
    db.commit()
    return category, reservation


def test_rate_draft_requires_confirmation_and_keeps_reservation_price(rate_client):
    client, db = rate_client
    category, reservation = seed_rate_context(db)

    response = client.post(
        "/api/rate-change-drafts",
        json={
            "category_id": category.id,
            "changes": [
                {"date": "2026-07-10", "values": {"price": 125}},
                {"date": "2026-07-11", "values": {"price_transfer": 140}},
            ],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "draft"
    assert body["impact"] == {
        "reservations_impacted": 1,
        "reservation_nights": 2,
        "dates_with_reservations": ["2026-07-10", "2026-07-11"],
    }
    assert db.query(DailyRate).count() == 0

    confirmed = client.post(
        f"/api/rate-change-drafts/{body['id']}/confirm",
        json={"expected_version": body["version"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert db.query(DailyRate).filter_by(date=date(2026, 7, 10)).one().price == 125
    rate_two = db.query(DailyRate).filter_by(date=date(2026, 7, 11)).one()
    assert rate_two.price == 100
    assert rate_two.price_transfer == 140
    db.refresh(reservation)
    assert float(reservation.total_amount) == 200
    rate_audits = db.query(AuditLog).filter(AuditLog.table_name == "daily_rates").all()
    draft_audits = db.query(AuditLog).filter(AuditLog.table_name == "rate_change_drafts").all()
    assert len(rate_audits) == 2
    assert len(draft_audits) == 2


def test_rate_confirmation_rolls_back_business_change_if_audit_write_fails(rate_client, monkeypatch):
    client, db = rate_client
    category, _reservation = seed_rate_context(db)
    created = client.post(
        "/api/rate-change-drafts",
        json={"category_id": category.id, "changes": [{"date": "2026-07-10", "values": {"price": 125}}]},
    )
    assert created.status_code == 201, created.text
    draft = created.json()

    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("app.services.audit_log_service.create_audit_log", fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        client.post(
            f"/api/rate-change-drafts/{draft['id']}/confirm",
            json={"expected_version": draft["version"]},
        )

    assert db.query(DailyRate).filter_by(hotel_id=1, category_id=category.id).count() == 0
    assert db.query(RateChangeDraft).filter_by(id=draft["id"]).one().status == "draft"


def test_stale_rate_draft_cannot_overwrite_a_newer_rate(rate_client):
    client, db = rate_client
    category, _reservation = seed_rate_context(db)
    response = client.post(
        "/api/rate-change-drafts",
        json={"category_id": category.id, "changes": [{"date": "2026-07-10", "values": {"price": 125}}]},
    )
    assert response.status_code == 201, response.text
    draft = response.json()
    db.add(DailyRate(hotel_id=1, category_id=category.id, date=date(2026, 7, 10), price=130))
    db.commit()

    confirmed = client.post(
        f"/api/rate-change-drafts/{draft['id']}/confirm",
        json={"expected_version": draft["version"]},
    )
    assert confirmed.status_code == 409
    assert db.query(DailyRate).filter_by(date=date(2026, 7, 10)).one().price == 130
    assert db.query(RateChangeDraft).filter_by(id=draft["id"]).one().status == "draft"


def test_rate_draft_is_tenant_scoped(rate_client):
    client, db = rate_client
    category, _reservation = seed_rate_context(db)
    response = client.post(
        "/api/rate-change-drafts",
        json={"category_id": category.id, "changes": [{"date": "2026-07-10", "values": {"price": 125}}]},
    )
    draft_id = response.json()["id"]
    app_context = AuthContext(hotel_id=2, user_id=123, user_role="owner", is_verified=True)
    client.app.dependency_overrides[get_auth_context] = lambda: app_context
    assert client.get(f"/api/rate-change-drafts/{draft_id}").status_code == 404


def test_rate_draft_rejects_unsafe_fields_and_duplicate_dates(rate_client):
    client, db = rate_client
    category, _reservation = seed_rate_context(db)
    extra_field = client.post(
        "/api/rate-change-drafts",
        json={"category_id": category.id, "changes": [{"date": "2026-07-10", "values": {"price": 120, "hotel_id": 99}}]},
    )
    assert extra_field.status_code == 400
    duplicate = client.post(
        "/api/rate-change-drafts",
        json={
            "category_id": category.id,
            "changes": [
                {"date": "2026-07-10", "values": {"price": 120}},
                {"date": "2026-07-10", "values": {"price": 130}},
            ],
        },
    )
    assert duplicate.status_code == 400


def _period_draft_payload(category_id: int, action: str, *, period_id: int | None = None, values=None):
    operation = {"action": action}
    if period_id is not None:
        operation["period_id"] = period_id
    if values is not None:
        operation["values"] = values
    return {"category_id": category_id, "draft_type": "price_period", "period_operation": operation}


def _period_values(*, name="Temporada de prueba", start="2026-07-10", end="2026-07-11", price=150):
    return {
        "name": name,
        "start_date": start,
        "end_date": end,
        "price_per_night": price,
        "priority": 0,
        "is_active": True,
    }


def test_price_period_create_is_draft_until_confirm_and_preserves_reservation_total(rate_client):
    client, db = rate_client
    category, reservation = seed_rate_context(db)

    response = client.post("/api/rate-change-drafts", json=_period_draft_payload(category.id, "create", values=_period_values()))
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft["draft_type"] == "price_period"
    assert draft["status"] == "draft"
    assert draft["period_operation"]["action"] == "create"
    assert [item["date"] for item in draft["period_operation"]["effective_changes"]] == ["2026-07-10", "2026-07-11"]
    assert draft["impact"]["reservation_nights"] == 2
    assert db.query(PricePeriod).count() == 0

    confirmed = client.post(f"/api/rate-change-drafts/{draft['id']}/confirm", json={"expected_version": draft["version"]})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    period = db.query(PricePeriod).filter_by(hotel_id=1, category_id=category.id, deleted_at=None).one()
    assert period.price_per_night == 150
    db.refresh(reservation)
    assert float(reservation.total_amount) == 200
    assert db.query(AuditLog).filter(AuditLog.table_name == "price_periods").count() == 1


def test_price_period_preview_excludes_explicit_daily_rate_nights(rate_client):
    client, db = rate_client
    category, _reservation = seed_rate_context(db)
    db.add(DailyRate(hotel_id=1, category_id=category.id, date=date(2026, 7, 10), price=135))
    db.commit()

    response = client.post("/api/rate-change-drafts", json=_period_draft_payload(category.id, "create", values=_period_values()))
    assert response.status_code == 201, response.text
    draft = response.json()
    assert [item["date"] for item in draft["period_operation"]["effective_changes"]] == ["2026-07-11"]
    assert draft["impact"]["reservation_nights"] == 1
    assert db.query(DailyRate).filter_by(date=date(2026, 7, 10)).one().price == 135


def test_price_period_update_and_delete_are_staged_and_confirmed_as_soft_delete(rate_client):
    client, db = rate_client
    category, _reservation = seed_rate_context(db)
    period = PricePeriod(
        hotel_id=1,
        category_id=category.id,
        name="Temporada anterior",
        start_date=date(2026, 7, 10),
        end_date=date(2026, 7, 11),
        price_per_night=110,
        priority=0,
        is_active=True,
    )
    db.add(period)
    db.commit()

    updated = client.post(
        "/api/rate-change-drafts",
        json=_period_draft_payload(category.id, "update", period_id=period.id, values=_period_values(price=175, name="Temporada nueva")),
    )
    assert updated.status_code == 201, updated.text
    update_draft = updated.json()
    db.refresh(period)
    assert period.price_per_night == 110
    confirmed_update = client.post(
        f"/api/rate-change-drafts/{update_draft['id']}/confirm",
        json={"expected_version": update_draft["version"]},
    )
    assert confirmed_update.status_code == 200, confirmed_update.text
    db.refresh(period)
    assert period.price_per_night == 175
    assert period.name == "Temporada nueva"

    deleted = client.post("/api/rate-change-drafts", json=_period_draft_payload(category.id, "delete", period_id=period.id))
    assert deleted.status_code == 201, deleted.text
    delete_draft = deleted.json()
    db.refresh(period)
    assert period.deleted_at is None
    confirmed_delete = client.post(
        f"/api/rate-change-drafts/{delete_draft['id']}/confirm",
        json={"expected_version": delete_draft["version"]},
    )
    assert confirmed_delete.status_code == 200, confirmed_delete.text
    db.refresh(period)
    assert period.deleted_at is not None
    assert db.query(AuditLog).filter(AuditLog.table_name == "price_periods").count() == 2


def test_stale_price_period_draft_requires_new_preview(rate_client):
    client, db = rate_client
    category, _reservation = seed_rate_context(db)
    period = PricePeriod(
        hotel_id=1,
        category_id=category.id,
        name="Temporada anterior",
        start_date=date(2026, 7, 10),
        end_date=date(2026, 7, 11),
        price_per_night=110,
        priority=0,
        is_active=True,
    )
    db.add(period)
    db.commit()

    response = client.post(
        "/api/rate-change-drafts",
        json=_period_draft_payload(category.id, "update", period_id=period.id, values=_period_values(price=175)),
    )
    draft = response.json()
    period.price_per_night = 120
    db.commit()
    confirmed = client.post(f"/api/rate-change-drafts/{draft['id']}/confirm", json={"expected_version": draft["version"]})
    assert confirmed.status_code == 409
    db.refresh(period)
    assert period.price_per_night == 120


def test_price_period_draft_rejects_daily_rate_changed_after_preview(rate_client):
    client, db = rate_client
    category, _reservation = seed_rate_context(db)
    response = client.post("/api/rate-change-drafts", json=_period_draft_payload(category.id, "create", values=_period_values()))
    assert response.status_code == 201, response.text
    draft = response.json()
    daily_rate = DailyRate(hotel_id=1, category_id=category.id, date=date(2026, 7, 10), price=150)
    db.add(daily_rate)
    db.commit()

    confirmed = client.post(f"/api/rate-change-drafts/{draft['id']}/confirm", json={"expected_version": draft["version"]})
    assert confirmed.status_code == 409
    assert db.query(PricePeriod).count() == 0
    assert db.query(DailyRate).filter_by(date=date(2026, 7, 10)).one().price == 150


def test_price_period_draft_rejects_impact_scope_over_366_nights(rate_client):
    client, db = rate_client
    category, _reservation = seed_rate_context(db)
    response = client.post(
        "/api/rate-change-drafts",
        json=_period_draft_payload(category.id, "create", values=_period_values(start="2026-01-01", end="2027-01-02")),
    )
    assert response.status_code == 400
    assert "366" in response.json()["detail"]
