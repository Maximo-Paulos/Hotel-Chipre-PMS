from datetime import date, timedelta

import pytest

from app.models.hotel_membership import HotelMembership
from app.models.operational_task import (
    OperationalTaskPriorityEnum,
    OperationalTaskStatusEnum,
    OperationalTaskTypeEnum,
)
from app.models.room_block import RoomBlock, RoomBlockReasonEnum
from app.models.user import User
from app.services.room_block_service import RoomBlockReleaseConflictError, resolve_block
from app.services.operational_task_service import (
    OperationalTaskError,
    TaskVersionConflict,
    acknowledge_handoff,
    create_handoff,
    create_task,
    list_tasks,
    serialize_handoff,
    serialize_task,
    update_task,
    validate_task_operator_scope,
)


def _user(db, email: str, role: str = "manager") -> User:
    user = User(email=email, password_hash="test", is_verified=True, is_active=True)
    db.add(user)
    db.flush()
    db.add(HotelMembership(hotel_id=1, user_id=user.id, role=role, status="active"))
    db.flush()
    return user


def test_task_lifecycle_history_and_stale_version(db, hotel_config, sample_rooms):
    manager = _user(db, "manager@example.test")
    task = create_task(
        db,
        hotel_id=1,
        task_type=OperationalTaskTypeEnum.HOUSEKEEPING,
        priority=OperationalTaskPriorityEnum.HIGH,
        title="Preparar habitación",
        room_id=sample_rooms[0].id,
        created_by_user_id=manager.id,
        assigned_to_user_id=manager.id,
    )
    assert serialize_task(task)["room_number"] == sample_rooms[0].room_number
    assert len(task.events) == 1

    task = update_task(
        db,
        hotel_id=1,
        task_id=task.id,
        actor_user_id=manager.id,
        client_version=0,
        status=OperationalTaskStatusEnum.IN_PROGRESS,
        comment="Tomada por el turno",
    )
    assert task.version == 1
    with pytest.raises(TaskVersionConflict):
        update_task(
            db,
            hotel_id=1,
            task_id=task.id,
            actor_user_id=manager.id,
            client_version=0,
            status=OperationalTaskStatusEnum.PENDING_REVIEW,
        )

    task = update_task(
        db,
        hotel_id=1,
        task_id=task.id,
        actor_user_id=manager.id,
        client_version=1,
        status=OperationalTaskStatusEnum.RESOLVED,
    )
    assert task.resolved_by_user_id == manager.id
    assert len(task.events) == 3


def test_maintenance_task_keeps_block_until_authorized_release(db, hotel_config, sample_rooms):
    manager = _user(db, "maintenance@example.test")
    block = RoomBlock(
        hotel_id=1,
        room_id=sample_rooms[1].id,
        reason_code=RoomBlockReasonEnum.MAINTENANCE,
        starts_at=date.today(),
        ends_at=date.today() + timedelta(days=1),
        is_indefinite=False,
        created_by_user_id=manager.id,
    )
    db.add(block)
    db.flush()
    task = create_task(
        db,
        hotel_id=1,
        task_type=OperationalTaskTypeEnum.MAINTENANCE,
        priority=OperationalTaskPriorityEnum.CRITICAL,
        title="Revisar ducha",
        room_id=sample_rooms[1].id,
        room_block_id=block.id,
        created_by_user_id=manager.id,
    )
    with pytest.raises(RoomBlockReleaseConflictError, match="incidencia de mantenimiento"):
        resolve_block(db, hotel_id=1, block_id=block.id, resolved_by_user_id=manager.id)
    task = update_task(
        db,
        hotel_id=1,
        task_id=task.id,
        actor_user_id=manager.id,
        client_version=0,
        status=OperationalTaskStatusEnum.RESOLVED,
    )
    db.refresh(block)
    assert task.status == OperationalTaskStatusEnum.RESOLVED
    assert block.resolved_at is None
    resolved_block = resolve_block(db, hotel_id=1, block_id=block.id, resolved_by_user_id=manager.id)
    assert resolved_block.resolved_at is not None


def test_handoff_is_tenant_scoped_and_acknowledged(db, hotel_config, sample_rooms):
    manager = _user(db, "handoff@example.test")
    task = create_task(
        db,
        hotel_id=1,
        task_type=OperationalTaskTypeEnum.RECEPTION,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Llamar al huésped",
        created_by_user_id=manager.id,
    )
    handoff = create_handoff(db, hotel_id=1, delivered_by_user_id=manager.id, task_ids=[task.id], notes="Turno noche")
    assert serialize_handoff(handoff)["task_ids"] == [task.id]
    handoff = acknowledge_handoff(
        db,
        hotel_id=1,
        handoff_id=handoff.id,
        received_by_user_id=manager.id,
        client_version=0,
    )
    assert handoff.received_by_user_id == manager.id
    assert handoff.version == 1


def test_operator_scope_matches_role_and_assignment(db, hotel_config, sample_rooms):
    receptionist = _user(db, "scope-reception@example.test", role="receptionist")
    housekeeping = _user(db, "scope-housekeeping@example.test", role="housekeeping")
    task = create_task(
        db,
        hotel_id=hotel_config.id,
        task_type=OperationalTaskTypeEnum.HOUSEKEEPING,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Preparar habitación",
        room_id=sample_rooms[0].id,
        assigned_to_user_id=housekeeping.id,
        created_by_user_id=housekeeping.id,
    )

    assert validate_task_operator_scope(
        db,
        hotel_id=hotel_config.id,
        task_id=task.id,
        role="housekeeping",
        user_id=housekeeping.id,
    ) is task
    with pytest.raises(OperationalTaskError, match="acceso operativo"):
        validate_task_operator_scope(
            db,
            hotel_id=hotel_config.id,
            task_id=task.id,
            role="receptionist",
            user_id=receptionist.id,
        )


def test_task_links_cannot_cross_tenant(db, hotel_config, sample_rooms_hotel2):
    manager = _user(db, "tenant@example.test")
    with pytest.raises(OperationalTaskError):
        create_task(
            db,
            hotel_id=1,
            task_type=OperationalTaskTypeEnum.GENERAL,
            priority=OperationalTaskPriorityEnum.LOW,
            title="No cruzar hoteles",
            room_id=sample_rooms_hotel2[0].id,
            created_by_user_id=manager.id,
        )


def test_list_tasks_orders_priority_and_due_date(db, hotel_config):
    manager = _user(db, "order@example.test")
    late = create_task(
        db,
        hotel_id=1,
        task_type=OperationalTaskTypeEnum.GENERAL,
        priority=OperationalTaskPriorityEnum.HIGH,
        title="Alta tarde",
        due_at=date.today(),
        created_by_user_id=manager.id,
    )
    early = create_task(
        db,
        hotel_id=1,
        task_type=OperationalTaskTypeEnum.GENERAL,
        priority=OperationalTaskPriorityEnum.CRITICAL,
        title="Crítica",
        created_by_user_id=manager.id,
    )
    assert [row.id for row in list_tasks(db, hotel_id=1)] == [early.id, late.id]
