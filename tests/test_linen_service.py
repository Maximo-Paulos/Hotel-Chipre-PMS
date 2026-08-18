from decimal import Decimal

import pytest

from app.models.hotel_config import HotelConfiguration
from app.services.linen_service import (
    LinenError,
    create_linen_item,
    create_location,
    current_stock,
    linen_summary,
    register_movement,
)


def _seed_hotels(db):
    db.add_all([
        HotelConfiguration(id=1, subscription_active=True),
        HotelConfiguration(id=2, subscription_active=True),
    ])
    db.flush()


def test_linen_outbound_movement_is_checked_against_its_own_location_not_hotel_wide_total(db):
    """Same per-location bug as stock_service: an 'out' at location B must be
    validated against location B's own balance, not the hotel-wide total --
    otherwise stock that only exists at location A could be drawn down by a
    movement recorded at location B, which never actually had it."""
    _seed_hotels(db)
    item = create_linen_item(db, hotel_id=1, name="Sabanas", unit="unidad")
    house = create_location(db, hotel_id=1, name="Deposito casa")
    vendor_location = create_location(db, hotel_id=1, name="Lavadero X")
    db.flush()

    register_movement(
        db, hotel_id=1, item_id=item.id, location_id=house.id, movement_type="in",
        quantity=Decimal("10.00"), reason="opening balance", reservation_id=None, created_by_user_id=None,
    )
    db.commit()

    # Hotel-wide total is 10, but vendor_location has 0 -- an "out" there
    # must be rejected even though the hotel-wide total would cover it.
    with pytest.raises(LinenError, match="negative"):
        register_movement(
            db, hotel_id=1, item_id=item.id, location_id=vendor_location.id, movement_type="out",
            quantity=Decimal("3.00"), reason="bug: draws from house's balance", reservation_id=None,
            created_by_user_id=None,
        )

    # The house location's real balance must be untouched by the rejected attempt.
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=house.id) == Decimal("10.00")
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=vendor_location.id) == Decimal("0.00")


def test_linen_summary_returns_every_active_item_balance_in_one_call_hotel_scoped(db):
    _seed_hotels(db)
    item = create_linen_item(db, hotel_id=1, name="Toallas", unit="unidad")
    other_hotel_item = create_linen_item(db, hotel_id=2, name="Toallas", unit="unidad")
    house = create_location(db, hotel_id=1, name="Deposito")
    db.flush()

    register_movement(
        db, hotel_id=1, item_id=item.id, location_id=house.id, movement_type="in",
        quantity=Decimal("6.00"), reason=None, reservation_id=None, created_by_user_id=None,
    )
    register_movement(
        db, hotel_id=2, item_id=other_hotel_item.id, location_id=None, movement_type="in",
        quantity=Decimal("50.00"), reason=None, reservation_id=None, created_by_user_id=None,
    )
    db.commit()

    summary = linen_summary(db, hotel_id=1)
    assert len(summary) == 1
    assert summary[0]["item"].id == item.id
    assert summary[0]["current_quantity"] == Decimal("6.00")

    summary_at_house = linen_summary(db, hotel_id=1, location_id=house.id)
    assert summary_at_house[0]["current_quantity"] == Decimal("6.00")
