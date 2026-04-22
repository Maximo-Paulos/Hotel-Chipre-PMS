from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from email.utils import parseaddr
from typing import Iterable

import requests

from app.config import get_settings

LOGGER = logging.getLogger("app.services.email.providers")


def _mask_email(email: str) -> str:
    local_part, at, domain = email.partition("@")
    if not at:
        return "***"
    if len(local_part) <= 2:
        masked_local = f"{local_part[:1]}***"
    else:
        masked_local = f"{local_part[:2]}***"
    return f"{masked_local}@{domain}"


def _mask_recipients(recipients: list[str]) -> str:
    return ", ".join(_mask_email(recipient) for recipient in recipients)


def _normalize_display_from(value: str) -> str:
    display_name, email_address = parseaddr(value)
    if display_name and email_address:
        return f"{display_name} <{email_address}>"
    return value.strip()


class EmailProviderError(RuntimeError):
    pass


class EmailProvider(ABC):
    provider_name = "base"

    @property
    @abstractmethod
    def configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def send(self, to: Iterable[str] | str, subject: str, body: str) -> dict[str, object]:
        raise NotImplementedError


class ResendEmailProvider(EmailProvider):
    provider_name = "resend"

    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    @property
    def configured(self) -> bool:
        s = self.settings
        return bool(
            (s.EMAIL_PROVIDER or "").strip().lower() == "resend"
            and (s.RESEND_API_KEY or "").strip()
            and (s.SYSTEM_EMAIL_FROM or "").strip()
            and (s.SYSTEM_EMAIL_REPLY_TO or "").strip()
        )

    def send(self, to: Iterable[str] | str, subject: str, body: str) -> dict[str, object]:
        if not self.configured:
            raise EmailProviderError(
                "Resend no esta configurado. Definí EMAIL_PROVIDER=resend, RESEND_API_KEY, SYSTEM_EMAIL_FROM y SYSTEM_EMAIL_REPLY_TO."
            )

        recipients = [to] if isinstance(to, str) else list(to)
        if not recipients:
            raise EmailProviderError("Resend requiere al menos un destinatario.")

        masked_recipients = _mask_recipients(recipients)
        payload: dict[str, object] = {
            "from": _normalize_display_from(self.settings.SYSTEM_EMAIL_FROM),
            "to": recipients,
            "subject": subject,
            "text": body,
            "reply_to": [self.settings.SYSTEM_EMAIL_REPLY_TO.strip()],
        }

        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.settings.RESEND_API_KEY.strip()}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=20,
            )
        except Exception as exc:  # pragma: no cover - network failure
            LOGGER.exception("Resend send failed recipients=%s subject=%s", masked_recipients, subject)
            raise EmailProviderError("No se pudo conectar con Resend para enviar el correo del sistema.") from exc

        if not response.ok:
            detail = None
            try:
                data = response.json()
                if isinstance(data, dict):
                    detail = data.get("message") or data.get("error") or data.get("error_description")
            except Exception:
                detail = None
            raise EmailProviderError(str(detail or "Resend rechazo el envio del correo del sistema."))

        response_payload = response.json() if response.content else {}
        email_id = response_payload.get("id") if isinstance(response_payload, dict) else None
        LOGGER.info("Resend send success recipients=%s subject=%s", masked_recipients, subject)
        return {"id": email_id, "provider": "resend"}


class NullEmailProvider(EmailProvider):
    provider_name = "null"

    @property
    def configured(self) -> bool:
        return False

    def send(self, to: Iterable[str] | str, subject: str, body: str) -> dict[str, object]:
        raise EmailProviderError("No hay un provider de email configurado.")


def get_email_provider(settings=None) -> EmailProvider:
    settings = settings or get_settings()
    provider = (getattr(settings, "EMAIL_PROVIDER", "") or "resend").strip().lower()
    if provider == "resend":
        return ResendEmailProvider(settings)
    if provider == "null":
        return NullEmailProvider()
    raise EmailProviderError(f"EMAIL_PROVIDER no soportado: {provider}")
