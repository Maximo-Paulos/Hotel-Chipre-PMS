"""
FastAPI routes for Reservations.
Complete CRUD + cancel, modify, no-show, extend stay.
"""
import logging
from datetime import date
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
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
    ReservationManualReviewResponse,
    ReservationOperationsSummaryRead,
    ReservationPendingActionRead,
    RoomMoveRequest,
)
from app.services.reservation_service import (
    create_reservation,
    transition_reservation_status,
    find_available_rooms,
    ReservationError,
    list_reservations as list_reservations_service,
    get_reservation_by_id,
    mark_reservation_no_show,
    update_reservation_fields,
    register_company_settlement,
)
from app.services.reservation_operations_service import (
    ReservationOperationsError,
    change_reservation_dates,
    extend_reservation_stay,
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
from app.dependencies.auth import get_auth_context, AuthContext, require_roles, require_permission
from app.services.permission_service import PERMISSION_RESERVATION_CREATE, PERMISSION_RESERVATION_ROOM_MOVE
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


def _trigger_reoptimization_bg(hotel_id: int, trigger_type: str = "new_reservation") -> None:
    """
    §5.2 — Run allocation engine in background after reservation changes.
    Creates its own DB session; all errors are suppressed to never affect the booking flow.
    """
    from app.database import get_session_factory
    from app.services.allocation_runtime_service import run_persisted_allocation

    db = None
    try:
        SessionFactory = get_session_factory()
        db = SessionFactory()
        run_persisted_allocation(db, hotel_id=hotel_id, trigger_type=trigger_type)
        db.commit()
    except Exception:
        logger.exception(
            "Background reservation reoptimization failed for hotel_id=%s trigger_type=%s",
            hotel_id,
            trigger_type,
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
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para crear nuevas reservas.",
        )
    try:
        reservation = create_reservation(db, data, hotel_id=context.hotel_id)
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


@router.post("/manual-ota", response_model=ReservationRead, status_code=status.HTTP_201_CREATED)
def create_or_update_manual_ota(
    data: ManualOTAReservationCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CREATE)),
):
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="SuscripciÃ³n inactiva. ReactivÃ¡ el plan para crear nuevas reservas.",
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
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    reservations = list_reservations_service(
        db, hotel_id=context.hotel_id, status_filter=status_filter, from_date=from_date, to_date=to_date
    )
    try:
        return [_to_read(r) for r in reservations]
    except Exception as exc:
        logger.exception("Reservation serialization failed for hotel_id=%s", context.hotel_id)
        raise HTTPException(status_code=500, detail="No se pudieron serializar las reservas") from exc


@router.get("/actions/pending", response_model=list[ReservationPendingActionRead])
def list_pending_actions(
    limit: int = 100,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
):
    safe_limit = max(1, min(limit, 250))
    try:
        return list_pending_reservation_actions(db, hotel_id=context.hotel_id, limit=safe_limit)
    except PaymentError as exc:
        logger.exception("Pending actions failed for hotel_id=%s", context.hotel_id)
        raise HTTPException(
            status_code=500,
            detail=f"No se pudieron calcular las acciones pendientes: {exc}",
        ) from exc


@router.get("/{reservation_id}/operations-summary", response_model=ReservationOperationsSummaryRead)
def reservation_operations_summary(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
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
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
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
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
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
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
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
    context: AuthContext = Depends(get_auth_context),
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
    context: AuthContext = Depends(get_auth_context),
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

    for guest_data in guests:
        document_number = str(guest_data.document_number or "").strip()
        if document_number:
            if document_number in incoming_new_document_numbers:
                continue
            existing_guest_id = (
                db.query(Guest.id)
                .filter(
                    Guest.document_number == document_number,
                    Guest.hotel_id == context.hotel_id,
                )
                .limit(1)
                .scalar()
            )
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
        # Check if guest already exists by DocNum
        guest = None
        if guest_data.document_number:
            guest = db.query(Guest).filter(
                Guest.document_number == guest_data.document_number,
                Guest.hotel_id == context.hotel_id,
            ).first()
        
        if not guest:
            guest = Guest(**guest_data.model_dump(exclude={"companions"}), hotel_id=context.hotel_id)
            db.add(guest)
            db.flush()
        
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
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
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


@router.post("/{reservation_id}/release-no-guarantee", response_model=ReservationRead)
def release_no_guarantee_reservation(
    reservation_id: int,
    reason: str | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """§10.2 — Internally release a no-guarantee OTA reservation (no provider cancel call)."""
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
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "receptionist")),
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
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "receptionist")),
):
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
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """Modify a reservation (dates, notes, room). Only allowed for pre-check-in states."""
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

@router.post("/{reservation_id}/extend", response_model=ReservationExtensionResponse)
def extend_stay(
    reservation_id: int,
    payload: ReservationExtensionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
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


@router.post("/{reservation_id}/room-move", response_model=ReservationRead)
def room_move(
    reservation_id: int,
    payload: RoomMoveRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_ROOM_MOVE)),
):
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    before = audit_log_service.model_snapshot(reservation)
    try:
        event = move_reservation_room(
            db,
            reservation=reservation,
            to_room_id=payload.to_room_id,
            hotel_id=context.hotel_id,
            moved_by_user_id=context.user_id,
            reason_code=payload.reason_code,
            notes=payload.notes,
        )
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
        return _to_read(reservation)
    except ReservationOperationsError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{reservation_id}/rebook-direct", response_model=OTARebookToDirectResponse)
def rebook_ota_to_direct(
    reservation_id: int,
    payload: OTARebookToDirectRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
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
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
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
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
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
