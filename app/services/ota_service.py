"""
OTA Integration Service.
Handles incoming reservations from Booking.com and Expedia,
and outgoing inventory/availability updates.
Uses row-level locking to handle race conditions on simultaneous bookings.
"""
import hashlib
import json
import secrets
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.commercial import ProductRoomCompatibility, RatePlan, SellableProduct
from app.models.reservation import Reservation, ReservationStatusEnum, ReservationSourceEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.guest import Guest
from app.models.ota import OTAReservationMapping, OTAWebhookCredential, OTASyncStatusEnum
from app.models.ota_core import (
    OTAConnection,
    OTAProvider,
    OTARatePlanMapping,
    OTAReservationLink,
    OTAReservationLifecycleEnum,
    OTARoomMapping,
)
from app.models.hotel_config import HotelConfiguration
from app.services.ota import NormalizedOTAReservation, get_default_adapter
from app.services.reservation_service import (
    create_reservation,
    find_available_rooms,
    generate_confirmation_code,
    ReservationError,
    transition_reservation_status,
    update_reservation_fields,
)
from app.schemas.reservation import ReservationCreate, ReservationUpdate


class OTAError(Exception):
    """Custom exception for OTA integration errors."""
    pass


class OTAAuthError(OTAError):
    """Raised when a webhook is missing a valid hotel-scoped secret."""
    pass


def _hotel_default_currency(db: Session, hotel_id: int) -> str:
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
    return str(getattr(config, "default_currency", None) or "ARS").strip().upper()[:3] or "ARS"


