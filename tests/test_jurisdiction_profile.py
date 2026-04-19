from app.models.guest import Guest
from app.services.checkin_service import validate_guest_for_checkin
from app.services.jurisdiction_profile import get_profile


def test_ar_profile_is_launch_active_and_default():
    profile = get_profile("AR")
    fallback = get_profile("unknown")

    assert profile.code == "AR"
    assert profile.launch_active is True
    assert profile.experimental is False
    assert fallback.code == "AR"


def test_uy_profile_lookup_is_safe():
    profile = get_profile("UY")

    assert profile.code == "UY"
    assert profile.launch_active is False
    assert profile.experimental is True
    assert "nationality" in profile.extra_required_fields


def test_missing_field_computation_uses_profile(db, hotel_config):
    guest = Guest(
        first_name="Lucia",
        last_name="Diaz",
        document_type="DNI",
        document_number="30111222",
        terms_accepted=True,
        hotel_id=hotel_config.id,
    )
    db.add(guest)
    db.flush()

    hotel_config.set_extra_policies({"jurisdiction_code": "AR"})
    db.flush()
    assert validate_guest_for_checkin(db, guest, hotel_config) == []

    hotel_config.set_extra_policies({"jurisdiction_code": "UY"})
    db.flush()
    assert "Nationality is required" in validate_guest_for_checkin(db, guest, hotel_config)
