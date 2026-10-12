"""
FastAPI routes for Guest management.
"""
import csv
import json
from datetime import date
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.guest import Guest, GuestCompanion, DocumentTypeEnum
from app.models.security_audit_log import SecurityAuditLog
from app.models.reservation import Reservation, ReservationStatusEnum
from app.schemas.guest import GuestCreate, GuestRead, GuestUpdate, GuestCompanionCreate, GuestCompanionRead
from app.schemas.guest_tag import GuestRatingUpdate, GuestTagCreate, GuestTagRead
from app.dependencies.auth import AuthContext, require_permission
from app.services.guest_service import (
    GuestCreatePayload,
    GuestServiceError,
    add_tag as add_guest_tag,
    find_or_create_guest,
    list_active_tags,
    quick_profile,
    resolve_tag as resolve_guest_tag,
    search_guests,
    set_rating,
)
from app.services.reservation_service import active_reservations
from app.services.csv_export_safety import spreadsheet_safe_row
from app.models.audit_log import AuditActionEnum
from app.services import audit_log_service
from app.services.permission_service import (
    PERMISSION_GUEST_CREATE,
    PERMISSION_GUEST_EDIT,
    PERMISSION_GUEST_EXPORT,
    PERMISSION_GUEST_TAGS,
    PERMISSION_GUEST_VIEW,
)

router = APIRouter(prefix="/api/guests", tags=["Guests"])
_GUEST_LEDGER_MAX_RANGE_DAYS = 367
_GUEST_LEDGER_MAX_ROWS = 10_000


def _guest_service_error_detail(exc: GuestServiceError) -> str:
    return {
        "Guest not found": "No se encontró el huésped.",
        "Guest tag not found": "No se encontró la etiqueta del huésped.",
    }.get(str(exc), "No se pudo completar la operación del huésped.")


def _enum_value(value) -> str:
    if isinstance(value, DocumentTypeEnum):
        return value.value
    return str(value or "")


def _build_guest_ledger_csv(rows: list[dict[str, object]]) -> str:
    fieldnames = [
        "first_name",
        "last_name",
        "document_type",
        "document_number",
        "nationality",
        "date_of_birth",
        "arrival_date",
        "departure_date",
        "terms_accepted",
        "country_of_residence",
        "phone",
        "email",
    ]
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(spreadsheet_safe_row(row))
    return "\ufeff" + buffer.getvalue()


# Allow trailing-slash-less POST from the UI (avoids 405).
@router.post("/", response_model=GuestRead, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=GuestRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_guest(
    data: GuestCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_CREATE)),
):
    companions_data = data.companions
    guest_dict = data.model_dump(exclude={"companions"})
    guest, created = find_or_create_guest(
        db,
        GuestCreatePayload(hotel_id=context.hotel_id, **guest_dict),
    )

    # BRM §2.1: an existing guest is reused; only attach companions to brand-new records.
    new_companions = []
    if created:
        for comp in companions_data:
            companion = GuestCompanion(guest_id=guest.id, **comp.model_dump())
            db.add(companion)
            new_companions.append(companion)

    db.commit()
    db.refresh(guest)
    if created:
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="guests",
            record_id=guest.id,
            action=AuditActionEnum.CREATE,
            actor_user_id=context.user_id,
            payload_after=audit_log_service.model_snapshot(guest),
        )
    for companion in new_companions:
        db.refresh(companion)
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="guest_companions",
            record_id=companion.id,
            action=AuditActionEnum.CREATE,
            actor_user_id=context.user_id,
            payload_after=audit_log_service.model_snapshot(companion),
        )
    return guest


@router.get("/", response_model=list[GuestRead])
def list_guests(
    skip: int = Query(0, ge=0),
    # A5: was already paginated, cap added to match the A2 precedent for
    # /api/reservations -- no `total` in the response (see frontend/src/api/
    # guests.ts), the UI treats a full page as "there may be more".
    limit: int = Query(50, ge=1, le=200),
    search: str = "",
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_VIEW)),
):
    return search_guests(
        db,
        context.hotel_id,
        search,
        skip=skip,
        limit=limit,
        default_order_by_id=True,
    )


@router.get("/search", response_model=list[GuestRead])
def search_guest_records(
    q: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_VIEW)),
):
    return search_guests(db, context.hotel_id, q, skip=skip, limit=limit)


