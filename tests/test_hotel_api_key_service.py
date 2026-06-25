from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.dependencies.api_key_auth import get_public_api_context
from app.models.hotel_api_key import HotelAPIKey, APIKeyPurposeEnum
from app.models.hotel_config import HotelConfiguration
from app.services.hotel_api_key_service import issue_key, list_keys, verify_key


def test_api_key_secret_is_only_returned_once_and_hash_is_stored(db):
    hotel = HotelConfiguration(id=1, subscription_active=True)
    db.add(hotel)
    db.flush()

    key, secret = issue_key(
        db,
        hotel_id=hotel.id,
        name="Website engine",
        purpose=APIKeyPurposeEnum.WEB_ENGINE,
        created_by_user_id=None,
        expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    db.commit()

    assert secret.startswith("hpk_")
    assert key.key_prefix == secret[:8]
    assert key.key_hash != secret
    assert secret not in key.key_hash

    stored = db.query(HotelAPIKey).filter(HotelAPIKey.id == key.id).one()
    assert stored.key_hash == key.key_hash
    assert not hasattr(stored, "secret")

    verified = verify_key(db, secret, hotel_id=hotel.id)
    assert verified.id == key.id

    listed = list_keys(db, hotel_id=hotel.id)
    assert [item.id for item in listed] == [key.id]
    assert all(not hasattr(item, "secret") for item in listed)


def test_public_api_key_uses_configured_hotel_rate_limit(db):
    hotel = HotelConfiguration(
        id=2,
        subscription_active=True,
        public_api_rate_limit_per_minute=2,
    )
    db.add(hotel)
    db.flush()
    _key, secret = issue_key(
        db,
        hotel_id=hotel.id,
        name="Configured API limit",
        purpose=APIKeyPurposeEnum.WEB_ENGINE,
    )
    db.commit()

    first = get_public_api_context(db=db, x_api_key=secret)
    second = get_public_api_context(db=db, x_api_key=secret)

    assert first.hotel_id == hotel.id
    assert second.hotel_id == hotel.id
    with pytest.raises(HTTPException) as exc:
        get_public_api_context(db=db, x_api_key=secret)
    assert exc.value.status_code == 429


def test_public_api_key_default_rate_limit_allows_sixty_per_minute(db):
    hotel = HotelConfiguration(id=3, subscription_active=True)
    db.add(hotel)
    db.flush()
    _key, secret = issue_key(
        db,
        hotel_id=hotel.id,
        name="Default API limit",
        purpose=APIKeyPurposeEnum.WEB_ENGINE,
    )
    db.commit()

    for _ in range(60):
        context = get_public_api_context(db=db, x_api_key=secret)
        assert context.hotel_id == hotel.id

    with pytest.raises(HTTPException) as exc:
        get_public_api_context(db=db, x_api_key=secret)
    assert exc.value.status_code == 429
