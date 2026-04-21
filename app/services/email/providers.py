from __future__ import annotations

import logging
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage
from typing import Iterable

import httpx

from app.config import get_settings

LOGGER = logging.getLogger("app.services.email_service")


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


class EmailProvider(ABC):
    provider_name = "base"

    @property
    @abstractmethod
    def configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def send(self, to: Iterable[str] | str, subject: str, body: str) -> bool:
        raise NotImplementedError


class SmtpEmailProvider(EmailProvider):
    provider_name = "smtp"

    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    @property
    def configured(self) -> bool:
        s = self.settings
        return bool(s.SMTP_HOST and s.SMTP_USER and s.SMTP_PASS)

    def send(self, to: Iterable[str] | str, subject: str, body: str) -> bool:
        if not self.configured:
            LOGGER.warning("SMTP send skipped because configuration is incomplete")
            return False

        recipients = [to] if isinstance(to, str) else list(to)
        masked_recipients = _mask_recipients(recipients)

        msg = EmailMessage()
        msg["From"] = self.settings.SMTP_FROM or self.settings.SMTP_USER
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            from app.services import email_service as email_service_module

            LOGGER.info(
                "SMTP connection attempt host=%s port=%s recipients=%s",
                self.settings.SMTP_HOST,
                self.settings.SMTP_PORT,
                masked_recipients,
            )
            with email_service_module.smtplib.SMTP(self.settings.SMTP_HOST, self.settings.SMTP_PORT, timeout=10) as smtp:
                LOGGER.info("SMTP connection established host=%s port=%s", self.settings.SMTP_HOST, self.settings.SMTP_PORT)
                LOGGER.info("SMTP authentication attempt user=%s", _mask_email(self.settings.SMTP_USER))
                smtp.starttls()
                smtp.login(self.settings.SMTP_USER, self.settings.SMTP_PASS)
                LOGGER.info("SMTP authentication success user=%s", _mask_email(self.settings.SMTP_USER))
                LOGGER.info("SMTP send attempt recipients=%s subject=%s", masked_recipients, subject)
                smtp.send_message(msg)
            LOGGER.info("SMTP send success recipients=%s subject=%s", masked_recipients, subject)
            return True
        except Exception:  # pragma: no cover
            LOGGER.exception(
                "SMTP send failed host=%s port=%s recipients=%s subject=%s",
                self.settings.SMTP_HOST,
                self.settings.SMTP_PORT,
                masked_recipients,
                subject,
            )
            return False


class HttpTransactionalEmailProvider(EmailProvider):
    provider_name = "transactional_http"

    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    @property
    def configured(self) -> bool:
        return bool(getattr(self.settings, "TRANSACTIONAL_EMAIL_ENDPOINT", "") or "")

    def send(self, to: Iterable[str] | str, subject: str, body: str) -> bool:
        endpoint = getattr(self.settings, "TRANSACTIONAL_EMAIL_ENDPOINT", "") or ""
        if not endpoint:
            LOGGER.warning("Transactional email skipped because endpoint is missing")
            return False

        recipients = [to] if isinstance(to, str) else list(to)
        masked_recipients = _mask_recipients(recipients)
        headers = {}
        api_key = getattr(self.settings, "TRANSACTIONAL_EMAIL_API_KEY", "") or ""
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {"to": recipients, "subject": subject, "body": body}
        try:
            with httpx.Client(timeout=10) as client:
                response = client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
            LOGGER.info("Transactional email sent endpoint=%s recipients=%s", endpoint, masked_recipients)
            return True
        except Exception:
            LOGGER.exception("Transactional email send failed endpoint=%s recipients=%s", endpoint, masked_recipients)
            return False


class NullEmailProvider(EmailProvider):
    provider_name = "null"

    @property
    def configured(self) -> bool:
        return False

    def send(self, to: Iterable[str] | str, subject: str, body: str) -> bool:
        LOGGER.warning("Email send skipped because no provider is configured")
        return False


def get_email_provider(settings=None) -> EmailProvider:
    settings = settings or get_settings()
    provider = (getattr(settings, "EMAIL_PROVIDER", "") or "").strip().lower()
    if provider == "transactional":
        return HttpTransactionalEmailProvider(settings)
    if provider == "smtp":
        return SmtpEmailProvider(settings)
    if provider == "null":
        return NullEmailProvider()
    if settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASS:
        return SmtpEmailProvider(settings)
    return NullEmailProvider()
