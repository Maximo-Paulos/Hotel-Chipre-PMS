"""
FastAPI routes for Reservations.
Complete CRUD + cancel, modify, no-show, extend stay.
"""
import logging
from datetime import date
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit_log import AuditActionEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory
from app.models.hotel_config import HotelConfiguration
from app.schemas.reservation import (
    ReservationCreate,
    ReservationDateChangeRequest,
    ReservationDateChangeResponse,
    ReservationExtensionRequest,
    ReservationExtensionResponse,
    ReservationNoShowRequest,
    ReservationRead,
    ReservationUpdate,
)
from app.schemas.ota_manual import ManualOTAReservationCreate
from app.schemas.reservation_operations import (
    AllocationRunRequest,
    AllocationRunResponse,
    OTARebookPreviewResponse,
    OTARebookToDirectRequest,
    OTARebookToDirectResponse,
    ReservationActionResolveRequest,
    ReservationExternalResolutionResponse,
    OccupancyGridResponse,
    ReservationBillingAdjustmentSummaryRead,
    ReservationChargeCreate,
    ReservationManualReviewResponse,
    ReservationOperationsSummaryRead,
    ReservationPendingActionRead,
    RoomMoveRequest,
    RoomMoveResponse,
)
from app.services.reservation_service import (
    create_reservation,
    transition_reservation_status,
    find_available_rooms,
    ReservationError,
    list_reservations as list_reservations_service,
    get_occupancy_grid,
    get_reservation_by_id,
    mark_reservation_no_show,
    update_reservation_fields,
    register_company_settlement,
)
from app.services.guest_restriction_service import GuestProhibitedError, RestrictionOverridePermissionError
from app.services.reservation_operations_service import (
    ReservationOperationsError,
    change_reservation_dates,
    extend_reservation_stay,
    add_reservation_charge,
    move_reservation_room,
    preview_ota_rebook_as_direct,
    rebook_ota_reservation_as_direct,
)
from app.services.reservation_action_service import (
    ReservationActionError,
    clear_reservation_manual_review,
    get_reservation_operations_summary,
    list_pending_reservation_actions,
    resolve_external_channel_follow_up,
)
from app.services.ota_manual_service import (
    OTAManualReservationError,
    create_or_update_manual_ota_reservation,
    release_no_guarantee,
)
from app.services.payment_service import PaymentError
from app.services.allocation_runtime_service import run_persisted_allocation
from app.dependencies.auth import AuthContext, require_all_permissions, require_permission
from app.services.permission_service import (
    PERMISSION_COMPANY_MANAGE,
    PERMISSION_GUEST_CREATE,
    PERMISSION_RESERVATION_CANCEL,
    PERMISSION_RESERVATION_CHARGE,
    PERMISSION_RESERVATION_CREATE,
    PERMISSION_RESERVATION_MANUAL_RATE,
    PERMISSION_RESERVATION_MOVE,
    PERMISSION_RESERVATION_READ,
    PERMISSION_RESERVATION_UPDATE,
    PERMISSION_ROOM_READ,
    audit_permission_denied,
    resolve,
)
from app.services import audit_log_service
from app.services.graph_projection import (
    project_company_link,
    project_reservation_assignment,
    project_room_movement,
)

router = APIRouter(prefix="/api/reservations", tags=["Reservations"])
logger = logging.getLogger(__name__)


def _to_read(r: Reservation) -> ReservationRead:
    result = ReservationRead.model_validate(r)
    result.balance_due = r.balance_due
    result.nights = r.nights
    result.additional_guests = [
        {"id": g.id, "first_name": g.first_name, "last_name": g.last_name, "document_type": g.document_type, "document_number": g.document_number}
        for g in r.additional_guests
    ]
    return result


def _is_manager_context(context: AuthContext) -> bool:
    return context.user_role in {"owner", "co_owner", "manager"}


