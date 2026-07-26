"""Live PostgreSQL RLS behavioral verification.

Unlike tests/test_tenant_rls_contract.py (which only asserts the *text* of the
RLS migration), these tests execute real queries against a real PostgreSQL
server with RLS policies active, proving the isolation/bypass mechanisms in
app/services/tenant_context.py actually work at the database level -- not
just that the migration source code looks right.

Two connection-design requirements make these assertions meaningful instead
of silently proving nothing:

1. Verification queries run as a dedicated NOSUPERUSER/NOBYPASSRLS role, not
   as the DATABASE_URL_TEST role. PostgreSQL superusers and BYPASSRLS roles
   bypass row security unconditionally.
2. Seed data is inserted through a plain, genuinely-committing ORM session,
   not the pg_session fixture. pg_session wraps each test in an outer
   transaction that is always rolled back at teardown (the standard
   test-isolation pattern) -- rows inserted through it are only visible
   within that same connection, never to the separate app_test_role
   connection used for verification. Seeding via the ORM (not raw INSERT
   SQL) also picks up Column(default=...) values that only apply at the
   ORM layer, not as server-side defaults.

Setup (once per local Postgres instance): a NOSUPERUSER NOBYPASSRLS role with
full grants on the public schema, e.g.:
  CREATE ROLE app_test_role WITH LOGIN NOSUPERUSER NOBYPASSRLS;
  GRANT USAGE ON SCHEMA public TO app_test_role;
  GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_test_role;
  GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_test_role;

Run with the same env as tests/test_postgres_validation.py (see that file's
module docstring for the full variable list), plus:
  RLS_TEST_ROLE_DSN=postgresql://app_test_role@<host>:<port>/<database>
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from tests.postgres_test_safety import (
    PostgresTargetSafetyError,
    validate_postgres_test_target,
)

PG_DSN = os.getenv("DATABASE_URL_TEST", "")
IS_PG = PG_DSN.startswith("postgresql")
ROLE_DSN = os.getenv("RLS_TEST_ROLE_DSN", "")


def _target_safety_error() -> str | None:
    if not IS_PG:
        return "PostgreSQL DSN not configured"
    if not ROLE_DSN:
        return "RLS_TEST_ROLE_DSN not configured"
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


def _role_connection():
    return create_engine(ROLE_DSN)


def _seed_engine():
    """A superuser engine whose commits are REAL, visible to other connections.

    See module docstring: pg_session's outer-transaction-rolled-back-at-teardown
    pattern makes it unsuitable for seeding data that a second, independent
    connection (the app_test_role one) needs to actually see.
    """
    safe_dsn = validate_postgres_test_target(PG_DSN, os.environ)
    return create_engine(safe_dsn)


def _seed_session(engine):
    return sessionmaker(bind=engine)()


@skip_if_no_pg
def test_tenant_isolation_blocks_cross_hotel_reads():
    """With app.hotel_id set to hotel A, hotel B's rows are invisible -- as the
    unprivileged application role, not as a superuser (which always bypasses RLS)."""
    from app.models.hotel_config import HotelConfiguration
    from app.models.guest import Guest

    seed_engine = _seed_engine()
    role = _role_connection()
    seed = _seed_session(seed_engine)
    try:
        seed.add_all([
            HotelConfiguration(id=88001, hotel_name="RLS-A", subscription_active=True),
            HotelConfiguration(id=88002, hotel_name="RLS-B", subscription_active=True),
        ])
        seed.flush()
        seed.add_all([
            Guest(hotel_id=88001, first_name="Alice", last_name="A",
                  document_type="DNI", document_number="88001001", terms_accepted=True),
            Guest(hotel_id=88002, first_name="Bob", last_name="B",
                  document_type="DNI", document_number="88002001", terms_accepted=True),
        ])
        seed.commit()

        with role.connect() as conn:
            with conn.begin():
                conn.execute(text("SET LOCAL app.hotel_id = '88001'"))
                visible = conn.execute(
                    text("SELECT hotel_id, first_name FROM guests WHERE hotel_id IN (88001, 88002)")
                ).fetchall()
                assert visible == [(88001, "Alice")], f"Expected only hotel A's guest, saw: {visible}"

        with role.connect() as conn:
            with conn.begin():
                conn.execute(text("SET LOCAL app.hotel_id = '88002'"))
                visible = conn.execute(
                    text("SELECT hotel_id, first_name FROM guests WHERE hotel_id IN (88001, 88002)")
                ).fetchall()
                assert visible == [(88002, "Bob")], f"Expected only hotel B's guest, saw: {visible}"
    finally:
        seed.rollback()
        seed.execute(text("DELETE FROM guests WHERE hotel_id IN (88001, 88002)"))
        seed.execute(text("DELETE FROM hotel_configuration WHERE id IN (88001, 88002)"))
        seed.commit()
        seed.close()
        seed_engine.dispose()
        role.dispose()


@skip_if_no_pg
def test_no_tenant_context_hides_all_rows():
    """Without app.hotel_id set at all, RLS default-denies -- zero rows, not a leak."""
    from app.models.hotel_config import HotelConfiguration
    from app.models.guest import Guest

    seed_engine = _seed_engine()
    role = _role_connection()
    seed = _seed_session(seed_engine)
    try:
        seed.add(HotelConfiguration(id=88003, hotel_name="RLS-NoCtx", subscription_active=True))
        seed.flush()
        seed.add(Guest(hotel_id=88003, first_name="Carol", last_name="C",
                        document_type="DNI", document_number="88003001", terms_accepted=True))
        seed.commit()

        with role.connect() as conn:
            with conn.begin():
                visible = conn.execute(text("SELECT hotel_id FROM guests WHERE hotel_id = 88003")).fetchall()
                assert visible == [], f"Expected zero rows with no tenant context set, saw: {visible}"
    finally:
        seed.rollback()
        seed.execute(text("DELETE FROM guests WHERE hotel_id = 88003"))
        seed.execute(text("DELETE FROM hotel_configuration WHERE id = 88003"))
        seed.commit()
        seed.close()
        seed_engine.dispose()
        role.dispose()


@skip_if_no_pg
def test_master_admin_bypass_sees_all_hotels_subscriptions():
    """C2: with app.master_admin='true', subscriptions across hotels are visible.

    Without it, even a hotel-scoped context only sees its own hotel's row --
    proving the bypass is additive (opt-in), not a blanket disable of RLS.
    """
    from app.models.hotel_config import HotelConfiguration
    from app.models.subscription_v2 import Subscription

    seed_engine = _seed_engine()
    role = _role_connection()
    seed = _seed_session(seed_engine)
    try:
        seed.add_all([
            HotelConfiguration(id=88101, hotel_name="MA-A", subscription_active=True),
            HotelConfiguration(id=88102, hotel_name="MA-B", subscription_active=True),
        ])
        seed.flush()
        seed.add_all([
            Subscription(hotel_id=88101, plan="starter", status="active"),
            Subscription(hotel_id=88102, plan="pro", status="active"),
        ])
        seed.commit()

        with role.connect() as conn:
            with conn.begin():
                conn.execute(text("SET LOCAL app.hotel_id = '88101'"))
                scoped = conn.execute(
                    text("SELECT hotel_id FROM subscriptions WHERE hotel_id IN (88101, 88102)")
                ).fetchall()
                assert scoped == [(88101,)], f"Expected only the scoped hotel without master_admin, saw: {scoped}"

        with role.connect() as conn:
            with conn.begin():
                conn.execute(text("SET LOCAL app.hotel_id = '88101'"))
                conn.execute(text("SET LOCAL app.master_admin = 'true'"))
                all_visible = conn.execute(
                    text("SELECT hotel_id FROM subscriptions WHERE hotel_id IN (88101, 88102) ORDER BY hotel_id")
                ).fetchall()
                assert all_visible == [(88101,), (88102,)], (
                    f"Expected both hotels visible with master_admin bypass, saw: {all_visible}"
                )
    finally:
        seed.rollback()
        seed.execute(text("DELETE FROM subscriptions WHERE hotel_id IN (88101, 88102)"))
        seed.execute(text("DELETE FROM hotel_configuration WHERE id IN (88101, 88102)"))
        seed.commit()
        seed.close()
        seed_engine.dispose()
        role.dispose()


@skip_if_no_pg
def test_after_commit_listener_reapplies_hotel_context():
    """C1: app.hotel_id must survive a commit within the same ORM session.

    Uses the real app session factory bound to the unprivileged role (so RLS
    is actually enforced) to prove the after_commit listener registered on
    the Session class in app/database.py genuinely reapplies lost context.
    """
    from app.models.hotel_config import HotelConfiguration
    from app.models.guest import Guest
    from app.services.tenant_context import set_tenant_hotel_context

    seed_engine = _seed_engine()
    role = _role_connection()
    seed = _seed_session(seed_engine)
    try:
        seed.add(HotelConfiguration(id=88201, hotel_name="AfterCommit", subscription_active=True))
        seed.commit()

        RoleSession = sessionmaker(bind=role, expire_on_commit=False)
        session = RoleSession()
        try:
            set_tenant_hotel_context(session, 88201)
            session.add(Guest(hotel_id=88201, first_name="Dana", last_name="D",
                               document_type="DNI", document_number="88201001", terms_accepted=True))
            session.commit()  # Postgres SET LOCAL is transaction-scoped; this clears it server-side

            # If the after_commit listener didn't reapply app.hotel_id, this query
            # runs with no tenant context and RLS default-denies -- zero rows.
            visible = session.execute(
                text("SELECT first_name FROM guests WHERE hotel_id = 88201")
            ).fetchall()
            assert visible == [("Dana",)], (
                f"Expected the guest to still be visible after commit (listener should "
                f"have reapplied app.hotel_id), saw: {visible}"
            )
        finally:
            session.close()
    finally:
        seed.rollback()
        seed.execute(text("DELETE FROM guests WHERE hotel_id = 88201"))
        seed.execute(text("DELETE FROM hotel_configuration WHERE id = 88201"))
        seed.commit()
        seed.close()
        seed_engine.dispose()
        role.dispose()