class OTAIntegrationService:
    """
    Handles bidirectional synchronization with OTAs (Booking.com, Expedia).
    
    Inbound: Receives reservation notifications via webhooks.
    Outbound: Pushes availability/inventory updates when internal state changes.
    """

    @staticmethod
    def _normalize_secret(secret: str | None) -> str:
        return (secret or "").strip()

    @staticmethod
    def _hash_secret(secret: str) -> str:
        normalized = OTAIntegrationService._normalize_secret(secret)
        if not normalized:
            raise OTAAuthError("Webhook OTA no autorizado")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _extract_external_property_id(payload: dict) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        candidates = [
            payload.get("external_property_id"),
            payload.get("property_id"),
            payload.get("propertyId"),
            payload.get("hotel_id"),
            payload.get("hotelId"),
        ]
        nested_property = payload.get("property")
        if isinstance(nested_property, dict):
            candidates.extend(
                [
                    nested_property.get("id"),
                    nested_property.get("property_id"),
                    nested_property.get("hotel_id"),
                    nested_property.get("code"),
                ]
            )
        for candidate in candidates:
            if candidate in (None, ""):
                continue
            return str(candidate).strip()
        return None

    @staticmethod
    def _resolve_webhook_credential(
        db: Session,
        hotel_id: int,
        provider: str,
        webhook_secret: str,
        payload: dict,
    ) -> OTAWebhookCredential:
        credential = (
            db.query(OTAWebhookCredential)
            .filter(
                OTAWebhookCredential.hotel_id == hotel_id,
                OTAWebhookCredential.provider == provider,
                OTAWebhookCredential.is_active == True,
            )
            .first()
        )
        if not credential:
            raise OTAAuthError("Webhook OTA no configurado para este hotel")

        presented_hash = OTAIntegrationService._hash_secret(webhook_secret)
        if presented_hash != credential.webhook_secret_hash:
            raise OTAAuthError("Webhook OTA no autorizado")

        external_property_id = OTAIntegrationService._extract_external_property_id(payload)
        if credential.external_property_id and external_property_id:
            if str(credential.external_property_id).strip() != external_property_id:
                raise OTAAuthError("Webhook OTA no coincide con el hotel configurado")

        return credential

    @staticmethod
    def generate_webhook_secret() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def _ensure_foundation_provider(db: Session, provider_code: str) -> OTAProvider:
        provider = db.query(OTAProvider).filter(OTAProvider.code == provider_code).first()
        if provider:
            return provider
        names = {
            "booking": "Booking.com",
            "expedia": "Expedia Group",
            "despegar": "Despegar",
        }
        provider = OTAProvider(
            code=provider_code,
            name=names.get(provider_code, provider_code.title()),
            auth_type="partner_api",
            security_model="partner_credentials",
            is_active=True,
        )
        db.add(provider)
        db.flush()
        return provider

    @staticmethod
    def _sync_foundation_reservation_link(
        db: Session,
        *,
        hotel_id: int,
        provider_code: str,
        external_reservation_id: str,
        external_confirmation_code: str | None,
        reservation: Reservation | None,
        payload: dict,
        gross_total: float | None,
        currency_code: str | None,
        sync_status: str,
        provider_state: OTAReservationLifecycleEnum = OTAReservationLifecycleEnum.CONFIRMED,
        error_message: str | None = None,
        rate_plan_id: int | None = None,
    ) -> OTAReservationLink:
        provider = OTAIntegrationService._ensure_foundation_provider(db, provider_code)
        connection = (
            db.query(OTAConnection)
            .filter(
                OTAConnection.hotel_id == hotel_id,
                OTAConnection.provider_id == provider.id,
                OTAConnection.is_enabled == True,
            )
            .order_by(OTAConnection.environment.asc())
            .first()
        )
        link = (
            db.query(OTAReservationLink)
            .filter(
                OTAReservationLink.hotel_id == hotel_id,
                OTAReservationLink.provider_id == provider.id,
                OTAReservationLink.external_reservation_id == external_reservation_id,
            )
            .first()
        )
        if not link:
            link = OTAReservationLink(
                hotel_id=hotel_id,
                provider_id=provider.id,
                connection_id=connection.id if connection else None,
                reservation_id=reservation.id if reservation else None,
                external_reservation_id=external_reservation_id,
            )
            db.add(link)

        link.connection_id = connection.id if connection else None
        link.reservation_id = reservation.id if reservation else None
        link.rate_plan_id = rate_plan_id or (reservation.rate_plan_id if reservation else None)
        link.external_confirmation_code = external_confirmation_code
        link.provider_state = provider_state
        link.sync_status = sync_status
        link.currency_code = currency_code
        link.gross_total = gross_total
        link.raw_payload_encrypted = json.dumps(payload)
        link.error_message = error_message
        link.last_seen_at = datetime.now(timezone.utc)
        db.flush()
        return link

    @staticmethod
    def _split_guest_name(full_name: str) -> tuple[str, str]:
        name_parts = (full_name or "OTA Guest").strip().split(" ", 1)
        first_name = name_parts[0] if name_parts and name_parts[0] else "OTA"
        last_name = name_parts[1] if len(name_parts) > 1 else "Guest"
        return first_name, last_name

    @staticmethod
    def _normalize_event_type(raw_value: str | None) -> str:
        normalized = str(raw_value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if any(token in normalized for token in ("cancel", "void", "deleted", "delete")):
            return "cancelled"
        if any(token in normalized for token in ("modify", "modified", "update", "updated", "change", "changed", "amend")):
            return "modified"
        return "new"

    @staticmethod
    def _sync_mapping_payload(
        mapping: OTAReservationMapping,
        *,
        guest_name: str,
        payload: dict,
        sync_status: OTASyncStatusEnum | None = None,
        error_message: str | None = None,
    ) -> None:
        mapping.ota_guest_name = guest_name
        mapping.raw_payload = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        if sync_status is not None:
            mapping.sync_status = sync_status
        mapping.error_message = error_message

    @staticmethod
    def _sync_guest_record(
        db: Session,
        *,
        hotel_id: int,
        guest: Guest | None,
        normalized: NormalizedOTAReservation,
    ) -> Guest:
        first_name, last_name = OTAIntegrationService._split_guest_name(normalized.guest_full_name)
        guest = guest or Guest(hotel_id=hotel_id, first_name=first_name, last_name=last_name)
        guest.hotel_id = hotel_id
        guest.first_name = first_name
        guest.last_name = last_name
        if normalized.guest_email is not None:
            guest.email = normalized.guest_email
        if normalized.guest_phone is not None:
            guest.phone = normalized.guest_phone
        if normalized.guest_nationality is not None:
            guest.nationality = normalized.guest_nationality
        if normalized.guest_document_type is not None:
            guest.document_type = normalized.guest_document_type
        if normalized.guest_document_number is not None:
            guest.document_number = normalized.guest_document_number
        db.add(guest)
        db.flush()
        return guest

    @staticmethod
    def _select_room_for_normalized_reservation(
        db: Session,
        *,
        hotel_id: int,
        reservation_id: int | None,
        normalized: NormalizedOTAReservation,
        candidate_categories: list[RoomCategory],
        current_room: Room | None = None,
    ) -> tuple[RoomCategory | None, Room | None]:
        from app.services.reservation_service import check_room_availability

        category_by_id = {category.id: category for category in candidate_categories}
        if (
            current_room
            and current_room.hotel_id == hotel_id
            and current_room.category_id in category_by_id
            and check_room_availability(
                db,
                current_room.id,
                normalized.check_in_date,
                normalized.check_out_date,
                hotel_id=hotel_id,
                exclude_reservation_id=reservation_id,
            )
        ):
            locked_room = (
                db.query(Room)
                .filter(Room.id == current_room.id, Room.hotel_id == hotel_id)
                .enable_eagerloads(False)
                .with_for_update()
                .first()
            )
            if locked_room:
                return category_by_id[current_room.category_id], locked_room

        for category in candidate_categories:
            available_rooms = find_available_rooms(
                db,
                category.id,
                normalized.check_in_date,
                normalized.check_out_date,
                hotel_id=hotel_id,
                exclude_reservation_id=reservation_id,
            )
            if not available_rooms:
                continue
            room = (
                db.query(Room)
                .filter(Room.id == available_rooms[0].id, Room.hotel_id == hotel_id)
                .enable_eagerloads(False)
                .with_for_update()
                .first()
            )
            if room:
                return category, room
        return None, None

    @staticmethod
    def _mark_reservation_manual_review(
        reservation: Reservation,
        *,
        reason: str,
        append_note: bool = True,
    ) -> None:
        reservation.requires_manual_review = True
        reservation.allocation_status = "manual_review"
        if append_note:
            existing = (reservation.notes or "").strip()
            note = f"[OTA MANUAL REVIEW] {reason}".strip()
            reservation.notes = f"{existing}\n{note}".strip() if existing else note

    @staticmethod
    def _reservation_source_for_provider(provider_code: str) -> ReservationSourceEnum:
        if provider_code == "booking":
            return ReservationSourceEnum.BOOKING
        if provider_code == "expedia":
            return ReservationSourceEnum.EXPEDIA
        return ReservationSourceEnum.OTHER_OTA

    @staticmethod
    def _create_legacy_mapping(
        db: Session,
        *,
        hotel_id: int,
        provider_code: str,
        external_reservation_id: str,
        guest_name: str,
        payload: dict,
    ) -> OTAReservationMapping:
        mapping = OTAReservationMapping(
            hotel_id=hotel_id,
            ota_name=provider_code,
            ota_reservation_id=external_reservation_id,
            ota_guest_name=guest_name,
            raw_payload=json.dumps(payload),
            sync_status=OTASyncStatusEnum.PENDING,
        )
        db.add(mapping)
        db.flush()
        return mapping

    @staticmethod
    def _apply_financial_snapshot(
        db: Session,
        hotel_id: int,
        reservation: Reservation,
        normalized: NormalizedOTAReservation,
        *,
        preserve_operational_status: bool = False,
    ) -> None:
        gross_total = normalized.gross_total or 0.0
        tax_total = normalized.tax_total or 0.0
        fee_total = normalized.fee_total or 0.0
        commission_total = normalized.commission_total or 0.0
        subtotal = gross_total - tax_total - fee_total
        if subtotal < 0:
            subtotal = gross_total

        reservation.total_amount = gross_total
        reservation.subtotal_amount = subtotal
        reservation.tax_amount = tax_total
        reservation.fee_amount = fee_total
        reservation.commission_amount = commission_total
        reservation.net_amount = gross_total - commission_total
        collection_model = OTAIntegrationService._normalize_collection_model(
            normalized.payment_collection_model,
            paid_amount=normalized.paid_amount,
            gross_total=gross_total,
        )
        amount_paid = OTAIntegrationService._resolve_paid_amount(
            normalized=normalized,
            collection_model=collection_model,
            gross_total=gross_total,
        )
        reservation.amount_paid = amount_paid
        reservation.payment_collection_model = collection_model
        reservation.settlement_status = OTAIntegrationService._normalize_settlement_status(
            normalized.settlement_status,
            collection_model=collection_model,
            amount_paid=amount_paid,
            gross_total=gross_total,
        )
        if not preserve_operational_status:
            if gross_total > 0 and amount_paid >= gross_total:
                reservation.status = ReservationStatusEnum.FULLY_PAID
            elif amount_paid > 0:
                reservation.status = ReservationStatusEnum.DEPOSIT_PAID
            else:
                reservation.status = ReservationStatusEnum.PENDING
        reservation.source_provider_code = normalized.provider_code
        reservation.external_confirmation_code = (
            normalized.external_confirmation_code or normalized.external_reservation_id
        )
        reservation.currency_code = normalized.currency_code or _hotel_default_currency(db, hotel_id)
        reservation.arrival_time_hint = normalized.arrival_time_hint
        reservation.pricing_snapshot = json.dumps(
            {
                "provider_code": normalized.provider_code,
                "gross_total": normalized.gross_total,
                "tax_total": normalized.tax_total,
                "fee_total": normalized.fee_total,
                "commission_total": normalized.commission_total,
                "paid_amount": amount_paid,
                "payment_collection_model": collection_model,
                "settlement_status": reservation.settlement_status,
                "currency_code": normalized.currency_code,
                "received_at": normalized.received_at.isoformat() if normalized.received_at else None,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        if normalized.notes:
            reservation.requested_attributes_json = json.dumps(
                {"notes": normalized.notes},
                ensure_ascii=True,
                sort_keys=True,
            )

    @staticmethod
    def _materialize_incoming_reservation(
        db: Session,
        *,
        hotel_id: int,
        mapping: OTAReservationMapping,
        normalized: NormalizedOTAReservation,
        payload: dict,
    ) -> OTAReservationMapping:
        sellable_product, rate_plan, candidate_categories = OTAIntegrationService._resolve_commercial_context(
            db,
            hotel_id=hotel_id,
            provider_code=normalized.provider_code,
            normalized=normalized,
        )
        if not candidate_categories:
            raise OTAError(
                f"Unknown {normalized.provider_code} room/product code: "
                f"{normalized.sellable_product_code or normalized.rate_plan_code or 'missing'}"
            )

        selected_category, room = OTAIntegrationService._select_room_for_normalized_reservation(
            db,
            hotel_id=hotel_id,
            reservation_id=None,
            normalized=normalized,
            candidate_categories=candidate_categories,
        )

        if not selected_category or not room:
            mapping.sync_status = OTASyncStatusEnum.CONFLICT
            mapping.error_message = "No rooms available - overbooking detected"
            db.flush()
            raise OTAError(
                f"OVERBOOKING: No rooms available for {normalized.provider_code} reservation "
                f"{normalized.external_reservation_id} "
                f"({normalized.sellable_product_code or normalized.rate_plan_code}, "
                f"{normalized.check_in_date} to {normalized.check_out_date})"
            )

        from app.services.reservation_service import check_room_availability

        if not check_room_availability(
            db,
            room.id,
            normalized.check_in_date,
            normalized.check_out_date,
            hotel_id=hotel_id,
        ):
            mapping.sync_status = OTASyncStatusEnum.CONFLICT
            mapping.error_message = "Room taken after lock - race condition handled"
            db.flush()
            raise OTAError(
                f"RACE CONDITION: Room {room.room_number} was taken between "
                f"availability check and lock acquisition"
            )

        if room.hotel_id != hotel_id:
            mapping.sync_status = OTASyncStatusEnum.CONFLICT
            mapping.error_message = "Room does not belong to the OTA hotel context"
            db.flush()
            raise OTAError("Cross-hotel room assignment blocked")

        guest = OTAIntegrationService._sync_guest_record(
            db,
            hotel_id=hotel_id,
            guest=None,
            normalized=normalized,
        )

        reservation_data = ReservationCreate(
            guest_id=guest.id,
            category_id=selected_category.id,
                room_id=room.id,
                check_in_date=normalized.check_in_date,
                check_out_date=normalized.check_out_date,
                num_adults=normalized.num_adults,
                num_children=normalized.num_children,
                sellable_product_id=sellable_product.id if sellable_product else None,
                rate_plan_id=rate_plan.id if rate_plan else None,
                source=OTAIntegrationService._reservation_source_for_provider(normalized.provider_code),
                external_id=normalized.external_reservation_id,
                pricing_channel_code=normalized.provider_code,
                target_currency=normalized.currency_code,
            )
        reservation = create_reservation(db, reservation_data, hotel_id=hotel_id)
        reservation.sellable_product_id = sellable_product.id if sellable_product else None
        reservation.rate_plan_id = rate_plan.id if rate_plan else None
        OTAIntegrationService._apply_financial_snapshot(db, hotel_id, reservation, normalized)

        mapping.reservation_id = reservation.id
        mapping.sync_status = OTASyncStatusEnum.SYNCED
        OTAIntegrationService._sync_foundation_reservation_link(
            db,
            hotel_id=hotel_id,
            provider_code=normalized.provider_code,
            external_reservation_id=normalized.external_reservation_id,
            external_confirmation_code=normalized.external_confirmation_code,
            reservation=reservation,
            payload=payload,
            gross_total=normalized.gross_total,
            currency_code=normalized.currency_code,
            sync_status=mapping.sync_status.value,
            rate_plan_id=rate_plan.id if rate_plan else None,
        )
        db.flush()
        return mapping

    @staticmethod
    def _resolve_commercial_context(
        db: Session,
        *,
        hotel_id: int,
        provider_code: str,
        normalized: NormalizedOTAReservation,
    ) -> tuple[SellableProduct | None, RatePlan | None, list[RoomCategory]]:
        provider = OTAIntegrationService._ensure_foundation_provider(db, provider_code)

        sellable_product = None
        rate_plan = None
        category_ids: list[int] = []

        product_code = normalized.sellable_product_code or ""
        if product_code:
            room_mapping = (
                db.query(OTARoomMapping)
                .filter(
                    OTARoomMapping.hotel_id == hotel_id,
                    OTARoomMapping.provider_id == provider.id,
                    OTARoomMapping.external_room_type_id == product_code,
                    OTARoomMapping.is_active == True,
                )
                .first()
            )
            if room_mapping:
                sellable_product = room_mapping.sellable_product or sellable_product
                if room_mapping.room_category_id:
                    category_ids.append(room_mapping.room_category_id)

            if sellable_product is None:
                sellable_product = (
                    db.query(SellableProduct)
                    .filter(
                        SellableProduct.hotel_id == hotel_id,
                        SellableProduct.code == product_code,
                        SellableProduct.is_active == True,
                    )
                    .first()
                )

            if sellable_product and sellable_product.primary_room_category_id:
                category_ids.append(sellable_product.primary_room_category_id)

            if sellable_product:
                compatibilities = (
                    db.query(ProductRoomCompatibility)
                    .filter(
                        ProductRoomCompatibility.hotel_id == hotel_id,
                        ProductRoomCompatibility.sellable_product_id == sellable_product.id,
                        ProductRoomCompatibility.allows_auto_assignment == True,
                    )
                    .order_by(ProductRoomCompatibility.priority.asc(), ProductRoomCompatibility.id.asc())
                    .all()
                )
                category_ids.extend(item.room_category_id for item in compatibilities)

        if normalized.rate_plan_code:
            rate_plan_mapping = (
                db.query(OTARatePlanMapping)
                .filter(
                    OTARatePlanMapping.hotel_id == hotel_id,
                    OTARatePlanMapping.provider_id == provider.id,
                    OTARatePlanMapping.external_rate_plan_id == normalized.rate_plan_code,
                    OTARatePlanMapping.is_active == True,
                )
                .first()
            )
            if rate_plan_mapping:
                rate_plan = rate_plan_mapping.rate_plan
            if rate_plan is None:
                rate_plan = (
                    db.query(RatePlan)
                    .filter(
                        RatePlan.hotel_id == hotel_id,
                        RatePlan.code == normalized.rate_plan_code,
                        RatePlan.is_active == True,
                    )
                    .first()
                )

        fallback_category_code = normalized.sellable_product_code or normalized.rate_plan_code or ""
        if fallback_category_code:
            fallback_category = (
                db.query(RoomCategory)
                .filter(
                    RoomCategory.hotel_id == hotel_id,
                    RoomCategory.code == fallback_category_code,
                )
                .first()
            )
            if fallback_category:
                category_ids.append(fallback_category.id)

        categories: list[RoomCategory] = []
        seen = set()
        for category_id in category_ids:
            if category_id in seen:
                continue
            category = (
                db.query(RoomCategory)
                .filter(RoomCategory.id == category_id, RoomCategory.hotel_id == hotel_id)
                .first()
            )
            if category:
                categories.append(category)
                seen.add(category.id)

        return sellable_product, rate_plan, categories

    @staticmethod
    def _process_existing_incoming_reservation(
        db: Session,
        *,
        hotel_id: int,
        mapping: OTAReservationMapping,
        normalized: NormalizedOTAReservation,
        payload: dict,
    ) -> OTAReservationMapping:
        reservation = mapping.reservation
        if reservation is None and mapping.reservation_id is not None:
            reservation = (
                db.query(Reservation)
                .filter(Reservation.id == mapping.reservation_id, Reservation.hotel_id == hotel_id)
                .first()
            )

        if reservation is None:
            OTAIntegrationService._sync_mapping_payload(
                mapping,
                guest_name=normalized.guest_full_name,
                payload=payload,
                sync_status=OTASyncStatusEnum.PENDING,
                error_message=None,
            )
            return OTAIntegrationService._materialize_incoming_reservation(
                db,
                hotel_id=hotel_id,
                mapping=mapping,
                normalized=normalized,
                payload=payload,
            )

        OTAIntegrationService._sync_mapping_payload(
            mapping,
            guest_name=normalized.guest_full_name,
            payload=payload,
            error_message=None,
        )
        OTAIntegrationService._sync_guest_record(
            db,
            hotel_id=hotel_id,
            guest=reservation.guest,
            normalized=normalized,
        )

        event_type = OTAIntegrationService._normalize_event_type(normalized.event_type)
        if event_type == "cancelled":
            return OTAIntegrationService._cancel_existing_reservation_from_normalized(
                db,
                hotel_id=hotel_id,
                mapping=mapping,
                reservation=reservation,
                normalized=normalized,
                payload=payload,
            )
        return OTAIntegrationService._update_existing_reservation_from_normalized(
            db,
            hotel_id=hotel_id,
            mapping=mapping,
            reservation=reservation,
            normalized=normalized,
            payload=payload,
        )

    @staticmethod
    def _update_existing_reservation_from_normalized(
        db: Session,
        *,
        hotel_id: int,
        mapping: OTAReservationMapping,
        reservation: Reservation,
        normalized: NormalizedOTAReservation,
        payload: dict,
    ) -> OTAReservationMapping:
        if reservation.status == ReservationStatusEnum.CANCELLED:
            OTAIntegrationService._mark_reservation_manual_review(
                reservation,
                reason="Llego una modificacion OTA sobre una reserva ya cancelada internamente.",
            )
            mapping.sync_status = OTASyncStatusEnum.CONFLICT
            mapping.error_message = "Modification received for a cancelled reservation"
            OTAIntegrationService._sync_foundation_reservation_link(
                db,
                hotel_id=hotel_id,
                provider_code=normalized.provider_code,
                external_reservation_id=normalized.external_reservation_id,
                external_confirmation_code=normalized.external_confirmation_code,
                reservation=reservation,
                payload=payload,
                gross_total=normalized.gross_total,
                currency_code=normalized.currency_code,
                sync_status="manual_resolution_required",
                provider_state=OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED,
                error_message=mapping.error_message,
                rate_plan_id=reservation.rate_plan_id,
            )
            db.flush()
            return mapping

        sellable_product, rate_plan, candidate_categories = OTAIntegrationService._resolve_commercial_context(
            db,
            hotel_id=hotel_id,
            provider_code=normalized.provider_code,
            normalized=normalized,
        )
        if not candidate_categories:
            OTAIntegrationService._sync_mapping_payload(
                mapping,
                guest_name=normalized.guest_full_name,
                payload=payload,
                sync_status=OTASyncStatusEnum.CONFLICT,
                error_message="No se pudo mapear el producto OTA a una categoria interna",
            )
            OTAIntegrationService._mark_reservation_manual_review(
                reservation,
                reason="El cambio OTA no pudo mapearse a una categoria interna.",
            )
            OTAIntegrationService._sync_foundation_reservation_link(
                db,
                hotel_id=hotel_id,
                provider_code=normalized.provider_code,
                external_reservation_id=normalized.external_reservation_id,
                external_confirmation_code=normalized.external_confirmation_code,
                reservation=reservation,
                payload=payload,
                gross_total=normalized.gross_total,
                currency_code=normalized.currency_code,
                sync_status="manual_resolution_required",
                provider_state=OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED,
                error_message=mapping.error_message,
                rate_plan_id=rate_plan.id if rate_plan else reservation.rate_plan_id,
            )
            db.flush()
            return mapping

        selected_category, selected_room = OTAIntegrationService._select_room_for_normalized_reservation(
            db,
            hotel_id=hotel_id,
            reservation_id=reservation.id,
            normalized=normalized,
            candidate_categories=candidate_categories,
            current_room=reservation.room,
        )

        new_notes = normalized.notes if normalized.notes is not None else reservation.notes
        update_payload = ReservationUpdate(
            check_in_date=normalized.check_in_date,
            check_out_date=normalized.check_out_date,
            num_adults=normalized.num_adults,
            num_children=normalized.num_children,
            notes=new_notes,
        )

        try:
            update_reservation_fields(
                db,
                reservation,
                update_payload,
                hotel_id=hotel_id,
            )
        except ReservationError:
            reservation.check_in_date = normalized.check_in_date
            reservation.check_out_date = normalized.check_out_date
            reservation.num_adults = normalized.num_adults
            reservation.num_children = normalized.num_children
            reservation.notes = new_notes

        reservation.sellable_product_id = sellable_product.id if sellable_product else None
        reservation.rate_plan_id = rate_plan.id if rate_plan else None
        reservation.category_id = selected_category.id if selected_category else reservation.category_id
        reservation.source_provider_code = normalized.provider_code
        reservation.external_id = normalized.external_reservation_id
        reservation.external_confirmation_code = (
            normalized.external_confirmation_code or normalized.external_reservation_id
        )
        OTAIntegrationService._apply_financial_snapshot(
            db,
            hotel_id,
            reservation,
            normalized,
            preserve_operational_status=reservation.status in {
                ReservationStatusEnum.CHECKED_IN,
                ReservationStatusEnum.CHECKED_OUT,
                ReservationStatusEnum.CANCELLED,
            },
        )

        if selected_room and selected_category:
            reservation.room_id = selected_room.id
            reservation.category_id = selected_category.id
            reservation.requires_manual_review = False
            reservation.allocation_status = "assigned"
            mapping.sync_status = OTASyncStatusEnum.SYNCED
            mapping.error_message = None
            provider_state = OTAReservationLifecycleEnum.MODIFIED
            sync_status = mapping.sync_status.value
            error_message = None
        else:
            reservation.room_id = None
            OTAIntegrationService._mark_reservation_manual_review(
                reservation,
                reason="El cambio OTA dejo la reserva sin una habitacion valida disponible.",
            )
            mapping.sync_status = OTASyncStatusEnum.CONFLICT
            mapping.error_message = "Reservation updated from OTA but requires manual reassignment"
            provider_state = OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED
            sync_status = "manual_resolution_required"
            error_message = mapping.error_message

        OTAIntegrationService._sync_foundation_reservation_link(
            db,
            hotel_id=hotel_id,
            provider_code=normalized.provider_code,
            external_reservation_id=normalized.external_reservation_id,
            external_confirmation_code=normalized.external_confirmation_code,
            reservation=reservation,
            payload=payload,
            gross_total=normalized.gross_total,
            currency_code=normalized.currency_code,
            sync_status=sync_status,
            provider_state=provider_state,
            error_message=error_message,
            rate_plan_id=rate_plan.id if rate_plan else reservation.rate_plan_id,
        )
        db.flush()
        return mapping

    @staticmethod
    def _cancel_existing_reservation_from_normalized(
        db: Session,
        *,
        hotel_id: int,
        mapping: OTAReservationMapping,
        reservation: Reservation,
        normalized: NormalizedOTAReservation,
        payload: dict,
    ) -> OTAReservationMapping:
        if reservation.status in {ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT}:
            OTAIntegrationService._mark_reservation_manual_review(
                reservation,
                reason="La OTA informo una cancelacion pero la reserva ya estaba operada.",
            )
            reservation.settlement_status = "manual_resolution_required"
            mapping.sync_status = OTASyncStatusEnum.CONFLICT
            mapping.error_message = "Cancellation received after check-in/checkout; manual resolution required"
            OTAIntegrationService._sync_foundation_reservation_link(
                db,
                hotel_id=hotel_id,
                provider_code=normalized.provider_code,
                external_reservation_id=normalized.external_reservation_id,
                external_confirmation_code=normalized.external_confirmation_code,
                reservation=reservation,
                payload=payload,
                gross_total=normalized.gross_total,
                currency_code=normalized.currency_code,
                sync_status="manual_resolution_required",
                provider_state=OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED,
                error_message=mapping.error_message,
                rate_plan_id=reservation.rate_plan_id,
            )
            db.flush()
            return mapping

        if reservation.status != ReservationStatusEnum.CANCELLED:
            transition_reservation_status(
                db,
                reservation,
                ReservationStatusEnum.CANCELLED,
                hotel_id=hotel_id,
                reason_code="ota_cancelled",
                notes=f"Cancelada por {normalized.provider_code} via webhook",
            )
        reservation.requires_manual_review = False
        reservation.allocation_status = "cancelled"
        reservation.settlement_status = (
            "review_cancellation" if reservation.payment_collection_model != "hotel_collect" else "not_applicable"
        )
        mapping.sync_status = OTASyncStatusEnum.SYNCED
        mapping.error_message = None
        OTAIntegrationService._sync_foundation_reservation_link(
            db,
            hotel_id=hotel_id,
            provider_code=normalized.provider_code,
            external_reservation_id=normalized.external_reservation_id,
            external_confirmation_code=normalized.external_confirmation_code,
            reservation=reservation,
            payload=payload,
            gross_total=normalized.gross_total,
            currency_code=normalized.currency_code,
            sync_status=mapping.sync_status.value,
            provider_state=OTAReservationLifecycleEnum.CANCELLED,
            error_message=None,
            rate_plan_id=reservation.rate_plan_id,
        )
        db.flush()
        return mapping

    @staticmethod
    def _process_normalized_webhook(
        db: Session,
        *,
        hotel_id: int,
        provider_code: str,
        webhook_secret: str,
        payload: dict,
        external_reservation_id_key: str,
    ) -> OTAReservationMapping:
        OTAIntegrationService._resolve_webhook_credential(db, hotel_id, provider_code, webhook_secret, payload)

        external_reservation_id = payload.get(external_reservation_id_key, "")
        if not external_reservation_id:
            raise OTAError(f"Missing {external_reservation_id_key} in {provider_code} payload")

        existing = db.query(OTAReservationMapping).filter(
            OTAReservationMapping.hotel_id == hotel_id,
            OTAReservationMapping.ota_name == provider_code,
            OTAReservationMapping.ota_reservation_id == external_reservation_id,
        ).first()
        adapter = get_default_adapter(provider_code)
        normalized = adapter.normalize_reservation_payload(payload)
        if existing:
            try:
                return OTAIntegrationService._process_existing_incoming_reservation(
                    db,
                    hotel_id=hotel_id,
                    mapping=existing,
                    normalized=normalized,
                    payload=payload,
                )
            except OTAError:
                raise
            except Exception as exc:
                OTAIntegrationService._sync_mapping_payload(
                    existing,
                    guest_name=normalized.guest_full_name,
                    payload=payload,
                    sync_status=OTASyncStatusEnum.FAILED,
                    error_message=str(exc),
                )
                db.flush()
                raise OTAError(f"Failed to process {provider_code} reservation update: {exc}")

        mapping = OTAIntegrationService._create_legacy_mapping(
            db,
            hotel_id=hotel_id,
            provider_code=provider_code,
            external_reservation_id=normalized.external_reservation_id,
            guest_name=normalized.guest_full_name,
            payload=payload,
        )
        if OTAIntegrationService._normalize_event_type(normalized.event_type) == "cancelled":
            OTAIntegrationService._sync_mapping_payload(
                mapping,
                guest_name=normalized.guest_full_name,
                payload=payload,
                sync_status=OTASyncStatusEnum.CONFLICT,
                error_message="Cancellation received for unknown OTA reservation",
            )
            OTAIntegrationService._sync_foundation_reservation_link(
                db,
                hotel_id=hotel_id,
                provider_code=normalized.provider_code,
                external_reservation_id=normalized.external_reservation_id,
                external_confirmation_code=normalized.external_confirmation_code,
                reservation=None,
                payload=payload,
                gross_total=normalized.gross_total,
                currency_code=normalized.currency_code,
                sync_status="manual_resolution_required",
                provider_state=OTAReservationLifecycleEnum.CANCELLED,
                error_message=mapping.error_message,
                rate_plan_id=None,
            )
            db.flush()
            return mapping

        try:
            return OTAIntegrationService._materialize_incoming_reservation(
                db,
                hotel_id=hotel_id,
                mapping=mapping,
                normalized=normalized,
                payload=payload,
            )
        except OTAError:
            raise
        except Exception as exc:
            mapping.sync_status = OTASyncStatusEnum.FAILED
            mapping.error_message = str(exc)
            db.flush()
            raise OTAError(f"Failed to process {provider_code} reservation: {exc}")

    @staticmethod
    def upsert_webhook_credential(
        db: Session,
        hotel_id: int,
        provider: str,
        webhook_secret: str,
        external_property_id: Optional[str] = None,
        is_active: bool = True,
    ) -> OTAWebhookCredential:
        credential = (
            db.query(OTAWebhookCredential)
            .filter(
                OTAWebhookCredential.hotel_id == hotel_id,
                OTAWebhookCredential.provider == provider,
            )
            .first()
        )
        secret_hash = OTAIntegrationService._hash_secret(webhook_secret)
        if credential:
            credential.webhook_secret_hash = secret_hash
            credential.external_property_id = (external_property_id or "").strip() or None
            credential.is_active = is_active
        else:
            credential = OTAWebhookCredential(
                hotel_id=hotel_id,
                provider=provider,
                webhook_secret_hash=secret_hash,
                external_property_id=(external_property_id or "").strip() or None,
                is_active=is_active,
            )
            db.add(credential)
        db.flush()
        return credential

    @staticmethod
    def _normalize_collection_model(
        raw_value: str | None,
        *,
        paid_amount: float | None,
        gross_total: float,
    ) -> str:
        normalized = (raw_value or "").strip().lower().replace("-", "_").replace(" ", "_")
        alias_map = {
            "prepaid": "ota_prepaid",
            "ota_prepaid": "ota_prepaid",
            "agency_collect": "ota_prepaid",
            "virtual_card": "ota_virtual_card",
            "ota_virtual_card": "ota_virtual_card",
            "hotel_collect": "hotel_collect",
            "pay_at_property": "hotel_collect",
            "pay_on_arrival": "hotel_collect",
            "partial": "ota_partial",
            "ota_partial": "ota_partial",
        }
        if normalized in alias_map:
            return alias_map[normalized]
        if paid_amount is not None and gross_total > 0 and paid_amount >= gross_total:
            return "ota_prepaid"
        if paid_amount:
            return "ota_partial"
        return "unknown"

    @staticmethod
    def _resolve_paid_amount(
        *,
        normalized: NormalizedOTAReservation,
        collection_model: str,
        gross_total: float,
    ) -> float:
        if normalized.paid_amount is not None:
            return round(max(normalized.paid_amount, 0.0), 2)
        if collection_model in {"ota_prepaid", "ota_virtual_card"} and gross_total > 0:
            return round(gross_total, 2)
        return 0.0

    @staticmethod
    def _normalize_settlement_status(
        raw_value: str | None,
        *,
        collection_model: str,
        amount_paid: float,
        gross_total: float,
    ) -> str:
        normalized = (raw_value or "").strip().lower().replace("-", "_").replace(" ", "_")
        allowed = {"pending", "partial", "settled", "not_applicable", "unknown"}
        if normalized in allowed:
            return normalized
        if collection_model == "hotel_collect":
            return "not_applicable"
        if amount_paid >= gross_total > 0:
            return "pending"
        if amount_paid > 0:
            return "partial"
        return "unknown"

    @staticmethod
    def process_booking_webhook(
        db: Session,
        hotel_id: int,
        webhook_secret: str,
        payload: dict,
    ) -> OTAReservationMapping:
        """
        Process an incoming reservation from Booking.com through the normalized
        adapter bridge.
        """
        return OTAIntegrationService._process_normalized_webhook(
            db,
            hotel_id=hotel_id,
            provider_code="booking",
            webhook_secret=webhook_secret,
            payload=payload,
            external_reservation_id_key="reservation_id",
        )

    @staticmethod
    def process_expedia_webhook(
        db: Session,
        hotel_id: int,
        webhook_secret: str,
        payload: dict,
    ) -> OTAReservationMapping:
        """
        Process an incoming reservation from Expedia through the normalized
        adapter bridge.
        """
        return OTAIntegrationService._process_normalized_webhook(
            db,
            hotel_id=hotel_id,
            provider_code="expedia",
            webhook_secret=webhook_secret,
            payload=payload,
            external_reservation_id_key="booking_id",
        )

    @staticmethod
    def process_despegar_webhook(
        db: Session,
        hotel_id: int,
        webhook_secret: str,
        payload: dict,
    ) -> OTAReservationMapping:
        """
        Process an incoming reservation from Despegar.

        Expected payload structure:
        {
            "reservation_id": "DSP-123",
            "confirmation_code": "DSP-123",
            "guest": {"first_name": "Ana", "last_name": "Perez", "email": "ana@example.com"},
            "stay": {"checkin": "2026-04-10", "checkout": "2026-04-13"},
            "product_code": "STD_DBL",
            "occupancy": {"adults": 2, "children": 0},
            "pricing": {"total": 700.00, "currency": "USD"}
        }
        """
        return OTAIntegrationService._process_normalized_webhook(
            db,
            hotel_id=hotel_id,
            provider_code="despegar",
            webhook_secret=webhook_secret,
            payload=payload,
            external_reservation_id_key="reservation_id",
        )

    @staticmethod
    def build_availability_update(db: Session, category_id: int, start_date: date, end_date: date) -> list[dict]:
        """
        Build an availability update payload for a given category and date range.
        Returns a list of {date, available_rooms} entries for OTA sync.
        """
        from datetime import timedelta

        category = db.query(RoomCategory).filter(RoomCategory.id == category_id).first()
        if not category:
            raise OTAError(f"Unknown room category id: {category_id}")

        rooms = db.query(Room).filter(
            Room.category_id == category_id,
            Room.hotel_id == category.hotel_id,
            Room.is_active == True,
            Room.status.in_([RoomStatusEnum.AVAILABLE, RoomStatusEnum.OCCUPIED]),
        ).all()

        total_rooms = len(rooms)
        availability = []

        current = start_date
        while current < end_date:
            next_day = current + timedelta(days=1)
            booked = 0
            for room in rooms:
                from app.services.reservation_service import check_room_availability
                if not check_room_availability(db, room.id, current, next_day, hotel_id=category.hotel_id):
                    booked += 1

            availability.append({
                "date": current.isoformat(),
                "total_rooms": total_rooms,
                "booked": booked,
                "available": total_rooms - booked,
            })
            current = next_day

        return availability
