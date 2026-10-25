from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models.hotel_config import HotelConfiguration
from app.models.laundry_discrepancy import LaundryDiscrepancyAction, LaundryRemitoDiscrepancy
from app.models.laundry_vendor import LaundryVendorSettlement
from app.models.linen import LinenMovement
from app.models.permission import HotelPermissionOverride
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.services.laundry_vendor_service import (
    LaundryDiscrepancyConflict,
    LaundryDiscrepancyNotFound,
    LaundryVendorError,
    approve_discrepancy,
    confirm_discrepancy_return_to_laundry,
    create_remito,
    create_vendor,
    list_discrepancies,
    resolve_discrepancy,
    set_vendor_price,
)
from app.services.linen_service import (
    LinenError,
    LinenIdempotencyConflict,
    available_stock,
    create_linen_item,
    create_location,
    current_stock,
    linen_summary,
    register_movement,
    retire_linen,
)


def _seed(db):
    db.add_all(
        [
            HotelConfiguration(id=1, subscription_active=True),
            HotelConfiguration(id=2, subscription_active=True),
            User(id=10, email="linen-owner@example.test", password_hash="test"),
            User(id=11, email="linen-manager@example.test", password_hash="test"),
        ]
    )
    db.flush()


def _shortage_case(db):
    _seed(db)
    item = create_linen_item(db, hotel_id=1, name="Sábana superior", unit="unidad")
    house = create_location(db, hotel_id=1, name="Hotel")
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Delta")
    register_movement(
        db,
        hotel_id=1,
        item_id=item.id,
        location_id=house.id,
        movement_type="in",
        quantity=Decimal("20"),
        reason="Conteo inicial",
        created_by_user_id=10,
    )
    set_vendor_price(
        db,
        hotel_id=1,
        vendor_id=vendor.id,
        linen_item_id=item.id,
        unit_price=Decimal("10.00"),
        effective_from=date(2026, 7, 1),
        actor_user_id=10,
    )
    create_remito(
        db,
        hotel_id=1,
        vendor_id=vendor.id,
        direction="outbound",
        remito_number="S-1",
        remito_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
        house_location_id=house.id,
        lines=[{"linen_item_id": item.id, "quantity": Decimal("6")}],
        actor_user_id=10,
    )
    create_remito(
        db,
        hotel_id=1,
        vendor_id=vendor.id,
        direction="inbound",
        remito_number="E-1",
        remito_date=datetime(2026, 7, 2, tzinfo=timezone.utc),
        house_location_id=house.id,
        lines=[{
            "linen_item_id": item.id,
            "quantity": Decimal("4"),
            "missing_quantity": Decimal("2"),
        }],
        actor_user_id=10,
    )
    db.flush()
    row = db.query(LaundryRemitoDiscrepancy).filter_by(hotel_id=1).one()
    db.commit()
    return item, house, vendor, row


def _approve(db, row, key="approve-1"):
    return approve_discrepancy(
        db,
        hotel_id=1,
        discrepancy_id=row.id,
        actor_user_id=11,
        reason="Revisé el conteo con el remito firmado.",
        idempotency_key=key,
    )


def test_shortage_stays_pending_and_does_not_adjust_stock_until_authorized_resolution(db):
    item, house, vendor, discrepancy = _shortage_case(db)

    assert discrepancy.status == "pending_review"
    assert discrepancy.custody_location_id is None
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=house.id) == Decimal("18.00")
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=vendor.linen_location_id) == Decimal("2.00")
    assert available_stock(db, hotel_id=1, item_id=item.id, location_id=vendor.linen_location_id) == Decimal("0.00")
    assert db.query(LinenMovement).filter_by(hotel_id=1, movement_type="adjustment_out").count() == 0
    assert list_discrepancies(db, hotel_id=2) == []
    with pytest.raises(LaundryDiscrepancyNotFound):
        approve_discrepancy(
            db,
            hotel_id=2,
            discrepancy_id=discrepancy.id,
            actor_user_id=11,
            reason="No corresponde a este hotel.",
            idempotency_key="foreign-hotel-approval",
        )

    before = db.query(LinenMovement).filter_by(hotel_id=1).count()
    approved = _approve(db, discrepancy)
    db.commit()
    assert approved.status == "pending_resolution"
    assert approved.reviewed_by_user_id == 11
    assert approved.reviewed_at is not None
    assert db.query(LinenMovement).filter_by(hotel_id=1).count() == before
    assert _approve(db, discrepancy).id == discrepancy.id


