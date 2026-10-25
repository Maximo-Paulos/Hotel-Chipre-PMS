from __future__ import annotations

from datetime import date

import pytest

from app.config import get_settings
from app.models.audit_log import AuditActionEnum, AuditLog
from app.models.analytics import FactReservationDaily
from app.models.guest import Guest
from app.models.ota import OTAReservationMapping, OTASyncStatusEnum
from app.models.ota_core import OTAReservationLifecycleEnum, OTAReservationLink
from app.models.payment import PaymentLink
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomHousekeepingStatusEnum, RoomStatusEnum
from app.schemas.reservation import ReservationCreate
from app.services.ota_service import OTAIntegrationService
from app.services.reservation_service import create_reservation, transition_reservation_status
import app.services.ota_service as ota_service_module
import app.services.reservation_service as reservation_service_module


@pytest.fixture(autouse=True)
def _enable_mocked_inbound_events(monkeypatch):
    monkeypatch.setenv("INBOUND_PROVIDER_EVENTS_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _booking_payload(**overrides):
    payload = {
        "reservation_id": "BKG-LIFECYCLE-001",
        "guest_name": "Jane Doe",
        "guest_email": "jane@example.com",
        "guest_phone": "+5491112345678",
        "checkin": "2026-09-01",
        "checkout": "2026-09-03",
        "room_type": "STD_DBL",
        "num_adults": 2,
        "num_children": 0,
        "total_price": 320.0,
        "currency": "ARS",
        "property_id": "booking-h1",
    }
    payload.update(overrides)
    return payload


def _seed_booking_secret(db, hotel_id: int = 1) -> str:
    secret = f"booking-secret-h{hotel_id}"
    OTAIntegrationService.upsert_webhook_credential(
        db,
        hotel_id=hotel_id,
        provider="booking",
        webhook_secret=secret,
        external_property_id=f"booking-h{hotel_id}",
    )
    return secret


def test_booking_modify_updates_existing_reservation_and_guest(db, sample_rooms, sample_categories, hotel_config):
    secret = _seed_booking_secret(db, hotel_config.id)
    initial = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    reservation_id = initial.reservation_id
    db.flush()
    initial_facts = db.query(FactReservationDaily).filter_by(reservation_id=reservation_id).all()
    assert sum(float(row.revenue_gross_ars) for row in initial_facts) == pytest.approx(320.0)

    updated_mapping = OTAIntegrationService.process_booking_webhook(
        db,
        hotel_config.id,
        secret,
        _booking_payload(
            event="reservation.modified",
            guest_name="Jane Roe",
            guest_email="jane.roe@example.com",
            guest_phone="+5491198765432",
            checkout="2026-09-04",
            total_price=470.0,
        ),
    )
    db.flush()

    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).one()
    link = db.query(OTAReservationLink).filter_by(
        hotel_id=hotel_config.id,
        external_reservation_id="BKG-LIFECYCLE-001",
    ).one()

    assert updated_mapping.id == initial.id
    assert reservation.id == reservation_id
    assert str(reservation.check_out_date) == "2026-09-04"
    assert reservation.total_amount == 470.0
    assert reservation.guest.first_name == "Jane"
    assert reservation.guest.last_name == "Roe"
    assert reservation.guest.email == "jane.roe@example.com"
    assert reservation.guest.phone == "+5491198765432"
    assert updated_mapping.sync_status == OTASyncStatusEnum.SYNCED
    assert link.provider_state == OTAReservationLifecycleEnum.MODIFIED
    updated_facts = db.query(FactReservationDaily).filter_by(reservation_id=reservation_id).all()
    assert len(updated_facts) == 3
    assert sum(float(row.revenue_gross_ars) for row in updated_facts) == pytest.approx(470.0)


