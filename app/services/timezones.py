"""
Timezone catalog helpers.

Keeps timezone lookup out of Postgres/Supabase dashboards and provides a
cached, process-local reference list for the app.
"""
from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones


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
