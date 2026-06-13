from datetime import datetime, timezone

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
