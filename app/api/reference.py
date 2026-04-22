"""
Reference data endpoints used by the frontend.
"""
from fastapi import APIRouter

from app.services.timezones import get_timezone_catalog

router = APIRouter(prefix="/api/reference", tags=["Reference"])


@router.get("/timezones", response_model=list[str])
def list_timezones() -> list[str]:
    """Return the cached IANA timezone catalog."""
    return list(get_timezone_catalog())
