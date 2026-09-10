"""Guest-facing reservation confirmation and voucher delivery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import TypeAdapter, ValidationError
from pydantic.networks import EmailStr
from sqlalchemy.orm import Session

from app.models.reservation import Reservation
from app.models.reservation_communication import (
    ReservationEmailDelivery,
    ReservationEmailKindEnum,
    ReservationEmailStatusEnum,
)
from app.services.hotel_outbound_email_service import (
    HotelOutboundEmailError,
    HotelOutboundSendResult,
    send_hotel_email,
)


class ReservationCommunicationError(ValueError):
    """A validation or tenant-scoped reservation communication error."""


@dataclass(frozen=True)
class ReservationEmailSendOutcome:
    delivery: ReservationEmailDelivery
    deduplicated: bool = False


def _clean_email(value: str | None) -> str:
    candidate = str(value or "").strip().lower()
    if not candidate:
        raise ReservationCommunicationError("La reserva no tiene un email de huésped disponible")
    try:
        return str(TypeAdapter(EmailStr).validate_python(candidate))
    except ValidationError as exc:
        raise ReservationCommunicationError("El email del huésped no tiene un formato válido") from exc


def _kind_value(kind: ReservationEmailKindEnum | str) -> ReservationEmailKindEnum:
    try:
        return kind if isinstance(kind, ReservationEmailKindEnum) else ReservationEmailKindEnum(str(kind))
    except ValueError as exc:
        raise ReservationCommunicationError("Tipo de comunicación no reconocido") from exc


def _money(value: object, currency: str) -> str:
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"))
    return f"{amount:.2f} {currency}"


def build_reservation_email(
    reservation: Reservation,
    *,
    kind: ReservationEmailKindEnum,
    hotel_name: str | None = None,
) -> tuple[str, str]:
    guest = reservation.guest
    room = reservation.room
    category = reservation.category
    guest_name = f"{guest.first_name} {guest.last_name}".strip() if guest else "huésped"
    property_name = hotel_name or "el hotel"
    room_label = f"habitación {room.room_number}" if room and room.hotel_id == reservation.hotel_id else (
        f"categoría {category.name}" if category and category.hotel_id == reservation.hotel_id else "habitación pendiente de asignar"
    )
    subject_prefix = "Confirmación de reserva" if kind == ReservationEmailKindEnum.CONFIRMATION else "Comprobante de reserva"
    subject = f"{subject_prefix} {reservation.confirmation_code}"
    total = _money(reservation.total_amount, str(reservation.currency_code or "ARS").upper())
    paid = _money(reservation.amount_paid, str(reservation.currency_code or "ARS").upper())
    balance = _money(
        max(Decimal("0"), Decimal(str(reservation.total_amount or 0)) - Decimal(str(reservation.amount_paid or 0))),
        str(reservation.currency_code or "ARS").upper(),
    )
    body = (
        f"Hola {guest_name},\n\n"
        f"{property_name} confirma tu reserva {reservation.confirmation_code}.\n\n"
        f"Ingreso: {reservation.check_in_date.isoformat()}\n"
        f"Salida: {reservation.check_out_date.isoformat()}\n"
        f"Alojamiento: {room_label}\n"
        f"Estado: {getattr(reservation.status, 'value', reservation.status)}\n\n"
        f"Total: {total}\n"
        f"Cobrado: {paid}\n"
        f"Saldo pendiente: {balance}\n\n"
        "Si necesitás corregir algún dato, respondé este correo o contactá a la recepción.\n"
    )
    return subject, body


def list_reservation_email_deliveries(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
) -> list[ReservationEmailDelivery]:
    return (
        db.query(ReservationEmailDelivery)
        .filter(
            ReservationEmailDelivery.hotel_id == hotel_id,
            ReservationEmailDelivery.reservation_id == reservation_id,
        )
        .order_by(ReservationEmailDelivery.created_at.desc(), ReservationEmailDelivery.id.desc())
        .all()
    )


def send_reservation_email(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    kind: ReservationEmailKindEnum | str,
    requested_by_user_id: int | None,
    recipient_email: str | None = None,
    resend: bool = False,
    sender=send_hotel_email,
) -> ReservationEmailSendOutcome:
    email_kind = _kind_value(kind)
    # Serialize sends for this reservation on PostgreSQL. The reservation row
    # exists before a delivery attempt, so locking it closes the race where
    # two browser clicks both observe an empty delivery history and contact
    # the provider twice. SQLite ignores FOR UPDATE but still benefits from
    # the guarded mutation in the UI and the same deduplication query.
    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
        .with_for_update()
        .one_or_none()
    )
    if reservation is None:
        raise ReservationCommunicationError("Reserva no encontrada")
    guest_email = _clean_email(recipient_email or getattr(reservation.guest, "email", None))
    subject, body = build_reservation_email(
        reservation,
        kind=email_kind,
        hotel_name=getattr(getattr(reservation, "hotel", None), "hotel_name", None),
    )

    # A pending, accepted, or unknown delivery is never retried implicitly.
    # Unknown means the provider result was ambiguous; only an explicit resend
    # may create another attempt.
    if not resend:
        existing = (
            db.query(ReservationEmailDelivery)
            .filter(
                ReservationEmailDelivery.hotel_id == hotel_id,
                ReservationEmailDelivery.reservation_id == reservation_id,
                ReservationEmailDelivery.kind == email_kind,
                ReservationEmailDelivery.status.in_(
                    [
                        ReservationEmailStatusEnum.PENDING,
                        ReservationEmailStatusEnum.ACCEPTED,
                        ReservationEmailStatusEnum.UNKNOWN,
                    ]
                ),
            )
            .order_by(ReservationEmailDelivery.created_at.desc(), ReservationEmailDelivery.id.desc())
            .first()
        )
        if existing is not None:
            return ReservationEmailSendOutcome(existing, deduplicated=True)

    delivery = ReservationEmailDelivery(
        hotel_id=hotel_id,
        reservation_id=reservation_id,
        kind=email_kind,
        status=ReservationEmailStatusEnum.PENDING,
        recipient_email=guest_email,
        subject=subject,
        is_resend=bool(resend),
        requested_by_user_id=requested_by_user_id,
        attempt_count=1,
    )
    db.add(delivery)
    db.flush()

    try:
        result: HotelOutboundSendResult = sender(
            db,
            hotel_id,
            to=guest_email,
            subject=subject,
            body=body,
        )
    except HotelOutboundEmailError as exc:
        delivery.status = ReservationEmailStatusEnum.FAILED
        delivery.last_error = str(exc)[:300]
        db.flush()
        return ReservationEmailSendOutcome(delivery)
    except Exception:
        # A timeout or transport exception can mean the provider accepted the
        # message before the client lost the response. Never claim failure and
        # silently retry it; keep it visible for an explicit operator decision.
        delivery.status = ReservationEmailStatusEnum.UNKNOWN
        delivery.last_error = "No se pudo confirmar la respuesta del proveedor"
        db.flush()
        return ReservationEmailSendOutcome(delivery)

    delivery.status = ReservationEmailStatusEnum.ACCEPTED
    delivery.provider_message_id = result.provider_message_id
    delivery.accepted_at = datetime.now(timezone.utc)
    delivery.last_error = None
    db.flush()
    return ReservationEmailSendOutcome(delivery)
