from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from app.api.operational_tasks import (
    create_operational_task,
    get_operational_task_history,
    patch_operational_task,
)
from app.api import operational_tasks as operational_tasks_api
from app.models.hotel_membership import HotelMembership
from app.models.operational_task import (
    OperationalTask,
    OperationalTaskPriorityEnum,
    OperationalTaskStatusEnum,
    OperationalTaskTypeEnum,
)
from app.models.room_block import RoomBlock, RoomBlockReasonEnum
from app.models.user import User
from app.api.operational_tasks import get_operational_tasks
from app.dependencies.auth import AuthContext
from app.schemas.operational_tasks import OperationalTaskCreate, OperationalTaskUpdate
from app.schemas.reservation import ReservationCreate
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
    task_history,
    task_author_labels,
    update_task,
    validate_task_operator_scope,
)
from app.services.permission_service import (
    PERMISSION_OPERATIONAL_TASK_MANAGE,
    PERMISSION_OPERATIONAL_TASK_READ,
    PERMISSION_RESERVATION_READ,
    ROLE_HOUSEKEEPING,
    ROLE_MANAGER,
    create_custom_role,
    ensure_permission_matrix_seeded,
    resolve,
    set_role_override,
)
from app.services.reservation_service import create_reservation


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


def test_task_comment_appends_history_without_changing_task_status(db, hotel_config, sample_rooms):
    manager = _user(db, "commenter@example.test")
    task = create_task(
        db,
        hotel_id=1,
        task_type=OperationalTaskTypeEnum.HOUSEKEEPING,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Revisar ropa blanca",
        room_id=sample_rooms[0].id,
        created_by_user_id=manager.id,
    )

    updated = update_task(
        db,
        hotel_id=1,
        task_id=task.id,
        actor_user_id=manager.id,
        client_version=task.version,
        comment="Faltan toallas en el depósito.",
    )

    events = task_history(db, hotel_id=1, task_id=task.id)
    assert updated.status == OperationalTaskStatusEnum.PENDING
    assert updated.version == 1
    assert events[-1].from_status == OperationalTaskStatusEnum.PENDING
    assert events[-1].to_status == OperationalTaskStatusEnum.PENDING
    assert events[-1].comment == "Faltan toallas en el depósito."


