"""
Reference data endpoints used by the frontend.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.timezones import get_country_catalog, get_timezone_catalog

router = APIRouter(prefix="/api/reference", tags=["Reference"])


class ReferenceCountry(BaseModel):
    code: str
    name: str
    timezone: str


@router.get("/timezones", response_model=list[str])
def list_timezones() -> list[str]:
    """Return the cached IANA timezone catalog."""
    return list(get_timezone_catalog())


@router.get("/countries", response_model=list[ReferenceCountry])
def list_countries() -> list[dict[str, str]]:
    """Return the curated country -> primary IANA timezone catalog."""
    return list(get_country_catalog())
