"""Forward tests for the scalable data-architecture specialist workflow.

These are intentionally two independent, end-to-end contracts. They protect
the two failure modes the specialist must catch before a change is considered
safe: a hotel context accidentally seeing another hotel's entity, and a
reservation being persisted from a quote that no longer matches the tariff.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import func

from app.models.daily_rate import DailyRate
from app.models.reservation import Reservation
from app.schemas.reservation import ReservationCreate
from app.services.reservation_quote_service import build_reservation_quote
from app.services.reservation_service import ReservationError, create_reservation
from app.services.security import hash_password

from tests.test_multi_hotel_isolation_contracts import (
    _seed_hotel_payload,
    _seed_membership,
    _set_auth_context_override,
    isolated_client,
)


def test_forward_multi_hotel_context_cannot_read_or_attach_foreign_entities(isolated_client):
    """A valid entity id from hotel 2 cannot cross hotel 1's API boundary."""

    client, db = isolated_client
    from app.models.user import User

    user = User(
        email="forward-owner@test.com",
        password_hash=hash_password("forward-pass"),
        role="owner",
        is_verified=True,
    )
    db.add(user)
    db.flush()

    hotel_one = _seed_hotel_payload(db, 1, "FORWARD-H1", "101", "FORWARD-H1-RES")
    hotel_two = _seed_hotel_payload(db, 2, "FORWARD-H2", "201", "FORWARD-H2-RES")
    _seed_membership(db, hotel_one["hotel"].id, user.id, "owner")
    db.commit()
    _set_auth_context_override(hotel_one["hotel"].id, user.id, user.email, "owner")

    foreign_detail = client.get(f"/api/reservations/{hotel_two['reservation'].id}")
    assert foreign_detail.status_code == 404, foreign_detail.text

    foreign_room_update = client.patch(
        f"/api/bookings/{hotel_one['reservation'].id}",
        json={"room_id": hotel_two["room"].id},
    )
    assert foreign_room_update.status_code in {400, 404}, foreign_room_update.text

    db.expire_all()
    persisted = db.get(Reservation, hotel_one["reservation"].id)
    assert persisted is not None
    assert persisted.room_id == hotel_one["room"].id


def test_forward_stale_tariff_quote_cannot_persist_reservation(
    db, sample_categories, sample_rooms, sample_guest, hotel_config
):
    """A tariff revision change invalidates the quote before any write."""

    category = sample_categories[0]
    check_in = date(2030, 2, 10)
    check_out = check_in + timedelta(days=2)
    quote = build_reservation_quote(
        db,
        hotel_id=hotel_config.id,
        category_id=category.id,
        check_in_date=check_in,
        check_out_date=check_out,
        occupancy=2,
    )
    assert quote["quote_token"]

    db.add(DailyRate(hotel_id=hotel_config.id, category_id=category.id, date=check_in, price=999.0))
    db.flush()
    before_count = db.query(func.count(Reservation.id)).scalar()

    with pytest.raises(ReservationError, match="venció"):
        create_reservation(
            db,
            ReservationCreate(
                guest_id=sample_guest.id,
                category_id=category.id,
                room_id=sample_rooms[0].id,
                check_in_date=check_in,
                check_out_date=check_out,
                num_adults=2,
                quote_token=quote["quote_token"],
            ),
            hotel_id=hotel_config.id,
        )

    assert db.query(func.count(Reservation.id)).scalar() == before_count
