"""
FastAPI routes for provider connections.
Exposes /api/connections/{provider}/connect with proper JSON serialization.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.connection import ConnectionCreate, ConnectionRead
from app.services.connection_service import upsert_connection, ConnectionError

router = APIRouter(prefix="/api/connections", tags=["Connections"])


@router.post("/{provider}/connect", response_model=ConnectionRead, status_code=status.HTTP_200_OK)
def connect_provider(provider: str, payload: ConnectionCreate, db: Session = Depends(get_db)):
    try:
        connection = upsert_connection(db, provider, payload.credentials, payload.settings)
        db.commit()
        db.refresh(connection)
        return connection
    except ConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
