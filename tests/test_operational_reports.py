from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.api import reports as reports_api
from app.models.cash_register import CashSession, CashSessionStatusEnum
from app.models.company import Company
from app.models.company_night_charge import CompanyNightCharge
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.operations import BillingAdjustment, BillingAdjustmentTypeEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.room_block import RoomBlock, RoomBlockReasonEnum
from app.models.user import User
from app.services.financial_ledger import billing_adjustment_totals_by_reservation
from app.services.operational_report_service import _daily_report_balance_candidate_query, daily_report


@pytest.fixture
def reports_client():
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
    db.add_all(
        [
            HotelConfiguration(id=1, hotel_name="Hotel Uno", subscription_active=True),
            HotelConfiguration(id=2, hotel_name="Hotel Dos", subscription_active=True),
            User(
                id=1100,
                email="reports@test.com",
                password_hash="test-hash",
                is_active=True,
                is_verified=True,
            ),
        ]
    )
    db.flush()

    ctx = {"hotel_id": 1, "role": "manager", "user_id": 1100}

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_auth():
        return AuthContext(
            hotel_id=ctx["hotel_id"],
            user_id=ctx["user_id"],
            user_email="reports@test.com",
            user_role=ctx["role"],
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    client = TestClient(fastapi_app)
    try:
        yield client, db, ctx
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def _make_room_set(db, hotel_id: int, prefix: str = "") -> tuple[RoomCategory, list[Room]]:
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"{prefix}Standard",
        code=f"{prefix}STD",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    rooms = [
        Room(
            hotel_id=hotel_id,
            category_id=category.id,
            room_number=f"{prefix}{number}",
            floor=1,
            status=RoomStatusEnum.AVAILABLE,
        )
        for number in ("101", "102", "103")
    ]
    db.add_all(rooms)
    db.flush()
    return category, rooms


def _make_guest(db, hotel_id: int, suffix: str) -> Guest:
    guest = Guest(
        hotel_id=hotel_id,
        first_name=f"Guest{suffix}",
        last_name="Report",
        document_number=f"DOC{hotel_id}{suffix}",
        terms_accepted=True,
    )
    db.add(guest)
    db.flush()
    return guest


def _make_reservation(
    db,
    *,
    hotel_id: int,
    guest: Guest,
    category: RoomCategory,
    room: Room | None,
    code: str,
    check_in: date,
    check_out: date,
    total: str = "200.00",
    paid: str = "0.00",
    status: ReservationStatusEnum = ReservationStatusEnum.PENDING,
    requires_manual_review: bool = False,
    allocation_status: str = "assigned",
) -> Reservation:
    reservation = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id if room else None,
        confirmation_code=code,
        check_in_date=check_in,
        check_out_date=check_out,
        total_amount=Decimal(total),
        amount_paid=Decimal(paid),
        status=status,
        num_adults=1,
        requires_manual_review=requires_manual_review,
        allocation_status=allocation_status,
    )
    db.add(reservation)
    db.flush()
    return reservation


def test_daily_report_includes_pending_payment_late_arrivals_and_room_blocks(reports_client):
    client, db, ctx = reports_client
    # pending_payments is financial data, redacted from the manager-safe
    # operational lane -- use owner to assert on the real computed values.
    ctx["role"] = "owner"
    report_date = date(2026, 6, 13)
    category, rooms = _make_room_set(db, 1, "A")
    pending_guest = _make_guest(db, 1, "pending")
    late_guest = _make_guest(db, 1, "late")
    departing_guest = _make_guest(db, 1, "departing")

    pending = _make_reservation(
        db,
        hotel_id=1,
        guest=pending_guest,
        category=category,
        room=rooms[0],
        code="RPT-PENDING",
        check_in=report_date,
        check_out=date(2026, 6, 15),
        total="300.00",
        paid="100.00",
    )
    late = _make_reservation(
        db,
        hotel_id=1,
        guest=late_guest,
        category=category,
        room=rooms[1],
        code="RPT-LATE",
        check_in=date(2026, 6, 12),
        check_out=date(2026, 6, 14),
        total="150.00",
        paid="150.00",
    )
    _make_reservation(
        db,
        hotel_id=1,
        guest=departing_guest,
        category=category,
        room=rooms[2],
        code="RPT-DEPART",
        check_in=date(2026, 6, 11),
        check_out=report_date,
        total="100.00",
        paid="100.00",
        status=ReservationStatusEnum.CHECKED_IN,
    )
    block = RoomBlock(
        hotel_id=1,
        room_id=rooms[2].id,
        reason_code=RoomBlockReasonEnum.MAINTENANCE,
        starts_at=date(2026, 6, 12),
        ends_at=date(2026, 6, 14),
        reason_note="AC repair",
    )
    db.add(block)
    db.add(CashSession(hotel_id=1, status=CashSessionStatusEnum.OPEN, opening_balance=Decimal("500.00")))
    db.flush()

    response = client.get("/api/reports/operational/daily", params={"report_date": report_date.isoformat()})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["hotel_id"] == 1
    assert payload["arrivals"]["count"] == 1
    assert payload["departures"]["count"] == 1
    assert [item["reservation_id"] for item in payload["pending_payments"]["reservations"]] == [pending.id]
    pending_alert = next(item for item in payload["alerts"] if item["code"] == "pending_payment")
    assert pending_alert["amount"] == "200.00"
    assert pending_alert["currency_code"] == "ARS"
    assert [item["reservation_id"] for item in payload["late_arrivals"]] == [late.id]
    assert [item["room_block_id"] for item in payload["active_room_blocks"]] == [block.id]
    assert payload["cash_session"]["status"] == "open"


