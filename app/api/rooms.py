"""
FastAPI routes for Room management + Housekeeping.
"""
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.audit_log import AuditActionEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.pricing import CategoryPricing
from app.schemas.room import (
    RoomCreate,
    RoomHousekeepingRead,
    RoomRead,
    RoomCategoryCreate,
    RoomCategoryOperationalRead,
    RoomCategoryRead,
    RoomCategoryUpdate,
    CategoryPricingSchema,
    CategoryPricingRead,
    RoomUpdate,
    RoomStatusUpdateResponse,
)
from app.services.reservation_service import ReservationError, find_available_rooms
from app.services.pricing_service import get_price_for_date
from app.dependencies.auth import AuthContext, require_permission
from app.services.allocation_runtime_service import run_persisted_allocation
from app.services.read_model_cache import get_cached_availability_payload, invalidate_hotel_operational_caches
from app.services.subscription_service import ensure_room_within_limit
from app.services.analytics_service import record_hotel_audit_event
from app.services import audit_log_service
from app.services.timeseries_projection import project_room_state_event
from app.services.distributed_lock import DistributedLockBusy, DistributedLockUnavailable
from app.services.permission_service import (
    PERMISSION_HOTEL_SETTINGS_UPDATE,
    PERMISSION_RATES_READ,
    PERMISSION_RATES_UPDATE,
    PERMISSION_RESERVATION_MOVE,
    PERMISSION_ROOM_READ,
    PERMISSION_ROOM_STATUS_UPDATE,
)

router = APIRouter(prefix="/api/rooms", tags=["Rooms"])


def _require_manager_room_lane(context: AuthContext) -> None:
    """Keep broad room mutations outside the housekeeping-only lane.

    The canonical dependency is evaluated first, so per-user revocations still
    fail closed. This secondary product lane prevents the housekeeping
    cleaning permission from authorizing inventory/configuration mutations.
    """

    if context.user_role not in {"owner", "co_owner", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenes permisos para esta accion")


class RoomStatusUpdate(BaseModel):
    status: RoomStatusEnum
    notes: Optional[str] = None


def _serialize_reallocation_result(result, *, include_message: bool = False) -> dict:
    payload = {
        "run_id": result.run.id,
        "status": result.run.status.value if hasattr(result.run.status, "value") else str(result.run.status),
        "assignments": len(result.solver_result.assignments),
        "moved": len(result.solver_result.moved_reservations),
        "moved_ids": result.solver_result.moved_reservations,
        "unassigned": len(result.solver_result.unassigned_reservations),
        "unassigned_ids": result.solver_result.unassigned_reservations,
        "objective_value": result.solver_result.objective_value,
        "error": result.solver_result.error,
    }
    if include_message:
        payload["message"] = "Reallocation executed"
    return payload


@router.post("/categories", response_model=RoomCategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    data: RoomCategoryCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_UPDATE)),
):
    category = RoomCategory(**data.model_dump(), hotel_id=context.hotel_id)
    db.add(category)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Ya existe una categoría con ese código en este hotel",
        )
    record_hotel_audit_event(
        db,
        hotel_id=context.hotel_id,
        user_id=context.user_id or 0,
        action_code="analytics.variable_cost.updated",
        entity_type="room_category",
        entity_id=category.id,
        after={"room_category_id": category.id, "variable_cost_per_night": float(category.variable_cost_per_night or 0)},
    )
    db.commit()
    db.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=RoomCategoryRead)
