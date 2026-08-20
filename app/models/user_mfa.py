"""TOTP MFA secrets and one-time recovery codes for normal user accounts."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class UserMfaSecret(Base):
    __tablename__ = "user_mfa_secrets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    encrypted_secret = Column(String(512), nullable=False)
    status = Column(String(20), nullable=False, default="pending", server_default="pending")
    last_used_step = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    confirmed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="mfa_secret")
    recovery_codes = relationship(
        "UserMfaRecoveryCode",
        back_populates="mfa_secret",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class UserMfaRecoveryCode(Base):
    __tablename__ = "user_mfa_recovery_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mfa_secret_id = Column(
        Integer,
        ForeignKey("user_mfa_secrets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash = Column(Text, nullable=False)
    used_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="mfa_recovery_codes")
    mfa_secret = relationship("UserMfaSecret", back_populates="recovery_codes")

    __table_args__ = (
        Index("ix_user_mfa_recovery_codes_user_unused", "user_id", "used_at"),
    )
