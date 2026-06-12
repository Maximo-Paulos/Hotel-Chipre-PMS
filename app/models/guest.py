"""
Guest and GuestCompanion models.
Exhaustive fields for check-in panel: identity documents, nationality, contact, etc.
"""
import enum
from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, Text, DateTime, Date, Enum,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone, timedelta

from app.database import Base


class DocumentTypeEnum(str, enum.Enum):
    DNI = "DNI"
    PASSPORT = "PASSPORT"
    CEDULA = "CEDULA"


class GuestRatingEnum(str, enum.Enum):
    NORMAL = "normal"
    EXCELENTE = "excelente"
    COMPLICADO = "complicado"


class Guest(Base):
    """
    Primary guest record. Contains all fields required for check-in
    and legal compliance (immigration forms, guest ledger, etc.).
    """
    __tablename__ = "guests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False, index=True)

    # Identity
    first_name = Column(String(120), nullable=False)
    last_name = Column(String(120), nullable=False)
    document_type = Column(
        Enum(
            DocumentTypeEnum,
            name="guest_document_type_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=True,
    )
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

    # Rating and behavioral classification (v72 §2.6)
    rating = Column(
        Enum(
            GuestRatingEnum,
            name="guest_rating_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=GuestRatingEnum.NORMAL,
    )

    # Check-in specifics
    terms_accepted = Column(Boolean, nullable=False, default=False)
    digital_signature = Column(Text, nullable=True)  # base64-encoded signature
    special_requests = Column(Text, nullable=True)
    observations = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    retention_until = Column(
        DateTime,
        nullable=True,
        default=lambda: datetime.now(timezone.utc) + timedelta(days=365 * 5),
    )
    updated_at = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    companions = relationship("GuestCompanion", back_populates="guest", lazy="selectin", cascade="all, delete-orphan")
    reservations = relationship("Reservation", back_populates="guest", lazy="selectin")
    tags = relationship("GuestTag", back_populates="guest", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint(
            "hotel_id", "document_type", "document_number",
            name="uq_guest_document_per_hotel",
        ),
        Index("ix_guest_hotel_id", "hotel_id"),
        # Search indexes (v72 §2.4 — must search fast by name, phone, email, document)
        Index("ix_guest_hotel_last_name", "hotel_id", "last_name"),
        Index("ix_guest_hotel_email", "hotel_id", "email"),
        Index("ix_guest_hotel_phone", "hotel_id", "phone"),
        Index("ix_guest_hotel_document_number", "hotel_id", "document_number"),
    )

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
    document_type = Column(
        Enum(
            DocumentTypeEnum,
            name="guest_document_type_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=True,
    )
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


class GuestTagTypeEnum(str, enum.Enum):
    NO_PAGO = "no_pago"
    ROBO = "robo"
    CONFLICTIVO = "conflictivo"
    ROBO_COSAS = "robo_cosas"         # Rompió cosas (v72 §2.6)
    PROHIBIDO_ALOJAR = "prohibido_alojar"  # blocks check-in until authorized (v72 §2.7)
    REQUIERE_DEPOSITO = "requiere_deposito"  # Requiere depósito extra (v72 §2.6)
    VIP = "vip"
    ALERGIAS = "alergias"
    OTRO = "otro"


class GuestTag(Base):
    """
    Behavioral / alert tags on a guest (v72 §2.6).
    Multiple tags per guest; each tag can have a note and expiry.
    """
    __tablename__ = "guest_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    guest_id = Column(Integer, ForeignKey("guests.id", ondelete="CASCADE"), nullable=False)

    tag_type = Column(
        Enum(
            GuestTagTypeEnum,
            name="guest_tag_type_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    note = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    guest = relationship("Guest", back_populates="tags")

    __table_args__ = (
        Index("ix_guest_tags_hotel_guest", "hotel_id", "guest_id"),
    )

    def __repr__(self) -> str:
        return f"<GuestTag(id={self.id}, guest_id={self.guest_id}, tag={self.tag_type})>"
