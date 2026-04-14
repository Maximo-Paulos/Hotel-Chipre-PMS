from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.services.ota.contracts import (
    NormalizedOTAReservation,
    OTAAdapterContext,
    OTAOperationResult,
    OTAProviderAdapter,
)


class BookingAdapter(OTAProviderAdapter):
    provider_code = "booking"

    def normalize_reservation_payload(self, payload: dict[str, Any]) -> NormalizedOTAReservation:
        pricing = payload.get("pricing", {}) if isinstance(payload.get("pricing"), dict) else {}
        taxes = payload.get("taxes", {}) if isinstance(payload.get("taxes"), dict) else {}
        fees = payload.get("fees", {}) if isinstance(payload.get("fees"), dict) else {}
        commission = payload.get("commission", {}) if isinstance(payload.get("commission"), dict) else {}
        guest = payload.get("guest", {}) if isinstance(payload.get("guest"), dict) else {}

        return NormalizedOTAReservation(
            provider_code=self.provider_code,
            external_reservation_id=str(payload["reservation_id"]),
            external_confirmation_code=str(payload.get("reservation_id")),
            guest_full_name=payload.get("guest_name", "OTA Guest"),
            guest_email=payload.get("guest_email"),
            check_in_date=date.fromisoformat(payload["checkin"]),
            check_out_date=date.fromisoformat(payload["checkout"]),
            sellable_product_code=payload.get("room_type"),
            rate_plan_code=payload.get("rate_plan_id"),
            num_adults=int(payload.get("num_adults", 1)),
            num_children=int(payload.get("num_children", 0)),
            currency_code=payload.get("currency") or pricing.get("currency"),
            gross_total=self._coerce_amount(payload.get("total_price", pricing.get("total"))),
            tax_total=self._coerce_amount(payload.get("tax_total", taxes.get("total"))),
            fee_total=self._coerce_amount(payload.get("fee_total", fees.get("total"))),
            commission_total=self._coerce_amount(payload.get("commission_total", commission.get("total"))),
            event_type=self._infer_event_type(payload),
            guest_phone=guest.get("phone") or payload.get("guest_phone"),
            guest_nationality=guest.get("nationality") or payload.get("guest_nationality"),
            guest_document_type=guest.get("document_type") or payload.get("guest_document_type"),
            guest_document_number=guest.get("document_number") or payload.get("guest_document_number"),
            paid_amount=self._coerce_amount(
                payload.get("paid_amount", payload.get("amount_paid", pricing.get("paid_total")))
            ),
            payment_collection_model=(
                payload.get("payment_collection_model")
                or pricing.get("payment_collection_model")
                or payload.get("payment_model")
            ),
            settlement_status=payload.get("settlement_status") or pricing.get("settlement_status"),
            arrival_time_hint=payload.get("arrival_time"),
            notes=payload.get("remarks"),
            raw_payload=payload,
            received_at=datetime.now(timezone.utc),
        )

    def verify_connection(self, context: OTAAdapterContext) -> OTAOperationResult:
        configured = bool(context.external_property_id and context.auth_config)
        return OTAOperationResult(
            success=configured,
            operation="verify_connection",
            provider_code=self.provider_code,
            message="configured" if configured else "Booking connection missing credentials or property mapping",
        )

    def pull_new_reservations(self, context: OTAAdapterContext):
        return []

    def pull_modifications(self, context: OTAAdapterContext):
        return []

    def pull_cancellations(self, context: OTAAdapterContext):
        return []

    def push_inventory(self, context: OTAAdapterContext, payload: dict):
        return OTAOperationResult(False, "push_inventory", self.provider_code, "Booking adapter not implemented yet")

    def push_rates(self, context: OTAAdapterContext, payload: dict):
        return OTAOperationResult(False, "push_rates", self.provider_code, "Booking adapter not implemented yet")

    def push_restrictions(self, context: OTAAdapterContext, payload: dict):
        return OTAOperationResult(False, "push_restrictions", self.provider_code, "Booking adapter not implemented yet")

    def cancel_reservation(self, context: OTAAdapterContext, external_reservation_id: str, payload: dict | None = None):
        return OTAOperationResult(False, "cancel_reservation", self.provider_code, "Booking adapter not implemented yet")

    def request_modification(self, context: OTAAdapterContext, external_reservation_id: str, payload: dict):
        return OTAOperationResult(False, "request_modification", self.provider_code, "Booking adapter not implemented yet")

    def reconcile_reservation(self, context: OTAAdapterContext, external_reservation_id: str):
        return OTAOperationResult(False, "reconcile_reservation", self.provider_code, "Booking adapter not implemented yet")

    @staticmethod
    def _coerce_amount(value: Any) -> float | None:
        if value in (None, ""):
            return None
        return float(value)

    @staticmethod
    def _infer_event_type(payload: dict[str, Any]) -> str:
        if payload.get("cancelled") or payload.get("is_cancelled"):
            return "cancelled"
        candidates = (
            payload.get("event"),
            payload.get("event_type"),
            payload.get("action"),
            payload.get("notification_type"),
            payload.get("reservation_status"),
            payload.get("status"),
            payload.get("state"),
        )
        for candidate in candidates:
            normalized = str(candidate or "").strip().lower()
            if not normalized:
                continue
            if any(token in normalized for token in ("cancel", "void", "deleted")):
                return "cancelled"
            if any(token in normalized for token in ("modify", "modified", "update", "updated", "change", "changed", "amend")):
                return "modified"
            if any(token in normalized for token in ("new", "create", "book", "confirm")):
                return "new"
        return "new"
