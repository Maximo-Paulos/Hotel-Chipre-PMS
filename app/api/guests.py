"""
FastAPI routes for Guest management.
"""
import csv
from datetime import date
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.guest import Guest, GuestCompanion, DocumentTypeEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.schemas.guest import GuestCreate, GuestRead, GuestUpdate, GuestCompanionCreate, GuestCompanionRead
from app.dependencies.auth import get_auth_context, AuthContext

router = APIRouter(prefix="/api/guests", tags=["Guests"])


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
        writer.writerow(row)
    return "\ufeff" + buffer.getvalue()


# Allow trailing-slash-less POST from the UI (avoids 405).
@router.post("/", response_model=GuestRead, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=GuestRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_guest(
    data: GuestCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    companions_data = data.companions
    guest_dict = data.model_dump(exclude={"companions"})
    guest = Guest(**guest_dict, hotel_id=context.hotel_id)
    db.add(guest)
    db.flush()

    for comp in companions_data:
        companion = GuestCompanion(guest_id=guest.id, **comp.model_dump())
        db.add(companion)

    db.commit()
    db.refresh(guest)
    return guest


@router.get("/", response_model=list[GuestRead])
def list_guests(
    skip: int = 0,
    limit: int = 50,
    search: str = "",
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    query = db.query(Guest).filter(Guest.hotel_id == context.hotel_id)
    if search:
        query = query.filter(
            (Guest.first_name.ilike(f"%{search}%"))
            | (Guest.last_name.ilike(f"%{search}%"))
            | (Guest.document_number.ilike(f"%{search}%"))
            | (Guest.email.ilike(f"%{search}%"))
        )
    return query.offset(skip).limit(limit).all()


@router.get("/ledger/export")
def export_guest_ledger(
    from_date: date,
    to_date: date,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    if to_date <= from_date:
        raise HTTPException(status_code=400, detail="to_date must be after from_date")

    reservations = (
        db.query(Reservation)
        .join(Guest, Guest.id == Reservation.guest_id)
        .filter(
            Reservation.hotel_id == context.hotel_id,
            Reservation.status != ReservationStatusEnum.CANCELLED,
            Reservation.check_in_date < to_date,
            Reservation.check_out_date > from_date,
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        .all()
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
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{guest_id}", response_model=GuestRead)
def get_guest(
    guest_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    guest = db.query(Guest).filter(Guest.id == guest_id, Guest.hotel_id == context.hotel_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    return guest


@router.patch("/{guest_id}", response_model=GuestRead)
def update_guest(
    guest_id: int,
    data: GuestUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    guest = db.query(Guest).filter(Guest.id == guest_id, Guest.hotel_id == context.hotel_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
        
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(guest, key, value)
        
    db.commit()
    db.refresh(guest)
    return guest

@router.post("/{guest_id}/companions", response_model=list[GuestCompanionRead], status_code=status.HTTP_201_CREATED)
def add_companions(
    guest_id: int,
    companions: list[GuestCompanionCreate],
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    """Add new companions to an existing guest."""
    guest = db.query(Guest).filter(Guest.id == guest_id, Guest.hotel_id == context.hotel_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
        
    new_companions = []
    for comp_data in companions:
        companion = GuestCompanion(guest_id=guest.id, **comp_data.model_dump())
        db.add(companion)
        new_companions.append(companion)
        
    db.commit()
    for c in new_companions:
        db.refresh(c)
    return new_companions