def _ensure_manual_rate_permission(db: Session, context: AuthContext) -> None:
    """A manual total_amount replaces the auto-quote from Tarifas entirely --
    only a role holding reservation:manual_rate (owner/co_owner by default)
    may use it. Rejects instead of silently ignoring the client-supplied
    override, so a direct API call can't bypass the UI gate."""
    if resolve(
        db,
        context.hotel_id,
        context.user_role,
        PERMISSION_RESERVATION_MANUAL_RATE,
        user_id=context.user_id,
    ):
        return
    audit_permission_denied(
        db,
        hotel_id=context.hotel_id,
        user_id=context.user_id,
        role=context.user_role,
        permission_code=PERMISSION_RESERVATION_MANUAL_RATE,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tenes permisos para fijar una tarifa manual en la reserva.",
    )


def _ensure_action_permission(
    db: Session,
    context: AuthContext,
    permission_code: str,
    *,
    detail: str = "No tenes permisos para esta accion",
) -> None:
    """Enforce payload-dependent actions before loading or mutating data."""
    if resolve(
        db,
        context.hotel_id,
        context.user_role,
        permission_code,
        user_id=context.user_id,
    ):
        return
    audit_permission_denied(
        db,
        hotel_id=context.hotel_id,
        user_id=context.user_id,
        role=context.user_role,
        permission_code=permission_code,
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _trigger_reoptimization_bg(hotel_id: int, trigger_type: str = "new_reservation") -> None:
    """
    §5.2 — Run allocation engine in background after reservation changes.
    Creates its own DB session; all errors are suppressed to never affect the booking flow.
    """
    from app.database import get_session_factory
    from app.services.allocation_runtime_service import run_persisted_allocation
    from app.services.tenant_context import set_tenant_hotel_context

    db = None
    try:
        SessionFactory = get_session_factory()
        db = SessionFactory()
        set_tenant_hotel_context(db, hotel_id)
        run_persisted_allocation(db, hotel_id=hotel_id, trigger_type=trigger_type)
        db.commit()
    except Exception as exc:
        logger.error(
            "Background reservation reoptimization failed for hotel_id=%s trigger_type=%s",
            hotel_id,
            trigger_type,
            extra={"error_type": type(exc).__name__},
        )
        if db is not None:
            db.rollback()
    finally:
        if db is not None:
            db.close()


def _project_reservation_graph(hotel_id: int, reservation: Reservation) -> None:
    project_reservation_assignment(
        hotel_id,
        reservation.id,
        reservation.room_id,
        reservation.guest_id,
        reservation.status,
    )
    if reservation.company_id is not None:
        project_company_link(hotel_id, reservation.company_id, reservation.id)


# Accept with and without trailing slash to avoid 405 when the FE omits it.
@router.post("/", response_model=ReservationRead, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=ReservationRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_new_reservation(
    data: ReservationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CREATE)),
):
    if data.total_amount is not None:
        _ensure_manual_rate_permission(db, context)
    # A manual total_amount (B4: tarifa manual en reserva directa) is an
    # explicit operator override -- it deliberately does not match whatever
    # the auto-quote for this category/dates would be, so a quote_token
    # would always fail its own consistency check in
    # _validate_quote_token_for_reservation. Only the normal auto-priced path
    # is required to prove it went through a live quote.
    if not data.quote_token and data.total_amount is None:
        raise HTTPException(
            status_code=400,
            detail="Se requiere una cotización vigente para crear la reserva.",
        )
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para crear nuevas reservas.",
        )
    try:
        reservation = create_reservation(
            db, data, hotel_id=context.hotel_id,
            actor_user_id=context.user_id, actor_role=context.user_role,
        )
        db.commit()
        db.refresh(reservation)
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="reservations",
            record_id=reservation.id,
            action=AuditActionEnum.CREATE,
            actor_user_id=context.user_id,
            payload_after=audit_log_service.model_snapshot(reservation),
        )
        _project_reservation_graph(context.hotel_id, reservation)
        background_tasks.add_task(_trigger_reoptimization_bg, hotel_id=context.hotel_id)
        return _to_read(reservation)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GuestProhibitedError as e:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": e.code, "message": str(e), "restriction_id": e.restriction_id},
        )
    except RestrictionOverridePermissionError:
        db.rollback()
        raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")


