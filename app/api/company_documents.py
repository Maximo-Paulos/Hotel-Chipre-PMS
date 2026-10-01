from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_all_permissions, require_permission
from app.models.audit_log import AuditActionEnum
from app.models.company_document import CompanyDocument, CompanyDocumentStatusEnum
from app.schemas.company_document import CompanyDocumentCreate, CompanyDocumentRead, CompanyDocumentStatusUpdate, CompanyDocumentUpload
from app.services.company_document_service import (
    CompanyDocumentError,
    create_document,
    get_company_document_bytes,
    list_documents_for_company,
    list_documents_for_reservation,
    set_signature_status,
    upload_company_document,
)
from app.services import audit_log_service
from app.services.permission_service import PERMISSION_CHECKIN_PERFORM, PERMISSION_COMPANY_MANAGE, PERMISSION_COMPANY_VIEW, PERMISSION_RESERVATION_READ


router = APIRouter(prefix="/api/company-documents", tags=["Company Documents"])


@router.post("/upload", response_model=CompanyDocumentRead, status_code=status.HTTP_201_CREATED)
def upload_company_document_route(
    payload: CompanyDocumentUpload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_MANAGE)),
):
    try:
        document = upload_company_document(
            db,
            hotel_id=context.hotel_id,
            user_id=context.user_id,
            reservation_id=payload.reservation_id,
            company_id=payload.company_id,
            doc_type=payload.doc_type,
            file_name=payload.file_name,
            content_base64=payload.content_base64,
            requires_signature=payload.requires_signature,
            notes=payload.notes,
        )
        document_id = document.id
        object_key = document._uncommitted_object_key
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            persisted = db.query(CompanyDocument.id).filter(
                CompanyDocument.id == document_id,
                CompanyDocument.hotel_id == context.hotel_id,
            ).first()
            if persisted is None:
                from app.services.object_storage import get_object_storage

                try:
                    get_object_storage().delete(object_key)
                except Exception:
                    pass
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No se pudo confirmar el guardado del voucher.") from exc
        db.refresh(document)
        document.__dict__.pop("_uncommitted_object_key", None)
        return document
    except CompanyDocumentError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{document_id}/file")
def get_company_document_file(
    document_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    try:
        content, file_name = get_company_document_bytes(db, hotel_id=context.hotel_id, document_id=document_id)
    except CompanyDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company document not found") from exc
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{file_name}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
        },
    )


def _get_document_or_404(db: Session, *, hotel_id: int, document_id: int) -> CompanyDocument:
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company document not found")
    return document


@router.post("", response_model=CompanyDocumentRead, status_code=status.HTTP_201_CREATED)
def create_company_document(
    payload: CompanyDocumentCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_MANAGE)),
):
    try:
        document = create_document(
            db,
            hotel_id=context.hotel_id,
            user_id=context.user_id,
            reservation_id=payload.reservation_id,
            company_id=payload.company_id,
            doc_type=payload.doc_type,
            file_name=payload.file_name,
            file_url=payload.file_url,
            stored_object_id=payload.stored_object_id,
            requires_signature=payload.requires_signature,
            notes=payload.notes,
        )
        db.commit()
        db.refresh(document)
        return document
    except CompanyDocumentError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{document_id}", response_model=CompanyDocumentRead)
def get_company_document(
    document_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_all_permissions(PERMISSION_COMPANY_MANAGE, PERMISSION_COMPANY_VIEW)),
):
    return _get_document_or_404(db, hotel_id=context.hotel_id, document_id=document_id)


@router.get("/company/{company_id}", response_model=list[CompanyDocumentRead])
def list_company_documents(
    company_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_all_permissions(PERMISSION_COMPANY_MANAGE, PERMISSION_COMPANY_VIEW)),
):
    return list_documents_for_company(db, hotel_id=context.hotel_id, company_id=company_id)


@router.get("/reservation/{reservation_id}", response_model=list[CompanyDocumentRead])
def list_reservation_documents(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    return list_documents_for_reservation(db, hotel_id=context.hotel_id, reservation_id=reservation_id)


@router.post("/{document_id}/mark-signed", response_model=CompanyDocumentRead)
def mark_company_document_signed_for_checkin(
    document_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CHECKIN_PERFORM)),
):
    try:
        document = set_signature_status(
            db,
            hotel_id=context.hotel_id,
            user_id=context.user_id,
            document_id=document_id,
            status=CompanyDocumentStatusEnum.SIGNED,
        )
        db.commit()
        db.refresh(document)
        return document
    except CompanyDocumentError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{document_id}/status", response_model=CompanyDocumentRead)
def patch_company_document_status(
    document_id: int,
    payload: CompanyDocumentStatusUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_MANAGE)),
):
    try:
        document = set_signature_status(
            db,
            hotel_id=context.hotel_id,
            user_id=context.user_id,
            document_id=document_id,
            status=payload.status,
        )
        db.commit()
        db.refresh(document)
        return document
    except CompanyDocumentError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company_document(
    document_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_MANAGE)),
):
    document = _get_document_or_404(db, hotel_id=context.hotel_id, document_id=document_id)
    before = audit_log_service.model_snapshot(document)
    document.deleted_at = datetime.now(timezone.utc)
    document.deleted_by_user_id = context.user_id
    db.commit()
    db.refresh(document)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="company_documents",
        record_id=document.id,
        action=AuditActionEnum.DELETE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(document),
    )
    return None
