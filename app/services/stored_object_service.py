"""Upload/verify/register object-storage bytes without exposing them in events."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.stored_object import StoredObject, StoredObjectStatusEnum
from app.services.object_storage import ObjectStorageError, get_object_storage


def register_uploaded_object(
    db: Session,
    *,
    hotel_id: int,
    purpose: str,
    object_key: str,
    data: bytes,
    content_type: str,
    created_by_user_id: int | None = None,
) -> StoredObject:
    """Persist pending metadata, upload, stat and mark ready after verification."""
    if not purpose or len(purpose) > 64:
        raise ValueError("object purpose is required and must be at most 64 characters")
    if not data:
        raise ValueError("object data must not be empty")
    digest = hashlib.sha256(data).hexdigest()
    storage = get_object_storage()
    row = StoredObject(
        hotel_id=hotel_id,
        purpose=purpose,
        object_key=object_key,
        backend=(getattr(get_settings(), "OBJECT_STORAGE_BACKEND", "local") or "local").lower(),
        content_type=content_type,
        byte_size=len(data),
        sha256_hex=digest,
        status=StoredObjectStatusEnum.PENDING_UPLOAD.value,
        created_by_user_id=created_by_user_id,
    )
    db.add(row)
    db.flush()
    try:
        storage.put_bytes(object_key, data, content_type=content_type)
        stat = storage.stat(object_key)
        if stat.byte_size != len(data):
            raise ObjectStorageError("stored object size verification failed")
        if stat.sha256_hex and stat.sha256_hex != digest:
            raise ObjectStorageError("stored object checksum verification failed")
    except Exception:
        row.status = StoredObjectStatusEnum.FAILED.value
        db.flush()
        raise
    row.status = StoredObjectStatusEnum.READY.value
    db.flush()
    return row


def signed_read_url(db: Session, *, hotel_id: int, object_id: str, expires_seconds: int = 300) -> str:
    row = (
        db.query(StoredObject)
        .filter(
            StoredObject.id == object_id,
            StoredObject.hotel_id == hotel_id,
            StoredObject.status == StoredObjectStatusEnum.READY.value,
            StoredObject.deleted_at.is_(None),
        )
        .one_or_none()
    )
    if row is None:
        raise ObjectStorageError("stored object is not available")
    return get_object_storage().get_signed_url(row.object_key, expires_seconds=expires_seconds)


def soft_delete_object(db: Session, *, hotel_id: int, object_id: str, user_id: int | None) -> StoredObject:
    row = (
        db.query(StoredObject)
        .filter(StoredObject.id == object_id, StoredObject.hotel_id == hotel_id, StoredObject.deleted_at.is_(None))
        .one_or_none()
    )
    if row is None:
        raise ObjectStorageError("stored object not found")
    row.deleted_at = datetime.now(timezone.utc)
    row.deleted_by_user_id = user_id
    row.status = StoredObjectStatusEnum.DELETED.value
    db.flush()
    return row
