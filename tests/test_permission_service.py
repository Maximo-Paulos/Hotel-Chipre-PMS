from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.dependencies.auth import AuthContext, require_all_permissions
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.hotel_role import HotelRole
from app.models.permission import (
    HotelPermissionOverride,
    Permission,
    RolePermissionDefault,
    UserPermissionOverride,
)
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.services.permission_service import (
    DEFAULT_MATRIX,
    PERMISSION_APIKEY_MANAGE,
    PERMISSION_CASH_APPROVE_DIFFERENCE,
    PERMISSION_CASH_OPERATE,
    PERMISSION_CHECKIN_PERFORM,
    PERMISSION_COMPANY_NIGHT_RATE_MANAGE,
    PERMISSION_DEFINITIONS,
    PERMISSION_GUEST_CREATE,
    PERMISSION_GUEST_EDIT,
    PERMISSION_GUEST_READ,
    PERMISSION_GUEST_ROOM_AVOIDANCE_RESOLVE,
    PERMISSION_GUEST_TAGS,
    PERMISSION_GUEST_UPDATE,
    PERMISSION_GUEST_VIEW,
    PERMISSION_HOTEL_PROPERTY_MANAGE,
    PERMISSION_HOTEL_SECURITY_MANAGE,
    PERMISSION_OCCUPANCY_VIEW,
    PERMISSION_PAYMENT_REFUND,
    PERMISSION_REPORTS_FINANCIAL_VIEW,
    PERMISSION_REPORTS_OPERATIONAL_VIEW,
    PERMISSION_RESERVATION_CANCEL_PAID,
    PERMISSION_RESERVATION_CHARGE,
    PERMISSION_RESERVATION_CREATE,
    PERMISSION_RESERVATION_MANUAL_RATE,
    PERMISSION_RESERVATION_MANUAL_RATE_POLICY_MANAGE,
    PERMISSION_RESERVATION_MOVE,
    PERMISSION_RESERVATION_MOVE_CAPACITY,
    PERMISSION_RESERVATION_MOVE_CATEGORY,
    PERMISSION_RESERVATION_MOVEMENT_GROUP_REVERT,
    PERMISSION_RESERVATION_PAID_TOTAL_ADJUST,
    PERMISSION_ROOM_CLEANING_STATUS,
    PERMISSION_SETTINGS_DAILY_REPORT_VIEW,
    PERMISSION_SETTINGS_NOTIFICATIONS_VIEW,
    PERMISSION_STOCK_ADJUST,
    PERMISSION_STOCK_OPERATE,
    PERMISSION_WHATSAPP_INBOX_VIEW,
    PERMISSION_WHATSAPP_NOTE_MANAGE,
    can_role_hold_permission,
    ensure_permission_matrix_seeded,
    get_matrix,
    resolve,
    resolve_many,
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
    assert rows[("manager", PERMISSION_CASH_OPERATE)] is True
    assert rows[("manager", PERMISSION_RESERVATION_CHARGE)] is True
    assert rows[("manager", PERMISSION_PAYMENT_REFUND)] is True
    assert rows[("manager", PERMISSION_RESERVATION_CANCEL_PAID)] is True
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
    assert rows[("housekeeping", PERMISSION_WHATSAPP_INBOX_VIEW)] is False
    assert rows[("housekeeping", PERMISSION_WHATSAPP_NOTE_MANAGE)] is False
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
    assert rows[("owner", PERMISSION_RESERVATION_MOVEMENT_GROUP_REVERT)] is True
    assert rows[("co_owner", PERMISSION_RESERVATION_MOVEMENT_GROUP_REVERT)] is True
    assert rows[("manager", PERMISSION_RESERVATION_MOVEMENT_GROUP_REVERT)] is True
    assert rows[("receptionist", PERMISSION_RESERVATION_MOVEMENT_GROUP_REVERT)] is False
    assert rows[("housekeeping", PERMISSION_RESERVATION_MOVEMENT_GROUP_REVERT)] is False
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
    assert resolve(db, 1, "co_owner", PERMISSION_RESERVATION_MANUAL_RATE) is True
    assert resolve(db, 1, "co_owner", PERMISSION_RESERVATION_MANUAL_RATE_POLICY_MANAGE) is True
    assert resolve(db, 1, "co_owner", PERMISSION_RESERVATION_PAID_TOTAL_ADJUST) is True
    assert resolve(db, 1, "co_owner", PERMISSION_APIKEY_MANAGE) is True
    assert resolve(db, 1, "co_owner", PERMISSION_HOTEL_SECURITY_MANAGE) is True
    assert resolve(db, 1, "co_owner", PERMISSION_HOTEL_PROPERTY_MANAGE) is False


def test_company_night_rate_permission_defaults_allow_management_roles(db):
    _seed_hotel(db, 1)
    seed_default_permissions(db)

    rows = {
        (row.role, row.permission_code): row.allowed
        for row in db.query(RolePermissionDefault).all()
    }
    assert rows[("owner", PERMISSION_COMPANY_NIGHT_RATE_MANAGE)] is True
    assert rows[("co_owner", PERMISSION_COMPANY_NIGHT_RATE_MANAGE)] is True
    assert rows[("manager", PERMISSION_COMPANY_NIGHT_RATE_MANAGE)] is True
    assert rows[("receptionist", PERMISSION_COMPANY_NIGHT_RATE_MANAGE)] is False
    assert can_role_hold_permission("manager", PERMISSION_COMPANY_NIGHT_RATE_MANAGE) is True
    assert can_role_hold_permission("receptionist", PERMISSION_COMPANY_NIGHT_RATE_MANAGE) is False

    set_override(db, 1, "manager", PERMISSION_COMPANY_NIGHT_RATE_MANAGE, False, user_id=None)
    assert resolve(db, 1, "manager", PERMISSION_COMPANY_NIGHT_RATE_MANAGE) is False

    with pytest.raises(ValueError, match="bloqueado"):
        set_override(
            db,
            1,
            "receptionist",
            PERMISSION_COMPANY_NIGHT_RATE_MANAGE,
            True,
            user_id=None,
        )


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


def test_resolve_many_preserves_user_role_and_hotel_override_precedence(db):
    _seed_hotel(db, 1)
    _seed_hotel(db, 2)
    seed_default_permissions(db)
    user = User(id=210, email="batch-permission@example.test", password_hash="synthetic")
    db.add(user)
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=1, user_id=user.id, role="receptionist", status="active"),
            HotelMembership(hotel_id=2, user_id=user.id, role="receptionist", status="active"),
            HotelPermissionOverride(
                hotel_id=1,
                role="receptionist",
                permission_code=PERMISSION_GUEST_READ,
                allowed=False,
            ),
            UserPermissionOverride(
                hotel_id=1,
                user_id=user.id,
                permission_code=PERMISSION_GUEST_READ,
                allowed=True,
            ),
            HotelPermissionOverride(
                hotel_id=1,
                role="receptionist",
                permission_code=PERMISSION_GUEST_CREATE,
                allowed=False,
            ),
        ]
    )
    db.flush()

    hotel_one = resolve_many(
        db,
        1,
        "receptionist",
        (PERMISSION_GUEST_READ, PERMISSION_GUEST_CREATE, PERMISSION_STOCK_ADJUST, "unknown:capability"),
        user_id=user.id,
    )
    hotel_two = resolve_many(
        db,
        2,
        "receptionist",
        (PERMISSION_GUEST_READ, PERMISSION_GUEST_CREATE),
        user_id=user.id,
    )

    assert hotel_one == {
        PERMISSION_GUEST_READ: True,  # User grant takes precedence over hotel-role denial.
        PERMISSION_GUEST_CREATE: False,  # Hotel-role denial takes precedence over the default.
        PERMISSION_STOCK_ADJUST: False,  # Default deny is retained.
        "unknown:capability": False,
    }
    assert hotel_two == {
        PERMISSION_GUEST_READ: True,  # No override from hotel 1 leaks into hotel 2.
        PERMISSION_GUEST_CREATE: True,
    }