def update_category(
    category_id: int,
    data: RoomCategoryUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_UPDATE)),
):
    category = db.query(RoomCategory).filter(RoomCategory.id == category_id, RoomCategory.hotel_id == context.hotel_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    before_variable_cost = float(category.variable_cost_per_night or 0)
    payload = data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(category, field, value)
    if "variable_cost_per_night" in payload and float(payload["variable_cost_per_night"] or 0) != before_variable_cost:
        record_hotel_audit_event(
            db,
            hotel_id=context.hotel_id,
            user_id=context.user_id or 0,
            action_code="analytics.variable_cost.updated",
            entity_type="room_category",
            entity_id=category.id,
            before={"room_category_id": category.id, "variable_cost_per_night": before_variable_cost},
            after={"room_category_id": category.id, "variable_cost_per_night": float(category.variable_cost_per_night or 0)},
        )
    db.commit()
    db.refresh(category)
    return category


def _attach_current_rate(db: Session, hotel_id: int, category: RoomCategory) -> RoomCategory:
    """Resolve today's effective rate from the single source of truth and attach it
    as a transient attribute so RoomCategoryRead serialises it. This keeps the rooms
    inventory view in sync with the Tarifas calendar and reservation pricing."""
    category.current_rate = get_price_for_date(
        db, hotel_id, category.id, date.today()
    )
    return category


def _housekeeping_room(room: Room) -> RoomHousekeepingRead:
    """Materialize the safe projection before FastAPI can inspect the ORM."""

    return RoomHousekeepingRead.model_validate(room)


@router.get("/categories", response_model=list[RoomCategoryRead | RoomCategoryOperationalRead])
def list_categories(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_READ)),
):
    categories = db.query(RoomCategory).filter(RoomCategory.hotel_id == context.hotel_id).all()
    if context.user_role == "housekeeping":
        return [RoomCategoryOperationalRead.model_validate(category) for category in categories]
    for category in categories:
        _attach_current_rate(db, context.hotel_id, category)
    return categories


@router.get("/categories/{category_id}", response_model=RoomCategoryRead | RoomCategoryOperationalRead)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_READ)),
):
    category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == category_id, RoomCategory.hotel_id == context.hotel_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if context.user_role == "housekeeping":
        return RoomCategoryOperationalRead.model_validate(category)
    return _attach_current_rate(db, context.hotel_id, category)


@router.get("/categories/pricing/all", response_model=list[CategoryPricingRead])
def get_all_category_pricing(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RATES_READ)),
):
    return (
        db.query(CategoryPricing)
        .join(RoomCategory, RoomCategory.id == CategoryPricing.category_id)
        .filter(RoomCategory.hotel_id == context.hotel_id)
        .all()
    )


@router.get("/categories/{category_id}/pricing", response_model=CategoryPricingSchema)
def get_category_pricing(
    category_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RATES_READ)),
):
    pricing = (
        db.query(CategoryPricing)
        .join(RoomCategory, RoomCategory.id == CategoryPricing.category_id)
        .filter(CategoryPricing.category_id == category_id, RoomCategory.hotel_id == context.hotel_id)
        .first()
    )
    if not pricing:
        raise HTTPException(status_code=404, detail="Pricing config not found")
    return pricing


@router.post("/categories/{category_id}/pricing", response_model=CategoryPricingSchema)
def update_category_pricing(
    category_id: int,
    data: CategoryPricingSchema,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RATES_UPDATE)),
):
    category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == category_id, RoomCategory.hotel_id == context.hotel_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    pricing = (
        db.query(CategoryPricing)
        .join(RoomCategory, RoomCategory.id == CategoryPricing.category_id)
        .filter(CategoryPricing.category_id == category_id, RoomCategory.hotel_id == context.hotel_id)
        .first()
    )
    if not pricing:
        pricing = CategoryPricing(category_id=category_id)
        db.add(pricing)
    
    for k, v in data.model_dump().items():
        setattr(pricing, k, v)
    
    db.commit()
    db.refresh(pricing)
    return pricing



@router.post("/", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
def create_room(
    data: RoomCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_UPDATE)),
):
    category = db.query(RoomCategory).filter(RoomCategory.id == data.category_id, RoomCategory.hotel_id == context.hotel_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    # Validate room limit for the hotel's subscription
    ensure_room_within_limit(db, category.hotel_id)
    room = Room(**data.model_dump(), hotel_id=context.hotel_id)
    db.add(room)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Ya existe una habitación con ese número en este hotel",
        )
    db.refresh(room)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="rooms",
        record_id=room.id,
        action=AuditActionEnum.CREATE,
        actor_user_id=context.user_id,
        payload_after=audit_log_service.model_snapshot(room),
    )
    return room


