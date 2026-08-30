from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models.security_audit_log import SecurityAuditLog
from app.models.hotel_config import HotelConfiguration
from app.models.permission import HotelPermissionOverride, Permission, RolePermissionDefault
from app.services.permission_service import (
    DEFAULT_MATRIX,
    PERMISSION_CASH_APPROVE_DIFFERENCE,
    PERMISSION_CASH_OPERATE,
    PERMISSION_CHECKIN_PERFORM,
    PERMISSION_GUEST_CREATE,
    PERMISSION_GUEST_EDIT,
    PERMISSION_GUEST_READ,
    PERMISSION_GUEST_ROOM_AVOIDANCE_RESOLVE,
    PERMISSION_GUEST_TAGS,
    PERMISSION_GUEST_UPDATE,
    PERMISSION_GUEST_VIEW,
    PERMISSION_DEFINITIONS,
    PERMISSION_OCCUPANCY_VIEW,
    PERMISSION_RESERVATION_CREATE,
    PERMISSION_RESERVATION_MANUAL_RATE,
    PERMISSION_RESERVATION_MOVE,
    PERMISSION_RESERVATION_MOVE_CAPACITY,
    PERMISSION_RESERVATION_MOVE_CATEGORY,
    PERMISSION_REPORTS_FINANCIAL_VIEW,
    PERMISSION_REPORTS_OPERATIONAL_VIEW,
    PERMISSION_ROOM_CLEANING_STATUS,
    PERMISSION_STOCK_ADJUST,
    PERMISSION_STOCK_OPERATE,
    can_role_hold_permission,
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
    assert rows[("receptionist", PERMISSION_GUEST_VIEW)] is True
    assert rows[("receptionist", PERMISSION_GUEST_CREATE)] is True
    assert rows[("receptionist", PERMISSION_GUEST_EDIT)] is True
    assert rows[("receptionist", PERMISSION_GUEST_TAGS)] is True
    assert rows[("housekeeping", PERMISSION_GUEST_EDIT)] is False
    assert rows[("housekeeping", PERMISSION_RESERVATION_CREATE)] is False
    assert rows[("housekeeping", PERMISSION_CHECKIN_PERFORM)] is False
    assert rows[("manager", PERMISSION_STOCK_OPERATE)] is True
    assert rows[("manager", PERMISSION_STOCK_ADJUST)] is False
    assert rows[("manager", PERMISSION_CASH_OPERATE)] is False
    assert rows[("manager", PERMISSION_CASH_APPROVE_DIFFERENCE)] is False
    assert rows[("receptionist", PERMISSION_CASH_OPERATE)] is True
    assert rows[("owner", PERMISSION_STOCK_ADJUST)] is True
    assert rows[("manager", PERMISSION_REPORTS_OPERATIONAL_VIEW)] is True
    assert rows[("manager", PERMISSION_REPORTS_FINANCIAL_VIEW)] is False
    assert rows[("owner", PERMISSION_REPORTS_FINANCIAL_VIEW)] is True
    assert rows[("co_owner", PERMISSION_REPORTS_FINANCIAL_VIEW)] is True
    assert rows[("housekeeping", PERMISSION_ROOM_CLEANING_STATUS)] is True
    # Product default: cleaning staff do not receive guest/reservation data.
    assert rows[("housekeeping", PERMISSION_OCCUPANCY_VIEW)] is False
    assert rows[("owner", PERMISSION_RESERVATION_MOVE)] is True
    assert rows[("owner", PERMISSION_RESERVATION_MOVE_CATEGORY)] is True
    assert rows[("owner", PERMISSION_RESERVATION_MOVE_CAPACITY)] is True
    assert rows[("co_owner", PERMISSION_RESERVATION_MOVE)] is True
    assert rows[("co_owner", PERMISSION_RESERVATION_MOVE_CATEGORY)] is True
    assert rows[("co_owner", PERMISSION_RESERVATION_MOVE_CAPACITY)] is True
    assert rows[("manager", PERMISSION_RESERVATION_MOVE)] is True
    assert rows[("manager", PERMISSION_RESERVATION_MOVE_CATEGORY)] is True
    assert rows[("manager", PERMISSION_RESERVATION_MOVE_CAPACITY)] is True
    assert rows[("receptionist", PERMISSION_RESERVATION_MOVE)] is True
    assert rows[("receptionist", PERMISSION_RESERVATION_MOVE_CATEGORY)] is False
    assert rows[("receptionist", PERMISSION_RESERVATION_MOVE_CAPACITY)] is False
    assert rows[("housekeeping", PERMISSION_RESERVATION_MOVE)] is False
    assert rows[("housekeeping", PERMISSION_RESERVATION_MOVE_CATEGORY)] is False
    assert rows[("housekeeping", PERMISSION_RESERVATION_MOVE_CAPACITY)] is False
    assert rows[("owner", PERMISSION_GUEST_ROOM_AVOIDANCE_RESOLVE)] is True
    assert rows[("co_owner", PERMISSION_GUEST_ROOM_AVOIDANCE_RESOLVE)] is True
    assert rows[("manager", PERMISSION_GUEST_ROOM_AVOIDANCE_RESOLVE)] is True
    assert rows[("receptionist", PERMISSION_GUEST_ROOM_AVOIDANCE_RESOLVE)] is False
    assert rows[("housekeeping", PERMISSION_GUEST_ROOM_AVOIDANCE_RESOLVE)] is False
    # Defaults remain conservative, but they are editable starting values
    # rather than a permanent ceiling for an explicit owner override.
    assert rows[("manager", PERMISSION_STOCK_ADJUST)] is False
    assert can_role_hold_permission("manager", PERMISSION_STOCK_ADJUST) is True
    assert can_role_hold_permission("manager", PERMISSION_RESERVATION_MANUAL_RATE) is True


def test_permission_override_can_deny_receptionist_guest_edit(db):
    _seed_hotel(db, 1)
    seed_default_permissions(db)

    assert resolve(db, 1, "receptionist", PERMISSION_GUEST_EDIT) is True

    set_override(db, 1, "receptionist", PERMISSION_GUEST_EDIT, False, user_id=None)

    assert resolve(db, 1, "receptionist", PERMISSION_GUEST_EDIT) is False
    audit = db.query(SecurityAuditLog).filter(SecurityAuditLog.action == "permission.override.updated").one()
    assert audit.hotel_id == 1


def test_housekeeping_cannot_create_reservation_by_default(db):
    _seed_hotel(db, 1)
    seed_default_permissions(db)

    assert resolve(db, 1, "housekeeping", PERMISSION_RESERVATION_CREATE) is False


def test_owner_override_can_grant_permission_missing_from_role_default(db):
    _seed_hotel(db, 1)
    seed_default_permissions(db)
    assert resolve(db, 1, "housekeeping", PERMISSION_GUEST_VIEW) is False

    set_override(db, 1, "housekeeping", PERMISSION_GUEST_VIEW, True, user_id=None)

    assert resolve(db, 1, "housekeeping", PERMISSION_GUEST_VIEW) is True
    matrix = get_matrix(db, 1)
    assert matrix["housekeeping"][PERMISSION_GUEST_READ]["allowed"] is True
    assert matrix["housekeeping"][PERMISSION_GUEST_READ]["source"] == "override"
    assert matrix["housekeeping"][PERMISSION_GUEST_READ]["help_es"]


def test_override_in_hotel_a_does_not_affect_hotel_b(db):
    _seed_hotel(db, 1)
    _seed_hotel(db, 2)
    seed_default_permissions(db)

    set_override(db, 1, "receptionist", PERMISSION_GUEST_EDIT, False, user_id=None)

    assert resolve(db, 1, "receptionist", PERMISSION_GUEST_EDIT) is False
    assert resolve(db, 2, "receptionist", PERMISSION_GUEST_EDIT) is True


def test_get_matrix_includes_hotel_overrides(db):
    _seed_hotel(db, 1)
    seed_default_permissions(db)
    set_override(db, 1, "receptionist", PERMISSION_GUEST_EDIT, False, user_id=None)

    matrix = get_matrix(db, 1)

    assert matrix["receptionist"][PERMISSION_GUEST_UPDATE]["allowed"] is False
    assert matrix["receptionist"][PERMISSION_GUEST_UPDATE]["source"] == "override"


def test_resolve_seeds_the_matrix_once_per_engine_not_per_call(db):
    """A1: resolve() used to call seed_default_permissions() on every invocation

    (~120 rows inserted/repaired + a full RolePermissionDefault scan + 2 flushes,
    every single authenticated request). Two consecutive resolve() calls on the
    same engine must seed at most once; the second call should cost ~2 queries
    (override lookup + default lookup), not re-run the whole seed.
    """
    _seed_hotel(db, 1)
    engine = db.get_bind()

    query_counts: list[int] = [0]

    def _count_query(*_args, **_kwargs):
        query_counts[0] += 1

    event.listen(engine, "before_cursor_execute", _count_query)
    try:
        query_counts[0] = 0
        resolve(db, 1, "receptionist", PERMISSION_GUEST_EDIT)
        first_call_queries = query_counts[0]

        query_counts[0] = 0
        resolve(db, 1, "receptionist", PERMISSION_GUEST_EDIT)
        second_call_queries = query_counts[0]
    finally:
        event.remove(engine, "before_cursor_execute", _count_query)

    # The first call still has to seed a cold engine (insert-if-missing on two
    # tables + a full RolePermissionDefault scan), so it costs more than a
    # plain override/default lookup.
    assert first_call_queries > 2
    # The second call must not repeat the seed: only override + default lookups.
    assert second_call_queries <= 2


def test_permission_seed_is_safe_when_two_requests_initialize_it_concurrently(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'permission-seed.sqlite').as_posix()}"
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    from app.database import Base

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def seed_in_request() -> None:
        with SessionLocal() as session:
            seed_default_permissions(session)
            session.commit()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(seed_in_request) for _ in range(2)]
        for future in futures:
            future.result()

    with SessionLocal() as session:
        assert session.query(Permission).count() == len(PERMISSION_DEFINITIONS)
        assert session.query(RolePermissionDefault).count() == sum(
            len(permissions) for permissions in DEFAULT_MATRIX.values()
        )

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
