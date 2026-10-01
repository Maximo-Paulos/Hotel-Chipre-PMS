"""
FastAPI routes for Booking management (thin layer over Reservation).
Provides basic CRUD plus a simple availability placeholder.
"""
import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.services.row_locks import lock_query
from app.config import is_demo_environment_allowed, is_demo_mode
from app.database import get_db
from app.models.hotel_config import HotelConfiguration
from app.services.timezones import hotel_today
from app.dependencies.auth import AuthContext, authorize_permission, get_auth_context, require_permission
from app.api.manual_rate_access import authorize_manual_rate_scope
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.audit_log import AuditActionEnum
from app.models.transaction import Transaction, TransactionStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.guest import Guest
from app.schemas.booking import BookingCreate, BookingRead, BookingUpdate
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.services.reservation_service import (
    ManualRatePolicyError,
    ReservationError,
    ReservationVersionConflict,
    check_room_availability,
    create_reservation,
    find_available_rooms,
    transition_reservation_status,
    update_reservation_fields,
    validate_reservation_category_compatibility,
    _validate_reservation_occupancy,
)
from app.services.reservation_quote_service import build_reservation_quote
from app.services.checkin_service import perform_checkin, perform_checkout, CheckInError
from app.services.guest_restriction_service import (
    GuestProhibitedError,
    RestrictionOverridePermissionError,
    get_active_guest_restrictions,
)
from app.services.graph_projection import project_company_link, project_reservation_assignment
from app.services import audit_log_service
from app.services.permission_service import (
    PERMISSION_RESERVATION_CANCEL,
    PERMISSION_RESERVATION_CANCEL_PAID,
    PERMISSION_RESERVATION_CREATE,
    PERMISSION_RESERVATION_MANUAL_RATE_LIMITED,
    PERMISSION_RESERVATION_DELETE,
    PERMISSION_RESERVATION_DEMO_SEED,
    PERMISSION_RESERVATION_READ,
    PERMISSION_RESERVATION_UPDATE,
    RESERVATION_MOVE_TIER_PERMISSIONS,
    PERMISSION_CHECKIN_PERFORM,
    PERMISSION_CHECKOUT_PERFORM,
    audit_permission_denied,
    resolve,
)
from app.services.temporary_action_grant_service import (
    TemporaryGrantActor,
    TemporaryGrantError,
    consume_grant_for_action,
)
from app.services.reservation_operations_service import (
    ReservationOperationsError,
    RoomMovePermissionError,
    enforce_room_move_permission,
    required_room_move_permission,
    reservation_has_payment_or_deposit,
)
from app.services.financial_ledger import has_payment_history_for_cancellation

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])
logger = logging.getLogger(__name__)


def _require_demo_mode():
    if not is_demo_environment_allowed():
        raise HTTPException(status_code=404)
    if not is_demo_mode():
        raise HTTPException(
            status_code=403,
            detail="Demo mode is disabled. Set DEMO_MODE=true to use this endpoint.",
        )


def _ensure_subscription_active(db: Session, hotel_id: int, action: str) -> None:
    config = db.get(HotelConfiguration, hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Suscripción inactiva. Reactivá el plan para {action} reservas.",
        )


def _ensure_permission_tier(
    db: Session,
    context: AuthContext,
    required_permission: str,
) -> None:
    required_index = RESERVATION_MOVE_TIER_PERMISSIONS.index(required_permission)
    if any(
        resolve(db, context.hotel_id, context.user_role, permission, user_id=context.user_id)
        for permission in RESERVATION_MOVE_TIER_PERMISSIONS[required_index:]
    ):
        return
    audit_permission_denied(
        db,
        hotel_id=context.hotel_id,
        user_id=context.user_id,
        role=context.user_role,
        permission_code=required_permission,
    )
    raise HTTPException(
        status_code=403,
        detail="No tenes permisos para cambiar la categoría de la reserva",
    )


def _is_manager_context(context: AuthContext) -> bool:
    return context.operational_role in {"owner", "co_owner", "manager"}


def _booking_to_read(res: Reservation) -> BookingRead:
    """Ensure computed fields land in the response."""
    result = BookingRead.model_validate(res)
    result.balance_due = float(res.balance_due)
    result.nights = res.nights
    result.additional_guests = [
        {
            "id": g.id,
            "first_name": g.first_name,
            "last_name": g.last_name,
            "document_type": g.document_type,
            "document_number": g.document_number,
        }
        for g in res.additional_guests
    ]
    return result


