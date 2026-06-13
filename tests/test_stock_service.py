from decimal import Decimal

import pytest

from app.models.hotel_config import HotelConfiguration
from app.services.stock_service import (
    StockError,
    create_location,
    create_stock_item,
    current_stock,
    list_stock_items,
    low_stock_items,
    register_movement,
)


def _seed_hotels(db):
    db.add_all([
        HotelConfiguration(id=1, subscription_active=True),
        HotelConfiguration(id=2, subscription_active=True),
    ])
    db.flush()


def test_stock_item_and_movement_are_hotel_scoped(db):
    _seed_hotels(db)

    item = create_stock_item(
        db,
        hotel_id=1,
        name="Towels",
        sku="TOWEL",
        unit="unit",
        min_quantity=Decimal("5.00"),
        active=True,
    )
    location = create_location(db, hotel_id=1, name="Laundry closet")
    other_item = create_stock_item(
        db,
        hotel_id=2,
        name="Towels",
        sku="TOWEL-H2",
        unit="unit",
        min_quantity=Decimal("5.00"),
        active=True,
    )
    db.flush()

    register_movement(
        db,
        hotel_id=1,
        item_id=item.id,
        location_id=location.id,
        movement_type="in",
        quantity=Decimal("10.00"),
        reason="opening balance",
        reservation_id=None,
        created_by_user_id=None,
    )
    register_movement(
        db,
        hotel_id=1,
        item_id=item.id,
        location_id=location.id,
        movement_type="out",
        quantity=Decimal("3.00"),
        reason="room service",
        reservation_id=None,
        created_by_user_id=None,
    )
    register_movement(
        db,
        hotel_id=2,
        item_id=other_item.id,
        location_id=None,
        movement_type="in",
        quantity=Decimal("99.00"),
        reason="other hotel",
        reservation_id=None,
        created_by_user_id=None,
    )
    db.commit()

    assert [stock_item.id for stock_item in list_stock_items(db, hotel_id=1)] == [item.id]
    assert current_stock(db, hotel_id=1, item_id=item.id) == Decimal("7.00")
    assert current_stock(db, hotel_id=2, item_id=other_item.id) == Decimal("99.00")

    with pytest.raises(StockError):
        current_stock(db, hotel_id=1, item_id=other_item.id)


def test_stock_movement_requires_positive_quantity(db):
    _seed_hotels(db)
    item = create_stock_item(
        db,
        hotel_id=1,
        name="Soap",
        sku=None,
        unit="unit",
        min_quantity=None,
        active=True,
    )
    db.flush()

    with pytest.raises(StockError):
        register_movement(
            db,
            hotel_id=1,
            item_id=item.id,
            location_id=None,
            movement_type="in",
            quantity=Decimal("0"),
            reason=None,
            reservation_id=None,
            created_by_user_id=None,
        )


def test_low_stock_items_are_hotel_scoped(db):
    _seed_hotels(db)
    item = create_stock_item(
        db,
        hotel_id=1,
        name="Shampoo",
        sku=None,
        unit="bottle",
        min_quantity=Decimal("3.00"),
        active=True,
    )
    other_item = create_stock_item(
        db,
        hotel_id=2,
        name="Shampoo",
        sku=None,
        unit="bottle",
        min_quantity=Decimal("3.00"),
        active=True,
    )
    db.flush()
    register_movement(
        db,
        hotel_id=2,
        item_id=other_item.id,
        location_id=None,
        movement_type="in",
        quantity=Decimal("10.00"),
        reason=None,
        reservation_id=None,
        created_by_user_id=None,
    )
    db.commit()

    assert [stock_item.id for stock_item in low_stock_items(db, hotel_id=1)] == [item.id]
    assert low_stock_items(db, hotel_id=2) == []
