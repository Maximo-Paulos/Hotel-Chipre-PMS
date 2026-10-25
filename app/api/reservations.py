"""
FastAPI routes for Reservations.
Complete CRUD + cancel, modify, no-show, extend stay.
"""
import csv
import json
import logging
from datetime import date
from decimal import Decimal
from io import StringIO
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.services.row_locks import lock_query
from app.database import get_db
from app.models.audit_log import AuditActionEnum
from app.models.company import Company
from app.models.guest import Guest
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.cancellation_review import ReservationCancellationReview
from app.models.security_audit_log import SecurityAuditLog
from app.models.room import Room, RoomCategory
from app.models.hotel_config import HotelConfiguration
from app.schemas.reservation import (
    ReservationCreate,
    ReservationDateChangeRequest,
    ReservationDateChangeResponse,
    CompanyExtensionRequestUpdate,
    ReservationExtensionRequest,
    ReservationExtensionPreviewResponse,
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
    ManualRoomMoveReasonCodeEnum,
    RoomMoveRequest,
    RoomMoveResponse,
)
from app.schemas.cancellation_review import (
    CancellationReviewDecisionRequest,
    CancellationReviewRead,
    CancellationReviewResolutionResponse,
    ReservationCancellationResponse,
)
from app.schemas.company_reservation_terms import (
    CompanyReservationTermsReviewEventRead,
    CompanyReservationTermsReviewRead,
    CompanyReservationTermsReviewRequest,
)
from app.services.reservation_service import (
    ConfirmedReservationPriceLocked,
    ManualRatePolicyError,
    create_reservation,
    transition_reservation_status,
    ReservationError,
    list_reservations as list_reservations_service,
    get_occupancy_grid,
    get_reservation_by_id,
    ReservationVersionConflict,
    mark_reservation_no_show,
    register_company_settlement,
    deferred_company_reservation_ids,
    reservation_has_deferred_company_billing,
)
from app.services.reservation_update_service import (
    ReservationUpdateAuthorization,
    ReservationUpdatePreparationError,
    apply_reservation_update,
    prepare_reservation_update,
)
from app.services.read_model_cache import get_cached_occupancy_grid_payload
from app.services.csv_export_safety import spreadsheet_safe_row
from app.services.guest_restriction_service import GuestProhibitedError, RestrictionOverridePermissionError
from app.services.reservation_operations_service import (
    ReservationOperationsError,
    ReservationExtensionImpactConfirmationError,
    RoomMovePermissionError,
    change_reservation_dates,
    extend_reservation_stay,
    preview_reservation_stay_extension,
    plan_reservation_extension_impact,
    set_company_extension_request,
    add_reservation_charge,
    move_reservation_room,
    preview_ota_rebook_as_direct,
    rebook_ota_reservation_as_direct,
    reservation_has_payment_or_deposit,
)
from app.services.room_movement_group_service import RoomMovementGroupError
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
from app.services.financial_ledger import (
    external_paid_balance_credit,
    has_payment_history_for_cancellation,
)
from app.services.allocation_runtime_service import (
    reservation_overlaps_default_horizon,
    run_persisted_allocation,
)
from app.services.allocation_trigger_service import (
    trigger_reoptimization_bg as _coalesced_reoptimization_bg,
)
from app.dependencies.auth import AuthContext, authorize_permission, get_auth_context, require_all_permissions, require_any_permission, require_permission
from app.api.manual_rate_access import authorize_manual_rate_scope
from app.services.timezones import hotel_today
from app.services.permission_service import (
    PERMISSION_CASH_OPERATE,
    PERMISSION_CASH_RECORD_PRIOR_RECEIPT,
    PERMISSION_COMPANY_MANAGE,
    PERMISSION_GUEST_CREATE,
    PERMISSION_GUEST_READ,
    PERMISSION_RESERVATION_CANCEL,
    PERMISSION_RESERVATION_CANCEL_PAID,
    PERMISSION_RESERVATION_CANCEL_PENALTY_APPROVE,
    PERMISSION_OTA_PAYMENT_CONFIRM,
    PERMISSION_RESERVATION_CHARGE,
    PERMISSION_RESERVATION_CREATE,
    PERMISSION_RESERVATION_PAID_TOTAL_ADJUST,
    PERMISSION_RESERVATION_EXPORT,
    PERMISSION_RESERVATION_MANUAL_RATE,
    PERMISSION_RESERVATION_RATE_ADJUST,
    PERMISSION_RESERVATION_MOVE,
    PERMISSION_RESERVATION_MOVE_CAPACITY,
    PERMISSION_RESERVATION_MOVE_CATEGORY,
    PERMISSION_RESERVATION_OTA_RECORD,
    PERMISSION_RESERVATION_READ,
    PERMISSION_RESERVATION_UPDATE,
    PERMISSION_ROOM_READ,
    PERMISSION_OCCUPANCY_VIEW,
    RESERVATION_MOVE_TIER_PERMISSIONS,
    audit_permission_denied,
    resolve,
)
from app.services.reservation_cancellation_service import (
    CancellationConfigurationRequired,
    CancellationReviewConflict,
    CancellationReviewNotFound,
    get_pending_cancellation_review,
    list_pending_cancellation_reviews,
    prepare_cancellation_request,
    process_payment_link_revocations_after_commit,
    request_reservation_cancellation,
    resolve_cancellation_review,
    review_read_payload,
)
from app.services.company_reservation_terms_service import (
    CompanyTermsReviewConflict,
    CompanyTermsReviewError,
    CompanyTermsReviewNotFound,
    get_company_terms_review,
    review_company_reservation_terms,
)
from app.services import audit_log_service
from app.services.temporary_action_grant_service import (
    TemporaryGrantActor,
    TemporaryGrantError,
    consume_grant_for_action,
)
from app.services.graph_projection import (
    project_company_link,
    project_reservation_assignment,
    project_room_movement,
)

router = APIRouter(prefix="/api/reservations", tags=["Reservations"])
logger = logging.getLogger(__name__)
_RESERVATION_CSV_MAX_RANGE_DAYS = 367
_RESERVATION_CSV_MAX_ROWS = 10_000


def _company_terms_review_response(
    *, reservation_id: int, state: dict, events: list[object]
) -> CompanyReservationTermsReviewRead:
    return CompanyReservationTermsReviewRead(
        reservation_id=reservation_id,
        history=[CompanyReservationTermsReviewEventRead.model_validate(event) for event in events],
        **state,
    )


