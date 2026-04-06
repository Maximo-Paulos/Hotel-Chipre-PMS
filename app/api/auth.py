"""
Auth endpoints: register, login, email verification and password reset.
Uses in-memory token store for stage; swap for persistent store in production.
"""
from datetime import datetime, timezone
import secrets
import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters.memory_tokens import token_store
from app.adapters.rate_limiter import login_limiter
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    RequestCode,
    ResetPasswordRequest,
    UserInfo,
    VerifyCodeRequest,
)
from app.services.email_service import (
    mailer,
    send_reset_password_email,
    send_verification_email,
    send_verification_success_email,
)
from app.services.security import create_access_token, hash_password, verify_password
from app.services.hotel_service import get_or_create_hotel_for_owner, get_memberships_for_user
from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _generate_code() -> str:
    return str(secrets.randbelow(900000) + 100000)


def _is_demo_mode() -> bool:
    return os.getenv("DEMO_MODE", "").lower() in {"1", "true", "yes", "on"}


def _build_auth_response(db: Session, user: User, requested_hotel_id: int | None = None) -> AuthResponse:
    memberships = get_memberships_for_user(db, user.id)
    if not memberships:
        hotel = get_or_create_hotel_for_owner(db, user.email)
        memberships = get_memberships_for_user(db, user.id)  # refreshed
    hotel_ids = [m.hotel_id for m in memberships]
    hotel_id = requested_hotel_id if requested_hotel_id in hotel_ids else hotel_ids[0]
    hotel = get_or_create_hotel_for_owner(db, user.email) if hotel_id is None else None
    token = create_access_token(
        subject=user.id,
        extra={
            "email": user.email,
            "role": user.role,
            "verified": user.is_verified,
            "hotel_id": hotel_id,
            "hotel_ids": hotel_ids,
        },
    )
    return AuthResponse(
        access_token=token,
        hotel_id=hotel_id,
        user=UserInfo.model_validate(user),
        requires_verification=not user.is_verified,
        hotel_ids=hotel_ids,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email.ilike(payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese email")

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=payload.role or "owner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # Create hotel + membership + subscription
    get_or_create_hotel_for_owner(db, user.email)
    db.commit()
    get_or_create_hotel_for_owner(db, user.email)

    # Send verification code when SMTP available; always store code for verify endpoint
    code = _generate_code()
    token_store.set(payload.email, code, ttl_minutes=15)
    if mailer.configured:
        send_verification_email(payload.email, code)

    return _build_auth_response(db, user)


@router.post("/request-verify")
def request_verify(payload: RequestCode):
    code = _generate_code()
    token_store.set(payload.email, code, ttl_minutes=15)
    response = {"sent": True, "code": code, "marker": "dev"}
    if mailer.configured:
        send_verification_email(payload.email, code)
    return response


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    key = payload.email.lower()
    settings = get_settings()
    login_limiter.limit = getattr(settings, "LOGIN_RATE_LIMIT", 5)
    if not login_limiter.allow(key):
        raise HTTPException(status_code=429, detail="Demasiados intentos. Esperá e intentá de nuevo.")

    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario deshabilitado")

    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    login_limiter.reset(key)

    if not user.is_verified:
        # Keep response but flag verification pending
        return _build_auth_response(db, user)

    return _build_auth_response(db, user)


@router.post("/verify-email", response_model=AuthResponse)
def verify_email(payload: VerifyCodeRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not token_store.verify(payload.email, payload.code):
        raise HTTPException(status_code=400, detail="Código inválido o expirado")
    user.is_verified = True
    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    send_verification_success_email(user.email)
    return _build_auth_response(db, user)


@router.post("/request-reset")
def request_reset(payload: RequestCode, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    code = _generate_code()
    token_store.set(payload.email, code, ttl_minutes=15)
    response = {"sent": True}
    if user and mailer.configured:
        send_reset_password_email(payload.email, code)
    elif _is_demo_mode():
        response["code"] = code
    return response


@router.post("/reset-password", response_model=AuthResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not token_store.verify(payload.email, payload.code):
        raise HTTPException(status_code=400, detail="Código inválido o expirado")
    user.password_hash = hash_password(payload.new_password)
    user.is_verified = True
    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _build_auth_response(db, user)


@router.get("/me", response_model=UserInfo)
def me(current_user: User = Depends(get_current_user)):
    return UserInfo.model_validate(current_user)