def test_resolve_many_preserves_legacy_deny_fallback_and_invariants(db):
    _seed_hotel(db, 1)
    seed_default_permissions(db)
    user = User(id=211, email="legacy-permission@example.test", password_hash="synthetic")
    db.add(user)
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=1, user_id=user.id, role="co_owner", status="active"),
            HotelPermissionOverride(
                hotel_id=1,
                role="co_owner",
                permission_code=PERMISSION_SETTINGS_NOTIFICATIONS_VIEW,
                allowed=False,
            ),
            HotelPermissionOverride(
                hotel_id=1,
                role="co_owner",
                permission_code=PERMISSION_HOTEL_PROPERTY_MANAGE,
                allowed=True,
            ),
        ]
    )
    db.flush()

    decisions = resolve_many(
        db,
        1,
        "co_owner",
        (PERMISSION_SETTINGS_DAILY_REPORT_VIEW, PERMISSION_HOTEL_PROPERTY_MANAGE),
        user_id=user.id,
    )
    assert decisions[PERMISSION_SETTINGS_DAILY_REPORT_VIEW] is False
    # Owner-only invariant remains authoritative over a stored grant.
    assert decisions[PERMISSION_HOTEL_PROPERTY_MANAGE] is False

    db.add(
        UserPermissionOverride(
            hotel_id=1,
            user_id=user.id,
            permission_code=PERMISSION_SETTINGS_DAILY_REPORT_VIEW,
            allowed=True,
        )
    )
    db.flush()
    assert resolve_many(
        db,
        1,
        "co_owner",
        (PERMISSION_SETTINGS_DAILY_REPORT_VIEW,),
        user_id=user.id,
    )[PERMISSION_SETTINGS_DAILY_REPORT_VIEW] is True


