"""Bind a SQLAlchemy transaction to the authenticated tenant.

PostgreSQL RLS policies read these transaction-local settings.  The helpers are
no-ops for SQLite so the existing local/test harness remains lightweight.
``set_config(..., is_local=true)`` is transaction-scoped by design, so a
commit silently clears it.  Every setter here also stashes its last-applied
value on ``session.info`` (survives commits, since it lives on the Session
object, not the transaction), and ``app.database``'s ``after_commit`` listener
reapplies those stashed values immediately after every commit -- so callers
no longer need to remember to re-set context by hand.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

_SESSION_INFO_KEY = "_tenant_settings"


def _apply_setting(db: Session, setting_name: str, setting_value: str) -> None:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    db.execute(
        text("SELECT set_config(:setting_name, :setting_value, true)"),
        {"setting_name": setting_name, "setting_value": setting_value},
    )


def _remember_setting(db: Session, setting_name: str, setting_value: str) -> None:
    """Stash the last value applied for ``setting_name`` on this session.

    ``session.info`` is a plain dict that lives on the Session instance and
    survives commits/rollbacks (unlike ``set_config(..., is_local=true)``),
    which is exactly what lets ``reapply_tenant_context`` restore it after a
    commit clears PostgreSQL's transaction-scoped setting.
    """
    db.info.setdefault(_SESSION_INFO_KEY, {})[setting_name] = setting_value


def _set_context_value(db: Session, setting_name: str, value: int | None) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"{setting_name} must be a positive integer")

    setting_value = "" if value is None else str(value)
    _remember_setting(db, setting_name, setting_value)
    _apply_setting(db, setting_name, setting_value)


def reapply_tenant_context(db: Session) -> None:
    """Reapply every ``set_config`` value this session set before a commit.

    Called from ``app.database``'s ``Session``-level ``after_commit`` event.
    No-op if this session never called a ``set_tenant_*``/
    ``set_master_admin_context`` helper (most sessions aren't tenant-scoped)
    or if the bind isn't PostgreSQL (``_apply_setting`` short-circuits there).
    """
    settings = db.info.get(_SESSION_INFO_KEY)
    if not settings:
        return
    for setting_name, setting_value in settings.items():
        _apply_setting(db, setting_name, setting_value)


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

    Same transaction-scoped caveat as set_tenant_hotel_context, but this is
    now handled automatically: the value is stashed on ``session.info`` and
    reapplied by ``app.database``'s ``after_commit`` listener.
    """
    setting_value = "true" if enabled else ""
    _remember_setting(db, "app.master_admin", setting_value)
    _apply_setting(db, "app.master_admin", setting_value)
