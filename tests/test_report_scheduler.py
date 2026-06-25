"""
R6b: scheduled report tasks (§15.1) + manual-review routing (§13.3).

No real emails are ever sent: ``send_hotel_email`` is monkeypatched everywhere.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum


@pytest.fixture
def db_session():
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

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _make_hotel(db, hotel_id: int, *, active: bool = True, owner_email: str | None = None) -> HotelConfiguration:
    hotel = HotelConfiguration(
        id=hotel_id,
        hotel_name=f"Hotel {hotel_id}",
        subscription_active=active,
        owner_email=owner_email or f"owner{hotel_id}@test.com",
    )
    db.add(hotel)
    db.flush()
    return hotel


def _make_reservation(db, hotel_id: int, *, check_in: date, check_out: date) -> Reservation:
    category = RoomCategory(
        hotel_id=hotel_id,
        name="Standard",
        code=f"STD{hotel_id}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    room = Room(
        hotel_id=hotel_id,
        category_id=category.id,
        room_number="101",
        floor=1,
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add(room)
    db.flush()
    guest = Guest(
        hotel_id=hotel_id,
        first_name="Rev",
        last_name="Guest",
        document_number=f"DOC{hotel_id}",
        terms_accepted=True,
    )
    db.add(guest)
    db.flush()
    reservation = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        confirmation_code=f"REV-{hotel_id}",
        check_in_date=check_in,
        check_out_date=check_out,
        total_amount=Decimal("200.00"),
        amount_paid=Decimal("0.00"),
        status=ReservationStatusEnum.PENDING,
        num_adults=1,
        requires_manual_review=True,
        allocation_status="manual_review",
    )
    db.add(reservation)
    db.flush()
    return reservation


# ── ÍTEM A: §15.1 scheduler tasks ──────────────────────────────────────────

def test_send_morning_reports_iterates_active_hotels(db_session, monkeypatch):
    _make_hotel(db_session, 1)
    _make_hotel(db_session, 2)
    _make_hotel(db_session, 3, active=False)  # inactive: must be skipped
    db_session.commit()

    calls: list[int] = []

    def fake_send(db, hotel_id, *, to, subject, body):
        calls.append(hotel_id)

        class _R:
            channel = "gmail_hotel"
            sender_email = "x@test.com"
            provider_message_id = "mid"

        return _R()

    monkeypatch.setattr(
        "app.services.hotel_outbound_email_service.send_hotel_email", fake_send
    )
    # The task opens its own session; point it at our in-memory one.
    import app.tasks.report_tasks as rt
    monkeypatch.setattr(rt, "get_engine", lambda url: None)
    monkeypatch.setattr(rt, "sessionmaker", lambda **_: (lambda: db_session))

    result = rt._run_scheduled_reports("morning", report_date=date(2026, 6, 25))

    assert sorted(calls) == [1, 2]  # active hotels only, per-hotel
    assert result["sent"] == 2
    assert result["hotels"] == 2


def test_one_hotel_failure_does_not_abort_the_rest(db_session, monkeypatch):
    _make_hotel(db_session, 1)
    _make_hotel(db_session, 2)
    db_session.commit()

    from app.services.hotel_outbound_email_service import HotelOutboundEmailError

    seen: list[int] = []

    def fake_send(db, hotel_id, *, to, subject, body):
        seen.append(hotel_id)
        if hotel_id == 1:
            raise HotelOutboundEmailError("gmail not connected")

        class _R:
            channel = "gmail_hotel"
            sender_email = "x@test.com"
            provider_message_id = "mid"

        return _R()

    monkeypatch.setattr(
        "app.services.hotel_outbound_email_service.send_hotel_email", fake_send
    )
    import app.tasks.report_tasks as rt
    monkeypatch.setattr(rt, "get_engine", lambda url: None)
    monkeypatch.setattr(rt, "sessionmaker", lambda **_: (lambda: db_session))

    result = rt._run_scheduled_reports("nightly", report_date=date(2026, 6, 25))

    assert sorted(seen) == [1, 2]  # hotel 2 still attempted after hotel 1 failed
    assert result["sent"] == 1
    assert result["failed"] == 1


# ── ÍTEM B: §13.3 manual-review routing ────────────────────────────────────

def test_review_for_today_triggers_immediate_alert(db_session, monkeypatch):
    _make_hotel(db_session, 1)
    today = date(2026, 6, 25)
    reservation = _make_reservation(
        db_session, 1, check_in=today, check_out=date(2026, 6, 27)
    )
    db_session.commit()

    sent: list[dict] = []

    def fake_send(db, hotel_id, *, to, subject, body):
        sent.append({"hotel_id": hotel_id, "to": list(to), "subject": subject})

        class _R:
            channel = "gmail_hotel"
            sender_email = "x@test.com"
            provider_message_id = "mid"

        return _R()

    monkeypatch.setattr(
        "app.services.hotel_outbound_email_service.send_hotel_email", fake_send
    )

    from app.services.operational_report_service import route_manual_review

    dispatched = route_manual_review(db_session, reservation, today=today)

    assert dispatched is True
    assert len(sent) == 1
    assert sent[0]["hotel_id"] == 1
    assert "owner1@test.com" in sent[0]["to"]  # per-hotel owner fallback


def test_review_for_future_does_not_trigger_immediate_alert(db_session, monkeypatch):
    _make_hotel(db_session, 1)
    today = date(2026, 6, 25)
    reservation = _make_reservation(
        db_session, 1, check_in=date(2026, 7, 10), check_out=date(2026, 7, 12)
    )
    db_session.commit()

    sent: list[int] = []

    def fake_send(db, hotel_id, *, to, subject, body):
        sent.append(hotel_id)

    monkeypatch.setattr(
        "app.services.hotel_outbound_email_service.send_hotel_email", fake_send
    )

    from app.services.operational_report_service import route_manual_review

    dispatched = route_manual_review(db_session, reservation, today=today)

    assert dispatched is False
    assert sent == []  # future review waits for the morning report


def test_review_routing_swallows_email_errors(db_session, monkeypatch):
    _make_hotel(db_session, 1)
    today = date(2026, 6, 25)
    reservation = _make_reservation(
        db_session, 1, check_in=today, check_out=date(2026, 6, 27)
    )
    db_session.commit()

    from app.services.hotel_outbound_email_service import HotelOutboundEmailError

    def fake_send(db, hotel_id, *, to, subject, body):
        raise HotelOutboundEmailError("boom")

    monkeypatch.setattr(
        "app.services.hotel_outbound_email_service.send_hotel_email", fake_send
    )

    from app.services.operational_report_service import route_manual_review

    # Must not raise even though delivery failed.
    assert route_manual_review(db_session, reservation, today=today) is False