@router.post("/manual-ota", response_model=ReservationRead, status_code=status.HTTP_201_CREATED)
def create_or_update_manual_ota(
    data: ManualOTAReservationCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_RESERVATION_CREATE, PERMISSION_RESERVATION_UPDATE)
    ),
):
    if data.total_amount is not None:
        _ensure_manual_rate_permission(db, context)
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para crear nuevas reservas.",
        )
    try:
        reservation = create_or_update_manual_ota_reservation(
            db,
            hotel_id=context.hotel_id,
            data=data,
            actor_user_id=context.user_id,
        )
        db.commit()
        db.refresh(reservation)
        _project_reservation_graph(context.hotel_id, reservation)
        return _to_read(reservation)
    except OTAManualReservationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[ReservationRead])
@router.get("", response_model=list[ReservationRead], include_in_schema=False)
def list_reservations(
    status_filter: str = "",
    from_date: date = None,
    to_date: date = None,
    search: str = "",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    order: Literal["recent", "check_in"] = "recent",
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    reservations = list_reservations_service(
        db,
        hotel_id=context.hotel_id,
        status_filter=status_filter,
        from_date=from_date,
        to_date=to_date,
        search=search,
        skip=skip,
        limit=limit,
        order=order,
    )
    try:
        return [_to_read(r) for r in reservations]
    except Exception as exc:
        logger.error("Reservation serialization failed for hotel_id=%s error_type=%s", context.hotel_id, type(exc).__name__)
        raise HTTPException(status_code=500, detail="No se pudieron serializar las reservas") from exc


@router.get("/actions/pending", response_model=list[ReservationPendingActionRead])
def list_pending_actions(
    limit: int = 100,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    safe_limit = max(1, min(limit, 250))
    try:
        return list_pending_reservation_actions(db, hotel_id=context.hotel_id, limit=safe_limit)
    except PaymentError as exc:
        logger.error("Pending actions failed for hotel_id=%s error_type=%s", context.hotel_id, type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail=f"No se pudieron calcular las acciones pendientes: {exc}",
        ) from exc


@router.get("/occupancy-grid", response_model=OccupancyGridResponse)
def occupancy_grid(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_READ)),
):
    """B2: planilla de ocupación — rooms x days grid data for one hotel."""
    if date_to <= date_from:
        raise HTTPException(status_code=422, detail="date_to must be greater than date_from")
    if (date_to - date_from).days > 92:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 92 days")
    grid = get_occupancy_grid(
        db,
        hotel_id=context.hotel_id,
        date_from=date_from,
        date_to=date_to,
    )
    if context.user_role != "housekeeping":
        return grid

    # Housekeeping needs the room/date occupancy blocks, never guest identity,
    # confirmation codes, payment balances, or unassigned reservation data.
    return {
        **grid,
        "reservations": [
            {
                **reservation,
                "confirmation_code": "",
                "guest_name": "",
                "operational_balance_due": 0.0,
            }
            for reservation in grid["reservations"]
        ],
        "unassigned": [],
    }


@router.get("/{reservation_id}/operations-summary", response_model=ReservationOperationsSummaryRead)
def reservation_operations_summary(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    try:
        return get_reservation_operations_summary(
            db,
            hotel_id=context.hotel_id,
            reservation_id=reservation_id,
        )
    except ReservationActionError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{reservation_id}/operations/resolve-external", response_model=ReservationExternalResolutionResponse)
def resolve_external_follow_up(
    reservation_id: int,
    payload: ReservationActionResolveRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_UPDATE)),
):
    try:
        response = resolve_external_channel_follow_up(
            db,
            hotel_id=context.hotel_id,
            reservation_id=reservation_id,
            resolved_by_user_id=context.user_id,
            notes=payload.notes,
        )
        db.commit()
        return response
    except ReservationActionError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{reservation_id}/operations/clear-manual-review", response_model=ReservationManualReviewResponse)