def test_today_arrival_count_is_server_side_hotel_local_and_not_page_limited(reports_client, monkeypatch):
    client, db, ctx = reports_client
    report_date = date(2026, 6, 13)
    monkeypatch.setattr(reports_api, "hotel_today", lambda _db, hotel_id: report_date)
    category, _rooms = _make_room_set(db, 1, "COUNT")
    guest = _make_guest(db, 1, "arrival-count")
    reservations = [
        Reservation(
            hotel_id=1,
            guest_id=guest.id,
            category_id=category.id,
            room_id=None,
            confirmation_code=f"COUNT-{index:03d}",
            check_in_date=report_date,
            check_out_date=date(2026, 6, 14),
            total_amount=Decimal("100.00"),
            amount_paid=Decimal("0.00"),
            status=ReservationStatusEnum.PENDING,
            num_adults=1,
        )
        for index in range(205)
    ]
    reservations.extend([
        Reservation(
            hotel_id=1,
            guest_id=guest.id,
            category_id=category.id,
            confirmation_code="COUNT-CANCELLED",
            check_in_date=report_date,
            check_out_date=date(2026, 6, 14),
            total_amount=Decimal("100.00"),
            amount_paid=Decimal("0.00"),
            status=ReservationStatusEnum.CANCELLED,
            num_adults=1,
        ),
        Reservation(
            hotel_id=1,
            guest_id=guest.id,
            category_id=category.id,
            confirmation_code="COUNT-NO-SHOW",
            check_in_date=report_date,
            check_out_date=date(2026, 6, 14),
            total_amount=Decimal("100.00"),
            amount_paid=Decimal("0.00"),
            status=ReservationStatusEnum.NO_SHOW,
            num_adults=1,
        ),
    ])
    db.add_all(reservations)
    db.flush()
    ctx["role"] = "receptionist"

    response = client.get("/api/reports/operational/arrivals/count")

    assert response.status_code == 200, response.text
    assert response.json() == {"report_date": report_date.isoformat(), "count": 205}


def test_operational_daily_report_separates_no_shows_from_arrivals(reports_client):
    client, db, _ctx = reports_client
    report_date = date(2026, 6, 13)
    category, rooms = _make_room_set(db, 1, "ARRIVAL-STATUS")
    active = _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "active-arrival"),
        category=category,
        room=rooms[0],
        code="ARRIVAL-ACTIVE",
        check_in=report_date,
        check_out=date(2026, 6, 14),
    )
    cancelled = _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "cancelled-arrival"),
        category=category,
        room=rooms[1],
        code="ARRIVAL-CANCELLED",
        check_in=report_date,
        check_out=date(2026, 6, 14),
        status=ReservationStatusEnum.CANCELLED,
    )
    no_show = _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "no-show-arrival"),
        category=category,
        room=rooms[2],
        code="ARRIVAL-NO-SHOW",
        check_in=report_date,
        check_out=date(2026, 6, 14),
        status=ReservationStatusEnum.NO_SHOW,
    )

    response = client.get("/api/reports/operational/daily", params={"report_date": report_date.isoformat()})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["arrivals"]["count"] == 1
    assert [item["reservation_id"] for item in payload["arrivals"]["reservations"]] == [active.id]
    assert payload["no_shows"]["count"] == 1
    assert [item["reservation_id"] for item in payload["no_shows"]["reservations"]] == [no_show.id]
    assert cancelled.id not in {item["reservation_id"] for item in payload["arrivals"]["reservations"]}