@pytest.mark.parametrize(
    ("operational_status", "room_status", "housekeeping_status"),
    [
        (
            ReservationStatusEnum.CHECKED_IN,
            RoomStatusEnum.OCCUPIED,
            RoomHousekeepingStatusEnum.CLEAN,
        ),
        (
            ReservationStatusEnum.CHECKED_OUT,
            RoomStatusEnum.CLEANING,
            RoomHousekeepingStatusEnum.DIRTY,
        ),
    ],
)
@pytest.mark.parametrize(
    "modification",
    [
        {"checkout": "2026-09-04"},
        {"room_type": "SUP_DBL"},
    ],
    ids=["stay-change", "room-category-change"],
)
def test_booking_modify_after_checkin_or_checkout_rejects_stay_or_room_changes(
    db,
    sample_rooms,
    sample_categories,
    hotel_config,
    operational_status,
    room_status,
    housekeeping_status,
    modification,
):
    secret = _seed_booking_secret(db, hotel_config.id)
    mapping = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    reservation = db.query(Reservation).filter_by(id=mapping.reservation_id).one()
    room = reservation.room
    original_room_id = reservation.room_id
    original_category_id = reservation.category_id
    original_check_in = reservation.check_in_date
    original_check_out = reservation.check_out_date
    reservation.status = operational_status
    room.status = room_status
    room.housekeeping_status = housekeeping_status
    db.flush()

    rejected_mapping = OTAIntegrationService.process_booking_webhook(
        db,
        hotel_config.id,
        secret,
        _booking_payload(
            event="reservation.modified",
            guest_name="Jane Changed",
            guest_email="jane.changed@example.com",
            **modification,
        ),
    )
    db.flush()
    db.refresh(reservation)
    db.refresh(room)
    link = db.query(OTAReservationLink).filter_by(
        hotel_id=hotel_config.id,
        external_reservation_id="BKG-LIFECYCLE-001",
    ).one()
    audit_entry = (
        db.query(AuditLog)
        .filter_by(
            hotel_id=hotel_config.id,
            table_name="reservations",
            record_id=reservation.id,
            action=AuditActionEnum.UPDATE,
        )
        .order_by(AuditLog.id.desc())
        .first()
    )

    assert rejected_mapping.id == mapping.id
    assert rejected_mapping.sync_status == OTASyncStatusEnum.CONFLICT
    assert rejected_mapping.error_message == (
        "Modification would change stay or room assignment after check-in/checkout"
    )
    assert reservation.status == operational_status
    assert reservation.check_in_date == original_check_in
    assert reservation.check_out_date == original_check_out
    assert reservation.room_id == original_room_id
    assert reservation.category_id == original_category_id
    assert reservation.requires_manual_review is True
    assert reservation.guest.first_name == "Jane"
    assert reservation.guest.last_name == "Doe"
    assert reservation.guest.email == "jane@example.com"
    assert link.provider_state == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED
    assert link.sync_status == "manual_resolution_required"
    assert audit_entry is not None
    assert "manual_review" in (audit_entry.payload_after or "")
    assert room.status == room_status
    assert room.housekeeping_status == housekeeping_status


def test_booking_modify_after_checkin_preserves_room_for_same_stay_and_category(
    db,
    sample_rooms,
    sample_categories,
    hotel_config,
):
    secret = _seed_booking_secret(db, hotel_config.id)
    mapping = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    reservation = db.query(Reservation).filter_by(id=mapping.reservation_id).one()
    room = reservation.room
    original_room_id = reservation.room_id
    reservation.status = ReservationStatusEnum.CHECKED_IN
    room.status = RoomStatusEnum.OCCUPIED
    db.flush()

    updated_mapping = OTAIntegrationService.process_booking_webhook(
        db,
        hotel_config.id,
        secret,
        _booking_payload(event="reservation.modified", total_price=470.0),
    )
    db.flush()
    db.refresh(reservation)
    db.refresh(room)

    assert updated_mapping.sync_status == OTASyncStatusEnum.SYNCED
    assert reservation.status == ReservationStatusEnum.CHECKED_IN
    assert reservation.room_id == original_room_id
    assert reservation.total_amount == 470.0
    assert room.status == RoomStatusEnum.OCCUPIED


