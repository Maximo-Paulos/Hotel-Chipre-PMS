import pytest

from app.models.hotel_config import HotelConfiguration
from app.services.laundry_service import (
    LaundryError,
    add_item,
    create_batch,
    list_batches,
    transition_status,
)


def _seed_hotels(db):
    db.add_all([
        HotelConfiguration(id=1, subscription_active=True),
        HotelConfiguration(id=2, subscription_active=True),
    ])
    db.flush()


def test_laundry_batch_lifecycle_is_hotel_scoped(db):
    _seed_hotels(db)

    batch = create_batch(db, hotel_id=1, notes="Morning pickup", created_by_user_id=None)
    add_item(db, hotel_id=1, batch_id=batch.id, item_type="sheet", quantity=4)
    other_batch = create_batch(db, hotel_id=2, notes="Other hotel", created_by_user_id=None)
    db.commit()

    assert [item.batch_code for item in list_batches(db, hotel_id=1)] == [batch.batch_code]
    assert list_batches(db, hotel_id=2)[0].batch_code == other_batch.batch_code

    sent = transition_status(db, hotel_id=1, batch_id=batch.id, new_status="sent")
    assert sent.status == "sent"
    assert sent.sent_at is not None
    received = transition_status(db, hotel_id=1, batch_id=batch.id, new_status="received")
    assert received.status == "received"
    assert received.received_at is not None
    closed = transition_status(db, hotel_id=1, batch_id=batch.id, new_status="closed")

    assert closed.status == "closed"
    assert closed.sent_at is not None
    assert closed.received_at is not None

    with pytest.raises(LaundryError):
        add_item(db, hotel_id=2, batch_id=batch.id, item_type="towel", quantity=1)


def test_laundry_invalid_status_transition_is_rejected(db):
    _seed_hotels(db)
    batch = create_batch(db, hotel_id=1, notes=None, created_by_user_id=None)
    db.flush()

    with pytest.raises(LaundryError):
        transition_status(db, hotel_id=1, batch_id=batch.id, new_status="received")
