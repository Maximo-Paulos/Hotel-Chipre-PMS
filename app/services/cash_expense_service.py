"""Manual cash expense submission and approval transitions."""
from __future__ import annotations

import base64
import binascii
import json
import logging
import re
import secrets
import warnings
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cash_expense import CashExpense, CashExpenseStatusEnum
from app.models.cash_register import CashMovementTypeEnum, CashSession, CashSessionStatusEnum
from app.models.security_audit_log import SecurityAuditLog
from app.models.stored_object import StoredObject, StoredObjectStatusEnum
from app.services.cash_register_service import CashRegisterError, add_movement
from app.services.object_storage import ObjectStorageError, get_object_storage
from app.services.stored_object_service import register_uploaded_object


LOGGER = logging.getLogger(__name__)
MAX_RECEIPT_BYTES = 5 * 1024 * 1024
MAX_RECEIPT_PIXELS = 40_000_000
ALLOWED_RECEIPT_FORMATS = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png"), "WEBP": ("image/webp", "webp")}


class CashExpenseError(ValueError):
    """Invalid expense payload or disallowed expense transition."""


def _money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _delete_object_key(object_key: str) -> None:
    try:
        get_object_storage().delete(object_key)
    except Exception as exc:
        LOGGER.error("cash_expense.receipt_cleanup_failed error_type=%s", type(exc).__name__)


def _decode_receipt(raw: str) -> tuple[bytes, str, str]:
    raw_value = (raw or "").strip()
    if raw_value.startswith("data:"):
        _metadata, separator, raw_value = raw_value.partition(",")
        if not separator:
            raise CashExpenseError("La imagen del comprobante no es válida")
    try:
        content = base64.b64decode(raw_value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise CashExpenseError("La imagen del comprobante no es válida") from exc
    if not content or len(content) > MAX_RECEIPT_BYTES:
        raise CashExpenseError("El comprobante debe pesar entre 1 byte y 5 MB")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                image_format = (image.format or "").upper()
                if image.width * image.height > MAX_RECEIPT_PIXELS:
                    raise CashExpenseError("La imagen del comprobante supera el tamaño máximo permitido")
                image.verify()
            with Image.open(BytesIO(content)) as image:
                normalized = ImageOps.exif_transpose(image)
                alpha = normalized.mode in {"RGBA", "LA"} or "transparency" in normalized.info
                normalized = normalized.convert("RGBA" if alpha else "RGB")
                output = BytesIO()
                if image_format == "JPEG":
                    normalized.convert("RGB").save(output, format="JPEG", quality=90, optimize=True)
                elif image_format == "PNG":
                    normalized.save(output, format="PNG", optimize=True)
                elif image_format == "WEBP":
                    normalized.save(output, format="WEBP", lossless=True, method=6)
                else:
                    raise CashExpenseError("Solo se aceptan imágenes JPEG, PNG o WEBP")
                content = output.getvalue()
    except CashExpenseError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError, ValueError) as exc:
        raise CashExpenseError("El comprobante debe ser una imagen válida") from exc

    if not content or len(content) > MAX_RECEIPT_BYTES:
        raise CashExpenseError("El comprobante normalizado debe pesar como máximo 5 MB")
    content_type, extension = ALLOWED_RECEIPT_FORMATS[image_format]
    return content, content_type, extension


def _safe_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    return re.sub(r"[^A-Za-z0-9._-]", "_", filename.strip())[:255] or None


def _require_open_session(db: Session, *, hotel_id: int, session_id: int) -> CashSession:
    # Match the row lock used by cash movements and close_session. This keeps
    # an expense from becoming pending on a session that closes concurrently.
    session = db.execute(
        select(CashSession)
        .where(
            CashSession.hotel_id == hotel_id,
            CashSession.id == session_id,
            CashSession.status == CashSessionStatusEnum.OPEN,
        )
        .with_for_update(of=CashSession)
    ).scalar_one_or_none()
    if session is None:
        raise CashExpenseError("La caja no está abierta o no pertenece a este hotel")
    return session


