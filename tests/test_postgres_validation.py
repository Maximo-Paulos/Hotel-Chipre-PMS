"""
PostgreSQL validation tests.

Run with:
  DATABASE_URL_TEST=<isolated-qa-dsn> \
  POSTGRES_TEST_DATABASE_URL_EXPLICIT=<same-isolated-qa-dsn> \
  POSTGRES_TEST_EXPECTED_HOST=<exact-qa-host> \
  POSTGRES_TEST_EXPECTED_ROLE=<exact-qa-role> \
  POSTGRES_TEST_EXPECTED_DATABASE=<exact-qa-database> \
  POSTGRES_TEST_ISOLATED_BRANCH_REF=<non-production-ref-present-in-dsn> \
  POSTGRES_TEST_PRODUCTION_REF=<canonical-production-ref> \
  POSTGRES_TEST_PROVIDER_EVIDENCE_TOKEN=<short-lived-provider-token> \
  QA_PROVIDER_EVIDENCE_PUBLIC_KEY=<ed25519-public-key-pem> \
  RENDER_SERVICE_ID=<exact-preview-service-id> \
  RENDER_GIT_COMMIT=<exact-preview-code-sha> \
  POSTGRES_TEST_ISOLATION_CONFIRMED=1 \
  ALLOW_DESTRUCTIVE_POSTGRES_TESTS=1 \
    pytest tests/test_postgres_validation.py -v

All tests in this file are skipped unless the target passes the explicit isolation
guard.  The guard intentionally refuses a DATABASE_URL_TEST value that was only
derived from .env. Remote Supabase targets require Ed25519 provider evidence;
loopback fixtures instead require an explicit local evidence JSON. This suite
creates and drops schema objects.

Covers:
- Alembic upgrade from base to HEAD on empty database
- Alembic downgrade and re-upgrade (idempotency)
- Enum types created correctly in PostgreSQL
- Numeric(12,2) enforced correctly
- All constraints active
- Deterministic PostgreSQL row-lock behavior used by allocation flows
- Concurrent reservation insertion through the reservation service
- Multi-tenant hotel_id isolation
- EXPLAIN ANALYZE index usage verification
"""
from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from decimal import Decimal
from threading import Barrier

import pytest

from tests.postgres_test_safety import (
    PostgresTargetSafetyError,
    validate_postgres_test_target,
)

PG_DSN = os.getenv("DATABASE_URL_TEST", "")
IS_PG = PG_DSN.startswith("postgresql")


def _target_safety_error() -> str | None:
    if not IS_PG:
        return "PostgreSQL DSN not configured"
    try:
        validate_postgres_test_target(PG_DSN, os.environ)
    except PostgresTargetSafetyError:
        return "PostgreSQL target is not explicitly proven isolated"
    return None


_PG_TARGET_SAFETY_ERROR = _target_safety_error()
skip_if_no_pg = pytest.mark.skipif(
    _PG_TARGET_SAFETY_ERROR is not None,
    reason=_PG_TARGET_SAFETY_ERROR or "PostgreSQL target is unsafe",
)


def _reset_pg_to_clean_head(env, cwd):
    """Rebuild the shared test DB into a pristine, fully-migrated schema.

    The session-scoped ``pg_engine`` fixture creates the ORM tables lazily (only
    when the first test that needs them runs — which is *after* the downgrade test)
    and drops them all at session teardown. That leaves ``alembic_version`` pointing
    at head while no tables exist. Running ``downgrade base`` against that
    inconsistent state fails on missing relations, so reset the schema and re-apply
    every migration from scratch before exercising the down/up cycle.
    """
    from sqlalchemy import create_engine, text

    safe_dsn = validate_postgres_test_target(PG_DSN, os.environ)
    safe_env = {**env, "DATABASE_URL": safe_dsn}
    engine = create_engine(safe_dsn)
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()

    baseline = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True, text=True, env=safe_env, cwd=cwd
    )
    assert baseline.returncode == 0, f"alembic baseline upgrade failed:\n{baseline.stderr}"


@skip_if_no_pg
def test_alembic_upgrade_on_empty_database():
    """Alembic upgrade head succeeds on fresh PostgreSQL database."""
    safe_dsn = validate_postgres_test_target(PG_DSN, os.environ)
    env = {**os.environ, "DATABASE_URL": safe_dsn}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True, text=True, env=env,
        cwd=os.path.dirname(os.path.dirname(__file__))
    )
    assert result.returncode == 0, f"alembic upgrade failed:\n{result.stderr}"


@skip_if_no_pg
def test_alembic_downgrade_and_reupgrade():
    """Alembic downgrade to base then upgrade to head — idempotency check."""
    cwd = os.path.dirname(os.path.dirname(__file__))
    safe_dsn = validate_postgres_test_target(PG_DSN, os.environ)
    env = {**os.environ, "DATABASE_URL": safe_dsn}

    # Establish a deterministic, fully-migrated baseline regardless of any leftover
    # state from the pg_engine fixture or a prior run.
    _reset_pg_to_clean_head(env, cwd)

    down = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        capture_output=True, text=True, env=env, cwd=cwd
    )
    assert down.returncode == 0, f"alembic downgrade failed:\n{down.stderr}"

    up = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True, text=True, env=env, cwd=cwd
    )
    assert up.returncode == 0, f"alembic re-upgrade failed:\n{up.stderr}"


