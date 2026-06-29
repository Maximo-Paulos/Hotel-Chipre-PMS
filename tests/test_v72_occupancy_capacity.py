from datetime import date

import pytest

from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.services.reservation_service import (
    ReservationError,
    create_reservation,
    update_reservation_fields,
)


def test_create_reservation_rejects_guest_total_above_category_capacity(
    db,
    sample_guest,
    sample_categories,
    sample_rooms,
):
    data = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 3, 1),
        check_out_date=date(2026, 3, 3),
        num_adults=2,
        num_children=1,
    )

    with pytest.raises(ReservationError, match="admite hasta 2.*solicitaron 3"):
        create_reservation(db, data, hotel_id=1)


def test_create_reservation_allows_guest_total_at_category_capacity(
    db,
    sample_guest,
    sample_categories,
    sample_rooms,
):
    data = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 3, 5),
        check_out_date=date(2026, 3, 7),
        num_adults=1,
        num_children=1,
    )

    reservation = create_reservation(db, data, hotel_id=1)

    assert reservation.num_adults == 1
    assert reservation.num_children == 1
    assert reservation.category_id == sample_categories[0].id


def test_create_reservation_rejects_zero_guest_total(
    db,
    sample_guest,
    sample_categories,
    sample_rooms,
):
    data = ReservationCreate.model_construct(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=None,
        sellable_product_id=None,
        rate_plan_id=None,
        tax_policy_id=None,
        company_id=None,
        check_in_date=date(2026, 3, 10),
        check_out_date=date(2026, 3, 12),
        num_adults=0,
        num_children=0,
        notes=None,
    )

    with pytest.raises(ReservationError, match="al menos 1"):
        create_reservation(db, data, hotel_id=1)


def test_update_reservation_rejects_guest_total_above_category_capacity(
    db,
    sample_guest,
    sample_categories,
    sample_rooms,
):
    data = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 3, 15),
        check_out_date=date(2026, 3, 17),
        num_adults=1,
        num_children=0,
    )
    reservation = create_reservation(db, data, hotel_id=1)

    with pytest.raises(ReservationError, match="admite hasta 2.*solicitaron 3"):
        update_reservation_fields(
            db,
            reservation,
            ReservationUpdate(num_adults=2, num_children=1),
            hotel_id=1,
        )
