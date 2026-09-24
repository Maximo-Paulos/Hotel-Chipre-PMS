"""Tenant-scoped custom roles layered over a built-in permission profile."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
    UniqueConstraint,
)

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HotelRole(Base):
    """A stable custom role code whose policy is scoped to one hotel."""

    __tablename__ = "hotel_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
    )
    code = Column(String(20), nullable=False)
    name = Column(String(80), nullable=False)
    name_key = Column(String(240), nullable=False)
    base_role = Column(String(20), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    version = Column(Integer, nullable=False, default=1, server_default="1")
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("hotel_id", "code", name="uq_hotel_roles_hotel_code"),
        UniqueConstraint("hotel_id", "name_key", name="uq_hotel_roles_hotel_name_key"),
        CheckConstraint(
            "base_role IN ('manager', 'receptionist', 'housekeeping')",
            name="ck_hotel_roles_base_role",
        ),
        CheckConstraint(
            "length(code) <= 20 AND substr(code, 1, 3) = 'cr_'",
            name="ck_hotel_roles_custom_code",
        ),
        Index("ix_hotel_roles_hotel_id", "hotel_id"),
        Index("ix_hotel_roles_hotel_active", "hotel_id", "is_active"),
    )
    __mapper_args__ = {"version_id_col": version}
