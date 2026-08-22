"""Apple OIDC verification and authorization-code helpers.

The identity token is always verified with Apple's published JWKS. This module
contains no provider credentials; the optional client-secret signing key is
read from the explicitly configured secret-file path at request time.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt


APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = f"{APPLE_ISSUER}/auth/keys"
APPLE_AUTHORIZE_URL = f"{APPLE_ISSUER}/auth/authorize"
APPLE_TOKEN_URL = f"{APPLE_ISSUER}/auth/token"


class AppleTokenError(ValueError):
    """Raised when an Apple token or provider response is not trustworthy."""


def verify_apple_id_token(
    id_token: str,
    *,
    client_id: str,
    expected_nonce: str | None = None,
    jwks_client: Any | None = None,
) -> dict[str, Any]:
    """Verify Apple signature, issuer, audience, expiry and optional nonce."""
    if not id_token.strip() or not client_id.strip():
        raise AppleTokenError("Apple id_token or client id is missing")
    try:
        client = jwks_client or jwt.PyJWKClient(APPLE_JWKS_URL)
        signing_key = client.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=APPLE_ISSUER,
            options={"require": ["exp", "iat", "sub"]},
        )
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise AppleTokenError("Apple id_token is invalid") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise AppleTokenError("Apple id_token has no subject")
    if expected_nonce is not None and claims.get("nonce") != expected_nonce:
        raise AppleTokenError("Apple id_token nonce is invalid")

    email_verified = claims.get("email_verified")
    if email_verified not in (True, "true", "True", 1, "1"):
        raise AppleTokenError("Apple email is not verified")
    return claims


def build_apple_authorization_url(
    *, client_id: str, redirect_uri: str, state: str, nonce: str
) -> str:
    # Multi-line dict literal nested inside an f-string expression needs
    # Python 3.12 (PEP 701); Render runs 3.11, where this is a SyntaxError
    # ("unterminated string literal") that crashes app.main at import time
    # and takes the whole backend down. Build the params separately instead.
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code id_token",
        "response_mode": "form_post",
        "scope": "name email",
        "state": state,
        "nonce": nonce,
    }
    return f"{APPLE_AUTHORIZE_URL}?{urlencode(params)}"


def _read_private_key(path_value: str) -> str:
    path = Path(path_value).expanduser()
    if not path.is_file():
        raise AppleTokenError("Apple private key file is not configured")
    try:
        private_key = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AppleTokenError("Apple private key file could not be read") from exc
    if "BEGIN PRIVATE KEY" not in private_key and "BEGIN EC PRIVATE KEY" not in private_key:
        raise AppleTokenError("Apple private key file is invalid")
    return private_key


def create_apple_client_secret(
    *, client_id: str, team_id: str, key_id: str, private_key_path: str
) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "iss": team_id,
            "iat": now,
            "exp": now + timedelta(days=180),
            "aud": APPLE_ISSUER,
            "sub": client_id,
        },
        _read_private_key(private_key_path),
        algorithm="ES256",
        headers={"kid": key_id},
    )


def exchange_apple_code(
    *, client_id: str, client_secret: str, code: str, redirect_uri: str
) -> dict[str, Any]:
    try:
        response = httpx.post(
            APPLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise AppleTokenError("Apple authorization could not be completed") from exc
    if not isinstance(body, dict) or not isinstance(body.get("id_token"), str):
        raise AppleTokenError("Apple did not return a valid id_token")
    return body