def test_housekeeping_can_read_all_general_tasks_but_cannot_operate_them(db, hotel_config, sample_rooms):
    cleaner = _user(db, "cleaner@example.test", role=ROLE_HOUSEKEEPING)
    another_user = _user(db, "another-staff@example.test", role=ROLE_MANAGER)
    general = create_task(
        db,
        hotel_id=hotel_config.id,
        task_type=OperationalTaskTypeEnum.GENERAL,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Nota para el próximo turno",
        description="Llega un proveedor a la tarde.",
        assigned_to_user_id=another_user.id,
        created_by_user_id=another_user.id,
    )
    housekeeping = create_task(
        db,
        hotel_id=hotel_config.id,
        task_type=OperationalTaskTypeEnum.HOUSEKEEPING,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Preparar habitación",
        assigned_to_user_id=None,
        created_by_user_id=another_user.id,
    )
    assigned_elsewhere = create_task(
        db,
        hotel_id=hotel_config.id,
        task_type=OperationalTaskTypeEnum.MAINTENANCE,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Revisar equipo",
        assigned_to_user_id=another_user.id,
        created_by_user_id=another_user.id,
    )
    another_user.display_name = "Gerente de prueba"
    db.flush()

    context = AuthContext(
        hotel_id=hotel_config.id,
        user_id=cleaner.id,
        user_email=cleaner.email,
        user_role=ROLE_HOUSEKEEPING,
        is_verified=True,
    )
    visible = get_operational_tasks(
        status_filter=None,
        task_type=None,
        room_id=None,
        limit=100,
        db=db,
        context=context,
    )
    visible_ids = {task["id"] for task in visible}
    assert general.id in visible_ids
    assert housekeeping.id in visible_ids
    assert assigned_elsewhere.id not in visible_ids
    general_read = next(task for task in visible if task["id"] == general.id)
    assert general_read["description"] == "Llega un proveedor a la tarde."
    assert general_read["created_by_name"] == "Gerente de prueba"

    report = create_operational_task(
        OperationalTaskCreate(
            task_type=OperationalTaskTypeEnum.GENERAL,
            title="Reportar un problema operativo",
            description="Hace falta asistencia en el pasillo.",
        ),
        db=db,
        context=context,
    )
    assert report["task_type"] == OperationalTaskTypeEnum.GENERAL.value
    assert report["title"] == "Reportar un problema operativo"
    reported_task = db.query(OperationalTask).filter(OperationalTask.id == report["id"]).one()
    with pytest.raises(HTTPException) as report_update_error:
        patch_operational_task(
            reported_task.id,
            OperationalTaskUpdate(client_version=reported_task.version, status=OperationalTaskStatusEnum.IN_PROGRESS),
            db=db,
            context=context,
        )
    assert report_update_error.value.status_code == 403
    assert reported_task.status == OperationalTaskStatusEnum.PENDING

    history = get_operational_task_history(general.id, db=db, context=context)
    assert history[0]["actor_name"] == "Gerente de prueba"
    with pytest.raises(HTTPException) as error:
        patch_operational_task(
            general.id,
            OperationalTaskUpdate(client_version=general.version, status=OperationalTaskStatusEnum.IN_PROGRESS),
            db=db,
            context=context,
        )
    assert error.value.status_code == 403
    assert general.status == OperationalTaskStatusEnum.PENDING


def test_task_author_fallback_is_hotel_scoped_and_used_by_list_create_and_update(
    db,
    hotel_config,
    sample_rooms_hotel2,
):
    manager = _user(db, "author-fallback@example.test", role=ROLE_MANAGER)
    manager.display_name = None
    db.add(HotelMembership(hotel_id=2, user_id=manager.id, role="owner", status="active"))
    db.flush()

    assert task_author_labels(db, hotel_id=hotel_config.id, user_ids={manager.id}) == {manager.id: "Gerencia"}
    assert task_author_labels(db, hotel_id=2, user_ids={manager.id}) == {manager.id: "Dueño"}

    context = AuthContext(
        hotel_id=hotel_config.id,
        user_id=manager.id,
        user_email=manager.email,
        user_role=ROLE_MANAGER,
        is_verified=True,
    )
    listed_task = create_task(
        db,
        hotel_id=hotel_config.id,
        task_type=OperationalTaskTypeEnum.GENERAL,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Tarea existente",
        description="Descripción original.",
        created_by_user_id=manager.id,
    )
    visible = get_operational_tasks(
        status_filter=None,
        task_type=None,
        room_id=None,
        limit=100,
        db=db,
        context=context,
    )
    serialized = next(task for task in visible if task["id"] == listed_task.id)
    assert serialized["created_by_name"] == "Gerencia"
    assert serialized["description"] == "Descripción original."
    assert manager.email not in str(serialized)

    created = create_operational_task(
        OperationalTaskCreate(title="Tarea nueva", description="Con detalle."),
        db=db,
        context=context,
    )
    assert created["created_by_name"] == "Gerencia"
    assert created["description"] == "Con detalle."
    assert created["created_at"] is not None

    updated = patch_operational_task(
        created["id"],
        OperationalTaskUpdate(client_version=created["version"], description="Detalle actualizado."),
        db=db,
        context=context,
    )
    assert updated["created_by_name"] == "Gerencia"
    assert updated["description"] == "Detalle actualizado."
    assert updated["created_at"] == created["created_at"]