@router.get(
    "/{reservation_id}/company-terms-review",
    response_model=CompanyReservationTermsReviewRead,
)
def read_company_terms_review(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_COMPANY_MANAGE, PERMISSION_RESERVATION_READ)
    ),
):
    """Read the company terms snapshot and current profile drift for managers."""
    try:
        state, events = get_company_terms_review(
            db,
            hotel_id=context.hotel_id,
            reservation_id=reservation_id,
        )
        return _company_terms_review_response(
            reservation_id=reservation_id,
            state=state,
            events=events,
        )
    except CompanyTermsReviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CompanyTermsReviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{reservation_id}/company-terms-review",
    response_model=CompanyReservationTermsReviewRead,
)
def decide_company_terms_review(
    reservation_id: int,
    payload: CompanyReservationTermsReviewRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_COMPANY_MANAGE, PERMISSION_RESERVATION_READ)
    ),
):
    """Record an auditable keep-snapshot or accept-current-config decision."""
    if context.user_id is None:
        raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")
    try:
        review_company_reservation_terms(
            db,
            hotel_id=context.hotel_id,
            reservation_id=reservation_id,
            actor_user_id=context.user_id,
            action=payload.action,
            reason=payload.reason,
            expected_config_fingerprint=payload.expected_config_fingerprint,
            idempotency_key=payload.idempotency_key,
        )
        db.commit()
        state, events = get_company_terms_review(
            db,
            hotel_id=context.hotel_id,
            reservation_id=reservation_id,
        )
        return _company_terms_review_response(
            reservation_id=reservation_id,
            state=state,
            events=events,
        )
    except CompanyTermsReviewNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CompanyTermsReviewConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CompanyTermsReviewError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _reservation_status_label_es(status: ReservationStatusEnum) -> str:
    return {
        ReservationStatusEnum.PARTIAL_CHECK_IN: "llegadas parciales",
        ReservationStatusEnum.CHECKED_IN: "en curso",
        ReservationStatusEnum.CHECKED_OUT: "finalizada",
        ReservationStatusEnum.CANCELLED: "cancelada",
        ReservationStatusEnum.NO_SHOW: "no presentada",
    }.get(status, "en un estado que no admite cambios")


def _can_view_guest_documents(db: Session | None, context: AuthContext | None) -> bool:
    """Resolve the canonical guest-profile permission for reservation reads."""
    if db is None or context is None or context.user_id is None:
        return False
    return resolve(
        db,
        context.hotel_id,
        context.user_role,
        PERMISSION_GUEST_READ,
        user_id=context.user_id,
    )


def _to_read(
    r: Reservation,
    *,
    db: Session | None = None,
    context: AuthContext | None = None,
    can_view_guest_documents: bool | None = None,
    company_billing_deferred: bool | None = None,
) -> ReservationRead:
    result = ReservationRead.model_validate(r)
    if can_view_guest_documents is None:
        can_view_guest_documents = _can_view_guest_documents(db, context)
    if not can_view_guest_documents:
        # Names remain useful reservation context, but identity-document PII
        # is governed by guest:view (canonical guest:read), not reservation:read.
        for guest in (result.guest, *result.additional_guests):
            if guest is not None:
                guest.document_type = None
                guest.document_number = None
    room = getattr(r, "room", None)
    result.room_number = (
        room.room_number
        if room is not None and getattr(room, "hotel_id", None) == r.hotel_id
        else getattr(r, "room_number", None)
    )
    category = getattr(r, "category", None)
    result.category_name = (
        category.name
        if category is not None and getattr(category, "hotel_id", None) == r.hotel_id
        else getattr(r, "category_name", None)
    )
    result.balance_due = getattr(
        r,
        "balance_due",
        max(0, float(r.total_amount or 0) - float(r.amount_paid or 0)),
    )
    result.nights = getattr(r, "nights", (r.check_out_date - r.check_in_date).days)
    result.reserved_nights = int(getattr(r, "reserved_nights", result.nights) or result.nights)
    result.used_nights = getattr(r, "used_nights", None)
    is_deferred = company_billing_deferred
    if is_deferred is None:
        is_deferred = (
            reservation_has_deferred_company_billing(db, r, hotel_id=r.hotel_id)
            if db is not None
            else bool(r.company_id is not None and r.settlement_status in {"deferred", "settled"})
        )
    result.company_billing_deferred = bool(is_deferred)
    result.external_paid_balance_credit_applied = external_paid_balance_credit(r) > 0
    if result.company_billing_deferred:
        # These fields represent lodging or aggregate reservation money. A
        # deferred company invoices lodging outside the PMS, so returning
        # null is safer than exposing historical amounts or suggesting $0.
        for field in (
            "total_amount",
            "amount_paid",
            "external_paid_amount",
            "external_paid_currency",
            "deposit_amount",
            "subtotal_amount",
            "tax_amount",
            "fee_amount",
            "commission_amount",
            "net_amount",
            "quoted_amount_ars",
            "quoted_amount_usd",
            "balance_due",
        ):
            setattr(result, field, None)
        result.external_paid_reference = None
        result.external_paid_confirmed = False
        result.external_paid_balance_credit_applied = False
    return result


