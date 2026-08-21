import csv
from io import StringIO
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

import app.database as db_module
import app.main as main_module
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.guest import Guest, DocumentTypeEnum
from app.models.hotel_config import HotelConfiguration
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.user import User


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch):
    """Spin up the real FastAPI app against an in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Route init_db to our ephemeral engine
    def fake_get_engine(database_url: str | None = None):
        return engine

    monkeypatch.setattr(db_module, "get_engine", fake_get_engine)
    db_module.init_db()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_auth_context():
        return AuthContext(
            hotel_id=1,
            user_id=1,
            user_email="owner@test.com",
            user_role="owner",
            is_verified=True,
            permissions=set(),
        )

    main_module.app.dependency_overrides[get_db] = override_get_db
    main_module.app.dependency_overrides[get_auth_context] = override_auth_context

    with TestClient(main_module.app) as client:
        with SessionLocal() as db:
            if not db.get(HotelConfiguration, 1):
                db.add(HotelConfiguration(id=1, owner_email="owner@test.com", subscription_active=True))
            if not db.get(User, 1):
                db.add(User(id=1, email="owner@test.com", password_hash="test-hash", is_active=True, is_verified=True))
            db.commit()
        yield client, SessionLocal

    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_rooms_crud_smoke(api_client):
    client, SessionLocal = api_client

    # Seed a category for room creation
    with SessionLocal() as db:
        cat = RoomCategory(
            hotel_id=1,
            name="Demo Standard",
            code="STD_DEMO",
            base_price_per_night=100.0,
            max_occupancy=2,
        )
        db.add(cat)
        db.commit()
        db.refresh(cat)
        category_id = cat.id

    create_resp = client.post(
        "/api/rooms/",
        json={"room_number": "101", "floor": 1, "category_id": category_id, "status": RoomStatusEnum.AVAILABLE.value},
    )
    assert create_resp.status_code == 201, create_resp.text
    room_id = create_resp.json()["id"]

    # Placeholder availability works without params
    avail = client.get("/api/rooms/availability")
    assert avail.status_code == 200
    assert avail.json()["status"] == "placeholder"

    update_resp = client.patch(f"/api/rooms/{room_id}", json={"notes": "Sea view"})
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["notes"] == "Sea view"

    delete_resp = client.delete(f"/api/rooms/{room_id}")
    assert delete_resp.status_code == 204, delete_resp.text

    list_resp = client.get("/api/rooms/")
    assert list_resp.status_code == 200
    assert list_resp.json() == []
    get_resp = client.get(f"/api/rooms/{room_id}")
    assert get_resp.status_code == 404
    with SessionLocal() as db:
        room = db.get(Room, room_id)
        assert room is not None
        assert room.deleted_at is not None


def test_guest_quick_profile_api_serializes_stays_without_relationship_recursion(api_client):
    client, SessionLocal = api_client

    with SessionLocal() as db:
        category = RoomCategory(
            hotel_id=1,
            name="Quick profile category",
            code="QPROFILE",
            base_price_per_night=100.0,
            max_occupancy=2,
        )
        guest = Guest(
            hotel_id=1,
            first_name="Profile",
            last_name="Guest",
            document_type=DocumentTypeEnum.DNI,
            document_number="QP-1",
        )
        db.add_all([category, guest])
        db.flush()
        room = Room(
            hotel_id=1,
            room_number="QP-101",
            floor=1,
            category_id=category.id,
            status=RoomStatusEnum.AVAILABLE,
        )
        db.add(room)
        db.flush()
        db.add(
            Reservation(
                confirmation_code="QP-RES-001",
                hotel_id=1,
                guest_id=guest.id,
                room_id=room.id,
                category_id=category.id,
                check_in_date=date(2026, 7, 20),
                check_out_date=date(2026, 7, 22),
                total_amount=100.0,
                amount_paid=100.0,
                status=ReservationStatusEnum.CHECKED_OUT,
            )
        )
        db.commit()
        guest_id = guest.id

    response = client.get(f"/api/guests/{guest_id}/quick-profile")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["guest"]["id"] == guest_id
    assert payload["last_stays"][0]["confirmation_code"] == "QP-RES-001"


def test_room_status_and_category_fetch(api_client):
    client, SessionLocal = api_client
    with SessionLocal() as db:
        cat = RoomCategory(
            hotel_id=1,
            name="Status Cat",
            code="STAT_CAT",
            base_price_per_night=90.0,
            max_occupancy=2,
        )
        db.add(cat)
        db.flush()
        room = Room(room_number="401", floor=4, category_id=cat.id, status=RoomStatusEnum.AVAILABLE, hotel_id=1)
        db.add(room)
        db.commit()
        db.refresh(cat)
        db.refresh(room)
        cat_id, room_id = cat.id, room.id

    cat_resp = client.get(f"/api/rooms/categories/{cat_id}")
    assert cat_resp.status_code == 200
    assert cat_resp.json()["code"] == "STAT_CAT"

    status_resp = client.patch(f"/api/rooms/{room_id}/status", json={"status": RoomStatusEnum.MAINTENANCE.value, "notes": "Deep clean"})
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["room"]["id"] == room_id
    assert body["room"]["status"] == RoomStatusEnum.MAINTENANCE.value
    assert body["room"]["notes"] == "Deep clean"
    assert "reallocation" in body

def test_bookings_basic_flow(api_client):
    client, SessionLocal = api_client
    today = date.today()
    checkout = today + timedelta(days=2)

    # Seed prerequisites
    with SessionLocal() as db:
        cat = RoomCategory(
            hotel_id=1,
            name="Suite",
            code="STE",
            base_price_per_night=200.0,
            max_occupancy=3,
        )
        guest = Guest(first_name="Test", last_name="Guest", email="guest@example.com", hotel_id=1)
        db.add_all([cat, guest])
        db.flush()
        room = Room(room_number="201", floor=2, category_id=cat.id, status=RoomStatusEnum.AVAILABLE, hotel_id=1)
        db.add(room)
        db.commit()
        db.refresh(cat)
        db.refresh(room)
        db.refresh(guest)
        payload = {
            "guest_id": guest.id,
            "category_id": cat.id,
            "room_id": room.id,
            "check_in_date": today.isoformat(),
            "check_out_date": checkout.isoformat(),
            "num_adults": 2,
        }

    # Placeholder availability
    avail = client.get("/api/bookings/availability")
    assert avail.status_code == 200
    assert avail.json()["status"] == "placeholder"

    quote = client.get(
        "/api/bookings/price-quote",
        params={
            "category_id": cat.id,
            "check_in_date": today.isoformat(),
            "check_out_date": checkout.isoformat(),
            "occupancy": 2,
        },
    )
    assert quote.status_code == 200, quote.text
    payload["quote_token"] = quote.json()["quote_token"]

    create = client.post("/api/bookings/", json=payload)
    assert create.status_code == 201, create.text
    booking_id = create.json()["id"]

    listing = client.get("/api/bookings/")
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    delete = client.delete(f"/api/bookings/{booking_id}")
    assert delete.status_code == 200
    assert delete.json()["deleted"] is True

    listing_after = client.get("/api/bookings/")
    assert listing_after.status_code == 200
    assert listing_after.json() == []
    get_after = client.get(f"/api/bookings/{booking_id}")
    assert get_after.status_code == 404
    with SessionLocal() as db:
        booking = db.get(Reservation, booking_id)
        assert booking is not None
        assert booking.deleted_at is not None


def test_booking_status_and_overlap(api_client):
    client, SessionLocal = api_client
    start = date(2026, 4, 1)
    end = start + timedelta(days=2)  # 2 nights

    with SessionLocal() as db:
        cat = RoomCategory(
            hotel_id=1,
            name="Standard API",
            code="STD_API",
            base_price_per_night=120.0,
            max_occupancy=2,
        )
        guest = Guest(
            first_name="API",
            last_name="Tester",
            email="api@test.com",
            hotel_id=1,
            document_type=DocumentTypeEnum.DNI,
            document_number="30123456",
            nationality="Argentina",
            date_of_birth=date(1992, 6, 14),
            birth_place="Buenos Aires",
            birth_country="Argentina",
            marital_status="single",
            occupation="Analista",
            terms_accepted=True,
        )
        room1 = Room(room_number="301", floor=3, category_id=1, status=RoomStatusEnum.AVAILABLE, hotel_id=1)
        room2 = Room(room_number="302", floor=3, category_id=1, status=RoomStatusEnum.AVAILABLE, hotel_id=1)
        db.add_all([cat, guest])
        db.flush()
        room1.category_id = cat.id
        room2.category_id = cat.id
        db.add_all([room1, room2])
        db.commit()
        db.refresh(cat)
        db.refresh(guest)
        db.refresh(room1)
        db.refresh(room2)
        cat_id, guest_id, room1_id, room2_id = cat.id, guest.id, room1.id, room2.id

    quote = client.get(
        "/api/bookings/price-quote",
        params={"category_id": cat_id, "check_in_date": start.isoformat(), "check_out_date": end.isoformat()},
    )
    assert quote.status_code == 200
    payload = quote.json()
    assert payload["nights"] == 2
    assert payload["total_amount"] == 240.0
    assert payload["deposit_amount"] == pytest.approx(72.0)

    base_payload = {
        "guest_id": guest_id,
        "category_id": cat_id,
        "check_in_date": start.isoformat(),
        "check_out_date": end.isoformat(),
        "num_adults": 2,
    }
    quote_token = client.get(
        "/api/bookings/price-quote",
        params={
            "category_id": cat_id,
            "check_in_date": start.isoformat(),
            "check_out_date": end.isoformat(),
            "occupancy": 2,
        },
    )
    assert quote_token.status_code == 200, quote_token.text
    base_payload["quote_token"] = quote_token.json()["quote_token"]
    create1 = client.post("/api/bookings/", json=base_payload | {"room_id": room1_id})
    assert create1.status_code == 201
    booking1_id = create1.json()["id"]
    assert create1.json()["balance_due"] == pytest.approx(240.0)

    # Overlap on same room should fail
    overlap = client.post("/api/bookings/", json=base_payload | {"room_id": room1_id})
    assert overlap.status_code == 400

    # Use second room for status flow
    create2 = client.post("/api/bookings/", json=base_payload | {"room_id": room2_id})
    assert create2.status_code == 201
    booking2_id = create2.json()["id"]

    # Cancel booking1
    cancel = client.post(f"/api/bookings/{booking1_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == ReservationStatusEnum.CANCELLED.value

    # Mark booking2 as fully paid and perform check-in/out.
    # Checkout (BR) rejects reservations with outstanding balance, so the paid
    # amount must actually cover the total — status alone is not enough.
    with SessionLocal() as db:
        res = db.query(Reservation).filter(Reservation.id == booking2_id).first()
        res.status = ReservationStatusEnum.FULLY_PAID
        res.amount_paid = res.total_amount
        db.commit()

    checkin = client.post(f"/api/bookings/{booking2_id}/checkin")
    assert checkin.status_code == 200
    assert checkin.json()["status"] == ReservationStatusEnum.CHECKED_IN.value

    checkout_resp = client.post(f"/api/bookings/{booking2_id}/checkout")
    assert checkout_resp.status_code == 200
    assert checkout_resp.json()["status"] == ReservationStatusEnum.CHECKED_OUT.value


def test_checkin_api_blocks_missing_primary_guest_fields(api_client):
    client, SessionLocal = api_client
    with SessionLocal() as db:
        guest = Guest(
            first_name="Incomplete",
            last_name="Guest",
            hotel_id=1,
            terms_accepted=False,
        )
        category = RoomCategory(
            hotel_id=1,
            name="Guest Cat",
            code="GST_CAT",
            base_price_per_night=100.0,
            max_occupancy=2,
        )
        db.add_all([guest, category])
        db.flush()
        reservation = Reservation(
            confirmation_code="CHK-REQ-001",
            hotel_id=1,
            guest_id=guest.id,
            category_id=category.id,
            check_in_date=date(2026, 4, 10),
            check_out_date=date(2026, 4, 12),
            total_amount=200.0,
            amount_paid=200.0,
            deposit_amount=60.0,
            subtotal_amount=200.0,
            tax_amount=0.0,
            fee_amount=0.0,
            commission_amount=0.0,
            net_amount=200.0,
            currency_code="ARS",
            status=ReservationStatusEnum.FULLY_PAID,
            num_adults=1,
            num_children=0,
        )
        db.add(reservation)
        db.commit()
        reservation_id = reservation.id

    resp = client.post(f"/api/checkin/{reservation_id}")
    assert resp.status_code == 400, resp.text
    assert "missing" in resp.json()["detail"].lower() or "required" in resp.json()["detail"].lower()


def _seed_ota_no_guarantee_reservation(SessionLocal) -> int:
    with SessionLocal() as db:
        guest = Guest(first_name="OTA", last_name="Guest", hotel_id=1, terms_accepted=True)
        category = RoomCategory(
            hotel_id=1,
            name="OTA Cat",
            code="OTA_CAT",
            base_price_per_night=100.0,
            max_occupancy=2,
        )
        db.add_all([guest, category])
        db.flush()
        reservation = Reservation(
            confirmation_code="OTA-REL-001",
            hotel_id=1,
            guest_id=guest.id,
            category_id=category.id,
            check_in_date=date(2026, 8, 1),
            check_out_date=date(2026, 8, 3),
            total_amount=200.0,
            amount_paid=0.0,
            deposit_amount=0.0,
            subtotal_amount=200.0,
            tax_amount=0.0,
            fee_amount=0.0,
            commission_amount=0.0,
            net_amount=200.0,
            currency_code="ARS",
            status=ReservationStatusEnum.PENDING,
            num_adults=1,
            num_children=0,
            source_provider_code="booking",
            external_id="BKG-REL-1",
            payment_collection_model="hotel_collect",
        )
        db.add(reservation)
        db.commit()
        return reservation.id


def test_release_no_guarantee_endpoint_releases_ota_reservation(api_client):
    client, SessionLocal = api_client
    reservation_id = _seed_ota_no_guarantee_reservation(SessionLocal)

    resp = client.post(f"/api/reservations/{reservation_id}/release-no-guarantee")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == ReservationStatusEnum.CANCELLED.value

    with SessionLocal() as db:
        res = db.query(Reservation).filter(Reservation.id == reservation_id).first()
        assert res.allocation_status == "internally_released"
        assert res.settlement_status == "internal_release_no_guarantee"


def test_add_reservation_guests_enforces_category_capacity(api_client):
    client, SessionLocal = api_client

    with SessionLocal() as db:
        primary_guest = Guest(
            first_name="Primary",
            last_name="Guest",
            document_type=DocumentTypeEnum.DNI,
            document_number="CAP-PRIMARY",
            hotel_id=1,
        )
        category = RoomCategory(
            hotel_id=1,
            name="Capacity Cat",
            code="CAP_CAT",
            base_price_per_night=100.0,
            max_occupancy=2,
        )
        db.add_all([primary_guest, category])
        db.flush()
        reservation = Reservation(
            confirmation_code="CAP-ADD-001",
            hotel_id=1,
            guest_id=primary_guest.id,
            category_id=category.id,
            check_in_date=date(2027, 4, 10),
            check_out_date=date(2027, 4, 12),
            total_amount=200.0,
            amount_paid=0.0,
            deposit_amount=60.0,
            subtotal_amount=200.0,
            tax_amount=0.0,
            fee_amount=0.0,
            commission_amount=0.0,
            net_amount=200.0,
            currency_code="ARS",
            status=ReservationStatusEnum.PENDING,
            num_adults=1,
            num_children=0,
        )
        db.add(reservation)
        db.commit()
        reservation_id = reservation.id

    up_to_capacity = client.post(
        f"/api/reservations/{reservation_id}/guests",
        json=[
            {
                "first_name": "Allowed",
                "last_name": "Guest",
                "document_type": DocumentTypeEnum.DNI.value,
                "document_number": "CAP-ALLOWED",
            }
        ],
    )
    assert up_to_capacity.status_code == 200, up_to_capacity.text
    assert len(up_to_capacity.json()["additional_guests"]) == 1

    exceeding = client.post(
        f"/api/reservations/{reservation_id}/guests",
        json=[
            {
                "first_name": "Extra",
                "last_name": "Guest",
                "document_type": DocumentTypeEnum.DNI.value,
                "document_number": "CAP-EXTRA",
            }
        ],
    )
    assert exceeding.status_code == 400
    assert "capacity" in exceeding.json()["detail"].lower()

    with SessionLocal() as db:
        reservation = db.get(Reservation, reservation_id)
        assert len(reservation.additional_guests) == 1


def test_add_reservation_guests_bulk_loads_existing_documents(api_client):
    client, SessionLocal = api_client

    with SessionLocal() as db:
        primary_guest = Guest(
            first_name="Primary",
            last_name="Guest",
            document_type=DocumentTypeEnum.DNI,
            document_number="TECH63-PRIMARY",
            hotel_id=1,
        )
        category = RoomCategory(
            hotel_id=1,
            name="TECH63 Category",
            code="TECH63",
            base_price_per_night=100.0,
            max_occupancy=4,
        )
        existing_guests = [
            Guest(
                first_name=f"Existing {index}",
                last_name="Guest",
                document_type=DocumentTypeEnum.DNI,
                document_number=f"TECH63-{index}",
                hotel_id=1,
            )
            for index in range(1, 4)
        ]
        payloads = [
            {
                "first_name": f"Existing {index}",
                "last_name": "Guest",
                "document_type": DocumentTypeEnum.DNI.value,
                "document_number": f"TECH63-{index}",
            }
            for index in range(1, 4)
        ]
        db.add_all([primary_guest, category, *existing_guests])
        db.flush()
        reservation = Reservation(
            confirmation_code="TECH63-RES-001",
            hotel_id=1,
            guest_id=primary_guest.id,
            category_id=category.id,
            check_in_date=date.today() + timedelta(days=1),
            check_out_date=date.today() + timedelta(days=3),
            total_amount=400.0,
            amount_paid=0.0,
            deposit_amount=0.0,
            subtotal_amount=400.0,
            tax_amount=0.0,
            fee_amount=0.0,
            commission_amount=0.0,
            net_amount=400.0,
            currency_code="ARS",
            status=ReservationStatusEnum.PENDING,
            num_adults=1,
        )
        db.add(reservation)
        db.commit()
        reservation_id = reservation.id
        engine = db.get_bind()

    statements: list[str] = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        response = client.post(f"/api/reservations/{reservation_id}/guests", json=payloads)
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)

    assert response.status_code == 200, response.text
    assert {guest["document_number"] for guest in response.json()["additional_guests"]} == {
        "TECH63-1",
        "TECH63-2",
        "TECH63-3",
    }
    bulk_document_selects = [
        statement
        for statement in statements
        if "from guests" in statement.lower()
        and (
            "guests.document_number in (" in statement.lower()
            or "trim(guests.document_number) in (" in statement.lower()
        )
    ]
    assert len(bulk_document_selects) == 1, (
        "existing guests should be loaded with one document-number IN query"
    )


def test_add_reservation_guests_matches_existing_document_despite_whitespace(api_client):
    """A legacy row with untrimmed whitespace must still be found by the
    bulk lookup, and a freshly created row must store the trimmed value --
    otherwise the lookup miss falls through to an insert of the exact same
    raw value and collides with uq_guest_document_per_hotel."""
    client, SessionLocal = api_client

    with SessionLocal() as db:
        primary_guest = Guest(
            first_name="Primary",
            last_name="Guest",
            document_type=DocumentTypeEnum.DNI,
            document_number="TECH63-WS-PRIMARY",
            hotel_id=1,
        )
        category = RoomCategory(
            hotel_id=1,
            name="TECH63 WS Category",
            code="TECH63WS",
            base_price_per_night=100.0,
            max_occupancy=4,
        )
        # Simulate a legacy row stored with raw whitespace before this
        # endpoint normalized values.
        existing_guest = Guest(
            first_name="Existing",
            last_name="WithSpace",
            document_type=DocumentTypeEnum.DNI,
            document_number="  TECH63-WS-1  ",
            hotel_id=1,
        )
        db.add_all([primary_guest, category, existing_guest])
        db.flush()
        reservation = Reservation(
            confirmation_code="TECH63-WS-RES-001",
            hotel_id=1,
            guest_id=primary_guest.id,
            category_id=category.id,
            check_in_date=date.today() + timedelta(days=1),
            check_out_date=date.today() + timedelta(days=3),
            total_amount=400.0,
            amount_paid=0.0,
            deposit_amount=0.0,
            subtotal_amount=400.0,
            tax_amount=0.0,
            fee_amount=0.0,
            commission_amount=0.0,
            net_amount=400.0,
            currency_code="ARS",
            status=ReservationStatusEnum.PENDING,
            num_adults=1,
        )
        db.add(reservation)
        db.commit()
        reservation_id = reservation.id
        existing_guest_id = existing_guest.id

    response = client.post(
        f"/api/reservations/{reservation_id}/guests",
        json=[
            {
                "first_name": "Existing",
                "last_name": "WithSpace",
                "document_type": DocumentTypeEnum.DNI.value,
                "document_number": "TECH63-WS-1",
            }
        ],
    )

    assert response.status_code == 200, response.text
    additional_guests = response.json()["additional_guests"]
    assert len(additional_guests) == 1
    assert additional_guests[0]["id"] == existing_guest_id

    with SessionLocal() as db:
        assert db.query(Guest).filter(Guest.hotel_id == 1, Guest.first_name == "Existing").count() == 1


def test_release_no_guarantee_endpoint_forbidden_for_unauthorized_role(api_client):
    client, SessionLocal = api_client
    reservation_id = _seed_ota_no_guarantee_reservation(SessionLocal)

    def receptionist_auth_context():
        return AuthContext(
            hotel_id=1,
            user_id=2,
            user_email="recep@test.com",
            user_role="receptionist",
            is_verified=True,
            permissions=set(),
        )

    main_module.app.dependency_overrides[get_auth_context] = receptionist_auth_context
    try:
        resp = client.post(f"/api/reservations/{reservation_id}/release-no-guarantee")
        assert resp.status_code == 403, resp.text
    finally:
        main_module.app.dependency_overrides[get_auth_context] = override_auth_context_owner


def override_auth_context_owner():
    return AuthContext(
        hotel_id=1,
        user_id=1,
        user_email="owner@test.com",
        user_role="owner",
        is_verified=True,
        permissions=set(),
    )


def test_guest_ledger_export_returns_csv_for_date_range(api_client):
    client, SessionLocal = api_client
    with SessionLocal() as db:
        guest_in_range = Guest(
            first_name="Ana",
            last_name="Lopez",
            document_type=DocumentTypeEnum.PASSPORT,
            document_number="P1234567",
            nationality="Argentina",
            date_of_birth=date(1990, 1, 2),
            country="Argentina",
            phone="+54911111111",
            email="ana@example.com",
            terms_accepted=True,
            hotel_id=1,
        )
        guest_outside_range = Guest(
            first_name="Bruno",
            last_name="Perez",
            document_type=DocumentTypeEnum.DNI,
            document_number="30112233",
            nationality="Argentina",
            date_of_birth=date(1988, 5, 15),
            terms_accepted=True,
            hotel_id=1,
        )
        category = RoomCategory(
            hotel_id=1,
            name="Ledger Cat",
            code="LEDGER_CAT",
            base_price_per_night=110.0,
            max_occupancy=2,
        )
        db.add_all([guest_in_range, guest_outside_range, category])
        db.flush()
        db.add_all(
            [
                Reservation(
                    confirmation_code="LEDGER-001",
                    hotel_id=1,
                    guest_id=guest_in_range.id,
                    category_id=category.id,
                    check_in_date=date(2026, 4, 10),
                    check_out_date=date(2026, 4, 12),
                    total_amount=220.0,
                    amount_paid=220.0,
                    deposit_amount=66.0,
                    subtotal_amount=220.0,
                    tax_amount=0.0,
                    fee_amount=0.0,
                    commission_amount=0.0,
                    net_amount=220.0,
                    currency_code="ARS",
                    status=ReservationStatusEnum.CHECKED_IN,
                    num_adults=1,
                    num_children=0,
                ),
                Reservation(
                    confirmation_code="LEDGER-002",
                    hotel_id=1,
                    guest_id=guest_outside_range.id,
                    category_id=category.id,
                    check_in_date=date(2026, 5, 1),
                    check_out_date=date(2026, 5, 3),
                    total_amount=220.0,
                    amount_paid=220.0,
                    deposit_amount=66.0,
                    subtotal_amount=220.0,
                    tax_amount=0.0,
                    fee_amount=0.0,
                    commission_amount=0.0,
                    net_amount=220.0,
                    currency_code="ARS",
                    status=ReservationStatusEnum.CHECKED_IN,
                    num_adults=1,
                    num_children=0,
                ),
            ]
        )
        db.commit()

    resp = client.get(
        "/api/guests/ledger/export",
        params={"from_date": "2026-04-01", "to_date": "2026-04-30"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert resp.headers["content-disposition"] == 'attachment; filename="guest-ledger-1-2026-04-01-2026-04-30.csv"'

    csv_text = resp.content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(csv_text))
    rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    assert row["first_name"] == "Ana"
    assert row["last_name"] == "Lopez"
    assert row["document_type"] == DocumentTypeEnum.PASSPORT.value
    assert row["document_number"] == "P1234567"
    assert row["nationality"] == "Argentina"
    assert row["date_of_birth"] == "1990-01-02"
    assert row["arrival_date"] == "2026-04-10"
    assert row["departure_date"] == "2026-04-12"
    assert row["terms_accepted"] == "true"