def _project_booking_graph(hotel_id: int, booking: Reservation) -> None:
    project_reservation_assignment(
        hotel_id,
        booking.id,
        booking.room_id,
        booking.guest_id,
        booking.status,
    )
    if booking.company_id is not None:
        project_company_link(hotel_id, booking.company_id, booking.id)


@router.get("/availability")
def availability(
    category_id: int | None = None,
    check_in_date: date | None = None,
    check_out_date: date | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    """
    Lightweight availability placeholder. When all parameters are provided,
    it returns real available room ids; otherwise it returns a helpful message.
    """
    if not (category_id and check_in_date and check_out_date):
        return {
            "status": "placeholder",
            "available_rooms": [],
            "message": "Provide category_id, check_in_date, and check_out_date to check availability.",
        }
    available = find_available_rooms(
        db,
        category_id,
        check_in_date,
        check_out_date,
        hotel_id=context.hotel_id,
    )
    return {
        "status": "ok",
        "available_rooms": [room.id for room in available],
        "count": len(available),
    }


@router.get("/price-quote")
def price_quote(
    category_id: int,
    check_in_date: date,
    check_out_date: date,
    guest_id: int | None = None,
    company_id: int | None = None,
    sellable_product_id: int | None = None,
    rate_plan_id: int | None = None,
    tax_policy_id: int | None = None,
    pricing_channel_code: str | None = None,
    pricing_payment_method: str | None = None,
    guest_scope: str = "all",
    target_currency: str | None = None,
    occupancy: int = Query(1, gt=0),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CREATE)),
):
    """
    Calculate pricing for a potential booking without persisting it.
    Uses the canonical daily/seasonal rate resolver and then the category base price.

    For deferred-billing companies, the quote retains date/category and token
    fields required for reservation creation, marks ``company_billing_deferred``
    true, and returns no monetary values (null amounts and empty price details).
    """
    if guest_id is not None:
        active = get_active_guest_restrictions(db, hotel_id=context.hotel_id, guest_id=guest_id)
        if active:
            error = GuestProhibitedError(active[0].id)
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "message": str(error), "restriction_id": error.restriction_id},
            )
    try:
        quote = build_reservation_quote(
            db,
            hotel_id=context.hotel_id,
            category_id=category_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            sellable_product_id=sellable_product_id,
            rate_plan_id=rate_plan_id,
            tax_policy_id=tax_policy_id,
            pricing_channel_code=pricing_channel_code,
            pricing_payment_method=pricing_payment_method,
            guest_scope=guest_scope,
            target_currency=target_currency,
            occupancy=occupancy,
            guest_id=guest_id,
            company_id=company_id,
        )
        if resolve(
            db,
            context.hotel_id,
            context.user_role,
            PERMISSION_RESERVATION_MANUAL_RATE_LIMITED,
            user_id=context.user_id,
        ):
            config = db.get(HotelConfiguration, context.hotel_id)
            quote["manual_rate_min_adjustment_pct"] = (
                str(config.manual_rate_min_adjustment_pct)
                if config and config.manual_rate_min_adjustment_pct is not None
                else None
            )
            quote["manual_rate_max_adjustment_pct"] = (
                str(config.manual_rate_max_adjustment_pct)
                if config and config.manual_rate_max_adjustment_pct is not None
                else None
            )
        return quote
    except (ReservationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[BookingRead])
