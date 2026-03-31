"""
Endpoints to trigger verification/reset emails.
In prod, codes should be persisted (DB/Redis). Here we use an in-memory store for Stage 1.
"""
import secrets

from fastapi import APIRouter, HTTPException

from app.adapters.memory_tokens import token_store
from app.services.email_service import mailer, send_reset_password_email, send_verification_email

router = APIRouter(prefix="/api/email", tags=["Email"])


def _generate_code() -> str:
    return str(secrets.randbelow(900000) + 100000)  # 6-digit numeric code


@router.post("/verify")
def send_verification(to: str):
    if not mailer.configured:
        raise HTTPException(status_code=503, detail="SMTP not configured")
    code = _generate_code()
    token_store.set(to, code, ttl_minutes=15)
    send_verification_email(to, code)
    return {"sent": True}


@router.post("/reset")
def send_reset(to: str):
    if not mailer.configured:
        raise HTTPException(status_code=503, detail="SMTP not configured")
    code = _generate_code()
    token_store.set(to, code, ttl_minutes=15)
    send_reset_password_email(to, code)
    return {"sent": True}


@router.post("/verify-code")
def verify_code(email: str, code: str):
    if token_store.verify(email, code):
        return {"valid": True}
    raise HTTPException(status_code=400, detail="Código inválido o expirado")
