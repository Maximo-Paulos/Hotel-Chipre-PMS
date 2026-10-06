from __future__ import annotations

import csv
import json
from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.guests import router as guests_router
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.guest import DocumentTypeEnum, Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.services.permission_service import resolve, set_override
from app.services.action_step_up_service import create_action_step_up_ticket


def _seed_hotel(db, hotel_id: int) -> None:
    db.add(HotelConfiguration(id=hotel_id, hotel_name=f"Hotel {hotel_id}", subscription_active=True))
    db.add(
        User(
            id=hotel_id,
            email=f"user-{hotel_id}@example.test",
            password_hash="test",
            is_active=True,
            is_verified=True,
        )
    )
    db.flush()


def _seed_reservation(db, hotel_id: int, *, suffix: str) -> None:
    guest = Guest(
        hotel_id=hotel_id,
        first_name=f"Guest {suffix}",
        last_name="Export",
        document_type=DocumentTypeEnum.DNI,
        document_number=f"DOC-{hotel_id}-{suffix}",
        terms_accepted=True,
    )
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Category {suffix}",
        code=f"EXP-{hotel_id}-{suffix}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    db.add_all((guest, category))
    db.flush()
    db.add(
        Reservation(
            hotel_id=hotel_id,
            guest_id=guest.id,
            category_id=category.id,
            confirmation_code=f"EXP-{hotel_id}-{suffix}",
            check_in_date=date(2026, 4, 10),
            check_out_date=date(2026, 4, 12),
            num_adults=1,
            total_amount=Decimal("100.00"),
            amount_paid=Decimal("100.00"),
            status=ReservationStatusEnum.CHECKED_IN,
        )
    )
    db.commit()


def _step_up_headers(auth_state, path: str) -> dict[str, str]:
    return {
        "X-Action-Step-Up-Ticket": create_action_step_up_ticket(
            user_id=auth_state["user_id"],
            hotel_id=auth_state["hotel_id"],
            token_version=0,
            permission_code="guest:export",
            method="GET",
            path=path,
        )
    }


@pytest.fixture
def guest_export_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    auth_state = {"hotel_id": 1, "role": "receptionist", "user_id": 1}

    app = FastAPI()
    app.include_router(guests_router)

    def override_get_db():
        yield db

    def override_auth_context():
        return AuthContext(
            hotel_id=auth_state["hotel_id"],
            user_id=auth_state["user_id"],
            user_email="role@example.test",
            user_role=auth_state["role"],
            is_verified=True,
            permissions=set(),
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_auth_context] = override_auth_context
    with TestClient(app) as client:
        yield client, db, auth_state
    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_guest_export_permission_can_be_granted_to_receptionist_by_owner(db):
    _seed_hotel(db, 8101)
    _seed_hotel(db, 8102)

    assert resolve(db, 8101, "owner", "guest:export") is True
    assert resolve(db, 8101, "co_owner", "guest:export") is True
    assert resolve(db, 8101, "manager", "guest:export") is True
    assert resolve(db, 8101, "receptionist", "guest:export") is False
    assert resolve(db, 8101, "housekeeping", "guest:export") is False

    set_override(db, 8101, "receptionist", "guest:export", True, user_id=None)

    assert resolve(db, 8101, "receptionist", "guest:export") is True
    assert resolve(db, 8102, "receptionist", "guest:export") is False


def test_guest_export_denies_unpermitted_role_without_csv_pii(guest_export_client):
    client, db, _auth_state = guest_export_client
    _seed_hotel(db, 1)
    _seed_reservation(db, 1, suffix="denied")

    response = client.get(
        "/api/guests/ledger/export",
        params={"from_date": "2026-04-01", "to_date": "2026-04-30"},
    )

    assert response.status_code == 403
    assert response.headers.get("content-type", "").startswith("application/json")
    assert "Guest denied" not in response.text


