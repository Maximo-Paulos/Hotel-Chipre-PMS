"""Signed, short-lived reservation quote tokens.

The token is a transport envelope, not a source of truth.  Reservation creation
always recomputes the quote and compares its pricing revision before persisting
anything.  The payload intentionally contains no guest data or credentials.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.config import get_settings, is_production_mode
from cryptography.fernet import Fernet, InvalidToken


class QuoteTokenError(ValueError):
    """Raised when a quote token is malformed, expired, or tampered with."""


_TOKEN_VERSION = 1
_MAX_TOKEN_BYTES = 24_000
_ENCRYPTED_TOKEN_PREFIX = "enc1."


def _secret() -> bytes:
    settings = get_settings()
    value = (
        (settings.SIGNED_TOKEN_SECRET or "").strip()
        or (settings.ACCESS_TOKEN_SECRET or "").strip()
        or (settings.JWT_SECRET or "").strip()
    )
    if not value or (is_production_mode(settings) and value == "change-me"):
        raise QuoteTokenError("Quote signing secret is not configured")
    return value.encode("utf-8")


def _encryption_fernet() -> Fernet:
    """Derive a quote-only encryption key from the configured signing secret.

    Domain separation keeps this key distinct from quote HMAC use and other
    application encryption keys while avoiding another deployment secret.
    """
    key_material = hashlib.sha256(b"hotel-pms:quote-token-encryption:v1\0" + _secret()).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    try:
        # Reject non-canonical Base64URL spellings. Without this round-trip
        # check, changing unused trailing bits can decode to the same bytes and
        # allow a tampered token to pass signature verification.
        if "=" in value:
            raise ValueError("padding is not allowed")
        padding = "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode((value + padding).encode("ascii"))
        if _encode(decoded) != value:
            raise ValueError("non-canonical encoding")
        return decoded
    except (ValueError, UnicodeError) as exc:
        raise QuoteTokenError("Invalid quote token encoding") from exc


def issue_quote_token(
    payload: dict[str, Any],
    *,
    ttl_seconds: int = 900,
    encrypt_payload: bool = False,
) -> str:
    """Issue a short-lived reservation token.

    Ordinary quotes use the historical signed format. Quotes whose contents
    must remain confidential use Fernet authenticated encryption so the
    client cannot read their verified pricing fields from the token.
    """
    now = int(time.time())
    body = {
        **payload,
        "v": _TOKEN_VERSION,
        "iat": now,
        "exp": now + max(60, min(int(ttl_seconds), 3600)),
    }
    body_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if encrypt_payload:
        return _ENCRYPTED_TOKEN_PREFIX + _encryption_fernet().encrypt(body_bytes).decode("ascii")

    encoded_body = _encode(body_bytes)
    signature = hmac.new(_secret(), encoded_body.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded_body}.{_encode(signature)}"


def verify_quote_token(token: str) -> dict[str, Any]:
    """Verify and decode a quote token without trusting any client fields."""
    if not isinstance(token, str) or len(token.encode("utf-8")) > _MAX_TOKEN_BYTES:
        raise QuoteTokenError("Invalid quote token")

    if token.startswith(_ENCRYPTED_TOKEN_PREFIX):
        try:
            body_bytes = _encryption_fernet().decrypt(token[len(_ENCRYPTED_TOKEN_PREFIX) :].encode("ascii"))
        except (InvalidToken, UnicodeError, ValueError) as exc:
            raise QuoteTokenError("Quote token is invalid") from exc
        try:
            payload = json.loads(body_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise QuoteTokenError("Invalid quote token payload") from exc
        if not isinstance(payload, dict) or payload.get("v") != _TOKEN_VERSION:
            raise QuoteTokenError("Unsupported quote token")
        if not isinstance(payload.get("exp"), int) or payload["exp"] < int(time.time()):
            raise QuoteTokenError("Quote token expired")
        return payload

    parts = token.split(".")
    if len(parts) != 2:
        raise QuoteTokenError("Invalid quote token")

    encoded_body, encoded_signature = parts
    expected = hmac.new(_secret(), encoded_body.encode("ascii"), hashlib.sha256).digest()
    try:
        supplied = _decode(encoded_signature)
    except QuoteTokenError as exc:
        raise QuoteTokenError("Quote token signature is invalid") from exc
    if not hmac.compare_digest(expected, supplied):
        raise QuoteTokenError("Quote token signature is invalid")

    try:
        payload = json.loads(_decode(encoded_body).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise QuoteTokenError("Invalid quote token payload") from exc
    if not isinstance(payload, dict) or payload.get("v") != _TOKEN_VERSION:
        raise QuoteTokenError("Unsupported quote token")
    if not isinstance(payload.get("exp"), int) or payload["exp"] < int(time.time()):
        raise QuoteTokenError("Quote token expired")
    return payload
