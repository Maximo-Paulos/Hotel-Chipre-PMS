"""
Security helpers: password hashing and JWT issuing/validation.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext
import bcrypt as _bcrypt

from app.config import get_settings

# Compatibility shim: bcrypt 4.1.x removed the __about__ attribute that
# passlib 1.7.x expects for backend version detection. Add it if missing to
# avoid noisy warnings on startup.
if not hasattr(_bcrypt, "__about__"):
    class _About:
        __version__ = getattr(_bcrypt, "__version__", "unknown")
    _bcrypt.__about__ = _About()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(subject: str | int, extra: Optional[Dict[str, Any]] = None) -> str:
    settings = get_settings()
    expire_minutes = getattr(settings, "JWT_EXPIRES_MINUTES", 60)
    to_encode: Dict[str, Any] = {"sub": str(subject)}
    if extra:
        to_encode.update(extra)
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    to_encode["exp"] = expire
    secret = getattr(settings, "JWT_SECRET", "change-me")
    algorithm = getattr(settings, "JWT_ALGORITHM", "HS256")
    return jwt.encode(to_encode, secret, algorithm=algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    settings = get_settings()
    secret = getattr(settings, "JWT_SECRET", "change-me")
    algorithm = getattr(settings, "JWT_ALGORITHM", "HS256")
    try:
        return jwt.decode(token, secret, algorithms=[algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