def test_guest_export_allows_owner_and_excludes_other_hotels(guest_export_client):
    client, db, auth_state = guest_export_client
    _seed_hotel(db, 1)
    _seed_hotel(db, 2)
    _seed_reservation(db, 1, suffix="included")
    _seed_reservation(db, 2, suffix="excluded")
    auth_state["role"] = "owner"

    response = client.get(
        "/api/guests/ledger/export",
        params={"from_date": "2026-04-01", "to_date": "2026-04-30"},
        headers=_step_up_headers(auth_state, "/api/guests/ledger/export"),
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert "Guest included" in response.text
    assert "Guest excluded" not in response.text
    export_event = db.query(SecurityAuditLog).filter_by(
        hotel_id=1,
        action="guest.ledger_csv_exported",
    ).one()
    assert json.loads(export_event.details or "{}") == {
        "from_date": "2026-04-01",
        "to_date": "2026-04-30",
        "row_count": 1,
    }
    assert export_event.user_id == auth_state["user_id"]
    assert export_event.resource_id is None
    assert "Guest included" not in export_event.details
    assert "DOC-1-included" not in export_event.details


def test_guest_export_rejects_invalid_and_overlong_date_ranges(guest_export_client):
    client, db, auth_state = guest_export_client
    _seed_hotel(db, 1)
    auth_state["role"] = "owner"

    missing_dates = client.get(
        "/api/guests/ledger/export",
        headers=_step_up_headers(auth_state, "/api/guests/ledger/export"),
    )
    assert missing_dates.status_code == 422

    invalid_range = client.get(
        "/api/guests/ledger/export",
        params={"from_date": "2026-04-10", "to_date": "2026-04-10"},
        headers=_step_up_headers(auth_state, "/api/guests/ledger/export"),
    )
    assert invalid_range.status_code == 422

    overlong_range = client.get(
        "/api/guests/ledger/export",
        params={"from_date": "2026-01-01", "to_date": "2027-01-04"},
        headers=_step_up_headers(auth_state, "/api/guests/ledger/export"),
    )
    assert overlong_range.status_code == 422
    assert db.query(SecurityAuditLog).filter_by(action="guest.ledger_csv_exported").count() == 0


def test_guest_export_excludes_soft_deleted_guest_identity(guest_export_client):
    from datetime import datetime, timezone

    client, db, auth_state = guest_export_client
    _seed_hotel(db, 1)
    _seed_reservation(db, 1, suffix="deleted")
    guest = db.query(Guest).filter_by(hotel_id=1).one()
    guest.deleted_at = datetime.now(timezone.utc)
    db.commit()
    auth_state["role"] = "owner"

    response = client.get(
        "/api/guests/ledger/export",
        params={"from_date": "2026-04-01", "to_date": "2026-04-30"},
        headers=_step_up_headers(auth_state, "/api/guests/ledger/export"),
    )

    assert response.status_code == 200
    assert "Guest deleted" not in response.text
    assert "DOC-1-deleted" not in response.text
    event = db.query(SecurityAuditLog).filter_by(action="guest.ledger_csv_exported").one()
    assert json.loads(event.details or "{}")["row_count"] == 0


def test_guest_export_rejects_results_over_cap_without_truncating(guest_export_client, monkeypatch):
    client, db, auth_state = guest_export_client
    _seed_hotel(db, 1)
    _seed_reservation(db, 1, suffix="cap-1")
    _seed_reservation(db, 1, suffix="cap-2")
    auth_state["role"] = "owner"
    monkeypatch.setattr("app.api.guests._GUEST_LEDGER_MAX_ROWS", 1)

    response = client.get(
        "/api/guests/ledger/export",
        params={"from_date": "2026-04-01", "to_date": "2026-04-30"},
        headers=_step_up_headers(auth_state, "/api/guests/ledger/export"),
    )

    assert response.status_code == 413
    assert "máximo de huéspedes exportables" in response.json()["detail"]
    assert "Guest cap-1" not in response.text
    assert "Guest cap-2" not in response.text
    assert db.query(SecurityAuditLog).filter_by(action="guest.ledger_csv_exported").count() == 0


def test_guest_export_neutralizes_formula_like_guest_fields(guest_export_client):
    client, db, auth_state = guest_export_client
    _seed_hotel(db, 1)
    _seed_reservation(db, 1, suffix="formula")
    guest = db.query(Guest).filter(Guest.hotel_id == 1).one()
    guest.first_name = '=HYPERLINK("https://evil.test","guest")'
    guest.last_name = "\t=1+1"
    guest.document_number = "@SUM(1,1)"
    guest.email = "+SUM(1,1)"
    db.commit()
    auth_state["role"] = "owner"

    response = client.get(
        "/api/guests/ledger/export",
        params={"from_date": "2026-04-01", "to_date": "2026-04-30"},
        headers=_step_up_headers(auth_state, "/api/guests/ledger/export"),
    )

    assert response.status_code == 200
    csv_text = response.content.decode("utf-8-sig")
    row = next(csv.DictReader(StringIO(csv_text)))
    assert row["first_name"] == "'=HYPERLINK(\"https://evil.test\",\"guest\")"
    assert row["last_name"] == "'\t=1+1"
    assert row["document_number"] == "'@SUM(1,1)"
    assert row["email"] == "'+SUM(1,1)"
    assert row["terms_accepted"] == "true"