def clear_manual_review(
    reservation_id: int,
    payload: ReservationActionResolveRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_UPDATE)),
):
    try:
        response = clear_reservation_manual_review(
            db,
            hotel_id=context.hotel_id,
            reservation_id=reservation_id,
            reviewed_by_user_id=context.user_id,
            notes=payload.notes,
        )
        db.commit()
        return response
    except ReservationActionError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{reservation_id}/operations/register-settlement", response_model=ReservationRead)
def register_settlement(
    reservation_id: int,
    payload: ReservationActionResolveRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_RESERVATION_UPDATE, PERMISSION_COMPANY_MANAGE)
    ),
):
    """Register the deferred corporate collection (v72 §3.5): settled."""
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    try:
        register_company_settlement(
            db,
            reservation,
            hotel_id=context.hotel_id,
            actor_user_id=context.user_id,
            notes=payload.notes,
        )
        db.commit()
    except ReservationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return _to_read(reservation)


@router.get("/{reservation_id}", response_model=ReservationRead)
def get_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return _to_read(reservation)


from app.schemas.guest import GuestCreate
from app.models.guest import Guest

@router.post("/{reservation_id}/guests", response_model=ReservationRead)
def add_reservation_guests(
    reservation_id: int,
    guests: list[GuestCreate],
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_RESERVATION_UPDATE, PERMISSION_GUEST_CREATE)
    ),
):
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    category = reservation.category or db.query(RoomCategory).filter(
        RoomCategory.id == reservation.category_id,
        RoomCategory.hotel_id == context.hotel_id,
    ).first()
    if not category:
        raise HTTPException(status_code=400, detail="Room category not found for reservation")

    linked_guest_ids = {reservation.guest_id}
    linked_guest_ids.update(g.id for g in reservation.additional_guests)
    incoming_existing_guest_ids: set[int] = set()
    incoming_new_document_numbers: set[str] = set()
    incoming_new_without_document = 0

    document_numbers = {
        str(guest_data.document_number or "").strip()
        for guest_data in guests
        if str(guest_data.document_number or "").strip()
    }
    existing_guests_by_document = {}
    if document_numbers:
        # Compare and key by the trimmed value on both sides: legacy rows
        # created before this endpoint normalized whitespace can still have
        # raw, untrimmed document_number values stored, and a mismatch here
        # would miss the existing guest and then collide on insert instead.
        existing_guests_by_document = {
            guest.document_number.strip(): guest
            for guest in (
                db.query(Guest)
                .filter(
                    Guest.hotel_id == context.hotel_id,
                    func.trim(Guest.document_number).in_(document_numbers),
                )
                .all()
            )
            if guest.document_number and guest.document_number.strip()
        }

    for guest_data in guests:
        document_number = str(guest_data.document_number or "").strip()
        if document_number:
            if document_number in incoming_new_document_numbers:
                continue
            existing_guest = existing_guests_by_document.get(document_number)
            existing_guest_id = existing_guest.id if existing_guest else None
            if existing_guest_id:
                if existing_guest_id not in linked_guest_ids:
                    incoming_existing_guest_ids.add(existing_guest_id)
            else:
                incoming_new_document_numbers.add(document_number)
        else:
            incoming_new_without_document += 1

    proposed_guest_count = (
        len(linked_guest_ids)
        + len(incoming_existing_guest_ids)
        + len(incoming_new_document_numbers)
        + incoming_new_without_document
    )
    if proposed_guest_count > category.max_occupancy:
        raise HTTPException(
            status_code=400,
            detail=(
                "Guest capacity exceeded for reservation room category: "
                f"max_occupancy={category.max_occupancy}, requested_total={proposed_guest_count}"
            ),
        )

    for guest_data in guests:
        # Existing document-bearing guests were loaded in one tenant-scoped
        # query above. Keep the map current for duplicate new documents in the
        # same request as well.
        document_number = str(guest_data.document_number or "").strip()
        guest = existing_guests_by_document.get(document_number) if document_number else None

        if not guest:
            guest_fields = guest_data.model_dump(exclude={"companions"})
            if document_number:
                # Store the same normalized value we looked up by, so this
                # row matches on the next request instead of silently
                # drifting back into the whitespace-mismatch this fixes.
                guest_fields["document_number"] = document_number
            guest = Guest(**guest_fields, hotel_id=context.hotel_id)
            db.add(guest)
            db.flush()
            if document_number:
                existing_guests_by_document[document_number] = guest
        
        # Link if not linked
        if guest not in reservation.additional_guests:
            reservation.additional_guests.append(guest)
            
    db.commit()
    db.refresh(reservation)
    return _to_read(reservation)


