import pytest

from app.services.staff_invitation_service import normalize_staff_role


def test_normalize_staff_role_accepts_reception_label_from_onboarding():
    assert normalize_staff_role("Reception") == "receptionist"


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("co_owner", "co_owner"),
        ("Copropietaria", "co_owner"),
        ("Copropietario", "co_owner"),
        ("Gerencia", "manager"),
        ("Recepción", "receptionist"),
        ("Limpieza", "housekeeping"),
    ],
)
def test_normalize_staff_role_accepts_spanish_onboarding_labels(label, expected):
    assert normalize_staff_role(label) == expected


@pytest.mark.parametrize("label", ["Owner", "owner", "Dueño", "Dueña"])
def test_normalize_staff_role_rejects_owner_assignment(label):
    with pytest.raises(ValueError, match="Dueño"):
        normalize_staff_role(label)