@pytest.mark.parametrize(
    ("resolution", "expected_status", "expected_vendor_stock", "expected_total"),
    [
        ("vendor_custody", "resolved", Decimal("2.00"), Decimal("20.00")),
        ("loss", "resolved", Decimal("0.00"), Decimal("18.00")),
        ("vendor_credit", "resolved", Decimal("0.00"), Decimal("18.00")),
    ],
)
def test_missing_linen_resolution_outcomes_keep_custody_and_ledger_consistent(
    db, resolution, expected_status, expected_vendor_stock, expected_total
):
    item, house, vendor, discrepancy = _shortage_case(db)
    _approve(db, discrepancy)
    db.commit()

    result = resolve_discrepancy(
        db,
        hotel_id=1,
        discrepancy_id=discrepancy.id,
        actor_user_id=11,
        resolution_code=resolution,
        reason=f"Gerencia confirmó {resolution} con el lavadero.",
        idempotency_key=f"resolve-{resolution}",
        resolution_amount=Decimal("1250.00") if resolution == "vendor_credit" else None,
        resolution_currency_code="ARS" if resolution == "vendor_credit" else None,
    )
    db.commit()

    assert result.status == expected_status
    assert result.resolution_code == resolution
    assert result.resolution_recorded_by_user_id == 11
    assert result.resolution_recorded_at is not None
    assert result.resolution_reason
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=vendor.linen_location_id) == expected_vendor_stock
    assert current_stock(db, hotel_id=1, item_id=item.id) == expected_total
    assert db.query(LaundryDiscrepancyAction).filter_by(
        hotel_id=1, discrepancy_id=discrepancy.id, action_type="resolution"
    ).count() == 1
    if resolution == "vendor_credit":
        action = db.query(LaundryDiscrepancyAction).filter_by(
            hotel_id=1, discrepancy_id=discrepancy.id, action_type="resolution"
        ).one()
        assert action.resolution_amount == Decimal("1250.00")
        assert action.resolution_currency_code == "ARS"
        # The negotiated credit is recorded for follow-up; it is not silently
        # netted against a vendor settlement.
        assert db.query(LaundryVendorSettlement).filter_by(hotel_id=1, vendor_id=vendor.id).count() == 0
    assert db.query(SecurityAuditLog).filter_by(
        hotel_id=1, user_id=11, action="laundry.discrepancy.resolved"
    ).count() == 1


@pytest.mark.parametrize(
    ("resolution", "expected_status"),
    [("vendor_claim", "pending_claim"), ("replacement", "awaiting_replacement")],
)
def test_claim_or_replacement_remains_pending_until_physical_receipt(db, resolution, expected_status):
    item, house, vendor, discrepancy = _shortage_case(db)
    _approve(db, discrepancy)
    db.commit()
    selected = resolve_discrepancy(
        db,
        hotel_id=1,
        discrepancy_id=discrepancy.id,
        actor_user_id=11,
        resolution_code=resolution,
        reason=f"El lavadero confirma {resolution}.",
        idempotency_key=f"select-{resolution}",
    )
    db.commit()
    assert selected.status == expected_status
    assert selected.remaining_quantity == Decimal("2.00")
    assert available_stock(db, hotel_id=1, item_id=item.id, location_id=vendor.linen_location_id) == Decimal(
        "2.00" if resolution == "vendor_claim" else "0.00"
    )

    receipt = create_remito(
        db,
        hotel_id=1,
        vendor_id=vendor.id,
        direction="inbound",
        remito_number=f"REC-{resolution}",
        remito_date=datetime(2026, 7, 3, tzinfo=timezone.utc),
        house_location_id=house.id,
        lines=[{"linen_item_id": item.id, "quantity": Decimal("2")}],
        actor_user_id=10,
    )
    db.commit()

    assert receipt.lines[0].quantity == Decimal("2.00")
    assert selected.status == "resolved"
    assert selected.remaining_quantity == Decimal("0.00")
    assert selected.resolved_by_user_id == 10
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=house.id) == Decimal("20.00")
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=vendor.linen_location_id) == Decimal("0.00")
    assert db.query(LaundryDiscrepancyAction).filter_by(
        hotel_id=1,
        discrepancy_id=discrepancy.id,
        action_type="replacement_receipt" if resolution == "replacement" else "claim_return",
    ).count() == 1


