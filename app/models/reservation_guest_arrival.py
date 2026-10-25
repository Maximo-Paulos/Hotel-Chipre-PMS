"""Append-only per-person arrival records for reservation check-in."""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from app.database import Base


class ReservationGuestArrival(Base):
    """One immutable lodging-arrival record per guest in a reservation.

    ``(hotel_id, reservation_id, guest_id)`` is also the natural idempotency
    key: retrying a lost POST returns the original actor and timestamp rather
    than writing a duplicate arrival.
    """

    __tablename__ = "reservation_guest_arrivals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, nullable=False)
    reservation_id = Column(Integer, nullable=False)
    guest_id = Column(Integer, nullable=False)
    arrived_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    # The ledger is immutable; prevent user deletion from mutating its actor.
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    actor_role = Column(String(40), nullable=False)

    __table_args__ = (
        CheckConstraint("length(trim(actor_role)) > 0", name="ck_reservation_guest_arrival_actor_role"),
        ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_reservation_guest_arrivals_hotel_id", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "reservation_id"], ["reservations.hotel_id", "reservations.id"],
            name="fk_reservation_guest_arrivals_hotel_reservation", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "guest_id"], ["guests.hotel_id", "guests.id"],
            name="fk_reservation_guest_arrivals_hotel_guest", ondelete="RESTRICT",
        ),
        UniqueConstraint("hotel_id", "id", name="uq_reservation_guest_arrivals_hotel_id_id"),
        UniqueConstraint(
            "hotel_id", "reservation_id", "guest_id",
            name="uq_reservation_guest_arrivals_guest",
        ),
        Index(
            "ix_reservation_guest_arrivals_hotel_reservation_arrived",
            "hotel_id", "reservation_id", "arrived_at", "id",
        ),
    )
