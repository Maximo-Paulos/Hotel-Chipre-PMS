"""
Guest and GuestCompanion models.
Exhaustive fields for check-in panel: identity documents, nationality, contact, etc.
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, Text, DateTime, Date
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.database import Base


class Guest(Base):
    """
    Primary guest record. Contains all fields required for check-in
    and legal compliance (immigration forms, guest ledger, etc.).
    """
    __tablename__ = "guests"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identity
    first_name = Column(String(120), nullable=False)
    last_name = Column(String(120), nullable=False)
    document_type = Column(String(30), nullable=True)   # "DNI", "PASSPORT", "CEDULA"
    document_number = Column(String(50), nullable=True)
    nationality = Column(String(80), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)

    # Contact
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    address_line1 = Column(String(250), nullable=True)
    address_line2 = Column(String(250), nullable=True)
    city = Column(String(100), nullable=True)
    state_province = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(80), nullable=True)

    # Check-in specifics
    terms_accepted = Column(Boolean, nullable=False, default=False)
    digital_signature = Column(Text, nullable=True)  # base64-encoded signature
    special_requests = Column(Text, nullable=True)
    observations = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    companions = relationship("GuestCompanion", back_populates="guest", lazy="selectin", cascade="all, delete-orphan")
    reservations = relationship("Reservation", back_populates="guest", lazy="selectin")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def has_valid_identity(self) -> bool:
        """Check if guest has provided required identity documents for check-in."""
        return bool(
            self.first_name
            and self.last_name
            and self.document_type
            and self.document_number
        )

    def __repr__(self) -> str:
        return f"<Guest(id={self.id}, name='{self.full_name}')>"


class GuestCompanion(Base):
    """
    Companion/additional occupant traveling with a primary guest.
    Hotels often need this for legal compliance and room occupancy tracking.
    """
    __tablename__ = "guest_companions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guest_id = Column(Integer, ForeignKey("guests.id", ondelete="CASCADE"), nullable=False)

    first_name = Column(String(120), nullable=False)
    last_name = Column(String(120), nullable=False)
    document_type = Column(String(30), nullable=True)
    document_number = Column(String(50), nullable=True)
    nationality = Column(String(80), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    relationship_to_guest = Column(String(50), nullable=True)  # "spouse", "child", etc.

    # Relationships
    guest = relationship("Guest", back_populates="companions")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<GuestCompanion(id={self.id}, name='{self.full_name}', guest_id={self.guest_id})>"
