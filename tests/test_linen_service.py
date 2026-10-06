from decimal import Decimal

import pytest

from app.models.hotel_config import HotelConfiguration
from app.models.linen import LinenParLevel
from app.models.user import User
from app.services.linen_service import (
    LinenError,
    LinenIdempotencyConflict,
    create_linen_item,
    create_location,
    current_stock,
    linen_summary,
    register_movement,
    register_opening_counts,
    set_location_minimum,
    transfer_linen_stock,
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
    with pytest.raises(LinenError, match="negativo"):
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
    assert summary_at_house[0]["location_balances"] == [
        {"location_id": house.id, "current_quantity": Decimal("6.00"), "has_movements": True}
    ]


def test_linen_opening_count_batch_is_atomic_and_only_applies_before_location_history(db):
    _seed_hotels(db)
    db.add(User(id=10, email="linen-count@example.test", password_hash="test"))
    db.flush()
    first = create_linen_item(db, hotel_id=1, name="Sabanas", unit="unidad")
    second = create_linen_item(db, hotel_id=1, name="Toallas", unit="unidad")
    house = create_location(db, hotel_id=1, name="Deposito")
    floor = create_location(db, hotel_id=1, name="Office 2")
    db.flush()

    movements = register_opening_counts(
        db,
        hotel_id=1,
        counts=[
            {"linen_item_id": first.id, "location_id": house.id, "quantity": Decimal("12")},
            {"linen_item_id": first.id, "location_id": floor.id, "quantity": Decimal("3")},
            {"linen_item_id": second.id, "location_id": house.id, "quantity": Decimal("8")},
        ],
        reason="Conteo inicial D0",
        created_by_user_id=10,
    )
    db.commit()

    assert len(movements) == 3
    assert all(row.movement_type == "in" and row.reason == "Conteo inicial D0" for row in movements)
    assert all(row.created_by_user_id == 10 for row in movements)
    assert current_stock(db, hotel_id=1, item_id=first.id, location_id=house.id) == Decimal("12.00")
    assert current_stock(db, hotel_id=1, item_id=first.id, location_id=floor.id) == Decimal("3.00")

    # Any prior movement locks only that item/location cell, and rejects the
    # complete batch so the other cell cannot be partially recorded.
    with pytest.raises(LinenError, match="movimientos previos"):
        register_opening_counts(
            db,
            hotel_id=1,
            counts=[
                {"linen_item_id": first.id, "location_id": house.id, "quantity": Decimal("2")},
                {"linen_item_id": second.id, "location_id": floor.id, "quantity": Decimal("5")},
            ],
            reason="Reintento parcial",
            created_by_user_id=10,
        )
    assert current_stock(db, hotel_id=1, item_id=second.id, location_id=floor.id) == Decimal("0.00")


def test_linen_summary_marks_zero_balance_as_having_history(db):
    _seed_hotels(db)
    item = create_linen_item(db, hotel_id=1, name="Toallones", unit="unidad")
    house = create_location(db, hotel_id=1, name="Office 3")
    register_movement(
        db, hotel_id=1, item_id=item.id, location_id=house.id, movement_type="in",
        quantity=Decimal("4"), reason="carga", created_by_user_id=None,
    )
    register_movement(
        db, hotel_id=1, item_id=item.id, location_id=house.id, movement_type="out",
        quantity=Decimal("4"), reason="retiro", created_by_user_id=None,
    )
    db.commit()

    summary = linen_summary(db, hotel_id=1, location_id=house.id)
    assert summary[0]["current_quantity"] == Decimal("0.00")
    assert summary[0]["location_balances"] == [
        {"location_id": house.id, "current_quantity": Decimal("0.00"), "has_movements": True}
    ]


def test_linen_transfer_is_atomic_linked_and_idempotent(db):
    _seed_hotels(db)
    db.add(User(id=10, email="linen-transfer@example.test", password_hash="test"))
    db.flush()
    item = create_linen_item(db, hotel_id=1, name="Toallones", unit="unidad")
    source = create_location(db, hotel_id=1, name="Deposito")
    destination = create_location(db, hotel_id=1, name="Office 2")
    register_movement(
        db, hotel_id=1, item_id=item.id, location_id=source.id, movement_type="in",
        quantity=Decimal("10"), reason="Conteo inicial", created_by_user_id=10,
    )
    db.commit()

    reference, outbound, inbound = transfer_linen_stock(
        db,
        hotel_id=1,
        item_id=item.id,
        source_location_id=source.id,
        destination_location_id=destination.id,
        quantity=Decimal("4"),
        reason="Reposición del office",
        created_by_user_id=10,
        idempotency_key="linen-transfer-key-1",
    )
    db.commit()

    assert outbound.transfer_reference == inbound.transfer_reference == reference
    assert (outbound.movement_type, inbound.movement_type) == ("out", "in")
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=source.id) == Decimal("6.00")
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=destination.id) == Decimal("4.00")
    assert current_stock(db, hotel_id=1, item_id=item.id) == Decimal("10.00")

    retried_reference, retried_outbound, retried_inbound = transfer_linen_stock(
        db,
        hotel_id=1,
        item_id=item.id,
        source_location_id=source.id,
        destination_location_id=destination.id,
        quantity=Decimal("4"),
        reason="Reposición del office",
        created_by_user_id=10,
        idempotency_key="linen-transfer-key-1",
    )
    assert (retried_reference, retried_outbound.id, retried_inbound.id) == (reference, outbound.id, inbound.id)

    with pytest.raises(LinenIdempotencyConflict):
        transfer_linen_stock(
            db,
            hotel_id=1,
            item_id=item.id,
            source_location_id=source.id,
            destination_location_id=destination.id,
            quantity=Decimal("3"),
            reason="Otro payload",
            created_by_user_id=10,
            idempotency_key="linen-transfer-key-1",
        )


