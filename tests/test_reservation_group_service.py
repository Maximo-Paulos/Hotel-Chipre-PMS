"""Atomic multi-room reservation grouping and aggregate balance contracts."""

from datetime import date, timedelta

import pytest

from app.models.company import Company
from app.models.reservation import Reservation
from app.models.reservation_group import ReservationGroup
from app.schemas.reservation import ReservationCreate
from app.services.reservation_group_service import create_reservation_group, list_reservation_groups
from app.services.reservation_quote_service import build_reservation_quote
from app.services.reservation_service import ReservationError


def _group_payloads(db, *, guest_id: int, category_id: int, company_id: int | None, count: int = 4):
    check_in = date(2030, 1, 10)
    check_out = check_in + timedelta(days=2)
    quote = build_reservation_quote(
        db,
        hotel_id=1,
        category_id=category_id,
        check_in_date=check_in,
        check_out_date=check_out,
        occupancy=2,
        company_id=company_id,
    )
    return [
        ReservationCreate(
            guest_id=guest_id,
            category_id=category_id,
            company_id=company_id,
            check_in_date=check_in,
            check_out_date=check_out,
            num_adults=2,
            quote_token=quote["quote_token"],
        )
        for _ in range(count)
    ]


def test_create_four_room_company_group_and_aggregate_summary(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    company = Company(
        hotel_id=1,
        legal_name="Acme Travel SRL",
        display_name="Acme Travel",
        base_price=80,
        requires_voucher=True,
    )
    db.add(company)
    db.flush()
    payloads = _group_payloads(
        db,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        company_id=company.id,
    )

    group, reservations = create_reservation_group(
        db,
        hotel_id=1,
        reservations=payloads,
        actor_user_id=None,
        actor_role=None,
    )
    db.flush()

    assert len(reservations) == 4
    assert len({row.room_id for row in reservations}) == 4
    assert all(row.group_id == group.id and row.company_id == company.id for row in reservations)
    assert db.query(ReservationGroup).filter_by(hotel_id=1, id=group.id).count() == 1
    assert db.query(Reservation).filter_by(hotel_id=1, group_id=group.id).count() == 4

    summary = list_reservation_groups(db, hotel_id=1, group_id=group.id)[0]
    assert summary["guest_name"] == "Carlos Pérez"
    assert summary["company_name"] == "Acme Travel"
    assert summary["reservation_count"] == 4
    assert summary["room_count"] == 4
    assert summary["total_amount"] == 640
    assert summary["amount_paid"] == 0
    assert summary["balance_due"] == 640
    assert len(summary["reservation_codes"]) == 4


@pytest.mark.parametrize("count", [1, 11])
def test_group_rejects_room_count_outside_bounds(
    db, sample_guest, sample_rooms, sample_categories, hotel_config, count
):
    payloads = _group_payloads(
        db,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        company_id=None,
        count=max(count, 2),
    )
    if count == 1:
        payloads = payloads[:1]
    with pytest.raises(ReservationError, match="entre 2 y 10"):
        create_reservation_group(
            db,
            hotel_id=1,
            reservations=payloads,
            actor_user_id=None,
            actor_role=None,
        )
    assert db.query(ReservationGroup).count() == 0


def test_group_rejects_inconsistent_company_and_manual_totals(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    payloads = _group_payloads(
        db,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        company_id=None,
    )
    payloads[1] = payloads[1].model_copy(update={"notes": "different terms"})
    with pytest.raises(ReservationError, match="compartir huésped, empresa"):
        create_reservation_group(
            db,
            hotel_id=1,
            reservations=payloads,
            actor_user_id=None,
            actor_role=None,
        )

    payloads = _group_payloads(
        db,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        company_id=None,
    )
    payloads[0] = payloads[0].model_copy(update={"total_amount": 10})
    with pytest.raises(ReservationError, match="tarifa manual"):
        create_reservation_group(
            db,
            hotel_id=1,
            reservations=payloads,
            actor_user_id=None,
            actor_role=None,
        )
    assert db.query(ReservationGroup).count() == 0