def list_bookings(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    bookings = (
        db.query(Reservation)
        .filter(Reservation.hotel_id == context.hotel_id, Reservation.deleted_at.is_(None))
        .order_by(Reservation.check_in_date)
        .all()
    )
    return [_booking_to_read(r) for r in bookings]


@router.post("/", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CREATE)),
):
    _ensure_subscription_active(db, context.hotel_id, "crear nuevas")
    # Reuse the existing ReservationCreate schema to drive business logic
    reservation_payload = ReservationCreate(**payload.model_dump())
    manual_rate_scope = None
    if reservation_payload.total_amount is not None:
        manual_rate_scope = authorize_manual_rate_scope(db, context)
        if not reservation_payload.manual_rate_reason:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Indicá el motivo de la tarifa manual.",
            )
    elif reservation_payload.manual_rate_reason is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El motivo solo corresponde cuando se ingresa una tarifa manual.",
        )
    if not reservation_payload.quote_token and reservation_payload.total_amount is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere una cotización vigente para crear la reserva.",
        )
    try:
        booking = create_reservation(
            db,
            reservation_payload,
            hotel_id=context.hotel_id,
            actor_user_id=context.user_id,
            actor_role=context.user_role,
            manual_rate_scope=manual_rate_scope,
        )
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="reservations",
            record_id=booking.id,
            action=AuditActionEnum.CREATE,
            actor_user_id=context.user_id,
            payload_after={
                **(audit_log_service.model_snapshot(booking) or {}),
                "source": "legacy_bookings",
            },
        )
        db.commit()
        db.refresh(booking)
        _project_booking_graph(context.hotel_id, booking)
        return _booking_to_read(booking)
    except ManualRatePolicyError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{booking_id}", response_model=BookingRead)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    booking = (
        db.query(Reservation)
        .filter(
            Reservation.id == booking_id,
            Reservation.hotel_id == context.hotel_id,
            Reservation.deleted_at.is_(None),
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return _booking_to_read(booking)


@router.post("/{booking_id}/cancel", response_model=BookingRead)
def cancel_booking(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
    temporary_grant_token: str | None = Header(default=None, alias="X-Temporary-Action-Grant"),
):
    if not context.is_verified:
        raise HTTPException(status_code=403, detail="Verifica tu email para usar el sistema")
    if context.user_id is None:
        raise HTTPException(status_code=401, detail="Autenticacion requerida")

    permission_allowed = resolve(
        db,
        context.hotel_id,
        context.user_role,
        PERMISSION_RESERVATION_CANCEL,
        user_id=context.user_id,
    )
    if not permission_allowed:
        audit_permission_denied(
            db,
            hotel_id=context.hotel_id,
            user_id=context.user_id,
            role=context.user_role,
            permission_code=PERMISSION_RESERVATION_CANCEL,
        )
        if not temporary_grant_token:
            raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")

    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        if not permission_allowed:
            raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para gestionar reservas.",
        )

    booking_query = (
        db.query(Reservation)
        .filter(
            Reservation.id == booking_id,
            Reservation.hotel_id == context.hotel_id,
            Reservation.deleted_at.is_(None),
        )
        .populate_existing()
    )
    booking = lock_query(booking_query, Reservation).first()
    if not booking:
        if not permission_allowed:
            raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT):
        if not permission_allowed:
            raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")
        raise HTTPException(status_code=400, detail="Cannot cancel a booking that is already checked-in or checked-out")
    if booking.status == ReservationStatusEnum.CANCELLED:
        if not permission_allowed:
            raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")
        raise HTTPException(status_code=400, detail="Booking is already cancelled")

    requires_paid_cancel_approval = has_payment_history_for_cancellation(db, context.hotel_id, booking)
    if requires_paid_cancel_approval:
        authorize_permission(request, db, context, PERMISSION_RESERVATION_CANCEL_PAID)
        # Consuming the one-use step-up ticket commits its own transaction,
        # releasing the reservation row lock. Reacquire and revalidate before
        # applying the cancellation so a concurrent state change cannot slip
        # through the MFA round-trip.
        booking_query = (
            db.query(Reservation)
            .filter(
                Reservation.id == booking_id,
                Reservation.hotel_id == context.hotel_id,
                Reservation.deleted_at.is_(None),
            )
            .populate_existing()
        )
        booking = lock_query(booking_query, Reservation).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        if booking.status in (
            ReservationStatusEnum.CHECKED_IN,
            ReservationStatusEnum.CHECKED_OUT,
            ReservationStatusEnum.CANCELLED,
        ):
            raise HTTPException(status_code=409, detail="Booking changed while approval was being verified")

    grant_consumed = False
    if not permission_allowed and temporary_grant_token:
        try:
            grant_consumed = consume_grant_for_action(
                db,
                temporary_grant_token,
                TemporaryGrantActor(user_id=context.user_id, hotel_id=context.hotel_id),
                permission_code=PERMISSION_RESERVATION_CANCEL,
                resource_type="reservation",
                resource_id=booking.id,
            )
        except TemporaryGrantError:
            db.rollback()
            raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")
        except Exception:
            db.rollback()
            raise
    if not permission_allowed and not grant_consumed:
        # A failed action consume can flush expiry changes; persist them while
        # keeping the protected reservation mutation untouched.
        db.commit()
        raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")

    try:
        # Grant consumption and the protected state transition share this
        # session transaction; a failed mutation rolls both back together.
        transition_reservation_status(
            db,
            booking,
            ReservationStatusEnum.CANCELLED,
            context.hotel_id,
            reason_code="cancelled_by_user",
            changed_by_user_id=context.user_id,
        )
        try:
            from app.services.payment_link_service import cancel_active_links_for_reservation

            cancel_active_links_for_reservation(
                db, context.hotel_id, booking.id, reason="reservation cancelled"
            )
        except Exception as exc:  # best-effort; never block the cancellation
            logger.error(
                "Failed cancelling payment links for reservation %s error_type=%s",
                booking.id,
                type(exc).__name__,
            )
        db.commit()
        db.refresh(booking)
        return _booking_to_read(booking)
    except ReservationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise


