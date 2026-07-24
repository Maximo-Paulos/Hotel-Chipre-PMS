from datetime import date, timedelta
import json

import pytest

from app.models.daily_rate import DailyRate
from app.schemas.reservation import ReservationCreate
from app.services.pricing_service import build_pricing_revision
from app.services.quote_token_service import QuoteTokenError, issue_quote_token, verify_quote_token
from app.services.reservation_quote_service import build_reservation_quote
from app.services.reservation_service import ReservationError, create_reservation


def _quote(db, category_id: int):
    check_in = date(2030, 1, 10)
    check_out = check_in + timedelta(days=2)
    return build_reservation_quote(
        db,
        hotel_id=1,
        category_id=category_id,
        check_in_date=check_in,
        check_out_date=check_out,
        occupancy=2,
    )


def test_quote_token_is_signed_and_round_trips_without_pii():
    token = issue_quote_token({"hotel_id": 1, "category_id": 2, "pricing_revision": "abc"})
    payload = verify_quote_token(token)
    assert payload["hotel_id"] == 1
    assert payload["pricing_revision"] == "abc"
    assert "email" not in json.dumps(payload)

    with pytest.raises(QuoteTokenError, match="signature"):
        verify_quote_token(f"{token[:-1]}x")


def test_reservation_rejects_quote_after_pricing_revision_changes(
    db, sample_categories, sample_rooms, sample_guest, hotel_config
):
    category = sample_categories[0]
    quote = _quote(db, category.id)
    assert quote["quote_token"]

    db.add(
        DailyRate(
            hotel_id=1,
            category_id=category.id,
            date=date(2030, 1, 10),
            price=999.0,
        )
    )
    db.flush()

    payload = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=category.id,
        room_id=sample_rooms[0].id,
        check_in_date=date(2030, 1, 10),
        check_out_date=date(2030, 1, 12),
        num_adults=2,
        quote_token=quote["quote_token"],
    )
    with pytest.raises(ReservationError, match="venció"):
        create_reservation(db, payload, hotel_id=1)


def test_confirmed_reservation_stores_pricing_revision(
    db, sample_categories, sample_rooms, sample_guest, hotel_config
):
    category = sample_categories[0]
    quote = _quote(db, category.id)
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=category.id,
            room_id=sample_rooms[1].id,
            check_in_date=date(2030, 1, 10),
            check_out_date=date(2030, 1, 12),
            num_adults=2,
            quote_token=quote["quote_token"],
        ),
        hotel_id=1,
    )
    revision = build_pricing_revision(
        db,
        hotel_id=1,
        category_id=category.id,
        check_in=date(2030, 1, 10),
        check_out=date(2030, 1, 12),
        occupancy=2,
    )
    snapshot = json.loads(reservation.pricing_snapshot or "{}")
    assert snapshot["pricing_revision"] == revision
    assert snapshot["breakdown"]