@router.get("/ledger/export")
def export_guest_ledger(
    from_date: date,
    to_date: date,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_EXPORT)),
):
    if to_date <= from_date:
        raise HTTPException(status_code=422, detail="El período de exportación es inválido.")
    range_days = (to_date - from_date).days
    if range_days > _GUEST_LEDGER_MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"El período máximo de exportación es de {_GUEST_LEDGER_MAX_RANGE_DAYS} días.",
        )

    reservations = (
        active_reservations(db, context.hotel_id)
        .join(Guest, (Guest.id == Reservation.guest_id) & (Guest.hotel_id == context.hotel_id))
        .filter(
            Reservation.status != ReservationStatusEnum.CANCELLED,
            Guest.deleted_at.is_(None),
            Reservation.check_in_date < to_date,
            Reservation.check_out_date > from_date,
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        .limit(_GUEST_LEDGER_MAX_ROWS + 1)
        .all()
    )
    if len(reservations) > _GUEST_LEDGER_MAX_ROWS:
        raise HTTPException(
            status_code=413,
            detail="El resultado supera el máximo de huéspedes exportables; acotá el período.",
        )

    csv_rows: list[dict[str, object]] = []
    for reservation in reservations:
        guest = reservation.guest
        csv_rows.append(
            {
                "first_name": guest.first_name,
                "last_name": guest.last_name,
                "document_type": _enum_value(guest.document_type),
                "document_number": guest.document_number or "",
                "nationality": guest.nationality or "",
                "date_of_birth": guest.date_of_birth.isoformat() if guest.date_of_birth else "",
                "arrival_date": reservation.check_in_date.isoformat(),
                "departure_date": reservation.check_out_date.isoformat(),
                "terms_accepted": "true" if guest.terms_accepted else "false",
                "country_of_residence": guest.country or "",
                "phone": guest.phone or "",
                "email": guest.email or "",
            }
        )

    csv_text = _build_guest_ledger_csv(csv_rows)
    filename = f"guest-ledger-{context.hotel_id}-{from_date.isoformat()}-{to_date.isoformat()}.csv"
    db.add(
        SecurityAuditLog(
            hotel_id=context.hotel_id,
            user_id=context.user_id,
            action="guest.ledger_csv_exported",
            resource_type="guest_ledger_export",
            resource_id=None,
            details=json.dumps(
                {
                    "from_date": from_date.isoformat(),
                    "to_date": to_date.isoformat(),
                    "row_count": len(reservations),
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    )
    db.commit()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/{guest_id}", response_model=GuestRead)
def get_guest(
    guest_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_VIEW)),
):
    guest = db.query(Guest).filter(Guest.id == guest_id, Guest.hotel_id == context.hotel_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="No se encontró el huésped.")
    return guest


@router.get("/{guest_id}/quick-profile")
def get_guest_quick_profile(
    guest_id: int,
    offset: int = 0,
    limit: int = 5,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_VIEW)),
):
    try:
        profile = quick_profile(
            db,
            hotel_id=context.hotel_id,
            guest_id=guest_id,
            offset=offset,
            limit=limit,
        )
        # Do not return ORM instances here. Guest.reservations and
        # GuestTag.guest form cyclic SQLAlchemy relationships; FastAPI's
        # generic encoder can recurse indefinitely once the guest has a stay.
        return {
            **profile,
            "guest": GuestRead.model_validate(profile["guest"]).model_dump(mode="json"),
            "active_tags": [
                GuestTagRead.model_validate(tag).model_dump(mode="json")
                for tag in profile["active_tags"]
            ],
        }
    except GuestServiceError as exc:
        raise HTTPException(status_code=404, detail=_guest_service_error_detail(exc)) from exc


@router.get("/{guest_id}/tags", response_model=list[GuestTagRead])
def get_guest_tags(
    guest_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_VIEW)),
):
    try:
        return list_active_tags(db, hotel_id=context.hotel_id, guest_id=guest_id)
    except GuestServiceError as exc:
        raise HTTPException(status_code=404, detail=_guest_service_error_detail(exc)) from exc


@router.post("/{guest_id}/tags", response_model=GuestTagRead, status_code=status.HTTP_201_CREATED)
def create_guest_tag(
    guest_id: int,
    data: GuestTagCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_TAGS)),
):
    try:
        tag = add_guest_tag(
            db,
            hotel_id=context.hotel_id,
            guest_id=guest_id,
            tag_type=data.tag_type,
            note=data.note,
            expires_at=data.expires_at,
            user_id=context.user_id,
        )
        db.commit()
        db.refresh(tag)
        return tag
    except GuestServiceError as exc:
        raise HTTPException(status_code=404, detail=_guest_service_error_detail(exc)) from exc


@router.post("/{guest_id}/tags/{tag_id}/resolve", response_model=GuestTagRead)
def resolve_tag(
    guest_id: int,
    tag_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_TAGS)),
):
    try:
        tag = resolve_guest_tag(
            db,
            hotel_id=context.hotel_id,
            guest_id=guest_id,
            tag_id=tag_id,
            user_id=context.user_id,
        )
        db.commit()
        db.refresh(tag)
        return tag
    except GuestServiceError as exc:
        raise HTTPException(status_code=404, detail=_guest_service_error_detail(exc)) from exc


@router.patch("/{guest_id}/rating", response_model=GuestRead)
def update_guest_rating(
    guest_id: int,
    data: GuestRatingUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_TAGS)),
):
    try:
        guest = set_rating(
            db,
            hotel_id=context.hotel_id,
            guest_id=guest_id,
            rating=data.rating,
            user_id=context.user_id,
        )
        db.commit()
        db.refresh(guest)
        return guest
    except GuestServiceError as exc:
        raise HTTPException(status_code=404, detail=_guest_service_error_detail(exc)) from exc


@router.patch("/{guest_id}", response_model=GuestRead)
def update_guest(
    guest_id: int,
    data: GuestUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_EDIT)),
):
    guest = db.query(Guest).filter(Guest.id == guest_id, Guest.hotel_id == context.hotel_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="No se encontró el huésped.")

    before = audit_log_service.model_snapshot(guest)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(guest, key, value)
        
    db.commit()
    db.refresh(guest)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="guests",
        record_id=guest.id,
        action=AuditActionEnum.UPDATE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(guest),
    )
    return guest

@router.post("/{guest_id}/companions", response_model=list[GuestCompanionRead], status_code=status.HTTP_201_CREATED)
def add_companions(
    guest_id: int,
    companions: list[GuestCompanionCreate],
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_EDIT)),
):
    """Add new companions to an existing guest."""
    guest = db.query(Guest).filter(Guest.id == guest_id, Guest.hotel_id == context.hotel_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="No se encontró el huésped.")
        
    new_companions = []
    for comp_data in companions:
        companion = GuestCompanion(guest_id=guest.id, **comp_data.model_dump())
        db.add(companion)
        new_companions.append(companion)
        
    db.commit()
    for c in new_companions:
        db.refresh(c)
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="guest_companions",
            record_id=c.id,
            action=AuditActionEnum.CREATE,
            actor_user_id=context.user_id,
            payload_after=audit_log_service.model_snapshot(c),
        )
    return new_companions
