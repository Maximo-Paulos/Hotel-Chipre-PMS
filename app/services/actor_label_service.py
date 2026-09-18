"""Tenant-scoped actor display labels for operational read projections."""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models.hotel_membership import HotelMembership
from app.models.user import User


_ACTOR_ID_CHUNK_SIZE = 500


def resolve_hotel_actor_labels(
    db: Session,
    *,
    hotel_id: int,
    user_ids: Iterable[int | None],
) -> dict[int, str]:
    """Resolve current per-hotel aliases, falling back to email, in bounded batches.

    Actor identity remains the immutable user id on the event. This function
    only supplies the display name and never looks up another hotel's alias.
    """

    ids = sorted({user_id for user_id in user_ids if user_id is not None})
    if not ids:
        return {}

    labels: dict[int, str] = {}
    for start in range(0, len(ids), _ACTOR_ID_CHUNK_SIZE):
        batch = ids[start : start + _ACTOR_ID_CHUNK_SIZE]
        rows = (
            db.query(HotelMembership.user_id, HotelMembership.alias, User.email)
            .join(User, User.id == HotelMembership.user_id)
            .filter(
                HotelMembership.hotel_id == hotel_id,
                HotelMembership.user_id.in_(batch),
            )
            .all()
        )
        for user_id, alias, email in rows:
            label = str(alias or "").strip() or str(email or "").strip()
            if label:
                labels[user_id] = label
    return labels
