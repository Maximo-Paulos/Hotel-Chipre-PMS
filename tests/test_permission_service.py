from app.models.security_audit_log import SecurityAuditLog
from app.models.hotel_config import HotelConfiguration
from app.models.permission import RolePermissionDefault
from app.services.permission_service import (
    PERMISSION_CHECKIN_PERFORM,
    PERMISSION_GUEST_EDIT,
    PERMISSION_RESERVATION_CREATE,
    get_matrix,
    resolve,
    seed_default_permissions,
    set_override,
)


def _seed_hotel(db, hotel_id: int) -> HotelConfiguration:
    hotel = HotelConfiguration(id=hotel_id, subscription_active=True)
    db.add(hotel)
    db.flush()
    return hotel


def test_default_permissions_seeded_for_owner_manager_reception_housekeeping(db):
    seed_default_permissions(db)

    rows = {
        (row.role, row.permission_code): row.allowed
        for row in db.query(RolePermissionDefault).all()
    }

    assert rows[("owner", PERMISSION_GUEST_EDIT)] is True
    assert rows[("manager", PERMISSION_RESERVATION_CREATE)] is True
    assert rows[("receptionist", PERMISSION_CHECKIN_PERFORM)] is True
    assert rows[("housekeeping", PERMISSION_GUEST_EDIT)] is False
    assert rows[("housekeeping", PERMISSION_RESERVATION_CREATE)] is False
    assert rows[("housekeeping", PERMISSION_CHECKIN_PERFORM)] is False


def test_permission_override_allows_receptionist_guest_edit(db):
    _seed_hotel(db, 1)
    seed_default_permissions(db)

    assert resolve(db, 1, "receptionist", PERMISSION_GUEST_EDIT) is False

    set_override(db, 1, "receptionist", PERMISSION_GUEST_EDIT, True, user_id=None)

    assert resolve(db, 1, "receptionist", PERMISSION_GUEST_EDIT) is True
    audit = db.query(SecurityAuditLog).filter(SecurityAuditLog.action == "permission.override.updated").one()
    assert audit.hotel_id == 1


def test_housekeeping_cannot_create_reservation_by_default(db):
    _seed_hotel(db, 1)
    seed_default_permissions(db)

    assert resolve(db, 1, "housekeeping", PERMISSION_RESERVATION_CREATE) is False


def test_override_in_hotel_a_does_not_affect_hotel_b(db):
    _seed_hotel(db, 1)
    _seed_hotel(db, 2)
    seed_default_permissions(db)

    set_override(db, 1, "receptionist", PERMISSION_GUEST_EDIT, True, user_id=None)

    assert resolve(db, 1, "receptionist", PERMISSION_GUEST_EDIT) is True
    assert resolve(db, 2, "receptionist", PERMISSION_GUEST_EDIT) is False


def test_get_matrix_includes_hotel_overrides(db):
    _seed_hotel(db, 1)
    seed_default_permissions(db)
    set_override(db, 1, "receptionist", PERMISSION_GUEST_EDIT, True, user_id=None)

    matrix = get_matrix(db, 1)

    assert matrix["receptionist"][PERMISSION_GUEST_EDIT]["allowed"] is True
    assert matrix["receptionist"][PERMISSION_GUEST_EDIT]["source"] == "override"
