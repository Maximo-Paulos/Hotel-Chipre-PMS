"""Tenant-scoped grouping for multiple reservations created as one stay party."""

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Text, UniqueConstraint

from app.database import Base


class ReservationGroup(Base):
    __tablename__ = "reservation_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    guest_id = Column(Integer, nullable=False)
    company_id = Column(Integer, nullable=True)
    check_in_date = Column(Date, nullable=False)
    check_out_date = Column(Date, nullable=False)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("hotel_id", "id", name="uq_reservation_groups_hotel_id_id"),
        ForeignKeyConstraint(
            ["hotel_id", "guest_id"], ["guests.hotel_id", "guests.id"],
            name="fk_reservation_groups_hotel_guest",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "company_id"], ["companies.hotel_id", "companies.id"],
            name="fk_reservation_groups_hotel_company",
        ),
        Index("ix_reservation_groups_hotel_created", "hotel_id", "created_at"),
    )