def test_linen_transfer_rejects_insufficient_source_without_partial_rows(db):
    _seed_hotels(db)
    item = create_linen_item(db, hotel_id=1, name="Sabanas", unit="unidad")
    source = create_location(db, hotel_id=1, name="Office 1")
    destination = create_location(db, hotel_id=1, name="Office 2")
    register_movement(
        db, hotel_id=1, item_id=item.id, location_id=source.id, movement_type="in",
        quantity=Decimal("2"), reason="Conteo inicial", created_by_user_id=None,
    )
    db.commit()

    with pytest.raises(LinenError, match="negativo"):
        transfer_linen_stock(
            db,
            hotel_id=1,
            item_id=item.id,
            source_location_id=source.id,
            destination_location_id=destination.id,
            quantity=Decimal("3"),
            reason="Reposición",
            created_by_user_id=None,
            idempotency_key="linen-transfer-too-much",
        )
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=source.id) == Decimal("2.00")
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=destination.id) == Decimal("0.00")


def test_linen_minimums_are_location_specific_and_allow_zero(db):
    _seed_hotels(db)
    db.add_all([
        User(id=10, email="linen-owner@example.test", password_hash="test"),
        User(id=11, email="linen-manager@example.test", password_hash="test"),
    ])
    db.flush()
    item = create_linen_item(db, hotel_id=1, name="Sabanas", unit="unidad")
    house = create_location(db, hotel_id=1, name="Deposito")
    laundry = create_location(db, hotel_id=1, name="Lavadero")
    other_hotel_location = create_location(db, hotel_id=2, name="Deposito H2")

    set_location_minimum(
        db, hotel_id=1, item_id=item.id, location_id=house.id,
        min_quantity=Decimal("4.00"), actor_user_id=10,
    )
    set_location_minimum(
        db, hotel_id=1, item_id=item.id, location_id=laundry.id,
        min_quantity=Decimal("0.00"), actor_user_id=10,
    )
    db.commit()

    house_summary = linen_summary(db, hotel_id=1, location_id=house.id)
    laundry_summary = linen_summary(db, hotel_id=1, location_id=laundry.id)
    hotel_summary = linen_summary(db, hotel_id=1)
    assert house_summary[0]["min_quantity"] == Decimal("4.00")
    assert laundry_summary[0]["min_quantity"] == Decimal("0.00")
    assert hotel_summary[0]["min_quantity"] is None
    assert db.query(LinenParLevel).filter_by(hotel_id=1, item_id=item.id).count() == 2

    with pytest.raises(LinenError, match="negativo"):
        set_location_minimum(
            db, hotel_id=1, item_id=item.id, location_id=house.id,
            min_quantity=Decimal("-1.00"), actor_user_id=10,
        )
    with pytest.raises(LinenError, match="ubicación de ropa blanca"):
        set_location_minimum(
            db, hotel_id=1, item_id=item.id, location_id=other_hotel_location.id,
            min_quantity=Decimal("1.00"), actor_user_id=10,
        )

    updated = set_location_minimum(
        db, hotel_id=1, item_id=item.id, location_id=house.id,
        min_quantity=Decimal("6.00"), actor_user_id=11,
    )
    assert updated.created_by_user_id == 10
    assert updated.updated_by_user_id == 11
    assert linen_summary(db, hotel_id=1, location_id=house.id)[0]["min_quantity"] == Decimal("6.00")