def test_task_create_does_not_commit_before_author_resolution(db, hotel_config, monkeypatch):
    manager = _user(db, "author-resolution-failure@example.test")
    context = AuthContext(
        hotel_id=hotel_config.id,
        user_id=manager.id,
        user_email=manager.email,
        user_role=ROLE_MANAGER,
        is_verified=True,
    )

    def fail_author_lookup(*_args, **_kwargs):
        raise RuntimeError("author lookup unavailable")

    monkeypatch.setattr(operational_tasks_api, "task_author_labels", fail_author_lookup)
    with pytest.raises(RuntimeError, match="author lookup unavailable"):
        create_operational_task(
            OperationalTaskCreate(title="No confirmar", description="Debe quedar sin guardar."),
            db=db,
            context=context,
        )

    db.rollback()
    assert db.query(OperationalTask).filter_by(hotel_id=hotel_config.id, title="No confirmar").count() == 0


def test_task_author_without_hotel_membership_does_not_expose_global_profile(db, hotel_config, sample_rooms_hotel2):
    observer = _user(db, "observer-task-author@example.test", role=ROLE_MANAGER)
    foreign_user = User(
        email="foreign-task-author@example.test",
        password_hash="test",
        display_name="Nombre de otro hotel",
        is_verified=True,
        is_active=True,
    )
    db.add(foreign_user)
    db.flush()
    db.add(HotelMembership(hotel_id=2, user_id=foreign_user.id, role="manager", status="active"))
    task = create_task(
        db,
        hotel_id=hotel_config.id,
        task_type=OperationalTaskTypeEnum.GENERAL,
        priority=OperationalTaskPriorityEnum.LOW,
        title="Tarea histórica sin membresía local",
    )
    task.created_by_user_id = foreign_user.id
    db.flush()

    labels = task_author_labels(db, hotel_id=hotel_config.id, user_ids={foreign_user.id})
    assert labels == {}
    visible = get_operational_tasks(
        status_filter=None,
        task_type=None,
        room_id=None,
        limit=100,
        db=db,
        context=AuthContext(
            hotel_id=hotel_config.id,
            user_id=observer.id,
            user_email=observer.email,
            user_role=ROLE_MANAGER,
            is_verified=True,
        ),
    )
    serialized = next(item for item in visible if item["id"] == task.id)
    assert serialized["created_by_name"] == "Personal del hotel"
    assert "Nombre de otro hotel" not in str(serialized)
    assert foreign_user.email not in str(serialized)


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


def test_custom_housekeeping_task_inbox_stays_in_housekeeping_lane(db, hotel_config):
    housekeeping_task = create_task(
        db,
        hotel_id=hotel_config.id,
        task_type=OperationalTaskTypeEnum.HOUSEKEEPING,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Preparar habitación para limpieza",
        created_by_user_id=None,
    )
    reception_task = create_task(
        db,
        hotel_id=hotel_config.id,
        task_type=OperationalTaskTypeEnum.GENERAL,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Llamar al huésped",
        created_by_user_id=None,
    )
    custom = create_custom_role(
        db,
        hotel_config.id,
        name="Limpieza de habitaciones",
        base_role=ROLE_HOUSEKEEPING,
        actor_user_id=None,
    )
    db.flush()
    db.commit()

    context = AuthContext(
        hotel_id=hotel_config.id,
        user_id=7001,
        user_email="custom-housekeeping@example.test",
        user_role=custom.code,
        base_role=ROLE_HOUSEKEEPING,
        is_verified=True,
    )
    tasks = get_operational_tasks(
        status_filter=None,
        task_type=None,
        room_id=None,
        limit=100,
        db=db,
        context=context,
    )
    task_ids = {task["id"] for task in tasks}
    assert housekeeping_task.id in task_ids
    assert reception_task.id in task_ids
    with pytest.raises(OperationalTaskError):
        validate_task_operator_scope(
            db,
            hotel_id=hotel_config.id,
            task_id=reception_task.id,
            role="housekeeping",
            user_id=7001,
        )