def test_occupancy_report_counts_pre_check_in_reservations(reports_client):
    client, db, _ctx = reports_client
    report_date = date(2026, 6, 13)
    category, rooms = _make_room_set(db, 1, "PRE-CHECK-IN-OCCUPANCY")
    _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "pre-check-in-occupancy"),
        category=category,
        room=rooms[0],
        code="RPT-PRE-CHECK-IN-OCCUPANCY",
        check_in=report_date,
        check_out=date(2026, 6, 14),
        status=ReservationStatusEnum.PRE_CHECK_IN,
    )

    response = client.get(
        "/api/reports/occupancy",
        params={"start_date": report_date.isoformat(), "end_date": report_date.isoformat()},
    )

    assert response.status_code == 200, response.text
    assert response.json()["daily"] == [
        {
            "date": report_date.isoformat(),
            "occupied": 1,
            "available": 2,
            "rate": 33.3,
        }
    ]


def test_daily_report_is_hotel_scoped(reports_client):
    client, db, _ctx = reports_client
    report_date = date(2026, 6, 13)
    category_1, rooms_1 = _make_room_set(db, 1, "H1")
    category_2, rooms_2 = _make_room_set(db, 2, "H2")
    _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "h1"),
        category=category_1,
        room=rooms_1[0],
        code="RPT-H1",
        check_in=report_date,
        check_out=date(2026, 6, 14),
        total="120.00",
        paid="0.00",
    )
    _make_reservation(
        db,
        hotel_id=2,
        guest=_make_guest(db, 2, "h2"),
        category=category_2,
        room=rooms_2[0],
        code="RPT-H2",
        check_in=report_date,
        check_out=date(2026, 6, 14),
        total="999.00",
        paid="0.00",
    )

    response = client.get("/api/reports/operational/daily", params={"report_date": report_date.isoformat()})

    assert response.status_code == 200, response.text
    codes = {item["confirmation_code"] for item in response.json()["arrivals"]["reservations"]}
    assert codes == {"RPT-H1"}


def test_available_with_review_surfaces_in_report(reports_client):
    client, db, _ctx = reports_client
    report_date = date(2026, 6, 13)
    category, rooms = _make_room_set(db, 1, "REV")
    review_reservation = _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "review"),
        category=category,
        room=rooms[0],
        code="RPT-REVIEW",
        check_in=date(2026, 6, 14),
        check_out=date(2026, 6, 15),
        total="100.00",
        paid="100.00",
        status=ReservationStatusEnum.FULLY_PAID,
        requires_manual_review=True,
        allocation_status="manual_review",
    )

    response = client.get("/api/reports/operational/daily", params={"report_date": report_date.isoformat()})

    assert response.status_code == 200, response.text
    assert response.json()["available_with_review"] == [
        {
            "reservation_id": review_reservation.id,
            "confirmation_code": "RPT-REVIEW",
            "room_id": rooms[0].id,
            "room_number": "REV101",
            "check_in_date": "2026-06-14",
            "check_out_date": "2026-06-15",
            "allocation_status": "manual_review",
        }
    ]


