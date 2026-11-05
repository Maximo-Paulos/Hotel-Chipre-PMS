"""Auditable, single-use currency conversion amounts approved per reservation."""
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
    UniqueConstraint,
    text,
)

from app.database import Base


class ManualFxPaymentQuote(Base):
    """A manager-approved tender/base amount pair for one reservation payment."""

    __tablename__ = "manual_fx_payment_quotes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reservation_id = Column(Integer, nullable=False)
    payment_method = Column(String(50), nullable=False)
    reservation_currency_code = Column(String(3), nullable=False)
    tender_currency_code = Column(String(3), nullable=False)
    reservation_amount = Column(Numeric(12, 2), nullable=False)
    tender_amount = Column(Numeric(12, 2), nullable=False)
    reason = Column(String(240), nullable=False)
    surcharge_quote_snapshot = Column(JSON, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    consumed_transaction_id = Column(Integer, nullable=True)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    superseded_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("reservation_amount > 0", name="ck_manual_fx_quote_reservation_amount_positive"),
        CheckConstraint("tender_amount > 0", name="ck_manual_fx_quote_tender_amount_positive"),
        CheckConstraint(
            "reservation_currency_code <> tender_currency_code",
            name="ck_manual_fx_quote_distinct_currencies",
        ),
        CheckConstraint(
            "length(trim(reason)) > 0",
            name="ck_manual_fx_quote_reason_nonempty",
        ),
        CheckConstraint(
            "(consumed_at IS NULL AND consumed_transaction_id IS NULL) OR "
            "(consumed_at IS NOT NULL AND consumed_transaction_id IS NOT NULL)",
            name="ck_manual_fx_quote_consumption_pair",
        ),
        CheckConstraint(
            "consumed_at IS NULL OR superseded_at IS NULL",
            name="ck_manual_fx_quote_not_consumed_and_superseded",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_manual_fx_quote_hotel_reservation",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "consumed_transaction_id"],
            ["transactions.hotel_id", "transactions.id"],
            name="fk_manual_fx_quote_consumed_transaction",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("hotel_id", "id", name="uq_manual_fx_quote_hotel_id_id"),
        Index(
            "uq_manual_fx_quote_active_reservation_method_currency",
            "hotel_id",
            "reservation_id",
            "payment_method",
            "tender_currency_code",
            unique=True,
            postgresql_where=text("consumed_at IS NULL AND superseded_at IS NULL"),
            sqlite_where=text("consumed_at IS NULL AND superseded_at IS NULL"),
        ),
        Index("ix_manual_fx_quotes_hotel_reservation", "hotel_id", "reservation_id", "created_at"),
    )
