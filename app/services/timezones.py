"""
Timezone catalog helpers.

Keeps timezone lookup out of Postgres/Supabase dashboards and provides a
cached, process-local reference list for the app.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from functools import lru_cache
import ipaddress
import os
from typing import TYPE_CHECKING
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from zoneinfo import ZoneInfo, available_timezones

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Country -> (display name, primary IANA timezone). Curated for Argentina,
# LATAM, and the rest of the product's current market, not the full ISO list.
COUNTRY_TIMEZONES: dict[str, tuple[str, str]] = {
    "AR": ("Argentina", "America/Argentina/Buenos_Aires"),
    "UY": ("Uruguay", "America/Montevideo"),
    "CL": ("Chile", "America/Santiago"),
    "BR": ("Brasil", "America/Sao_Paulo"),
    "PY": ("Paraguay", "America/Asuncion"),
    "BO": ("Bolivia", "America/La_Paz"),
    "PE": ("Peru", "America/Lima"),
    "CO": ("Colombia", "America/Bogota"),
    "MX": ("Mexico", "America/Mexico_City"),
    "ES": ("Espana", "Europe/Madrid"),
    "US": ("Estados Unidos", "America/New_York"),
}


@lru_cache(maxsize=1)
def get_country_catalog() -> tuple[dict[str, str], ...]:
    """Return the curated country -> timezone catalog as {code, name, timezone} dicts."""
    return tuple(
        {"code": code, "name": name, "timezone": tz}
        for code, (name, tz) in COUNTRY_TIMEZONES.items()
    )


@lru_cache(maxsize=1)
def get_timezone_catalog() -> tuple[str, ...]:
    """
    Return a stable, sorted catalog of supported IANA timezone names.

    The set is cached for the lifetime of the process so repeated UI loads do
    not keep recomputing the catalog.
    """
    return tuple(sorted(available_timezones()))


def is_valid_timezone(timezone_name: str) -> bool:
    """Return True when the timezone exists in the supported catalog."""
    candidate = timezone_name.strip()
    if not candidate:
        return False
    return candidate in get_timezone_catalog()


def normalize_timezone(timezone_name: str) -> str:
    """Trim whitespace and validate the timezone name."""
    candidate = timezone_name.strip()
    if not is_valid_timezone(candidate):
        raise ValueError(f"Invalid timezone: {timezone_name}")
    return candidate


def local_today(timezone_name: str | None) -> date:
    """Today's calendar date in the hotel's own timezone.

    `date.today()` is the *server's* date. Render runs in UTC, so for a hotel
    in Argentina (UTC-3) every request between 21:00 and midnight local time
    gets tomorrow's date -- which is how the rate calendar ended up marking
    Monday as "Hoy" on a Sunday night. UTC stays the fallback for a missing or
    legacy-invalid configuration.
    """
    try:
        zone = ZoneInfo(normalize_timezone(timezone_name or ""))
    except (AttributeError, ValueError):
        zone = ZoneInfo("UTC")
    return datetime.now(zone).date()


def business_clock_enabled_for_hotel(hotel_id: int, db: "Session | None" = None) -> bool:
    """Return whether the explicitly selected local synthetic hotel may use
    its persisted business date.

    Every condition is required. In particular, Settings' implicit
    ``APP_ENV=development`` default does not enable time travel. PostgreSQL is
    eligible only when an exact database name is explicitly allowlisted, its
    configured and bound connections are loopback, and the session points to
    that same database.
    """
    from app.config import get_settings

    if not isinstance(hotel_id, int) or hotel_id <= 0:
        return False

    settings = get_settings()
    fields_set = getattr(settings, "model_fields_set", set())
    if (
        settings.APP_ENV != "development"
        or "APP_ENV" not in fields_set
        or not settings.LOCAL_SIMULATION_CLOCK_ENABLED
        or "LOCAL_SIMULATION_CLOCK_ENABLED" not in fields_set
        or settings.LOCAL_SIMULATION_CLOCK_HOTEL_ID != hotel_id
        or "EXTERNAL_EFFECTS_ENABLED" not in fields_set
        or settings.EXTERNAL_EFFECTS_ENABLED is not False
        or "CONNECTIONS_ENABLED" not in fields_set
        or settings.CONNECTIONS_ENABLED is not False
    ):
        return False

    # Respect the legacy environment alias too. A conflicting production or
    # preview label must never be masked by a development value from .env.
    for name in ("APP_ENV", "ENVIRONMENT"):
        value = os.getenv(name)
        if value is not None and value.strip().lower() != "development":
            return False

    try:
        configured_url = make_url(settings.DATABASE_URL)
        backend = configured_url.get_backend_name()
        if backend == "sqlite":
            return db is None or db.get_bind().dialect.name == "sqlite"
        if backend != "postgresql":
            return False

        if "LOCAL_SIMULATION_CLOCK_POSTGRES_DATABASE" not in fields_set:
            return False
        database_allowlist = (settings.LOCAL_SIMULATION_CLOCK_POSTGRES_DATABASE or "").strip()
        environment_hostaddr = os.getenv("PGHOSTADDR", "").strip()
        if environment_hostaddr:
            try:
                if not ipaddress.ip_address(environment_hostaddr).is_loopback:
                    return False
            except ValueError:
                return False
        if (
            not database_allowlist
            or configured_url.database != database_allowlist
            or configured_url.host not in {"127.0.0.1", "::1"}
            or bool(configured_url.query)
            or bool(os.getenv("PGSERVICE", "").strip())
            or db is None
        ):
            return False

        bound = db.get_bind()
        bound_url = getattr(bound, "url", None)
        if bound_url is None:
            bound_url = getattr(getattr(bound, "engine", None), "url", None)
        if bound.dialect.name != "postgresql" or bound_url is None:
            return False
        return (
            bound_url.database == configured_url.database
            and bound_url.host == configured_url.host
            and bound_url.port == configured_url.port
            and not bound_url.query
        )
    except (ArgumentError, AttributeError, TypeError, ValueError):
        return False


def hotel_timezone_name(db: "Session", hotel_id: int) -> str:
    """Return a valid timezone for this hotel, using UTC for legacy gaps."""
    from app.models.hotel_config import HotelConfiguration

    config = db.get(HotelConfiguration, hotel_id)
    try:
        return normalize_timezone(config.hotel_timezone if config else "")
    except (AttributeError, ValueError):
        return "UTC"


def hotel_today(db: "Session", hotel_id: int) -> date:
    """Return the hotel's current business date.

    Prefer `local_today(config.hotel_timezone)` where the caller already holds
    the HotelConfiguration -- inside a request the identity map makes the
    lookup below free, but it is still a query the caller may not need. Only
    the one explicitly configured synthetic hotel may use a simulated date;
    security, audit, session, invitation, token, and provider timestamps must
    continue using real UTC time directly.
    """
    from app.models.hotel_config import HotelConfiguration
    from app.models.business_clock import HotelBusinessClock

    config = db.get(HotelConfiguration, hotel_id)
    real_local_today = local_today(config.hotel_timezone if config else None)
    if not business_clock_enabled_for_hotel(hotel_id, db):
        return real_local_today

    clock = db.get(HotelBusinessClock, hotel_id)
    return clock.business_date if clock is not None else real_local_today


def hotel_business_now(db: "Session", hotel_id: int) -> datetime:
    """Return an operational timestamp on the hotel's current business date.

    Security, audit, session, invitation, token, and provider timestamps must
    use real UTC directly. Hotel actions use this clock so local simulations
    can move operational dates while retaining the current hotel-local time of
    day. Outside the explicitly enabled local simulation, this is the
    real UTC timestamp.
    """
    real_now = datetime.now(timezone.utc)
    if not business_clock_enabled_for_hotel(hotel_id, db):
        return real_now

    timezone_name = hotel_timezone_name(db, hotel_id)
    try:
        hotel_timezone = ZoneInfo(normalize_timezone(timezone_name))
    except (AttributeError, ValueError):
        hotel_timezone = ZoneInfo("UTC")

    local_wall_time = real_now.astimezone(hotel_timezone).timetz().replace(tzinfo=None)
    business_local_time = datetime.combine(
        hotel_today(db, hotel_id),
        local_wall_time,
        tzinfo=hotel_timezone,
    )
    return business_local_time.astimezone(timezone.utc)


def utc_naive(value: datetime) -> datetime:
    """Normalize UTC timestamps for legacy ``DateTime`` columns without TZ."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
