"""Manual bank-transfer evidence and approval lifecycle."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class PaymentProofStatusEnum(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PaymentProof(Base):
    """Private image evidence awaiting explicit staff confirmation."""

    __tablename__ = "payment_proofs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False, index=True)
    reservation_id = Column(Integer, nullable=False, index=True)
    transaction_id = Column(Integer, nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="ARS")
    payment_method = Column(String(30), nullable=False, default="bank_transfer")
    status = Column(String(20), nullable=False, default=PaymentProofStatusEnum.PENDING.value, index=True)
    storage_key = Column(String(255), nullable=False, unique=True)
    original_filename = Column(String(255), nullable=True)
    content_type = Column(String(80), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    sha256_hex = Column(String(64), nullable=False)
    submitted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    reviewed_at = Column(DateTime, nullable=True)

    transaction = relationship("Transaction", foreign_keys=[transaction_id], lazy="joined")
    blob = relationship(
        "PaymentProofBlob",
        back_populates="proof",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_proofs_amount_positive"),
        CheckConstraint("file_size_bytes > 0", name="ck_payment_proofs_file_size_positive"),
        CheckConstraint("payment_method = 'bank_transfer'", name="ck_payment_proofs_bank_transfer_only"),
        ForeignKeyConstraint(
            ["hotel_id", "reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_payment_proofs_hotel_reservation",
            ondelete="CASCADE",
        ),
        UniqueConstraint("transaction_id"),
        UniqueConstraint("hotel_id", "id", name="uq_payment_proofs_hotel_id_id"),
        ForeignKeyConstraint(
            ["hotel_id", "transaction_id"],
            ["transactions.hotel_id", "transactions.id"],
            name="fk_payment_proofs_hotel_transaction",
        ),
        UniqueConstraint("hotel_id", "sha256_hex", name="uq_payment_proofs_hotel_sha256"),
        Index("ix_payment_proofs_hotel_reservation_status", "hotel_id", "reservation_id", "status"),
    )


class PaymentProofBlob(Base):
    """Private binary payload kept separately from queryable proof metadata."""

    __tablename__ = "payment_proof_blobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False, index=True)
    proof_id = Column(Integer, nullable=False, unique=True, index=True)
    # Nullable (legacy): new rows upload bytes to object storage and only keep
    # object_key/byte_size here; content stays populated only for rows written
    # before the object-storage migration (see alembic
    # 20260901_payment_proof_object_storage).
    content = Column(LargeBinary, nullable=True)
    content_type = Column(String(80), nullable=False)
    sha256_hex = Column(String(64), nullable=False)
    object_key = Column(String(255), nullable=True, unique=True)
    byte_size = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    proof = relationship("PaymentProof", back_populates="blob", uselist=False)

    __table_args__ = (
        CheckConstraint(
            "(content IS NOT NULL AND length(content) > 0) OR (object_key IS NOT NULL)",
            name="ck_payment_proof_blobs_content_or_object_key",
        ),
        CheckConstraint("length(sha256_hex) = 64", name="ck_payment_proof_blobs_sha256_length"),
        UniqueConstraint("hotel_id", "id", name="uq_payment_proof_blobs_hotel_id_id"),
        ForeignKeyConstraint(
            ["hotel_id", "proof_id"],
            ["payment_proofs.hotel_id", "payment_proofs.id"],
            name="fk_payment_proof_blobs_hotel_proof",
            ondelete="CASCADE",
        ),
        Index("ix_payment_proof_blobs_hotel_proof", "hotel_id", "proof_id"),
    )
