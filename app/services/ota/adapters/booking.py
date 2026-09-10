"""Booking.com Connectivity adapter.

The adapter keeps provider traffic behind a small, injectable transport. A
hotel can prepare mappings and credentials without enabling a sync job, while
an explicit verification or sync uses the official HTTPS Connectivity
endpoints. Provider responses are normalized before entering the PMS and
credentials are never included in operation evidence.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, datetime, timezone
import json
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import requests

from app.services.ota.contracts import (
    NormalizedOTAReservation,
    OTAAdapterContext,
    OTAOperationResult,
    OTAProviderAdapter,
)


class BookingAdapterError(RuntimeError):
    """A provider operation failed before it could return normalized data."""


Requester = Callable[..., Any]


class BookingAdapter(OTAProviderAdapter):
    provider_code = "booking"

    _SECURE_BASE = "https://secure-supply-xml.booking.com"
    _SUPPLY_BASE = "https://supply-xml.booking.com"
    _DEFAULT_ENDPOINTS = {
        "new_reservations": "/hotels/ota/OTA_HotelResNotif",
        "reservation_changes": "/hotels/ota/OTA_HotelResModifyNotif",
        "availability": "/hotels/xml/availability",
    }

    def __init__(self, requester: Requester | None = None) -> None:
        self._requester = requester or requests.request
        self.last_result: OTAOperationResult | None = None

    def normalize_reservation_payload(self, payload: dict[str, Any]) -> NormalizedOTAReservation:
        pricing = payload.get("pricing", {}) if isinstance(payload.get("pricing"), dict) else {}
        taxes = payload.get("taxes", {}) if isinstance(payload.get("taxes"), dict) else {}
        fees = payload.get("fees", {}) if isinstance(payload.get("fees"), dict) else {}
        commission = payload.get("commission", {}) if isinstance(payload.get("commission"), dict) else {}
        guest = payload.get("guest", {}) if isinstance(payload.get("guest"), dict) else {}

        return NormalizedOTAReservation(
            provider_code=self.provider_code,
            external_reservation_id=str(payload["reservation_id"]),
            external_confirmation_code=str(payload.get("confirmation_code") or payload.get("reservation_id")),
            guest_full_name=payload.get("guest_name", "OTA Guest"),
            guest_email=payload.get("guest_email"),
            check_in_date=date.fromisoformat(str(payload["checkin"])[:10]),
            check_out_date=date.fromisoformat(str(payload["checkout"])[:10]),
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
            notes=payload.get("remarks") or payload.get("notes"),
            raw_payload=payload,
            received_at=datetime.now(timezone.utc),
        )

    def verify_connection(self, context: OTAAdapterContext) -> OTAOperationResult:
        ready, message = self._validate_context(context)
        if not ready:
            return self._remember(
                OTAOperationResult(False, "verify_connection", self.provider_code, message, retryable=False)
            )

        result, _payload = self._request(
            context,
            "GET",
            self._endpoint(context, "new_reservations", secure=True),
            params={"hotel_ids": context.external_property_id, "limit": "10"},
            operation="verify_connection",
        )
        return self._remember(result)

    def pull_new_reservations(self, context: OTAAdapterContext) -> list[NormalizedOTAReservation]:
        return self._pull_reservations(context, "new_reservations", "pull_new_reservations", "new")

    def pull_modifications(self, context: OTAAdapterContext) -> list[NormalizedOTAReservation]:
        return self._pull_reservations(context, "reservation_changes", "pull_modifications", "modified")

    def pull_cancellations(self, context: OTAAdapterContext) -> list[str]:
        result, payload = self._request(
            context,
            "GET",
            self._endpoint(context, "reservation_changes", secure=True),
            params={"hotel_ids": context.external_property_id},
            operation="pull_cancellations",
        )
        if not result.success:
            raise BookingAdapterError(result.message or "Booking no pudo consultar cancelaciones")
        ids: list[str] = []
        for item in self._reservation_payloads(payload):
            if self._infer_event_type(item) == "cancelled" and item.get("reservation_id"):
                ids.append(str(item["reservation_id"]))
        return list(dict.fromkeys(ids))

    def acknowledge_reservations(
        self,
        context: OTAAdapterContext,
        reservation_ids: Iterable[str],
        *,
        successful: bool = True,
        error_message: str | None = None,
    ) -> OTAOperationResult:
        """Acknowledge processed reservation messages in Booking's queue."""
        ids = [str(value).strip() for value in reservation_ids if str(value).strip()]
        if not ids:
            return self._remember(
                OTAOperationResult(True, "acknowledge_reservations", self.provider_code, "No hay reservas para confirmar")
            )
        root = ET.Element(
            "OTA_HotelResNotifRS",
            {"TimeStamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "Target": "Production"},
        )
        if successful:
            ET.SubElement(root, "Success")
            reservations = ET.SubElement(root, "HotelReservations")
            for reservation_id in ids:
                reservation = ET.SubElement(reservations, "HotelReservation")
                info = ET.SubElement(reservation, "ResGlobalInfo")
                identifiers = ET.SubElement(info, "HotelReservationIDs")
                ET.SubElement(identifiers, "HotelReservationID", {"ResID_Value": reservation_id})
        else:
            errors = ET.SubElement(root, "Errors")
            for reservation_id in ids:
                ET.SubElement(
                    errors,
                    "Error",
                    {"Code": "193", "RecordID": reservation_id, "ShortText": (error_message or "Processing failed")[:180]},
                )
        body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        result, _payload = self._request(
            context,
            "POST",
            self._endpoint(context, "new_reservations", secure=True),
            data=body,
            headers={"Content-Type": "application/xml"},
            operation="acknowledge_reservations",
        )
        return self._remember(result)

    def push_inventory(self, context: OTAAdapterContext, payload: dict[str, Any]) -> OTAOperationResult:
        return self._push_availability(context, payload, "push_inventory")

    def push_rates(self, context: OTAAdapterContext, payload: dict[str, Any]) -> OTAOperationResult:
        return self._push_availability(context, payload, "push_rates")

    def push_restrictions(self, context: OTAAdapterContext, payload: dict[str, Any]) -> OTAOperationResult:
        return self._push_availability(context, payload, "push_restrictions")

    def cancel_reservation(
        self,
        context: OTAAdapterContext,
        external_reservation_id: str,
        payload: dict[str, Any] | None = None,
    ) -> OTAOperationResult:
        return self._unsupported_outbound(
            "cancel_reservation", "Booking no permite anunciar cancelaciones salientes en la v1"
        )

    def request_modification(
        self,
        context: OTAAdapterContext,
        external_reservation_id: str,
        payload: dict[str, Any],
    ) -> OTAOperationResult:
        return self._unsupported_outbound(
            "request_modification", "Booking no permite anunciar modificaciones salientes en la v1"
        )

    def reconcile_reservation(self, context: OTAAdapterContext, external_reservation_id: str) -> OTAOperationResult:
        result, _payload = self._request(
            context,
            "GET",
            self._endpoint(context, "new_reservations", secure=True),
            params={"id": str(external_reservation_id), "hotel_ids": context.external_property_id},
            operation="reconcile_reservation",
        )
        return self._remember(result)

    def _pull_reservations(
        self,
        context: OTAAdapterContext,
        endpoint_key: str,
        operation: str,
        expected_event: str,
    ) -> list[NormalizedOTAReservation]:
        result, payload = self._request(
            context,
            "GET",
            self._endpoint(context, endpoint_key, secure=True),
            params={"hotel_ids": context.external_property_id},
            operation=operation,
        )
        if not result.success:
            raise BookingAdapterError(result.message or "Booking no pudo consultar reservas")
        normalized: list[NormalizedOTAReservation] = []
        seen: set[str] = set()
        for item in self._reservation_payloads(payload):
            try:
                reservation = self.normalize_reservation_payload(item)
            except (KeyError, TypeError, ValueError):
                raise BookingAdapterError("Booking devolvio una reserva sin datos obligatorios") from None
            if expected_event == "new" and reservation.event_type == "cancelled":
                continue
            if expected_event == "modified" and reservation.event_type == "new":
                # Booking's modification queue may omit a status attribute;
                # being in that queue is enough to classify the message.
                reservation.event_type = "modified"
            if reservation.external_reservation_id in seen:
                continue
            seen.add(reservation.external_reservation_id)
            normalized.append(reservation)
        return normalized

    def _push_availability(
        self,
        context: OTAAdapterContext,
        payload: dict[str, Any],
        operation: str,
    ) -> OTAOperationResult:
        xml_body = payload.get("xml") or payload.get("body")
        if not xml_body:
            try:
                xml_body = self._build_availability_xml(context, payload)
            except (TypeError, ValueError, KeyError) as exc:
                return self._remember(OTAOperationResult(False, operation, self.provider_code, str(exc), retryable=False))
        if isinstance(xml_body, str):
            xml_body = xml_body.encode("utf-8")
        if not isinstance(xml_body, (bytes, bytearray)):
            return self._remember(
                OTAOperationResult(False, operation, self.provider_code, "La carga de Booking no es XML valido")
            )
        result, _payload = self._request(
            context,
            "POST",
            self._endpoint(context, "availability", secure=False),
            data=bytes(xml_body),
            headers={"Content-Type": "application/xml", "Accept-Version": "1.1"},
            operation=operation,
        )
        return self._remember(result)

    def _request(
        self,
        context: OTAAdapterContext,
        method: str,
        url: str,
        *,
        operation: str,
        params: dict[str, str] | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[OTAOperationResult, Any]:
        ready, message = self._validate_context(context)
        if not ready:
            return OTAOperationResult(False, operation, self.provider_code, message, retryable=False), None
        request_headers = self._auth_headers(context)
        request_headers.update({"Accept": "application/xml, application/json", **(headers or {})})
        try:
            response = self._requester(
                method,
                url,
                headers=request_headers,
                params=params,
                data=data,
                timeout=self._timeout(context),
            )
        except requests.RequestException:
            return (
                OTAOperationResult(
                    False,
                    operation,
                    self.provider_code,
                    "No se pudo contactar a Booking Connectivity.",
                    retryable=True,
                    raw_request=self._safe_request_summary(method, url),
                ),
                None,
            )
        status_code = int(getattr(response, "status_code", 0) or 0)
        response_body = getattr(response, "content", b"") or b""
        payload = self._decode_response(response_body, getattr(response, "headers", {}) or {})
        ok = bool(getattr(response, "ok", status_code < 400)) and status_code < 400
        message = "Booking acepto la operacion" if ok else self._provider_error(status_code, payload)
        return (
            OTAOperationResult(
                success=ok,
                operation=operation,
                provider_code=self.provider_code,
                message=message,
                payload=payload if isinstance(payload, dict) else None,
                http_status=status_code or None,
                retryable=status_code == 429 or status_code >= 500,
                raw_request=self._safe_request_summary(method, url),
            ),
            payload,
        )

    def _validate_context(self, context: OTAAdapterContext) -> tuple[bool, str]:
        if not context.external_property_id:
            return False, "Falta asociar el alojamiento de Booking con este hotel"
        auth = context.auth_config or {}
        if not any(auth.get(key) for key in ("access_token", "token", "jwt")):
            return False, "Booking Connectivity requiere un token de máquina del alojamiento"
        if not self._base_url(context, secure=True).startswith("https://"):
            return False, "Booking Connectivity solo admite endpoints HTTPS"
        return True, ""

    def _auth_headers(self, context: OTAAdapterContext) -> dict[str, str]:
        auth = context.auth_config or {}
        token = str(auth.get("access_token") or auth.get("token") or auth.get("jwt") or "").strip()
        return {"Authorization": f"Bearer {token}"}

    def _endpoint(self, context: OTAAdapterContext, key: str, *, secure: bool) -> str:
        custom = (context.settings or {}).get("endpoints") or {}
        value = custom.get(key) or self._DEFAULT_ENDPOINTS[key]
        if str(value).startswith("http"):
            return str(value)
        return urljoin(self._base_url(context, secure=secure).rstrip("/") + "/", str(value).lstrip("/"))

    def _base_url(self, context: OTAAdapterContext, *, secure: bool) -> str:
        settings = context.settings or {}
        configured = settings.get("secure_base_url" if secure else "supply_base_url")
        if configured:
            return str(configured).rstrip("/")
        return (self._SECURE_BASE if secure else self._SUPPLY_BASE).rstrip("/")

    @staticmethod
    def _timeout(context: OTAAdapterContext) -> float:
        try:
            return min(max(float((context.settings or {}).get("timeout_seconds", 20)), 1), 60)
        except (TypeError, ValueError):
            return 20.0

    @staticmethod
    def _safe_request_summary(method: str, url: str) -> str:
        return json.dumps({"method": method.upper(), "url": url}, ensure_ascii=True)

    @staticmethod
    def _decode_response(body: bytes, headers: dict[str, Any]) -> Any:
        if not body:
            return {}
        text = body.decode("utf-8", errors="replace").strip()
        content_type = str(headers.get("Content-Type") or headers.get("content-type") or "").lower()
        if "json" in content_type or text.startswith(("{", "[")):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw_status": "invalid_json"}
        try:
            return ET.fromstring(body)
        except ET.ParseError:
            return {"raw_status": "unparseable_response"}

    @staticmethod
    def _provider_error(status_code: int, payload: Any) -> str:
        if status_code == 401:
            return "Booking rechazo las credenciales o el permiso del alojamiento"
        if status_code == 403:
            return "Booking no autorizo esta operación para el alojamiento"
        if status_code == 429:
            return "Booking solicito reintentar por limite de llamadas"
        if status_code >= 500:
            return "Booking no esta disponible; el intento puede reintentarse"
        if isinstance(payload, dict):
            detail = payload.get("message") or payload.get("error")
            if detail:
                return f"Booking rechazo la operacion: {str(detail)[:180]}"
        return f"Booking rechazo la operacion (HTTP {status_code})"

    def _reservation_payloads(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            values = payload.get("reservations") or payload.get("data") or payload.get("items")
            if isinstance(values, dict):
                values = values.get("reservation") or values.get("reservations") or []
            if isinstance(values, list):
                return [item for item in values if isinstance(item, dict)]
            if payload.get("reservation_id"):
                return [payload]
            return []
        if not isinstance(payload, ET.Element):
            return []
        return [item for item in (self._xml_reservation_to_payload(node) for node in payload.iter()) if item]

    def _xml_reservation_to_payload(self, node: ET.Element) -> dict[str, Any] | None:
        if self._local_name(node.tag) != "HotelReservation":
            return None
        descendants = list(node.iter())
        ids = [item.attrib.get("ResID_Value") for item in descendants if self._local_name(item.tag) == "HotelReservationID"]
        reservation_id = next((value for value in ids if value), None)
        time_span = next((item for item in descendants if self._local_name(item.tag) == "TimeSpan"), None)
        checkin = (time_span.attrib.get("Start") if time_span is not None else None) or (time_span.attrib.get("start") if time_span is not None else None)
        checkout = (time_span.attrib.get("End") if time_span is not None else None) or (time_span.attrib.get("end") if time_span is not None else None)
        if not reservation_id or not checkin or not checkout:
            return None
        given = next((item.text for item in descendants if self._local_name(item.tag) == "GivenName" and item.text), "")
        surname = next((item.text for item in descendants if self._local_name(item.tag) in {"Surname", "LastName"} and item.text), "")
        room = next((item for item in descendants if self._local_name(item.tag) == "RoomType"), None)
        total = next((item for item in descendants if self._local_name(item.tag) == "Total"), None)
        guest_counts = [item for item in descendants if self._local_name(item.tag) == "GuestCount"]
        adults = sum(int(item.attrib.get("Count", "0") or 0) for item in guest_counts if item.attrib.get("AgeQualifyingCode") == "10") or 1
        children = sum(int(item.attrib.get("Count", "0") or 0) for item in guest_counts if item.attrib.get("AgeQualifyingCode") == "8")
        status = node.attrib.get("ResStatus") or node.attrib.get("res_status") or ""
        return {
            "reservation_id": reservation_id,
            "checkin": checkin,
            "checkout": checkout,
            "guest_name": f"{given or 'OTA'} {surname}".strip(),
            "room_type": room.attrib.get("RoomTypeCode") if room is not None else None,
            "total_price": (total.attrib.get("AmountAfterTax") or total.attrib.get("AmountBeforeTax")) if total is not None else None,
            "currency": total.attrib.get("CurrencyCode") if total is not None else None,
            "num_adults": adults,
            "num_children": children,
            "event": status,
            "raw_xml": ET.tostring(node, encoding="unicode"),
        }

    @staticmethod
    def _build_availability_xml(context: OTAAdapterContext, payload: dict[str, Any]) -> bytes:
        updates = payload.get("updates")
        if not isinstance(updates, list) or not updates:
            raise ValueError("La publicación de Booking requiere una lista de cambios")
        root = ET.Element("request")
        rooms: dict[str, ET.Element] = {}
        for update in updates:
            if not isinstance(update, dict):
                raise ValueError("Cada cambio de Booking debe ser un objeto")
            room_id = str(update.get("room_id") or update.get("room") or "").strip()
            value = str(update.get("date") or update.get("value") or "").strip()
            if not room_id or not value:
                raise ValueError("Cada cambio de Booking requiere room_id y date")
            room = rooms.setdefault(room_id, ET.SubElement(root, "room", {"id": room_id}))
            date_node = ET.SubElement(room, "date", {"value": value})
            rate_id = update.get("rate_id") or update.get("rate")
            rate_attrs: dict[str, str] = {}
            if rate_id not in (None, ""):
                rate_attrs["id"] = str(rate_id)
            rate_attrs["currencycode"] = str(update.get("currency") or payload.get("currency") or "ARS").upper()
            for key in (
                "roomstosell",
                "price",
                "price1",
                "closed",
                "minimumstay",
                "minimumstay_arrival",
                "maximumstay",
                "maximumstay_arrival",
                "exactstay_arrival",
                "closedonarrival",
                "closedondeparture",
                "min_advance_res",
                "max_advance_res",
            ):
                if update.get(key) not in (None, ""):
                    rate_attrs[key] = str(update[key])
            ET.SubElement(date_node, "rate", rate_attrs)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _local_name(tag: str) -> str:
        return str(tag).rsplit("}", 1)[-1]

    def _unsupported_outbound(self, operation: str, message: str) -> OTAOperationResult:
        return self._remember(OTAOperationResult(False, operation, self.provider_code, message, retryable=False))

    def _remember(self, result: OTAOperationResult) -> OTAOperationResult:
        self.last_result = result
        return result

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