def test_resolve_many_custom_role_is_hotel_scoped_and_reads_fresh_revocation(db):
    _seed_hotel(db, 1)
    _seed_hotel(db, 2)
    seed_default_permissions(db)
    role_code = "cr_batched"
    db.add_all(
        [
            HotelRole(
                hotel_id=1,
                code=role_code,
                name="Custom reception",
                name_key="custom reception",
                base_role="receptionist",
                is_active=True,
            ),
            HotelRole(
                hotel_id=2,
                code=role_code,
                name="Custom housekeeping",
                name_key="custom housekeeping",
                base_role="housekeeping",
                is_active=True,
            ),
            HotelPermissionOverride(
                hotel_id=1,
                role=role_code,
                permission_code=PERMISSION_GUEST_READ,
                allowed=True,
            ),
        ]
    )
    db.flush()

    assert resolve_many(db, 1, role_code, (PERMISSION_GUEST_READ,))[PERMISSION_GUEST_READ] is True
    assert resolve_many(db, 2, role_code, (PERMISSION_GUEST_READ,))[PERMISSION_GUEST_READ] is False

    # No process cache is involved: a committed revocation affects the next read.
    override = db.query(HotelPermissionOverride).filter_by(
        hotel_id=1,
        role=role_code,
        permission_code=PERMISSION_GUEST_READ,
    ).one()
    override.allowed = False
    db.commit()
    assert resolve_many(db, 1, role_code, (PERMISSION_GUEST_READ,))[PERMISSION_GUEST_READ] is False


def test_require_all_permissions_batches_effective_and_step_up_policy_reads(db):
    _seed_hotel(db, 1)
    seed_default_permissions(db)
    ensure_permission_matrix_seeded(db)
    context = AuthContext(
        hotel_id=1,
        user_id=212,
        user_role="receptionist",
        is_verified=True,
        permissions=set(),
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 1234),
            "root_path": "",
            "path": "/api/test/require-all",
            "query_string": b"",
            "headers": [],
        }
    )
    query_count = 0

    def count_query(*_args, **_kwargs):
        nonlocal query_count
        query_count += 1

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", count_query)
    try:
        authorized = require_all_permissions(PERMISSION_GUEST_READ, PERMISSION_GUEST_CREATE)(
            request,
            db,
            context,
        )
    finally:
        event.remove(engine, "before_cursor_execute", count_query)

    assert authorized is context
    assert context.permissions == {PERMISSION_GUEST_READ, PERMISSION_GUEST_CREATE}
    # One joined read for defaults and both override layers, plus one batched
    # step-up catalog read, independent of the number of requested permissions.
    assert query_count == 2

    denied_context = AuthContext(
        hotel_id=1,
        user_id=None,
        user_role="receptionist",
        is_verified=True,
        permissions=set(),
    )
    with pytest.raises(HTTPException) as denied:
        require_all_permissions(PERMISSION_GUEST_READ, PERMISSION_STOCK_ADJUST)(
            request,
            db,
            denied_context,
        )
    assert denied.value.status_code == 403
    audit = db.query(SecurityAuditLog).filter_by(action="permission.denied").one()
    assert audit.hotel_id == 1
    assert audit.resource_id == PERMISSION_STOCK_ADJUST


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