def test_daily_report_derives_late_and_review_lists_from_unbounded_candidates(reports_client):
    client, db, ctx = reports_client
    ctx["role"] = "owner"
    report_date = date(2026, 6, 13)
    category, rooms = _make_room_set(db, 1, "SUBSET")

    # Create the later stay first so the expected order proves the report sorts
    # by check-in date, then id, rather than relying on insertion order.
    late_later = _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "late-later"),
        category=category,
        room=rooms[0],
        code="SUBSET-LATE-LATER",
        check_in=date(2026, 6, 12),
        check_out=date(2026, 6, 15),
        paid="200.00",
        requires_manual_review=True,
        allocation_status="manual_review",
    )
    late_same_date = _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "late-same-date"),
        category=category,
        room=None,
        code="SUBSET-LATE-SAME-DATE",
        check_in=date(2026, 6, 12),
        check_out=date(2026, 6, 15),
        paid="200.00",
    )
    late_earlier = _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "late-earlier"),
        category=category,
        room=rooms[1],
        code="SUBSET-LATE-EARLIER",
        check_in=date(2026, 6, 10),
        check_out=date(2026, 6, 14),
        paid="200.00",
        requires_manual_review=True,
        allocation_status="manual_review",
    )
    review_upcoming = _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "review-upcoming"),
        category=category,
        room=rooms[2],
        code="SUBSET-REVIEW-UPCOMING",
        check_in=date(2026, 6, 14),
        check_out=date(2026, 6, 16),
        paid="200.00",
        requires_manual_review=True,
        allocation_status="manual_review",
    )
    far_future = _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "far-future"),
        category=category,
        room=None,
        code="SUBSET-FAR-FUTURE",
        check_in=date(2027, 6, 10),
        check_out=date(2027, 6, 12),
        total="250.00",
    )
    # A terminal status and a checkout on the boundary must remain outside the
    # derived subsets, exactly as in the original standalone queries.
    _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "checked-in"),
        category=category,
        room=None,
        code="SUBSET-CHECKED-IN",
        check_in=date(2026, 6, 12),
        check_out=date(2026, 6, 15),
        paid="200.00",
        status=ReservationStatusEnum.CHECKED_IN,
    )
    _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "checkout-boundary"),
        category=category,
        room=None,
        code="SUBSET-CHECKOUT-BOUNDARY",
        check_in=date(2026, 6, 12),
        check_out=report_date,
        requires_manual_review=True,
    )

    reservation_selects: list[str] = []
    redundant_transaction_loads: list[str] = []
    additional_guest_loads: list[str] = []
    related_collection_loads: list[str] = []

    def capture_reservation_select(_connection, _cursor, statement, _parameters, _context, _executemany):
        normalized = " ".join(statement.lower().split())
        if (
            normalized.lstrip().startswith("select")
            and " from reservations " in normalized
            and "where reservations.hotel_id = ? and reservations.deleted_at is null" in normalized
        ):
            reservation_selects.append(normalized)
        if (
            normalized.lstrip().startswith("select transactions.id")
            and " from transactions " in normalized
            and "transactions.id" in normalized
            and " in (" in normalized
        ):
            redundant_transaction_loads.append(normalized)
        if "reservation_additional_guests" in normalized:
            additional_guest_loads.append(normalized)
        if any(
            marker in normalized
            for marker in (
                "from guest_companions ",
                "from guest_tags ",
                "where guests_1.id in (",
                "where rooms_1.id in (",
            )
        ):
            related_collection_loads.append(normalized)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", capture_reservation_select)
    try:
        response = client.get(
            "/api/reports/operational/daily",
            params={"report_date": report_date.isoformat()},
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_reservation_select)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["reservation_id"] for item in payload["late_arrivals"]] == [
        late_earlier.id,
        late_later.id,
        late_same_date.id,
    ]
    assert [item["reservation_id"] for item in payload["available_with_review"]] == [
        late_earlier.id,
        late_later.id,
        review_upcoming.id,
    ]
    assert [item["reservation_id"] for item in payload["pending_payments"]["reservations"]] == [
        far_future.id,
    ]
    # The report keeps one lightweight flag projection, aggregates direct
    # balances in SQL, and fetches only the visible payment page.
    assert len(reservation_selects) == 6, (
        "expected three operational groups and three hotel-scoped candidate reads, "
        f"got {len(reservation_selects)}"
    )
    candidate_queries = [
        statement
        for statement in reservation_selects
        if "from transactions " in statement and "from billing_adjustments " in statement
    ]
    assert len(candidate_queries) == 2, candidate_queries
    flags_queries = [
        statement
        for statement in reservation_selects
        if "company_night_charges" in statement and "requires_manual_review" in statement
    ]
    assert len(flags_queries) == 1, flags_queries
    flags_query = flags_queries[0]
    # The flags projection is flat and tenant scoped, and does not aggregate
    # payments/adjustments that the later batch helpers load for selected IDs.
    assert "join guests " in flags_query
    assert "guests.hotel_id = reservations.hotel_id" in flags_query
    assert "join rooms " in flags_query
    assert "rooms.hotel_id = reservations.hotel_id" in flags_query
    assert "daily_report_balance_scope" not in flags_query
    assert "daily_report_transaction_totals" not in flags_query
    assert "daily_report_adjustment_totals" not in flags_query
    assert "from transactions " not in flags_query
    assert "from billing_adjustments " not in flags_query
    for query in candidate_queries:
        assert "daily_report_transaction_totals" in query
        assert "daily_report_adjustment_totals" in query
        assert "group by transactions.hotel_id, transactions.reservation_id" in query
    page_queries = [statement for statement in candidate_queries if " limit " in statement]
    assert len(page_queries) == 1, page_queries
    assert redundant_transaction_loads == [], redundant_transaction_loads
    assert additional_guest_loads == [], additional_guest_loads
    assert related_collection_loads == [], related_collection_loads