@router.post("/{reservation_id}/cancel", response_model=ReservationRead)
def cancel_reservation(
    reservation_id: int,
    manager_pin: str | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CANCEL)),
):
    """Cancel a reservation. Post check-in cancellations are not allowed."""
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para gestionar reservas.",
        )
    r = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if r.status in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT):
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel a reservation that is already checked-in or checked-out",
        )

    if r.status == ReservationStatusEnum.CANCELLED:
        raise HTTPException(status_code=400, detail="Reservation is already cancelled")
    before = audit_log_service.model_snapshot(r)
    try:
        transition_reservation_status(
            db,
            r,
            ReservationStatusEnum.CANCELLED,
            context.hotel_id,
            reason_code="cancelled_by_user",
            changed_by_user_id=context.user_id,
        )
        # Cancel any still-payable seña links so the guest can't pay a stale link.
        try:
            from app.services.payment_link_service import cancel_active_links_for_reservation

            cancel_active_links_for_reservation(db, context.hotel_id, r.id, reason="reservation cancelled")
        except Exception as exc:  # best-effort; never block the cancellation
            logger.error("Failed cancelling payment links for reservation %s error_type=%s", r.id, type(exc).__name__)
        db.commit()
        db.refresh(r)
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="reservations",
            record_id=r.id,
            action=AuditActionEnum.STATUS_CHANGE,
            actor_user_id=context.user_id,
            payload_before=before,
            payload_after=audit_log_service.model_snapshot(r),
        )
        return _to_read(r)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{reservation_id}/charges",
    response_model=ReservationBillingAdjustmentSummaryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_reservation_charge(
    reservation_id: int,
    payload: ReservationChargeCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CHARGE)),
):
    """Record a human-readable consumption or extra charge for an active stay."""
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    try:
        charge = add_reservation_charge(
            db,
            reservation=reservation,
            hotel_id=context.hotel_id,
            amount=payload.amount,
            currency_code=payload.currency_code,
            description=payload.description,
            actor_user_id=context.user_id,
        )
        db.commit()
        db.refresh(charge)
        return ReservationBillingAdjustmentSummaryRead(
            id=charge.id,
            type=charge.adjustment_type.value,
            amount=charge.amount,
            tax_amount=charge.tax_amount,
            total_amount=charge.total_amount,
            currency_code=charge.currency_code,
            notes=charge.notes,
        )
    except ReservationOperationsError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{reservation_id}/release-no-guarantee", response_model=ReservationRead)
def release_no_guarantee_reservation(
    reservation_id: int,
    reason: str | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CANCEL)),
):
    """§10.2 — Internally release a no-guarantee OTA reservation (no provider cancel call)."""
    # This provider-reconciliation exception remains a manager lane. The
    # canonical cancellation permission is still evaluated first (and can be
    # revoked per user/role), while ordinary receptionist cancellations use
    # the normal /cancel action above.
    if not _is_manager_context(context):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenes permisos para esta accion")
    r = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    before = audit_log_service.model_snapshot(r)
    try:
        release_no_guarantee(
            db,
            reservation=r,
            actor_user_id=context.user_id,
            reason=reason,
        )
        db.commit()
        db.refresh(r)
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="reservations",
            record_id=r.id,
            action=AuditActionEnum.STATUS_CHANGE,
            actor_user_id=context.user_id,
            payload_before=before,
            payload_after=audit_log_service.model_snapshot(r),
        )
        return _to_read(r)
    except OTAManualReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{reservation_id}/noshow", response_model=ReservationRead)
