"""
Jurisdiction-agnostic guest profile rules.

The profile layer keeps legal-field requirements explicit without hard-coding
country-specific behavior into the guest or check-in models.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.guest import DocumentTypeEnum, Guest
from app.models.reservation import Reservation


@dataclass(frozen=True, slots=True)
class GuestProfile:
    code: str
    name: str
    required_primary_guest_fields: tuple[str, ...]
    allowed_primary_document_types: tuple[DocumentTypeEnum, ...]
    retention_years: int


AR_GUEST_PROFILE = GuestProfile(
    code="AR",
    name="Argentina",
    required_primary_guest_fields=(
        "first_name",
        "last_name",
        "document_type",
        "document_number",
        "nationality",
        "date_of_birth",
        "arrival_date",
        "departure_date",
        "terms_accepted",
    ),
    allowed_primary_document_types=(
        DocumentTypeEnum.DNI,
        DocumentTypeEnum.PASSPORT,
        DocumentTypeEnum.CEDULA,
    ),
    retention_years=5,
)

PROFILES: dict[str, GuestProfile] = {AR_GUEST_PROFILE.code: AR_GUEST_PROFILE}


class GuestProfileError(ValueError):
    """Raised when a requested guest profile is not available."""


def get_guest_profile(profile_code: str = "AR") -> GuestProfile:
    code = (profile_code or "").strip().upper()
    profile = PROFILES.get(code)
    if not profile:
        raise GuestProfileError(f"Unknown guest profile: {profile_code}")
    return profile


def _enum_value(value: Any) -> str:
    if isinstance(value, DocumentTypeEnum):
        return value.value
    return str(value or "").strip()


def validate_primary_guest_record(
    guest: Guest,
    reservation: Reservation,
    profile: GuestProfile,
) -> list[str]:
    errors: list[str] = []

    required_guest_fields: dict[str, str] = {
        "first_name": "First name is required",
        "last_name": "Last name is required",
        "document_type": "Document type (DNI/PASSPORT/CEDULA) is required",
        "document_number": "Document number is required",
        "nationality": "Nationality is required",
        "date_of_birth": "Date of birth is required",
        "terms_accepted": "Terms acceptance is required",
        "arrival_date": "Arrival date is required",
        "departure_date": "Departure date is required",
    }
    for field_name in profile.required_primary_guest_fields:
        message = required_guest_fields[field_name]
        if field_name == "arrival_date":
            if reservation.check_in_date is None:
                errors.append(message)
            continue
        if field_name == "departure_date":
            if reservation.check_out_date is None:
                errors.append(message)
            continue
        value = getattr(guest, field_name, None)
        if field_name == "terms_accepted":
            if not bool(value):
                errors.append(message)
            continue
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(message)

    doc_type = _enum_value(getattr(guest, "document_type", None))
    allowed_doc_types = {item.value for item in profile.allowed_primary_document_types}
    if doc_type and doc_type not in allowed_doc_types:
        errors.append("Document type (DNI/PASSPORT/CEDULA) is required")

    if reservation.check_in_date and reservation.check_out_date and reservation.check_out_date <= reservation.check_in_date:
        errors.append("Departure date must be after arrival date")

    return errors
