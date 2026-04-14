"""
FastAPI routes for Guest management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.guest import Guest, GuestCompanion
from app.schemas.guest import GuestCreate, GuestRead, GuestUpdate
from app.dependencies.auth import get_auth_context, AuthContext

router = APIRouter(prefix="/api/guests", tags=["Guests"])


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

from app.schemas.guest import GuestCompanionCreate, GuestCompanionRead

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