def mark_no_show(
    reservation_id: int,
    payload: ReservationNoShowRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CANCEL)),
):
    """Mark a reservation as no-show without automatic charge."""
    r = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    before = audit_log_service.model_snapshot(r)
    try:
        mark_reservation_no_show(
            db,
            r,
            hotel_id=context.hotel_id,
            client_version=payload.client_version,
            changed_by_user_id=context.user_id,
            notes=payload.notes,
        )
        db.commit()
        db.refresh(r)
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="reservations",
            record_id=r.id,
            action=AuditActionEnum.STATUS_CHANGE,
            actor_user_id=context.user_id,
            payload_before=before,
            payload_after=audit_log_service.model_snapshot(r),
        )
        return _to_read(r)
    except ReservationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{reservation_id}/date-change", response_model=ReservationDateChangeResponse)
def change_dates(
    reservation_id: int,
    payload: ReservationDateChangeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_UPDATE)),
):
    if payload.room_id is not None:
        _ensure_action_permission(db, context, PERMISSION_RESERVATION_MOVE)
    r = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    before = audit_log_service.model_snapshot(r)
    try:
        result = change_reservation_dates(
            db,
            reservation=r,
            hotel_id=context.hotel_id,
            check_in_date=payload.check_in_date,
            check_out_date=payload.check_out_date,
            client_version=payload.client_version,
            room_id=payload.room_id,
            pricing_mode=payload.pricing_mode,
            manager_authorized=_is_manager_context(context),
            changed_by_user_id=context.user_id,
            reason=payload.reason,
        )
        db.commit()
        db.refresh(result.original_reservation)
        db.refresh(result.reservation)
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="reservations",
            record_id=result.reservation.id,
            action=AuditActionEnum.UPDATE,
            actor_user_id=context.user_id,
            payload_before=before,
            payload_after=audit_log_service.model_snapshot(result.reservation),
        )
        background_tasks.add_task(
            _trigger_reoptimization_bg,
            hotel_id=context.hotel_id,
            trigger_type="reservation_date_change",
        )
        return ReservationDateChangeResponse(
            original_reservation=_to_read(result.original_reservation),
            reservation=_to_read(result.reservation),
            recreated=result.recreated,
            status_transitioned=result.status_transitioned,
        )
    except ReservationOperationsError as e:
        db.rollback()
        status_code = 403 if "requiere gerente" in str(e) else 400
        raise HTTPException(status_code=status_code, detail=str(e))


@router.patch("/{reservation_id}", response_model=ReservationRead)
def modify_reservation(
    reservation_id: int,
    data: ReservationUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_UPDATE)),
):
    """Modify a reservation (dates, notes, room). Only allowed for pre-check-in states."""
    if "room_id" in data.model_fields_set:
        _ensure_action_permission(db, context, PERMISSION_RESERVATION_MOVE)
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para gestionar reservas.",
        )
    r = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if r.status in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT, ReservationStatusEnum.CANCELLED):
        raise HTTPException(status_code=400, detail=("Cannot modify: reservation is " + r.status.value))
    before = audit_log_service.model_snapshot(r)
    mobility_restriction_changed = (
        "mobility_restriction" in data.model_fields_set
        and data.mobility_restriction != r.mobility_restriction
    )
    try:
        update_reservation_fields(
            db,
            r,
            data,
            context.hotel_id,
            changed_by_user_id=context.user_id,
            actor_role=context.user_role,
            room_move_reason_code="manual_update",
            room_move_notes="Cambio manual desde API de reservas",
            client_version=data.client_version,
        )
        db.commit()
        db.refresh(r)
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="reservations",
            record_id=r.id,
            action=AuditActionEnum.UPDATE,
            actor_user_id=context.user_id,
            payload_before=before,
            payload_after=audit_log_service.model_snapshot(r),
        )
        if any(value is not None for value in (data.check_in_date, data.check_out_date, data.room_id)) or mobility_restriction_changed:
            background_tasks.add_task(
                _trigger_reoptimization_bg,
                hotel_id=context.hotel_id,
                trigger_type="reservation_update",
            )
        return _to_read(r)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GuestProhibitedError as e:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": e.code, "message": str(e), "restriction_id": e.restriction_id},
        )
    except RestrictionOverridePermissionError:
        db.rollback()
        raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")

