"""
Common contracts for OTA provider adapters.

The goal is to keep Booking, Expedia and Despegar behind the same interface so
the PMS core can orchestrate sync and lifecycle without channel-specific
branches everywhere.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(slots=True)
class OTAAdapterContext:
    hotel_id: int
    provider_code: str
    connection_id: int | None = None
    environment: str = "sandbox"
    external_property_id: str | None = None
    auth_config: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OTAOperationResult:
    success: bool
    operation: str
    provider_code: str
    message: str | None = None
    payload: dict[str, Any] | None = None
    raw_request: str | None = None
    raw_response: str | None = None
    http_status: int | None = None
    retryable: bool = False


@dataclass(slots=True)
class NormalizedOTAReservation:
    provider_code: str
    external_reservation_id: str
    external_confirmation_code: str | None
    guest_full_name: str
    guest_email: str | None
    check_in_date: date
    check_out_date: date
    sellable_product_code: str | None
    rate_plan_code: str | None
    num_adults: int
    num_children: int
    currency_code: str | None
    gross_total: float | None
    tax_total: float | None
    fee_total: float | None
    commission_total: float | None
    arrival_time_hint: str | None = None
    notes: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    received_at: datetime | None = None


class OTAProviderAdapter(ABC):
    provider_code: str

    @abstractmethod
    def verify_connection(self, context: OTAAdapterContext) -> OTAOperationResult:
        raise NotImplementedError

    @abstractmethod
    def pull_new_reservations(self, context: OTAAdapterContext) -> list[NormalizedOTAReservation]:
        raise NotImplementedError

    @abstractmethod
    def pull_modifications(self, context: OTAAdapterContext) -> list[NormalizedOTAReservation]:
        raise NotImplementedError

    @abstractmethod
    def pull_cancellations(self, context: OTAAdapterContext) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def push_inventory(self, context: OTAAdapterContext, payload: dict[str, Any]) -> OTAOperationResult:
        raise NotImplementedError

    @abstractmethod
    def push_rates(self, context: OTAAdapterContext, payload: dict[str, Any]) -> OTAOperationResult:
        raise NotImplementedError

    @abstractmethod
    def push_restrictions(self, context: OTAAdapterContext, payload: dict[str, Any]) -> OTAOperationResult:
        raise NotImplementedError

    @abstractmethod
    def cancel_reservation(
        self,
        context: OTAAdapterContext,
        external_reservation_id: str,
        payload: dict[str, Any] | None = None,
    ) -> OTAOperationResult:
        raise NotImplementedError

    @abstractmethod
    def request_modification(
        self,
        context: OTAAdapterContext,
        external_reservation_id: str,
        payload: dict[str, Any],
    ) -> OTAOperationResult:
        raise NotImplementedError

    @abstractmethod
    def reconcile_reservation(
        self,
        context: OTAAdapterContext,
        external_reservation_id: str,
    ) -> OTAOperationResult:
        raise NotImplementedError
