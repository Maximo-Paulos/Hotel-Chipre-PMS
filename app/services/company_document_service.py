from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.company_document import CompanyDocument, CompanyDocumentStatusEnum, CompanyDocumentTypeEnum
from app.models.reservation import Reservation
from app.models.security_audit_log import SecurityAuditLog


class CompanyDocumentError(Exception):
    """Raised for invalid company document operations."""


def _get_reservation(db: Session, *, hotel_id: int, reservation_id: int) -> Reservation:
    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
        .first()
    )
    if reservation is None:
        raise CompanyDocumentError("Reservation does not belong to the active hotel")
    return reservation


def _get_company(db: Session, *, hotel_id: int, company_id: int) -> Company:
    company = (
        db.query(Company)
        .filter(Company.id == company_id, Company.hotel_id == hotel_id)
        .first()
    )
    if company is None:
        raise CompanyDocumentError("Company does not belong to the active hotel")
    return company


def create_document(
    db: Session,
    *,
    hotel_id: int,
    user_id: int | None,
    reservation_id: int,
    company_id: int | None = None,
    doc_type: CompanyDocumentTypeEnum = CompanyDocumentTypeEnum.OTHER,
    file_name: str | None = None,
    file_url: str | None = None,
    requires_signature: bool = False,
    notes: str | None = None,
) -> CompanyDocument:
    reservation = _get_reservation(db, hotel_id=hotel_id, reservation_id=reservation_id)
    resolved_company_id = company_id if company_id is not None else reservation.company_id
    if resolved_company_id is not None:
        _get_company(db, hotel_id=hotel_id, company_id=resolved_company_id)
        if reservation.company_id is not None and reservation.company_id != resolved_company_id:
            raise CompanyDocumentError("Document company does not match reservation company")

    document = CompanyDocument(
        hotel_id=hotel_id,
        reservation_id=reservation_id,
        company_id=resolved_company_id,
        doc_type=doc_type,
        status=CompanyDocumentStatusEnum.PENDING,
        file_name=file_name,
        file_url=file_url,
        requires_signature=requires_signature or doc_type == CompanyDocumentTypeEnum.SIGNATURE_REQUIRED,
        notes=notes,
        created_by_user_id=user_id,
    )
    db.add(document)
    db.flush()
    return document


def set_signature_status(
    db: Session,
    *,
    hotel_id: int,
    user_id: int | None,
    document_id: int,
    status: CompanyDocumentStatusEnum,
) -> CompanyDocument:
    document = (
        db.query(CompanyDocument)
        .filter(CompanyDocument.id == document_id, CompanyDocument.hotel_id == hotel_id)
        .first()
    )
    if document is None:
        raise CompanyDocumentError("Company document does not belong to the active hotel")

    if document.status != CompanyDocumentStatusEnum.PENDING or status not in {
        CompanyDocumentStatusEnum.SIGNED,
        CompanyDocumentStatusEnum.REJECTED,
    }:
        raise CompanyDocumentError("Invalid signature status transition")

    previous_status = document.status
    document.status = status
    if status == CompanyDocumentStatusEnum.SIGNED:
        document.signed_at = datetime.now(timezone.utc)
        document.signed_by_user_id = user_id
    else:
        document.signed_at = None
        document.signed_by_user_id = None

    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=user_id,
            action="company_document.signature_status_changed",
            resource_type="company_document",
            resource_id=str(document.id),
            details=json.dumps(
                {
                    "document_id": document.id,
                    "reservation_id": document.reservation_id,
                    "company_id": document.company_id,
                    "from_status": previous_status.value,
                    "to_status": status.value,
                },
                sort_keys=True,
            ),
        )
    )
    db.flush()
    return document


def list_documents_for_company(db: Session, *, hotel_id: int, company_id: int) -> list[CompanyDocument]:
    return (
        db.query(CompanyDocument)
        .filter(CompanyDocument.hotel_id == hotel_id, CompanyDocument.company_id == company_id)
        .order_by(CompanyDocument.created_at.desc(), CompanyDocument.id.desc())
        .all()
    )


def list_documents_for_reservation(db: Session, *, hotel_id: int, reservation_id: int) -> list[CompanyDocument]:
    return (
        db.query(CompanyDocument)
        .filter(CompanyDocument.hotel_id == hotel_id, CompanyDocument.reservation_id == reservation_id)
        .order_by(CompanyDocument.created_at.desc(), CompanyDocument.id.desc())
        .all()
    )
