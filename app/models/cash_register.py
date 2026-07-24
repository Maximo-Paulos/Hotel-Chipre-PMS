"""
Cash register (caja) models — Sprint 1 requirement per v72 §13.

Lifecycle:
  CashSession (apertura → cierre)
    ↳ CashMovement* (ingresos / egresos durante el turno)
    ↳ CashCloseReport (arqueo y diferencias al cerrar)

Rules:
  - A hotel can only have ONE open session at a time.
  - Movements cannot be added to a closed session.
  - The close report captures expected vs actual and the difference.
  - Re-apertura allowed after supervisor approval (via PendingOperationalAction).
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class CashSessionStatusEnum(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    PENDING_APPROVAL = "pending_approval"  # re-apertura needs supervisor


class CashMovementTypeEnum(str, enum.Enum):
    INCOME = "income"    # cobro, ingreso
    EXPENSE = "expense"  # egreso, retiro
    ADJUSTMENT = "adjustment"  # corrección manual


class CashCustodyStatusEnum(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class CashSession(Base):
    """
    Single cash-register shift. Only one OPEN session per hotel at a time
    (enforced by partial unique index in PostgreSQL; SQLite tolerates multiple
    open rows but the service layer guards it).
    """
    __tablename__ = "cash_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
    )
    opened_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    closed_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    status = Column(
        Enum(
            CashSessionStatusEnum,
            name="cash_session_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=CashSessionStatusEnum.OPEN,
    )

    opening_balance = Column(Numeric(12, 2), nullable=False, default=0)
    currency_code = Column(String(3), nullable=False, default="ARS")

    opened_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    closed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    movements = relationship(
        "CashMovement", back_populates="session",
        lazy="selectin", cascade="all, delete-orphan",
    )
    close_report = relationship(
        "CashCloseReport", back_populates="session",
        foreign_keys="CashCloseReport.session_id",
        uselist=False, lazy="select",
    )

    __table_args__ = (
        CheckConstraint("opening_balance >= 0", name="ck_cash_sessions_opening_nonneg"),
        Index("ix_cash_sessions_hotel_status", "hotel_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<CashSession(id={self.id}, hotel={self.hotel_id}, status={self.status})>"


class CashMovement(Base):
    """
    Individual money movement within an open cash session.
    Linked optionally to a reservation or transaction for reconciliation.
    """
    __tablename__ = "cash_movements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id = Column(
        Integer,
        ForeignKey("cash_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    reservation_id = Column(
        Integer,
        ForeignKey("reservations.id", ondelete="SET NULL"),
        nullable=True,
    )
    transaction_id = Column(
        Integer,
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    recorded_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    movement_type = Column(
        Enum(
            CashMovementTypeEnum,
            name="cash_movement_type_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )

    amount = Column(Numeric(12, 2), nullable=False)
    description = Column(String(300), nullable=True)
    recorded_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    session = relationship("CashSession", back_populates="movements")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_cash_movements_amount_positive"),
        Index("ix_cash_movements_session_id", "session_id"),
        Index("ix_cash_movements_hotel_id", "hotel_id"),
    )

    def __repr__(self) -> str:
        return f"<CashMovement(id={self.id}, session={self.session_id}, type={self.movement_type}, amount={self.amount})>"


class CashCloseReport(Base):
    """
    Arqueo de caja: expected vs actual cash at session close.
    Differences are flagged for supervisor review.
    """
    __tablename__ = "cash_close_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id = Column(
        Integer,
        ForeignKey("cash_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    closed_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    expected_balance = Column(Numeric(12, 2), nullable=False)
    declared_balance = Column(Numeric(12, 2), nullable=False)
    difference = Column(Numeric(12, 2), nullable=False)
    difference_approved = Column(Boolean, nullable=False, default=False)
    approved_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    notes = Column(Text, nullable=True)
    closed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    successor_session_id = Column(
        Integer,
        ForeignKey("cash_sessions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )

    session = relationship("CashSession", back_populates="close_report", foreign_keys=[session_id])
    successor_session = relationship("CashSession", foreign_keys=[successor_session_id], uselist=False)
    custody_handoff = relationship(
        "CashCustodyHandoff",
        back_populates="close_report",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_cash_close_reports_hotel_id", "hotel_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<CashCloseReport(id={self.id}, session={self.session_id}, "
            f"expected={self.expected_balance}, declared={self.declared_balance}, "
            f"diff={self.difference})>"
        )


class CashCustodyHandoff(Base):
    """Custody record connecting a closed cash session to its successor."""

    __tablename__ = "cash_custody_handoffs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
    )
    close_report_id = Column(
        Integer,
        ForeignKey("cash_close_reports.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    delivered_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    received_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    delivered_amount = Column(Numeric(12, 2), nullable=False)
    status = Column(
        Enum(
            CashCustodyStatusEnum,
            name="cash_custody_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=CashCustodyStatusEnum.PENDING,
    )
    delivered_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    received_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    close_report = relationship("CashCloseReport", back_populates="custody_handoff")

    __table_args__ = (
        CheckConstraint("delivered_amount >= 0", name="ck_cash_custody_delivered_nonneg"),
        Index("ix_cash_custody_handoffs_hotel_status", "hotel_id", "status"),
    )
