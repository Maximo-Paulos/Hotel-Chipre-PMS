"""
Jurisdiction profiles for guest/check-in validation.

AR remains the only launch-active profile. Country expansion should happen by
adding profile definitions here instead of mutating the shared guest data model.
"""
from __future__ import annotations

from dataclasses import dataclass


FIELD_MESSAGES = {
    "first_name": "First name is required",
    "last_name": "Last name is required",
    "document_type": "Document type (DNI/Passport) is required",
    "document_number": "Document number is required",
    "nationality": "Nationality is required",
    "country": "Country is required",
}


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

    required_fields: list[str] = ["first_name", "last_name"]
    if require_document:
        required_fields.extend(profile.document_fields)
        required_fields.extend(profile.extra_required_fields)

    for field_name in required_fields:
        value = getattr(guest, field_name, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            message = FIELD_MESSAGES.get(field_name, f"{field_name} is required")
            if message not in missing:
                missing.append(message)

    if require_terms and profile.requires_terms_acceptance and not getattr(guest, "terms_accepted", False):
        missing.append("Guest must accept terms and conditions")

    return missing
