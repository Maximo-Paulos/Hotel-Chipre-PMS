"""Exact, case-insensitive lookup helpers for user identity fields."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def find_user_by_email(db: Session, email: str | None) -> User | None:
    """Find an exact email match without treating SQL wildcard characters specially."""

    candidate_email = (email or "").strip()
    if not candidate_email:
        return None
    return (
        db.query(User)
        .filter(func.lower(User.email) == func.lower(candidate_email))
        .first()
    )