def _is_manager_context(context: AuthContext) -> bool:
    return context.operational_role in {"owner", "co_owner", "manager"}


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
    acceptable_permissions: tuple[str, ...] = (),
    detail: str = "No tenes permisos para esta accion",
) -> None:
    """Enforce payload-dependent actions before loading or mutating data."""
    if any(
        resolve(
            db,
            context.hotel_id,
            context.user_role,
            candidate_permission,
            user_id=context.user_id,
        )
        for candidate_permission in (permission_code, *acceptable_permissions)
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


def _trigger_reoptimization_bg(
    hotel_id: int,
    trigger_type: str = "new_reservation",
    origin_key: str | None = None,
) -> None:
    """Coalesce concurrent hotel triggers and preserve their event origin."""
    _coalesced_reoptimization_bg(
        hotel_id=hotel_id,
        trigger_type=trigger_type,
        origin_key=origin_key,
    )


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


def _authorize_company_reservation_management(
    request: Request,
    db: Session,
    context: AuthContext,
    reservation: Reservation,
) -> None:
    """Require company management for edits to a company booking.

    Reception's separate stay, guest-document and payment flows remain
    available; this guard applies to reservation/company mutation routes.
    """
    if reservation.company_id is not None:
        authorize_permission(request, db, context, PERMISSION_COMPANY_MANAGE)


def _reservation_room_capacity_category(
    db: Session,
    *,
    hotel_id: int,
    reservation: Reservation,
) -> RoomCategory | None:
    """Return the assigned room's physical category, falling back if unassigned."""
    category_id = reservation.category_id
    if reservation.room_id is not None:
        room = (
            db.query(Room)
            .filter(Room.id == reservation.room_id, Room.hotel_id == hotel_id)
            .first()
        )
        if room is None:
            return None
        category_id = room.category_id
    return (
        db.query(RoomCategory)
        .filter(RoomCategory.id == category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )


# Accept with and without trailing slash to avoid 405 when the FE omits it.
@router.post("/", response_model=ReservationRead, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=ReservationRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_new_reservation(
    data: ReservationCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CREATE)),
):
    if data.company_id is not None:
        authorize_permission(request, db, context, PERMISSION_COMPANY_MANAGE)
    manual_rate_scope = None
    if data.total_amount is not None:
        manual_rate_scope = authorize_manual_rate_scope(db, context)
        if not data.manual_rate_reason:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Indicá el motivo de la tarifa manual.",
            )
    elif data.manual_rate_reason is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El motivo solo corresponde cuando se ingresa una tarifa manual.",
        )
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
            manual_rate_scope=manual_rate_scope,
        )
        # create_reservation keeps the first-fit room as the transactional
        # fallback and persists a durable proposal request. Wake the worker for
        # every eligible booking, including assigned rooms, so reception can
        # review possible improvements without applying them automatically.
        should_reoptimize = (
            not reservation.is_wait_listed
            and reservation_overlaps_default_horizon(
                db,
                hotel_id=context.hotel_id,
                check_in_date=reservation.check_in_date,
                check_out_date=reservation.check_out_date,
            )
        )
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="reservations",
            record_id=reservation.id,
            action=AuditActionEnum.CREATE,
            actor_user_id=context.user_id,
            payload_after={
                **(audit_log_service.model_snapshot(reservation) or {}),
                "source": "reservations_api",
            },
        )
        db.commit()
        db.refresh(reservation)
        _project_reservation_graph(context.hotel_id, reservation)
        if should_reoptimize:
            background_tasks.add_task(
                _trigger_reoptimization_bg,
                hotel_id=context.hotel_id,
                origin_key=db.info.get("domain_event_origin_key"),
            )
        return _to_read(reservation, db=db, context=context)
    except ManualRatePolicyError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
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
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(
            PERMISSION_RESERVATION_CREATE,
            PERMISSION_RESERVATION_UPDATE,
            PERMISSION_RESERVATION_OTA_RECORD,
        )
    ),
):
    # An OTA-reported price is a separate capability from overriding the
    # automatic quote on a direct reservation. The dependency above gates the
    # OTA entry path; direct manual rates remain guarded by manual_rate.
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para crear nuevas reservas.",
        )
    if data.amount_paid is not None:
        # Any explicit edit (including reducing a previous OTA credit) changes
        # financial history, so require the separate manager-level capability
        # and MFA step-up when the account has MFA enabled.
        authorize_permission(request, db, context, PERMISSION_OTA_PAYMENT_CONFIRM)
    existing = lock_query(
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == context.hotel_id,
            Reservation.source_provider_code == data.channel.strip().lower(),
            Reservation.external_id == data.external_id.strip(),
        )
        # Payment processing locks this same tenant-scoped reservation row.
        # Refresh and acquire that lock before checking whether a receptionist
        # may change paid dates/occupancy, so a concurrent payment cannot land
        # between the authorization decision and the mutation.
        .populate_existing(),
        Reservation,
    )
    existing = existing.first()
    if existing is not None:
        if data.room_id is not None and data.room_id != existing.room_id:
            _ensure_action_permission(
                db,
                context,
                PERMISSION_RESERVATION_MOVE,
                acceptable_permissions=RESERVATION_MOVE_TIER_PERMISSIONS[1:],
            )
        dates_changed = (
            data.check_in_date != existing.check_in_date
            or data.check_out_date != existing.check_out_date
        )
        occupancy_changed = (
            data.num_adults != existing.num_adults
            or data.num_children != existing.num_children
        )
        if (
            (dates_changed or occupancy_changed)
            and reservation_has_payment_or_deposit(db, hotel_id=context.hotel_id, reservation=existing)
            and not _is_manager_context(context)
        ):
            raise HTTPException(
                status_code=403,
                detail="Modificar fechas u ocupación de una reserva con pagos requiere gerente, dueño o codueño.",
            )
    before = audit_log_service.model_snapshot(existing)
    try:
        reservation = create_or_update_manual_ota_reservation(
            db,
            hotel_id=context.hotel_id,
            data=data,
            actor_user_id=context.user_id,
        )
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="reservations",
            record_id=reservation.id,
            action=AuditActionEnum.UPDATE if before is not None else AuditActionEnum.CREATE,
            actor_user_id=context.user_id,
            payload_before=before,
            payload_after={
                **(audit_log_service.model_snapshot(reservation) or {}),
                "source": "manual_ota",
            },
        )
        db.commit()
        try:
            from app.services.payment_link_service import process_payment_link_revocations

            process_payment_link_revocations(db, context.hotel_id, reservation_id=reservation.id)
            db.commit()
        except Exception as exc:  # noqa: BLE001 - manual OTA state change is already durable
            db.rollback()
            logger.warning(
                "payment_link.revocation_attempt_unavailable hotel_id=%s reservation_id=%s error_type=%s",
                context.hotel_id,
                reservation.id,
                type(exc).__name__,
            )
        db.refresh(reservation)
        _project_reservation_graph(context.hotel_id, reservation)
        if (
            before is None
            and not reservation.is_wait_listed
            and reservation_overlaps_default_horizon(
                db,
                hotel_id=context.hotel_id,
                check_in_date=reservation.check_in_date,
                check_out_date=reservation.check_out_date,
            )
        ):
            background_tasks.add_task(
                _trigger_reoptimization_bg,
                hotel_id=context.hotel_id,
                trigger_type="new_reservation",
                origin_key=db.info.get("domain_event_origin_key"),
            )
        return _to_read(reservation, db=db, context=context)
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
    upcoming_only: bool = False,
    company_id: int | None = Query(None, gt=0),
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
        upcoming_only=upcoming_only,
        company_id=company_id,
        context=context,
    )
    try:
        deferred_ids = deferred_company_reservation_ids(
            db,
            hotel_id=context.hotel_id,
            reservations=reservations,
        )
        can_view_guest_documents = _can_view_guest_documents(db, context)
        return [
            _to_read(
                r,
                db=db,
                can_view_guest_documents=can_view_guest_documents,
                company_billing_deferred=r.id in deferred_ids,
            )
            for r in reservations
        ]
    except Exception as exc:
        logger.error("Reservation serialization failed for hotel_id=%s error_type=%s", context.hotel_id, type(exc).__name__)
        raise HTTPException(status_code=500, detail="No se pudieron serializar las reservas") from exc


