from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.services.apple_auth_service import AppleTokenError, verify_apple_id_token


class FakeJwkClient:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, _token):
        return type("SigningKey", (), {"key": self.key})()


@pytest.fixture
def signing_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _token(private_key, **overrides):
    now = datetime.now(timezone.utc)
    claims = {
        "iss": "https://appleid.apple.com",
        "aud": "com.example.hotel-chipre",
        "sub": "apple-sub",
        "email": "relay@privaterelay.appleid.com",
        "email_verified": True,
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "nonce": "nonce-1",
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


def _verify(token, public_key, **kwargs):
    return verify_apple_id_token(
        token,
        client_id="com.example.hotel-chipre",
        jwks_client=FakeJwkClient(public_key),
        **kwargs,
    )


def test_valid_apple_token_is_verified(signing_keys):
    private_key, public_key = signing_keys
    claims = _verify(_token(private_key), public_key, expected_nonce="nonce-1")
    assert claims["sub"] == "apple-sub"


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://evil.example"},
        {"aud": "another-client"},
        {"exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
    ],
)
def test_apple_token_rejects_wrong_issuer_audience_or_expiry(signing_keys, overrides):
    private_key, public_key = signing_keys
    with pytest.raises(AppleTokenError):
        _verify(_token(private_key, **overrides), public_key, expected_nonce="nonce-1")


def test_apple_token_rejects_invalid_signature(signing_keys):
    _private_key, public_key = signing_keys
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(AppleTokenError):
        _verify(_token(other_key), public_key, expected_nonce="nonce-1")


def test_apple_token_rejects_nonce_mismatch(signing_keys):
    private_key, public_key = signing_keys
    with pytest.raises(AppleTokenError):
        _verify(_token(private_key), public_key, expected_nonce="different-nonce")
