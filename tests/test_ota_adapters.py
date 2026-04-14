from __future__ import annotations

from app.services.ota.adapters import BookingAdapter, DespegarAdapter, ExpediaAdapter
from app.services.ota.registry import build_default_ota_orchestrator


def test_booking_adapter_normalizes_pricing_breakdown():
    payload = {
        "reservation_id": "BKG-100",
        "event": "reservation.modified",
        "guest_name": "Jane Doe",
        "guest_email": "jane@example.com",
        "guest_phone": "+5491112345678",
        "checkin": "2026-09-01",
        "checkout": "2026-09-04",
        "room_type": "STD_DBL",
        "rate_plan_id": "flex",
        "num_adults": 2,
        "num_children": 1,
        "currency": "ARS",
        "total_price": 540.0,
        "tax_total": 40.0,
        "fee_total": 10.0,
        "commission_total": 54.0,
        "arrival_time": "20:00",
    }

    normalized = BookingAdapter().normalize_reservation_payload(payload)

    assert normalized.provider_code == "booking"
    assert normalized.external_reservation_id == "BKG-100"
    assert normalized.sellable_product_code == "STD_DBL"
    assert normalized.rate_plan_code == "flex"
    assert normalized.gross_total == 540.0
    assert normalized.tax_total == 40.0
    assert normalized.fee_total == 10.0
    assert normalized.commission_total == 54.0
    assert normalized.event_type == "modified"
    assert normalized.guest_phone == "+5491112345678"
    assert normalized.arrival_time_hint == "20:00"


def test_expedia_adapter_normalizes_nested_pricing_breakdown():
    payload = {
        "booking_id": "EXP-200",
        "guest": {"first_name": "Emma", "last_name": "Stone", "email": "emma@example.com"},
        "status": "cancelled",
        "stay": {"checkin": "2026-09-10", "checkout": "2026-09-13"},
        "room_type_id": "SUP_DBL",
        "rate_plan_id": "non_ref",
        "occupancy": {"adults": 2, "children": 0},
        "pricing": {
            "currency": "USD",
            "total": 750.0,
            "taxes": {"total": 100.0},
            "fees": {"total": 20.0},
            "commission": {"total": 90.0},
        },
    }

    normalized = ExpediaAdapter().normalize_reservation_payload(payload)

    assert normalized.provider_code == "expedia"
    assert normalized.external_reservation_id == "EXP-200"
    assert normalized.guest_full_name == "Emma Stone"
    assert normalized.sellable_product_code == "SUP_DBL"
    assert normalized.gross_total == 750.0
    assert normalized.tax_total == 100.0
    assert normalized.fee_total == 20.0
    assert normalized.commission_total == 90.0
    assert normalized.event_type == "cancelled"


def test_despegar_adapter_normalizes_partner_payload():
    payload = {
        "reservation_id": "DSP-300",
        "confirmation_code": "DSP-CNF-300",
        "guest": {"first_name": "Ana", "last_name": "Perez", "email": "ana@example.com"},
        "action": "booking_updated",
        "stay": {"checkin": "2026-10-01", "checkout": "2026-10-03"},
        "product_code": "TRPL_SHR",
        "rate_plan_code": "desp-flex",
        "occupancy": {"adults": 3, "children": 0},
        "pricing": {"currency": "USD", "total": 640.0, "commission": {"total": 96.0}},
        "notes": "Late arrival",
    }

    normalized = DespegarAdapter().normalize_reservation_payload(payload)

    assert normalized.provider_code == "despegar"
    assert normalized.external_confirmation_code == "DSP-CNF-300"
    assert normalized.sellable_product_code == "TRPL_SHR"
    assert normalized.rate_plan_code == "desp-flex"
    assert normalized.num_adults == 3
    assert normalized.commission_total == 96.0
    assert normalized.notes == "Late arrival"
    assert normalized.event_type == "modified"


def test_default_registry_registers_three_core_adapters():
    orchestrator = build_default_ota_orchestrator()

    assert orchestrator.get_adapter("booking").provider_code == "booking"
    assert orchestrator.get_adapter("expedia").provider_code == "expedia"
    assert orchestrator.get_adapter("despegar").provider_code == "despegar"
