"""C2 evidence: master-admin RLS bypass, against a REAL PostgreSQL target only.

SQLite ignores row-level security entirely, so tests/test_master_admin_panel.py
only proves the request flow doesn't crash -- it cannot prove the RLS policy
itself does the right thing. This file is the functional proof, and it is
useless (auto-skipped) without an explicitly-isolated PostgreSQL DSN in
DATABASE_URL_TEST (see tests/postgres_test_safety.py). It was written and
reviewed but NOT executed in the security-auditor session that added it --
no PostgreSQL instance was reachable in that sandbox. Whoever runs this
against a real isolated Postgres before deploying the RLS migration to
production should treat a pass here as the actual verification gate the
plan requires; a pass in SQLite-only CI does not substitute for it.

Run with:
  DATABASE_URL_TEST=<isolated-qa-dsn> ... (same env as tests/test_postgres_validation.py)
    pytest tests/test_master_admin_rls_bypass_pg.py -v
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

import pytest

from tests.postgres_test_safety import (
    PostgresTargetSafetyError,
    validate_postgres_test_target,
)

PG_DSN = os.getenv("DATABASE_URL_TEST", "")
IS_PG = PG_DSN.startswith("postgresql")


def _target_safety_error() -> Optional[str]:
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


def _reset_and_migrate_to_head(safe_dsn: str, env: dict, cwd: str) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(safe_dsn)
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True, text=True, env=env, cwd=cwd,
    )
    assert result.returncode == 0, f"alembic upgrade head failed:\n{result.stderr}"


@skip_if_no_pg
def test_master_admin_reproduces_the_bug_then_the_bypass_fixes_it():
    """Reproduce the pre-fix bug, then prove the fix, on a real Postgres target.

    1. Migrate a clean schema to head (baseline tenant RLS migration +
       f3bdaadd3d15_master_admin_rls_bypass).
    2. Seed a Subscription for two different hotels.
    3. A connection that never sets app.hotel_id/app.master_admin -- exactly
       what app/master_admin/router.py did before this fix -- must see ZERO
       rows across both hotels. This is the correctness bug: the panel would
       have silently shown 0 active/trialing/past_due subscriptions.
    4. The same query, after set_master_admin_context's SQL
       (set_config('app.master_admin', 'true', true)), must see BOTH rows.
    5. An ordinary tenant session (app.hotel_id set, app.master_admin unset)
       must still see only its own hotel's row -- the bypass must not leak
       into normal tenant-scoped requests.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from app.models.hotel_config import HotelConfiguration
    from app.models.subscription_v2 import Subscription

    safe_dsn = validate_postgres_test_target(PG_DSN, os.environ)
    cwd = os.path.dirname(os.path.dirname(__file__))
    env = {**os.environ, "DATABASE_URL": safe_dsn}
    _reset_and_migrate_to_head(safe_dsn, env, cwd)

    engine = create_engine(safe_dsn)
    hotel_a, hotel_b = 99101, 99102
    try:
        # Seed through the ORM (for column defaults) with the bypass enabled,
        # since a plain insert would otherwise hit the same RLS WITH CHECK gap.
        # Keep app.hotel_id aligned with each seeded tenant as well: the ORM
        # change collector writes tenant-scoped domain_event_outbox rows, whose
        # own RLS policy intentionally requires a matching hotel context.
        with Session(engine) as session, session.begin():
            session.execute(text("SELECT set_config('app.master_admin', 'true', true)"))
            for hotel_id, hotel_name, owner_email in (
                (hotel_a, "PG RLS Hotel A", "a@example.test"),
                (hotel_b, "PG RLS Hotel B", "b@example.test"),
            ):
                session.execute(
                    text("SELECT set_config('app.hotel_id', :hotel_id, true)"),
                    {"hotel_id": str(hotel_id)},
                )
                session.add(
                    HotelConfiguration(
                        id=hotel_id,
                        hotel_name=hotel_name,
                        owner_email=owner_email,
                        subscription_active=True,
                    )
                )
                session.flush()
                session.add(
                    Subscription(
                        hotel_id=hotel_id,
                        plan="starter",
                        status="active",
                        room_limit=15,
                        staff_limit=3,
                        can_write_cache=True,
                    )
                )
                session.flush()
                # ``after_flush`` queues the subscription's outbox rows for
                # the next flush. Persist them before switching app.hotel_id
                # to the next tenant, or they would be checked against that
                # tenant's RLS context.
                session.flush()

        count_sql = text("SELECT count(*) FROM subscriptions WHERE hotel_id IN (:a, :b)")

        # Step 3 -- reproduce the bug: no context set at all.
        with engine.connect() as conn:
            no_context_count = conn.execute(count_sql, {"a": hotel_a, "b": hotel_b}).scalar_one()
        assert no_context_count == 0, (
            "Pre-fix bug did not reproduce: an uncontextualized connection must "
            "see zero subscription rows under FORCE ROW LEVEL SECURITY"
        )

        # Step 4 -- prove the fix: master_admin bypass sees both hotels.
        with engine.connect() as conn, conn.begin():
            conn.execute(text("SELECT set_config('app.master_admin', 'true', true)"))
            bypass_count = conn.execute(count_sql, {"a": hotel_a, "b": hotel_b}).scalar_one()
        assert bypass_count == 2

        # Step 5 -- the bypass must not leak into ordinary tenant sessions.
        with engine.connect() as conn, conn.begin():
            conn.execute(text("SELECT set_config('app.hotel_id', :hotel_id, true)"), {"hotel_id": str(hotel_a)})
            scoped_count = conn.execute(count_sql, {"a": hotel_a, "b": hotel_b}).scalar_one()
        assert scoped_count == 1, "A tenant-scoped session must only see its own hotel's row"
    finally:
        with engine.connect() as conn, conn.begin():
            conn.execute(text("SELECT set_config('app.master_admin', 'true', true)"))
            conn.execute(text("DELETE FROM subscriptions WHERE hotel_id IN (:a, :b)"), {"a": hotel_a, "b": hotel_b})
            conn.execute(text("DELETE FROM hotel_configuration WHERE id IN (:a, :b)"), {"a": hotel_a, "b": hotel_b})
        engine.dispose()