@pytest.mark.parametrize("block_all_candidates", [False, True])
def test_booking_modify_rechecks_locked_room_and_falls_back_or_marks_conflict(
    db,
    sample_rooms,
    sample_categories,
    hotel_config,
    monkeypatch,
    block_all_candidates,
):
    secret = _seed_booking_secret(db, hotel_config.id)
    initial = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    reservation = db.query(Reservation).filter_by(id=initial.reservation_id).one()
    original_check_in = reservation.check_in_date
    original_check_out = reservation.check_out_date
    original_total_amount = reservation.total_amount
    original_guest_email = reservation.guest.email
    reservation.room_id = None
    db.flush()
    db.expire(reservation, ["room"])

    original_find_available_rooms = ota_service_module.find_available_rooms
    injected_competitors: list[int] = []

    def race_after_candidate_scan(*args, **kwargs):
        candidates = original_find_available_rooms(*args, **kwargs)
        if candidates and not injected_competitors:
            selected_candidates = candidates if block_all_candidates else candidates[:1]
            competitor = Guest(
                hotel_id=hotel_config.id,
                first_name="Race",
                last_name="Competitor",
            )
            db.add(competitor)
            db.flush()
            for candidate in selected_candidates:
                create_reservation(
                    db,
                    ReservationCreate(
                        guest_id=competitor.id,
                        category_id=candidate.category_id,
                        room_id=candidate.id,
                        check_in_date=date(2026, 9, 5),
                        check_out_date=date(2026, 9, 7),
                    ),
                    hotel_id=hotel_config.id,
                )
                injected_competitors.append(candidate.id)
        return candidates

    monkeypatch.setattr(ota_service_module, "find_available_rooms", race_after_candidate_scan)
    modified = OTAIntegrationService.process_booking_webhook(
        db,
        hotel_config.id,
        secret,
        _booking_payload(
            event="reservation.modified",
            checkin="2026-09-05",
            checkout="2026-09-07",
        ),
    )
    db.flush()
    db.refresh(reservation)

    assert injected_competitors
    if block_all_candidates:
        assert modified.sync_status == OTASyncStatusEnum.CONFLICT
        assert reservation.room_id is None
        assert reservation.requires_manual_review is True
        assert reservation.check_in_date == original_check_in
        assert reservation.check_out_date == original_check_out
        assert reservation.total_amount == original_total_amount
        assert reservation.guest.email == original_guest_email
    else:
        assert modified.sync_status == OTASyncStatusEnum.SYNCED
        assert reservation.room_id is not None
        assert reservation.room_id not in injected_competitors


