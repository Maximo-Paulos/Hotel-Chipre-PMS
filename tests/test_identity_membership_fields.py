from sqlalchemy import inspect

from app.models.hotel_membership import HotelMembership
from app.models.user import User


def test_existing_accounts_keep_password_login_enabled_by_default(db):
    user = User(email="account-fields@example.test", password_hash="synthetic-hash")
    db.add(user)
    db.flush()

    loaded = db.get(User, user.id)
    assert loaded.password_login_enabled is True


def test_membership_alias_fields_are_optional_and_unique_per_hotel(db, hotel_config):
    user = User(email="alias-fields@example.test", password_hash="synthetic-hash")
    db.add(user)
    db.flush()

    membership = HotelMembership(hotel_id=hotel_config.id, user_id=user.id, role="manager", status="active")
    db.add(membership)
    db.flush()

    loaded = db.get(HotelMembership, membership.id)
    assert loaded.alias is None
    assert loaded.alias_key is None

    unique_pairs = {
        tuple(index.columns.keys())
        for index in inspect(HotelMembership).local_table.indexes
        if index.unique
    }
    assert ("hotel_id", "alias_key") in unique_pairs
