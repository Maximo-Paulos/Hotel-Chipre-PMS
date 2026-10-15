from __future__ import annotations

import hashlib
from tempfile import SpooledTemporaryFile
from types import SimpleNamespace

import pytest

from app.models.stored_object import StoredObjectStatusEnum
from app.services.object_storage import LocalObjectStorage, ObjectStorageError
from app.services.stored_object_service import (
    register_uploaded_object,
    register_uploaded_object_file,
    signed_read_url,
)


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


def test_register_uploaded_object_file_streams_and_verifies_local_file(db, hotel_config, monkeypatch, tmp_path):
    import app.services.stored_object_service as stored_object_module

    storage = LocalObjectStorage(tmp_path / "objects")
    monkeypatch.setattr(stored_object_module, "get_object_storage", lambda: storage)
    monkeypatch.setattr(
        stored_object_module,
        "get_settings",
        lambda: SimpleNamespace(OBJECT_STORAGE_BACKEND="local"),
    )
    data = (b"streamed-export-row\n" * 16_384) + b"last-row"
    with SpooledTemporaryFile(max_size=128, mode="w+b") as source:
        source.write(data)
        row = register_uploaded_object_file(
            db,
            hotel_id=hotel_config.id,
            purpose="analytics_export",
            object_key=f"analytics-exports/{hotel_config.id}/streamed.xlsx",
            data_file=source,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            created_by_user_id=None,
        )

    assert row.status == StoredObjectStatusEnum.READY.value
    assert row.byte_size == len(data)
    assert row.sha256_hex == hashlib.sha256(data).hexdigest()
    assert storage.get_bytes(row.object_key) == data