def create_cash_expense(
    db: Session,
    *,
    hotel_id: int,
    session_id: int,
    recorded_by_user_id: int | None,
    amount: Decimal,
    category: str,
    vendor: str,
    description: str | None,
    receipt_reference: str | None,
    receipt_image_base64: str | None,
    receipt_filename: str | None,
) -> CashExpense:
    session = _require_open_session(db, hotel_id=hotel_id, session_id=session_id)
    value = _money(amount)
    clean_category = (category or "").strip()
    clean_vendor = (vendor or "").strip()
    clean_reference = (receipt_reference or "").strip() or None
    clean_description = (description or "").strip() or None
    if value <= 0 or value > Decimal("9999999999.99"):
        raise CashExpenseError("El importe del gasto debe ser positivo y válido")
    if not clean_category or len(clean_category) > 64:
        raise CashExpenseError("La categoría del gasto es obligatoria")
    if not clean_vendor or len(clean_vendor) > 120:
        raise CashExpenseError("El proveedor del gasto es obligatorio")
    if clean_description and len(clean_description) > 300:
        raise CashExpenseError("La descripción supera el máximo permitido")
    if clean_reference and len(clean_reference) > 120:
        raise CashExpenseError("La referencia del comprobante supera el máximo permitido")
    if not clean_reference and not receipt_image_base64:
        raise CashExpenseError("Ingresá la referencia del comprobante o adjuntá una imagen")

    receipt_object_id = None
    object_key = None
    if receipt_image_base64:
        content, content_type, extension = _decode_receipt(receipt_image_base64)
        object_key = f"cash-expenses/{hotel_id}/{secrets.token_urlsafe(24)}.{extension}"
        try:
            stored = register_uploaded_object(
                db,
                hotel_id=hotel_id,
                purpose="cash_expense_receipt",
                object_key=object_key,
                data=content,
                content_type=content_type,
                created_by_user_id=recorded_by_user_id,
            )
            receipt_object_id = stored.id
        except Exception:
            db.rollback()
            _delete_object_key(object_key)
            raise CashExpenseError("No se pudo guardar el comprobante")

    expense = CashExpense(
        hotel_id=hotel_id,
        session_id=session.id,
        amount=value,
        currency_code=session.currency_code,
        category=clean_category,
        vendor=clean_vendor,
        description=clean_description,
        receipt_reference=clean_reference,
        receipt_filename=_safe_filename(receipt_filename),
        receipt_object_id=receipt_object_id,
        status=CashExpenseStatusEnum.PENDING.value,
        recorded_by_user_id=recorded_by_user_id,
    )
    try:
        db.add(expense)
        db.flush()
        db.add(
            SecurityAuditLog(
                hotel_id=hotel_id,
                user_id=recorded_by_user_id,
                action="cash.expense.recorded",
                resource_type="cash_expense",
                resource_id=str(expense.id),
                details=json.dumps(
                    {
                        "session_id": session.id,
                        "amount": str(value),
                        "currency_code": session.currency_code,
                        "category": clean_category,
                        "status": expense.status,
                    },
                    sort_keys=True,
                ),
            )
        )
        db.flush()
    except Exception:
        db.rollback()
        if object_key:
            _delete_object_key(object_key)
        raise
    if object_key:
        expense._uncommitted_object_key = object_key
    return expense


def list_cash_expenses(db: Session, *, hotel_id: int, status: str | None = None) -> list[CashExpense]:
    query = db.query(CashExpense).filter(CashExpense.hotel_id == hotel_id)
    if status is not None:
        if status not in {item.value for item in CashExpenseStatusEnum}:
            raise CashExpenseError("Estado de gasto inválido")
        query = query.filter(CashExpense.status == status)
    return query.order_by(CashExpense.created_at.desc(), CashExpense.id.desc()).limit(200).all()


def get_cash_expense(db: Session, *, hotel_id: int, expense_id: int, lock: bool = False) -> CashExpense:
    query = db.query(CashExpense).filter(CashExpense.hotel_id == hotel_id, CashExpense.id == expense_id)
    if lock:
        query = query.with_for_update(of=CashExpense)
    expense = query.one_or_none()
    if expense is None:
        raise CashExpenseError("Gasto no encontrado")
    return expense


