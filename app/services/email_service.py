"""
Platform email service facade backed by the system transactional provider.
"""
from __future__ import annotations

from typing import Iterable

from app.master_admin.email_provider import (
    MasterEmailConnectionError,
    get_system_email_status,
    send_system_email,
)


class Mailer:
    @property
    def provider_name(self) -> str:
        return get_system_email_status().provider

    @property
    def configured(self) -> bool:
        return bool(get_system_email_status().configured)

    def available_providers(self) -> list[str]:
        return ["resend"]

    def send(self, to: Iterable[str] | str, subject: str, body: str) -> bool:
        try:
            send_system_email(None, to, subject, body)
            return True
        except MasterEmailConnectionError as exc:
            raise exc


mailer = Mailer()


def send_platform_email(to: Iterable[str] | str, subject: str, body: str) -> bool:
    return mailer.send(to, subject, body)


def send_verification_email(email: str, code: str) -> bool:
    subject = "Verifica tu cuenta en Hotel Chipre PMS"
    body = (
        "Hola,\n\n"
        "Usa este codigo de 6 digitos para verificar tu cuenta en Hotel Chipre PMS:\n\n"
        f"{code}\n\n"
        "Si no solicitaste este correo, puedes ignorarlo.\n\n"
        "Hotel Chipre PMS"
    )
    return send_platform_email(email, subject, body)


def send_reset_password_email(email: str, code: str) -> bool:
    subject = "Recupera tu acceso a Hotel Chipre PMS"
    body = (
        "Hola,\n\n"
        "Usa este codigo de 6 digitos para restablecer tu acceso a Hotel Chipre PMS:\n\n"
        f"{code}\n\n"
        "Si no solicitaste este correo, puedes ignorarlo.\n\n"
        "Hotel Chipre PMS"
    )
    return send_platform_email(email, subject, body)


def send_verification_success_email(email: str) -> bool:
    subject = "Tu cuenta fue verificada en Hotel Chipre PMS"
    body = (
        "Hola,\n\n"
        "Tu email fue verificado con exito. Ya podes iniciar sesion y usar el sistema.\n\n"
        "Si no realizaste esta accion, respondé a este correo o contacta al soporte.\n\n"
        "Hotel Chipre PMS"
    )
    return send_platform_email(email, subject, body)
