"""
User accounts for authentication.
Stores hashed passwords and basic profile flags.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(200), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    # Stable Google OIDC subject. Email is an attribute that can be spoofed
    # during password registration; the provider subject is the identity key
    # used for subsequent Google logins.
    google_sub = Column(String(255), nullable=True, unique=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    role = Column(String(50), nullable=False, default="owner")
    # Bumped whenever previously issued JWTs must be invalidated server-side
    # (currently: password reset). JWTs are otherwise stateless with no
    # blacklist, so this is the only revocation mechanism available.
    token_version = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_login = Column(DateTime, nullable=True)

    mfa_secret = relationship(
        "UserMfaSecret",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    mfa_recovery_codes = relationship(
        "UserMfaRecoveryCode",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sessions = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', active={self.is_active})>"
