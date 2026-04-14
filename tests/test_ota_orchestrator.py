from __future__ import annotations

import json
from datetime import date

from app.models.hotel_config import HotelConfiguration
from app.models.ota_core import OTAConnection, OTAProvider, OTASyncEvent, OTASyncJob
from app.services.ota.contracts import (
    NormalizedOTAReservation,
    OTAAdapterContext,
    OTAOperationResult,
    OTAProviderAdapter,
)
from app.services.ota.orchestrator import OTAOrchestratorError, OTAOrchestratorService


class FakeBookingAdapter(OTAProviderAdapter):
    provider_code = "booking"

    def normalize_reservation_payload(self, payload: dict) -> NormalizedOTAReservation:
        return NormalizedOTAReservation(
            provider_code="booking",
            external_reservation_id=str(payload["reservation_id"]),
            external_confirmation_code=str(payload["reservation_id"]),
            guest_full_name=payload.get("guest_name", "Guest"),
            guest_email=payload.get("guest_email"),
            check_in_date=date.fromisoformat(payload["checkin"]),
            check_out_date=date.fromisoformat(payload["checkout"]),
            sellable_product_code=payload.get("room_type"),
            rate_plan_code=payload.get("rate_plan_id"),
            num_adults=payload.get("num_adults", 1),
            num_children=payload.get("num_children", 0),
            currency_code=payload.get("currency"),
            gross_total=payload.get("total_price"),
            tax_total=None,
            fee_total=None,
            commission_total=None,
            raw_payload=payload,
        )

    def verify_connection(self, context: OTAAdapterContext) -> OTAOperationResult:
        return OTAOperationResult(
            success=True,
            operation="verify_connection",
            provider_code=self.provider_code,
            message="ok",
            payload={"property_id": context.external_property_id},
            http_status=200,
        )

    def pull_new_reservations(self, context: OTAAdapterContext):
        return []

    def pull_modifications(self, context: OTAAdapterContext):
        return []

    def pull_cancellations(self, context: OTAAdapterContext):
        return []

    def push_inventory(self, context: OTAAdapterContext, payload):
        raise NotImplementedError

    def push_rates(self, context: OTAAdapterContext, payload):
        raise NotImplementedError

    def push_restrictions(self, context: OTAAdapterContext, payload):
        raise NotImplementedError

    def cancel_reservation(self, context: OTAAdapterContext, external_reservation_id: str, payload=None):
        raise NotImplementedError

    def request_modification(self, context: OTAAdapterContext, external_reservation_id: str, payload):
        raise NotImplementedError

    def reconcile_reservation(self, context: OTAAdapterContext, external_reservation_id: str):
        raise NotImplementedError


class FailingBookingAdapter(FakeBookingAdapter):
    def verify_connection(self, context: OTAAdapterContext) -> OTAOperationResult:
        return OTAOperationResult(
            success=False,
            operation="verify_connection",
            provider_code=self.provider_code,
            message="bad credentials",
            http_status=401,
        )


def test_ota_orchestrator_verifies_connection_and_persists_event(db):
    hotel = HotelConfiguration(id=31, hotel_name="Hotel Orchestrator", subscription_active=True)
    provider = OTAProvider(code="booking", name="Booking.com", auth_type="connectivity_api", security_model="partner")
    db.add_all([hotel, provider])
    db.flush()

    connection = OTAConnection(
        hotel_id=31,
        provider_id=provider.id,
        environment="sandbox",
        status="pending",
        is_enabled=True,
        external_property_id="hotel-31",
        auth_config_encrypted=json.dumps({"token": "abc"}),
        settings_json=json.dumps({"mode": "pull"}),
    )
    db.add(connection)
    db.flush()

    orchestrator = OTAOrchestratorService()
    orchestrator.register_adapter(FakeBookingAdapter())

    result = orchestrator.verify_connection(db, connection.id)
    db.commit()

    assert result.success is True
    refreshed = db.get(OTAConnection, connection.id)
    assert refreshed.status == "healthy"
    assert refreshed.last_error is None
    job = db.query(OTASyncJob).filter_by(connection_id=connection.id, job_type="verify_connection").one()
    assert job.status == "succeeded"
    event = db.query(OTASyncEvent).filter_by(job_id=job.id, event_type="verify_connection").one()
    assert event.result == "succeeded"


def test_ota_orchestrator_records_failed_verification(db):
    hotel = HotelConfiguration(id=32, hotel_name="Hotel Error", subscription_active=True)
    provider = OTAProvider(code="booking", name="Booking.com", auth_type="connectivity_api", security_model="partner")
    db.add_all([hotel, provider])
    db.flush()

    connection = OTAConnection(
        hotel_id=32,
        provider_id=provider.id,
        environment="sandbox",
        status="pending",
        is_enabled=True,
        external_property_id="hotel-32",
        auth_config_encrypted=json.dumps({"token": "expired"}),
    )
    db.add(connection)
    db.flush()

    orchestrator = OTAOrchestratorService()
    orchestrator.register_adapter(FailingBookingAdapter())

    result = orchestrator.verify_connection(db, connection.id)
    db.commit()

    assert result.success is False
    refreshed = db.get(OTAConnection, connection.id)
    assert refreshed.status == "error"
    assert refreshed.last_error == "bad credentials"
    job = db.query(OTASyncJob).filter_by(connection_id=connection.id, job_type="verify_connection").one()
    assert job.status == "failed"
    event = db.query(OTASyncEvent).filter_by(job_id=job.id, event_type="verify_connection").one()
    assert event.result == "failed"
    assert event.http_status == 401


def test_ota_orchestrator_raises_for_unknown_provider():
    orchestrator = OTAOrchestratorService()

    try:
        orchestrator.get_adapter("despegar")
    except OTAOrchestratorError as exc:
        assert "despegar" in str(exc)
    else:
        raise AssertionError("Expected OTAOrchestratorError for unknown provider")
