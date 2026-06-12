"""
CompanyDocument — attachments/vouchers for company reservations (v72 §3.6).
Tracks PDF vouchers, documents requiring signature, and authorizations.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text,
    Enum, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class CompanyDocumentTypeEnum(str, enum.Enum):
    VOUCHER_PDF = "voucher_pdf"         # PDF voucher to print
    SIGNATURE_REQUIRED = "signature_required"  # must be signed by guest
    AUTHORIZATION = "authorization"     # authorization from company
    EXTENSION = "extension"             # extension sent by company
    OTHER = "other"


class CompanyDocumentStatusEnum(str, enum.Enum):
    PENDING = "pending"
    SIGNED = "signed"
    WAIVED = "waived"
    REJECTED = "rejected"


class CompanyDocument(Base):
    """
    Document/voucher associated with a company reservation (v72 §3.6).
    If requires_signature=True, reception must see it clearly, download/print,
    and mark as signed before check-in can proceed.
    """
    __tablename__ = "company_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)

    doc_type = Column(
        Enum(
            CompanyDocumentTypeEnum,
            name="company_document_type_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=CompanyDocumentTypeEnum.OTHER,
    )
    status = Column(
        Enum(
            CompanyDocumentStatusEnum,
            name="company_document_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=CompanyDocumentStatusEnum.PENDING,
    )

    file_name = Column(String(300), nullable=True)
    file_url = Column(String(1000), nullable=True)     # storage URL (no cleartext auth)
    requires_signature = Column(Boolean, nullable=False, default=False)
    signed_at = Column(DateTime, nullable=True)
    signed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_company_documents_hotel_reservation", "hotel_id", "reservation_id"),
        Index("ix_company_documents_hotel_company", "hotel_id", "company_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<CompanyDocument(id={self.id}, reservation_id={self.reservation_id}, "
            f"doc_type={self.doc_type}, status={self.status})>"
        )
