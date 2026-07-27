from decimal import Decimal

import pytest

from app.models.hotel_config import HotelConfiguration
from app.services.stock_service import (
    StockError,
    create_location,
    create_stock_item,
    current_stock,
    delete_stock_item,
    list_stock_movements,
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


def test_stock_outbound_cannot_make_quantity_negative(db):
    _seed_hotels(db)
    item = create_stock_item(
        db,
        hotel_id=1,
        name="Linen",
        sku=None,
        unit="unit",
        min_quantity=None,
        active=True,
    )
    register_movement(
        db,
        hotel_id=1,
        item_id=item.id,
        location_id=None,
        movement_type="in",
        quantity=Decimal("2.00"),
        reason="opening balance",
        reservation_id=None,
        created_by_user_id=None,
    )

    with pytest.raises(StockError, match="negative"):
        register_movement(
            db,
            hotel_id=1,
            item_id=item.id,
            location_id=None,
            movement_type="out",
            quantity=Decimal("3.00"),
            reason="consumption",
            reservation_id=None,
            created_by_user_id=None,
        )


def test_stock_movement_history_is_hotel_scoped_newest_first_and_limited(db):
    _seed_hotels(db)
    item = create_stock_item(
        db,
        hotel_id=1,
        name="Amenities",
        sku=None,
        unit="unit",
        min_quantity=None,
        active=True,
    )
    other_item = create_stock_item(
        db,
        hotel_id=2,
        name="Amenities",
        sku=None,
        unit="unit",
        min_quantity=None,
        active=True,
    )
    db.flush()

    first = register_movement(
        db,
        hotel_id=1,
        item_id=item.id,
        location_id=None,
        movement_type="in",
        quantity=Decimal("5.00"),
        reason="opening balance",
        reservation_id=None,
        created_by_user_id=None,
    )
    latest = register_movement(
        db,
        hotel_id=1,
        item_id=item.id,
        location_id=None,
        movement_type="out",
        quantity=Decimal("2.00"),
        reason="room consumption",
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

    history = list_stock_movements(db, hotel_id=1, item_id=item.id, limit=20)

    assert [movement.id for movement in history] == [latest.id, first.id]
    assert [movement.id for movement in list_stock_movements(db, hotel_id=1, item_id=None, limit=1)] == [latest.id]


def test_stock_adjustment_can_correct_quantity_downward(db):
    _seed_hotels(db)
    item = create_stock_item(
        db,
        hotel_id=1,
        name="Sabanas",
        sku=None,
        unit="unit",
        min_quantity=None,
        active=True,
    )
    register_movement(
        db,
        hotel_id=1,
        item_id=item.id,
        location_id=None,
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
        location_id=None,
        movement_type="adjustment_out",
        quantity=Decimal("3.00"),
        reason="physical count found fewer units",
        reservation_id=None,
        created_by_user_id=None,
    )

    assert current_stock(db, hotel_id=1, item_id=item.id) == Decimal("7.00")


def test_stock_adjustment_downward_cannot_make_quantity_negative(db):
    _seed_hotels(db)
    item = create_stock_item(
        db,
        hotel_id=1,
        name="Frazadas",
        sku=None,
        unit="unit",
        min_quantity=None,
        active=True,
    )
    register_movement(
        db,
        hotel_id=1,
        item_id=item.id,
        location_id=None,
        movement_type="in",
        quantity=Decimal("2.00"),
        reason="opening balance",
        reservation_id=None,
        created_by_user_id=None,
    )

    with pytest.raises(StockError, match="negative"):
        register_movement(
            db,
            hotel_id=1,
            item_id=item.id,
            location_id=None,
            movement_type="adjustment_out",
            quantity=Decimal("5.00"),
            reason="conteo",
            reservation_id=None,
            created_by_user_id=None,
        )


def test_current_stock_location_filter_is_additive_and_hotel_wide_total_unchanged(db):
    """D1: current_stock(location_id=...) narrows the balance to one location;
    omitting it must keep returning the old hotel-wide total (no regression
    for any existing caller that never passes the parameter)."""
    _seed_hotels(db)
    item = create_stock_item(db, hotel_id=1, name="Sabanas", sku=None, unit="unit", min_quantity=None, active=True)
    house = create_location(db, hotel_id=1, name="Deposito casa")
    vendor_location = create_location(db, hotel_id=1, name="Lavadero X")
    db.flush()

    register_movement(
        db, hotel_id=1, item_id=item.id, location_id=house.id, movement_type="in",
        quantity=Decimal("10.00"), reason="opening balance", reservation_id=None, created_by_user_id=None,
    )
    register_movement(
        db, hotel_id=1, item_id=item.id, location_id=house.id, movement_type="out",
        quantity=Decimal("4.00"), reason="sent to laundry", reservation_id=None, created_by_user_id=None,
    )
    register_movement(
        db, hotel_id=1, item_id=item.id, location_id=vendor_location.id, movement_type="in",
        quantity=Decimal("4.00"), reason="received by laundry", reservation_id=None, created_by_user_id=None,
    )
    db.commit()

    # Hotel-wide total (no location_id) still adds up across every location.
    assert current_stock(db, hotel_id=1, item_id=item.id) == Decimal("10.00")
    # Per-location balances split the same total correctly.
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=house.id) == Decimal("6.00")
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=vendor_location.id) == Decimal("4.00")


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


