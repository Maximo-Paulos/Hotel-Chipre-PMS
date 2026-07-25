"""Secure manual transfer-proof submission and approval."""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
import secrets
import warnings
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.payment_proof import PaymentProof, PaymentProofBlob, PaymentProofStatusEnum
from app.models.reservation import Reservation
from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum
from app.schemas.transaction import PaymentRequest
from app.services.financial_ledger import operational_balance_due
from app.services.payment_service import PaymentError, process_payment
from app.services.audit_log_service import queue_audit_log


class PaymentProofError(ValueError):
    """Raised for invalid evidence or an invalid approval transition."""


MAX_PROOF_BYTES = 5 * 1024 * 1024
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
        raise PaymentProofError("El comprobante debe pesar entre 1 byte y 5 MB")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                image_format = (image.format or "").upper()
                image.verify()
            with Image.open(BytesIO(content)) as image:
                image = ImageOps.exif_transpose(image)
                has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
                normalized = image.convert("RGBA" if has_alpha else "RGB")
                output = BytesIO()
                if image_format == "JPEG":
                    normalized.convert("RGB").save(output, format="JPEG", quality=92, optimize=True)
                elif image_format == "PNG":
                    normalized.save(output, format="PNG", optimize=True)
                else:
                    normalized.save(output, format="WEBP", lossless=True, method=6)
                content = output.getvalue()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError, ValueError) as exc:
        raise PaymentProofError("El comprobante debe ser una imagen valida") from exc
    content_type = ALLOWED_FORMATS.get(image_format)
    if content_type is None:
        raise PaymentProofError("Solo se aceptan imagenes JPEG, PNG o WEBP")
    if not content or len(content) > MAX_PROOF_BYTES:
        raise PaymentProofError("El comprobante normalizado debe pesar como maximo 5 MB")
    extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[image_format]
    return content, content_type, extension


def _safe_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", filename.strip())
    return cleaned[:255] or None


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
    # Use the ledger-derived operational balance (room + billing adjustments like
    # consumption charges), not the naive Reservation.balance_due property, which
    # only accounts for total_amount - amount_paid and would reject legitimate
    # transfers that also cover real consumption on the account.
    balance = operational_balance_due(db, hotel_id=hotel_id, reservation=reservation)
    if Decimal(str(amount)) > balance:
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

    storage_key = f"db://payment-proofs/{hotel_id}/{secrets.token_urlsafe(24)}.{extension}"

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
        db.add(
            PaymentProofBlob(
                hotel_id=hotel_id,
                proof_id=proof.id,
                content=content,
                content_type=content_type,
                sha256_hex=digest,
            )
        )
        db.flush()
        queue_audit_log(
            db,
            hotel_id=hotel_id,
            table_name="payment_proofs",
            record_id=proof.id,
            action=AuditActionEnum.CREATE,
            actor_user_id=submitted_by_user_id,
            payload_after={"status": proof.status, "amount": str(proof.amount), "sha256_hex": proof.sha256_hex},
        )
        db.flush()
    except IntegrityError as exc:
        # A concurrent duplicate hash can win between the pre-check and the
        # INSERT. The transaction rollback removes both metadata and blob.
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
    queue_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="payment_proofs",
        record_id=proof.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=reviewed_by_user_id,
        payload_after={"status": proof.status, "transaction_id": proof.transaction_id},
    )
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
    queue_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="payment_proofs",
        record_id=proof.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=reviewed_by_user_id,
        payload_after={"status": proof.status, "rejection_reason": proof.rejection_reason},
    )
    db.flush()
    return proof


def get_transfer_proof_bytes(
    db: Session,
    *,
    hotel_id: int,
    proof_id: int,
) -> tuple[bytes, str, str | None]:
    """Read private proof bytes only after tenant-scoped authorization."""
    proof = get_transfer_proof(db, hotel_id=hotel_id, proof_id=proof_id)
    blob = (
        db.query(PaymentProofBlob)
        .filter(PaymentProofBlob.hotel_id == hotel_id, PaymentProofBlob.proof_id == proof.id)
        .one_or_none()
    )
    if blob is None:
        raise PaymentProofError("Archivo de comprobante no encontrado")
    return bytes(blob.content), blob.content_type, proof.original_filename
