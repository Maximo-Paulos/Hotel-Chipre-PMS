"""Bind a SQLAlchemy transaction to the authenticated tenant.

PostgreSQL RLS policies read these transaction-local settings.  The helpers are
no-ops for SQLite so the existing local/test harness remains lightweight.  A
context must be set again after every commit because ``is_local=true`` makes it
transaction-scoped by design.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def _set_context_value(db: Session, setting_name: str, value: int | None) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"{setting_name} must be a positive integer")

    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    db.execute(
        text("SELECT set_config(:setting_name, :setting_value, true)"),
        {
            "setting_name": setting_name,
            "setting_value": "" if value is None else str(value),
        },
    )


def set_tenant_user_context(db: Session, user_id: int | None) -> None:
    """Set the authenticated user id used by membership RLS policies."""

    _set_context_value(db, "app.user_id", user_id)


def set_tenant_hotel_context(db: Session, hotel_id: int | None) -> None:
    """Set or clear the current hotel id for tenant-scoped RLS policies."""

    _set_context_value(db, "app.hotel_id", hotel_id)


def set_tenant_context(db: Session, *, user_id: int | None, hotel_id: int | None) -> None:
    """Set both principals for a request or a single-hotel worker job."""

    set_tenant_user_context(db, user_id)
    set_tenant_hotel_context(db, hotel_id)


def set_master_admin_context(db: Session, enabled: bool = True) -> None:
    """Flag the transaction as a verified master-admin session.

    RLS policies that opt in (see alembic/versions/f3bdaadd3d15_*) read
    ``current_setting('app.master_admin', true) = 'true'`` as an OR bypass
    of the normal ``hotel_id = app.hotel_id`` clause, so a real master-admin
    request (never any other caller) can see rows across every hotel. Call
    only from app/master_admin/security.py::require_master_admin, after the
    session/CSRF/lockout checks pass -- never from request input.

    Same transaction-scoped caveat as set_tenant_hotel_context: this must be
    re-set after any commit within the same request (tracked as C1, not
    fixed here).
    """
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    db.execute(
        text("SELECT set_config('app.master_admin', :value, true)"),
        {"value": "true" if enabled else ""},
    )
