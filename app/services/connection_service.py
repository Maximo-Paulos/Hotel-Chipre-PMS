"""
Connection service to manage external provider credentials/settings.
Provides an idempotent upsert used by the API layer.
"""
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.connection import Connection


class ConnectionError(Exception):
    """Raised for validation problems while creating/updating a connection."""
    pass


def _validate_payload(provider: str, credentials: Dict[str, Any], settings: Optional[Dict[str, Any]]) -> tuple[str, Dict[str, Any], Optional[Dict[str, Any]]]:
    if not provider or not provider.strip():
        raise ConnectionError("provider is required")
    if not isinstance(credentials, dict):
        raise ConnectionError("credentials must be an object")
    if settings is not None and not isinstance(settings, dict):
        raise ConnectionError("settings must be an object")
    return provider.strip().lower(), credentials, settings


def upsert_connection(
    db: Session,
    provider: str,
    credentials: Dict[str, Any],
    settings: Optional[Dict[str, Any]] = None,
) -> Connection:
    """
    Create or update a provider connection while keeping JSON fields intact.
    - Normalizes provider to lower-case.
    - Reuses the same row if the provider already exists.
    """
    normalized_provider, credentials, settings = _validate_payload(provider, credentials, settings)

    conn = db.query(Connection).filter(Connection.provider == normalized_provider).first()
    if conn:
        conn.credentials = credentials
        conn.settings = settings or {}
        conn.status = "connected"
    else:
        conn = Connection(
            provider=normalized_provider,
            credentials=credentials,
            settings=settings or {},
            status="connected",
        )
        db.add(conn)

    db.flush()
    return conn