@router.get(
    "/export.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
def export_reservations_csv(
    start_date: date = Query(..., description="Inclusive first stay date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Inclusive last stay date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_RESERVATION_READ, PERMISSION_RESERVATION_EXPORT)
    ),
):
    """Export a bounded, tenant-scoped reservation CSV without guest documents or contacts."""
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="El período de exportación es inválido.")
    inclusive_days = (end_date - start_date).days + 1
    if inclusive_days > _RESERVATION_CSV_MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"El período máximo de exportación es de {_RESERVATION_CSV_MAX_RANGE_DAYS} días.",
        )

    # Use scalar columns and tenant-constrained joins so guest documents and
    # contact fields are never selected for this export.
    query = (
        db.query(
            Reservation.confirmation_code.label("confirmation_code"),
            Guest.first_name.label("guest_first_name"),
            Guest.last_name.label("guest_last_name"),
            Reservation.status.label("reservation_status"),
            Reservation.check_in_date.label("check_in_date"),
            Reservation.check_out_date.label("check_out_date"),
            Reservation.num_adults.label("num_adults"),
            Reservation.num_children.label("num_children"),
            Reservation.total_amount.label("total_amount"),
            Reservation.currency_code.label("currency_code"),
            Reservation.source.label("source"),
            Room.room_number.label("room_number"),
            RoomCategory.name.label("category_name"),
        )
        .outerjoin(
            Guest,
            and_(Guest.id == Reservation.guest_id, Guest.hotel_id == context.hotel_id),
        )
        .outerjoin(
            Room,
            and_(Room.id == Reservation.room_id, Room.hotel_id == context.hotel_id),
        )
        .outerjoin(
            RoomCategory,
            and_(RoomCategory.id == Reservation.category_id, RoomCategory.hotel_id == context.hotel_id),
        )
        .filter(
            Reservation.hotel_id == context.hotel_id,
            Reservation.deleted_at.is_(None),
            Reservation.check_in_date <= end_date,
            Reservation.check_out_date > start_date,
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.check_out_date.asc(), Reservation.id.asc())
        .limit(_RESERVATION_CSV_MAX_ROWS + 1)
    )
    reservations = query.all()
    if len(reservations) > _RESERVATION_CSV_MAX_ROWS:
        raise HTTPException(
            status_code=413,
            detail="El resultado supera el máximo de reservas exportables; acotá el período.",
        )

    fieldnames = [
        "codigo_reserva",
        "huesped",
        "estado",
        "check_in",
        "check_out",
        "noches",
        "habitacion",
        "categoria",
        "adultos",
        "menores",
        "total",
        "moneda",
        "origen",
    ]
    output = StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        delimiter=";",
        lineterminator="\r\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in reservations:
        status_value = getattr(row.reservation_status, "value", row.reservation_status) or ""
        source_value = getattr(row.source, "value", row.source) or ""
        total_amount = Decimal(str(row.total_amount or 0)).quantize(Decimal("0.01"))
        safe_row = spreadsheet_safe_row(
            {
                "codigo_reserva": row.confirmation_code or "",
                "huesped": f"{row.guest_first_name or ''} {row.guest_last_name or ''}".strip(),
                "estado": str(status_value),
                "check_in": row.check_in_date.isoformat(),
                "check_out": row.check_out_date.isoformat(),
                "noches": (row.check_out_date - row.check_in_date).days,
                "habitacion": row.room_number or "",
                "categoria": row.category_name or "",
                "adultos": row.num_adults,
                "menores": row.num_children,
                "total": format(total_amount, ".2f"),
                "moneda": row.currency_code or "",
                "origen": str(source_value),
            }
        )
        writer.writerow(safe_row)

    db.add(
        SecurityAuditLog(
            hotel_id=context.hotel_id,
            user_id=context.user_id,
            action="reservation.csv_exported",
            resource_type="reservation_export",
            resource_id=None,
            details=json.dumps(
                {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "row_count": len(reservations),
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    )
    db.commit()

    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": (
                f'attachment; filename="reservas-{start_date.isoformat()}-{end_date.isoformat()}.csv"'
            )
        },
    )


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
            detail="No se pudieron calcular las acciones pendientes. Intentá de nuevo.",
        ) from exc


@router.get(
    "/cancellation-reviews/pending",
    response_model=list[CancellationReviewRead],
)
def list_pending_cancellation_reviews_endpoint(
    limit: int = Query(default=100, ge=1, le=250),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CANCEL_PENALTY_APPROVE)),
):
    """Return the current hotel's cancellation decisions awaiting review."""
    rows = list_pending_cancellation_reviews(db, hotel_id=context.hotel_id, limit=limit)
    can_manage_companies = resolve(
        db,
        context.hotel_id,
        context.user_role,
        PERMISSION_COMPANY_MANAGE,
        user_id=context.user_id,
    )
    return [
        review_read_payload(review, reservation)
        for review, reservation in rows
        if reservation.company_id is None or can_manage_companies
    ]


