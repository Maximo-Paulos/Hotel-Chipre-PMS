from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models.hotel_config import HotelConfiguration
from app.services.laundry_vendor_service import (
    LaundryVendorError,
    create_remito,
    create_vendor,
    list_remitos,
    list_vendor_prices,
    mark_vendor_settlement_paid,
    set_vendor_price,
    vendor_balance,
    vendor_settlements,
    vendor_spend,
)
from app.services.stock_service import StockError, create_location, create_stock_item, current_stock, register_movement


def _seed_hotels(db):
    db.add_all([
        HotelConfiguration(id=1, subscription_active=True),
        HotelConfiguration(id=2, subscription_active=True),
    ])
    db.flush()


def _seed_house_stock(db, *, hotel_id, item, house_location, quantity):
    register_movement(
        db, hotel_id=hotel_id, item_id=item.id, location_id=house_location.id, movement_type="in",
        quantity=quantity, reason="opening balance", reservation_id=None, created_by_user_id=None,
    )


def test_create_vendor_creates_its_own_stock_location(db):
    _seed_hotels(db)
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Norte", contact_phone="123", contact_email=None)
    db.commit()

    assert vendor.stock_location_id is not None
    assert "Lavadero Norte" in vendor.stock_location.name


def test_create_remito_outbound_transfers_between_locations_without_changing_hotel_total(db):
    _seed_hotels(db)
    item = create_stock_item(db, hotel_id=1, name="Sabanas", sku=None, unit="unit", min_quantity=None, active=True)
    house = create_location(db, hotel_id=1, name="Deposito casa")
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Sur")
    db.flush()
    _seed_house_stock(db, hotel_id=1, item=item, house_location=house, quantity=Decimal("20.00"))
    db.commit()

    remito = create_remito(
        db,
        hotel_id=1,
        vendor_id=vendor.id,
        direction="outbound",
        remito_number="R-001",
        remito_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
        house_location_id=house.id,
        lines=[{"stock_item_id": item.id, "quantity": Decimal("15.00")}],
        actor_user_id=None,
    )
    db.commit()

    assert len(remito.lines) == 1
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=house.id) == Decimal("5.00")
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=vendor.stock_location_id) == Decimal("15.00")
    # Transfer, not consumption: hotel-wide total is unchanged.
    assert current_stock(db, hotel_id=1, item_id=item.id) == Decimal("20.00")


def test_create_remito_inbound_reverses_the_transfer(db):
    _seed_hotels(db)
    item = create_stock_item(db, hotel_id=1, name="Toallas", sku=None, unit="unit", min_quantity=None, active=True)
    house = create_location(db, hotel_id=1, name="Deposito casa")
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Este")
    db.flush()
    _seed_house_stock(db, hotel_id=1, item=item, house_location=house, quantity=Decimal("20.00"))
    db.commit()

    create_remito(
        db, hotel_id=1, vendor_id=vendor.id, direction="outbound", remito_number="R-010",
        remito_date=datetime(2026, 7, 1, tzinfo=timezone.utc), house_location_id=house.id,
        lines=[{"stock_item_id": item.id, "quantity": Decimal("15.00")}], actor_user_id=None,
    )
    db.commit()

    create_remito(
        db, hotel_id=1, vendor_id=vendor.id, direction="inbound", remito_number="R-011",
        remito_date=datetime(2026, 7, 3, tzinfo=timezone.utc), house_location_id=house.id,
        lines=[{"stock_item_id": item.id, "quantity": Decimal("15.00")}], actor_user_id=None,
    )
    db.commit()

    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=house.id) == Decimal("20.00")
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=vendor.stock_location_id) == Decimal("0.00")
    assert current_stock(db, hotel_id=1, item_id=item.id) == Decimal("20.00")


