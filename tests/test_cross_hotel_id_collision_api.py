"""
Fase 12 — cross-hotel ID-collision regression suite (security-auditor).

Reservation/guest/room/stock/payment IDs are a single autoincrement sequence
shared by every hotel on the platform (composite ``(hotel_id, id)`` unique
constraints exist for FK integrity, not to give each hotel its own id space).
That means a real attacker never needs literally identical numbers in two
hotels: they only need to enumerate the *shared* id space (id, id+1, id-1...)
against their own bearer token/hotel context. This suite creates Hotel B data
first, then Hotel A data, so Hotel A's authenticated user is guaranteed a set
of *real, existing* Hotel B ids to probe by direct id — and asserts every
read/write path returns 403/404, never 200 with foreign-hotel data.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (register all mappers before create_all)
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.cash_register import CashSession, CashSessionStatusEnum
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.payment import PaymentLink
from app.models.payment_proof import PaymentProof, PaymentProofBlob
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory
from app.models.stock import StockItem, StockLocation
from app.models.user import User

HOTEL_A = 9101
HOTEL_B = 9102


@pytest.fixture
def two_hotel_client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    db.add_all(
        [
            HotelConfiguration(id=HOTEL_A, hotel_name="Hotel A", subscription_active=True),
            HotelConfiguration(id=HOTEL_B, hotel_name="Hotel B", subscription_active=True),
            User(id=HOTEL_A, email="owner-a@test.com", password_hash="x", is_active=True, is_verified=True),
            User(id=HOTEL_B, email="owner-b@test.com", password_hash="x", is_active=True, is_verified=True),
        ]
    )
    db.flush()

    def _seed_room_stack(hotel_id: int, tag: str) -> tuple[RoomCategory, Room]:
        cat = RoomCategory(hotel_id=hotel_id, name=f"Std {tag}", code=f"STD-{tag}", base_price_per_night=100, max_occupancy=2)
        db.add(cat)
        db.flush()
        room = Room(hotel_id=hotel_id, category_id=cat.id, room_number=f"{tag}-101", floor=1)
        db.add(room)
        db.flush()
        return cat, room

    def _seed_reservation(hotel_id: int, cat: RoomCategory, tag: str) -> Reservation:
        guest = Guest(hotel_id=hotel_id, first_name="Ana", last_name=tag, terms_accepted=True)
        db.add(guest)
        db.flush()
        res = Reservation(
            confirmation_code=f"RES-{tag}",
            hotel_id=hotel_id,
            guest_id=guest.id,
            category_id=cat.id,
            check_in_date=date(2026, 8, 1),
            check_out_date=date(2026, 8, 3),
            total_amount=200,
            amount_paid=0,
            deposit_amount=0,
            source=ReservationSourceEnum.DIRECT,
            status=ReservationStatusEnum.PENDING,
        )
        db.add(res)
        db.flush()
        return res, guest

    # ── Seed Hotel B FIRST so its ids land below Hotel A's in the shared
    # autoincrement sequence — this is what real cross-hotel id guessing
    # looks like (Hotel A can trivially probe smaller/adjacent ids).
    cat_b, room_b = _seed_room_stack(HOTEL_B, "B")
    res_b, guest_b = _seed_reservation(HOTEL_B, cat_b, "B")
    stock_item_b = StockItem(hotel_id=HOTEL_B, name="Toallas B", unit="unidad")
    stock_location_b = StockLocation(hotel_id=HOTEL_B, name="Deposito B")
    db.add_all([stock_item_b, stock_location_b])
    cash_b = CashSession(
        hotel_id=HOTEL_B, status=CashSessionStatusEnum.OPEN, opening_balance=0,
        currency_code="ARS", opened_at=datetime.now(timezone.utc),
    )
    db.add(cash_b)
    link_b = PaymentLink(
        hotel_id=HOTEL_B, reservation_id=res_b.id, link_code="LINK-B",
        requested_amount=Decimal("100.00"), recipient_email="guest-b@test.com",
    )
    db.add(link_b)
    proof_b = PaymentProof(
        hotel_id=HOTEL_B, reservation_id=res_b.id, amount=Decimal("50.00"),
        currency="ARS", payment_method="bank_transfer", status="pending",
        storage_key="proof-b-key", content_type="image/png", file_size_bytes=4,
        sha256_hex="b" * 64,
    )
    db.add(proof_b)
    db.flush()
    proof_blob_b = PaymentProofBlob(
        hotel_id=HOTEL_B, proof_id=proof_b.id, content=b"png-bytes",
        content_type="image/png", sha256_hex="b" * 64,
    )
    db.add(proof_blob_b)

    # ── Now seed Hotel A's own data (its ids will differ but that's not the
    # point — Hotel A's *token* is what we test against Hotel B's real ids).
    cat_a, room_a = _seed_room_stack(HOTEL_A, "A")
    res_a, guest_a = _seed_reservation(HOTEL_A, cat_a, "A")

    db.commit()

    ids = {
        "category_b": cat_b.id, "room_b": room_b.id, "reservation_b": res_b.id,
        "guest_b": guest_b.id, "stock_item_b": stock_item_b.id,
        "stock_location_b": stock_location_b.id, "cash_session_b": cash_b.id,
        "payment_link_b": link_b.id, "payment_proof_b": proof_b.id,
        "category_a": cat_a.id, "reservation_a": res_a.id,
    }

    auth_state = {"hotel_id": HOTEL_A, "role": "owner", "user_id": HOTEL_A}

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_auth():
        return AuthContext(
            hotel_id=auth_state["hotel_id"],
            user_id=auth_state["user_id"],
            user_email=f"user-{auth_state['hotel_id']}@test.com",
            user_role=auth_state["role"],
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    client = TestClient(fastapi_app)
    try:
        yield client, ids
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


# ── Hotel A (the attacker's own valid session) probing real Hotel B ids ────


def test_reservation_read_denied_across_hotels(two_hotel_client):
    client, ids = two_hotel_client
    resp = client.get(f"/api/reservations/{ids['reservation_b']}")
    assert resp.status_code in (403, 404), resp.text
    assert "RES-B" not in resp.text


def test_reservation_financial_summary_denied_across_hotels(two_hotel_client):
    client, ids = two_hotel_client
    resp = client.get(f"/api/payments/summary/{ids['reservation_b']}")
    assert resp.status_code in (400, 403, 404), resp.text


def test_guest_read_denied_across_hotels(two_hotel_client):
    client, ids = two_hotel_client
    resp = client.get(f"/api/guests/{ids['guest_b']}")
    assert resp.status_code == 404, resp.text


def test_room_read_denied_across_hotels(two_hotel_client):
    client, ids = two_hotel_client
    resp = client.get(f"/api/rooms/{ids['room_b']}")
    assert resp.status_code == 404, resp.text


def test_room_category_read_denied_across_hotels(two_hotel_client):
    client, ids = two_hotel_client
    resp = client.get(f"/api/rooms/categories/{ids['category_b']}")
    assert resp.status_code == 404, resp.text


def test_room_write_denied_across_hotels(two_hotel_client):
    client, ids = two_hotel_client
    resp = client.patch(f"/api/rooms/{ids['room_b']}", json={"floor": 9})
    assert resp.status_code == 404, resp.text


def test_stock_item_read_denied_across_hotels(two_hotel_client):
    client, ids = two_hotel_client
    resp = client.get(f"/api/stock/items/{ids['stock_item_b']}")
    assert resp.status_code == 404, resp.text


def test_stock_item_write_denied_across_hotels(two_hotel_client):
    client, ids = two_hotel_client
    resp = client.patch(f"/api/stock/items/{ids['stock_item_b']}", json={"name": "hijacked"})
    assert resp.status_code == 404, resp.text


def test_stock_location_read_denied_across_hotels(two_hotel_client):
    client, ids = two_hotel_client
    resp = client.get(f"/api/stock/locations/{ids['stock_location_b']}")
    assert resp.status_code == 404, resp.text


def test_cash_session_movement_denied_across_hotels(two_hotel_client):
    client, ids = two_hotel_client
    resp = client.post(
        f"/api/cash-register/sessions/{ids['cash_session_b']}/movements",
        json={"movement_type": "income", "amount": "1.00"},
    )
    assert resp.status_code in (400, 403, 404), resp.text


def test_payment_link_cancel_denied_across_hotels(two_hotel_client):
    client, ids = two_hotel_client
    resp = client.post(f"/api/payment-links/{ids['payment_link_b']}/cancel", json={})
    assert resp.status_code in (400, 403, 404), resp.text


def test_payment_proof_image_denied_across_hotels(two_hotel_client):
    client, ids = two_hotel_client
    resp = client.get(f"/api/payment-proofs/{ids['payment_proof_b']}/image")
    assert resp.status_code == 404, resp.text
    assert resp.content != b"png-bytes"


def test_payment_proof_approve_denied_across_hotels(two_hotel_client):
    client, ids = two_hotel_client
    resp = client.post(f"/api/payment-proofs/{ids['payment_proof_b']}/approve")
    assert resp.status_code in (400, 403, 404), resp.text


def test_daily_rate_category_write_denied_across_hotels(two_hotel_client):
    client, ids = two_hotel_client
    resp = client.post(
        f"/api/rates/category/{ids['category_b']}/daily",
        json={"date": "2026-09-01", "price": 999},
    )
    assert resp.status_code == 404, resp.text
