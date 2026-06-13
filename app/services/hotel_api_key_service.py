"""Hotel-scoped public API key lifecycle."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.hotel_api_key import APIKeyPurposeEnum, HotelAPIKey


class HotelAPIKeyError(Exception):
    pass


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _generate_secret() -> str:
    return f"hpk_{secrets.token_urlsafe(32)}"


def issue_key(
    db: Session,
    *,
    hotel_id: int,
    name: str,
    purpose: APIKeyPurposeEnum = APIKeyPurposeEnum.OTHER,
    created_by_user_id: int | None = None,
    expires_at: datetime | None = None,
) -> tuple[HotelAPIKey, str]:
    """Create a key and return the plaintext secret exactly once."""

    clean_name = (name or "").strip()
    if not clean_name:
        raise HotelAPIKeyError("El nombre de la clave es obligatorio")

    secret = _generate_secret()
    key = HotelAPIKey(
        hotel_id=hotel_id,
        created_by_user_id=created_by_user_id,
        name=clean_name,
        purpose=purpose,
        key_prefix=secret[:8],
        key_hash=_hash_secret(secret),
        expires_at=expires_at,
        is_active=True,
    )
    db.add(key)
    db.flush()
    return key, secret


def verify_key(db: Session, secret: str, *, hotel_id: int | None = None) -> HotelAPIKey:
    """Resolve a plaintext key to an active hotel-scoped credential."""

    raw = (secret or "").strip()
    if not raw:
        raise HotelAPIKeyError("API key requerida")

    query = db.query(HotelAPIKey).filter(HotelAPIKey.key_hash == _hash_secret(raw))
    if hotel_id is not None:
        query = query.filter(HotelAPIKey.hotel_id == hotel_id)
    key = query.one_or_none()
    if key is None or not key.is_active:
        raise HotelAPIKeyError("API key invalida")
    now = datetime.now(timezone.utc)
    expires_at = key.expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            raise HotelAPIKeyError("API key expirada")
    key.last_used_at = now
    db.flush()
    return key


def revoke_key(
    db: Session,
    *,
    hotel_id: int,
    key_id: int,
    revoked_by_user_id: int | None = None,
) -> HotelAPIKey:
    key = (
        db.query(HotelAPIKey)
        .filter(HotelAPIKey.id == key_id, HotelAPIKey.hotel_id == hotel_id)
        .one_or_none()
    )
    if key is None:
        raise HotelAPIKeyError("API key no encontrada")
    if key.is_active:
        key.is_active = False
        key.revoked_at = datetime.now(timezone.utc)
        key.revoked_by_user_id = revoked_by_user_id
        db.flush()
    return key


def list_keys(db: Session, *, hotel_id: int) -> list[HotelAPIKey]:
    """List hotel keys. Callers must not serialize key_hash."""

    return (
        db.query(HotelAPIKey)
        .filter(HotelAPIKey.hotel_id == hotel_id)
        .order_by(HotelAPIKey.created_at.desc(), HotelAPIKey.id.desc())
        .all()
    )
