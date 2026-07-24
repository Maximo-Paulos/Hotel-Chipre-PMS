"""Secure manual transfer-proof submission and approval."""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
import secrets
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.payment_proof import PaymentProof, PaymentProofStatusEnum
from app.models.reservation import Reservation
from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum
from app.schemas.transaction import PaymentRequest
from app.services.payment_service import PaymentError, process_payment


class PaymentProofError(ValueError):
    """Raised for invalid evidence or an invalid approval transition."""


MAX_PROOF_BYTES = 8 * 1024 * 1024
ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def _decode_image(image_base64: str) -> tuple[bytes, str, str]:
    raw_value = (image_base64 or "").strip()
    if raw_value.startswith("data:"):
        _, separator, raw_value = raw_value.partition(",")
        if not separator:
            raise PaymentProofError("Imagen de comprobante invalida")
    try:
        content = base64.b64decode(raw_value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise PaymentProofError("Imagen de comprobante invalida") from exc
    if not content or len(content) > MAX_PROOF_BYTES:
        raise PaymentProofError("El comprobante debe pesar entre 1 byte y 8 MB")

    try:
        with Image.open(BytesIO(content)) as image:
            image_format = (image.format or "").upper()
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise PaymentProofError("El comprobante debe ser una imagen valida") from exc
    content_type = ALLOWED_FORMATS.get(image_format)
    if content_type is None:
        raise PaymentProofError("Solo se aceptan imagenes JPEG, PNG o WEBP")
    extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[image_format]
    return content, content_type, extension


def _safe_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", filename.strip())
    return cleaned[:255] or None


def _proof_path(storage_key: str) -> Path:
    root = Path(get_settings().PAYMENT_PROOFS_DIR).resolve()
    candidate = (root / storage_key).resolve()
    if root not in candidate.parents:
        raise PaymentProofError("Ruta de comprobante invalida")
    return candidate


def _reservation(db: Session, hotel_id: int, reservation_id: int) -> Reservation:
    row = (
        db.query(Reservation)
        .filter(Reservation.hotel_id == hotel_id, Reservation.id == reservation_id)
        .one_or_none()
    )
    if row is None:
        raise PaymentProofError("Reserva no encontrada para este hotel")
    return row


def submit_transfer_proof(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    amount,
    image_base64: str,
    original_filename: str | None,
    submitted_by_user_id: int | None,
) -> PaymentProof:
    reservation = _reservation(db, hotel_id, reservation_id)
    if amount <= 0:
        raise PaymentProofError("El importe del comprobante debe ser positivo")
    if amount > reservation.balance_due:
        raise PaymentProofError("El importe supera el saldo pendiente de la reserva")

    content, content_type, extension = _decode_image(image_base64)
    digest = hashlib.sha256(content).hexdigest()
    duplicate = (
        db.query(PaymentProof)
        .filter(PaymentProof.hotel_id == hotel_id, PaymentProof.sha256_hex == digest)
        .first()
    )
    if duplicate is not None:
        raise PaymentProofError("Este comprobante ya fue presentado")

    storage_key = f"{hotel_id}/{secrets.token_urlsafe(24)}.{extension}"
    path = _proof_path(storage_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

    proof = PaymentProof(
        hotel_id=hotel_id,
        reservation_id=reservation_id,
        amount=amount,
        currency=(reservation.currency_code or "ARS").upper()[:3],
        payment_method=PaymentMethodEnum.BANK_TRANSFER.value,
        status=PaymentProofStatusEnum.PENDING.value,
        storage_key=storage_key,
        original_filename=_safe_filename(original_filename),
        content_type=content_type,
        file_size_bytes=len(content),
        sha256_hex=digest,
        submitted_by_user_id=submitted_by_user_id,
    )
    try:
        db.add(proof)
        db.flush()
    except IntegrityError as exc:
        # A concurrent duplicate hash can win between the pre-check and the
        # INSERT. Do not leave an orphaned evidence file on that path.
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise PaymentProofError("Este comprobante ya fue presentado") from exc
    return proof


def list_transfer_proofs(db: Session, *, hotel_id: int, reservation_id: int | None = None) -> list[PaymentProof]:
    query = db.query(PaymentProof).filter(PaymentProof.hotel_id == hotel_id)
    if reservation_id is not None:
        query = query.filter(PaymentProof.reservation_id == reservation_id)
    return query.order_by(PaymentProof.created_at.desc(), PaymentProof.id.desc()).all()


def get_transfer_proof(db: Session, *, hotel_id: int, proof_id: int) -> PaymentProof:
    proof = db.query(PaymentProof).filter(PaymentProof.hotel_id == hotel_id, PaymentProof.id == proof_id).one_or_none()
    if proof is None:
        raise PaymentProofError("Comprobante no encontrado")
    return proof


def approve_transfer_proof(
    db: Session,
    *,
    hotel_id: int,
    proof_id: int,
    reviewed_by_user_id: int,
) -> PaymentProof:
    proof = get_transfer_proof(db, hotel_id=hotel_id, proof_id=proof_id)
    if proof.status == PaymentProofStatusEnum.APPROVED.value:
        return proof
    if proof.status == PaymentProofStatusEnum.REJECTED.value:
        raise PaymentProofError("No se puede aprobar un comprobante rechazado")

    try:
        transaction = process_payment(
            db,
            PaymentRequest(
                reservation_id=proof.reservation_id,
                amount=float(proof.amount),
                payment_method=PaymentMethodEnum.BANK_TRANSFER,
                transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
                currency=proof.currency,
                description=f"Transferencia aprobada por comprobante #{proof.id}",
            ),
            hotel_id=hotel_id,
            actor_user_id=reviewed_by_user_id,
            idempotency_key=f"transfer-proof:{proof.id}",
            manual_confirmation=True,
        )
    except (PaymentError, ValueError) as exc:
        raise PaymentProofError(str(exc)) from exc

    proof.status = PaymentProofStatusEnum.APPROVED.value
    proof.transaction = transaction
    proof.transaction_id = transaction.id
    proof.reviewed_by_user_id = reviewed_by_user_id
    proof.reviewed_at = datetime.now(timezone.utc)
    proof.rejection_reason = None
    db.flush()
    return proof


def reject_transfer_proof(
    db: Session,
    *,
    hotel_id: int,
    proof_id: int,
    reviewed_by_user_id: int,
    reason: str,
) -> PaymentProof:
    proof = get_transfer_proof(db, hotel_id=hotel_id, proof_id=proof_id)
    if proof.status == PaymentProofStatusEnum.APPROVED.value:
        raise PaymentProofError("No se puede rechazar un comprobante aprobado")
    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise PaymentProofError("El rechazo requiere un motivo")
    proof.status = PaymentProofStatusEnum.REJECTED.value
    proof.reviewed_by_user_id = reviewed_by_user_id
    proof.reviewed_at = datetime.now(timezone.utc)
    proof.rejection_reason = clean_reason[:2000]
    db.flush()
    return proof


def proof_file_path(proof: PaymentProof) -> Path:
    path = _proof_path(proof.storage_key)
    if not path.is_file():
        raise PaymentProofError("Archivo de comprobante no encontrado")
    return path