def test_create_remito_rejects_insufficient_stock_at_source_and_creates_nothing(db):
    _seed_hotels(db)
    item = create_stock_item(db, hotel_id=1, name="Fundas", sku=None, unit="unit", min_quantity=None, active=True)
    house = create_location(db, hotel_id=1, name="Deposito casa")
    other_location = create_location(db, hotel_id=1, name="Otro deposito")
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Oeste")
    db.flush()
    # Plenty of stock hotel-wide, but none of it at the "house" location --
    # the hotel-wide guard in register_movement would not catch this alone.
    _seed_house_stock(db, hotel_id=1, item=item, house_location=other_location, quantity=Decimal("50.00"))
    db.commit()

    with pytest.raises(LaundryVendorError, match="Not enough"):
        create_remito(
            db, hotel_id=1, vendor_id=vendor.id, direction="outbound", remito_number="R-020",
            remito_date=datetime(2026, 7, 1, tzinfo=timezone.utc), house_location_id=house.id,
            lines=[{"stock_item_id": item.id, "quantity": Decimal("10.00")}], actor_user_id=None,
        )

    assert list_remitos(db, hotel_id=1, vendor_id=vendor.id) == []
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=house.id) == Decimal("0.00")
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=other_location.id) == Decimal("50.00")


def test_create_remito_rolls_back_entirely_when_a_later_line_fails(db):
    _seed_hotels(db)
    ok_item = create_stock_item(db, hotel_id=1, name="Colchas", sku=None, unit="unit", min_quantity=None, active=True)
    short_item = create_stock_item(db, hotel_id=1, name="Almohadas", sku=None, unit="unit", min_quantity=None, active=True)
    house = create_location(db, hotel_id=1, name="Deposito casa")
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Rollback")
    db.flush()
    _seed_house_stock(db, hotel_id=1, item=ok_item, house_location=house, quantity=Decimal("10.00"))
    _seed_house_stock(db, hotel_id=1, item=short_item, house_location=house, quantity=Decimal("2.00"))
    db.commit()

    with pytest.raises(LaundryVendorError):
        create_remito(
            db, hotel_id=1, vendor_id=vendor.id, direction="outbound", remito_number="R-030",
            remito_date=datetime(2026, 7, 1, tzinfo=timezone.utc), house_location_id=house.id,
            lines=[
                {"stock_item_id": ok_item.id, "quantity": Decimal("5.00")},
                {"stock_item_id": short_item.id, "quantity": Decimal("99.00")},
            ],
            actor_user_id=None,
        )

    # The first line's pair of movements must not have survived either.
    assert current_stock(db, hotel_id=1, item_id=ok_item.id, location_id=house.id) == Decimal("10.00")
    assert current_stock(db, hotel_id=1, item_id=ok_item.id, location_id=vendor.stock_location_id) == Decimal("0.00")
    assert list_remitos(db, hotel_id=1, vendor_id=vendor.id) == []


def test_remito_line_snapshots_price_and_flags_missing_price(db):
    _seed_hotels(db)
    priced_item = create_stock_item(db, hotel_id=1, name="Sabanas", sku=None, unit="unit", min_quantity=None, active=True)
    unpriced_item = create_stock_item(db, hotel_id=1, name="Fundas", sku=None, unit="unit", min_quantity=None, active=True)
    house = create_location(db, hotel_id=1, name="Deposito casa")
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Precios")
    db.flush()
    _seed_house_stock(db, hotel_id=1, item=priced_item, house_location=house, quantity=Decimal("10.00"))
    _seed_house_stock(db, hotel_id=1, item=unpriced_item, house_location=house, quantity=Decimal("10.00"))
    db.commit()

    set_vendor_price(db, hotel_id=1, vendor_id=vendor.id, stock_item_id=priced_item.id, unit_price=Decimal("200.00"))
    db.commit()

    remito = create_remito(
        db, hotel_id=1, vendor_id=vendor.id, direction="outbound", remito_number="R-040",
        remito_date=datetime(2026, 7, 1, tzinfo=timezone.utc), house_location_id=house.id,
        lines=[
            {"stock_item_id": priced_item.id, "quantity": Decimal("2.00")},
            {"stock_item_id": unpriced_item.id, "quantity": Decimal("3.00")},
        ],
        actor_user_id=None,
    )
    db.commit()

    lines_by_item = {line.stock_item_id: line for line in remito.lines}
    assert lines_by_item[priced_item.id].unit_price_snapshot == Decimal("200.00")
    assert lines_by_item[unpriced_item.id].unit_price_snapshot is None


