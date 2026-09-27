"""
Demo-only utilities: seed sample data and reset the database.
Exposed only when the DEMO_MODE environment flag is enabled.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import is_demo_environment_allowed, is_demo_mode, is_testing_mode
import app.models  # noqa: F401 - ensures all models are registered on Base.metadata
from app.database import Base, get_db
from app.services.demo_reset_safety import (
    DemoResetSafetyError,
    assert_demo_database_target_is_safe,
    assert_demo_reset_is_safe,
)

router = APIRouter(prefix="/api", tags=["Demo"])


def _require_demo_mode() -> None:
    """Guard demo mutations behind both an approved runtime and an explicit flag."""
    if not is_demo_environment_allowed():
        raise HTTPException(status_code=404)
    if is_testing_mode():
        return
    if not is_demo_mode():
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
    try:
        assert_demo_database_target_is_safe(db.get_bind().url)
    except DemoResetSafetyError as exc:
        db.rollback()
        raise HTTPException(status_code=404) from exc
    already_seeded = db.query(Room).count() > 0
    run_seed_demo(db)
    status = "already_seeded" if already_seeded else "seeded"
    return {"status": status}


@router.post("/reset")
def reset_demo(db: Session = Depends(get_db)):
    """
    Drop and recreate all tables.
    Keeps the app in a known-good empty state for quick testing; no autoseed.
    """

    _require_demo_mode()
    engine = db.get_bind()
    try:
        assert_demo_reset_is_safe(engine.url)
    except DemoResetSafetyError as exc:
        db.rollback()
        raise HTTPException(status_code=404) from exc
    db.commit()  # ensure no pending transactions before DDL
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return {"status": "reset_empty"}
