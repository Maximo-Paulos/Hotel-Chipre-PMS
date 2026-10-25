"""Auditable, tenant-scoped approval records for manual reservation cancellation."""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)

from app.database import Base


class ReservationCancellationReview(Base):
    __tablename__ = "reservation_cancellation_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
    )
    reservation_id = Column(Integer, nullable=False)

    # The proposal is an immutable record of what was evaluated at request
    # time. A stored penalty is descriptive only; it is never a payment or a
    # balance adjustment.
    review_type = Column(String(40), nullable=False)
    status = Column(String(24), nullable=False, default="pending", server_default="pending")
    reason_code = Column(String(80), nullable=False)
    policy_snapshot = Column(JSON, nullable=True)
    reservation_total = Column(Numeric(12, 2), nullable=True)
    reservation_currency_code = Column(String(3), nullable=True)
    free_cancellation_hours = Column(Integer, nullable=True)
    check_in_time = Column(String(5), nullable=True)
    hotel_timezone = Column(String(100), nullable=True)
    cancellation_cutoff_at = Column(DateTime(timezone=True), nullable=True)
    penalty_amount = Column(Numeric(12, 2), nullable=True)
    penalty_currency_code = Column(String(3), nullable=True)

    requested_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_reason = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "review_type IN ('penalty', 'historical_policy_missing', 'policy_needs_review')",
            name="ck_reservation_cancellation_review_type_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_reservation_cancellation_review_status_valid",
        ),
        CheckConstraint(
            "(penalty_amount IS NULL AND penalty_currency_code IS NULL) OR "
            "(penalty_amount >= 0 AND length(penalty_currency_code) = 3 "
            "AND penalty_currency_code = upper(penalty_currency_code))",
            name="ck_reservation_cancellation_review_penalty_valid",
        ),
        UniqueConstraint("hotel_id", "id", name="uq_reservation_cancellation_reviews_hotel_id_id"),
        ForeignKeyConstraint(
            ["hotel_id", "reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_reservation_cancellation_reviews_hotel_reservation",
            ondelete="CASCADE",
        ),
        Index(
            "ix_reservation_cancellation_reviews_hotel_status_requested",
            "hotel_id",
            "status",
            "requested_at",
        ),
        Index(
            "uq_reservation_cancellation_reviews_pending_reservation",
            "hotel_id",
            "reservation_id",
            unique=True,
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
    )
