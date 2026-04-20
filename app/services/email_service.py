"""
Platform email service for PMS-owned transactional emails.

This mailer is reserved for system-originated messages such as account
verification, password reset, invitations, and platform notices. Guest-facing
operational emails must use a hotel-owned outbound channel (for now, Gmail).
"""
import logging
import smtplib
from email.message import EmailMessage
from typing import Iterable

from app.config import get_settings

LOGGER = logging.getLogger(__name__)


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


class Mailer:
    def __init__(self):
        self.settings = get_settings()

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
            LOGGER.info(
                "SMTP connection attempt host=%s port=%s recipients=%s",
                self.settings.SMTP_HOST,
                self.settings.SMTP_PORT,
                masked_recipients,
            )
            with smtplib.SMTP(self.settings.SMTP_HOST, self.settings.SMTP_PORT, timeout=10) as smtp:
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
