from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False)
    legal_name = Column(String(200), nullable=False)
    display_name = Column(String(200), nullable=False)
    tax_id = Column(String(50), nullable=True)
    country_code = Column(String(2), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    deactivated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("hotel_id", "display_name", name="uq_companies_hotel_display_name"),
        Index("ix_companies_hotel_id", "hotel_id"),
        Index("ix_companies_hotel_active", "hotel_id", "is_active"),
        Index(
            "uq_companies_hotel_tax_id_not_null",
            "hotel_id",
            "tax_id",
            unique=True,
            sqlite_where=text("tax_id IS NOT NULL"),
            postgresql_where=text("tax_id IS NOT NULL"),
        ),
    )