def test_vendor_credit_requires_explicit_negotiated_amount_and_currency(db):
    _, _, _, discrepancy = _shortage_case(db)
    _approve(db, discrepancy)
    db.commit()
    with pytest.raises(LaundryVendorError, match="crédito requiere importe y moneda"):
        resolve_discrepancy(
            db,
            hotel_id=1,
            discrepancy_id=discrepancy.id,
            actor_user_id=11,
            resolution_code="vendor_credit",
            reason="El lavadero lo reconoce en factura.",
            idempotency_key="credit-without-amount",
        )


def test_excess_is_pending_identification_until_stock_acceptance_or_return(db):
    _seed(db)
    item = create_linen_item(db, hotel_id=1, name="Sábana inferior", unit="unidad")
    house = create_location(db, hotel_id=1, name="Hotel")
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Excedente")
    register_movement(
        db,
        hotel_id=1,
        item_id=item.id,
        location_id=house.id,
        movement_type="in",
        quantity=Decimal("10"),
        reason="Conteo inicial",
        created_by_user_id=10,
    )
    inbound = create_remito(
        db,
        hotel_id=1,
        vendor_id=vendor.id,
        direction="inbound",
        remito_number="EX-1",
        remito_date=datetime(2026, 7, 2, tzinfo=timezone.utc),
        house_location_id=house.id,
        lines=[{"linen_item_id": item.id, "quantity": Decimal("2")}],
        actor_user_id=10,
    )
    db.commit()
    row = list_discrepancies(db, hotel_id=1, discrepancy_type="excess_return")[0]
    assert inbound.lines[0].quantity == Decimal("2.00")
    assert row.status == "pending_approval"
    assert row.custody_location_id == house.id
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=house.id) == Decimal("10.00")
    assert linen_summary(db, hotel_id=1)[0]["pending_excess_quantity"] == Decimal("2.00")

    approved = approve_discrepancy(
        db,
        hotel_id=1,
        discrepancy_id=row.id,
        actor_user_id=11,
        reason="Se cotejó el remito.",
        idempotency_key="approve-excess",
    )
    db.commit()
    assert approved.status == "pending_identification"
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=house.id) == Decimal("10.00")

    reconciled = resolve_discrepancy(
        db,
        hotel_id=1,
        discrepancy_id=row.id,
        actor_user_id=11,
        resolution_code="hotel_stock",
        reason="Se confirmó que las dos sábanas pertenecen al hotel.",
        idempotency_key="accept-excess",
    )
    db.commit()
    assert reconciled.status == "resolved"
    assert reconciled.remaining_quantity == Decimal("0.00")
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=house.id) == Decimal("12.00")
    assert resolve_discrepancy(
        db,
        hotel_id=1,
        discrepancy_id=row.id,
        actor_user_id=11,
        resolution_code="hotel_stock",
        reason="Se confirmó que las dos sábanas pertenecen al hotel.",
        idempotency_key="accept-excess",
    ).id == row.id


