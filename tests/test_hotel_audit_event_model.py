from __future__ import annotations

from app.models.analytics import HotelAuditEvent
from app.models.hotel_config import HotelConfiguration


def test_hotel_audit_event_allows_system_actor(db):
    hotel = HotelConfiguration(id=506, hotel_name="System Actor Hotel", subscription_active=True)
    db.add(hotel)
    db.flush()

    event = HotelAuditEvent(
        hotel_id=hotel.id,
        user_id=None,
        action_code="system.sync.completed",
        entity_type="ota_sync",
    )
    db.add(event)
    db.commit()

    saved = db.get(HotelAuditEvent, event.id)
    assert saved is not None
    assert saved.user_id is None