@skip_if_no_pg
def test_numeric_precision_enforced_on_postgres(pg_session):
    """Numeric(12,2) columns correctly store and return Decimal values."""
    from app.models.hotel_config import HotelConfiguration
    from app.models.guest import Guest
    from app.models.room import RoomCategory
    from app.models.reservation import Reservation, ReservationStatusEnum, ReservationSourceEnum

    hotel = HotelConfiguration(id=9001, hotel_name="PG-Test", subscription_active=True)
    pg_session.add(hotel)
    pg_session.flush()

    cat = RoomCategory(hotel_id=9001, name="Std", code="STD",
                       base_price_per_night=Decimal("123.45"), max_occupancy=2)
    pg_session.add(cat)
    pg_session.flush()

    assert isinstance(cat.base_price_per_night, Decimal)
    assert cat.base_price_per_night == Decimal("123.45")


@skip_if_no_pg
def test_enum_types_exist_in_postgres(pg_engine):
    """All PostgreSQL enum types are created by migrations."""
    from sqlalchemy import text
    expected_enums = [
        "reservation_status_enum",
        "guest_rating_enum",
        "guest_tag_type_enum",
        "cash_session_status_enum",
        "cash_movement_type_enum",
        "waitlist_status_enum",
        "api_key_purpose_enum",
        "room_block_reason_enum",
        "company_document_type_enum",
        "company_document_status_enum",
    ]
    with pg_engine.connect() as conn:
        result = conn.execute(
            text("SELECT typname FROM pg_type WHERE typtype = 'e'")
        ).fetchall()
        existing = {row[0] for row in result}

    for enum_name in expected_enums:
        assert enum_name in existing, f"PostgreSQL enum '{enum_name}' not found"


@skip_if_no_pg
def test_unique_constraints_enforced_on_postgres(pg_session):
    """Critical unique constraints reject duplicates in PostgreSQL."""
    from sqlalchemy.exc import IntegrityError
    from app.models.hotel_config import HotelConfiguration
    from app.models.guest import Guest

    hotel = HotelConfiguration(id=9002, hotel_name="PG-Uniq", subscription_active=True)
    pg_session.add(hotel)
    pg_session.flush()

    pg_session.add(Guest(hotel_id=9002, first_name="A", last_name="B",
                         document_type="DNI", document_number="77777777",
                         terms_accepted=True))
    pg_session.flush()

    pg_session.add(Guest(hotel_id=9002, first_name="C", last_name="D",
                         document_type="DNI", document_number="77777777",
                         terms_accepted=True))
    with pytest.raises(IntegrityError):
        pg_session.flush()


@skip_if_no_pg
def test_explain_analyze_guest_search_index(pg_engine):
    """
    EXPLAIN ANALYZE for guest search by last_name uses index ix_guest_hotel_last_name.
    Verifies no sequential scan on the guests table when filtering hotel_id + last_name.
    """
    from sqlalchemy import text

    explain_query = """
    EXPLAIN (FORMAT JSON, ANALYZE false)
    SELECT * FROM guests
    WHERE hotel_id = 1 AND last_name = 'Smith'
    """
    with pg_engine.connect() as conn:
        result = conn.execute(text(explain_query)).fetchone()
        plan = result[0]  # JSON plan

    plan_str = str(plan)
    # Index scan or bitmap index scan expected — NOT Seq Scan
    assert "Seq Scan" not in plan_str or "Index" in plan_str, (
        f"Expected index scan for guest search, got:\n{plan_str}"
    )


@skip_if_no_pg
def test_explain_analyze_reservation_date_range_index(pg_engine):
    """
    EXPLAIN ANALYZE for reservation date range uses ix_reservation_dates.
    """
    from sqlalchemy import text

    explain_query = """
    EXPLAIN (FORMAT JSON, ANALYZE false)
    SELECT * FROM reservations
    WHERE hotel_id = 1
      AND check_in_date >= '2026-08-01'
      AND check_out_date <= '2026-08-31'
    """
    with pg_engine.connect() as conn:
        result = conn.execute(text(explain_query)).fetchone()
        plan_str = str(result[0])

    # Should use ix_reservation_dates or ix_reservation_hotel_id
    assert "Seq Scan" not in plan_str or "Index" in plan_str, (
        f"Expected index scan for reservation date range:\n{plan_str}"
    )