@router.post("/{booking_id}/checkin", response_model=BookingRead)
def checkin_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CHECKIN_PERFORM)),
):
    try:
        booking = perform_checkin(db, booking_id, hotel_id=context.hotel_id)
        db.commit()
        db.refresh(booking)
        return _booking_to_read(booking)
    except CheckInError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{booking_id}/checkout", response_model=BookingRead)
def checkout_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CHECKOUT_PERFORM)),
):
    try:
        booking = perform_checkout(db, booking_id, hotel_id=context.hotel_id)
        db.commit()
        db.refresh(booking)
        return _booking_to_read(booking)
    except CheckInError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{booking_id}", response_model=BookingRead)
def update_booking(
    booking_id: int,
    payload: BookingUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_UPDATE)),
):
    _ensure_subscription_active(db, context.hotel_id, "gestionar")
    if payload.status is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede cambiar el estado desde esta ruta. Usá la acción específica de la reserva.",
        )

    booking_query = (
        db.query(Reservation)
        .filter(
            Reservation.id == booking_id,
            Reservation.hotel_id == context.hotel_id,
            Reservation.deleted_at.is_(None),
        )
        .populate_existing()
    )
    booking = lock_query(booking_query, Reservation).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    data = payload.model_dump(exclude_unset=True)
    effective_data = {
        field: value
        for field, value in data.items()
        if field not in {"client_version", "status"}
        and not (field == "room_id" and value is None)
        and getattr(booking, field, None) != value
    }
    metadata_fields = {"arrival_time_hint", "reservation_comment"}
    terminal_mutation_fields = set(effective_data) - metadata_fields
    if booking.status in {
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW,
    } and terminal_mutation_fields:
        raise HTTPException(status_code=400, detail=("Cannot modify: reservation is " + booking.status.value))

    if payload.client_version is not None and booking.version != payload.client_version:
        raise HTTPException(status_code=409, detail="Reservation was modified concurrently. Reload and retry.")
    if not effective_data:
        return _booking_to_read(booking)
    if payload.client_version is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="client_version es obligatorio para modificar una reserva. Recargá e intentá nuevamente.",
        )

    before = audit_log_service.model_snapshot(booking)
    data = effective_data
    dates_changed = (
        ("check_in_date" in data and data["check_in_date"] != booking.check_in_date)
        or ("check_out_date" in data and data["check_out_date"] != booking.check_out_date)
    )
    occupancy_changed = (
        ("num_adults" in data and data["num_adults"] != booking.num_adults)
        or ("num_children" in data and data["num_children"] != booking.num_children)
    )
    if (
        (dates_changed or occupancy_changed)
        and reservation_has_payment_or_deposit(db, hotel_id=context.hotel_id, reservation=booking)
        and not _is_manager_context(context)
    ):
        raise HTTPException(
            status_code=403,
            detail="Modificar fechas u ocupación de una reserva con pagos requiere gerente, dueño o codueño.",
        )

    # Route legacy metadata-only edits through the canonical service so version
    # checks, reservation.updated events and field normalization stay aligned
    # with the primary reservations endpoint.
    if set(data) <= metadata_fields:
        try:
            update_reservation_fields(
                db,
                booking,
                ReservationUpdate(**{**data, "client_version": payload.client_version}),
                context.hotel_id,
                changed_by_user_id=context.user_id,
                actor_role=context.user_role,
                client_version=payload.client_version,
                preserve_unclassified_price=True,
            )
        except ReservationVersionConflict as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ReservationError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="reservations",
            record_id=booking.id,
            action=AuditActionEnum.UPDATE,
            actor_user_id=context.user_id,
            payload_before=before,
            payload_after={
                **(audit_log_service.model_snapshot(booking) or {}),
                "source": "legacy_bookings",
            },
        )
        db.commit()
        db.refresh(booking)
        return _booking_to_read(booking)

    new_category_id = data.get("category_id", booking.category_id)
    new_ci = data.get("check_in_date", booking.check_in_date)
    new_co = data.get("check_out_date", booking.check_out_date)
    category_changed = new_category_id != booking.category_id

    # Validate category existence
    category = db.query(RoomCategory).filter(RoomCategory.id == new_category_id, RoomCategory.hotel_id == context.hotel_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Category not found")
    if category_changed:
        current_category = (
            db.query(RoomCategory)
            .filter(
                RoomCategory.id == booking.category_id,
                RoomCategory.hotel_id == context.hotel_id,
            )
            .first()
        )
        if current_category is None:
            raise HTTPException(status_code=400, detail="Current category not found")
        _ensure_permission_tier(
            db,
            context,
            required_room_move_permission(current_category, category),
        )
        try:
            validate_reservation_category_compatibility(
                db,
                reservation=booking,
                category=category,
                hotel_id=context.hotel_id,
            )
        except ReservationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Validate dates
    if new_co <= new_ci:
        raise HTTPException(status_code=400, detail="check_out_date must be after check_in_date")

    # Validate existing room still matches category
    if booking.room_id is not None and booking.category_id != new_category_id:
        room = (
            db.query(Room)
            .filter(Room.id == booking.room_id, Room.hotel_id == context.hotel_id)
            .first()
        )
        if room and room.category_id != new_category_id:
            raise HTTPException(status_code=400, detail="Existing room does not belong to the new category; change room first")

    room_id_changed = (
        "room_id" in data
        and data["room_id"] is not None
        and data["room_id"] != booking.room_id
    )
    if room_id_changed:
        room = (
            db.query(Room)
            .filter(
                Room.id == data["room_id"],
                Room.hotel_id == context.hotel_id,
                Room.deleted_at.is_(None),
            )
            .first()
        )
        if not room:
            raise HTTPException(status_code=400, detail="Room not found")
        if room.category_id != new_category_id:
            raise HTTPException(status_code=400, detail="Room does not belong to the booking category")
        try:
            enforce_room_move_permission(
                db,
                reservation=booking,
                destination_room=room,
                hotel_id=context.hotel_id,
                actor_role=context.user_role,
                actor_user_id=context.user_id,
            )
        except RoomMovePermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ReservationOperationsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    new_num_adults = data.get("num_adults", booking.num_adults)
    new_num_children = data.get("num_children", booking.num_children)
    if category_changed or occupancy_changed:
        try:
            _validate_reservation_occupancy(category, new_num_adults, new_num_children)
        except ReservationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Use the canonical update service for all mutable booking fields. This
    # preserves the reservation's commercial context and applies occupancy,
    # availability, audit-event, and pricing rules consistently.
    service_data = {
        field: value
        for field, value in data.items()
        if field in ReservationUpdate.model_fields
    }
    if service_data.get("check_in_date") == booking.check_in_date:
        service_data.pop("check_in_date")
    if service_data.get("check_out_date") == booking.check_out_date:
        service_data.pop("check_out_date")
    if "room_id" in service_data and service_data["room_id"] == booking.room_id:
        service_data.pop("room_id")
    if category_changed:
        booking.category_id = new_category_id
    if (category_changed or occupancy_changed) and not {
        "check_in_date",
        "check_out_date",
    }.intersection(service_data):
        # The canonical service recalculates category/occupancy-sensitive
        # prices when dates are included; same dates are deliberate here.
        service_data["check_in_date"] = booking.check_in_date

    try:
        update_reservation_fields(
            db,
            booking,
            ReservationUpdate(**service_data),
            context.hotel_id,
            changed_by_user_id=context.user_id,
            actor_role=context.user_role,
            room_move_reason_code="legacy_bookings",
            room_move_notes="Actualización desde la ruta legacy de reservas",
            client_version=payload.client_version,
            preserve_unclassified_price=True,
        )
    except GuestProhibitedError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc), "restriction_id": exc.restriction_id},
        ) from exc
    except RestrictionOverridePermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail="No tenés permisos para esta acción") from exc
    except ReservationVersionConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ReservationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="reservations",
        record_id=booking.id,
        action=AuditActionEnum.UPDATE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after={
            **(audit_log_service.model_snapshot(booking) or {}),
            "source": "legacy_bookings",
        },
    )
    db.commit()
    db.refresh(booking)
    return _booking_to_read(booking)


