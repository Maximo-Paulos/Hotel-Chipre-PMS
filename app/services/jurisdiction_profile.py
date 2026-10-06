"""
Jurisdiction profiles for guest/check-in validation.

AR remains the only launch-active profile. Country expansion should happen by
adding profile definitions here instead of mutating the shared guest data model.
"""
from __future__ import annotations

from dataclasses import dataclass


FIELD_MESSAGES = {
    "first_name": "El nombre es obligatorio",
    "last_name": "El apellido es obligatorio",
    "document_type": "El tipo de documento (DNI/pasaporte) es obligatorio",
    "document_number": "El número de documento es obligatorio",
    "nationality": "La nacionalidad es obligatoria",
    "country": "El país es obligatorio",
    "birth_place": "El lugar de nacimiento es obligatorio",
    "birth_country": "El país de nacimiento es obligatorio",
    "marital_status": "El estado civil es obligatorio",
    "occupation": "La ocupación es obligatoria",
}

# B3.3: mandatory for every check-in regardless of jurisdiction/config —
# unlike document_fields these don't depend on require_document, they're a
# standalone hotel policy decision.
ALWAYS_REQUIRED_FIELDS: tuple[str, ...] = (
    "birth_place",
    "birth_country",
    "marital_status",
    "occupation",
)


@dataclass(frozen=True)
class JurisdictionProfile:
    code: str
    name: str
    launch_active: bool
    experimental: bool
    document_fields: tuple[str, ...]
    extra_required_fields: tuple[str, ...] = ()
    requires_terms_acceptance: bool = True


AR_PROFILE = JurisdictionProfile(
    code="AR",
    name="Argentina",
    launch_active=True,
    experimental=False,
    document_fields=("document_type", "document_number"),
)

UY_PROFILE = JurisdictionProfile(
    code="UY",
    name="Uruguay",
    launch_active=False,
    experimental=True,
    document_fields=("document_type", "document_number"),
    extra_required_fields=("nationality",),
)

CL_PROFILE = JurisdictionProfile(
    code="CL",
    name="Chile",
    launch_active=False,
    experimental=True,
    document_fields=("document_type", "document_number"),
    extra_required_fields=("nationality", "country"),
)

PROFILES = {
    AR_PROFILE.code: AR_PROFILE,
    UY_PROFILE.code: UY_PROFILE,
    CL_PROFILE.code: CL_PROFILE,
}


def get_profile(code: str | None) -> JurisdictionProfile:
    normalized = (code or AR_PROFILE.code).strip().upper()
    return PROFILES.get(normalized, AR_PROFILE)


def compute_missing_guest_fields(
    guest,
    *,
    jurisdiction_code: str | None = None,
    require_document: bool = True,
    require_terms: bool = True,
) -> list[str]:
    profile = get_profile(jurisdiction_code)
    missing: list[str] = []

    required_fields: list[str] = ["first_name", "last_name", *ALWAYS_REQUIRED_FIELDS]
    if require_document:
        required_fields.extend(profile.document_fields)
        required_fields.extend(profile.extra_required_fields)

    for field_name in required_fields:
        value = getattr(guest, field_name, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            message = FIELD_MESSAGES.get(field_name, "Este dato es obligatorio")
            if message not in missing:
                missing.append(message)

    if require_terms and profile.requires_terms_acceptance and not getattr(guest, "terms_accepted", False):
        missing.append("El huésped debe aceptar los términos y condiciones")

    return missing
