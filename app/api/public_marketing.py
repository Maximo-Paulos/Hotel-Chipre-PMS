"""Unauthenticated endpoints the marketing site calls.

Nothing here touches hotel data. Both routes are reachable by anyone on the
internet, so the write path is rate limited, honeypotted and idempotent.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.adapters.rate_limiter import lead_capture_limiter
from app.database import get_db
from app.schemas.marketing import (
    LeadCreateRequest,
    LeadCreateResponse,
    PublicPricingResponse,
)
from app.services import marketing_service

router = APIRouter(prefix="/api/public", tags=["Public Marketing"])


def _request_source(request: Request) -> str:
    return (request.client.host if request.client else None) or "unknown"


@router.get("/pricing", response_model=PublicPricingResponse)
def public_pricing(response: Response, db: Session = Depends(get_db)):
    # The landing page is static apart from this call; a short shared cache
    # keeps a traffic spike off the database without making an edit in the
    # master-admin console take minutes to show up.
    response.headers["Cache-Control"] = "public, max-age=60, s-maxage=300"
    return PublicPricingResponse(**marketing_service.public_pricing(db))


@router.post("/leads", response_model=LeadCreateResponse, status_code=status.HTTP_200_OK)
def create_lead(
    payload: LeadCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    # A bot filling every field trips this; a person never sees the input.
    # Answer 200 anyway so the bot cannot tell the honeypot exists.
    if payload.company_website:
        return LeadCreateResponse()

    source_key = _request_source(request)
    if not lead_capture_limiter.allow(source_key, db=db):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Probá de nuevo en unos minutos.",
        )
    db.commit()

    marketing_service.record_lead(
        db,
        email=str(payload.email),
        source_key=source_key,
        name=payload.name,
        hotel_name=payload.hotel_name,
        rooms_estimate=payload.rooms_estimate,
        city=payload.city,
        phone=payload.phone,
        source=payload.source,
        utm=payload.utm,
    )
    db.commit()
    return LeadCreateResponse()
