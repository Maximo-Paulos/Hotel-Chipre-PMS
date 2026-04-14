"""
FastAPI routes for Reservations.
Complete CRUD + cancel, modify, no-show, extend stay.
"""
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory
from app.models.hotel_config import HotelConfiguration
from app.schemas.reservation import ReservationCreate, ReservationRead, ReservationUpdate
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
    check_room_availability,
    find_available_rooms,
    ReservationError,
    list_reservations as list_reservations_service,
    get_reservation_by_id,
    update_reservation_fields,
)
from app.services.reservation_operations_service import (
    ReservationOperationsError,
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
from app.services.allocation_runtime_service import run_persisted_allocation
from app.dependencies.auth import get_auth_context, AuthContext, require_roles

router = APIRouter(prefix="/api/reservations", tags=["Reservations"])


def _to_read(r: Reservation) -> ReservationRead:
    result = ReservationRead.model_validate(r)
    result.balance_due = r.balance_due
    result.nights = r.nights
    result.additional_guests = [
        {"id": g.id, "first_name": g.first_name, "last_name": g.last_name, "document_type": g.document_type, "document_number": g.document_number}
        for g in r.additional_guests
    ]
    return result


# Accept with and without trailing slash to avoid 405 when the FE omits it.
@router.post("/", response_model=ReservationRead, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=ReservationRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_new_reservation(
    data: ReservationCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
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
        return _to_read(reservation)
    except ReservationError as e:
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
    return [_to_read(r) for r in reservations]


@router.get("/actions/pending", response_model=list[ReservationPendingActionRead])
def list_pending_actions(
    limit: int = 100,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
):
    safe_limit = max(1, min(limit, 250))
    return list_pending_reservation_actions(db, hotel_id=context.hotel_id, limit=safe_limit)


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
        return _to_read(r)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{reservation_id}/noshow", response_model=ReservationRead)
def mark_no_show(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """Mark a reservation as no-show (cancels it). Valid when guest doesn't arrive."""
    r = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if r.status in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT, ReservationStatusEnum.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Cannot mark no-show: reservation is '{r.status.value}'")
    try:
        r.notes = (r.notes or '') + f'\n[NO-SHOW] Marcado como no-show el {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}'
        transition_reservation_status(
            db,
            r,
            ReservationStatusEnum.CANCELLED,
            context.hotel_id,
            reason_code="no_show",
            changed_by_user_id=context.user_id,
        )
        db.commit()
        db.refresh(r)
        return _to_read(r)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{reservation_id}", response_model=ReservationRead)
def modify_reservation(
    reservation_id: int,
    data: ReservationUpdate,
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
    try:
        update_reservation_fields(
            db,
            r,
            data,
            context.hotel_id,
            changed_by_user_id=context.user_id,
            room_move_reason_code="manual_update",
            room_move_notes="Cambio manual desde API de reservas",
        )
        db.commit()
        db.refresh(r)
        return _to_read(r)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{reservation_id}/extend", response_model=ReservationRead)
def extend_stay(
    reservation_id: int,
    new_checkout: date,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """Extend a guest's stay to a new checkout date."""
    r = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if r.status not in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.FULLY_PAID):
        raise HTTPException(status_code=400, detail=f"Can only extend stays that are checked-in or fully paid, got '{r.status.value}'")
    if new_checkout <= r.check_out_date:
        raise HTTPException(status_code=400, detail="New checkout must be after current checkout")
    if r.room_id and not check_room_availability(
        db,
        r.room_id,
        r.check_out_date,
        new_checkout,
        hotel_id=context.hotel_id,
        exclude_reservation_id=r.id,
    ):
        raise HTTPException(status_code=400, detail="Room is not available for the extended dates")

    extra_nights = (new_checkout - r.check_out_date).days
    try:
        update_reservation_fields(
            db,
            r,
            ReservationUpdate(check_out_date=new_checkout),
            context.hotel_id,
            changed_by_user_id=context.user_id,
            room_move_reason_code="extend_stay",
            room_move_notes=f"Extension hasta {new_checkout}",
        )
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    r.notes = (r.notes or '') + f"\n[EXTENSION] +{extra_nights} noches hasta {new_checkout}"

    if r.balance_due > 0 and r.status == ReservationStatusEnum.FULLY_PAID:
        r.status = ReservationStatusEnum.DEPOSIT_PAID

    db.commit()
    db.refresh(r)
    return _to_read(r)


@router.post("/{reservation_id}/room-move", response_model=ReservationRead)
def room_move(
    reservation_id: int,
    payload: RoomMoveRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
):
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    try:
        move_reservation_room(
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
