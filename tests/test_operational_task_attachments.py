import base64
import hashlib
from datetime import date, datetime, timezone

import pytest

from app.models.hotel_membership import HotelMembership
from app.models.business_clock import HotelBusinessClock
from app.models.operational_task import OperationalTaskPriorityEnum, OperationalTaskTypeEnum
from app.models.user import User
from app.services import operational_task_service, stored_object_service
from app.services.object_storage import ObjectStat
from app.services.operational_task_service import (
    OperationalTaskError,
    create_task,
    create_task_attachment,
    list_task_attachments,
    task_attachment_content,
)


class MemoryObjectStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, key, data, *, content_type=None):
        self.objects[key] = data

    def get_bytes(self, key):
        return self.objects[key]

    def delete(self, key):
        self.objects.pop(key, None)

    def stat(self, key):
        data = self.objects[key]
        return ObjectStat(byte_size=len(data), sha256_hex=hashlib.sha256(data).hexdigest())

    def get_signed_url(self, key, *, expires_seconds=300):
        raise AssertionError("Operational-task photos must use an authenticated content endpoint")


def _create_task_context(db, hotel_id):
    user = User(email=f"task-photo-{hotel_id}@example.test", password_hash="test", is_active=True, is_verified=True)
    db.add(user)
    db.flush()
    db.add(HotelMembership(hotel_id=hotel_id, user_id=user.id, role="manager", status="active"))
    db.flush()
    task = create_task(
        db,
        hotel_id=hotel_id,
        task_type=OperationalTaskTypeEnum.HOUSEKEEPING,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Revisar habitación",
        created_by_user_id=user.id,
    )
    return user, task


def test_task_photo_is_private_tenant_scoped_and_integrity_checked(db, hotel_config, monkeypatch):
    storage = MemoryObjectStorage()
    monkeypatch.setattr(stored_object_service, "get_object_storage", lambda: storage)
    monkeypatch.setattr(operational_task_service, "get_object_storage", lambda: storage)
    user, task = _create_task_context(db, hotel_config.id)
    image = b"\x89PNG\r\n\x1a\n" + b"test-image-bytes"
    attachment = create_task_attachment(
        db,
        hotel_id=hotel_config.id,
        task_id=task.id,
        actor_user_id=user.id,
        file_name="../../room photo.png",
        content_type="image/png",
        content_base64=base64.b64encode(image).decode("ascii"),
    )
    db.commit()

    listed = list_task_attachments(db, hotel_id=hotel_config.id, task_id=task.id)
    assert [item.id for item in listed] == [attachment.id]
    assert attachment.file_name == "room_photo.png"
    assert attachment.stored_object_id not in storage.objects
    content = task_attachment_content(
        db,
        hotel_id=hotel_config.id,
        task_id=task.id,
        attachment_id=attachment.id,
    )
    assert content["content_type"] == "image/png"
    assert content["byte_size"] == len(image)
    assert base64.b64decode(content["content_base64"]) == image

    with pytest.raises(OperationalTaskError, match="Foto no encontrada"):
        task_attachment_content(db, hotel_id=hotel_config.id + 1, task_id=task.id, attachment_id=attachment.id)

    storage.objects[next(iter(storage.objects))] = b"tampered image"
    with pytest.raises(OperationalTaskError, match="no está disponible"):
        task_attachment_content(db, hotel_id=hotel_config.id, task_id=task.id, attachment_id=attachment.id)


def test_task_photo_timestamp_uses_local_business_date(db, hotel_config, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///local-business-clock-test.db")
    monkeypatch.setenv("LOCAL_SIMULATION_CLOCK_ENABLED", "true")
    monkeypatch.setenv("LOCAL_SIMULATION_CLOCK_HOTEL_ID", str(hotel_config.id))
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "false")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_SIMULATION_CLOCK_POSTGRES_DATABASE", raising=False)
    get_settings.cache_clear()
    try:
        db.add(
            HotelBusinessClock(
                hotel_id=hotel_config.id,
                business_date=date(2041, 7, 8),
                advanced_at=datetime.now(timezone.utc),
            )
        )
        db.flush()

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                value = cls(2026, 10, 17, 21, 30, 12, tzinfo=timezone.utc)
                return value.astimezone(tz) if tz else value

        monkeypatch.setattr("app.services.timezones.datetime", FixedDateTime)
        storage = MemoryObjectStorage()
        monkeypatch.setattr(stored_object_service, "get_object_storage", lambda: storage)
        monkeypatch.setattr(operational_task_service, "get_object_storage", lambda: storage)
        user, task = _create_task_context(db, hotel_config.id)
        image = b"\x89PNG\r\n\x1a\n" + b"test-image-bytes"

        attachment = create_task_attachment(
            db,
            hotel_id=hotel_config.id,
            task_id=task.id,
            actor_user_id=user.id,
            file_name="room.png",
            content_type="image/png",
            content_base64=base64.b64encode(image).decode("ascii"),
        )

        assert attachment.created_at == datetime(2041, 7, 8, 21, 30, 12)
        assert attachment.created_at.tzinfo is None
    finally:
        get_settings.cache_clear()
