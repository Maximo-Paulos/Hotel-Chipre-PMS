from __future__ import annotations

import hashlib

import pytest

from app.models.stored_object import StoredObjectStatusEnum
from app.services.object_storage import ObjectStorageError
from app.services.stored_object_service import register_uploaded_object, signed_read_url


def test_register_uploaded_object_verifies_bytes_and_is_tenant_scoped(db, hotel_config):
    row = register_uploaded_object(
        db,
        hotel_id=hotel_config.id,
        purpose="test_attachment",
        object_key=f"attachments/{hotel_config.id}/object.txt",
        data=b"hello",
        content_type="text/plain",
        created_by_user_id=None,
    )
    db.commit()
    assert row.status == StoredObjectStatusEnum.READY.value
    assert row.byte_size == 5
    assert row.sha256_hex == hashlib.sha256(b"hello").hexdigest()
    assert signed_read_url(db, hotel_id=hotel_config.id, object_id=row.id).startswith("local-object://")

    with pytest.raises(ObjectStorageError):
        signed_read_url(db, hotel_id=hotel_config.id + 1000, object_id=row.id)
