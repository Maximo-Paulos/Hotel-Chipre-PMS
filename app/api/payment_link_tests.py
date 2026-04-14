from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.schemas.payment_link_test import PaymentLinkTestCreate, PaymentLinkTestRead
from app.services.payment_link_test_service import (
    PaymentLinkTestError,
    cancel_mercadopago_payment_link_test,
    create_mercadopago_payment_link_test,
    list_payment_link_tests,
    refresh_mercadopago_payment_link_test,
    refresh_mercadopago_payment_link_test_by_reference,
    validate_mercadopago_webhook_signature,
)

router = APIRouter(prefix="/api/payment-link-tests", tags=["Payment Link Tests"])


@router.get("/mercadopago", response_model=list[PaymentLinkTestRead])
@router.get("", response_model=list[PaymentLinkTestRead])
@router.get("/", response_model=list[PaymentLinkTestRead])
def list_tests(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    tests = list_payment_link_tests(db, context.hotel_id)
    db.commit()
    return tests


@router.post("/mercadopago", response_model=PaymentLinkTestRead, status_code=status.HTTP_201_CREATED)
def create_mercadopago_test(
    payload: PaymentLinkTestCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        test = create_mercadopago_payment_link_test(db, context.hotel_id, payload)
        db.commit()
        db.refresh(test)
        return test
    except PaymentLinkTestError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"No se pudo crear el link de pago: {exc}")


@router.post("/mercadopago/{test_id}/refresh", response_model=PaymentLinkTestRead)
@router.post("/{test_id}/refresh", response_model=PaymentLinkTestRead)
def refresh_test(
    test_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        test = refresh_mercadopago_payment_link_test(db, context.hotel_id, test_id)
        db.commit()
        db.refresh(test)
        return test
    except PaymentLinkTestError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"No se pudo refrescar el estado del pago: {exc}")


@router.post("/mercadopago/{test_id}/cancel", response_model=PaymentLinkTestRead)
@router.post("/{test_id}/cancel", response_model=PaymentLinkTestRead)
def cancel_test(
    test_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        test = cancel_mercadopago_payment_link_test(db, context.hotel_id, test_id)
        db.commit()
        db.refresh(test)
        return test
    except PaymentLinkTestError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"No se pudo cancelar el link de pago: {exc}")


@router.post("/mercadopago/webhook")
async def mercadopago_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    external_reference = request.query_params.get("external_reference")
    hotel_id = request.query_params.get("hotel_id")
    payload = {}
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    if not external_reference and isinstance(payload, dict):
        data = payload.get("data") or {}
        if isinstance(data, dict):
            external_reference = data.get("external_reference") or payload.get("external_reference")

    if not external_reference:
        return {"status": "ignored", "reason": "external_reference_missing"}

    data_id = request.query_params.get("data.id") or request.query_params.get("data_id") or request.query_params.get("id")
    if not data_id and isinstance(payload, dict):
        data = payload.get("data") or {}
        if isinstance(data, dict):
            data_id = data.get("id") or data.get("id_url")

    try:
        validate_mercadopago_webhook_signature(
            settings.MERCADOPAGO_WEBHOOK_SECRET,
            data_id=str(data_id or ""),
            request_id=request.headers.get("x-request-id") or request.headers.get("X-Request-Id"),
            signature_header=request.headers.get("x-signature") or request.headers.get("X-Signature"),
        )
    except PaymentLinkTestError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    try:
        record = refresh_mercadopago_payment_link_test_by_reference(
            db,
            str(external_reference),
            hotel_id=int(hotel_id) if hotel_id and hotel_id.isdigit() else None,
        )
        db.commit()
    except PaymentLinkTestError as exc:
        db.rollback()
        return {"status": "error", "reason": str(exc)}
    except Exception as exc:
        db.rollback()
        return {"status": "error", "reason": f"{exc}"}

    if not record:
        return {"status": "ignored", "reason": "payment_link_not_found"}
    return {"status": "ok", "payment_link_test_id": record.id, "payment_status": record.status}
