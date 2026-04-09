"""
Platform email service for PMS-owned transactional emails.

This mailer is reserved for system-originated messages such as account
verification, password reset, invitations, and platform notices. Guest-facing
operational emails must use a hotel-owned outbound channel (for now, Gmail).
"""
import smtplib
from email.message import EmailMessage
from typing import Iterable

from app.config import get_settings


class Mailer:
    def __init__(self):
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        s = self.settings
        return bool(s.SMTP_HOST and s.SMTP_USER and s.SMTP_PASS)

    def send(self, to: Iterable[str] | str, subject: str, body: str) -> None:
        if not self.configured:
            return

        recipients = [to] if isinstance(to, str) else list(to)

        msg = EmailMessage()
        msg["From"] = self.settings.SMTP_FROM or self.settings.SMTP_USER
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            with smtplib.SMTP(self.settings.SMTP_HOST, self.settings.SMTP_PORT, timeout=10) as smtp:
                smtp.starttls()
                smtp.login(self.settings.SMTP_USER, self.settings.SMTP_PASS)
                smtp.send_message(msg)
        except Exception as exc:  # pragma: no cover
            print(f"[mailer] failed to send email: {exc}")


mailer = Mailer()


def send_platform_email(to: Iterable[str] | str, subject: str, body: str) -> None:
    mailer.send(to, subject, body)


def send_verification_email(email: str, code: str) -> None:
    subject = "Verifica tu cuenta - Hotel PMS"
    body = (
        f"Hola,\n\n"
        f"Usa este codigo para verificar tu cuenta: {code}\n\n"
        "Si no solicitaste este correo, ignoralo."
    )
    send_platform_email(email, subject, body)


def send_reset_password_email(email: str, code: str) -> None:
    subject = "Recupera tu acceso - Hotel PMS"
    body = (
        f"Hola,\n\n"
        f"Usa este codigo para restablecer tu acceso: {code}\n\n"
        "Si no solicitaste este correo, ignoralo."
    )
    send_platform_email(email, subject, body)


def send_verification_success_email(email: str) -> None:
    subject = "Cuenta verificada - Hotel PMS"
    body = (
        "Hola,\n\n"
        "Tu email fue verificado con exito. Ya puedes iniciar sesion y usar el sistema.\n\n"
        "Si no realizaste esta accion, contacta al soporte."
    )
    send_platform_email(email, subject, body)
