from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.api import operational_tasks as operational_tasks_api
from app.api.operational_tasks import get_operational_task_history
from app.dependencies.auth import AuthContext
from app.models.domain_event_outbox import DomainEventOutbox
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.operational_task import OperationalTaskEvent, OperationalTaskPriorityEnum, OperationalTaskTypeEnum
from app.models.user import User
from app.services.operational_task_service import create_task


def test_task_changes_publish_task_domain_and_history_uses_hotel_scoped_actor_labels(
    pg_session, monkeypatch
):
    db = pg_session
    hotel = HotelConfiguration(id=991108, hotel_name="Synthetic Task Realtime")
    foreign_hotel = HotelConfiguration(id=991109, hotel_name="Synthetic Foreign Hotel")
    local_actor = User(
        email="task-actor-pg@example.test",
        password_hash="synthetic-test-hash",
        display_name=None,
        is_active=True,
        is_verified=True,
    )
    foreign_actor = User(
        email="task-foreign-actor-pg@example.test",
        password_hash="synthetic-test-hash",
        display_name="Foreign Profile Name",
        is_active=True,
        is_verified=True,
    )
    db.add_all([hotel, foreign_hotel, local_actor, foreign_actor])
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=hotel.id, user_id=local_actor.id, role="manager", status="active"),
            HotelMembership(hotel_id=foreign_hotel.id, user_id=foreign_actor.id, role="owner", status="active"),
        ]
    )
    db.flush()

    task = create_task(
        db,
        hotel_id=hotel.id,
        task_type=OperationalTaskTypeEnum.GENERAL,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Synthetic task for realtime verification",
        created_by_user_id=local_actor.id,
    )
    db.add(
        OperationalTaskEvent(
            hotel_id=hotel.id,
            task_id=task.id,
            actor_user_id=foreign_actor.id,
            from_status="pending",
            to_status="pending",
            comment="Historical event from a non-member actor",
            created_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        )
    )
    db.flush()

    # The test isolates history projection; authorization itself is covered by
    # the existing operational-task contract tests.
    monkeypatch.setattr(operational_tasks_api, "_can", lambda *_args, **_kwargs: True)
    history = get_operational_task_history(
        task.id,
        db=db,
        context=AuthContext(
            hotel_id=hotel.id,
            user_id=local_actor.id,
            user_email=local_actor.email,
            user_role="manager",
            is_verified=True,
        ),
    )

    assert history[0]["actor_name"] == "Gerencia"
    assert history[1]["actor_name"] is None
    assert local_actor.email not in str(history)
    assert foreign_actor.email not in str(history)
    assert "Foreign Profile Name" not in str(history)

    task_event = (
        db.query(DomainEventOutbox)
        .filter_by(hotel_id=hotel.id, domain="tasks", event_type="operational_tasks.created")
        .one()
    )
    assert task_event.payload == {"task_id": task.id, "status": "pending"}
