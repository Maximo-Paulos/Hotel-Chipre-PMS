"""
Timezone catalog helpers.

Keeps timezone lookup out of Postgres/Supabase dashboards and provides a
cached, process-local reference list for the app.
"""
from functools import lru_cache
from zoneinfo import available_timezones


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