@router.post("/demo-seed")
def seed_demo_bookings(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_DEMO_SEED)),
):
    """Quickly seed demo bookings (requires DEMO_MODE=true)."""
    _require_demo_mode()
    today = hotel_today(db, context.hotel_id)

    category = db.query(RoomCategory).filter(RoomCategory.hotel_id == context.hotel_id).first()
    if not category:
        category = RoomCategory(
            hotel_id=context.hotel_id,
            name="Demo Category",
            code="DEMO",
            base_price_per_night=100.0,
            max_occupancy=2,
        )
        db.add(category)
        db.flush()

    rooms = (
        db.query(Room)
        .filter(
            Room.category_id == category.id,
            Room.hotel_id == context.hotel_id,
            Room.deleted_at.is_(None),
        )
        .all()
    )
    if not rooms:
        rooms = [
            Room(hotel_id=context.hotel_id, room_number="D1", floor=1, category_id=category.id, status=RoomStatusEnum.AVAILABLE),
            Room(hotel_id=context.hotel_id, room_number="D2", floor=1, category_id=category.id, status=RoomStatusEnum.AVAILABLE),
        ]
        db.add_all(rooms)
        db.flush()

    guest = db.query(Guest).filter(Guest.hotel_id == context.hotel_id).first()
    if not guest:
        guest = Guest(first_name="Demo", last_name="Guest", email="demo@example.com", hotel_id=context.hotel_id)
        db.add(guest)
        db.flush()

    created_ids: list[int] = []
    for idx, room in enumerate(rooms[:2]):
        ci = today + timedelta(days=idx * 3)
        co = ci + timedelta(days=2)
        payload = ReservationCreate(
            guest_id=guest.id,
            category_id=category.id,
            room_id=room.id,
            check_in_date=ci,
            check_out_date=co,
            num_adults=2,
        )
        try:
            res = create_reservation(db, payload, hotel_id=context.hotel_id)
            created_ids.append(res.id)
        except ReservationError:
            continue

    db.commit()
    return {"status": "ok", "created": len(created_ids), "booking_ids": created_ids}


@router.delete("/{booking_id}")
def delete_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_DELETE)),
):
    _ensure_subscription_active(db, context.hotel_id, "gestionar")
    booking_query = (
        db.query(Reservation)
        .filter(
            Reservation.id == booking_id,
            Reservation.hotel_id == context.hotel_id,
            Reservation.deleted_at.is_(None),
        )
        .populate_existing()
    )
    booking = lock_query(booking_query, Reservation).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    # Avoid deleting checked-in/checked-out bookings to preserve history
    if booking.status in {ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT}:
        raise HTTPException(status_code=400, detail="Cannot delete an active/finished booking")
    if reservation_has_payment_or_deposit(db, hotel_id=context.hotel_id, reservation=booking):
        raise HTTPException(
            status_code=409,
            detail="A booking with payment history cannot be deleted; use the cancellation workflow instead",
        )
    before = audit_log_service.model_snapshot(booking)
    booking.deleted_at = datetime.now(timezone.utc)
    booking.deleted_by_user_id = context.user_id
    db.commit()
    db.refresh(booking)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="reservations",
        record_id=booking.id,
        action=AuditActionEnum.DELETE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(booking),
    )
    return {"deleted": True, "id": booking_id}
