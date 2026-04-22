"""
Platform email service facade backed by the owner-managed Gmail connection.
"""
from __future__ import annotations

from typing import Iterable

from app.database import get_session_factory
from app.master_admin.email_provider import MasterEmailConnectionError, get_system_email_status, send_system_email


class Mailer:
    @property
    def provider_name(self) -> str:
        db = get_session_factory()()
        try:
            status = get_system_email_status(db)
            return "gmail_oauth" if status.configured else "null"
        finally:
            db.close()

    @property
    def configured(self) -> bool:
        db = get_session_factory()()
        try:
            status = get_system_email_status(db)
            return bool(status.configured)
        finally:
            db.close()

    def available_providers(self) -> list[str]:
        return ["gmail_oauth"]

    def send(self, to: Iterable[str] | str, subject: str, body: str) -> bool:
        db = get_session_factory()()
        try:
            send_system_email(db, to, subject, body)
            db.commit()
            return True
        except MasterEmailConnectionError as exc:
            db.rollback()
            raise exc
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


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
