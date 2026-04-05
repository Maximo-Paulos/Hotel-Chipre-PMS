"""
Reservation model with strict state machine.
States: pending â†’ deposit_paid â†’ fully_paid â†’ checked_in â†’ checked_out
                                                â†— (skip deposit)
Also supports: cancelled (from any pre-checkin state)
"""
import enum
from sqlalchemy import (
    Column, Integer, Float, String, ForeignKey, Enum, Text, DateTime, Date,
    CheckConstraint, UniqueConstraint, Index, Table
)
from sqlalchemy.orm import relationship, validates
from datetime import datetime, timezone

from app.database import Base


class ReservationStatusEnum(str, enum.Enum):
    PENDING = "pending"
    DEPOSIT_PAID = "deposit_paid"
    FULLY_PAID = "fully_paid"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"


class ReservationSourceEnum(str, enum.Enum):
    DIRECT = "direct"            # Walk-in or website
    BOOKING = "booking"          # Booking.com
    EXPEDIA = "expedia"          # Expedia
    OTHER_OTA = "other_ota"


# Valid state transitions
VALID_TRANSITIONS: dict[ReservationStatusEnum, set[ReservationStatusEnum]] = {
    ReservationStatusEnum.PENDING: {
        ReservationStatusEnum.DEPOSIT_PAID,
        ReservationStatusEnum.FULLY_PAID,
        ReservationStatusEnum.CANCELLED,
    },
    ReservationStatusEnum.DEPOSIT_PAID: {
        ReservationStatusEnum.FULLY_PAID,
        ReservationStatusEnum.CANCELLED,
    },
    ReservationStatusEnum.FULLY_PAID: {
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CANCELLED,
    },
    ReservationStatusEnum.CHECKED_IN: {
        ReservationStatusEnum.CHECKED_OUT,
    },
    ReservationStatusEnum.CHECKED_OUT: set(),
    ReservationStatusEnum.CANCELLED: set(),     # Terminal state
}


reservation_additional_guests = Table(
    "reservation_additional_guests",
    Base.metadata,
    Column("reservation_id", Integer, ForeignKey("reservations.id", ondelete="CASCADE"), primary_key=True),
    Column("guest_id", Integer, ForeignKey("guests.id", ondelete="CASCADE"), primary_key=True)
)


class Reservation(Base):
    """
    Core reservation entity.
    Tracks the full lifecycle from booking to checkout, including financial state.
    """
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    confirmation_code = Column(String(30), nullable=False, unique=True, index=True)
    # Default single-hotel context for tests; explicit in multi-hotel flows.
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False, default=1)

    # Guest and Room linkage
    guest_id = Column(Integer, ForeignKey("guests.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True)  # Nullable until assigned
    category_id = Column(Integer, ForeignKey("room_categories.id"), nullable=False)

    # Dates
    check_in_date = Column(Date, nullable=False)
    check_out_date = Column(Date, nullable=False)
    actual_check_in = Column(DateTime, nullable=True)
    actual_check_out = Column(DateTime, nullable=True)

    # Financial
    total_amount = Column(Float, nullable=False, default=0.0)
    amount_paid = Column(Float, nullable=False, default=0.0)
    deposit_amount = Column(Float, nullable=False, default=0.0)

    # Status
    status = Column(
        Enum(ReservationStatusEnum, name="reservation_status_enum", create_constraint=True),
        nullable=False,
        default=ReservationStatusEnum.PENDING,
    )

    # Source tracking (OTA or direct)
    source = Column(
        Enum(ReservationSourceEnum, name="reservation_source_enum", create_constraint=True),
        nullable=False,
        default=ReservationSourceEnum.DIRECT,
    )
    external_id = Column(String(100), nullable=True, index=True)  # OTA booking ID

    # Number of guests
    num_adults = Column(Integer, nullable=False, default=1)
    num_children = Column(Integer, nullable=False, default=0)

    notes = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    guest = relationship("Guest", back_populates="reservations", lazy="joined")
    additional_guests = relationship("Guest", secondary=reservation_additional_guests, lazy="selectin")
    room = relationship("Room", back_populates="reservations", lazy="joined")
    category = relationship("RoomCategory", lazy="joined")
    transactions = relationship("Transaction", back_populates="reservation", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("check_out_date > check_in_date", name="ck_reservation_dates"),
        CheckConstraint("total_amount >= 0", name="ck_reservation_total_positive"),
        CheckConstraint("amount_paid >= 0", name="ck_reservation_paid_positive"),
        CheckConstraint("num_adults > 0", name="ck_reservation_adults_positive"),
        CheckConstraint("num_children >= 0", name="ck_reservation_children_positive"),
        Index("ix_reservation_dates", "check_in_date", "check_out_date"),
        Index("ix_reservation_hotel_id", "hotel_id"),
    )

    @property
    def balance_due(self) -> float:
        """Outstanding balance on the reservation."""
        return max(0.0, self.total_amount - self.amount_paid)

    @property
    def nights(self) -> int:
        """Number of nights for the stay."""
        return (self.check_out_date - self.check_in_date).days

    def can_transition_to(self, new_status: ReservationStatusEnum) -> bool:
        """Check if a state transition is valid."""
        if (
            self.status in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT)
            and new_status == ReservationStatusEnum.CANCELLED
        ):
            # Defensive guard: never allow cancellations after check-in/checkout
            return False
        return new_status in VALID_TRANSITIONS.get(self.status, set())

    def __repr__(self) -> str:
        return (
            f"<Reservation(id={self.id}, code='{self.confirmation_code}', "
            f"status={self.status}, room_id={self.room_id})>"
        )