def test_stock_item_name_can_be_reused_after_delete(db):
    """Owner-reported bug: deleting an item ("producto que ya no se usa") is
    a soft delete, so a plain per-hotel unique-name constraint kept the name
    reserved forever. Recreating a replacement item under the same name
    ("producto que cambio") must succeed, not raise an unhandled 500."""
    _seed_hotels(db)
    item = create_stock_item(db, hotel_id=1, name="Detergente", unit="unidad")
    db.commit()

    delete_stock_item(db, hotel_id=1, item_id=item.id)
    db.commit()

    replacement = create_stock_item(db, hotel_id=1, name="Detergente", unit="unidad")
    db.commit()

    assert replacement.id != item.id
    assert [stock_item.id for stock_item in list_stock_items(db, hotel_id=1)] == [replacement.id]


def test_stock_item_active_duplicate_name_raises_clean_error(db):
    """A real (non-deleted) duplicate must still be rejected -- with a clean
    StockError, not a raw IntegrityError leaking out as a 500."""
    _seed_hotels(db)
    create_stock_item(db, hotel_id=1, name="Detergente", unit="unidad")
    db.commit()

    with pytest.raises(StockError, match="Detergente"):
        create_stock_item(db, hotel_id=1, name="Detergente", unit="unidad")

    # The session must still be usable after the failed insert (SAVEPOINT
    # rollback, not a whole-transaction rollback).
    assert len(list_stock_items(db, hotel_id=1)) == 1


def test_stock_item_kind_defaults_to_supply_and_filters(db):
    """D (stock/lavanderia separation): StockPage only ever wants
    kind='supply' (bolsas, detergentes, jabon); LaundryPage only wants
    kind='linen' (ropa blanca)."""
    _seed_hotels(db)
    supply = create_stock_item(db, hotel_id=1, name="Bolsas de residuos", unit="unidad")
    linen = create_stock_item(db, hotel_id=1, name="Sabanas", unit="unidad", kind="linen")
    db.commit()

    assert supply.kind == "supply"
    assert linen.kind == "linen"
    assert [i.id for i in list_stock_items(db, hotel_id=1, kind="supply")] == [supply.id]
    assert [i.id for i in list_stock_items(db, hotel_id=1, kind="linen")] == [linen.id]
    assert {i.id for i in list_stock_items(db, hotel_id=1)} == {supply.id, linen.id}

    with pytest.raises(StockError):
        create_stock_item(db, hotel_id=1, name="Invalido", unit="unidad", kind="not-a-kind")