def test_booking_modify_without_room_keeps_confirmed_stay_and_terms_unchanged(
    db,
    sample_rooms,
    sample_categories,
    hotel_config,
    monkeypatch,
):
    secret = _seed_booking_secret(db, hotel_config.id)
    mapping = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    reservation = db.query(Reservation).filter_by(id=mapping.reservation_id).one()
    original = {
        "check_in": reservation.check_in_date,
        "check_out": reservation.check_out_date,
        "room_id": reservation.room_id,
        "category_id": reservation.category_id,
        "total_amount": reservation.total_amount,
        "currency_code": reservation.currency_code,
        "guest_name": (reservation.guest.first_name, reservation.guest.last_name),
        "guest_email": reservation.guest.email,
    }

    competitor = Guest(hotel_id=hotel_config.id, first_name="Existing", last_name="Occupant")
    db.add(competitor)
    db.flush()
    create_reservation(
        db,
        ReservationCreate(
            guest_id=competitor.id,
            category_id=reservation.category_id,
            room_id=reservation.room_id,
            check_in_date=date(2026, 9, 5),
            check_out_date=date(2026, 9, 7),
        ),
        hotel_id=hotel_config.id,
    )
    monkeypatch.setattr(ota_service_module, "find_available_rooms", lambda *args, **kwargs: [])

    conflict = OTAIntegrationService.process_booking_webhook(
        db,
        hotel_config.id,
        secret,
        _booking_payload(
            event="reservation.modified",
            guest_name="Jane Changed",
            guest_email="jane.changed@example.com",
            checkin="2026-09-05",
            checkout="2026-09-07",
            total_price=470.0,
        ),
    )
    db.flush()
    db.refresh(reservation)

    assert conflict.sync_status == OTASyncStatusEnum.CONFLICT
    assert conflict.error_message == (
        "OTA modification rejected: no compatible room is available; "
        "resolve the change in the provider extranet"
    )
    assert reservation.requires_manual_review is True
    assert reservation.check_in_date == original["check_in"]
    assert reservation.check_out_date == original["check_out"]
    assert reservation.room_id == original["room_id"]
    assert reservation.category_id == original["category_id"]
    assert reservation.total_amount == original["total_amount"]
    assert reservation.currency_code == original["currency_code"]
    assert (reservation.guest.first_name, reservation.guest.last_name) == original["guest_name"]
    assert reservation.guest.email == original["guest_email"]


def test_booking_modify_rechecks_current_room_after_lock_and_reassigns_on_conflict(
    db,
    sample_rooms,
    sample_categories,
    hotel_config,
    monkeypatch,
):
    secret = _seed_booking_secret(db, hotel_config.id)
    initial = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    reservation = db.query(Reservation).filter_by(id=initial.reservation_id).one()
    originally_assigned_room_id = reservation.room_id
    original_check_room_availability = reservation_service_module.check_room_availability
    competitor_reservation_ids: list[int] = []

    def race_after_current_room_precheck(*args, **kwargs):
        available_before_lock = original_check_room_availability(*args, **kwargs)
        if (
            available_before_lock
            and kwargs.get("exclude_reservation_id") == reservation.id
            and not competitor_reservation_ids
        ):
            competitor = Guest(
                hotel_id=hotel_config.id,
                first_name="Race",
                last_name="Competitor",
            )
            db.add(competitor)
            db.flush()
            competing_reservation = create_reservation(
                db,
                ReservationCreate(
                    guest_id=competitor.id,
                    category_id=reservation.category_id,
                    room_id=originally_assigned_room_id,
                    check_in_date=date(2026, 9, 5),
                    check_out_date=date(2026, 9, 7),
                ),
                hotel_id=hotel_config.id,
            )
            competitor_reservation_ids.append(competing_reservation.id)
        return available_before_lock

    monkeypatch.setattr(
        reservation_service_module,
        "check_room_availability",
        race_after_current_room_precheck,
    )
    modified = OTAIntegrationService.process_booking_webhook(
        db,
        hotel_config.id,
        secret,
        _booking_payload(
            event="reservation.modified",
            checkin="2026-09-05",
            checkout="2026-09-07",
        ),
    )
    db.flush()
    db.refresh(reservation)

    assert competitor_reservation_ids
    assert modified.sync_status == OTASyncStatusEnum.SYNCED
    assert reservation.room_id is not None
    assert reservation.room_id != originally_assigned_room_id