def test_excess_return_to_laundry_is_only_closed_after_handover(db):
    _seed(db)
    item = create_linen_item(db, hotel_id=1, name="Funda extra", unit="unidad")
    house = create_location(db, hotel_id=1, name="Hotel")
    vendor = create_vendor(db, hotel_id=1, name="Lavadero Retorno")
    inbound = create_remito(
        db,
        hotel_id=1,
        vendor_id=vendor.id,
        direction="inbound",
        remito_number="EX-RETURN",
        remito_date=datetime(2026, 7, 2, tzinfo=timezone.utc),
        house_location_id=house.id,
        lines=[{"linen_item_id": item.id, "quantity": Decimal("1")}],
        actor_user_id=10,
    )
    db.commit()
    row = list_discrepancies(db, hotel_id=1, discrepancy_type="excess_return")[0]
    approve_discrepancy(
        db, hotel_id=1, discrepancy_id=row.id, actor_user_id=11,
        reason="Cotejo completado.", idempotency_key="approve-extra-return",
    )
    db.commit()
    marked = resolve_discrepancy(
        db, hotel_id=1, discrepancy_id=row.id, actor_user_id=11,
        resolution_code="return_to_laundry", reason="No es stock del hotel.",
        idempotency_key="mark-extra-return",
    )
    db.commit()
    assert marked.status == "return_to_laundry"
    assert marked.remaining_quantity == Decimal("1.00")
    returned = confirm_discrepancy_return_to_laundry(
        db, hotel_id=1, discrepancy_id=row.id, actor_user_id=10,
        reason="Entregado al chofer del lavadero.", idempotency_key="confirm-extra-return",
    )
    db.commit()
    assert returned.status == "returned_to_laundry"
    assert returned.returned_by_user_id == 10
    assert returned.returned_at is not None
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=house.id) == Decimal("0.00")
    assert inbound.lines[0].quantity == Decimal("1.00")


def test_retirement_is_audited_idempotent_and_only_from_hotel_location(db):
    _seed(db)
    item = create_linen_item(db, hotel_id=1, name="Toalla gastada", unit="unidad")
    house = create_location(db, hotel_id=1, name="Hotel")
    vendor = create_vendor(db, hotel_id=1, name="Lavadero retiro")
    register_movement(
        db, hotel_id=1, item_id=item.id, location_id=house.id, movement_type="in",
        quantity=Decimal("10"), reason="Conteo inicial", created_by_user_id=10,
    )
    db.commit()

    movement = retire_linen(
        db, hotel_id=1, item_id=item.id, location_id=house.id, quantity=Decimal("1"),
        reason="Desgaste por uso", created_by_user_id=11, idempotency_key="retire-worn-1",
    )
    db.commit()
    replay = retire_linen(
        db, hotel_id=1, item_id=item.id, location_id=house.id, quantity=Decimal("1"),
        reason="Desgaste por uso", created_by_user_id=11, idempotency_key="retire-worn-1",
    )
    assert replay.id == movement.id
    assert current_stock(db, hotel_id=1, item_id=item.id, location_id=house.id) == Decimal("9.00")
    audit = db.query(SecurityAuditLog).filter_by(
        hotel_id=1, user_id=11, action="laundry.linen.retired", resource_id=str(movement.id)
    ).one()
    assert audit.created_at is not None

    with pytest.raises(LinenIdempotencyConflict):
        retire_linen(
            db, hotel_id=1, item_id=item.id, location_id=house.id, quantity=Decimal("2"),
            reason="Desgaste por uso", created_by_user_id=11, idempotency_key="retire-worn-1",
        )
    with pytest.raises(LinenError, match="solo se puede registrar en una ubicación del hotel"):
        retire_linen(
            db, hotel_id=1, item_id=item.id, location_id=vendor.linen_location_id, quantity=Decimal("1"),
            reason="Desgaste por uso", created_by_user_id=11, idempotency_key="retire-at-vendor",
        )
