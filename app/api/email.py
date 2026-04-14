"""
Endpoints to trigger verification/reset emails.
These use persisted one-time tokens.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.adapters.memory_tokens import token_store
from app.database import get_db
from app.models.user import User
from app.services.email_service import mailer, send_reset_password_email, send_verification_email

router = APIRouter(prefix="/api/email", tags=["Email"])


def _generate_code() -> str:
    return str(secrets.randbelow(900000) + 100000)  # 6-digit numeric code


@router.post("/verify")
def send_verification(to: str, db: Session = Depends(get_db)):
    if not mailer.configured:
        raise HTTPException(status_code=503, detail="SMTP not configured")
    user = db.query(User).filter(User.email.ilike(to)).first()
    if not user:
        return {"sent": True}
    code = _generate_code()
    token_store.issue(db, "email_verification", to, code, ttl_minutes=15)
    db.commit()
    send_verification_email(to, code)
    return {"sent": True}


@router.post("/reset")
def send_reset(to: str, db: Session = Depends(get_db)):
    if not mailer.configured:
        raise HTTPException(status_code=503, detail="SMTP not configured")
    user = db.query(User).filter(User.email.ilike(to)).first()
    if not user or not user.is_verified:
        return {"sent": True}
    code = _generate_code()
    token_store.issue(db, "password_reset", to, code, ttl_minutes=15)
    db.commit()
    send_reset_password_email(to, code)
    return {"sent": True}


@router.post("/verify-code")
def verify_code(email: str, code: str, db: Session = Depends(get_db)):
    if token_store.verify(db, "email_verification", email, code):
        db.commit()
        return {"valid": True}
    raise HTTPException(status_code=400, detail="Codigo invalido o expirado")
