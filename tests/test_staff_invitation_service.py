from app.services.staff_invitation_service import normalize_staff_role


def test_normalize_staff_role_accepts_reception_label_from_onboarding():
    assert normalize_staff_role("Reception") == "receptionist"