@router.get("/", response_model=list[RoomRead | RoomHousekeepingRead])
def list_rooms(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_READ)),
):
    rooms = db.query(Room).filter(Room.hotel_id == context.hotel_id, Room.deleted_at.is_(None)).all()
    if context.user_role == "housekeeping":
        return [_housekeeping_room(room) for room in rooms]
    return rooms


@router.get("/availability")
def room_availability(
    category_id: int | None = None,
    check_in_date: date | None = None,
    check_out_date: date | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_READ)),
):
    """
    Simple availability helper. Returns a placeholder message if required
    parameters are missing; otherwise returns available room ids.
    """
    if not (category_id and check_in_date and check_out_date):
        return {
            "status": "placeholder",
            "available_rooms": [],
            "message": "Provide category_id, check_in_date, and check_out_date to check availability.",
        }
    try:
        def producer():
            available = find_available_rooms(
                db,
                category_id,
                check_in_date,
                check_out_date,
                hotel_id=context.hotel_id,
            )
            return {
                "status": "ok",
                "count": len(available),
                "available_rooms": [room.id for room in available],
            }

        return get_cached_availability_payload(
            hotel_id=context.hotel_id,
            category_id=category_id,
            check_in=check_in_date,
            check_out=check_out_date,
            producer=producer,
        )
    except ReservationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{room_id}", response_model=RoomRead | RoomHousekeepingRead)
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_READ)),
):
    room = db.query(Room).filter(Room.id == room_id, Room.hotel_id == context.hotel_id, Room.deleted_at.is_(None)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if context.user_role == "housekeeping":
        return _housekeeping_room(room)
    return room


@router.patch("/{room_id}", response_model=RoomRead)
def update_room(
    room_id: int,
    data: RoomUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_STATUS_UPDATE)),
):
    """Generic room update (number, floor, notes, status, etc.)."""
    _require_manager_room_lane(context)
    room = db.query(Room).filter(Room.id == room_id, Room.hotel_id == context.hotel_id, Room.deleted_at.is_(None)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    before = audit_log_service.model_snapshot(room)
    payload = data.model_dump(exclude_unset=True)
    if "category_id" in payload and payload["category_id"] is not None:
        category = db.query(RoomCategory).filter(RoomCategory.id == payload["category_id"], RoomCategory.hotel_id == context.hotel_id).first()
        if not category:
            raise HTTPException(status_code=400, detail="Category not found")
        room.category_id = payload["category_id"]

    # If reactivating a room, enforce plan room limit
    if payload.get("is_active") is True and room.is_active is False:
        ensure_room_within_limit(db, room.hotel_id)

    for field in ("room_number", "floor", "status", "is_active", "score", "is_accessible", "description", "notes"):
        if field in payload:
            setattr(room, field, payload[field])

    # When deactivating, ensure no active reservations remain assigned
    if payload.get("is_active") is False:
        active_res = db.query(Reservation).filter(
            Reservation.room_id == room_id,
            Reservation.hotel_id == context.hotel_id,
            Reservation.deleted_at.is_(None),
            Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]),
        ).count()
        if active_res > 0:
            raise HTTPException(status_code=400, detail="Room has active reservations and cannot be deactivated")

    db.commit()
    db.refresh(room)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="rooms",
        record_id=room.id,
        action=AuditActionEnum.UPDATE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(room),
    )
    invalidate_hotel_operational_caches(context.hotel_id)
    return room


