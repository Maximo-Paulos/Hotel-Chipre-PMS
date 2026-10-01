"""Pydantic datetime types for values stored as UTC in naive DB columns."""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


UTCDateTime = Annotated[datetime, AfterValidator(_normalize_utc)]
