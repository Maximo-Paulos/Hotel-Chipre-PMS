from __future__ import annotations

import base64
import binascii
import json
import re
import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.company_document import CompanyDocument, CompanyDocumentStatusEnum, CompanyDocumentTypeEnum
from app.models.reservation import Reservation
from app.models.security_audit_log import SecurityAuditLog
from app.models.stored_object import StoredObject, StoredObjectStatusEnum
from app.services.object_storage import ObjectStorageError, get_object_storage
from app.services.stored_object_service import register_uploaded_object


class CompanyDocumentError(Exception):
    """Raised for invalid company document operations."""


MAX_COMPANY_DOCUMENT_BYTES = 5 * 1024 * 1024


def _decode_company_pdf(content_base64: str) -> bytes:
    raw = (content_base64 or "").strip()
    if raw.startswith("data:"):
        header, separator, raw = raw.partition(",")
        if not separator or not header.lower().startswith("data:application/pdf;base64"):
            raise CompanyDocumentError("El voucher debe ser un archivo PDF válido")
    try:
        content = base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise CompanyDocumentError("El voucher debe ser un archivo PDF válido") from exc
    if not content or len(content) > MAX_COMPANY_DOCUMENT_BYTES:
        raise CompanyDocumentError("El PDF debe pesar como máximo 5 MB")
    if not content.startswith(b"%PDF-"):
        raise CompanyDocumentError("El contenido del archivo no coincide con un PDF")
    return content


def _safe_company_filename(filename: str) -> str:
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", basename.strip())[:255]
    if not cleaned.lower().endswith(".pdf"):
        cleaned = f"{cleaned or 'voucher'}.pdf"
    return cleaned or "voucher.pdf"


def _get_reservation(db: Session, *, hotel_id: int, reservation_id: int) -> Reservation:
    reservation = (
        db.query(Reservation)
        .filter(
            Reservation.id == reservation_id,
            Reservation.hotel_id == hotel_id,
            Reservation.deleted_at.is_(None),
        )
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


def _get_reservation_company(
    db: Session,
    *,
    hotel_id: int,
    reservation: Reservation,
    company_id: int | None,
) -> Company | None:
    if reservation.company_id is None:
        if company_id is not None:
            raise CompanyDocumentError("A company document requires a reservation linked to that company")
        return None
    if company_id is not None and company_id != reservation.company_id:
        raise CompanyDocumentError("Document company does not match reservation company")
    return _get_company(db, hotel_id=hotel_id, company_id=reservation.company_id)


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
    stored_object_id: str | None = None,
    requires_signature: bool = False,
    notes: str | None = None,
) -> CompanyDocument:
    reservation = _get_reservation(db, hotel_id=hotel_id, reservation_id=reservation_id)
    reservation_company = _get_reservation_company(
        db,
        hotel_id=hotel_id,
        reservation=reservation,
        company_id=company_id,
    )
    resolved_company_id = reservation_company.id if reservation_company is not None else None
    if stored_object_id is not None:
        stored_object = (
            db.query(StoredObject)
            .filter(
                StoredObject.id == stored_object_id,
                StoredObject.hotel_id == hotel_id,
                StoredObject.status == StoredObjectStatusEnum.READY.value,
                StoredObject.deleted_at.is_(None),
            )
            .one_or_none()
        )
        if stored_object is None:
            raise CompanyDocumentError("Stored document object does not belong to the active hotel")

    document = CompanyDocument(
        hotel_id=hotel_id,
        reservation_id=reservation_id,
        company_id=resolved_company_id,
        doc_type=doc_type,
        status=CompanyDocumentStatusEnum.PENDING,
        file_name=file_name,
        file_url=file_url,
        stored_object_id=stored_object_id,
        requires_signature=requires_signature or doc_type == CompanyDocumentTypeEnum.SIGNATURE_REQUIRED,
        notes=notes,
        created_by_user_id=user_id,
    )
    db.add(document)
    db.flush()
    return document