def test_daily_report_does_not_hydrate_future_reservation_entities(reports_client):
    _client, db, _ctx = reports_client
    report_date = date(2026, 6, 13)
    category, _rooms = _make_room_set(db, 1, "FUTURE-SCALAR")
    guest = _make_guest(db, 1, "future-scalar")
    reservations = [
        _make_reservation(
            db,
            hotel_id=1,
            guest=guest,
            category=category,
            room=None,
            code=f"RPT-FUTURE-SCALAR-{idx}",
            check_in=date(2026, 7, idx + 1),
            check_out=date(2026, 7, idx + 3),
            total="200.00",
            paid="200.00" if idx < 19 else "0.00",
            status=ReservationStatusEnum.FULLY_PAID if idx < 19 else ReservationStatusEnum.PENDING,
        )
        for idx in range(20)
    ]
    db.commit()
    pending_id = reservations[-1].id
    db.expunge_all()

    loaded_reservation_ids = []

    def record_loaded_reservation(session, instance):
        if isinstance(instance, Reservation):
            loaded_reservation_ids.append(instance.id)

    event.listen(db, "loaded_as_persistent", record_loaded_reservation)
    try:
        report = reports_api.build_daily_operational_report(db, hotel_id=1, report_date=report_date)
    finally:
        event.remove(db, "loaded_as_persistent", record_loaded_reservation)

    assert [item.reservation_id for item in report.pending_payments.reservations] == [pending_id]
    assert loaded_reservation_ids == []