@router.post("/{reservation_id}/extend", response_model=ReservationExtensionResponse)
def extend_stay(
    reservation_id: int,
    payload: ReservationExtensionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_UPDATE)),
):
    """Extend a guest's stay to a new checkout date."""
    r = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    before = audit_log_service.model_snapshot(r)
    try:
        result = extend_reservation_stay(
            db,
            reservation=r,
            hotel_id=context.hotel_id,
            new_checkout_date=payload.new_checkout_date,
            client_version=payload.client_version,
            pricing_mode=payload.pricing_mode,
            payment_action=payload.payment_action,
            immediate_payment=payload.immediate_payment,
            payment_link=payload.payment_link,
            changed_by_user_id=context.user_id,
            notes=payload.notes,
        )
        if not result.success:
            db.rollback()
            raise HTTPException(status_code=409, detail={"message": "Extension conflict could not be resolved", "conflicts": result.conflicts or []})
        db.commit()
        db.refresh(r)
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="reservations",
            record_id=r.id,
            action=AuditActionEnum.UPDATE,
            actor_user_id=context.user_id,
            payload_before=before,
            payload_after=audit_log_service.model_snapshot(r),
        )
        response = ReservationExtensionResponse(
            reservation=_to_read(r),
            extension_amount=result.extension_amount,
            transaction=result.transaction,
            payment_link=result.payment_link,
        )
        background_tasks.add_task(
            _trigger_reoptimization_bg,
            hotel_id=context.hotel_id,
            trigger_type="reservation_date_change",
        )
        return response
    except ReservationOperationsError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{reservation_id}/room-move", response_model=RoomMoveResponse)
def room_move(
    reservation_id: int,
    payload: RoomMoveRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_MOVE)),
):
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    before = audit_log_service.model_snapshot(reservation)
    try:
        result = move_reservation_room(
            db,
            reservation=reservation,
            to_room_id=payload.to_room_id,
            hotel_id=context.hotel_id,
            moved_by_user_id=context.user_id,
            reason_code=payload.reason_code,
            notes=payload.notes,
            price_action=payload.price_action,
        )
        event = result.event
        db.commit()
        db.refresh(reservation)
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="reservations",
            record_id=reservation.id,
            action=AuditActionEnum.UPDATE,
            actor_user_id=context.user_id,
            payload_before=before,
            payload_after=audit_log_service.model_snapshot(reservation),
        )
        _project_reservation_graph(context.hotel_id, reservation)
        project_room_movement(
            context.hotel_id,
            reservation.id,
            event.from_room_id,
            event.to_room_id,
            event.movement_group_id or event.id,
        )
        background_tasks.add_task(
            _trigger_reoptimization_bg,
            hotel_id=context.hotel_id,
            trigger_type="reservation_room_move",
        )
        return RoomMoveResponse(
            reservation=_to_read(reservation),
            category_changed=result.category_changed,
            price_action=result.price_action,
            previous_total_amount=result.previous_total_amount,
            quoted_total_amount=result.quoted_total_amount,
            amount_delta=result.amount_delta,
            currency_code=result.currency_code,
        )
    except ReservationOperationsError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{reservation_id}/rebook-direct", response_model=OTARebookToDirectResponse)