@router.patch("/{room_id}/status", response_model=RoomStatusUpdateResponse)
def update_room_status(
    room_id: int,
    data: RoomStatusUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_STATUS_UPDATE)),
):
    """Update room status for housekeeping. When a room is set to cleaning/maintenance/blocked,
    any reservations assigned to it are automatically relocated by the allocation engine."""
    _require_manager_room_lane(context)
    room = db.query(Room).filter(Room.id == room_id, Room.hotel_id == context.hotel_id, Room.deleted_at.is_(None)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    before = audit_log_service.model_snapshot(room)
    room.status = data.status
    if data.notes is not None:
        room.notes = data.notes
    db.commit()
    db.refresh(room)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="rooms",
        record_id=room.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(room),
    )
    invalidate_hotel_operational_caches(context.hotel_id)
    project_room_state_event(
        context.hotel_id,
        room.id,
        data.status.value,
        datetime.now(timezone.utc),
        {"source": "rooms.status.patch", "notes": data.notes},
    )
    
    # If room was moved to an unavailable state, trigger reallocation
    realloc_result = None
    if data.status in (RoomStatusEnum.CLEANING, RoomStatusEnum.MAINTENANCE, RoomStatusEnum.BLOCKED):
        try:
            result = run_persisted_allocation(
                db,
                hotel_id=context.hotel_id,
                trigger_type=f"room_status_{data.status.value}",
                apply=True,
            )
            if result.solver_result.assignments or result.solver_result.unassigned_reservations:
                db.commit()
                realloc_result = _serialize_reallocation_result(result)
        except Exception as e:
            realloc_result = {"error": str(e)}
    
    return {"room": room, "reallocation": realloc_result}


@router.patch("/{room_id}/cleaning-status", response_model=RoomStatusUpdateResponse)
def update_room_cleaning_status(
    room_id: int,
    data: RoomStatusUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_STATUS_UPDATE)),
):
    """Apply the narrow housekeeping transition without reallocating guests.

    This endpoint deliberately cannot enter maintenance/blocked/occupied, and
    cannot touch a room assigned to a non-terminal reservation. Broader room
    state changes remain on the manager-only status endpoint above.
    """

    room = (
        db.query(Room)
        .filter(
            Room.id == room_id,
            Room.hotel_id == context.hotel_id,
            Room.deleted_at.is_(None),
        )
        .first()
    )
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    allowed_states = {RoomStatusEnum.AVAILABLE, RoomStatusEnum.CLEANING}
    if room.status not in allowed_states or data.status not in allowed_states or room.status == data.status:
        raise HTTPException(
            status_code=422,
            detail="Solo se permiten transiciones entre cleaning y available",
        )

    has_active_reservation = (
        db.query(Reservation.id)
        .filter(
            Reservation.hotel_id == context.hotel_id,
            Reservation.room_id == room.id,
            Reservation.deleted_at.is_(None),
            Reservation.status.notin_(
                [
                    ReservationStatusEnum.CANCELLED,
                    ReservationStatusEnum.CHECKED_OUT,
                    ReservationStatusEnum.NO_SHOW,
                ]
            ),
        )
        .first()
        is not None
    )
    if has_active_reservation:
        raise HTTPException(
            status_code=409,
            detail="La habitacion tiene una reserva activa y no puede cambiarse desde housekeeping",
        )

    if data.notes is not None:
        raise HTTPException(
            status_code=422,
            detail="El endpoint de limpieza solo permite cambiar el estado",
        )

    before = audit_log_service.model_snapshot(room)
    room.status = data.status
    db.commit()
    db.refresh(room)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="rooms",
        record_id=room.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(room),
    )
    invalidate_hotel_operational_caches(context.hotel_id)
    project_room_state_event(
        context.hotel_id,
        room.id,
        data.status.value,
        datetime.now(timezone.utc),
        {"source": "rooms.cleaning_status.patch", "notes": data.notes},
    )
    safe_room = _housekeeping_room(room) if context.user_role == "housekeeping" else room
    return {"room": safe_room, "reallocation": None}


class RoomCategoryAssignmentUpdate(BaseModel):
    category_id: int

