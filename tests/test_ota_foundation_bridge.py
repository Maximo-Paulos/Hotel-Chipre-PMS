from __future__ import annotations

from app.models.commercial import ProductRoomCompatibility, SellableProduct
from app.models.room import RoomStatusEnum
from app.models.ota_core import OTAReservationLink
from app.services.ota_service import OTAIntegrationService


def test_booking_webhook_populates_foundation_ota_link(db, sample_rooms, sample_categories, hotel_config):
    secret = "booking-bridge-secret"
    OTAIntegrationService.upsert_webhook_credential(
        db,
        hotel_id=hotel_config.id,
        provider="booking",
        webhook_secret=secret,
        external_property_id="booking-h1",
    )
    payload = {
        "reservation_id": "BK-BRIDGE-001",
        "guest_name": "Bridge Guest",
        "guest_email": "bridge@example.com",
        "checkin": "2026-09-01",
        "checkout": "2026-09-03",
        "room_type": "STD_DBL",
        "num_adults": 2,
        "num_children": 0,
        "total_price": 500.0,
        "currency": "ARS",
        "property_id": "booking-h1",
    }

    mapping = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, payload)
    db.flush()

    link = db.query(OTAReservationLink).filter_by(
        hotel_id=hotel_config.id,
        external_reservation_id="BK-BRIDGE-001",
    ).one()
    assert link.provider.code == "booking"
    assert link.reservation_id == mapping.reservation_id
    assert link.currency_code == "ARS"
    assert mapping.reservation.source_provider_code == "booking"


def test_expedia_webhook_populates_foundation_ota_link(db, sample_rooms, sample_categories, hotel_config):
    secret = "expedia-bridge-secret"
    OTAIntegrationService.upsert_webhook_credential(
        db,
        hotel_id=hotel_config.id,
        provider="expedia",
        webhook_secret=secret,
        external_property_id="expedia-h1",
    )
    payload = {
        "booking_id": "EXP-BRIDGE-001",
        "guest": {"first_name": "Emma", "last_name": "Bridge", "email": "emma@example.com"},
        "stay": {"checkin": "2026-09-10", "checkout": "2026-09-12"},
        "room_type_id": "SUP_DBL",
        "occupancy": {"adults": 2, "children": 0},
        "pricing": {"total": 650.0, "currency": "USD"},
        "property_id": "expedia-h1",
    }

    mapping = OTAIntegrationService.process_expedia_webhook(db, hotel_config.id, secret, payload)
    db.flush()

    link = db.query(OTAReservationLink).filter_by(
        hotel_id=hotel_config.id,
        external_reservation_id="EXP-BRIDGE-001",
    ).one()
    assert link.provider.code == "expedia"
    assert link.reservation_id == mapping.reservation_id
    assert link.currency_code == "USD"
    assert mapping.reservation.source_provider_code == "expedia"


def test_despegar_webhook_populates_foundation_ota_link(db, sample_rooms, sample_categories, hotel_config):
    secret = "despegar-bridge-secret"
    OTAIntegrationService.upsert_webhook_credential(
        db,
        hotel_id=hotel_config.id,
        provider="despegar",
        webhook_secret=secret,
        external_property_id="despegar-h1",
    )
    payload = {
        "reservation_id": "DSP-BRIDGE-001",
        "confirmation_code": "DSP-CNF-001",
        "guest": {"first_name": "Lola", "last_name": "Bridge", "email": "lola@example.com"},
        "stay": {"checkin": "2026-09-20", "checkout": "2026-09-22"},
        "product_code": "STD_DBL",
        "occupancy": {"adults": 2, "children": 0},
        "pricing": {"total": 580.0, "currency": "USD", "commission": {"total": 87.0}},
        "property_id": "despegar-h1",
    }

    mapping = OTAIntegrationService.process_despegar_webhook(db, hotel_config.id, secret, payload)
    db.flush()

    link = db.query(OTAReservationLink).filter_by(
        hotel_id=hotel_config.id,
        external_reservation_id="DSP-BRIDGE-001",
    ).one()
    assert link.provider.code == "despegar"
    assert link.reservation_id == mapping.reservation_id
    assert link.currency_code == "USD"
    assert mapping.reservation.source_provider_code == "despegar"


def test_booking_webhook_links_reservation_to_sellable_product(db, sample_rooms, sample_categories, hotel_config):
    product = SellableProduct(
        hotel_id=hotel_config.id,
        primary_room_category_id=sample_categories[0].id,
        code="STD_DBL",
        name="Standard Double Product",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(product)
    db.flush()

    secret = "booking-product-secret"
    OTAIntegrationService.upsert_webhook_credential(
        db,
        hotel_id=hotel_config.id,
        provider="booking",
        webhook_secret=secret,
        external_property_id="booking-h1",
    )
    payload = {
        "reservation_id": "BK-BRIDGE-SELLABLE-001",
        "guest_name": "Product Guest",
        "guest_email": "product@example.com",
        "checkin": "2026-10-01",
        "checkout": "2026-10-03",
        "room_type": "STD_DBL",
        "num_adults": 2,
        "num_children": 0,
        "total_price": 430.0,
        "currency": "ARS",
        "property_id": "booking-h1",
    }

    mapping = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, payload)
    db.flush()

    assert mapping.reservation.sellable_product_id == product.id
    assert mapping.reservation.category_id == sample_categories[0].id


def test_booking_webhook_uses_product_compatibility_when_primary_category_has_no_inventory(
    db,
    sample_rooms,
    sample_categories,
    hotel_config,
):
    product = SellableProduct(
        hotel_id=hotel_config.id,
        primary_room_category_id=sample_categories[0].id,
        code="DBL_SHARED",
        name="Doble compartida",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(product)
    db.flush()
    db.add(
        ProductRoomCompatibility(
            hotel_id=hotel_config.id,
            sellable_product_id=product.id,
            room_category_id=sample_categories[1].id,
            compatibility_kind="upgrade",
            priority=5,
            allows_auto_assignment=True,
        )
    )
    for room in sample_rooms:
        if room.category_id == sample_categories[0].id:
            room.status = RoomStatusEnum.MAINTENANCE
    db.flush()

    secret = "booking-compat-secret"
    OTAIntegrationService.upsert_webhook_credential(
        db,
        hotel_id=hotel_config.id,
        provider="booking",
        webhook_secret=secret,
        external_property_id="booking-h1",
    )
    payload = {
        "reservation_id": "BK-BRIDGE-COMPAT-001",
        "guest_name": "Compat Guest",
        "guest_email": "compat@example.com",
        "checkin": "2026-10-10",
        "checkout": "2026-10-12",
        "room_type": "DBL_SHARED",
        "num_adults": 2,
        "num_children": 0,
        "total_price": 510.0,
        "currency": "ARS",
        "property_id": "booking-h1",
    }

    mapping = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, payload)
    db.flush()

    assert mapping.reservation.sellable_product_id == product.id
    assert mapping.reservation.category_id == sample_categories[1].id
    assert mapping.reservation.room.category_id == sample_categories[1].id
