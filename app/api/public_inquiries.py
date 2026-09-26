"""Public contact form endpoint for the marketing site."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.public_inquiry import PublicInquiryAccepted, PublicInquiryCreate
from app.services.public_inquiry_service import (
    PublicInquiryRateLimitError,
    PublicInquiryUnavailableError,
    create_public_inquiry,
)

router = APIRouter(prefix="/api/public/inquiries", tags=["Public Inquiries"])


@router.post("", response_model=PublicInquiryAccepted, status_code=status.HTTP_201_CREATED)
def submit_public_inquiry(
    payload: PublicInquiryCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        create_public_inquiry(db, payload, request)
    except PublicInquiryUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El formulario de contacto no está disponible temporalmente. Intentá nuevamente más tarde.",
        ) from exc
    except PublicInquiryRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Recibimos demasiadas consultas desde este origen. Intentá nuevamente más tarde.",
            headers={"Retry-After": "900"},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Solicitud inválida") from exc
    return PublicInquiryAccepted()
