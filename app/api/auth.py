"""
Auth endpoints: register, login, email verification and password reset.
Verification and reset codes are persisted in the database.
"""
from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters.memory_tokens import token_store
from app.adapters.rate_limiter import login_limiter, reset_request_limiter, verify_request_limiter
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    RequestCode,
    ResetPasswordRequest,
    ResetCodeValidationResponse,
    UserInfo,
    VerifyCodeRequest,
)
from app.services.email_service import (
    mailer,
    send_reset_password_email,
    send_verification_email,
    send_verification_success_email,
)
from app.services.hotel_service import get_or_create_hotel_for_owner, get_memberships_for_user
from app.services.security import create_access_token, hash_password, verify_password
from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _generate_code() -> str:
    return str(secrets.randbelow(900000) + 100000)


def _build_auth_response(db: Session, user: User, requested_hotel_id: int | None = None) -> AuthResponse:
    memberships = get_memberships_for_user(db, user.id)
    memberships_by_hotel = {m.hotel_id: m for m in memberships if m.status == "active"}
    if not memberships_by_hotel:
        raise HTTPException(
            status_code=403,
            detail="La cuenta no tiene acceso a ningun hotel activo. Pedile al owner que te invite nuevamente.",
        )
    hotel_ids = list(memberships_by_hotel.keys())
    if requested_hotel_id is not None and requested_hotel_id not in memberships_by_hotel:
        raise HTTPException(status_code=403, detail="No tenes acceso al hotel solicitado")
    hotel_id = requested_hotel_id if requested_hotel_id is not None else hotel_ids[0]
    active_membership = memberships_by_hotel[hotel_id]
    token = create_access_token(
        subject=user.id,
        extra={
            "email": user.email,
            "role": active_membership.role,
            "verified": user.is_verified,
            "hotel_id": hotel_id,
            "hotel_ids": hotel_ids,
        },
    )
    return AuthResponse(
        access_token=token,
        hotel_id=hotel_id,
        user=UserInfo(
            id=user.id,
            email=user.email,
            role=active_membership.role,
            is_verified=user.is_verified,
            is_active=user.is_active,
        ),
        requires_verification=not user.is_verified,
        hotel_ids=hotel_ids,
    )


def _issue_email_token(db: Session, email: str, token_type: str) -> str:
    code = _generate_code()
    token_store.issue(db, token_type=token_type, subject_key=email, code=code, ttl_minutes=15)
    return code


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
    # Create hotel + membership + subscription for the new owner.
    get_or_create_hotel_for_owner(db, user.email)
    db.commit()

    code = _issue_email_token(db, payload.email, "email_verification")
    db.commit()
    if mailer.configured:
        send_verification_email(payload.email, code)

    return _build_auth_response(db, user)


@router.post("/request-verify")
def request_verify(payload: RequestCode, db: Session = Depends(get_db)):
    key = payload.email.lower()
    if not verify_request_limiter.allow(key, db=db):
        db.commit()
        raise HTTPException(status_code=429, detail="Demasiados intentos de verificacion. Espera unos minutos.")
    db.commit()

    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if not user or user.is_verified:
        return {"sent": True}

    code = _issue_email_token(db, payload.email, "email_verification")
    db.commit()
    if mailer.configured:
        send_verification_email(payload.email, code)
    return {"sent": True}


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    key = payload.email.lower()
    settings = get_settings()
    login_limiter.limit = getattr(settings, "LOGIN_RATE_LIMIT", 5)
    if not login_limiter.allow(key, db=db):
        db.commit()
        raise HTTPException(status_code=429, detail="Demasiados intentos. Espera e intenta de nuevo.")
    db.commit()

    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales invalidas")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario deshabilitado")

    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    login_limiter.reset(key, db=db)
    db.commit()
    return _build_auth_response(db, user)


@router.post("/verify-email", response_model=AuthResponse)
def verify_email(payload: VerifyCodeRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if not user or not token_store.verify(db, "email_verification", payload.email, payload.code):
        raise HTTPException(status_code=400, detail="Codigo invalido o expirado")
    user.is_verified = True
    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    send_verification_success_email(user.email)
    return _build_auth_response(db, user)


@router.post("/request-reset")
def request_reset(payload: RequestCode, db: Session = Depends(get_db)):
    key = payload.email.lower()
    settings = get_settings()
    reset_request_limiter.limit = getattr(settings, "RESET_RATE_LIMIT", reset_request_limiter.limit)
    if not reset_request_limiter.allow(key, db=db):
        db.commit()
        raise HTTPException(status_code=429, detail="Demasiados intentos de reset. Espera unos minutos.")
    db.commit()

    response = {"sent": True}
    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if user and user.is_verified:
        code = _issue_email_token(db, payload.email, "password_reset")
        db.commit()
        if mailer.configured:
            send_reset_password_email(payload.email, code)
    return response


@router.post("/validate-reset", response_model=ResetCodeValidationResponse)
def validate_reset(payload: VerifyCodeRequest, db: Session = Depends(get_db)):
    """Validate reset code without changing password (paso previo en UI)."""
    is_valid = token_store.verify(db, "password_reset", payload.email, payload.code, consume=False)
    return ResetCodeValidationResponse(valid=is_valid)


@router.post("/reset-password", response_model=AuthResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if not user or not token_store.verify(db, "password_reset", payload.email, payload.code):
        raise HTTPException(status_code=400, detail="Codigo invalido o expirado")
    user.password_hash = hash_password(payload.new_password)
    user.is_verified = True
    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _build_auth_response(db, user)


@router.get("/me", response_model=UserInfo)
def me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memberships = get_memberships_for_user(db, current_user.id)
    active_membership = next((m for m in memberships if m.status == "active"), None)
    return UserInfo(
        id=current_user.id,
        email=current_user.email,
        role=active_membership.role if active_membership else (current_user.role or "owner"),
        is_verified=current_user.is_verified,
        is_active=current_user.is_active,
    )
