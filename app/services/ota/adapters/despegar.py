from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.services.ota.contracts import (
    NormalizedOTAReservation,
    OTAAdapterContext,
    OTAOperationResult,
    OTAProviderAdapter,
)


class DespegarAdapter(OTAProviderAdapter):
    provider_code = "despegar"

    def normalize_reservation_payload(self, payload: dict[str, Any]) -> NormalizedOTAReservation:
        guest = payload.get("guest", {}) if isinstance(payload.get("guest"), dict) else {}
        stay = payload.get("stay", {}) if isinstance(payload.get("stay"), dict) else {}
        occupancy = payload.get("occupancy", {}) if isinstance(payload.get("occupancy"), dict) else {}
        pricing = payload.get("pricing", {}) if isinstance(payload.get("pricing"), dict) else {}
        taxes = pricing.get("taxes", {}) if isinstance(pricing.get("taxes"), dict) else {}
        fees = pricing.get("fees", {}) if isinstance(pricing.get("fees"), dict) else {}
        commission = pricing.get("commission", {}) if isinstance(pricing.get("commission"), dict) else {}
        first_name = guest.get("first_name") or guest.get("name") or ""
        last_name = guest.get("last_name") or guest.get("surname") or ""
        return NormalizedOTAReservation(
            provider_code=self.provider_code,
            external_reservation_id=str(payload["reservation_id"]),
            external_confirmation_code=str(payload.get("confirmation_code") or payload.get("reservation_id")),
            guest_full_name=f"{first_name} {last_name}".strip() or payload.get("guest_name", "OTA Guest"),
            guest_email=guest.get("email") or payload.get("guest_email"),
            check_in_date=date.fromisoformat(stay["checkin"]),
            check_out_date=date.fromisoformat(stay["checkout"]),
            sellable_product_code=payload.get("product_code") or payload.get("room_type_code"),
            rate_plan_code=payload.get("rate_plan_code") or payload.get("rate_plan_id"),
            num_adults=int(occupancy.get("adults", payload.get("num_adults", 1))),
            num_children=int(occupancy.get("children", payload.get("num_children", 0))),
            currency_code=pricing.get("currency") or payload.get("currency"),
            gross_total=self._coerce_amount(pricing.get("total") or payload.get("total_price")),
            tax_total=self._coerce_amount(pricing.get("tax_total", taxes.get("total"))),
            fee_total=self._coerce_amount(pricing.get("fee_total", fees.get("total"))),
            commission_total=self._coerce_amount(pricing.get("commission_total", commission.get("total"))),
            event_type=self._infer_event_type(payload),
            guest_phone=guest.get("phone") or payload.get("guest_phone"),
            guest_nationality=guest.get("nationality") or payload.get("guest_nationality"),
            guest_document_type=guest.get("document_type") or payload.get("guest_document_type"),
            guest_document_number=guest.get("document_number") or payload.get("guest_document_number"),
            paid_amount=self._coerce_amount(
                pricing.get("paid_total") or pricing.get("paid_amount") or payload.get("paid_amount")
            ),
            payment_collection_model=(
                payload.get("payment_collection_model")
                or pricing.get("payment_collection_model")
                or payload.get("payment_model")
            ),
            settlement_status=payload.get("settlement_status") or pricing.get("settlement_status"),
            arrival_time_hint=payload.get("arrival_time"),
            notes=payload.get("remarks") or payload.get("notes"),
            raw_payload=payload,
            received_at=datetime.now(timezone.utc),
        )

    def verify_connection(self, context: OTAAdapterContext) -> OTAOperationResult:
        configured = bool(context.external_property_id and context.auth_config)
        return OTAOperationResult(
            success=configured,
            operation="verify_connection",
            provider_code=self.provider_code,
            message="configured" if configured else "Despegar connection missing credentials or property mapping",
        )

    def pull_new_reservations(self, context: OTAAdapterContext):
        return []

    def pull_modifications(self, context: OTAAdapterContext):
        return []

    def pull_cancellations(self, context: OTAAdapterContext):
        return []

    def push_inventory(self, context: OTAAdapterContext, payload: dict):
        return OTAOperationResult(False, "push_inventory", self.provider_code, "Despegar adapter not implemented yet")

    def push_rates(self, context: OTAAdapterContext, payload: dict):
        return OTAOperationResult(False, "push_rates", self.provider_code, "Despegar adapter not implemented yet")

    def push_restrictions(self, context: OTAAdapterContext, payload: dict):
        return OTAOperationResult(False, "push_restrictions", self.provider_code, "Despegar adapter not implemented yet")

    def cancel_reservation(self, context: OTAAdapterContext, external_reservation_id: str, payload: dict | None = None):
        return OTAOperationResult(False, "cancel_reservation", self.provider_code, "Despegar adapter not implemented yet")

    def request_modification(self, context: OTAAdapterContext, external_reservation_id: str, payload: dict):
        return OTAOperationResult(False, "request_modification", self.provider_code, "Despegar adapter not implemented yet")

    def reconcile_reservation(self, context: OTAAdapterContext, external_reservation_id: str):
        return OTAOperationResult(False, "reconcile_reservation", self.provider_code, "Despegar adapter not implemented yet")

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
