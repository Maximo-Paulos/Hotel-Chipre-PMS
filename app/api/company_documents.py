from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.models.company_document import CompanyDocument
from app.schemas.company_document import CompanyDocumentCreate, CompanyDocumentRead, CompanyDocumentStatusUpdate
from app.services.company_document_service import (
    CompanyDocumentError,
    create_document,
    list_documents_for_company,
    list_documents_for_reservation,
    set_signature_status,
)
from app.services.permission_service import PERMISSION_COMPANY_MANAGE


router = APIRouter(prefix="/api/company-documents", tags=["Company Documents"])


def _get_document_or_404(db: Session, *, hotel_id: int, document_id: int) -> CompanyDocument:
    document = (
        db.query(CompanyDocument)
        .filter(CompanyDocument.id == document_id, CompanyDocument.hotel_id == hotel_id)
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
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_MANAGE)),
):
    return _get_document_or_404(db, hotel_id=context.hotel_id, document_id=document_id)


@router.get("/company/{company_id}", response_model=list[CompanyDocumentRead])
def list_company_documents(
    company_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_MANAGE)),
):
    return list_documents_for_company(db, hotel_id=context.hotel_id, company_id=company_id)


@router.get("/reservation/{reservation_id}", response_model=list[CompanyDocumentRead])
def list_reservation_documents(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_MANAGE)),
):
    return list_documents_for_reservation(db, hotel_id=context.hotel_id, reservation_id=reservation_id)


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
    db.delete(document)
    db.commit()
    return None
