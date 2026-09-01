from __future__ import annotations

import hashlib

import pytest

from app.services.object_storage import (
    LocalObjectStorage,
    ObjectStorageError,
    S3ObjectStorage,
    get_object_storage,
)


def test_local_object_storage_put_get_roundtrip_preserves_integrity(tmp_path):
    storage = LocalObjectStorage(tmp_path)
    data = b"comprobante binario de prueba"
    key = "payment-proofs/1/abc.png"

    storage.put_bytes(key, data, content_type="image/png")
    fetched = storage.get_bytes(key)

    assert fetched == data
    assert hashlib.sha256(fetched).hexdigest() == hashlib.sha256(data).hexdigest()
    assert (tmp_path / "payment-proofs" / "1" / "abc.png").exists()


def test_local_object_storage_get_missing_key_raises():
    storage = LocalObjectStorage("/tmp/does-not-exist-object-storage-root")
    with pytest.raises(ObjectStorageError):
        storage.get_bytes("nope")


def test_local_object_storage_delete_is_idempotent(tmp_path):
    storage = LocalObjectStorage(tmp_path)
    key = "analytics-exports/1/2026/09/1.xlsx"
    storage.put_bytes(key, b"xlsx-bytes")

    storage.delete(key)
    with pytest.raises(ObjectStorageError):
        storage.get_bytes(key)

    # Deleting again (or a key that never existed) must not raise.
    storage.delete(key)


@pytest.mark.parametrize("bad_key", ["../escape", "/absolute/path", "a/../../b"])
def test_local_object_storage_rejects_path_traversal_keys(tmp_path, bad_key):
    storage = LocalObjectStorage(tmp_path)
    with pytest.raises(ObjectStorageError):
        storage.put_bytes(bad_key, b"data")


def test_s3_object_storage_is_an_unwired_stub():
    storage = S3ObjectStorage(bucket="test-bucket")
    with pytest.raises(NotImplementedError):
        storage.put_bytes("key", b"data")
    with pytest.raises(NotImplementedError):
        storage.get_bytes("key")
    with pytest.raises(NotImplementedError):
        storage.delete("key")


def test_get_object_storage_defaults_to_local_backend(monkeypatch, tmp_path):
    class _Settings:
        OBJECT_STORAGE_BACKEND = "local"
        OBJECT_STORAGE_LOCAL_DIR = str(tmp_path)

    import app.services.object_storage as object_storage_module

    monkeypatch.setattr(object_storage_module, "get_settings", lambda: _Settings())
    storage = get_object_storage()
    assert isinstance(storage, LocalObjectStorage)


def test_get_object_storage_s3_backend_builds_s3_storage(monkeypatch):
    class _Settings:
        OBJECT_STORAGE_BACKEND = "s3"
        OBJECT_STORAGE_S3_BUCKET = "hotel-chipre-proofs"
        OBJECT_STORAGE_S3_ENDPOINT_URL = ""
        OBJECT_STORAGE_S3_REGION = "us-east-1"

    import app.services.object_storage as object_storage_module

    monkeypatch.setattr(object_storage_module, "get_settings", lambda: _Settings())
    storage = get_object_storage()
    assert isinstance(storage, S3ObjectStorage)


def test_get_object_storage_rejects_unknown_backend(monkeypatch):
    class _Settings:
        OBJECT_STORAGE_BACKEND = "not-a-real-backend"

    import app.services.object_storage as object_storage_module

    monkeypatch.setattr(object_storage_module, "get_settings", lambda: _Settings())
    with pytest.raises(ObjectStorageError):
        get_object_storage()
