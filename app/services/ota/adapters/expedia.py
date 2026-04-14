from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.services.ota.contracts import (
    NormalizedOTAReservation,
    OTAAdapterContext,
    OTAOperationResult,
    OTAProviderAdapter,
)


class ExpediaAdapter(OTAProviderAdapter):
    provider_code = "expedia"

    def normalize_reservation_payload(self, payload: dict[str, Any]) -> NormalizedOTAReservation:
        guest = payload.get("guest", {})
        stay = payload.get("stay", {})
        occupancy = payload.get("occupancy", {})
        pricing = payload.get("pricing", {})
        taxes = pricing.get("taxes", {}) if isinstance(pricing.get("taxes"), dict) else {}
        fees = pricing.get("fees", {}) if isinstance(pricing.get("fees"), dict) else {}
        commission = pricing.get("commission", {}) if isinstance(pricing.get("commission"), dict) else {}

        return NormalizedOTAReservation(
            provider_code=self.provider_code,
            external_reservation_id=str(payload["booking_id"]),
            external_confirmation_code=str(payload.get("booking_id")),
            guest_full_name=f"{guest.get('first_name', '')} {guest.get('last_name', '')}".strip() or "OTA Guest",
            guest_email=guest.get("email"),
            check_in_date=date.fromisoformat(stay["checkin"]),
            check_out_date=date.fromisoformat(stay["checkout"]),
            sellable_product_code=payload.get("room_type_id"),
            rate_plan_code=payload.get("rate_plan_id"),
            num_adults=int(occupancy.get("adults", 1)),
            num_children=int(occupancy.get("children", 0)),
            currency_code=pricing.get("currency"),
            gross_total=self._coerce_amount(pricing.get("total")),
            tax_total=self._coerce_amount(pricing.get("tax_total", taxes.get("total"))),
            fee_total=self._coerce_amount(pricing.get("fee_total", fees.get("total"))),
            commission_total=self._coerce_amount(pricing.get("commission_total", commission.get("total"))),
            event_type=self._infer_event_type(payload),
            guest_phone=guest.get("phone") or guest.get("phone_number"),
            guest_nationality=guest.get("nationality"),
            guest_document_type=guest.get("document_type"),
            guest_document_number=guest.get("document_number"),
            paid_amount=self._coerce_amount(pricing.get("paid_total") or pricing.get("paid_amount")),
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
            message="configured" if configured else "Expedia connection missing credentials or property mapping",
        )

    def pull_new_reservations(self, context: OTAAdapterContext):
        return []

    def pull_modifications(self, context: OTAAdapterContext):
        return []

    def pull_cancellations(self, context: OTAAdapterContext):
        return []

    def push_inventory(self, context: OTAAdapterContext, payload: dict):
        return OTAOperationResult(False, "push_inventory", self.provider_code, "Expedia adapter not implemented yet")

    def push_rates(self, context: OTAAdapterContext, payload: dict):
        return OTAOperationResult(False, "push_rates", self.provider_code, "Expedia adapter not implemented yet")

    def push_restrictions(self, context: OTAAdapterContext, payload: dict):
        return OTAOperationResult(False, "push_restrictions", self.provider_code, "Expedia adapter not implemented yet")

    def cancel_reservation(self, context: OTAAdapterContext, external_reservation_id: str, payload: dict | None = None):
        return OTAOperationResult(False, "cancel_reservation", self.provider_code, "Expedia adapter not implemented yet")

    def request_modification(self, context: OTAAdapterContext, external_reservation_id: str, payload: dict):
        return OTAOperationResult(False, "request_modification", self.provider_code, "Expedia adapter not implemented yet")

    def reconcile_reservation(self, context: OTAAdapterContext, external_reservation_id: str):
        return OTAOperationResult(False, "reconcile_reservation", self.provider_code, "Expedia adapter not implemented yet")

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
            payload.get("booking_status"),
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
