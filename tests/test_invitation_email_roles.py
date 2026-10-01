import pytest

from app.services.invitation_email_service import send_staff_invitation_email


class RecordingMailer:
    configured = True

    def __init__(self):
        self.message = None

    def send(self, email: str, subject: str, body: str) -> bool:
        self.message = (email, subject, body)
        return True


@pytest.mark.parametrize(
    ("role", "label"),
    [
        ("owner", "Dueño"),
        ("co_owner", "Copropietaria"),
        ("manager", "Gerencia"),
        ("receptionist", "Recepción"),
        ("housekeeping", "Limpieza"),
    ],
)
def test_staff_invitation_email_uses_human_role_labels(role: str, label: str):
    sender = RecordingMailer()

    accept_url, delivery = send_staff_invitation_email(
        email="staff@example.test",
        hotel_name="Hotel de prueba",
        role=role,
        inviter_email="owner@example.test",
        token="synthetic-token",
        frontend_url="https://app.example.test",
        sender=sender,
    )

    assert delivery == "sent"
    assert accept_url.startswith("https://app.example.test/invitations/accept#token=")
    assert sender.message is not None
    body = sender.message[2]
    assert f"con el rol {label}." in body
    if role not in {"owner", "co_owner"}:
        assert role not in body
