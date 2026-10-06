from datetime import date, datetime, timezone

from sqlalchemy.dialects import postgresql

from app.models.guest import Guest
from app.models.reservation import (
    Reservation,
    ReservationStatusEnum,
)
from app.models.operations import ReservationStatusHistory
from app.models.transaction import (
    PaymentMethodEnum,
    Transaction,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from app.schemas.reservation import ReservationCreate
from app.services.reservation_service import ReservationError, create_reservation
from app.services import row_locks
from app.tasks.no_show_tasks import sweep_no_shows


def _reservation(db, *, hotel_id, guest, category, room, status=ReservationStatusEnum.PENDING, code):
    row = create_reservation(
        db,
        ReservationCreate(
            guest_id=guest.id,
            category_id=category.id,
            room_id=room.id,
            check_in_date=date(2026, 10, 1),
            check_out_date=date(2026, 10, 3),
        ),
        hotel_id=hotel_id,
    )
    row.confirmation_code = code
    row.status = status
    db.flush()
    return row


def test_sweep_respects_local_cutoff_boundary_and_uses_hotel_timezone(
    db, hotel_config, sample_guest, sample_categories, sample_rooms, monkeypatch
):
    captured = []
    original_lock_query = row_locks.lock_query

    def capture_lock_target(query, model):
        locked_query = original_lock_query(query, model)
        captured.append(str(locked_query.statement.compile(dialect=postgresql.dialect())))
        return locked_query

    monkeypatch.setattr("app.tasks.no_show_tasks.lock_query", capture_lock_target)
    hotel_config.hotel_timezone = "America/Argentina/Buenos_Aires"
    hotel_config.no_show_cutoff_hours = 24
    row = _reservation(
        db, hotel_id=hotel_config.id, guest=sample_guest, category=sample_categories[0],
        room=sample_rooms[0], code="SWEEP-CUTOFF",
    )
    # Oct 2 00:00 in Argentina is Oct 2 03:00 UTC.
    before = datetime(2026, 10, 2, 2, 59, 59, tzinfo=timezone.utc)
    exact = datetime(2026, 10, 2, 3, 0, 0, tzinfo=timezone.utc)

    before_result = sweep_no_shows(db, now_utc=before)
    exact_result = sweep_no_shows(db, now_utc=exact)
    repeated_result = sweep_no_shows(db, now_utc=exact)

    assert before_result["marked"] == before_result["scanned"] == 0
    assert exact_result["marked"] == exact_result["scanned"] == 1
    assert repeated_result["marked"] == repeated_result["scanned"] == 0
    assert row.status == ReservationStatusEnum.NO_SHOW
    assert db.query(ReservationStatusHistory).filter_by(reservation_id=row.id, to_status="no_show").count() == 1
    # The exact-boundary transition locks once; each invocation also issues
    # the bounded eligibility query so a repeated sweep can prove idempotency.
    assert len(captured) == 3
    assert all("FOR UPDATE OF reservations" in sql for sql in captured)


def test_sweep_marks_pending_and_paid_as_no_show_without_changing_money(
    db, hotel_config, sample_guest, sample_categories, sample_rooms
):
    # Lifecycle cleanup continues for hotels whose paid subscription has
    # expired; the reservation records still need a terminal outcome.
    hotel_config.subscription_active = False
    hotel_config.no_show_cutoff_hours = 0
    pending = _reservation(
        db, hotel_id=hotel_config.id, guest=sample_guest, category=sample_categories[0],
        room=sample_rooms[0], code="SWEEP-PENDING",
    )
    paid = _reservation(
        db, hotel_id=hotel_config.id, guest=sample_guest, category=sample_categories[0],
        room=sample_rooms[1], status=ReservationStatusEnum.FULLY_PAID, code="SWEEP-PAID",
    )
    deposit_paid = _reservation(
        db, hotel_id=hotel_config.id, guest=sample_guest, category=sample_categories[0],
        room=sample_rooms[2], status=ReservationStatusEnum.DEPOSIT_PAID, code="SWEEP-DEPOSIT",
    )
    payment = Transaction(
        hotel_id=hotel_config.id,
        reservation_id=paid.id,
        amount=20,
        currency="ARS",
        transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        payment_method=PaymentMethodEnum.CASH,
        status=TransactionStatusEnum.COMPLETED,
    )
    db.add(payment)
    db.flush()

    result = sweep_no_shows(db, now_utc=datetime(2026, 10, 2, 3, tzinfo=timezone.utc))

    assert set(result["reservation_ids"]) == {pending.id, paid.id, deposit_paid.id}
    assert pending.status == paid.status == deposit_paid.status == ReservationStatusEnum.NO_SHOW
    assert all(row.no_show_policy_applied.value == "none" for row in (pending, paid, deposit_paid))
    assert db.query(Transaction).filter_by(reservation_id=paid.id).one().status == TransactionStatusEnum.COMPLETED
    history = db.query(ReservationStatusHistory).filter_by(
        reservation_id=paid.id, to_status="no_show"
    ).one()
    assert history.reason_code == "no_show"
    assert history.notes == "Marcada como no-show sin cargo automático"


def test_sweep_excludes_checked_in_and_is_idempotent(
    db, hotel_config, sample_guest, sample_categories, sample_rooms
):
    hotel_config.no_show_cutoff_hours = 0
    checked_in = _reservation(
        db, hotel_id=hotel_config.id, guest=sample_guest, category=sample_categories[0],
        room=sample_rooms[0], status=ReservationStatusEnum.CHECKED_IN, code="SWEEP-IN",
    )
    now = datetime(2026, 10, 2, 3, tzinfo=timezone.utc)

    assert sweep_no_shows(db, now_utc=now)["marked"] == 0
    assert checked_in.status == ReservationStatusEnum.CHECKED_IN
    assert sweep_no_shows(db, now_utc=now)["marked"] == 0
    assert db.query(ReservationStatusHistory).filter_by(reservation_id=checked_in.id, to_status="no_show").count() == 0


def test_sweep_is_tenant_scoped(
    db, hotel_config, sample_guest, sample_categories, sample_rooms,
    sample_categories_hotel2, sample_rooms_hotel2,
):
    guest2 = Guest(first_name="Second", last_name="Guest", hotel_id=2)
    db.add(guest2)
    db.flush()
    row = _reservation(
        db, hotel_id=2, guest=guest2, category=sample_categories_hotel2[0],
        room=sample_rooms_hotel2[0], code="SWEEP-OTHER-HOTEL",
    )

    result = sweep_no_shows(db, hotel_id=hotel_config.id, now_utc=datetime(2026, 10, 2, 3, tzinfo=timezone.utc))

    assert result["marked"] == 0
    assert row.status == ReservationStatusEnum.PENDING


def test_no_show_sweep_is_scheduled_even_when_external_effects_are_disabled(monkeypatch):
    from app.config import Settings
    from app.tasks.celery_app import build_beat_schedule

    settings = Settings(
        _env_file=None,
        EXTERNAL_EFFECTS_ENABLED=False,
        CONNECTIONS_ENABLED=False,
        REALTIME_EVENTS_ENABLED=False,
    )

    schedule = build_beat_schedule(settings)

    assert schedule["reservations-no-show-sweep"]["task"] == "reservations.sweep_no_shows"


def test_sweep_task_visits_every_hotel_including_inactive_subscriptions(monkeypatch):
    from app.tasks.no_show_tasks import sweep_no_shows_task

    class Query:
        def order_by(self, *_args):
            return self

        def all(self):
            # Represents all tenants returned by HotelConfiguration, including
            # one whose subscription_active flag is false.
            return [(1,), (2,)]

    class FakeDb:
        def query(self, *_args):
            return Query()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    class SessionFactory:
        def __call__(self):
            return FakeDb()

    visited = []
    monkeypatch.setattr("app.tasks.no_show_tasks.get_engine", lambda _url: object())
    monkeypatch.setattr("app.tasks.no_show_tasks.sessionmaker", lambda bind: SessionFactory())
    monkeypatch.setattr(
        "app.tasks.no_show_tasks.sweep_no_shows",
        lambda _db, *, hotel_id: visited.append(hotel_id)
        or {"hotels_scanned": 0, "scanned": 0, "marked": 0, "reservation_ids": []},
    )

    sweep_no_shows_task.run()

    assert visited == [1, 2]
