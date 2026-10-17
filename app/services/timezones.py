"""
Timezone catalog helpers.

Keeps timezone lookup out of Postgres/Supabase dashboards and provides a
cached, process-local reference list for the app.
"""
from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
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


def business_clock_enabled_for_hotel(hotel_id: int) -> bool:
    """Return whether the explicitly selected local synthetic hotel may use
    its persisted business date.

    Every condition is required. In particular, Settings' implicit
    ``APP_ENV=development`` default does not enable time travel, nor does a
    local flag have any effect when the configured database is PostgreSQL.
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
    ):
        return False

    # Respect the legacy environment alias too. A conflicting production or
    # preview label must never be masked by a development value from .env.
    for name in ("APP_ENV", "ENVIRONMENT"):
        value = os.getenv(name)
        if value is not None and value.strip().lower() != "development":
            return False

    try:
        return make_url(settings.DATABASE_URL).get_backend_name() == "sqlite"
    except (ArgumentError, TypeError, ValueError):
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
    if not business_clock_enabled_for_hotel(hotel_id):
        return real_local_today

    clock = db.get(HotelBusinessClock, hotel_id)
    return clock.business_date if clock is not None else real_local_today
