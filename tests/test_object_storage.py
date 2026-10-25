from __future__ import annotations

import hashlib

import pytest

from app.services.object_storage import (
    GCSObjectStorage,
    LocalObjectStorage,
    ObjectStorageError,
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


def test_local_object_storage_stat_and_signed_url_are_bounded(tmp_path, monkeypatch):
    class _Settings:
        OBJECT_STORAGE_SIGNING_SECRET = "test-secret"

    import app.services.object_storage as object_storage_module

    monkeypatch.setattr(object_storage_module, "get_settings", lambda: _Settings())
    storage = LocalObjectStorage(tmp_path)
    storage.put_bytes("private/report.xlsx", b"report")
    stat = storage.stat("private/report.xlsx")
    assert stat.byte_size == 6
    assert stat.sha256_hex == hashlib.sha256(b"report").hexdigest()
    assert "expires=" in storage.get_signed_url("private/report.xlsx", expires_seconds=300)
    with pytest.raises(ObjectStorageError):
        storage.get_signed_url("private/report.xlsx", expires_seconds=901)


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


def test_gcs_backend_requires_explicit_bucket():
    with pytest.raises(ObjectStorageError, match="GCS_BUCKET"):
        GCSObjectStorage(bucket="")


def test_gcs_delete_treats_missing_object_as_success(monkeypatch):
    class _NotFound(Exception):
        code = 404

    class _Blob:
        def delete(self):
            raise _NotFound()

    class _Bucket:
        def blob(self, key):
            assert key == "analytics-exports/1/2026/09/1.xlsx"
            return _Blob()

    storage = GCSObjectStorage(bucket="test-bucket")
    monkeypatch.setattr(storage, "_get_bucket", lambda: _Bucket())

    storage.delete("analytics-exports/1/2026/09/1.xlsx")


def test_gcs_delete_does_not_hide_transient_failures(monkeypatch):
    class _Unavailable(Exception):
        code = 503

    class _Blob:
        def delete(self):
            raise _Unavailable()

    class _Bucket:
        def blob(self, key):
            return _Blob()

    storage = GCSObjectStorage(bucket="test-bucket")
    monkeypatch.setattr(storage, "_get_bucket", lambda: _Bucket())

    with pytest.raises(ObjectStorageError, match="GCS delete failed"):
        storage.delete("analytics-exports/1/2026/09/1.xlsx")


def test_get_object_storage_defaults_to_local_backend(monkeypatch, tmp_path):
    class _Settings:
        OBJECT_STORAGE_BACKEND = "local"
        OBJECT_STORAGE_LOCAL_DIR = str(tmp_path)

    import app.services.object_storage as object_storage_module

    monkeypatch.setattr(object_storage_module, "get_settings", lambda: _Settings())
    storage = get_object_storage()
    assert isinstance(storage, LocalObjectStorage)


def test_get_object_storage_rejects_unimplemented_s3_backend(monkeypatch):
    class _Settings:
        OBJECT_STORAGE_BACKEND = "s3"
        OBJECT_STORAGE_S3_BUCKET = "hotel-chipre-proofs"
        OBJECT_STORAGE_S3_ENDPOINT_URL = ""
        OBJECT_STORAGE_S3_REGION = "us-east-1"

    import app.services.object_storage as object_storage_module

    monkeypatch.setattr(object_storage_module, "get_settings", lambda: _Settings())
    with pytest.raises(ObjectStorageError, match="s3.*not supported yet"):
        get_object_storage()


def test_get_object_storage_rejects_unknown_backend(monkeypatch):
    class _Settings:
        OBJECT_STORAGE_BACKEND = "not-a-real-backend"

    import app.services.object_storage as object_storage_module

    monkeypatch.setattr(object_storage_module, "get_settings", lambda: _Settings())
    with pytest.raises(ObjectStorageError):
        get_object_storage()