@router.post(
    "/cancellation-reviews/{review_id}/decision",
    response_model=CancellationReviewResolutionResponse,
)
def decide_cancellation_review(
    review_id: int,
    payload: CancellationReviewDecisionRequest,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CANCEL_PENALTY_APPROVE)),
):
    review = (
        db.query(ReservationCancellationReview)
        .filter(
            ReservationCancellationReview.id == review_id,
            ReservationCancellationReview.hotel_id == context.hotel_id,
        )
        .first()
    )
    if review is None:
        raise HTTPException(status_code=404, detail="No se encontró la revisión de cancelación.")
    reservation = get_reservation_by_id(db, review.reservation_id, context.hotel_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")
    _authorize_company_reservation_management(request, db, context, reservation)
    try:
        resolved_review, resolved_reservation = resolve_cancellation_review(
            db,
            hotel_id=context.hotel_id,
            review_id=review_id,
            user_id=context.user_id,
            decision=payload.decision,
            reason=payload.reason,
        )
        db.commit()
        if payload.decision == "approve":
            process_payment_link_revocations_after_commit(
                db,
                hotel_id=context.hotel_id,
                reservation_id=resolved_reservation.id,
            )
        db.refresh(resolved_review)
        db.refresh(resolved_reservation)
        return CancellationReviewResolutionResponse(
            cancellation_review=review_read_payload(resolved_review, resolved_reservation),
            reservation=_to_read(resolved_reservation, db=db, context=context),
        )
    except CancellationReviewNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail="No se encontró la revisión de cancelación.") from exc
    except CancellationReviewConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ReservationError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.get("/occupancy-grid", response_model=OccupancyGridResponse)
def occupancy_grid(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_all_permissions(PERMISSION_ROOM_READ, PERMISSION_OCCUPANCY_VIEW)),
):
    """B2: planilla de ocupación — rooms x days grid data for one hotel."""
    if date_to <= date_from:
        raise HTTPException(status_code=422, detail="La fecha de salida debe ser posterior a la fecha de llegada.")
    if (date_to - date_from).days > 92:
        raise HTTPException(status_code=422, detail="El período no puede superar los 92 días.")
    grid = get_cached_occupancy_grid_payload(
        hotel_id=context.hotel_id,
        date_from=date_from,
        date_to=date_to,
        role=context.operational_role,
        producer=lambda: get_occupancy_grid(
            db,
            hotel_id=context.hotel_id,
            date_from=date_from,
            date_to=date_to,
            context=context,
        ),
    )
    if context.operational_role != "housekeeping":
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
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id, for_update=True)
    if not reservation:
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")
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
    return _to_read(reservation, db=db, context=context)


@router.get("/{reservation_id}", response_model=ReservationRead)
def get_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")
    return _to_read(reservation, db=db, context=context)


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
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id, for_update=True)
    if not reservation:
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")
    if reservation.status not in {
        ReservationStatusEnum.PENDING,
        ReservationStatusEnum.DEPOSIT_PAID,
        ReservationStatusEnum.FULLY_PAID,
        ReservationStatusEnum.PRE_CHECK_IN,
        ReservationStatusEnum.PARTIAL_CHECK_IN,
        ReservationStatusEnum.CHECKED_IN,
    }:
        raise HTTPException(status_code=409, detail="No se pueden agregar perfiles en el estado actual de la reserva.")

    category = _reservation_room_capacity_category(
        db,
        hotel_id=context.hotel_id,
        reservation=reservation,
    )
    if not category:
        raise HTTPException(status_code=400, detail="No se encontró la categoría de habitación para la reserva.")

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
            if document_number:
                existing_guests_by_document[document_number] = guest
        
        # Link if not linked
        if guest not in reservation.additional_guests:
            reservation.additional_guests.append(guest)

    # Flush once for the whole guest batch. Per-guest flushes add a database
    # round trip for every new companion, even though relationship inserts can
    # be persisted together by the unit of work.
    db.flush()
    response = _to_read(reservation, db=db, context=context)
    # Build the response while ORM relationships remain loaded. Committing
    # expires the instance by default; refreshing it here re-queries the full
    # reservation graph after a mutation whose result is already in memory.
    db.commit()
    return response


@router.post("/{reservation_id}/cancel", response_model=ReservationCancellationResponse)
def cancel_reservation(
    reservation_id: int,
    request: Request,
    manager_pin: str | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
    temporary_grant_token: str | None = Header(default=None, alias="X-Temporary-Action-Grant"),
):
    """Cancel a reservation. Post check-in cancellations are not allowed."""
    if not context.is_verified:
        raise HTTPException(status_code=403, detail="Verifica tu email para usar el sistema")
    if context.user_id is None:
        raise HTTPException(status_code=401, detail="Autenticacion requerida")

    permissions = context.permissions or set()
    permissions.add(PERMISSION_RESERVATION_CANCEL)
    context.permissions = permissions
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
    reservation_query = (
        db.query(Reservation)
        .filter(
            Reservation.id == reservation_id,
            Reservation.hotel_id == context.hotel_id,
            Reservation.deleted_at.is_(None),
        )
        .populate_existing()
    )
    r = lock_query(reservation_query, Reservation).first()
    if not r:
        if not permission_allowed:
            raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")

    _authorize_company_reservation_management(request, db, context, r)

    if r.status in (
        ReservationStatusEnum.PARTIAL_CHECK_IN,
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CHECKED_OUT,
    ):
        if not permission_allowed:
            raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")
        raise HTTPException(
            status_code=400,
            detail="No se puede cancelar una reserva que ya tiene check-in o check-out.",
        )

    if r.status == ReservationStatusEnum.CANCELLED:
        if not permission_allowed:
            raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")
        raise HTTPException(status_code=400, detail="La reserva ya está cancelada.")

    requires_paid_cancel_approval = has_payment_history_for_cancellation(db, context.hotel_id, r)
    if requires_paid_cancel_approval:
        authorize_permission(request, db, context, PERMISSION_RESERVATION_CANCEL_PAID)
        # Consuming the one-use step-up ticket commits its own transaction and
        # releases this row lock. Reacquire the row and revalidate its lifecycle
        # state before performing the protected mutation.
        reservation_query = (
            db.query(Reservation)
            .filter(
                Reservation.id == reservation_id,
                Reservation.hotel_id == context.hotel_id,
                Reservation.deleted_at.is_(None),
            )
            .populate_existing()
        )
        r = lock_query(reservation_query, Reservation).first()
        if not r:
            raise HTTPException(status_code=404, detail="No se encontró la reserva.")
        if r.status in (
            ReservationStatusEnum.PARTIAL_CHECK_IN,
            ReservationStatusEnum.CHECKED_IN,
            ReservationStatusEnum.CHECKED_OUT,
            ReservationStatusEnum.CANCELLED,
        ):
            raise HTTPException(
                status_code=409,
                detail="La reserva cambió mientras se verificaba la autorización. Recargá e intentá de nuevo.",
            )

    if not permission_allowed:
        try:
            grant_consumed = consume_grant_for_action(
                db,
                temporary_grant_token,
                TemporaryGrantActor(user_id=context.user_id, hotel_id=context.hotel_id),
                permission_code=PERMISSION_RESERVATION_CANCEL,
                resource_type="reservation",
                resource_id=r.id,
            )
        except TemporaryGrantError:
            db.rollback()
            raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")
        except Exception:
            db.rollback()
            raise
        if not grant_consumed:
            # The consume path may have flushed expiry transitions. No action
            # was authorized or mutated, so persist those transitions before
            # returning the deny response.
            db.commit()
            raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")

    try:
        pending_review = get_pending_cancellation_review(
            db,
            hotel_id=context.hotel_id,
            reservation_id=r.id,
            lock=True,
        )
        preparation = None
        if pending_review is None:
            try:
                preparation = prepare_cancellation_request(r, config)
            except CancellationConfigurationRequired as exc:
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": exc.reason_code,
                        "message": "Configurá el horario de check-in y la zona horaria del hotel antes de evaluar la cancelación.",
                    },
                ) from exc
        result = request_reservation_cancellation(
            db,
            r,
            user_id=context.user_id,
            source="reservations_api",
            preparation=preparation,
        )
        db.commit()
        if result.outcome == "cancelled":
            process_payment_link_revocations_after_commit(
                db,
                hotel_id=context.hotel_id,
                reservation_id=r.id,
            )
        db.refresh(r)
        return ReservationCancellationResponse(
            **_to_read(r, db=db, context=context).model_dump(),
            cancellation_outcome=result.outcome,
            cancellation_review=(
                review_read_payload(result.review, r) if result.review is not None else None
            ),
        )
    except ReservationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except CancellationReviewConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TemporaryGrantError:
        db.rollback()
        raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")
    except Exception:
        db.rollback()
        raise


