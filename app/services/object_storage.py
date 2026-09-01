"""Minimal object-storage abstraction: put/get/delete bytes by key.

Why this exists: payment-proof images and analytics .xlsx exports used to
live as a Postgres LargeBinary column and a local filesystem path
(`ANALYTICS_EXPORTS_DIR`) respectively. Both are wrong for Render/Cloud Run,
where the container filesystem is ephemeral and gets wiped on every
redeploy/restart -- and a filesystem path never survives a move to a real
object store either. This module gives both write paths one small interface
to target instead.

Two implementations:
- LocalObjectStorage: writes to a local directory. This is the only backend
  actually wired up in this environment (no S3-compatible bucket
  credentials exist here) -- it is fine for dev/tests, and it is what
  `OBJECT_STORAGE_BACKEND=local` (the default) uses in every environment
  today, ephemeral-disk caveat and all.
- S3ObjectStorage: stub for a real S3-compatible bucket (AWS S3, Cloudflare
  R2, Backblaze B2, MinIO, ...). Deliberately NotImplementedError -- see its
  docstring for exactly what wiring it up needs.

get_object_storage() picks the backend from Settings via getattr() with
safe defaults, so it works today without requiring any new fields on
app.config.Settings; add OBJECT_STORAGE_* fields there (env-configurable)
once a real bucket is provisioned and OBJECT_STORAGE_BACKEND=s3 is set.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.config import get_settings


class ObjectStorageError(RuntimeError):
    """Raised when a storage backend cannot complete an operation."""


class ObjectStorage(ABC):
    """Content-addressed-ish blob store: put/get/delete bytes by string key."""

    @abstractmethod
    def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> None: ...

    @abstractmethod
    def get_bytes(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


def _safe_relative_path(key: str) -> Path:
    """Reject any key that could escape the storage root (no `..`, no leading `/`)."""
    if not key or key.startswith("/") or ".." in Path(key).parts:
        raise ObjectStorageError(f"Unsafe object storage key: {key!r}")
    return Path(key)


class LocalObjectStorage(ObjectStorage):
    """Stores objects as files under a local directory root.

    Generalizes the pattern `ANALYTICS_EXPORTS_DIR` used before this module
    existed (write bytes under a root dir, keyed by a relative path) to any
    object key, not just export jobs -- payment-proof images use it too now.
    """

    def __init__(self, base_dir: str | Path):
        self._base_dir = Path(base_dir)

    def _path_for(self, key: str) -> Path:
        return self._base_dir / _safe_relative_path(key)

    def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        # ponytail: content_type is accepted for interface parity with a real
        # object-store PUT (which usually takes a Content-Type header), but a
        # plain file has nowhere to keep it -- callers persist content_type
        # themselves alongside the key (see PaymentProofBlob.content_type).
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_bytes(self, key: str) -> bytes:
        path = self._path_for(key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise ObjectStorageError(f"Object not found: {key}") from exc

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        try:
            path.unlink()
        except FileNotFoundError:
            pass


class S3ObjectStorage(ObjectStorage):
    """Stub for a real S3-compatible bucket. Not wired to a live bucket --
    there are no bucket credentials in this environment, so this raises
    NotImplementedError instead of pretending to work.

    TODO before enabling `OBJECT_STORAGE_BACKEND=s3` in production:
    - Add `boto3` to requirements.txt (not currently a dependency).
    - Add to app.config.Settings: `OBJECT_STORAGE_S3_BUCKET`,
      `OBJECT_STORAGE_S3_ENDPOINT_URL` (leave empty for AWS S3 itself; set it
      for R2/B2/MinIO/etc), `OBJECT_STORAGE_S3_REGION`. Credentials go
      through the standard AWS env vars / instance role -- never a hardcoded
      key/secret in Settings.
    - Implement put_bytes/get_bytes/delete with boto3's S3 client
      (put_object/get_object/delete_object with a shared `boto3.client("s3",
      endpoint_url=..., region_name=...)`), translating ClientError
      (specifically NoSuchKey on get) into ObjectStorageError.
    - Keep the same key convention the local backend already uses
      (`payment-proofs/{hotel_id}/...`, `analytics-exports/{hotel_id}/...`)
      so nothing else has to change when the backend switches.
    """

    def __init__(self, *, bucket: str, endpoint_url: str | None = None, region: str | None = None):
        self._bucket = bucket
        self._endpoint_url = endpoint_url
        self._region = region

    def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        raise NotImplementedError("S3ObjectStorage requires boto3 + bucket credentials -- see class docstring")

    def get_bytes(self, key: str) -> bytes:
        raise NotImplementedError("S3ObjectStorage requires boto3 + bucket credentials -- see class docstring")

    def delete(self, key: str) -> None:
        raise NotImplementedError("S3ObjectStorage requires boto3 + bucket credentials -- see class docstring")


def get_object_storage() -> ObjectStorage:
    """Backend picked by `settings.OBJECT_STORAGE_BACKEND` (default: local).

    Uses getattr() with defaults so this works even before Settings grows
    dedicated OBJECT_STORAGE_* fields -- see module docstring.
    """
    settings = get_settings()
    backend = (getattr(settings, "OBJECT_STORAGE_BACKEND", "") or "local").lower()
    if backend == "local":
        local_dir = getattr(settings, "OBJECT_STORAGE_LOCAL_DIR", "") or "./var/object-storage"
        return LocalObjectStorage(local_dir)
    if backend == "s3":
        return S3ObjectStorage(
            bucket=getattr(settings, "OBJECT_STORAGE_S3_BUCKET", ""),
            endpoint_url=getattr(settings, "OBJECT_STORAGE_S3_ENDPOINT_URL", "") or None,
            region=getattr(settings, "OBJECT_STORAGE_S3_REGION", "") or None,
        )
    raise ObjectStorageError(f"Unknown OBJECT_STORAGE_BACKEND: {backend!r}")