def test_booking_cancel_cancels_existing_pre_checkin_reservation(db, sample_rooms, sample_categories, hotel_config):
    secret = _seed_booking_secret(db, hotel_config.id)
    mapping = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    db.flush()
    payment_link = PaymentLink(
        hotel_id=hotel_config.id,
        reservation_id=mapping.reservation_id,
        link_code="ota-cancel-open-link",
        requested_amount=100,
        recipient_email="ota-guest@example.test",
        provider="mercado_pago",
        status="pending",
        execution_mode="provider",
        payable=True,
        external_checkout_url="https://mp.test/ota-cancel-open-link",
    )
    db.add(payment_link)
    db.flush()

    cancelled_mapping = OTAIntegrationService.process_booking_webhook(
        db,
        hotel_config.id,
        secret,
        _booking_payload(event="reservation.cancelled"),
    )
    db.flush()

    reservation = db.query(Reservation).filter(Reservation.id == mapping.reservation_id).one()
    link = db.query(OTAReservationLink).filter_by(
        hotel_id=hotel_config.id,
        external_reservation_id="BKG-LIFECYCLE-001",
    ).one()

    assert cancelled_mapping.id == mapping.id
    assert reservation.status == ReservationStatusEnum.CANCELLED
    assert reservation.allocation_status == "cancelled"
    assert cancelled_mapping.sync_status == OTASyncStatusEnum.SYNCED
    assert link.provider_state == OTAReservationLifecycleEnum.CANCELLED
    assert payment_link.status == "cancelled"
    assert payment_link.payable is False


def test_booking_cancel_with_confirmed_external_payment_requires_settlement_review(
    db, sample_rooms, sample_categories, hotel_config
):
    secret = _seed_booking_secret(db, hotel_config.id)
    mapping = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    reservation = db.query(Reservation).filter(Reservation.id == mapping.reservation_id).one()
    reservation.external_paid_amount = 90
    reservation.external_paid_confirmed = True
    reservation.external_paid_ever_confirmed = True
    reservation.amount_paid = 90
    db.flush()

    cancelled_mapping = OTAIntegrationService.process_booking_webhook(
        db,
        hotel_config.id,
        secret,
        _booking_payload(event="reservation.cancelled"),
    )

    db.refresh(reservation)
    assert cancelled_mapping.sync_status == OTASyncStatusEnum.SYNCED
    assert reservation.status == ReservationStatusEnum.CANCELLED
    assert reservation.requires_manual_review is True
    assert reservation.settlement_status == "review_cancellation"


def test_booking_cancel_after_checkin_requires_manual_resolution(db, sample_rooms, sample_categories, hotel_config):
    secret = _seed_booking_secret(db, hotel_config.id)
    mapping = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    reservation = db.query(Reservation).filter(Reservation.id == mapping.reservation_id).one()
    transition_reservation_status(db, reservation, ReservationStatusEnum.FULLY_PAID, hotel_id=hotel_config.id)
    transition_reservation_status(db, reservation, ReservationStatusEnum.CHECKED_IN, hotel_id=hotel_config.id)
    db.flush()

    cancelled_mapping = OTAIntegrationService.process_booking_webhook(
        db,
        hotel_config.id,
        secret,
        _booking_payload(event="reservation.cancelled"),
    )
    db.flush()

    db.refresh(reservation)
    link = db.query(OTAReservationLink).filter_by(
        hotel_id=hotel_config.id,
        external_reservation_id="BKG-LIFECYCLE-001",
    ).one()

    assert reservation.status == ReservationStatusEnum.CHECKED_IN
    assert reservation.requires_manual_review is True
    assert reservation.allocation_status == "manual_review"
    assert reservation.settlement_status == "manual_resolution_required"
    assert cancelled_mapping.sync_status == OTASyncStatusEnum.CONFLICT
    assert link.provider_state == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED


def test_duplicate_booking_webhook_does_not_duplicate_reservation_or_guest(db, sample_rooms, sample_categories, hotel_config):
    secret = _seed_booking_secret(db, hotel_config.id)
    OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    db.flush()

    assert db.query(OTAReservationMapping).filter_by(
        hotel_id=hotel_config.id,
        ota_name="booking",
        ota_reservation_id="BKG-LIFECYCLE-001",
    ).count() == 1
    assert db.query(Reservation).filter_by(
        hotel_id=hotel_config.id,
        external_id="BKG-LIFECYCLE-001",
    ).count() == 1
    assert db.query(Guest).filter_by(
        hotel_id=hotel_config.id,
        email="jane@example.com",
    ).count() == 1