@router.post(
    "/{reservation_id}/charges",
    response_model=ReservationBillingAdjustmentSummaryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_reservation_charge(
    reservation_id: int,
    payload: ReservationChargeCreate,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CHARGE)),
):
    """Record a human-readable consumption or extra charge for an active stay."""
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")
    _authorize_company_reservation_management(request, db, context, reservation)
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
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")
    if reservation_has_payment_or_deposit(db, hotel_id=context.hotel_id, reservation=r):
        raise HTTPException(
            status_code=409,
            detail="Una reserva de OTA con pagos registrados no se puede liberar como sin garantía.",
        )
    before = audit_log_service.model_snapshot(r)
    try:
        release_no_guarantee(
            db,
            reservation=r,
            actor_user_id=context.user_id,
            reason=reason,
        )
        db.commit()
        try:
            from app.services.payment_link_service import process_payment_link_revocations

            process_payment_link_revocations(db, context.hotel_id, reservation_id=r.id)
            db.commit()
        except Exception as exc:  # noqa: BLE001 - release is already durable
            db.rollback()
            logger.warning(
                "payment_link.revocation_attempt_unavailable hotel_id=%s reservation_id=%s error_type=%s",
                context.hotel_id,
                r.id,
                type(exc).__name__,
            )
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
        return _to_read(r, db=db, context=context)
    except OTAManualReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{reservation_id}/noshow", response_model=ReservationRead)
def mark_no_show(
    reservation_id: int,
    payload: ReservationNoShowRequest,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CANCEL)),
):
    """Mark a reservation as no-show without automatic charge."""
    r = get_reservation_by_id(db, reservation_id, context.hotel_id, for_update=True)
    if not r:
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")
    _authorize_company_reservation_management(request, db, context, r)
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
        return _to_read(r, db=db, context=context)
    except ReservationError as e:
        db.rollback()
        if isinstance(e, ReservationVersionConflict):
            raise HTTPException(status_code=409, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{reservation_id}/date-change", response_model=ReservationDateChangeResponse)
def change_dates(
    reservation_id: int,
    payload: ReservationDateChangeRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_UPDATE)),
):
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para gestionar reservas.",
        )
    if payload.room_id is not None:
        # change_reservation_dates/create_reservation rejects a room from a
        # different category, so this implicit move is necessarily tier 1.
        # A wider tier still implies tier 1 for an explicitly customized role.
        _ensure_action_permission(
            db,
            context,
            PERMISSION_RESERVATION_MOVE,
            acceptable_permissions=RESERVATION_MOVE_TIER_PERMISSIONS[1:],
        )
    r = get_reservation_by_id(db, reservation_id, context.hotel_id, for_update=True)
    if not r:
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")
    _authorize_company_reservation_management(request, db, context, r)
    before = audit_log_service.model_snapshot(r)
    previous_allocation_interval = (r.check_in_date, r.check_out_date)
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
        if any(
            reservation_overlaps_default_horizon(
                db,
                hotel_id=context.hotel_id,
                check_in_date=check_in,
                check_out_date=check_out,
            )
            for check_in, check_out in (
                previous_allocation_interval,
                (result.reservation.check_in_date, result.reservation.check_out_date),
            )
        ):
            background_tasks.add_task(
                _trigger_reoptimization_bg,
                hotel_id=context.hotel_id,
                trigger_type="reservation_date_change",
                origin_key=db.info.get("domain_event_origin_key"),
            )
        return ReservationDateChangeResponse(
            original_reservation=_to_read(result.original_reservation, db=db, context=context),
            reservation=_to_read(result.reservation, db=db, context=context),
            recreated=result.recreated,
            status_transitioned=result.status_transitioned,
        )
    except ReservationVersionConflict as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ReservationOperationsError as e:
        db.rollback()
        status_code = 403 if "requiere gerente" in str(e) else 400
        raise HTTPException(status_code=status_code, detail=str(e))


