"""Shared room query scopes."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.room import Room


def active_rooms(db: Session, hotel_id: int | None = None):
    """Return the rooms that currently exist for operational use.

    Soft-deleted rooms must never reach room counts, availability, or
    operator-facing lists. Restore and audit/history paths intentionally
    bypass this helper so they can address the original row.
    """
    query = db.query(Room).filter(Room.deleted_at.is_(None))
    if hotel_id is not None:
        query = query.filter(Room.hotel_id == hotel_id)
    return query
