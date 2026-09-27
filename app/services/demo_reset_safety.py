"""Fail-closed safety checks for destructive local demo database resets."""
from __future__ import annotations

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from app.config import get_settings, is_demo_environment_allowed


class DemoResetSafetyError(RuntimeError):
    """The runtime or database target is not explicitly safe for a demo reset."""


_LOCAL_POSTGRES_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "db"})


def assert_demo_database_target_is_safe(database_url: str | URL | None = None) -> None:
    """Allow demo data operations only against an explicitly local database."""
    raw_url = database_url or get_settings().DATABASE_URL
    try:
        url = raw_url if isinstance(raw_url, URL) else make_url(raw_url)
    except (ArgumentError, TypeError, ValueError) as exc:
        raise DemoResetSafetyError("Demo database reset requires an approved local database.") from exc

    if url.get_backend_name() == "sqlite":
        return

    if (
        url.get_backend_name() == "postgresql"
        and (url.host or "").lower() in _LOCAL_POSTGRES_HOSTS
        and url.port in (None, 5432)
        and url.database == "hotel_pms"
        and not url.query
    ):
        return

    raise DemoResetSafetyError("Demo database reset requires an approved local database.")


def assert_demo_reset_is_safe(database_url: str | URL | None = None) -> None:
    """Allow destructive demo resets only in development against a local DB.

    The environment check prevents production/preview labels and conflicting
    runtime aliases from authorizing a reset. The target allowlist is separate:
    a process mislabeled as development must not be able to drop a hosted DB.
    """
    if not is_demo_environment_allowed():
        raise DemoResetSafetyError("Demo database reset is unavailable in this environment.")
    assert_demo_database_target_is_safe(database_url)