def test_report_only_custom_manager_cannot_read_or_mutate_out_of_scope_tasks(
    db, hotel_config, sample_guest, sample_rooms, monkeypatch
):
    other = _user(db, "other-manager-task@example.test")
    custom = create_custom_role(
        db,
        hotel_config.id,
        name="Coordinador de turno",
        base_role=ROLE_MANAGER,
        actor_user_id=None,
    )
    actor = _user(db, "limited-manager-task@example.test", role=custom.code)
    ensure_permission_matrix_seeded(db)
    for code in (
        PERMISSION_OPERATIONAL_TASK_READ,
        PERMISSION_OPERATIONAL_TASK_MANAGE,
        PERMISSION_RESERVATION_READ,
    ):
        set_role_override(
            db,
            hotel_config.id,
            custom.code,
            code,
            False,
            actor_user_id=None,
        )
    db.commit()
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_rooms[0].category_id,
            room_id=sample_rooms[0].id,
            check_in_date=date(2027, 12, 1),
            check_out_date=date(2027, 12, 3),
        ),
        hotel_id=hotel_config.id,
    )
    own_task = create_task(
        db,
        hotel_id=hotel_config.id,
        task_type=OperationalTaskTypeEnum.GENERAL,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Revisar nota del turno",
        reservation_id=reservation.id,
        assigned_to_user_id=actor.id,
        created_by_user_id=actor.id,
    )
    other_task = create_task(
        db,
        hotel_id=hotel_config.id,
        task_type=OperationalTaskTypeEnum.MAINTENANCE,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Inspección de caldera",
        assigned_to_user_id=other.id,
        created_by_user_id=other.id,
    )
    db.flush()
    db.commit()

    context = AuthContext(
        hotel_id=hotel_config.id,
        user_id=actor.id,
        user_email=actor.email,
        user_role=custom.code,
        base_role=ROLE_MANAGER,
        is_verified=True,
    )
    visible = get_operational_tasks(
        status_filter=None,
        task_type=None,
        room_id=None,
        limit=100,
        db=db,
        context=context,
    )
    assert [task["id"] for task in visible] == [own_task.id]
    assert visible[0]["reservation_id"] is None
    assert visible[0]["confirmation_code"] is None

    scope_checks = []
    original_scope_check = operational_tasks_api.validate_task_operator_read_scope

    def capture_scope_lock(*args, **kwargs):
        # Read-only history checks must not ask the validator to lock the task.
        assert "for_update" not in kwargs
        scope_checks.append(True)
        return original_scope_check(*args, **kwargs)

    monkeypatch.setattr(operational_tasks_api, "validate_task_operator_read_scope", capture_scope_lock)
    own_history = get_operational_task_history(own_task.id, db=db, context=context)
    assert len(own_history) == 1
    assert scope_checks == [True]

    with pytest.raises(HTTPException) as history_error:
        get_operational_task_history(other_task.id, db=db, context=context)
    assert history_error.value.status_code == 404
    with pytest.raises(HTTPException) as missing_history_error:
        get_operational_task_history(99999999, db=db, context=context)
    assert missing_history_error.value.status_code == 404
    assert history_error.value.detail == missing_history_error.value.detail

    with pytest.raises(HTTPException) as patch_error:
        patch_operational_task(
            other_task.id,
            OperationalTaskUpdate(client_version=0, status=OperationalTaskStatusEnum.IN_PROGRESS),
            db=db,
            context=context,
        )
    assert patch_error.value.status_code == 403
    assert other_task.status == OperationalTaskStatusEnum.PENDING
    with pytest.raises(HTTPException) as missing_patch_error:
        patch_operational_task(
            99999999,
            OperationalTaskUpdate(client_version=0, status=OperationalTaskStatusEnum.IN_PROGRESS),
            db=db,
            context=context,
        )
    assert missing_patch_error.value.status_code == 403
    assert patch_error.value.detail == missing_patch_error.value.detail

    assert resolve(db, hotel_config.id, custom.code, PERMISSION_OPERATIONAL_TASK_MANAGE, user_id=actor.id) is False

    with pytest.raises(HTTPException) as assignment_error:
        create_operational_task(
            OperationalTaskCreate(
                title="Asignación ajena",
                assigned_to_user_id=other.id,
            ),
            db=db,
            context=context,
        )
    assert assignment_error.value.status_code == 403

    reservation_link_errors = []
    for reservation_id in (reservation.id, 99999999):
        with pytest.raises(HTTPException) as link_error:
            create_operational_task(
                OperationalTaskCreate(title="Consultar reserva", reservation_id=reservation_id),
                db=db,
                context=context,
            )
        reservation_link_errors.append((link_error.value.status_code, link_error.value.detail))
    assert reservation_link_errors == [
        (403, "No tenés permisos para vincular una reserva"),
        (403, "No tenés permisos para vincular una reserva"),
    ]

    manager = _user(db, "full-manager-task@example.test", role=ROLE_MANAGER)
    manager_context = AuthContext(
        hotel_id=hotel_config.id,
        user_id=manager.id,
        user_email=manager.email,
        user_role=ROLE_MANAGER,
        is_verified=True,
    )
    manager_tasks = get_operational_tasks(
        status_filter=None,
        task_type=None,
        room_id=None,
        limit=100,
        db=db,
        context=manager_context,
    )
    assert {task["id"] for task in manager_tasks} == {own_task.id, other_task.id}


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