def test_set_vendor_price_upserts_a_single_current_price(db):
    _seed_hotels(db)
    item = create_stock_item(db, hotel_id=1, name="Sabanas", sku=None, unit="unit", min_quantity=None, active=True)
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Precio Unico")
    db.flush()

    set_vendor_price(db, hotel_id=1, vendor_id=vendor.id, stock_item_id=item.id, unit_price=Decimal("100.00"))
    set_vendor_price(db, hotel_id=1, vendor_id=vendor.id, stock_item_id=item.id, unit_price=Decimal("150.00"))
    db.commit()

    prices = list_vendor_prices(db, hotel_id=1, vendor_id=vendor.id)
    assert len(prices) == 1
    assert prices[0].unit_price == Decimal("150.00")


def test_vendor_balance_reflects_partial_return(db):
    _seed_hotels(db)
    item = create_stock_item(db, hotel_id=1, name="Sabanas", sku=None, unit="unit", min_quantity=None, active=True)
    house = create_location(db, hotel_id=1, name="Deposito casa")
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Balance")
    db.flush()
    _seed_house_stock(db, hotel_id=1, item=item, house_location=house, quantity=Decimal("20.00"))
    db.commit()

    create_remito(
        db, hotel_id=1, vendor_id=vendor.id, direction="outbound", remito_number="R-050",
        remito_date=datetime(2026, 7, 1, tzinfo=timezone.utc), house_location_id=house.id,
        lines=[{"stock_item_id": item.id, "quantity": Decimal("20.00")}], actor_user_id=None,
    )
    db.commit()
    create_remito(
        db, hotel_id=1, vendor_id=vendor.id, direction="inbound", remito_number="R-051",
        remito_date=datetime(2026, 7, 3, tzinfo=timezone.utc), house_location_id=house.id,
        lines=[{"stock_item_id": item.id, "quantity": Decimal("15.00")}], actor_user_id=None,
    )
    db.commit()

    balance = vendor_balance(db, hotel_id=1, vendor_id=vendor.id)
    assert len(balance) == 1
    assert balance[0]["stock_item_id"] == item.id
    assert balance[0]["quantity"] == Decimal("5.00")


def test_vendor_spend_sums_outbound_lines_in_period(db):
    _seed_hotels(db)
    item = create_stock_item(db, hotel_id=1, name="Sabanas", sku=None, unit="unit", min_quantity=None, active=True)
    house = create_location(db, hotel_id=1, name="Deposito casa")
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Spend")
    db.flush()
    _seed_house_stock(db, hotel_id=1, item=item, house_location=house, quantity=Decimal("100.00"))
    db.commit()
    set_vendor_price(db, hotel_id=1, vendor_id=vendor.id, stock_item_id=item.id, unit_price=Decimal("100.00"))
    db.commit()

    create_remito(
        db, hotel_id=1, vendor_id=vendor.id, direction="outbound", remito_number="R-060",
        remito_date=datetime(2026, 7, 5, tzinfo=timezone.utc), house_location_id=house.id,
        lines=[{"stock_item_id": item.id, "quantity": Decimal("10.00")}], actor_user_id=None,
    )
    db.commit()

    set_vendor_price(db, hotel_id=1, vendor_id=vendor.id, stock_item_id=item.id, unit_price=Decimal("120.00"))
    db.commit()
    create_remito(
        db, hotel_id=1, vendor_id=vendor.id, direction="outbound", remito_number="R-061",
        remito_date=datetime(2026, 7, 15, tzinfo=timezone.utc), house_location_id=house.id,
        lines=[{"stock_item_id": item.id, "quantity": Decimal("5.00")}], actor_user_id=None,
    )
    db.commit()

    # 10*100 (snapshot at R-060 time) + 5*120 (snapshot at R-061 time) = 1600
    spend = vendor_spend(db, hotel_id=1, vendor_id=vendor.id)
    assert spend["total"] == Decimal("1600.00")
    assert spend["by_item"][0]["quantity"] == Decimal("15.00")

    # Narrow to a date range that only includes the second remito.
    narrow_spend = vendor_spend(
        db, hotel_id=1, vendor_id=vendor.id,
        date_from=datetime(2026, 7, 10, tzinfo=timezone.utc), date_to=datetime(2026, 7, 20, tzinfo=timezone.utc),
    )
    assert narrow_spend["total"] == Decimal("600.00")


