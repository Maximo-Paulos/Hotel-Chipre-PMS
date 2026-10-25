"""Reservation-level review for changes to mutable company configuration."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.company import Company
from app.models.reservation_company_terms_review import ReservationCompanyTermsReview
from app.models.reservation import ReservationStatusEnum
from app.models.user import User
from app.schemas.reservation import ReservationCreate
from app.services.company_reservation_terms import get_company_terms_review_state
from app.services.company_reservation_terms_service import (
    CompanyTermsReviewConflict,
    CompanyTermsReviewNotFound,
    get_company_terms_review,
    review_company_reservation_terms,
)
from app.services.reservation_service import create_reservation


def _seed_company_reservation(db, *, hotel_id, guest, category, room):
    company = Company(
        hotel_id=hotel_id,
        legal_name=f"Terms QA {hotel_id} SA",
        display_name=f"Terms QA {hotel_id}",
        tax_id=f"terms-qa-{hotel_id}",
        contact_name="QA contact",
        contact_email=f"terms-{hotel_id}@example.test",
        contact_phone="+541100000000",
        payment_deferred=False,
        deferred_days=0,
        requires_voucher=False,
        requires_signature=False,
        base_price=Decimal("100.00"),
        extra_person_nightly_surcharge=Decimal("0.00"),
    )
    db.add(company)
    db.flush()
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=guest.id,
            category_id=category.id,
            room_id=room.id,
            company_id=company.id,
            check_in_date=date(2035, 5, 10),
            check_out_date=date(2035, 5, 12),
        ),
        hotel_id=hotel_id,
    )
    actor = User(
        email=f"manager-{hotel_id}@example.test",
        password_hash="test-hash",
        is_active=True,
        is_verified=True,
    )
    db.add(actor)
    db.flush()
    return company, reservation, actor


def test_company_terms_change_is_reviewed_without_silently_rewriting_booking(
    db, hotel_config, sample_guest, sample_rooms, sample_categories
):
    company, reservation, actor = _seed_company_reservation(
        db, hotel_id=hotel_config.id, guest=sample_guest, category=sample_categories[0], room=sample_rooms[0]
    )
    original_snapshot = reservation.company_terms_snapshot
    original_total = Decimal(str(reservation.total_amount))
    company.requires_voucher = True
    db.flush()

    state, events = get_company_terms_review(db, hotel_id=hotel_config.id, reservation_id=reservation.id)

    assert state["status"] == "hold_for_manager_review"
    assert state["needs_review"] is True
    assert state["blocks_checkin"] is True
    assert state["changed_fields"] == ["requires_voucher"]
    assert events == []

    reviewed, event = review_company_reservation_terms(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        actor_user_id=actor.id,
        action="keep_snapshot",
        reason="La empresa confirmó el acuerdo original.",
        expected_config_fingerprint=state["current_fingerprint"],
        idempotency_key=uuid4(),
    )

    assert reviewed["status"] == "manager_kept_snapshot"
    assert reviewed["needs_review"] is False
    assert reservation.company_terms_snapshot == original_snapshot
    assert Decimal(str(reservation.total_amount)) == original_total
    assert event.changed_fields == ["requires_voucher"]
    assert db.query(ReservationCompanyTermsReview).count() == 1


def test_manager_accepts_current_terms_without_repricing_and_retry_is_idempotent(
    db, hotel_config, sample_guest, sample_rooms, sample_categories
):
    company, reservation, actor = _seed_company_reservation(
        db, hotel_id=hotel_config.id, guest=sample_guest, category=sample_categories[0], room=sample_rooms[0]
    )
    company.payment_deferred = True
    company.deferred_days = 45
    db.flush()
    state = get_company_terms_review_state(db, reservation, hotel_id=hotel_config.id, company=company)
    original_total = Decimal(str(reservation.total_amount))
    original_economics = reservation.company_terms_snapshot["applied_economics"]
    idempotency_key = uuid4()
    args = {
        "db": db,
        "hotel_id": hotel_config.id,
        "reservation_id": reservation.id,
        "actor_user_id": actor.id,
        "action": "accept_current",
        "reason": "Gerencia confirmó el pago diferido actualizado.",
        "expected_config_fingerprint": state["current_fingerprint"],
        "idempotency_key": idempotency_key,
    }

    reviewed, event = review_company_reservation_terms(**args)
    retried, retry_event = review_company_reservation_terms(**args)

    assert reviewed["status"] == "manager_accepted_current"
    assert reviewed["needs_review"] is False
    assert retried["needs_review"] is False
    assert retry_event.id == event.id
    assert db.query(ReservationCompanyTermsReview).count() == 1
    assert reservation.settlement_status == "deferred"
    assert reservation.settlement_due_date == date(2035, 6, 26)
    assert Decimal(str(reservation.total_amount)) == original_total
    assert reservation.company_terms_snapshot["applied_economics"] == original_economics


def test_stale_company_config_requires_manager_to_reload_before_deciding(
    db, hotel_config, sample_guest, sample_rooms, sample_categories
):
    company, reservation, actor = _seed_company_reservation(
        db, hotel_id=hotel_config.id, guest=sample_guest, category=sample_categories[0], room=sample_rooms[0]
    )
    stale_state = get_company_terms_review_state(db, reservation, hotel_id=hotel_config.id, company=company)
    company.requires_signature = True
    db.flush()

    with pytest.raises(CompanyTermsReviewConflict, match="cambió"):
        review_company_reservation_terms(
            db,
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
            actor_user_id=actor.id,
            action="accept_current",
            reason="Revisar la nueva configuración.",
            expected_config_fingerprint=stale_state["current_fingerprint"],
            idempotency_key=uuid4(),
        )

    assert db.query(ReservationCompanyTermsReview).count() == 0


def test_legacy_reservation_without_snapshot_cannot_claim_to_keep_unknown_terms(
    db, hotel_config, sample_guest, sample_rooms, sample_categories
):
    company, reservation, actor = _seed_company_reservation(
        db, hotel_id=hotel_config.id, guest=sample_guest, category=sample_categories[0], room=sample_rooms[0]
    )
    reservation.company_terms_snapshot = None
    reservation.company_terms_reviewed_config = None
    db.flush()
    state = get_company_terms_review_state(db, reservation, hotel_id=hotel_config.id, company=company)
    assert state["status"] == "snapshot_missing"
    assert state["blocks_checkin"] is True

    with pytest.raises(CompanyTermsReviewConflict, match="no conserva una copia histórica"):
        review_company_reservation_terms(
            db,
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
            actor_user_id=actor.id,
            action="keep_snapshot",
            reason="Intento de conservar algo que no fue guardado.",
            expected_config_fingerprint=state["current_fingerprint"],
            idempotency_key=uuid4(),
        )

    resolved, _ = review_company_reservation_terms(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        actor_user_id=actor.id,
        action="accept_current",
        reason="Gerencia aceptó explícitamente las condiciones vigentes.",
        expected_config_fingerprint=state["current_fingerprint"],
        idempotency_key=uuid4(),
    )
    assert resolved["status"] == "manager_accepted_current"
    assert resolved["needs_review"] is False


def test_company_terms_review_does_not_disclose_reservation_across_hotels(
    db, hotel_config, sample_guest, sample_rooms, sample_categories
):
    _company, reservation, _actor = _seed_company_reservation(
        db, hotel_id=hotel_config.id, guest=sample_guest, category=sample_categories[0], room=sample_rooms[0]
    )

    with pytest.raises(CompanyTermsReviewNotFound):
        get_company_terms_review(db, hotel_id=hotel_config.id + 1, reservation_id=reservation.id)


@pytest.mark.parametrize(
    "terminal_status",
    [ReservationStatusEnum.CANCELLED, ReservationStatusEnum.NO_SHOW, ReservationStatusEnum.CHECKED_OUT],
)
def test_company_terms_review_rejects_closed_reservations_without_mutation(
    db, hotel_config, sample_guest, sample_rooms, sample_categories, terminal_status
):
    company, reservation, actor = _seed_company_reservation(
        db, hotel_id=hotel_config.id, guest=sample_guest, category=sample_categories[0], room=sample_rooms[0]
    )
    reservation.status = terminal_status
    db.flush()
    original_snapshot = reservation.company_terms_snapshot
    original_settlement_status = reservation.settlement_status
    state = get_company_terms_review_state(db, reservation, hotel_id=hotel_config.id, company=company)

    with pytest.raises(CompanyTermsReviewConflict, match="reserva cerrada"):
        review_company_reservation_terms(
            db,
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
            actor_user_id=actor.id,
            action="accept_current",
            reason="No debe modificar una reserva cerrada.",
            expected_config_fingerprint=state["current_fingerprint"],
            idempotency_key=uuid4(),
        )

    assert reservation.company_terms_snapshot == original_snapshot
    assert reservation.settlement_status == original_settlement_status
    assert db.query(ReservationCompanyTermsReview).filter_by(reservation_id=reservation.id).count() == 0
