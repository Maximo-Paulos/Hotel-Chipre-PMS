"""Send staff invitations and keep the reusable sign-in route visible."""

from typing import Literal, Protocol

from app.config import get_settings
from app.services.email_service import mailer


class InvitationMailer(Protocol):
    @property
    def configured(self) -> bool: ...

    def send(self, email: str, subject: str, body: str) -> bool: ...


EmailDeliveryStatus = Literal["sent", "failed", "not_configured"]

_ROLE_LABELS = {
    "owner": "Dueño",
    "co_owner": "Copropietaria",
    "manager": "Gerencia",
    "receptionist": "Recepción",
    "housekeeping": "Limpieza",
}


def send_staff_invitation_email(
    *,
    email: str,
    hotel_name: str,
    role: str,
    inviter_email: str,
    token: str,
    frontend_url: str | None = None,
    sender: InvitationMailer | None = None,
) -> tuple[str, EmailDeliveryStatus]:
    settings = get_settings()
    base = (frontend_url if frontend_url is not None else settings.FRONTEND_URL).rstrip("/")
    transport = sender or mailer
    # The fragment carries the one-time capability without placing it in HTTP
    # request logs. The fixed login URL remains useful after the link is used.
    accept_url = f"{base}/invitations/accept#token={token}"
    login_url = f"{base}/login"
    subject = f"Invitación a {hotel_name}"
    role_label = _ROLE_LABELS.get(role, role)
    body = (
        f"Hola,\n\n"
        f"Te invitaron al hotel '{hotel_name}' con el rol {role_label}.\n"
        f"Aceptá la invitación aquí: {accept_url}\n\n"
        f"Después podés ingresar siempre desde {login_url}.\n"
        "Si recibiste más de un correo, usá el enlace del más reciente: cada reenvío invalida los anteriores.\n\n"
        f"Invitó: {inviter_email}\n"
        "Si no esperabas este correo, podés ignorarlo."
    )
    try:
        configured = transport.configured
    except Exception:
        return accept_url, "failed"
    if not configured:
        return accept_url, "not_configured"
    try:
        sent = transport.send(email, subject, body)
    except Exception:
        # Keep provider diagnostics private; the persisted invitation remains
        # available for an explicit operator retry.
        return accept_url, "failed"
    return accept_url, "sent" if sent else "failed"