def test_remito_price_snapshot_is_frozen_when_vendor_price_changes_later(db):
    """Owner's core requirement: a remito's cost is fixed at creation time.

    The bill is "100 sabanas at $100 this month, 50 at $200 next month" --
    never "recompute everything at today's price". unit_price_snapshot on
    LaundryRemitoLine is what makes that true: it is copied once at remito
    creation (see create_remito) and never touched again, even when the
    vendor's current LaundryVendorPrice.unit_price changes afterwards.
    """
    _seed_hotels(db)
    item = create_stock_item(db, hotel_id=1, name="Sabana", sku=None, unit="unit", min_quantity=None, active=True)
    house = create_location(db, hotel_id=1, name="Deposito casa")
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Congelado")
    db.flush()
    _seed_house_stock(db, hotel_id=1, item=item, house_location=house, quantity=Decimal("100.00"))
    db.commit()

    set_vendor_price(db, hotel_id=1, vendor_id=vendor.id, stock_item_id=item.id, unit_price=Decimal("100.00"))
    db.commit()

    first_remito = create_remito(
        db, hotel_id=1, vendor_id=vendor.id, direction="outbound", remito_number="R-JUL",
        remito_date=datetime(2026, 7, 1, tzinfo=timezone.utc), house_location_id=house.id,
        lines=[{"stock_item_id": item.id, "quantity": Decimal("10.00")}], actor_user_id=None,
    )
    db.commit()
    first_line = first_remito.lines[0]
    assert first_line.unit_price_snapshot == Decimal("100.00")

    # Price hike takes effect for the vendor going forward.
    set_vendor_price(db, hotel_id=1, vendor_id=vendor.id, stock_item_id=item.id, unit_price=Decimal("200.00"))
    db.commit()

    second_remito = create_remito(
        db, hotel_id=1, vendor_id=vendor.id, direction="outbound", remito_number="R-AUG",
        remito_date=datetime(2026, 8, 1, tzinfo=timezone.utc), house_location_id=house.id,
        lines=[{"stock_item_id": item.id, "quantity": Decimal("5.00")}], actor_user_id=None,
    )
    db.commit()
    assert second_remito.lines[0].unit_price_snapshot == Decimal("200.00")

    # The first remito must be untouched by the later price change.
    db.refresh(first_line)
    assert first_line.unit_price_snapshot == Decimal("100.00")


def test_vendor_settlements_groups_by_calendar_quarter_and_defaults_unpaid(db):
    _seed_hotels(db)
    item = create_stock_item(db, hotel_id=1, name="Sabanas", sku=None, unit="unit", min_quantity=None, active=True)
    house = create_location(db, hotel_id=1, name="Deposito casa")
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Trimestre")
    db.flush()
    _seed_house_stock(db, hotel_id=1, item=item, house_location=house, quantity=Decimal("100.00"))
    db.commit()

    set_vendor_price(db, hotel_id=1, vendor_id=vendor.id, stock_item_id=item.id, unit_price=Decimal("100.00"))
    db.commit()
    create_remito(
        db, hotel_id=1, vendor_id=vendor.id, direction="outbound", remito_number="R-Q1",
        remito_date=datetime(2026, 2, 10, tzinfo=timezone.utc), house_location_id=house.id,
        lines=[{"stock_item_id": item.id, "quantity": Decimal("10.00")}], actor_user_id=None,
    )
    db.commit()

    set_vendor_price(db, hotel_id=1, vendor_id=vendor.id, stock_item_id=item.id, unit_price=Decimal("200.00"))
    db.commit()
    create_remito(
        db, hotel_id=1, vendor_id=vendor.id, direction="outbound", remito_number="R-Q3",
        remito_date=datetime(2026, 7, 15, tzinfo=timezone.utc), house_location_id=house.id,
        lines=[{"stock_item_id": item.id, "quantity": Decimal("5.00")}], actor_user_id=None,
    )
    db.commit()

    quarters = vendor_settlements(db, hotel_id=1, vendor_id=vendor.id, year=2026)
    assert [q["period_start"] for q in quarters] == [
        date(2026, 1, 1), date(2026, 4, 1), date(2026, 7, 1), date(2026, 10, 1)
    ]
    assert quarters[0]["total_amount"] == Decimal("1000.00")  # 10 * 100 (Q1's own snapshot)
    assert quarters[1]["total_amount"] == Decimal("0.00")
    assert quarters[2]["total_amount"] == Decimal("1000.00")  # 5 * 200 (Q3's own snapshot)
    assert quarters[3]["total_amount"] == Decimal("0.00")
    # Nobody has marked anything paid yet -- default is "not paid", no row persisted.
    assert all(q["paid"] is False for q in quarters)


