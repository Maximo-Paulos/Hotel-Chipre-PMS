"""
Simple SMTP mailer for transactional emails (verification/reset).
Uses environment-driven settings and degrades gracefully if SMTP is not configured.
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

    def send(
        self,
        to: Iterable[str] | str,
        subject: str,
        body: str,
    ) -> None:
        """
        Sends a plain-text email using STARTTLS (port 587 by default).
        Raises only if SMTP is configured; otherwise no-ops to avoid breaking flows in dev.
        """
        if not self.configured:
            # Silent no-op if not configured
            return

        if isinstance(to, str):
            recipients = [to]
        else:
            recipients = list(to)

        msg = EmailMessage()
        msg["From"] = self.settings.SMTP_FROM or self.settings.SMTP_USER
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP(self.settings.SMTP_HOST, self.settings.SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(self.settings.SMTP_USER, self.settings.SMTP_PASS)
            smtp.send_message(msg)


mailer = Mailer()


def send_verification_email(email: str, code: str) -> None:
    """
    Sends a simple verification code email.
    """
    subject = "Verificá tu cuenta - Hotel PMS"
    body = (
        f"Hola,\n\n"
        f"Usá este código para verificar tu cuenta: {code}\n\n"
        f"Si no solicitaste este correo, ignoralo."
    )
    mailer.send(email, subject, body)


def send_reset_password_email(email: str, code: str) -> None:
    """
    Sends a password-reset code email.
    """
    subject = "Recuperá tu acceso - Hotel PMS"
    body = (
        f"Hola,\n\n"
        f"Usá este código para restablecer tu acceso: {code}\n\n"
        f"Si no solicitaste este correo, ignoralo."
    )
    mailer.send(email, subject, body)