@router.patch("/{reservation_id}", response_model=ReservationRead)
def modify_reservation(
    reservation_id: int,
    data: ReservationUpdate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_UPDATE)),
):
    """Modify reservation details with optimistic concurrency protection.

    A direct individual reservation without payment history may receive a
    manual total correction under its bounded or unbounded manual-rate scope.
    Corrections to reservations with payment history retain the stricter
    ``reservation:paid_total_adjust`` policy and never rewrite transactions.
    """
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para gestionar reservas.",
        )
    r = get_reservation_by_id(db, reservation_id, context.hotel_id, for_update=True)
    if not r:
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")
    authorization = ReservationUpdateAuthorization(
        company_management=lambda: _authorize_company_reservation_management(
            request,
            db,
            context,
            r,
        ),
        paid_total_adjustment=lambda: authorize_permission(
            request,
            db,
            context,
            PERMISSION_RESERVATION_PAID_TOTAL_ADJUST,
        ),
        manual_rate_scope=lambda: authorize_manual_rate_scope(db, context),
        # update_reservation_fields rejects cross-category rooms, so this
        # legacy edit path only supports a same-category (tier 1) move.
        room_move=lambda: _ensure_action_permission(
            db,
            context,
            PERMISSION_RESERVATION_MOVE,
            acceptable_permissions=RESERVATION_MOVE_TIER_PERMISSIONS[1:],
        ),
    )
    try:
        prepared = prepare_reservation_update(
            db,
            r,
            data,
            context.hotel_id,
            actor_is_manager=_is_manager_context(context),
            authorization=authorization,
        )
    except ReservationUpdatePreparationError as exc:
        if exc.code == "deferred_company_billing":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.detail) from exc
        if exc.code == "manual_rate_target":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.detail) from exc
        if exc.code == "paid_dates_require_manager":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.detail) from exc
        if exc.code == "status_restricted":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No se puede modificar una reserva en estado «"
                    f"{_reservation_status_label_es(r.status)}»."
                ),
            ) from exc
        if exc.code == "client_version_required":
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail=exc.detail,
            ) from exc
        raise
    except ConfirmedReservationPriceLocked as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ReservationVersionConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if prepared.update_data is None:
        return _to_read(r, db=db, context=context)

    update_plan = prepared.plan
    update_data = prepared.update_data
    previous_allocation_interval = prepared.previous_allocation_interval
    mobility_restriction_changed = update_plan.mobility_restriction_changed
    try:
        apply_reservation_update(
            db,
            r,
            update_data,
            context.hotel_id,
            actor_user_id=context.user_id,
            actor_role=context.user_role,
            total_adjustment_kind=prepared.total_adjustment_kind,
            manual_rate_scope=prepared.manual_rate_scope,
            confirmed_price_change_review_required=prepared.confirmed_price_change_review_required,
        )
        if (
            update_plan.dates_changed or update_plan.room_changed or mobility_restriction_changed
        ) and any(
            reservation_overlaps_default_horizon(
                db,
                hotel_id=context.hotel_id,
                check_in_date=check_in,
                check_out_date=check_out,
            )
            for check_in, check_out in (
                previous_allocation_interval,
                (r.check_in_date, r.check_out_date),
            )
        ):
            background_tasks.add_task(
                _trigger_reoptimization_bg,
                hotel_id=context.hotel_id,
                trigger_type="reservation_update",
                origin_key=db.info.get("domain_event_origin_key"),
            )
        return _to_read(r, db=db, context=context)
    except ConfirmedReservationPriceLocked as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ManualRatePolicyError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except ReservationError as e:
        db.rollback()
        if isinstance(e, ReservationVersionConflict):
            raise HTTPException(status_code=409, detail=str(e)) from e
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
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_UPDATE)),
):
    """Extend a guest's stay to a new checkout date."""
    r = get_reservation_by_id(db, reservation_id, context.hotel_id, for_update=True)
    if not r:
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")

    if r.company_id is not None:
        require_all_permissions(PERMISSION_COMPANY_MANAGE)(request, db, context)

    company_uses_deferred_settlement = False
    if r.company_id is not None:
        company = (
            db.query(Company)
            .filter(Company.hotel_id == context.hotel_id, Company.id == r.company_id)
            .with_for_update()
            .one_or_none()
        )
        company_uses_deferred_settlement = bool(company and company.payment_deferred)
    is_deferred_company_reservation = (
        r.settlement_status == "deferred" or company_uses_deferred_settlement
    )

    if payload.payment_action == "company_account" and r.company_id is None:
        require_all_permissions(PERMISSION_COMPANY_MANAGE)(request, db, context)
    elif payload.payment_action not in {"company_account", "pending_balance"}:
        # Preserve the dependency's all-or-nothing permission and step-up
        # handling for every action that creates or requests a payment.
        require_all_permissions(
            PERMISSION_RESERVATION_CHARGE,
            PERMISSION_CASH_OPERATE,
        )(request, db, context)

    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para gestionar reservas.",
        )
    if payload.immediate_payment and payload.immediate_payment.collected_before:
        authorize_permission(request, db, context, PERMISSION_CASH_RECORD_PRIOR_RECEIPT)
        if (
            payload.immediate_payment.collected_on is not None
            and payload.immediate_payment.collected_on > hotel_today(db, context.hotel_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La fecha del cobro previo no puede ser futura.",
            )
    before = audit_log_service.model_snapshot(r)
    previous_allocation_interval = (r.check_in_date, r.check_out_date)
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
            can_manage_company_reservations=resolve(
                db,
                context.hotel_id,
                context.user_role,
                PERMISSION_COMPANY_MANAGE,
                user_id=context.user_id,
            ),
            confirmed_impact_fingerprint=payload.confirmed_impact_fingerprint,
        )
        if not result.success:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "No se pudo resolver el conflicto de extensión de estadía.",
                    "conflicts": result.conflicts or [],
                    **({"impact_plan": result.impact_plan} if result.impact_plan else {}),
                },
            )
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
        db.commit()
        db.refresh(r)
        response = ReservationExtensionResponse(
            reservation=_to_read(r, db=db, context=context),
            extension_amount=result.extension_amount,
            transaction=result.transaction,
            payment_link=result.payment_link,
        )
        if any(
            reservation_overlaps_default_horizon(
                db,
                hotel_id=context.hotel_id,
                check_in_date=check_in,
                check_out_date=check_out,
            )
            for check_in, check_out in (
                previous_allocation_interval,
                (r.check_in_date, r.check_out_date),
            )
        ):
            background_tasks.add_task(
                _trigger_reoptimization_bg,
                hotel_id=context.hotel_id,
                trigger_type="reservation_date_change",
                origin_key=db.info.get("domain_event_origin_key"),
            )
        return response
    except ReservationExtensionImpactConfirmationError as e:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": e.code,
                "message": str(e),
                **({"impact_plan": e.impact_plan} if e.impact_plan else {}),
            },
        ) from e
    except ReservationVersionConflict as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    except RoomMovementGroupError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ReservationOperationsError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{reservation_id}/extend-preview",
    response_model=ReservationExtensionPreviewResponse,
    response_model_exclude_none=True,
)
def preview_stay_extension(
    reservation_id: int,
    request: Request,
    new_checkout_date: date = Query(...),
    payment_action: Literal["individual", "company_account"] = "individual",
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_UPDATE)),
):
    """Return a server-priced, read-only extension quote for direct stays."""
    # A preview exposes the amount to be collected. Reservation readers may
    # see financial details, but cash movement permissions are not needed
    # until an extension actually records or requests payment.
    require_all_permissions(PERMISSION_RESERVATION_READ)(request, db, context)
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")
    if payment_action == "company_account":
        require_all_permissions(PERMISSION_COMPANY_MANAGE)(request, db, context)
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para gestionar reservas.",
        )
    try:
        amount = preview_reservation_stay_extension(
            db,
            reservation=reservation,
            hotel_id=context.hotel_id,
            new_checkout_date=new_checkout_date,
            payment_action=payment_action,
        )
        impact_plan = plan_reservation_extension_impact(
            db,
            reservation=reservation,
            hotel_id=context.hotel_id,
            new_checkout_date=new_checkout_date,
            can_manage_company_reservations=resolve(
                db,
                context.hotel_id,
                context.user_role,
                PERMISSION_COMPANY_MANAGE,
                user_id=context.user_id,
            ),
        )
    except ReservationOperationsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReservationExtensionPreviewResponse(
        reservation_id=reservation.id,
        current_checkout_date=reservation.check_out_date,
        new_checkout_date=new_checkout_date,
        client_version=reservation.version or 0,
        extension_amount=amount,
        currency_code=reservation.currency_code,
        impact_plan=impact_plan,
    )