def test_mark_vendor_settlement_paid_upserts_and_is_visual_only(db):
    _seed_hotels(db)
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Pago")
    db.commit()

    mark_vendor_settlement_paid(
        db, hotel_id=1, vendor_id=vendor.id, period_start=date(2026, 7, 1), paid=True,
        notes="Coincide con la factura de julio", actor_user_id=None,
    )
    db.commit()

    quarters = vendor_settlements(db, hotel_id=1, vendor_id=vendor.id, year=2026)
    q3 = quarters[2]
    assert q3["paid"] is True
    assert q3["paid_at"] is not None
    assert q3["notes"] == "Coincide con la factura de julio"

    # Toggle back to unpaid -- paid_at clears, notes about the discrepancy stay.
    mark_vendor_settlement_paid(db, hotel_id=1, vendor_id=vendor.id, period_start=date(2026, 7, 1), paid=False)
    db.commit()
    quarters = vendor_settlements(db, hotel_id=1, vendor_id=vendor.id, year=2026)
    q3 = quarters[2]
    assert q3["paid"] is False
    assert q3["paid_at"] is None
    assert q3["notes"] == "Coincide con la factura de julio"


def test_mark_vendor_settlement_paid_rejects_a_non_quarter_start_date(db):
    _seed_hotels(db)
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Fecha Invalida")
    db.commit()

    with pytest.raises(LaundryVendorError, match="first day of a calendar quarter"):
        mark_vendor_settlement_paid(db, hotel_id=1, vendor_id=vendor.id, period_start=date(2026, 7, 15), paid=True)


def test_vendor_settlements_are_hotel_scoped(db):
    _seed_hotels(db)
    vendor1 = create_vendor(db, hotel_id=1, name="Lavadero H1 Trimestre")
    db.commit()

    with pytest.raises(LaundryVendorError):
        vendor_settlements(db, hotel_id=2, vendor_id=vendor1.id, year=2026)
    with pytest.raises(LaundryVendorError):
        mark_vendor_settlement_paid(db, hotel_id=2, vendor_id=vendor1.id, period_start=date(2026, 7, 1), paid=True)


def test_vendors_and_remitos_are_hotel_scoped(db):
    _seed_hotels(db)
    item1 = create_stock_item(db, hotel_id=1, name="Sabanas", sku=None, unit="unit", min_quantity=None, active=True)
    item2 = create_stock_item(db, hotel_id=2, name="Sabanas", sku=None, unit="unit", min_quantity=None, active=True)
    house1 = create_location(db, hotel_id=1, name="Deposito casa 1")
    house2 = create_location(db, hotel_id=2, name="Deposito casa 2")
    vendor1 = create_vendor(db, hotel_id=1, name="Lavadero H1")
    vendor2 = create_vendor(db, hotel_id=2, name="Lavadero H2")
    db.flush()
    _seed_house_stock(db, hotel_id=1, item=item1, house_location=house1, quantity=Decimal("10.00"))
    _seed_house_stock(db, hotel_id=2, item=item2, house_location=house2, quantity=Decimal("10.00"))
    db.commit()

    create_remito(
        db, hotel_id=1, vendor_id=vendor1.id, direction="outbound", remito_number="R-1",
        remito_date=datetime(2026, 7, 1, tzinfo=timezone.utc), house_location_id=house1.id,
        lines=[{"stock_item_id": item1.id, "quantity": Decimal("5.00")}], actor_user_id=None,
    )
    db.commit()

    # Hotel 1 cannot create a remito against hotel 2's vendor.
    with pytest.raises(LaundryVendorError):
        create_remito(
            db, hotel_id=1, vendor_id=vendor2.id, direction="outbound", remito_number="R-2",
            remito_date=datetime(2026, 7, 1, tzinfo=timezone.utc), house_location_id=house1.id,
            lines=[{"stock_item_id": item1.id, "quantity": Decimal("1.00")}], actor_user_id=None,
        )

    assert [r.vendor_id for r in list_remitos(db, hotel_id=1)] == [vendor1.id]
    assert list_remitos(db, hotel_id=2) == []
    with pytest.raises(LaundryVendorError):
        vendor_balance(db, hotel_id=2, vendor_id=vendor1.id)