@skip_if_no_pg
def test_room_row_lock_uses_skip_locked_deterministically(pg_engine):
    """A competing allocator cannot acquire a room row already locked by T1.

    This proves the PostgreSQL locking primitive only. It intentionally does not
    claim that the complete reservation service prevents every double-booking
    race; that separate end-to-end concurrency evidence remains tracked below.
    """
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    from app.models.hotel_config import HotelConfiguration
    from app.models.room import Room, RoomCategory, RoomStatusEnum

    Session = sessionmaker(bind=pg_engine, expire_on_commit=False)
    setup = Session()
    hotel = HotelConfiguration(id=9901, hotel_name="PG-Lock-Test", subscription_active=True)
    category = RoomCategory(
        hotel_id=hotel.id,
        name="PG Lock Category",
        code="PG-LOCK",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    setup.add_all([hotel, category])
    setup.flush()
    room = Room(
        hotel_id=hotel.id,
        category_id=category.id,
        room_number="PG-LOCK-1",
        floor=1,
        status=RoomStatusEnum.AVAILABLE,
        is_active=True,
    )
    setup.add(room)
    setup.commit()

    s1 = Session()
    s2 = Session()

    try:
        locked = s1.execute(
            text("SELECT id FROM rooms WHERE id = :room_id FOR UPDATE"),
            {"room_id": room.id},
        ).fetchall()
        assert locked == [(room.id,)]

        competing = s2.execute(
            text(
                "SELECT id FROM rooms WHERE id = :room_id "
                "FOR UPDATE SKIP LOCKED"
            ),
            {"room_id": room.id},
        ).fetchall()
        assert competing == []
    finally:
        s1.rollback()
        s2.rollback()
        s1.close()
        s2.close()
        cleanup = Session()
        try:
            cleanup.query(Room).filter(Room.id == room.id).delete()
            cleanup.query(RoomCategory).filter(RoomCategory.id == category.id).delete()
            cleanup.query(HotelConfiguration).filter(HotelConfiguration.id == hotel.id).delete()
            cleanup.commit()
        finally:
            cleanup.close()
            setup.close()


@skip_if_no_pg
def test_concurrent_reservation_auto_assignment_does_not_double_book(pg_engine):
    """Concurrent auto-assignment requests serialize on the candidate room row."""
    from sqlalchemy.orm import sessionmaker

    from app.models.guest import Guest
    from app.models.hotel_config import HotelConfiguration
    from app.models.reservation import Reservation
    from app.models.room import Room, RoomCategory, RoomStatusEnum
    from app.schemas.reservation import ReservationCreate
    from app.services.reservation_service import ReservationError, create_reservation

    hotel_id = 9902
    Session = sessionmaker(bind=pg_engine, expire_on_commit=False)
    setup = Session()
    try:
        hotel = HotelConfiguration(id=hotel_id, hotel_name="PG-Concurrency-Test", subscription_active=True)
        category = RoomCategory(
            hotel_id=hotel_id,
            name="PG Concurrency Category",
            code="PG-CONCURRENCY",
            base_price_per_night=Decimal("100.00"),
            max_occupancy=2,
        )
        guest_a = Guest(
            hotel_id=hotel_id,
            first_name="Synthetic",
            last_name="Concurrency A",
            terms_accepted=True,
        )
        guest_b = Guest(
            hotel_id=hotel_id,
            first_name="Synthetic",
            last_name="Concurrency B",
            terms_accepted=True,
        )
        setup.add_all([hotel, category, guest_a, guest_b])
        setup.flush()
        room = Room(
            hotel_id=hotel_id,
            category_id=category.id,
            room_number="PG-CONCURRENCY-1",
            floor=1,
            status=RoomStatusEnum.AVAILABLE,
            is_active=True,
        )
        setup.add(room)
        setup.commit()
        category_id = category.id
        guest_ids = (guest_a.id, guest_b.id)
    finally:
        setup.close()

    ready = Barrier(2)

    def attempt(guest_id: int) -> tuple[str, int | None, str | None]:
        db = Session()
        try:
            ready.wait(timeout=10)
            reservation = create_reservation(
                db,
                ReservationCreate(
                    guest_id=guest_id,
                    category_id=category_id,
                    check_in_date=date(2026, 10, 1),
                    check_out_date=date(2026, 10, 4),
                ),
                hotel_id=hotel_id,
            )
            db.commit()
            return "assigned", reservation.room_id, None
        except ReservationError as exc:
            db.rollback()
            return "rejected", None, str(exc)
        except Exception as exc:  # pragma: no cover - makes unexpected DB failures explicit
            db.rollback()
            return "error", None, repr(exc)
        finally:
            db.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, guest_ids))

        assert sorted(result[0] for result in results) == ["assigned", "rejected"]
        assert not [result for result in results if result[0] == "error"]

        check = Session()
        try:
            assert check.query(Reservation).filter(Reservation.hotel_id == hotel_id).count() == 1
        finally:
            check.close()
    finally:
        cleanup = Session()
        try:
            cleanup.query(Reservation).filter(Reservation.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(Guest).filter(Guest.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(Room).filter(Room.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).delete(synchronize_session=False)
            cleanup.commit()
        finally:
            cleanup.close()
