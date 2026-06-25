from __future__ import annotations

from datetime import datetime
import json

import pytest

from app.config import get_settings
from app.models.audit_log import AuditLog
from app.models.guest import Guest, GuestRatingEnum
from app.models.hotel_config import HotelConfiguration
from app.models.user import User
from app.services.audit_projection import project_audit_to_mongo
from app.services.guest_service import set_rating


@pytest.fixture(autouse=True)
def mongo_off(monkeypatch):
    monkeypatch.setenv("MONGO_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _hotel(db, hotel_id: int) -> HotelConfiguration:
    hotel = HotelConfiguration(id=hotel_id, hotel_name=f"Mongo Audit {hotel_id}", subscription_active=True)
    db.add(hotel)
    db.flush()
    return hotel


def _user(db, user_id: int) -> User:
    user = User(
        id=user_id,
        email=f"mongo-audit-{user_id}@example.com",
        password_hash="test",
        is_active=True,
        is_verified=True,
        role="manager",
    )
    db.add(user)
    db.flush()
    return user


def _guest(db, hotel_id: int) -> Guest:
    guest = Guest(
        hotel_id=hotel_id,
        first_name="Mongo",
        last_name="Projection",
        document_type="DNI",
        document_number=f"MONGO-{hotel_id}",
        terms_accepted=True,
    )
    db.add(guest)
    db.flush()
    return guest


def test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(db):
    _hotel(db, 7301)
    _user(db, 730101)
    guest = _guest(db, 7301)

    result = set_rating(
        db,
        hotel_id=7301,
        guest_id=guest.id,
        rating=GuestRatingEnum.EXCELENTE,
        user_id=730101,
    )

    audit = db.query(AuditLog).filter_by(hotel_id=7301, table_name="guests", record_id=guest.id).one()
    assert result.rating == GuestRatingEnum.EXCELENTE
    assert audit.actor_user_id == 730101
    assert json.loads(audit.payload_after)["rating"] == GuestRatingEnum.EXCELENTE.value


def test_project_audit_to_mongo_with_mongo_off_is_noop():
    project_audit_to_mongo(
        {
            "hotel_id": 1,
            "table_name": "guests",
            "record_id": 2,
            "action": "update",
            "actor_user_id": None,
            "payload_before": None,
            "payload_after": "{}",
            "timestamp": "2026-01-01T00:00:00",
        }
    )


def test_audit_projection_document_shape_from_decorator(db, monkeypatch):
    _hotel(db, 7302)
    _user(db, 730201)
    guest = _guest(db, 7302)
    projected_docs: list[dict] = []
    monkeypatch.setattr("app.decorators.audit_hooks.project_audit_to_mongo", projected_docs.append)

    set_rating(
        db,
        hotel_id=7302,
        guest_id=guest.id,
        rating=GuestRatingEnum.COMPLICADO,
        user_id=730201,
    )

    assert len(projected_docs) == 1
    doc = projected_docs[0]
    assert set(doc) == {
        "hotel_id",
        "table_name",
        "record_id",
        "action",
        "actor_user_id",
        "payload_before",
        "payload_after",
        "timestamp",
    }
    assert doc["hotel_id"] == 7302
    assert doc["table_name"] == "guests"
    assert doc["record_id"] == guest.id
    assert doc["action"] == "update"
    assert doc["actor_user_id"] == 730201
    assert json.loads(doc["payload_before"])["rating"] == GuestRatingEnum.NORMAL.value
    assert json.loads(doc["payload_after"])["rating"] == GuestRatingEnum.COMPLICADO.value
    assert isinstance(datetime.fromisoformat(doc["timestamp"]), datetime)