def rebook_ota_to_direct(
    reservation_id: int,
    payload: OTARebookToDirectRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_RESERVATION_UPDATE, PERMISSION_RESERVATION_CREATE)
    ),
):
    if payload.total_override is not None:
        _ensure_manual_rate_permission(db, context)
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    try:
        result = rebook_ota_reservation_as_direct(
            db,
            reservation=reservation,
            hotel_id=context.hotel_id,
            target_category_id=payload.target_category_id,
            target_rate_plan_id=payload.target_rate_plan_id,
            target_tax_policy_id=payload.target_tax_policy_id,
            created_by_user_id=context.user_id,
            target_room_id=payload.target_room_id,
            pricing_channel_code=payload.pricing_channel_code,
            guest_scope=payload.guest_scope,
            target_currency=payload.target_currency,
            discount_pct=payload.discount_pct,
            total_override=payload.total_override,
            notes=payload.notes,
        )
        db.commit()
        return OTARebookToDirectResponse(
            adjustment_id=result.adjustment.id,
            original_reservation_id=result.original_reservation.id,
            new_reservation_id=result.new_reservation.id,
            billing_adjustment_id=(result.billing_adjustment.id if result.billing_adjustment else None),
            amount_delta=result.adjustment.amount_delta or 0.0,
            currency_code=result.adjustment.currency_code,
            quoted_total_amount=result.preview.quoted_total_amount,
            pricing_source=result.preview.pricing_source,
        )
    except ReservationOperationsError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{reservation_id}/rebook-direct/preview", response_model=OTARebookPreviewResponse)
def preview_ota_rebook_to_direct(
    reservation_id: int,
    payload: OTARebookToDirectRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    if payload.total_override is not None:
        _ensure_manual_rate_permission(db, context)
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    try:
        preview = preview_ota_rebook_as_direct(
            db,
            reservation=reservation,
            hotel_id=context.hotel_id,
            target_category_id=payload.target_category_id,
            target_rate_plan_id=payload.target_rate_plan_id,
            target_tax_policy_id=payload.target_tax_policy_id,
            pricing_channel_code=payload.pricing_channel_code,
            guest_scope=payload.guest_scope,
            target_currency=payload.target_currency,
            discount_pct=payload.discount_pct,
            total_override=payload.total_override,
        )
        return OTARebookPreviewResponse(
            target_category_id=preview.target_category_id,
            target_rate_plan_id=preview.target_rate_plan_id,
            target_sellable_product_id=preview.target_sellable_product_id,
            pricing_source=preview.pricing_source,
            currency_code=preview.currency_code,
            original_total_amount=preview.original_total_amount,
            quoted_total_amount=preview.quoted_total_amount,
            subtotal_amount=preview.subtotal_amount,
            tax_amount=preview.tax_amount,
            fee_amount=preview.fee_amount,
            commission_amount=preview.commission_amount,
            net_amount=preview.net_amount,
            deposit_amount=preview.deposit_amount,
            amount_delta=preview.amount_delta,
            fx_rate_snapshot=preview.fx_rate_snapshot,
        )
    except ReservationOperationsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/allocation/recalculate", response_model=AllocationRunResponse)
def recalculate_allocation(
    payload: AllocationRunRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_MOVE)),
):
    result = run_persisted_allocation(
        db,
        hotel_id=context.hotel_id,
        trigger_type="manual_api_recalculate",
        apply=payload.apply,
        horizon_start=payload.horizon_start,
        horizon_end=payload.horizon_end,
    )
    db.commit()
    return AllocationRunResponse(
        run_id=result.run.id,
        status=result.run.status.value if hasattr(result.run.status, "value") else str(result.run.status),
        objective_score=result.run.objective_score or 0.0,
        assignments_created=len(result.solver_result.assignments),
        unassigned_count=len(result.solver_result.unassigned_reservations),
        moved_count=len(result.solver_result.moved_reservations),
    )
