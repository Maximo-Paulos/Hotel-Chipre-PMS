from app.services.invitation_email_service import (
    send_staff_role_changed_email,
    send_staff_welcome_email,
)


class RecordingMailer:
    configured = True

    def __init__(self, *, result=True, error=None):
        self.result = result
        self.error = error
        self.messages = []

    def send(self, email, subject, body):
        if self.error is not None:
            raise self.error
        self.messages.append((email, subject, body))
        return self.result


def test_staff_welcome_notice_contains_access_details_without_capabilities():
    mailer = RecordingMailer()

    status = send_staff_welcome_email(
        email="staff@example.test",
        role="manager",
        hotel_name="Hotel Chipre",
        frontend_url="https://app.example.test/",
        sender=mailer,
    )

    assert status == "sent"
    email, subject, body = mailer.messages[0]
    assert email == "staff@example.test"
    assert subject == "Tu acceso a Hotels-PMS ya está activo"
    assert "Hotel Chipre" in body
    assert "Gerencia" in body
    assert "https://app.example.test/login" in body
    assert "token" not in body.lower()
    assert "password" not in body.lower()


def test_staff_role_notice_names_the_hotel_and_both_roles():
    mailer = RecordingMailer()

    status = send_staff_role_changed_email(
        email="staff@example.test",
        previous_role="receptionist",
        role="housekeeping",
        hotel_name="Hotel Chipre",
        frontend_url="https://app.example.test",
        sender=mailer,
    )

    assert status == "sent"
    email, subject, body = mailer.messages[0]
    assert email == "staff@example.test"
    assert subject == "Se actualizó tu rol en Hotels-PMS"
    assert "Hotel Chipre" in body
    assert "Recepción a Limpieza" in body
    assert "https://app.example.test/login" in body


def test_staff_notices_report_unavailable_or_failed_delivery_without_provider_details(caplog):
    unavailable = RecordingMailer()
    unavailable.configured = False
    failing = RecordingMailer(error=RuntimeError("private provider response with message body"))

    assert send_staff_welcome_email(
        email="staff@example.test", role="manager", sender=unavailable
    ) == "not_configured"
    assert send_staff_role_changed_email(
        email="staff@example.test",
        previous_role="manager",
        role="receptionist",
        sender=failing,
    ) == "failed"
    assert "private provider response" not in caplog.text
