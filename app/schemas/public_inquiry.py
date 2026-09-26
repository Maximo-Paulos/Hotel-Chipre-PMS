"""Validation and response contracts for public marketing inquiries."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, StrictBool, field_validator


def _clean_required(value: str, field_name: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError(f"{field_name} no puede estar vacío")
    if "\x00" in cleaned:
        raise ValueError(f"{field_name} contiene caracteres inválidos")
    return cleaned


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    if "\x00" in cleaned:
        raise ValueError("El campo contiene caracteres inválidos")
    return cleaned or None


class PublicInquiryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    company_name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=50)
    message: str = Field(min_length=1, max_length=4000)
    source_path: str = Field(default="/contacto", min_length=1, max_length=200)
    privacy_consent: StrictBool
    website: str | None = Field(default=None, max_length=200)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _clean_required(value, "El nombre")

    @field_validator("company_name", "phone", mode="before")
    @classmethod
    def clean_optional_fields(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not cleaned:
            raise ValueError("El mensaje no puede estar vacío")
        if any(ord(char) < 32 and char not in "\n\t" for char in cleaned):
            raise ValueError("El mensaje contiene caracteres inválidos")
        return cleaned

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, value: str) -> str:
        cleaned = _clean_required(value, "La ruta de origen")
        if not cleaned.startswith("/") or any(ord(char) < 32 for char in cleaned):
            raise ValueError("La ruta de origen no es válida")
        return cleaned

    @field_validator("privacy_consent")
    @classmethod
    def require_privacy_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Debés aceptar la Política de Privacidad")
        return value

    @property
    def normalized_email(self) -> str:
        return str(self.email).strip().lower()


class PublicInquiryAccepted(BaseModel):
    status: str = "accepted"


class PublicInquiryRead(BaseModel):
    id: int
    notification_status: str
    created_at: datetime
