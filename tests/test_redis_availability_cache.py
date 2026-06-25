from __future__ import annotations

from datetime import date
import json

import pytest

from app.api.rooms import room_availability
from app.config import get_settings
from app.dependencies.auth import AuthContext
from app.schemas.reservation import ReservationCreate
from app.services import read_model_cache
from app.services.reservation_service import create_reservation


@pytest.fixture(autouse=True)
def read_model_cache_off(monkeypatch):
    monkeypatch.setenv("READ_MODEL_CACHE_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def get(self, key: str):
        return self.store.get(key)

    def setex(self, key: str, ttl_seconds: int, value: str):
        self.store[key] = value
        self.ttls[key] = ttl_seconds


def test_availability_with_cache_off_falls_back_to_postgres(db, sample_categories, sample_rooms, sample_guest, hotel_config):
    category = sample_categories[0]
    booked_room = next(room for room in sample_rooms if room.category_id == category.id)
    create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=category.id,
            room_id=booked_room.id,
            check_in_date=date(2026, 8, 1),
            check_out_date=date(2026, 8, 3),
            num_adults=1,
        ),
        hotel_id=hotel_config.id,
    )
    db.flush()

    payload = room_availability(
        category_id=category.id,
        check_in_date=date(2026, 8, 1),
        check_out_date=date(2026, 8, 3),
        db=db,
        context=AuthContext(hotel_id=hotel_config.id, user_id=1, user_role="manager", is_verified=True),
    )

    assert payload["status"] == "ok"
    assert booked_room.id not in payload["available_rooms"]
    assert payload["count"] == len([room for room in sample_rooms if room.category_id == category.id]) - 1


def test_availability_invalidator_does_not_raise_when_redis_off():
    read_model_cache.invalidate_hotel_operational_caches(1)


def test_availability_key_shape_and_serialization(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setenv("READ_MODEL_CACHE_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(read_model_cache, "_get_redis_client", lambda: fake_redis)

    payload = read_model_cache.get_cached_availability_payload(
        hotel_id=11,
        category_id=22,
        check_in=date(2026, 9, 1),
        check_out=date(2026, 9, 4),
        producer=lambda: {"status": "ok", "generated_on": date(2026, 9, 1), "available_rooms": [301]},
    )

    key = "hotel:11:availability:category:22:checkin:2026-09-01:checkout:2026-09-04"
    assert payload["available_rooms"] == [301]
    assert list(fake_redis.store) == [key]
    assert json.loads(fake_redis.store[key]) == {
        "available_rooms": [301],
        "generated_on": "2026-09-01",
        "status": "ok",
    }
    assert fake_redis.ttls[key] == get_settings().READ_MODEL_AVAILABILITY_TTL_SECONDS
