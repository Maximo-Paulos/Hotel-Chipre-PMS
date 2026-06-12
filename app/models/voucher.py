"""
Hotel voucher (credit) models — refund path 2 per product §8.7.

A HotelVoucher is created when a refund is routed to a hotel credit instead of
returning money to the original payment gateway. The guest can redeem it on a
future reservation; each redemption is tracked in VoucherRedemption.

Invariants:
  - remaining_amount starts at original_amount and decreases with each redemption.
  - remaining_amount >= 0 enforced by CHECK constraint.
  - is_transferable defaults False (non-transferable per §8.7 TODO default).
  - voucher_code is unique within hotel (not globally — hotels use their own codes).
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
    Numeric,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class VoucherStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    PARTIALLY_REDEEMED = "partially_redeemed"
    FULLY_REDEEMED = "fully_redeemed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class HotelVoucher(Base):
    """
    Hotel credit issued to a guest (typically as a refund alternative).
    The code is human-readable and unique within the hotel scope.
    """
    __tablename__ = "hotel_vouchers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
    )
    guest_id = Column(
        Integer,
        ForeignKey("guests.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_reservation_id = Column(
        Integer,
        ForeignKey("reservations.id", ondelete="SET NULL"),
        nullable=True,
    )

    voucher_code = Column(String(50), nullable=False)
    original_amount = Column(Numeric(12, 2), nullable=False)
    remaining_amount = Column(Numeric(12, 2), nullable=False)
    currency_code = Column(String(3), nullable=False, default="ARS")

    status = Column(
        Enum(
            VoucherStatusEnum,
            name="voucher_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=VoucherStatusEnum.ACTIVE,
    )

    is_transferable = Column(Boolean, nullable=False, default=False)
    issued_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)
    issued_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes = Column(Text, nullable=True)

    hotel = relationship("HotelConfiguration", lazy="select")
    guest = relationship("Guest", lazy="select")
    source_reservation = relationship("Reservation", foreign_keys=[source_reservation_id], lazy="select")
    issued_by = relationship("User", lazy="select")
    redemptions = relationship("VoucherRedemption", back_populates="voucher", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("remaining_amount >= 0", name="ck_hotel_vouchers_remaining_nonneg"),
        CheckConstraint("original_amount > 0", name="ck_hotel_vouchers_original_positive"),
        UniqueConstraint("hotel_id", "voucher_code", name="uq_hotel_vouchers_code_per_hotel"),
        Index("ix_hotel_vouchers_hotel_guest", "hotel_id", "guest_id"),
        Index("ix_hotel_vouchers_hotel_status", "hotel_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<HotelVoucher(id={self.id}, hotel={self.hotel_id}, "
            f"code={self.voucher_code!r}, remaining={self.remaining_amount}, status={self.status})>"
        )


class VoucherRedemption(Base):
    """
    Records each partial or full redemption of a HotelVoucher on a reservation.
    """
    __tablename__ = "voucher_redemptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
    )
    voucher_id = Column(
        Integer,
        ForeignKey("hotel_vouchers.id", ondelete="CASCADE"),
        nullable=False,
    )
    reservation_id = Column(
        Integer,
        ForeignKey("reservations.id", ondelete="SET NULL"),
        nullable=True,
    )
    amount_used = Column(Numeric(12, 2), nullable=False)
    redeemed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    redeemed_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    voucher = relationship("HotelVoucher", back_populates="redemptions")
    reservation = relationship("Reservation", lazy="select")
    redeemed_by = relationship("User", lazy="select")

    __table_args__ = (
        CheckConstraint("amount_used > 0", name="ck_voucher_redemptions_amount_positive"),
        Index("ix_voucher_redemptions_voucher_id", "voucher_id"),
        Index("ix_voucher_redemptions_hotel_reservation", "hotel_id", "reservation_id"),
    )

    def __repr__(self) -> str:
        return f"<VoucherRedemption(id={self.id}, voucher={self.voucher_id}, amount={self.amount_used})>"
