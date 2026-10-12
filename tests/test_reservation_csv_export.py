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

from app.api import reservations as reservations_api
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.security_audit_log import SecurityAuditLog
from app.services.permission_service import resolve
from app.services.action_step_up_service import create_action_step_up_ticket


@pytest.fixture
def reservation_export_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    auth_state = {"hotel_id": 1, "role": "manager", "user_id": 10}

    app = FastAPI()
    app.include_router(reservations_api.router)

    def override_get_db():
        yield db

    def override_auth_context():
        return AuthContext(
            hotel_id=auth_state["hotel_id"],
            user_id=auth_state["user_id"],
            user_email="reservation-export@example.test",
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
    engine.dispose()


def _seed_hotel(db, hotel_id: int, *, first_name: str = "Ana"):
    hotel = HotelConfiguration(
        id=hotel_id,
        hotel_name=f"Reservation export {hotel_id}",
        subscription_active=True,
    )
    guest = Guest(
        hotel_id=hotel_id,
        first_name=first_name,
        last_name="Export",
        document_number=f"PRIVATE-DOCUMENT-{hotel_id}",
        email=f"private-{hotel_id}@example.test",
        phone=f"PRIVATE-PHONE-{hotel_id}",
    )
    category = RoomCategory(
        hotel_id=hotel_id,
        name="Standard",
        code=f"STD-{hotel_id}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=3,
    )
    db.add_all([hotel, guest, category])
    db.flush()
    room = Room(
        hotel_id=hotel_id,
        category_id=category.id,
        room_number=f"10{hotel_id}",
        floor=1,
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add(room)
    db.flush()
    return guest, category, room


def _add_reservation(
    db,
    *,
    hotel_id: int,
    guest_id: int,
    category_id: int,
    room_id: int,
    confirmation_code: str,
    check_in: date,
    check_out: date,
):
    reservation = Reservation(
        hotel_id=hotel_id,
        guest_id=guest_id,
        category_id=category_id,
        room_id=room_id,
        confirmation_code=confirmation_code,
        check_in_date=check_in,
        check_out_date=check_out,
        status=ReservationStatusEnum.PENDING,
        total_amount=Decimal("200.00"),
        amount_paid=Decimal("0.00"),
        currency_code="ARS",
        num_adults=2,
        num_children=1,
        source=ReservationSourceEnum.DIRECT,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _rows(response):
    return list(csv.DictReader(StringIO(response.content.decode("utf-8-sig")), delimiter=";"))


def _step_up_headers(auth_state) -> dict[str, str]:
    path = "/api/reservations/export.csv"
    return {
        "X-Action-Step-Up-Ticket": create_action_step_up_ticket(
            user_id=auth_state["user_id"],
            hotel_id=auth_state["hotel_id"],
            token_version=0,
            permission_code="reservation:export",
            method="GET",
            path=path,
        )
    }


def test_reservation_export_requires_dedicated_permission(reservation_export_client):
    client, db, auth_state = reservation_export_client
    _seed_hotel(db, 1)
    _add_reservation(
        db,
        hotel_id=1,
        guest_id=1,
        category_id=1,
        room_id=1,
        confirmation_code="DENIED-1",
        check_in=date(2026, 4, 10),
        check_out=date(2026, 4, 12),
    )
    db.commit()
    auth_state["role"] = "receptionist"

    response = client.get(
        "/api/reservations/export.csv",
        params={"start_date": "2026-04-01", "end_date": "2026-04-30"},
    )

    assert response.status_code == 403
    assert response.headers.get("content-type", "").startswith("application/json")
    assert "DENIED-1" not in response.text


def test_reservation_export_uses_inclusive_occupancy_dates_and_hotel_scope(reservation_export_client):
    client, db, auth_state = reservation_export_client
    guest, category, room = _seed_hotel(db, 1, first_name="Sensitive name")
    _add_reservation(
        db,
        hotel_id=1,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        confirmation_code="START-DAY",
        check_in=date(2026, 4, 10),
        check_out=date(2026, 4, 11),
    )
    _add_reservation(
        db,
        hotel_id=1,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        confirmation_code="ENDS-ON-END",
        check_in=date(2026, 4, 11),
        check_out=date(2026, 4, 12),
    )
    _add_reservation(
        db,
        hotel_id=1,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        confirmation_code="STARTS-ON-END",
        check_in=date(2026, 4, 12),
        check_out=date(2026, 4, 13),
    )
    _add_reservation(
        db,
        hotel_id=1,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        confirmation_code="CHECKOUT-AT-START",
        check_in=date(2026, 4, 9),
        check_out=date(2026, 4, 10),
    )
    _add_reservation(
        db,
        hotel_id=1,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        confirmation_code="AFTER-END",
        check_in=date(2026, 4, 13),
        check_out=date(2026, 4, 14),
    )
    other_guest, other_category, other_room = _seed_hotel(db, 2, first_name="Other tenant")
    _add_reservation(
        db,
        hotel_id=2,
        guest_id=other_guest.id,
        category_id=other_category.id,
        room_id=other_room.id,
        confirmation_code="OTHER-HOTEL",
        check_in=date(2026, 4, 10),
        check_out=date(2026, 4, 12),
    )
    db.commit()

    response = client.get(
        "/api/reservations/export.csv",
        params={"start_date": "2026-04-10", "end_date": "2026-04-12"},
        headers=_step_up_headers(auth_state),
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["content-disposition"] == (
        'attachment; filename="reservas-2026-04-10-2026-04-12.csv"'
    )
    rows = _rows(response)
    assert {row["codigo_reserva"] for row in rows} == {
        "START-DAY",
        "ENDS-ON-END",
        "STARTS-ON-END",
    }
    assert "OTHER-HOTEL" not in response.text
    assert "PRIVATE-DOCUMENT-1" not in response.text
    assert "private-1@example.test" not in response.text
    assert "PRIVATE-PHONE-1" not in response.text
    assert set(rows[0]) == {
        "codigo_reserva",
        "huesped",
        "estado",
        "check_in",
        "check_out",
        "noches",
        "habitacion",
        "categoria",
        "adultos",
        "menores",
        "total",
        "moneda",
        "origen",
    }
    assert rows[0]["huesped"] == "Sensitive name Export"
    assert rows[0]["check_in"] == "2026-04-10"
    assert rows[0]["check_out"] == "2026-04-11"
    assert rows[0]["noches"] == "1"

    export_event = (
        db.query(SecurityAuditLog)
        .filter_by(hotel_id=1, action="reservation.csv_exported")
        .one()
    )
    details = json.loads(export_event.details or "{}")
    assert details == {
        "start_date": "2026-04-10",
        "end_date": "2026-04-12",
        "row_count": 3,
    }
    assert "Sensitive name" not in export_event.details
    assert "PRIVATE-DOCUMENT" not in export_event.details
    assert "private-1@example.test" not in export_event.details
    assert export_event.resource_id is None


def test_reservation_export_neutralizes_formula_like_text(reservation_export_client):
    client, db, auth_state = reservation_export_client
    guest, category, room = _seed_hotel(
        db,
        1,
        first_name='=HYPERLINK("https://evil.test","guest")',
    )
    _add_reservation(
        db,
        hotel_id=1,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        confirmation_code='=HYPERLINK("https://evil.test","reservation")',
        check_in=date(2026, 4, 10),
        check_out=date(2026, 4, 12),
    )
    db.commit()

    response = client.get(
        "/api/reservations/export.csv",
        params={"start_date": "2026-04-10", "end_date": "2026-04-10"},
        headers=_step_up_headers(auth_state),
    )

    assert response.status_code == 200, response.text
    row = _rows(response)[0]
    assert row["codigo_reserva"].startswith("'=HYPERLINK(")
    assert row["huesped"].startswith("'=HYPERLINK(")


def test_reservation_export_rejects_invalid_and_overlong_date_ranges(reservation_export_client):
    client, db, auth_state = reservation_export_client
    _seed_hotel(db, 1)
    db.commit()

    missing_dates = client.get("/api/reservations/export.csv", headers=_step_up_headers(auth_state))
    assert missing_dates.status_code == 422

    invalid_range = client.get(
        "/api/reservations/export.csv",
        params={"start_date": "2026-04-11", "end_date": "2026-04-10"},
        headers=_step_up_headers(auth_state),
    )
    assert invalid_range.status_code == 422

    overlong_range = client.get(
        "/api/reservations/export.csv",
        params={"start_date": "2026-01-01", "end_date": "2027-01-03"},
        headers=_step_up_headers(auth_state),
    )
    assert overlong_range.status_code == 422


def test_reservation_export_rejects_results_over_cap_without_truncating(
    reservation_export_client,
    monkeypatch,
):
    client, db, auth_state = reservation_export_client
    guest, category, room = _seed_hotel(db, 1)
    for index in range(3):
        _add_reservation(
            db,
            hotel_id=1,
            guest_id=guest.id,
            category_id=category.id,
            room_id=room.id,
            confirmation_code=f"CAP-{index}",
            check_in=date(2026, 4, 10),
            check_out=date(2026, 4, 12),
        )
    db.commit()
    monkeypatch.setattr(reservations_api, "_RESERVATION_CSV_MAX_ROWS", 2)

    response = client.get(
        "/api/reservations/export.csv",
        params={"start_date": "2026-04-10", "end_date": "2026-04-12"},
        headers=_step_up_headers(auth_state),
    )

    assert response.status_code == 413
    assert "máximo de reservas exportables" in response.json()["detail"]
    assert "CAP-0" not in response.text
    assert db.query(SecurityAuditLog).filter_by(action="reservation.csv_exported").count() == 0


def test_reservation_export_permission_catalog_and_default_roles():
    from app.services.permission_service import _CANONICAL_DEFINITIONS

    assert "reservation:export" in _CANONICAL_DEFINITIONS
    assert _CANONICAL_DEFINITIONS["reservation:export"][0] == "reservations"

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(HotelConfiguration(id=1, hotel_name="Permission catalog"))
        db.commit()
        assert resolve(db, 1, "owner", "reservation:export") is True
        assert resolve(db, 1, "co_owner", "reservation:export") is True
        assert resolve(db, 1, "manager", "reservation:export") is True
        assert resolve(db, 1, "receptionist", "reservation:export") is False
    finally:
        db.close()
        engine.dispose()