@skip_if_no_pg
def test_master_admin_dashboard_reads_hotels_without_outbox_rls_failure(monkeypatch):
    """A master-admin dashboard read may seed a missing subscription safely.

    Snapshot generation can flush a subscription and its durable domain events.
    The dashboard must set each tenant context for those writes while retaining
    the verified master-admin context needed to enumerate hotels.
    """
    from fastapi import Request
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from app.master_admin import router as master_admin_router
    from app.models.hotel_config import HotelConfiguration
    from app.models.subscription import (
        HotelEntitlementOverride,
        HotelSubscription,
        SubscriptionEntitlement,
        SubscriptionPlan,
    )
    from app.services import subscription_entitlements

    safe_dsn = validate_postgres_test_target(PG_DSN, os.environ)
    cwd = os.path.dirname(os.path.dirname(__file__))
    env = {**os.environ, "DATABASE_URL": safe_dsn}
    _reset_and_migrate_to_head(safe_dsn, env, cwd)

    engine = create_engine(safe_dsn)
    hotel_ids = (99203, 99204)
    try:
        # This legacy catalog table is created by the app's metadata bootstrap
        # rather than an Alembic migration; ensure the isolated DB matches that
        # runtime setup before exercising the snapshot path.
        from app.database import Base

        Base.metadata.create_all(
            engine,
            tables=[
                SubscriptionPlan.__table__,
                HotelSubscription.__table__,
                SubscriptionEntitlement.__table__,
                HotelEntitlementOverride.__table__,
            ],
        )
        # Create a tenant with no v2 subscription. Flush twice so its own
        # outbox rows are persisted before the transaction commits.
        with Session(engine) as session, session.begin():
            session.execute(text("SELECT set_config('app.master_admin', 'true', true)"))
            for hotel_id in hotel_ids:
                session.execute(
                    text("SELECT set_config('app.hotel_id', :hotel_id, true)"),
                    {"hotel_id": str(hotel_id)},
                )
                session.add(
                    HotelConfiguration(
                        id=hotel_id,
                        hotel_name=f"PG master dashboard synthetic {hotel_id}",
                        owner_email=f"master-dashboard-{hotel_id}@example.test",
                        subscription_active=True,
                    )
                )
                session.flush()
                session.flush()

        def authorize_master_admin(*, request, db, write=False):
            db.execute(text("SELECT set_config('app.master_admin', 'true', true)"))

        monkeypatch.setattr(master_admin_router, "require_master_admin", authorize_master_admin)
        monkeypatch.setattr(subscription_entitlements, "_is_enforcement_enabled", lambda: False)
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/master-admin/dashboard/hotels",
                "headers": [],
                "query_string": b"",
            }
        )

        with Session(engine) as session:
            result = master_admin_router.dashboard_hotels(request=request, db=session)
            matching = [item for item in result["items"] if item["hotel_id"] in hotel_ids]
            assert len(matching) == len(hotel_ids)
            assert {item["status"] for item in matching} == {"active"}
            session.rollback()
    finally:
        engine.dispose()