def upload_company_document(
    db: Session,
    *,
    hotel_id: int,
    user_id: int | None,
    reservation_id: int,
    company_id: int | None,
    doc_type: CompanyDocumentTypeEnum,
    file_name: str,
    content_base64: str,
    requires_signature: bool = False,
    notes: str | None = None,
) -> CompanyDocument:
    """Store a tenant-scoped PDF privately and link it to a company reservation."""
    content = _decode_company_pdf(content_base64)
    safe_filename = _safe_company_filename(file_name)
    reservation = _get_reservation(db, hotel_id=hotel_id, reservation_id=reservation_id)
    reservation_company = _get_reservation_company(
        db,
        hotel_id=hotel_id,
        reservation=reservation,
        company_id=company_id,
    )
    resolved_company_id = reservation_company.id if reservation_company is not None else None
    company_requires_signature = reservation_company.requires_signature if reservation_company is not None else False
    effective_requires_signature = requires_signature or company_requires_signature
    object_key = f"company-vouchers/{hotel_id}/{secrets.token_urlsafe(24)}.pdf"
    try:
        stored_object = register_uploaded_object(
            db,
            hotel_id=hotel_id,
            purpose="company_voucher",
            object_key=object_key,
            data=content,
            content_type="application/pdf",
            created_by_user_id=user_id,
        )
        document = create_document(
            db,
            hotel_id=hotel_id,
            user_id=user_id,
            reservation_id=reservation_id,
            company_id=company_id,
            doc_type=doc_type,
            file_name=safe_filename,
            stored_object_id=stored_object.id,
            requires_signature=effective_requires_signature,
            notes=notes,
        )
        db.add(
            SecurityAuditLog(
                hotel_id=hotel_id,
                user_id=user_id,
                action="company_document.uploaded",
                resource_type="company_document",
                resource_id=str(document.id),
                details=json.dumps(
                    {
                        "document_id": document.id,
                        "reservation_id": reservation_id,
                        "company_id": document.company_id,
                        "doc_type": doc_type.value,
                        "stored_object_id": stored_object.id,
                    },
                    sort_keys=True,
                ),
            )
        )
        db.flush()
    except Exception:
        db.rollback()
        try:
            get_object_storage().delete(object_key)
        except Exception:
            pass
        raise
    document._uncommitted_object_key = object_key
    return document


def get_company_document_bytes(
    db: Session, *, hotel_id: int, document_id: int
) -> tuple[bytes, str]:
    document = (
        db.query(CompanyDocument)
        .filter(
            CompanyDocument.id == document_id,
            CompanyDocument.hotel_id == hotel_id,
            CompanyDocument.deleted_at.is_(None),
            CompanyDocument.stored_object_id.isnot(None),
        )
        .one_or_none()
    )
    if document is None:
        raise CompanyDocumentError("Company document is not available")
    stored = (
        db.query(StoredObject)
        .filter(
            StoredObject.id == document.stored_object_id,
            StoredObject.hotel_id == hotel_id,
            StoredObject.purpose == "company_voucher",
            StoredObject.status == StoredObjectStatusEnum.READY.value,
            StoredObject.deleted_at.is_(None),
        )
        .one_or_none()
    )
    if stored is None:
        raise CompanyDocumentError("Company document is not available")
    try:
        return get_object_storage().get_bytes(stored.object_key), _safe_company_filename(document.file_name or "voucher.pdf")
    except ObjectStorageError as exc:
        raise CompanyDocumentError("Company document is not available") from exc


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
        .filter(
            CompanyDocument.id == document_id,
            CompanyDocument.hotel_id == hotel_id,
            CompanyDocument.deleted_at.is_(None),
        )
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
        .filter(
            CompanyDocument.hotel_id == hotel_id,
            CompanyDocument.company_id == company_id,
            CompanyDocument.deleted_at.is_(None),
        )
        .order_by(CompanyDocument.created_at.desc(), CompanyDocument.id.desc())
        .all()
    )


def list_documents_for_reservation(db: Session, *, hotel_id: int, reservation_id: int) -> list[CompanyDocument]:
    return (
        db.query(CompanyDocument)
        .filter(
            CompanyDocument.hotel_id == hotel_id,
            CompanyDocument.reservation_id == reservation_id,
            CompanyDocument.deleted_at.is_(None),
        )
        .order_by(CompanyDocument.created_at.desc(), CompanyDocument.id.desc())
        .all()
    )