def approve_cash_expense(
    db: Session,
    *,
    hotel_id: int,
    expense_id: int,
    approved_by_user_id: int,
) -> CashExpense:
    expense = get_cash_expense(db, hotel_id=hotel_id, expense_id=expense_id, lock=True)
    if expense.status == CashExpenseStatusEnum.APPROVED.value:
        return expense
    if expense.status != CashExpenseStatusEnum.PENDING.value:
        raise CashExpenseError("Solo se pueden aprobar gastos pendientes")
    session = _require_open_session(db, hotel_id=hotel_id, session_id=expense.session_id)
    movement = add_movement(
        db,
        hotel_id=hotel_id,
        session_id=session.id,
        recorded_by_user_id=approved_by_user_id,
        movement_type=CashMovementTypeEnum.EXPENSE,
        amount=_money(expense.amount),
        description=f"Gasto aprobado · {expense.category} · {expense.vendor}",
    )
    now = datetime.now(timezone.utc)
    expense.status = CashExpenseStatusEnum.APPROVED.value
    expense.cash_movement_id = movement.id
    expense.approved_by_user_id = approved_by_user_id
    expense.approved_at = now
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=approved_by_user_id,
            action="cash.expense.approved",
            resource_type="cash_expense",
            resource_id=str(expense.id),
            details=json.dumps(
                {"cash_movement_id": movement.id, "session_id": session.id, "amount": str(expense.amount)},
                sort_keys=True,
            ),
        )
    )
    db.flush()
    return expense


def reject_cash_expense(
    db: Session,
    *,
    hotel_id: int,
    expense_id: int,
    rejected_by_user_id: int,
    reason: str,
) -> CashExpense:
    expense = get_cash_expense(db, hotel_id=hotel_id, expense_id=expense_id, lock=True)
    if expense.status == CashExpenseStatusEnum.REJECTED.value:
        return expense
    if expense.status != CashExpenseStatusEnum.PENDING.value:
        raise CashExpenseError("Solo se pueden rechazar gastos pendientes")
    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise CashExpenseError("El rechazo requiere un motivo")
    expense.status = CashExpenseStatusEnum.REJECTED.value
    expense.rejected_by_user_id = rejected_by_user_id
    expense.rejected_at = datetime.now(timezone.utc)
    expense.rejection_reason = clean_reason[:1000]
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=rejected_by_user_id,
            action="cash.expense.rejected",
            resource_type="cash_expense",
            resource_id=str(expense.id),
            details=json.dumps({"session_id": expense.session_id, "reason": expense.rejection_reason}, sort_keys=True),
        )
    )
    db.flush()
    return expense


def get_cash_expense_receipt_bytes(
    db: Session,
    *,
    hotel_id: int,
    expense_id: int,
) -> tuple[bytes, str, str | None]:
    expense = get_cash_expense(db, hotel_id=hotel_id, expense_id=expense_id)
    if not expense.receipt_object_id:
        raise CashExpenseError("Comprobante no encontrado")
    stored = (
        db.query(StoredObject)
        .filter(
            StoredObject.hotel_id == hotel_id,
            StoredObject.id == expense.receipt_object_id,
            StoredObject.purpose == "cash_expense_receipt",
            StoredObject.status == StoredObjectStatusEnum.READY.value,
            StoredObject.deleted_at.is_(None),
        )
        .one_or_none()
    )
    if stored is None:
        raise CashExpenseError("Comprobante no encontrado")
    try:
        content = get_object_storage().get_bytes(stored.object_key)
    except (ObjectStorageError, NotImplementedError) as exc:
        raise CashExpenseError("Comprobante no disponible") from exc
    return content, stored.content_type, expense.receipt_filename


def recover_failed_cash_expense_commit(db: Session, expense: CashExpense) -> tuple[CashExpense | None, bool]:
    """Resolve an uncertain commit before deleting its uploaded receipt."""
    object_key = getattr(expense, "_uncommitted_object_key", None)
    if not object_key:
        return None, False
    db.rollback()
    try:
        persisted = (
            db.query(CashExpense)
            .filter(
                CashExpense.id == expense.id,
                CashExpense.hotel_id == expense.hotel_id,
                CashExpense.receipt_object_id == expense.receipt_object_id,
            )
            .one_or_none()
        )
        if persisted is not None:
            persisted.__dict__.pop("_uncommitted_object_key", None)
            return persisted, True
    except Exception as exc:
        db.rollback()
        LOGGER.error("cash_expense.commit_outcome_unknown error_type=%s", type(exc).__name__)
        return None, False
    _delete_object_key(object_key)
    expense.__dict__.pop("_uncommitted_object_key", None)
    return None, True
