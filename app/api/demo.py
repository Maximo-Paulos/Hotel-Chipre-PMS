"""
Demo-only utilities: seed sample data and reset the database.
Exposed only when the DEMO_MODE environment flag is enabled.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - ensures all models are registered on Base.metadata
from app.database import Base, get_db

router = APIRouter(prefix="/api", tags=["Demo"])


def _require_demo_mode() -> None:
    """Guard endpoints so they only run in explicit demo mode."""
    if os.getenv("DEMO_MODE", "").lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(
            status_code=403,
            detail="Demo mode is disabled. Set DEMO_MODE=true to use this endpoint.",
        )


@router.post("/seed")
def seed_demo(db: Session = Depends(get_db)):
    """
    Populate the database with minimal demo data.
    Idempotent: running twice simply returns 'already_seeded'.
    """
    from app.models.room import Room
    from app.scripts.seed_demo import seed as run_seed_demo

    _require_demo_mode()
    already_seeded = db.query(Room).count() > 0
    run_seed_demo(db)
    status = "already_seeded" if already_seeded else "seeded"
    return {"status": status}


@router.post("/reset")
def reset_demo(db: Session = Depends(get_db)):
    """
    Drop and recreate all tables, then reseed demo data.
    Keeps the app in a known-good demo state for quick testing.
    """
    from app.scripts.seed_demo import seed as run_seed_demo

    _require_demo_mode()
    db.commit()  # ensure no pending transactions before DDL
    engine = db.get_bind()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    run_seed_demo(db)
    return {"status": "reset"}