def test_task_list_resolves_reservation_context_permission_once_for_multiple_tasks(monkeypatch, db, hotel_config):
    manager = _user(db, "task-list-permission-check@example.test", role=ROLE_MANAGER)
    for index in range(4):
        create_task(
            db,
            hotel_id=hotel_config.id,
            task_type=OperationalTaskTypeEnum.GENERAL,
            priority=OperationalTaskPriorityEnum.MEDIUM,
            title=f"Tarea {index}",
            created_by_user_id=manager.id,
        )
    context = AuthContext(
        hotel_id=hotel_config.id,
        user_id=manager.id,
        user_email=manager.email,
        user_role=ROLE_MANAGER,
        is_verified=True,
    )
    original_check = operational_tasks_api._can_read_reservation_context
    permission_checks = 0

    def count_permission_checks(*args, **kwargs):
        nonlocal permission_checks
        permission_checks += 1
        return original_check(*args, **kwargs)

    monkeypatch.setattr(operational_tasks_api, "_can_read_reservation_context", count_permission_checks)
    visible = get_operational_tasks(
        status_filter=None,
        task_type=None,
        room_id=None,
        limit=100,
        db=db,
        context=context,
    )

    assert len(visible) == 4
    assert permission_checks == 1


def test_list_tasks_does_not_query_unreturned_relationships(db, hotel_config):
    hotel_id = hotel_config.id
    manager = _user(db, "task-list-loader-check@example.test", role=ROLE_MANAGER)
    create_task(
        db,
        hotel_id=hotel_id,
        task_type=OperationalTaskTypeEnum.GENERAL,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Tarea con historial interno",
        created_by_user_id=manager.id,
    )
    db.commit()
    db.expunge_all()
    statements = []
    engine = db.get_bind()

    def capture_statement(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", capture_statement)
    try:
        tasks = list_tasks(db, hotel_id=hotel_id)
    finally:
        event.remove(engine, "before_cursor_execute", capture_statement)

    select_statements = [statement for statement in statements if statement.lstrip().startswith("select")]
    assert len(tasks) == 1
    assert len(select_statements) == 1
    assert "operational_task_events" not in select_statements[0]
    assert "shift_handoff_tasks" not in select_statements[0]
    assert "users" not in select_statements[0]
