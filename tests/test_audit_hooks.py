from __future__ import annotations

import json

from app.decorators.audit_hooks import audited_change
from app.models.audit_log import AuditActionEnum, AuditLog
from app.models.guest import Guest, GuestRatingEnum, GuestTagTypeEnum
from app.models.hotel_config import HotelConfiguration
from app.models.user import User
from app.services.guest_service import add_tag, set_rating


def _hotel(db, hotel_id: int) -> HotelConfiguration:
    hotel = HotelConfiguration(id=hotel_id, hotel_name=f"Audit Hook {hotel_id}", subscription_active=True)
    db.add(hotel)
    db.flush()
    return hotel


def _user(db, user_id: int) -> User:
    user = User(
        id=user_id,
        email=f"audit-hook-{user_id}@example.com",
        password_hash="test",
        is_active=True,
        is_verified=True,
        role="manager",
    )
    db.add(user)
    db.flush()
    return user


def _guest(db, hotel_id: int, *, suffix: str = "1") -> Guest:
    guest = Guest(
        hotel_id=hotel_id,
        first_name="Audit",
        last_name=f"Guest {suffix}",
        document_type="DNI",
        document_number=f"88000{hotel_id}{suffix}",
        terms_accepted=True,
    )
    db.add(guest)
    db.flush()
    return guest


def test_modifying_guest_creates_audit_log_with_before_after(db):
    _hotel(db, 7201)
    _user(db, 720101)
    guest = _guest(db, 7201)

    set_rating(
        db,
        hotel_id=7201,
        guest_id=guest.id,
        rating=GuestRatingEnum.COMPLICADO,
        user_id=720101,
    )

    audit = db.query(AuditLog).filter_by(table_name="guests", record_id=guest.id).one()
    before = json.loads(audit.payload_before)
    after = json.loads(audit.payload_after)

    assert audit.hotel_id == 7201
    assert audit.actor_user_id == 720101
    assert before["rating"] == GuestRatingEnum.NORMAL.value
    assert after["rating"] == GuestRatingEnum.COMPLICADO.value


def test_audit_failure_does_not_raise_from_decorated_function(db, monkeypatch):
    _hotel(db, 7202)
    guest = _guest(db, 7202)

    class RaisingAuditLog:
        def __init__(self, **kwargs):
            raise RuntimeError("audit sink unavailable")

    monkeypatch.setattr("app.decorators.audit_hooks.AuditLog", RaisingAuditLog)

    @audited_change(table_name="guests", action=AuditActionEnum.UPDATE)
    def change_guest(db, *, hotel_id: int, guest_id: int):
        guest = db.get(Guest, guest_id)
        guest.last_name = "Still Updated"
        db.flush()
        return guest

    result = change_guest(db, hotel_id=7202, guest_id=guest.id)

    assert result.last_name == "Still Updated"
    assert db.get(Guest, guest.id).last_name == "Still Updated"


def test_audit_log_uses_correct_hotel_id_isolation(db):
    _hotel(db, 7203)
    _hotel(db, 7204)
    guest_a = _guest(db, 7203, suffix="A")
    guest_b = _guest(db, 7204, suffix="B")

    set_rating(db, hotel_id=7204, guest_id=guest_b.id, rating=GuestRatingEnum.EXCELENTE)

    assert (
        db.query(AuditLog)
        .filter_by(hotel_id=7203, table_name="guests", record_id=guest_a.id)
        .count()
        == 0
    )
    audit = db.query(AuditLog).filter_by(hotel_id=7204, table_name="guests", record_id=guest_b.id).one()
    assert json.loads(audit.payload_after)["rating"] == GuestRatingEnum.EXCELENTE.value


def test_audit_log_has_correct_action_enum_value(db):
    _hotel(db, 7205)
    guest = _guest(db, 7205)

    add_tag(
        db,
        hotel_id=7205,
        guest_id=guest.id,
        tag_type=GuestTagTypeEnum.PROHIBIDO_ALOJAR,
        note="Manager review required",
    )

    audit = db.query(AuditLog).filter_by(table_name="guest_tags", hotel_id=7205).one()
    assert audit.action == AuditActionEnum.CREATE
    assert audit.action.value == "create"