@router.put("/{reservation_id}/extension-request", response_model=ReservationRead)
def update_company_extension_request(
    reservation_id: int,
    payload: CompanyExtensionRequestUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_UPDATE)),
):
    """Record a pending company extension without changing the stay or terms."""
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para gestionar reservas.",
        )
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id, for_update=True)
    if reservation is None:
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")
    before = audit_log_service.model_snapshot(reservation)
    try:
        set_company_extension_request(
            db,
            reservation=reservation,
            hotel_id=context.hotel_id,
            pending=payload.pending,
            note=payload.note,
            client_version=payload.client_version,
            actor_user_id=context.user_id,
        )
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
        db.commit()
        db.refresh(reservation)
        return _to_read(reservation, db=db, context=context)
    except ReservationVersionConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ReservationOperationsError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{reservation_id}/room-move", response_model=RoomMoveResponse)
def room_move(
    reservation_id: int,
    payload: RoomMoveRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_any_permission(
            PERMISSION_RESERVATION_MOVE,
            PERMISSION_RESERVATION_MOVE_CATEGORY,
            PERMISSION_RESERVATION_MOVE_CAPACITY,
        )
    ),
):
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para gestionar reservas.",
        )
    try:
        manual_reason_code = ManualRoomMoveReasonCodeEnum(payload.reason_code)
    except ValueError as exc:
        allowed = ", ".join(reason.value for reason in ManualRoomMoveReasonCodeEnum)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"reason_code debe ser uno de: {allowed}",
        ) from exc
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id, for_update=True)
    if not reservation:
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")
    before = audit_log_service.model_snapshot(reservation)
    try:
        result = move_reservation_room(
            db,
            reservation=reservation,
            to_room_id=payload.to_room_id,
            hotel_id=context.hotel_id,
            client_version=payload.client_version,
            moved_by_user_id=context.user_id,
            actor_role=context.user_role,
            reason_code=manual_reason_code.value,
            notes=payload.notes,
            price_action=payload.price_action,
            origin_room_disposition=payload.origin_room_disposition.value if payload.origin_room_disposition else None,
            origin_room_disposition_note=payload.origin_room_disposition_note,
        )
        event = result.event
        audit_log_service.queue_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="reservations",
            record_id=reservation.id,
            action=AuditActionEnum.UPDATE,
            actor_user_id=context.user_id,
            payload_before=before,
            payload_after=audit_log_service.model_snapshot(reservation),
        )
        db.commit()
        db.refresh(reservation)
        _project_reservation_graph(context.hotel_id, reservation)
        project_room_movement(
            context.hotel_id,
            reservation.id,
            event.from_room_id,
            event.to_room_id,
            event.movement_group_id or event.id,
        )
        if reservation_overlaps_default_horizon(
            db,
            hotel_id=context.hotel_id,
            check_in_date=reservation.check_in_date,
            check_out_date=reservation.check_out_date,
        ):
            background_tasks.add_task(
                _trigger_reoptimization_bg,
                hotel_id=context.hotel_id,
                trigger_type="reservation_room_move",
                origin_key=db.info.get("domain_event_origin_key"),
            )
        return RoomMoveResponse(
            reservation=_to_read(reservation, db=db, context=context),
            category_changed=result.category_changed,
            price_action=result.price_action,
            previous_total_amount=result.previous_total_amount,
            quoted_total_amount=result.quoted_total_amount,
            amount_delta=result.amount_delta,
            currency_code=result.currency_code,
            origin_room_disposition=result.origin_room_disposition,
            origin_room_disposition_note=result.origin_room_disposition_note,
            origin_room_status_before=result.origin_room_status_before,
            origin_room_status_after=result.origin_room_status_after,
        )
    except ReservationVersionConflict as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    except RoomMovePermissionError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except RoomMovementGroupError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ReservationOperationsError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{reservation_id}/rebook-direct", response_model=OTARebookToDirectResponse)
def rebook_ota_to_direct(
    reservation_id: int,
    payload: OTARebookToDirectRequest,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_RESERVATION_UPDATE, PERMISSION_RESERVATION_CREATE)
    ),
):
    if payload.discount_pct > 0:
        authorize_permission(request, db, context, PERMISSION_RESERVATION_RATE_ADJUST)
    if payload.total_override is not None:
        _ensure_manual_rate_permission(db, context)
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")
    if reservation_has_payment_or_deposit(db, hotel_id=context.hotel_id, reservation=reservation):
        raise HTTPException(
            status_code=409,
            detail=(
                "This reservation has payment history. Rebooking does not transfer or reconcile payments; "
                "resolve the financial balance before converting it to a direct booking."
            ),
        )
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
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    if payload.discount_pct > 0:
        authorize_permission(request, db, context, PERMISSION_RESERVATION_RATE_ADJUST)
    if payload.total_override is not None:
        _ensure_manual_rate_permission(db, context)
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="No se encontró la reserva.")
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
