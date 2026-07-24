from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.schemas.payment_proof import PaymentProofCreate, PaymentProofRead, PaymentProofReject
from app.services.payment_proof_service import (
    PaymentProofError,
    approve_transfer_proof,
    get_transfer_proof,
    list_transfer_proofs,
    proof_file_path,
    reject_transfer_proof,
    submit_transfer_proof,
)


router = APIRouter(prefix="/api/payment-proofs", tags=["Payment proofs"])


@router.post("", response_model=PaymentProofRead, status_code=201)
@router.post("/", response_model=PaymentProofRead, status_code=201, include_in_schema=False)
def submit_proof(
    payload: PaymentProofCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "receptionist")),
):
    try:
        proof = submit_transfer_proof(
            db,
            hotel_id=context.hotel_id,
            reservation_id=payload.reservation_id,
            amount=payload.amount,
            image_base64=payload.image_base64,
            original_filename=payload.original_filename,
            submitted_by_user_id=context.user_id,
        )
        db.commit()
        db.refresh(proof)
        return proof
    except PaymentProofError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[PaymentProofRead])
@router.get("/", response_model=list[PaymentProofRead], include_in_schema=False)
def list_proofs(
    reservation_id: int | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "receptionist")),
):
    return list_transfer_proofs(db, hotel_id=context.hotel_id, reservation_id=reservation_id)


@router.get("/{proof_id}/image")
def get_proof_image(
    proof_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "receptionist")),
):
    try:
        proof = get_transfer_proof(db, hotel_id=context.hotel_id, proof_id=proof_id)
        return FileResponse(proof_file_path(proof), media_type=proof.content_type, filename=proof.original_filename)
    except PaymentProofError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{proof_id}/approve", response_model=PaymentProofRead)
def approve_proof(
    proof_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    try:
        proof = approve_transfer_proof(
            db,
            hotel_id=context.hotel_id,
            proof_id=proof_id,
            reviewed_by_user_id=context.user_id or 0,
        )
        db.commit()
        db.refresh(proof)
        return proof
    except PaymentProofError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{proof_id}/reject", response_model=PaymentProofRead)
def reject_proof(
    proof_id: int,
    payload: PaymentProofReject,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    try:
        proof = reject_transfer_proof(
            db,
            hotel_id=context.hotel_id,
            proof_id=proof_id,
            reviewed_by_user_id=context.user_id or 0,
            reason=payload.reason,
        )
        db.commit()
        db.refresh(proof)
        return proof
    except PaymentProofError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
