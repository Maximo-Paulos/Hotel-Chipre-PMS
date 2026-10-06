from app.models.guest import Guest
from app.services.checkin_service import validate_guest_for_checkin
from app.services.jurisdiction_profile import compute_missing_guest_fields, get_profile


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
        birth_place="Rosario",
        birth_country="Argentina",
        marital_status="single",
        occupation="Ingeniera",
        hotel_id=hotel_config.id,
    )
    db.add(guest)
    db.flush()

    hotel_config.jurisdiction_code = "AR"
    db.flush()
    assert validate_guest_for_checkin(db, guest, hotel_config) == []

    hotel_config.jurisdiction_code = "UY"
    db.flush()
    assert "La nacionalidad es obligatoria" in validate_guest_for_checkin(db, guest, hotel_config)


def test_required_guest_field_and_terms_messages_are_in_spanish():
    guest = Guest(
        first_name="",
        last_name="",
        document_type="",
        document_number="",
        nationality="",
        country="",
        birth_place="",
        birth_country="",
        marital_status="",
        occupation="",
        terms_accepted=False,
    )

    missing = compute_missing_guest_fields(guest, jurisdiction_code="CL")

    assert missing == [
        "El nombre es obligatorio",
        "El apellido es obligatorio",
        "El lugar de nacimiento es obligatorio",
        "El país de nacimiento es obligatorio",
        "El estado civil es obligatorio",
        "La ocupación es obligatoria",
        "El tipo de documento (DNI/pasaporte) es obligatorio",
        "El número de documento es obligatorio",
        "La nacionalidad es obligatoria",
        "El país es obligatorio",
        "El huésped debe aceptar los términos y condiciones",
    ]
