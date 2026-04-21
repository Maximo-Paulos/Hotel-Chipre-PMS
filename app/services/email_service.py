"""
Platform email service facade backed by pluggable providers.
"""
from __future__ import annotations

import smtplib
from typing import Iterable

from app.services.email.providers import EmailProvider, get_email_provider


class Mailer:
    def __init__(self, provider: EmailProvider | None = None):
        self.settings = None
        self.provider = provider or get_email_provider(self.settings)

    def _resolve_provider(self) -> EmailProvider:
        self.provider = get_email_provider(self.settings)
        return self.provider

    @property
    def configured(self) -> bool:
        return self._resolve_provider().configured

    @property
    def provider_name(self) -> str:
        return getattr(self._resolve_provider(), "provider_name", "unknown")

    def available_providers(self) -> list[str]:
        return ["smtp", "transactional_http", "null"]

    def send(self, to: Iterable[str] | str, subject: str, body: str) -> bool:
        return self._resolve_provider().send(to, subject, body)


mailer = Mailer()


def send_platform_email(to: Iterable[str] | str, subject: str, body: str) -> bool:
    return mailer.send(to, subject, body)


def send_verification_email(email: str, code: str) -> bool:
    subject = "Verifica tu cuenta - Hotel PMS"
    body = (
        f"Hola,\n\n"
        f"Usa este codigo para verificar tu cuenta: {code}\n\n"
        "Si no solicitaste este correo, ignoralo."
    )
    return send_platform_email(email, subject, body)


def send_reset_password_email(email: str, code: str) -> bool:
    subject = "Recupera tu acceso - Hotel PMS"
    body = (
        f"Hola,\n\n"
        f"Usa este codigo para restablecer tu acceso: {code}\n\n"
        "Si no solicitaste este correo, ignoralo."
    )
    return send_platform_email(email, subject, body)


def send_verification_success_email(email: str) -> bool:
    subject = "Cuenta verificada - Hotel PMS"
    body = (
        "Hola,\n\n"
        "Tu email fue verificado con exito. Ya puedes iniciar sesion y usar el sistema.\n\n"
        "Si no realizaste esta accion, contacta al soporte."
    )
    return send_platform_email(email, subject, body)
