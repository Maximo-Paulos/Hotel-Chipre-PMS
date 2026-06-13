"""
Configurable permission matrix models.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from app.database import Base


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100), nullable=False, unique=True)
    description = Column(String(255), nullable=False)


class RolePermissionDefault(Base):
    __tablename__ = "role_permission_defaults"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String(50), nullable=False)
    permission_code = Column(String(100), nullable=False)
    allowed = Column(Boolean, nullable=False, default=False, server_default="0")

    __table_args__ = (
        UniqueConstraint("role", "permission_code", name="uq_role_permission_defaults_role_permission"),
        ForeignKeyConstraint(
            ["permission_code"],
            ["permissions.code"],
            name="fk_role_permission_defaults_permission_code_permissions",
            ondelete="CASCADE",
        ),
    )


class HotelPermissionOverride(Base):
    __tablename__ = "hotel_permission_overrides"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, nullable=False)
    role = Column(String(50), nullable=False)
    permission_code = Column(String(100), nullable=False)
    allowed = Column(Boolean, nullable=False, default=False, server_default="0")
    updated_by_user_id = Column(Integer, nullable=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("hotel_id", "role", "permission_code", name="uq_hotel_permission_overrides_hotel_role_permission"),
        ForeignKeyConstraint(
            ["hotel_id"],
            ["hotel_configuration.id"],
            name="fk_hotel_permission_overrides_hotel_id_hotel_configuration",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["permission_code"],
            ["permissions.code"],
            name="fk_hotel_permission_overrides_permission_code_permissions",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name="fk_hotel_permission_overrides_updated_by_user_id_users",
            ondelete="SET NULL",
        ),
        Index("ix_hotel_permission_overrides_hotel_id", "hotel_id"),
    )