def test_billing_adjustment_aggregation_is_tenant_scoped_projection(reports_client):
    _client, db, _ctx = reports_client
    category_1, rooms_1 = _make_room_set(db, 1, "LEDGER1")
    category_2, rooms_2 = _make_room_set(db, 2, "LEDGER2")
    reservation_1 = _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "ledger-1"),
        category=category_1,
        room=rooms_1[0],
        code="LEDGER-1",
        check_in=date(2026, 6, 13),
        check_out=date(2026, 6, 14),
    )
    reservation_2 = _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "ledger-2"),
        category=category_1,
        room=rooms_1[1],
        code="LEDGER-2",
        check_in=date(2026, 6, 13),
        check_out=date(2026, 6, 14),
    )
    foreign_reservation = _make_reservation(
        db,
        hotel_id=2,
        guest=_make_guest(db, 2, "ledger-foreign"),
        category=category_2,
        room=rooms_2[0],
        code="LEDGER-FOREIGN",
        check_in=date(2026, 6, 13),
        check_out=date(2026, 6, 14),
    )

    def add_adjustment(hotel_id: int, reservation_id: int, amount: str) -> None:
        db.add(
            BillingAdjustment(
                hotel_id=hotel_id,
                reservation_id=reservation_id,
                adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
                amount=Decimal(amount),
                currency_code="ARS",
                total_amount=Decimal(amount),
            )
        )

    add_adjustment(1, reservation_1.id, "10.10")
    add_adjustment(1, reservation_1.id, "1.20")
    add_adjustment(1, reservation_2.id, "4.56")
    add_adjustment(2, foreign_reservation.id, "999.99")
    db.flush()

    statements: list[str] = []

    def capture_select(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(" ".join(statement.lower().split()))

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", capture_select)
    try:
        totals = billing_adjustment_totals_by_reservation(
            db,
            1,
            [reservation_1.id, reservation_2.id, foreign_reservation.id],
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_select)

    assert totals == {
        reservation_1.id: Decimal("11.30"),
        reservation_2.id: Decimal("4.56"),
    }
    assert len(statements) == 1, statements
    assert "sum(billing_adjustments.total_amount)" in statements[0]
    assert "group by billing_adjustments.reservation_id" in statements[0]
    assert "billing_adjustments.hotel_id" in statements[0]
    assert " join " not in statements[0]


def test_billing_adjustment_aggregation_executes_on_postgres(pg_session):
    """Exercise Numeric SUM and tenant scoping on the real PostgreSQL dialect."""
    hotel_id = 9301
    foreign_hotel_id = 9302
    pg_session.add_all(
        [
            HotelConfiguration(id=hotel_id, hotel_name="Synthetic PG Ledger"),
            HotelConfiguration(id=foreign_hotel_id, hotel_name="Synthetic PG Foreign Ledger"),
        ]
    )
    pg_session.flush()

    category, _rooms = _make_room_set(pg_session, hotel_id, "PGL")
    foreign_category, _foreign_rooms = _make_room_set(pg_session, foreign_hotel_id, "PGF")
    guest = _make_guest(pg_session, hotel_id, "pg-ledger")
    foreign_guest = _make_guest(pg_session, foreign_hotel_id, "pg-ledger-foreign")
    reservation = _make_reservation(
        pg_session,
        hotel_id=hotel_id,
        guest=guest,
        category=category,
        room=None,
        code="PG-LEDGER-AGGREGATE-001",
        check_in=date(2026, 10, 6),
        check_out=date(2026, 10, 7),
    )
    foreign_reservation = _make_reservation(
        pg_session,
        hotel_id=foreign_hotel_id,
        guest=foreign_guest,
        category=foreign_category,
        room=None,
        code="PG-LEDGER-AGGREGATE-FOREIGN",
        check_in=date(2026, 10, 6),
        check_out=date(2026, 10, 7),
    )
    pg_session.add_all(
        [
            BillingAdjustment(
                hotel_id=hotel_id,
                reservation_id=reservation.id,
                adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
                amount=Decimal("10.10"),
                currency_code="ARS",
                total_amount=Decimal("10.10"),
            ),
            BillingAdjustment(
                hotel_id=hotel_id,
                reservation_id=reservation.id,
                adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
                amount=Decimal("1.20"),
                currency_code="ARS",
                total_amount=Decimal("1.20"),
            ),
            BillingAdjustment(
                hotel_id=foreign_hotel_id,
                reservation_id=foreign_reservation.id,
                adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
                amount=Decimal("999.99"),
                currency_code="ARS",
                total_amount=Decimal("999.99"),
            ),
        ]
    )
    pg_session.flush()

    totals = billing_adjustment_totals_by_reservation(
        pg_session,
        hotel_id,
        [reservation.id, foreign_reservation.id],
    )

    assert totals == {reservation.id: Decimal("11.30")}


def test_reports_permission_denied_for_housekeeping(reports_client):
    client, _db, ctx = reports_client
    ctx["role"] = "housekeeping"

    response = client.get("/api/reports/operational/daily", params={"report_date": "2026-06-13"})

    assert response.status_code == 403


def test_daily_report_pending_payments_reflect_consumption_charges(reports_client):
    """A fully-paid stay that later gets a consumption charge (BillingAdjustment)
    must show up as a pending payment with the real balance due, matching the
    canonical operational_balance_due helper used elsewhere in the app."""
    client, db, ctx = reports_client
    # pending_payments is financial data, redacted from the manager-safe
    # operational lane -- use owner to assert on the real computed values.
    ctx["role"] = "owner"
    report_date = date(2026, 6, 13)
    category, rooms = _make_room_set(db, 1, "C")
    guest = _make_guest(db, 1, "consumption")
    reservation = _make_reservation(
        db,
        hotel_id=1,
        guest=guest,
        category=category,
        room=rooms[0],
        code="RPT-CONSUME",
        check_in=date(2026, 6, 12),
        check_out=date(2026, 6, 15),
        total="200.00",
        paid="200.00",
        status=ReservationStatusEnum.CHECKED_IN,
    )
    db.commit()

    # Real journey: charge a consumption via the normal API, not a DB write.
    # reservation:charge is reception's lane, not manager's -- switch role for
    # this call, then switch back since the report itself is a manager view.
    ctx["role"] = "receptionist"
    charge_response = client.post(
        f"/api/reservations/{reservation.id}/charges",
        json={"amount": "50.00", "currency_code": "ARS", "description": "Minibar QA"},
    )
    assert charge_response.status_code == 201, charge_response.text
    ctx["role"] = "owner"

    response = client.get("/api/reports/operational/daily", params={"report_date": report_date.isoformat()})

    assert response.status_code == 200, response.text
    payload = response.json()
    pending_ids = [item["reservation_id"] for item in payload["pending_payments"]["reservations"]]
    assert reservation.id in pending_ids, (
        "A stay with an unpaid consumption charge must appear in pending_payments"
    )
    pending_item = next(
        item for item in payload["pending_payments"]["reservations"] if item["reservation_id"] == reservation.id
    )
    assert Decimal(pending_item["balance_due"]) == Decimal("50.00")
    alert_reservation_ids = {
        alert["reservation_id"] for alert in payload["alerts"] if alert["code"] == "pending_payment"
    }
    assert reservation.id in alert_reservation_ids


def test_daily_report_projects_only_future_reservations_with_pending_balance(reports_client):
    _client, db, _ctx = reports_client
    report_date = date(2026, 6, 13)
    category, _rooms = _make_room_set(db, 1, "FUTURE")
    guest = _make_guest(db, 1, "future")
    reservations = [
        _make_reservation(
            db,
            hotel_id=1,
            guest=guest,
            category=category,
            room=None,
            code=f"RPT-FUTURE-{idx}",
            check_in=date(2026, 7, idx + 1),
            check_out=date(2026, 7, idx + 3),
            total="200.00",
            paid="200.00" if idx < 19 else "0.00",
            status=ReservationStatusEnum.FULLY_PAID if idx < 19 else ReservationStatusEnum.PENDING,
        )
        for idx in range(20)
    ]
    adjustment_reservation = _make_reservation(
        db,
        hotel_id=1,
        guest=guest,
        category=category,
        room=None,
        code="RPT-FUTURE-ADJUSTMENT",
        check_in=date(2026, 7, 30),
        check_out=date(2026, 8, 1),
        total="200.00",
        paid="200.00",
        status=ReservationStatusEnum.FULLY_PAID,
    )
    db.add(
        BillingAdjustment(
            hotel_id=1,
            reservation_id=adjustment_reservation.id,
            adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
            amount=Decimal("25.00"),
            currency_code="ARS",
            total_amount=Decimal("25.00"),
        )
    )
    db.commit()
    pending_id = reservations[-1].id
    adjustment_id = adjustment_reservation.id
    db.expunge_all()

    candidate_ids = [
        row.id
        for row in _daily_report_balance_candidate_query(
            db,
            hotel_id=1,
            report_date=report_date,
        ).all()
    ]
    assert candidate_ids == [pending_id, adjustment_id]

    loaded_reservation_ids = []

    def record_loaded_reservation(session, instance):
        if isinstance(instance, Reservation):
            loaded_reservation_ids.append(instance.id)

    event.listen(db, "loaded_as_persistent", record_loaded_reservation)
    try:
        report = daily_report(db, hotel_id=1, report_date=report_date)
    finally:
        event.remove(db, "loaded_as_persistent", record_loaded_reservation)

    assert [item.reservation_id for item in report.pending_payments.reservations] == [pending_id, adjustment_id]
    assert loaded_reservation_ids == []


def test_daily_report_paginates_pending_details_and_keeps_global_balance(reports_client):
    client, db, ctx = reports_client
    ctx["role"] = "owner"
    report_date = date(2026, 6, 13)
    category, _rooms = _make_room_set(db, 1, "PAGED")
    guest = _make_guest(db, 1, "paged")
    reservations = [
        _make_reservation(
            db,
            hotel_id=1,
            guest=guest,
            category=category,
            room=None,
            code=f"RPT-PAGED-{idx:03d}",
            check_in=date(2026, 7, 1),
            check_out=date(2026, 7, 3),
            total="200.00",
            paid="0.00",
        )
        for idx in range(65)
    ]
    db.commit()

    candidate_page_selects = []

    def capture_candidate_page(_connection, _cursor, statement, parameters, _context, _executemany):
        normalized = " ".join(statement.lower().split())
        if (
            "from transactions " in normalized
            and "from billing_adjustments " in normalized
            and " limit " in normalized
        ):
            candidate_page_selects.append((normalized, tuple(parameters)))

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", capture_candidate_page)
    try:
        first_response = client.get(
            "/api/reports/operational/daily",
            params={"report_date": report_date.isoformat()},
        )
        second_response = client.get(
            "/api/reports/operational/daily",
            params={"report_date": report_date.isoformat(), "pending_page": 2},
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_candidate_page)

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text
    first = first_response.json()
    second = second_response.json()
    first_group = first["pending_payments"]
    second_group = second["pending_payments"]
    assert first_group["count"] == second_group["count"] == 65
    assert first_group["page"] == 1
    assert second_group["page"] == 2
    assert first_group["page_size"] == second_group["page_size"] == 50
    assert first_group["total_pages"] == second_group["total_pages"] == 2
    assert len(first_group["reservations"]) == 50
    assert len(second_group["reservations"]) == 15
    first_ids = {item["reservation_id"] for item in first_group["reservations"]}
    second_ids = {item["reservation_id"] for item in second_group["reservations"]}
    assert first_ids.isdisjoint(second_ids)
    assert first_ids | second_ids == {reservation.id for reservation in reservations}
    assert first_group["total_balance_by_currency"] == [
        {"currency_code": "ARS", "total_balance": "13000.00"}
    ]
    assert second_group["total_balance_by_currency"] == first_group["total_balance_by_currency"]
    assert len(candidate_page_selects) == 2, candidate_page_selects
    assert [query_params[-2:] for _query, query_params in candidate_page_selects] == [
        (50, 0),
        (15, 50),
    ]
    assert sum(alert["code"] == "pending_payment" for alert in first["alerts"]) == 50
    assert sum(alert["code"] == "pending_payment" for alert in second["alerts"]) == 15
    assert first["alert_count"] == second["alert_count"] == 66


def test_daily_report_pages_direct_balances_before_deferred_company_extras(reports_client):
    client, db, ctx = reports_client
    ctx["role"] = "owner"
    report_date = date(2026, 6, 13)
    category, _rooms = _make_room_set(db, 1, "MIXED-PAGE")
    guest = _make_guest(db, 1, "mixed-page")
    direct = _make_reservation(
        db,
        hotel_id=1,
        guest=guest,
        category=category,
        room=None,
        code="RPT-MIXED-DIRECT",
        check_in=date(2026, 7, 1),
        check_out=date(2026, 7, 3),
        total="100.00",
    )
    company = Company(
        hotel_id=1,
        legal_name="Empresa Mixta SA",
        display_name="Empresa Mixta",
        payment_deferred=True,
    )
    db.add(company)
    db.flush()
    deferred = _make_reservation(
        db,
        hotel_id=1,
        guest=guest,
        category=category,
        room=None,
        code="RPT-MIXED-DEFERRED",
        check_in=date(2026, 7, 4),
        check_out=date(2026, 7, 6),
        total="500.00",
    )
    deferred.company_id = company.id
    deferred.settlement_status = "deferred"
    db.flush()
    adjustment = BillingAdjustment(
        hotel_id=1,
        reservation_id=deferred.id,
        adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
        amount=Decimal("50.00"),
        currency_code="ARS",
        total_amount=Decimal("50.00"),
    )
    db.add(adjustment)
    db.flush()
    db.add(
        CompanyNightCharge(
            hotel_id=1,
            reservation_id=deferred.id,
            company_id=company.id,
            billing_adjustment_id=adjustment.id,
            stay_date=report_date,
            amount=Decimal("50.00"),
            currency_code="ARS",
        )
    )
    db.commit()

    first = client.get(
        "/api/reports/operational/daily",
        params={"report_date": report_date.isoformat(), "pending_page_size": 1},
    )
    second = client.get(
        "/api/reports/operational/daily",
        params={"report_date": report_date.isoformat(), "pending_page": 2, "pending_page_size": 1},
    )

    assert first.status_code == second.status_code == 200
    first_group = first.json()["pending_payments"]
    second_group = second.json()["pending_payments"]
    assert first_group["count"] == second_group["count"] == 2
    assert first_group["total_balance_by_currency"] == second_group["total_balance_by_currency"] == [
        {"currency_code": "ARS", "total_balance": "150.00"}
    ]
    assert first_group["reservations"][0]["reservation_id"] == direct.id
    assert first_group["reservations"][0]["balance_due"] == "100.00"
    assert second_group["reservations"][0]["reservation_id"] == deferred.id
    assert second_group["reservations"][0]["company_billing_deferred"] is True
    assert second_group["reservations"][0]["company_night_extra_due"] == "50.00"
