from __future__ import annotations

import json

from app.models.hotel_config import HotelConfiguration
from app.models.ota_core import OTAConnection, OTAProvider, OTASyncEvent, OTASyncJob
from app.services.ota.contracts import OTAAdapterContext, OTAOperationResult, OTAProviderAdapter
from app.services.ota.orchestrator import OTAOrchestratorService


class FakeBookingAdapter(OTAProviderAdapter):
    provider_code = "booking"

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
