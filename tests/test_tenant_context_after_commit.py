"""C1: after_begin listener reapplies transaction-scoped RLS tenant context.

``set_config(..., is_local=true)`` is transaction-scoped, so a commit clears
``app.hotel_id``/``app.user_id``/``app.master_admin`` -- see
app/services/tenant_context.py. These tests can't exercise real PostgreSQL
RLS (SQLite is a no-op dialect for these helpers), so they instead prove:

1. The listener is registered on the SQLAlchemy ``Session`` class and a
   normal SQLite commit flow is unaffected (flow-only, no-op assertion).
2. The reapplication mechanism itself: by stubbing the internal
   ``_apply_setting`` function (the only place that actually issues
   ``set_config``), we can watch it get called once when context is set and
   again -- with the identical value -- once the next statement after
   ``db.commit()`` lazily autobegins a new transaction and fires
   ``after_begin``, without needing a live PostgreSQL connection.

Listens on ``after_begin`` rather than ``after_commit`` deliberately: an
``after_commit`` handler only receives the ``Session``, which SQLAlchemy
considers to be in a transitional "committed" state where ``session.execute``
raises ``InvalidRequestError`` (proven by a real-Postgres regression in
tests/test_rls_live_verification.py before this fix). ``after_begin`` instead
fires once the next transaction (including the one SQLAlchemy autobegins
right after a commit) has actually started, and hands over the raw
``Connection`` to execute on directly.
"""
from __future__ import annotations

from sqlalchemy import event, text
from sqlalchemy.orm import Session

import app.database as app_database
from app.services import tenant_context


def test_after_begin_listener_is_registered_on_session_class():
    assert event.contains(Session, "after_begin", app_database._reapply_tenant_context)


def test_sqlite_commit_with_no_tenant_context_is_a_clean_noop(db):
    """Most sessions never call set_tenant_*; the listener must not touch them."""
    db.commit()  # would raise/log if reapply_tenant_context_on_connection misbehaved
    assert db.info.get("_tenant_settings") is None


def test_after_begin_reapplies_stashed_hotel_context(db, monkeypatch):
    calls: list[tuple[str, str]] = []

    def _spy_apply_setting(session, setting_name, setting_value, connection=None):
        calls.append((setting_name, setting_value))

    # Stub the one function that would issue `SELECT set_config(...)` against
    # a real PostgreSQL connection -- lets this run on the SQLite test session.
    monkeypatch.setattr(tenant_context, "_apply_setting", _spy_apply_setting)

    tenant_context.set_tenant_hotel_context(db, 42)
    assert calls == [("app.hotel_id", "42")]

    db.commit()
    db.execute(text("SELECT 1"))  # autobegins the next transaction, firing after_begin

    assert calls == [("app.hotel_id", "42"), ("app.hotel_id", "42")]


def test_after_begin_reapplies_master_admin_context(db, monkeypatch):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        tenant_context,
        "_apply_setting",
        lambda session, setting_name, setting_value, connection=None: calls.append(
            (setting_name, setting_value)
        ),
    )

    tenant_context.set_master_admin_context(db, enabled=True)
    db.commit()
    db.execute(text("SELECT 1"))  # autobegins the next transaction, firing after_begin

    assert calls == [("app.master_admin", "true"), ("app.master_admin", "true")]


def test_after_begin_reapplies_multiple_stashed_settings(db, monkeypatch):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        tenant_context,
        "_apply_setting",
        lambda session, setting_name, setting_value, connection=None: calls.append(
            (setting_name, setting_value)
        ),
    )

    tenant_context.set_tenant_context(db, user_id=7, hotel_id=42)
    calls.clear()  # only care about what the next after_begin reapplies

    db.commit()
    db.execute(text("SELECT 1"))  # autobegins the next transaction, firing after_begin

    assert set(calls) == {("app.user_id", "7"), ("app.hotel_id", "42")}