@router.patch("/{room_id}/category")
def update_room_category(
    room_id: int,
    data: RoomCategoryAssignmentUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_STATUS_UPDATE)),
):
    """Update the category of a specific room."""
    _require_manager_room_lane(context)
    room = db.query(Room).filter(Room.id == room_id, Room.hotel_id == context.hotel_id, Room.deleted_at.is_(None)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    before = audit_log_service.model_snapshot(room)
    category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == data.category_id, RoomCategory.hotel_id == context.hotel_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=400, detail="Target category does not exist")

    room.category_id = data.category_id
    db.commit()
    db.refresh(room)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="rooms",
        record_id=room.id,
        action=AuditActionEnum.UPDATE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(room),
    )
    return room


@router.post("/reallocate")
def trigger_reallocation(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_MOVE)),
):
    """Manually trigger the allocation engine to optimally redistribute all reservations.
    This maximizes availability and profitability by packing rooms tightly and
    relocating reservations away from cleaning/maintenance rooms.
    Returns unassigned reservations (to be shown in yellow in the UI)."""
    
    _require_manager_room_lane(context)
    try:
        result = run_persisted_allocation(
            db,
            hotel_id=context.hotel_id,
            trigger_type="rooms_manual_reallocate",
            apply=True,
        )
        db.commit()
        if not result.solver_result.assignments and not result.solver_result.unassigned_reservations:
            return {
                "status": "ok",
                "message": "No active reservations to reallocate",
                "moved": 0,
                "unassigned": [],
            }
        payload = _serialize_reallocation_result(result, include_message=True)
        payload["status"] = "ok" if result.solver_result.success else "manual_review"
        return payload
    except DistributedLockBusy:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya hay otra redistribución en curso")
    except DistributedLockUnavailable:
        db.rollback()
        raise HTTPException(status_code=503, detail="El control de concurrencia no está disponible")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo completar la redistribución")


@router.get("/housekeeping/summary")
def housekeeping_summary(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_READ)),
):
    """Get housekeeping overview: how many rooms in each status."""
    rooms = db.query(Room).filter(Room.hotel_id == context.hotel_id, Room.deleted_at.is_(None)).all()
    summary = {
        "total": len(rooms),
        "available": 0,
        "occupied": 0,
        "maintenance": 0,
        "blocked": 0,
        "cleaning": 0,
        "rooms": [],
    }
    # Also check which rooms are actually occupied by checked-in guests
    checked_in_rooms = set()
    checked_in_res = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == context.hotel_id,
            Reservation.deleted_at.is_(None),
            Reservation.status == ReservationStatusEnum.CHECKED_IN,
        )
        .all()
    )
    for r in checked_in_res:
        if r.room_id:
            checked_in_rooms.add(r.room_id)

    for room in sorted(rooms, key=lambda r: r.room_number):
        is_guest_in = room.id in checked_in_rooms
        status_value = room.status.value
        summary[status_value] = summary.get(status_value, 0) + 1
        summary["rooms"].append({
            "id": room.id,
            "room_number": room.room_number,
            "floor": room.floor,
            "category_id": room.category_id,
            "status": status_value,
            "has_guest": is_guest_in,
            "notes": None if context.user_role == "housekeeping" else room.notes,
        })
    return summary


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_UPDATE)),
):
    """Soft-delete a room when no active reservations are attached."""
    room = db.query(Room).filter(Room.id == room_id, Room.hotel_id == context.hotel_id, Room.deleted_at.is_(None)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    in_use = db.query(Reservation).filter(
        Reservation.room_id == room_id,
        Reservation.hotel_id == context.hotel_id,
        Reservation.deleted_at.is_(None),
        Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]),
    ).count()
    if in_use > 0:
        raise HTTPException(status_code=400, detail="Room has active reservations and cannot be deleted")

    before = audit_log_service.model_snapshot(room)
    room.deleted_at = datetime.now(timezone.utc)
    room.deleted_by_user_id = context.user_id
    db.commit()
    db.refresh(room)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="rooms",
        record_id=room.id,
        action=AuditActionEnum.DELETE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(room),
    )
    invalidate_hotel_operational_caches(context.hotel_id)
    return None
