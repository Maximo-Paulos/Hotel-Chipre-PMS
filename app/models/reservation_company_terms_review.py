"""Append-only manager decisions for company-term changes on a reservation."""

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
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base


class ReservationCompanyTermsReview(Base):
    __tablename__ = "reservation_company_terms_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, nullable=False)
    reservation_id = Column(Integer, nullable=False)
    company_id = Column(Integer, nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    action = Column(String(40), nullable=False)
    reason = Column(Text, nullable=False)
    idempotency_key = Column(String(36), nullable=False)
    expected_config_fingerprint = Column(String(64), nullable=False)
    changed_fields = Column(JSON, nullable=False)
    previous_snapshot = Column(JSON, nullable=True)
    previous_reviewed_config = Column(JSON, nullable=True)
    current_company_terms = Column(JSON, nullable=False)
    resulting_snapshot = Column(JSON, nullable=True)
    applied_reservation_changes = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "action IN ('keep_snapshot', 'accept_current')",
            name="ck_reservation_company_terms_review_action",
        ),
        CheckConstraint("length(trim(reason)) > 0", name="ck_reservation_company_terms_review_reason"),
        ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_reservation_company_terms_reviews_hotel", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "reservation_id"], ["reservations.hotel_id", "reservations.id"],
            name="fk_reservation_company_terms_reviews_reservation", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "company_id"], ["companies.hotel_id", "companies.id"],
            name="fk_reservation_company_terms_reviews_company", ondelete="RESTRICT",
        ),
        UniqueConstraint("hotel_id", "id", name="uq_reservation_company_terms_reviews_hotel_id_id"),
        UniqueConstraint(
            "hotel_id", "reservation_id", "idempotency_key",
            name="uq_reservation_company_terms_reviews_idempotency",
        ),
        Index(
            "ix_reservation_company_terms_reviews_hotel_reservation_created",
            "hotel_id", "reservation_id", "created_at", "id",
        ),
    )
