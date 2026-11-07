from datetime import date
from types import SimpleNamespace

from app.models.reservation import ReservationOutcomeEnum, ReservationStatusEnum
from app.services import reservation_service


class _SessionStub:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)

    def flush(self):
        pass


def test_checkout_transition_marks_reservation_outcome_completed(monkeypatch):
    reservation = SimpleNamespace(
        id=43,
        hotel_id=4,
        room=None,
        status=ReservationStatusEnum.CHECKED_IN,
        outcome=ReservationOutcomeEnum.PENDING,
        check_in_date=date(2026, 11, 4),
        check_out_date=date(2026, 11, 7),
        can_transition_to=lambda target: target == ReservationStatusEnum.CHECKED_OUT,
    )
    session = _SessionStub()
    monkeypatch.setattr(reservation_service, "_invalidate_availability_cache", lambda hotel_id: None)

    updated = reservation_service.transition_reservation_status(
        session,
        reservation,
        ReservationStatusEnum.CHECKED_OUT,
        hotel_id=4,
        refresh_facts=False,
    )

    assert updated.status == ReservationStatusEnum.CHECKED_OUT
    assert updated.outcome == ReservationOutcomeEnum.COMPLETED
